"""Évaluation d'une expérience exécutée (protocole d'évaluation, methode.md §4.2 à §4.4).

Usage : uv run python scripts/evaluate.py --exp experiments/EXP-…

Pour chaque jeu de `config.yaml` (corpus × partition) : lecture des références
(data/processed/<corpus>/rttm/), des UEM (data/splits/<corpus>/uem/) et des hypothèses
(rttm/ de l'expérience) ; écriture de `results_<corpus>_<partition>.json` (schéma §4.3) et
de `per_file_<corpus>_<partition>.csv` ; ajout d'une ligne par jeu à
results/leaderboard.csv. C'est le seul code qui écrit dans le leaderboard.

`arbre_propre` vaut true si l'exécution et l'évaluation ont eu lieu sur le même commit,
sans fichier modifié ni non suivi hors du dossier de l'expérience.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import yaml
from scipy.io import wavfile

from whospoke.evaluation.metrics import DiarizationEvaluator, round_rates
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

LEADERBOARD = REPO_ROOT / "results" / "leaderboard.csv"
LEADERBOARD_COLUMNS = [
    "exp_id", "date", "slug", "reference", "variable_modifiee", "corpus", "partition",
    "pipeline", "mode_n_locuteurs", "der_c0", "manquee_c0", "fausse_alarme_c0",
    "confusion_c0", "der_c025", "jer_c0", "mae_n_locuteurs", "rtf", "rtf_cpu", "git_commit",
]


def audio_duration(path: Path) -> float:
    sample_rate, data = wavfile.read(path, mmap=True)
    return data.shape[0] / sample_rate


def round2(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def timing_block(execution: dict, files: list[str]) -> dict:
    """Bloc `temps` d'un jeu : somme des temps de calcul de ses fichiers."""
    by_uri = {row["uri"]: row for row in execution["fichiers"]}
    audio = sum(by_uri[uri]["duree_audio_s"] for uri in files)
    compute = sum(by_uri[uri]["calcul_s"] for uri in files)
    return {
        "device": execution["device"],
        "chargement_modeles_s": round(execution["chargement_modeles_s"], 2),
        "calcul_s": round(compute, 2),
        "rtf": round(compute / audio, 4),
    }


def cpu_block(execution: dict | None) -> dict | None:
    if execution is None:
        return None
    return {
        "sous_ensemble": execution["sous_ensemble"],
        "duree_audio_s": round(execution["duree_audio_s"], 2),
        "calcul_s": round(execution["calcul_s"], 2),
        "rtf": round(execution["rtf"], 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--exp", required=True, type=Path, help="dossier de l'expérience")
    parser.add_argument("--leaderboard", type=Path, default=LEADERBOARD, help=argparse.SUPPRESS)
    args = parser.parse_args()
    leaderboard = args.leaderboard

    exp_dir = args.exp.resolve()
    config = yaml.safe_load((exp_dir / "config.yaml").read_text())
    main_run = json.loads((exp_dir / f"execution_{config['device']}.json").read_text())
    cpu_path = exp_dir / "execution_cpu.json"
    cpu_run = None
    if config.get("mesure_cpu") and config["device"] != "cpu":
        if not cpu_path.exists():
            sys.exit("Mesure CPU prévue par config.yaml mais execution_cpu.json absent")
        cpu_run = json.loads(cpu_path.read_text())
    elif config["device"] == "cpu":
        cpu_run = main_run

    runs = [main_run] + ([cpu_run] if cpu_run is not None and cpu_run is not main_run else [])
    state = git_state(exclude=exp_dir)
    commits = {run["git_commit"] for run in runs}
    clean = all(run["arbre_propre"] for run in runs) and commits == {state["commit"]} and state["clean"]
    if not clean:
        print(f"[évaluation] arbre_propre = false (commits {commits}, HEAD {state['commit']}, "
              f"non commités : {state['dirty']})", file=sys.stderr)

    existing = set()
    if leaderboard.exists():
        with leaderboard.open() as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != LEADERBOARD_COLUMNS:
                sys.exit("En-tête de results/leaderboard.csv différent de methode.md §4.4")
            existing = {(row["exp_id"], row["corpus"], row["partition"]) for row in reader}

    new_rows = []
    for jeu in config["jeux"]:
        corpus, partition = jeu["corpus"], jeu["partition"]
        key = (config["exp_id"], corpus, partition)
        if key in existing:
            sys.exit(f"{key} figure déjà dans le leaderboard : une évaluation n'est pas refaite")
        results_path = exp_dir / f"results_{corpus}_{partition}.json"
        if results_path.exists():
            sys.exit(f"{results_path.name} existe déjà")

        files = dataset_uris(jeu["liste"])
        evaluator = DiarizationEvaluator()
        durations = {}
        for uri in files:
            reference = load_rttm(reference_rttm(corpus, uri), uri)
            hypothesis = load_rttm(exp_dir / "rttm" / f"{uri}.rttm", uri)
            evaluator.add(reference, hypothesis, uem=load_uem(uem_path(corpus, uri), uri))
            durations[uri] = audio_duration(processed_wav(corpus, uri))
        report = evaluator.report()

        timing_by_uri = {row["uri"]: row for row in main_run["fichiers"]}
        rows = evaluator.per_file()
        for row in rows:
            timing = timing_by_uri[row["uri"]]
            row["duree_audio_s"] = round(durations[row["uri"]], 3)
            row["calcul_s"] = timing["calcul_s"]
            row["rtf"] = timing["rtf"]
        per_file_path = exp_dir / f"per_file_{corpus}_{partition}.csv"
        with per_file_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            for row in rows:
                writer.writerow({k: round(v, 4) if isinstance(v, float) else v for k, v in row.items()})

        metrics = {name: round_rates(report[name]) for name in ("collar_0", "collar_0_25")}
        results = {
            "exp_id": config["exp_id"],
            "slug": config["slug"],
            "date": main_run["date_fin"],
            "git_commit": main_run["git_commit"][:7],
            "arbre_propre": clean,
            "reference": config.get("reference"),
            "variable_modifiee": config.get("variable_modifiee"),
            "donnees": {
                "corpus": corpus,
                "partition": partition,
                "n_fichiers": len(files),
                "duree_audio_s": round(sum(durations.values()), 1),
            },
            "systeme": {
                "pipeline": config["pipeline"]["nom"],
                "mode_n_locuteurs": main_run["mode_n_locuteurs"],
                "vad": config["pipeline"].get("vad"),
                "device": main_run["device"],
            },
            "materiel": config.get("materiel"),
            "metriques": {
                "collar_0": metrics["collar_0"],
                "collar_0_25": metrics["collar_0_25"],
                "der_zones_sans_chevauchement": round2(report["der_zones_sans_chevauchement"]),
                "der_zones_chevauchement": round2(report["der_zones_chevauchement"]),
                "n_locuteurs": round_rates(report["n_locuteurs"]),
            },
            "temps": timing_block(main_run, files),
            "temps_cpu": cpu_block(cpu_run),
            "invalidee": None,
        }
        results_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")

        c0, c025 = metrics["collar_0"], metrics["collar_0_25"]
        new_rows.append({
            "exp_id": config["exp_id"], "date": results["date"], "slug": config["slug"],
            "reference": config.get("reference") or "", "variable_modifiee": config.get("variable_modifiee") or "",
            "corpus": corpus, "partition": partition, "pipeline": config["pipeline"]["nom"],
            "mode_n_locuteurs": main_run["mode_n_locuteurs"],
            "der_c0": c0["der"], "manquee_c0": c0["manquee"], "fausse_alarme_c0": c0["fausse_alarme"],
            "confusion_c0": c0["confusion"], "der_c025": c025["der"], "jer_c0": c0["jer"],
            "mae_n_locuteurs": results["metriques"]["n_locuteurs"]["erreur_absolue_moyenne"],
            "rtf": results["temps"]["rtf"],
            "rtf_cpu": "" if results["temps_cpu"] is None else results["temps_cpu"]["rtf"],
            "git_commit": results["git_commit"],
        })
        print(f"[évaluation] {corpus}/{partition} : {len(files)} fichiers, DER c0 {c0['der']:.2f} %, "
              f"c025 {c025['der']:.2f} %, JER {c0['jer']:.2f} %")

    write_header = not leaderboard.exists() or leaderboard.stat().st_size == 0
    with leaderboard.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEADERBOARD_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerows(new_rows)


if __name__ == "__main__":
    main()
