"""Exécution d'une expérience : hypothèses RTTM et mesures de temps (protocole §3.5, D19).

Usage :
    uv run python scripts/run_experiment.py --config experiments/EXP-…/config.yaml
    uv run python scripts/run_experiment.py --config … --trace
    uv run python scripts/run_experiment.py --config … --mesure-cpu

Mode normal : traite tous les fichiers des jeux de `config.yaml` sur le périphérique
`device`, écrit un RTTM par fichier dans `rttm/`, le journal `run.log` et les mesures
`execution_<périphérique>.json`.

Mode `--mesure-cpu` : traite en CPU seul le sous-ensemble de mesure du temps
(`mesure_cpu.liste`), sans écrire de RTTM, et écrit `execution_cpu.json`. Inutile quand
`device` vaut déjà `cpu` : scripts/evaluate.py tire alors `temps_cpu` de l'exécution
principale, restreinte aux fichiers de `mesure_cpu.liste`.

Clés de `config.yaml` lues ici (D19) :
- `mode_n_locuteurs` (`estime` par défaut, `borne` ou `oracle`) : en `oracle`, le nombre de
  locuteurs de chaque fichier est lu dans sa référence (locuteurs présents dans l'UEM) et
  passé au moteur à l'appel ;
- `detection_oracle` (false par défaut) : si vrai, les régions de parole de la référence
  dans l'UEM sont imposées au moteur (refusé par les moteurs qui ne le prennent pas en charge) ;
- `balayage` (facultatif) : réglage d'un paramètre sur une partition dev (D19 §4). Pour
  chaque valeur de `debut` à `fin` au pas `pas`, les fichiers du jeu de dev sont traités
  et évalués avec les métriques du protocole ; une ligne par valeur est écrite dans
  `balayage_<corpus>_<partition>.csv`. La valeur de plus faible DER sans collar est
  retenue (la plus petite en cas d'égalité), puis l'exécution normale de tous les jeux se
  fait avec cette seule valeur. Pour θ de la baseline, l'analyse, la détection, la
  segmentation, les représentations et la matrice de liaison sont calculées une seule
  fois par fichier ; seule la coupe et l'attribution sont refaites pour chaque valeur.

Option `--trace` : le moteur enregistre, pour chaque fichier, sa trace (D19 §3) dans
`trace/<uri>/` (non versionné). Sans effet sur les résultats.

Mesure du temps : le chargement des modèles est mesuré à part ; un préchauffage sur les
`prechauffage_s` premières secondes du premier fichier n'est pas compté ; le temps de
calcul de chaque fichier couvre la lecture du WAV normalisé et la pipeline complète, à
l'horloge murale, après synchronisation du périphérique. Le balayage est chronométré à
part et n'entre pas dans le RTF.

Alimentation (D21 §3) : l'état d'alimentation (`pmset -g batt` sur macOS) est relevé au
début de l'exécution, puis toutes les 60 s dans un fil d'arrière-plan, puis à la fin ; les
relevés sont consignés dans le bloc `alimentation` de `execution_<périphérique>.json`, d'où
scripts/evaluate.py tire `temps.conforme` (secteur pendant toute l'exécution).

Le code doit être commité avant l'exécution : l'état de l'arbre (chemins contrôlés de
D18) et la liste de tous les fichiers non commités sont consignés, puis repris par
scripts/evaluate.py (`arbre_propre`).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

import librosa
import numpy as np
import torch
import yaml
from pyannote.core import Segment, Timeline

from whospoke.audio import load_waveform
from whospoke.evaluation.metrics import DiarizationEvaluator
from whospoke.experiment import (
    REPO_ROOT,
    dataset_uris,
    git_state,
    load_rttm,
    load_uem,
    processed_wav,
    reference_rttm,
    uem_path,
)
from whospoke.pipelines.baseline import Baseline, save_trace
from whospoke.pipelines.pyannote_community1 import PyannoteCommunity1
from whospoke.power import PowerMonitor

PIPELINES = {PyannoteCommunity1.name: PyannoteCommunity1, Baseline.name: Baseline}

SWEEP_COLUMNS = [
    "valeur", "retenue", "der_c0", "manquee_c0", "fausse_alarme_c0", "confusion_c0", "jer_c0",
    "der_c025", "manquee_c025", "fausse_alarme_c025", "confusion_c025", "jer_c025",
    "der_zones_sans_chevauchement", "der_zones_chevauchement",
    "mae_n_locuteurs", "taux_exact_n_locuteurs", "n_locuteurs_moyen_hypothese",
    "n_locuteurs_moyen_reference",
]


def setup_logging(exp_dir: Path) -> logging.Logger:
    logger = logging.getLogger("run_experiment")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%dT%H:%M:%S%z")
    for handler in (logging.FileHandler(exp_dir / "run.log", encoding="utf-8"), logging.StreamHandler()):
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def reference_in_uem(corpus: str, uri: str):
    """Référence restreinte à l'UEM (base des oracles et du comptage, protocole §3.4)."""
    uem = load_uem(uem_path(corpus, uri), uri)
    return load_rttm(reference_rttm(corpus, uri), uri).crop(uem, mode="intersection"), uem


def oracle_inputs(config: dict, corpus: str, uri: str) -> tuple[int | None, Timeline | None]:
    """(nombre de locuteurs, régions de parole) imposés au moteur d'après la configuration."""
    mode = config.get("mode_n_locuteurs", "estime")
    oracle_speech = bool(config.get("detection_oracle", False))
    if mode != "oracle" and not oracle_speech:
        return None, None
    reference, _ = reference_in_uem(corpus, uri)
    num_speakers = len(reference.labels()) if mode == "oracle" else None
    speech = reference.get_timeline().support() if oracle_speech else None
    return num_speakers, speech


def sweep_values(spec: dict) -> list[float]:
    """Valeurs de `debut` à `fin` incluse, au pas `pas`, arrondies pour éviter la dérive."""
    n = int(round((spec["fin"] - spec["debut"]) / spec["pas"]))
    return [round(spec["debut"] + k * spec["pas"], 10) for k in range(n + 1)]


def sweep_row(value: float, report: dict, counts: list[tuple[int, int]]) -> dict:
    row = {"valeur": value}
    for name, suffix in (("collar_0", "c0"), ("collar_0_25", "c025")):
        for key in ("der", "manquee", "fausse_alarme", "confusion", "jer"):
            row[f"{key}_{suffix}"] = report[name][key]
    for zone in ("sans_chevauchement", "chevauchement"):
        row[f"der_zones_{zone}"] = report[f"der_zones_{zone}"]
    row["mae_n_locuteurs"] = report["n_locuteurs"]["erreur_absolue_moyenne"]
    row["taux_exact_n_locuteurs"] = report["n_locuteurs"]["taux_exact"]
    row["n_locuteurs_moyen_hypothese"] = float(np.mean([k_hyp for _, k_hyp in counts]))
    row["n_locuteurs_moyen_reference"] = float(np.mean([k_ref for k_ref, _ in counts]))
    return row


def run_sweep(config: dict, pipeline, exp_dir: Path, logger: logging.Logger) -> dict:
    """Balayage d'un réglage sur dev (D19 §4) ; écrit le CSV et renvoie le bloc consigné."""
    spec = config["balayage"]
    parameter = spec["parametre"]
    jeux = [jeu for jeu in config["jeux"] if jeu["partition"] == spec["partition"]]
    if spec["partition"] == "test" or len(jeux) != 1:
        sys.exit(f"Balayage : une seule partition de réglage attendue, jamais test ({spec['partition']!r})")
    if not (isinstance(pipeline, Baseline) and parameter == "theta"):
        sys.exit(f"Balayage de {parameter!r} non pris en charge pour {pipeline.name}")
    jeu = jeux[0]
    corpus, partition = jeu["corpus"], jeu["partition"]
    values = sweep_values(spec)
    logger.info("balayage de %s sur %s/%s : %d valeurs de %s à %s", parameter, corpus, partition,
                len(values), values[0], values[-1])

    t0 = time.perf_counter()
    prepared = []
    for uri in dataset_uris(jeu["liste"]):
        waveform, sample_rate = load_waveform(processed_wav(corpus, uri))
        num_speakers, speech = oracle_inputs(config, corpus, uri)
        truth = (load_rttm(reference_rttm(corpus, uri), uri), load_uem(uem_path(corpus, uri), uri))
        prepared.append((pipeline.prepare(waveform, sample_rate, uri=uri, speech=speech), num_speakers, truth))
        del waveform
    prepare_s = time.perf_counter() - t0
    logger.info("balayage : préparation de %d fichiers en %.1f s", len(prepared), prepare_s)

    rows, scores = [], []
    for value in values:
        evaluator = DiarizationEvaluator()
        counts = []
        for prep, num_speakers, (reference, uem) in prepared:
            annotation = pipeline.finish(prep, theta=value, num_speakers=num_speakers).annotation
            result = evaluator.add(reference, annotation, uem=uem)
            counts.append((result["n_locuteurs"]["reference"], result["n_locuteurs"]["hypothese"]))
        row = sweep_row(value, evaluator.report(), counts)
        rows.append(row)
        scores.append(row["der_c0"])
        logger.info("balayage %s = %s : DER c0 %.2f %%, %.2f locuteurs en moyenne",
                    parameter, value, row["der_c0"], row["n_locuteurs_moyen_hypothese"])
    best = int(np.argmin(scores))  # premier minimum : plus petite valeur en cas d'égalité
    chosen = values[best]

    path = exp_dir / f"balayage_{corpus}_{partition}.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SWEEP_COLUMNS)
        writer.writeheader()
        for index, row in enumerate(rows):
            row["retenue"] = index == best
            writer.writerow({k: round(v, 2) if isinstance(v, float) and k != "valeur" else v
                             for k, v in row.items()})
    sweep_s = time.perf_counter() - t0
    logger.info("balayage : %s retenu = %s (DER c0 %.2f %%), %.1f s au total",
                parameter, chosen, scores[best], sweep_s)
    pipeline.set_param(parameter, chosen)
    return {
        "parametre": parameter, "corpus": corpus, "partition": partition,
        "valeurs": values, "critere": "der collar_0 minimal", "valeur_retenue": chosen,
        "der_c0_retenu": round(scores[best], 2), "fichier": path.name,
        "preparation_s": round(prepare_s, 3), "calcul_s": round(sweep_s, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Clés de config.yaml, balayage et mesure du temps : voir l'en-tête du script.",
    )
    parser.add_argument("--config", required=True, type=Path, help="config.yaml de l'expérience (dans son dossier experiments/EXP-…)")
    parser.add_argument("--mesure-cpu", action="store_true", help="mesure en CPU seul sur le sous-ensemble mesure_cpu.liste (temps.txt), sans RTTM")
    parser.add_argument("--trace", action="store_true", help="enregistre la trace du moteur par fichier dans trace/<uri>/ (D19 §3, non versionnée)")
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
    trace_dir = exp_dir / "trace"

    logger = setup_logging(exp_dir)
    power = PowerMonitor()
    first = power.start()
    logger.info("alimentation au début : %s (%s)", first["source"] or "illisible", first["brut"])
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
    pipeline = PIPELINES[config["pipeline"]["nom"]](
        device=device_name, speaker_mode=config.get("mode_n_locuteurs"), trace=args.trace, **params,
    )
    loading_s = time.perf_counter() - t0
    logger.info("pipeline %s chargée sur %s en %.2f s (paramètres : %s, nombre de locuteurs : %s, "
                "détection oracle : %s, trace : %s)", pipeline.name, pipeline.device, loading_s, params,
                pipeline.speaker_mode, bool(config.get("detection_oracle", False)), args.trace)

    sweep = None
    if config.get("balayage"):
        if args.mesure_cpu:
            # La valeur retenue est celle de l'exécution principale.
            main_run = exp_dir / f"execution_{config['device']}.json"
            if not main_run.exists():
                sys.exit("Mesure CPU d'un balayage : exécuter d'abord l'expérience complète")
            retained = json.loads(main_run.read_text())["balayage"]
            pipeline.set_param(retained["parametre"], retained["valeur_retenue"])
            sweep = {"repris_de": main_run.name, **retained}
        else:
            sweep = run_sweep(config, pipeline, exp_dir, logger)

    # Préchauffage non compté, sur un extrait du premier fichier.
    warmup_s = float(config.get("prechauffage_s", 60.0))
    corpus0, _, uri0 = jobs[0]
    waveform, sample_rate = load_waveform(processed_wav(corpus0, uri0))
    t0 = time.perf_counter()
    num_speakers0, speech0 = oracle_inputs(config, corpus0, uri0)
    if speech0 is not None:
        speech0 = speech0.crop(Segment(0.0, warmup_s))  # régions ramenées à l'extrait
    trace_flag, pipeline.trace = pipeline.trace, False
    pipeline.run(waveform[:, : int(warmup_s * sample_rate)], sample_rate,
                 num_speakers=num_speakers0, speech=speech0)
    pipeline.trace = trace_flag
    logger.info("préchauffage : %.0f s de %s en %.2f s (non compté)", warmup_s, uri0, time.perf_counter() - t0)
    del waveform

    per_file = []
    for index, (corpus, partition, uri) in enumerate(jobs, start=1):
        num_speakers, speech = oracle_inputs(config, corpus, uri)
        t0 = time.perf_counter()
        waveform, sample_rate = load_waveform(processed_wav(corpus, uri))
        result = pipeline.run(waveform, sample_rate, uri=uri, num_speakers=num_speakers, speech=speech)
        compute_s = time.perf_counter() - t0
        annotation = result.annotation
        audio_s = waveform.shape[1] / sample_rate
        n_hyp = len(annotation.labels())
        if write_rttm:
            with (rttm_dir / f"{uri}.rttm").open("w") as handle:
                annotation.write_rttm(handle)
        if result.trace is not None:
            save_trace(result.trace, trace_dir / uri)
        per_file.append({
            "uri": uri, "corpus": corpus, "partition": partition,
            "duree_audio_s": round(audio_s, 3), "calcul_s": round(compute_s, 3),
            "rtf": round(compute_s / audio_s, 4), "n_locuteurs_hypothese": n_hyp,
            "n_locuteurs_impose": num_speakers,
            "etapes_s": {step: round(d, 3) for step, d in result.durees_etapes.items()},
        })
        logger.info("[%d/%d] %s %s : %.1f s d'audio, %.2f s de calcul, RTF %.4f, %d locuteurs%s",
                    index, len(jobs), partition, uri, audio_s, compute_s, compute_s / audio_s, n_hyp,
                    "" if num_speakers is None else f" (imposé : {num_speakers})")

    last = power.stop()
    power_block = power.block()
    logger.info("alimentation à la fin : %s ; %d relevés, conforme : %s", last["source"] or "illisible",
                len(power_block["releves"]), power_block["conforme"])
    if power_block["conforme"] is not True:
        logger.warning("temps de calcul non conforme au protocole §3.5 (secteur non attesté)")

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
                     "pyannote.audio": __import__("pyannote.audio").audio.__version__,
                     "librosa": librosa.__version__},
        "mode_n_locuteurs": pipeline.speaker_mode,
        "detection_oracle": bool(config.get("detection_oracle", False)),
        "trace": args.trace,
        "balayage": sweep,
        "configuration_effective": pipeline.describe_dict(),
        "chargement_modeles_s": round(loading_s, 3),
        "prechauffage": {"uri": uri0, "duree_s": warmup_s},
        "duree_audio_s": round(total_audio, 3),
        "calcul_s": round(total_compute, 3),
        "rtf": round(total_compute / total_audio, 4),
        "alimentation": power_block,
        "fichiers": per_file,
    }
    output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n")
    logger.info("total : %.1f s d'audio, %.1f s de calcul, RTF %.4f ; temps pour 30 min : %.0f s",
                total_audio, total_compute, total_compute / total_audio, 1800 * total_compute / total_audio)


if __name__ == "__main__":
    main()
