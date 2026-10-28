"""Exécution d'une expérience : hypothèses RTTM et mesures de temps (protocole §3.5).

Usage :
    uv run python scripts/run_experiment.py --config experiments/EXP-…/config.yaml
    uv run python scripts/run_experiment.py --config … --mesure-cpu

Mode normal : traite tous les fichiers des jeux de `config.yaml` sur le périphérique
`device`, écrit un RTTM par fichier dans `rttm/`, le journal `run.log` et les mesures
`execution_<périphérique>.json`.

Mode `--mesure-cpu` : traite en CPU seul le sous-ensemble de mesure du temps
(`mesure_cpu.liste`), sans écrire de RTTM, et écrit `execution_cpu.json`.

Mesure du temps : le chargement des modèles est mesuré à part ; un préchauffage sur les
`prechauffage_s` premières secondes du premier fichier n'est pas compté ; le temps de
calcul de chaque fichier couvre la lecture du WAV normalisé et la pipeline complète, à
l'horloge murale, après synchronisation du périphérique.

Le code doit être commité avant l'exécution : l'état de l'arbre (chemins contrôlés de
D18) et la liste de tous les fichiers non commités sont consignés, puis repris par
scripts/evaluate.py (`arbre_propre`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

import torch
import yaml

from whospoke.audio import load_waveform
from whospoke.experiment import (
    REPO_ROOT,
    dataset_uris,
    git_state,
    processed_wav,
)
from whospoke.pipelines.pyannote_community1 import PyannoteCommunity1

PIPELINES = {PyannoteCommunity1.name: PyannoteCommunity1}


def setup_logging(exp_dir: Path) -> logging.Logger:
    logger = logging.getLogger("run_experiment")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%dT%H:%M:%S%z")
    for handler in (logging.FileHandler(exp_dir / "run.log", encoding="utf-8"), logging.StreamHandler()):
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", required=True, type=Path, help="config.yaml de l'expérience (dans son dossier experiments/EXP-…)")
    parser.add_argument("--mesure-cpu", action="store_true", help="mesure en CPU seul sur le sous-ensemble mesure_cpu.liste (temps.txt), sans RTTM")
    args = parser.parse_args()

    config_path = args.config.resolve()
    exp_dir = config_path.parent
    config = yaml.safe_load(config_path.read_text())
    if not exp_dir.name.startswith(config["exp_id"]):
        sys.exit(f"Dossier {exp_dir.name} incohérent avec exp_id {config['exp_id']}")

    if args.mesure_cpu:
        device_name = "cpu"
        files = dataset_uris(config["mesure_cpu"]["liste"])
        corpus = config["mesure_cpu"]["corpus"]
        jobs = [(corpus, "temps", uri) for uri in files]
        write_rttm = False
    else:
        device_name = config["device"]
        jobs = [
            (jeu["corpus"], jeu["partition"], uri)
            for jeu in config["jeux"]
            for uri in dataset_uris(jeu["liste"])
        ]
        write_rttm = True
    output_json = exp_dir / f"execution_{device_name}.json"
    if output_json.exists():
        sys.exit(f"{output_json.relative_to(REPO_ROOT)} existe déjà : une expérience exécutée est immuable")
    rttm_dir = exp_dir / "rttm"
    if write_rttm:
        if rttm_dir.exists() and any(rttm_dir.iterdir()):
            sys.exit(f"{rttm_dir.relative_to(REPO_ROOT)} n'est pas vide : expérience déjà exécutée")
        rttm_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logging(exp_dir)
    state = git_state()
    logger.info("expérience %s, mode %s", config["exp_id"], "mesure CPU" if args.mesure_cpu else "complet")
    logger.info("commit %s, arbre propre (chemins contrôlés, D18) : %s", state["commit"], state["clean"])
    if state["dirty"]:
        level = logging.INFO if state["clean"] else logging.WARNING
        logger.log(level, "fichiers non commités : %s", ", ".join(state["dirty"]))
    logger.info(
        "python %s, torch %s, plateforme %s, fils torch %d",
        platform.python_version(), torch.__version__, platform.platform(), torch.get_num_threads(),
    )

    params = config["pipeline"].get("parametres") or {}
    t0 = time.perf_counter()
    pipeline = PIPELINES[config["pipeline"]["nom"]](device=device_name, **params)
    loading_s = time.perf_counter() - t0
    logger.info("pipeline %s chargée sur %s en %.2f s (paramètres : %s)",
                pipeline.name, pipeline.device, loading_s, params)

    # Préchauffage non compté, sur un extrait du premier fichier.
    warmup_s = float(config.get("prechauffage_s", 60.0))
    corpus0, _, uri0 = jobs[0]
    waveform, sample_rate = load_waveform(processed_wav(corpus0, uri0))
    t0 = time.perf_counter()
    pipeline(waveform[:, : int(warmup_s * sample_rate)], sample_rate)
    logger.info("préchauffage : %.0f s de %s en %.2f s (non compté)", warmup_s, uri0, time.perf_counter() - t0)
    del waveform

    per_file = []
    for index, (corpus, partition, uri) in enumerate(jobs, start=1):
        t0 = time.perf_counter()
        waveform, sample_rate = load_waveform(processed_wav(corpus, uri))
        annotation = pipeline(waveform, sample_rate, uri=uri)
        compute_s = time.perf_counter() - t0
        audio_s = waveform.shape[1] / sample_rate
        n_hyp = len(annotation.labels())
        if write_rttm:
            with (rttm_dir / f"{uri}.rttm").open("w") as handle:
                annotation.write_rttm(handle)
        per_file.append({
            "uri": uri, "corpus": corpus, "partition": partition,
            "duree_audio_s": round(audio_s, 3), "calcul_s": round(compute_s, 3),
            "rtf": round(compute_s / audio_s, 4), "n_locuteurs_hypothese": n_hyp,
        })
        logger.info("[%d/%d] %s %s : %.1f s d'audio, %.2f s de calcul, RTF %.4f, %d locuteurs",
                    index, len(jobs), partition, uri, audio_s, compute_s, compute_s / audio_s, n_hyp)

    total_audio = sum(row["duree_audio_s"] for row in per_file)
    total_compute = sum(row["calcul_s"] for row in per_file)
    result = {
        "exp_id": config["exp_id"],
        "mode": "mesure_cpu" if args.mesure_cpu else "complet",
        "sous_ensemble": config["mesure_cpu"]["liste"] if args.mesure_cpu else None,
        "date_fin": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_commit": state["commit"],
        "arbre_propre": state["clean"],
        "fichiers_non_commites": state["dirty"],
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "device": pipeline.device.type,
        "torch_threads": torch.get_num_threads(),
        "versions": {"python": platform.python_version(), "torch": torch.__version__,
                     "pyannote.audio": __import__("pyannote.audio").audio.__version__},
        "mode_n_locuteurs": pipeline.speaker_mode,
        "chargement_modeles_s": round(loading_s, 3),
        "prechauffage": {"uri": uri0, "duree_s": warmup_s},
        "duree_audio_s": round(total_audio, 3),
        "calcul_s": round(total_compute, 3),
        "rtf": round(total_compute / total_audio, 4),
        "fichiers": per_file,
    }
    output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    logger.info("total : %.1f s d'audio, %.1f s de calcul, RTF %.4f ; temps pour 30 min : %.0f s",
                total_audio, total_compute, total_compute / total_audio, 1800 * total_compute / total_audio)


if __name__ == "__main__":
    main()
