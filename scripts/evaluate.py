"""Évaluation d'une expérience exécutée (protocole d'évaluation, methode.md §4.2 à §4.4).

Usage :
    uv run python scripts/evaluate.py --exp experiments/EXP-…
    uv run python scripts/evaluate.py --exp experiments/EXP-… --requalifier

Pour chaque jeu de `config.yaml` (corpus × partition) : lecture des références
(data/processed/<corpus>/rttm/), des UEM (data/splits/<corpus>/uem/) et des hypothèses
(rttm/ de l'expérience) ; écriture de `results_<corpus>_<partition>.json` (schéma §4.3) et
de `per_file_<corpus>_<partition>.csv` ; ajout d'une ligne par jeu à
results/leaderboard.csv. C'est le seul code qui écrit dans le leaderboard.

Contrôle de configuration : l'empreinte `config_sha256` consignée dans chaque
`execution_*.json` doit correspondre au `config.yaml` de l'expérience ; sinon
l'évaluation est refusée (la configuration a changé depuis l'exécution).

`temps_cpu` : si `device` vaut `cpu`, il est tiré de l'exécution principale, restreinte
aux fichiers de `mesure_cpu.liste` ; sinon de `execution_cpu.json` (`--mesure-cpu`).

`arbre_propre` vaut true si les exécutions et l'évaluation ont eu lieu sur le même commit,
sans fichier non commité sous les chemins contrôlés de D18 (`whospoke.experiment.is_controlled`),
d'après les listes `fichiers_non_commites` consignées par les exécutions.

Mode `--requalifier` (D18, methode.md §4.2) : pour une expérience déjà évaluée, recalcule
`arbre_propre` à partir des `fichiers_non_commites` consignés dans ses `execution_*.json`,
et ajoute à chaque `results_*.json` un bloc `requalification` (date, règle, ancienne et
nouvelle valeur). Les métriques, les per_file et le leaderboard ne sont pas modifiés.
Si les exécutions portent sur des commits différents (amendement du 28/10/2026 de D18),
la requalification n'est admise que si chaque exécution est propre, si `git diff` entre
leurs commits est vide sur les chemins contrôlés et si leur `config_sha256` est le même ;
le bloc consigne alors `commits` et `"diff_chemins_controles": "vide"`. Sinon, elle est
refusée et rien n'est écrit (l'expérience est à refaire sous un nouveau numéro).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml
from scipy.io import wavfile

from whospoke.evaluation.metrics import DiarizationEvaluator, round_rates
from whospoke.experiment import (
    REPO_ROOT,
    dataset_uris,
    git_state,
    is_controlled,
    tree_is_clean,
    load_rttm,
    load_uem,
    processed_wav,
    reference_rttm,
    uem_path,
)

LEADERBOARD = REPO_ROOT / "results" / "leaderboard.csv"
REQUALIFICATION_RULE = "D18"
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


def cpu_block(execution: dict | None, subset: str | None = None) -> dict | None:
    """Bloc `temps_cpu` : mesure CPU dédiée, ou exécution principale en CPU restreinte à `subset`."""
    if execution is None:
        return None
    if execution["mode"] == "mesure_cpu":
        return {
            "sous_ensemble": execution["sous_ensemble"],
            "duree_audio_s": round(execution["duree_audio_s"], 2),
            "calcul_s": round(execution["calcul_s"], 2),
            "rtf": round(execution["rtf"], 4),
        }
    by_uri = {row["uri"]: row for row in execution["fichiers"]}
    rows = execution["fichiers"] if subset is None else [by_uri[uri] for uri in dataset_uris(subset)]
    audio = sum(row["duree_audio_s"] for row in rows)
    compute = sum(row["calcul_s"] for row in rows)
    return {
        "sous_ensemble": subset,
        "duree_audio_s": round(audio, 2),
        "calcul_s": round(compute, 2),
        "rtf": round(compute / audio, 4),
    }


def check_config(exp_dir: Path, runs: dict[str, dict]) -> None:
    """Refuse l'évaluation si une exécution ne porte pas l'empreinte du config.yaml actuel."""
    expected = hashlib.sha256((exp_dir / "config.yaml").read_bytes()).hexdigest()
    for name, run in runs.items():
        recorded = run.get("config_sha256")
        if recorded != expected:
            sys.exit(f"{name} : config_sha256 {recorded} différent de l'empreinte de "
                     f"config.yaml ({expected}) ; évaluation refusée")


def runs_are_clean(runs: list[dict]) -> bool:
    """Règle D18 appliquée aux exécutions : même commit, aucun chemin contrôlé non commité."""
    commits = {run["git_commit"] for run in runs}
    return len(commits) == 1 and all(tree_is_clean(run["fichiers_non_commites"]) for run in runs)


def controlled_diff(commits: list[str], repo: Path = REPO_ROOT) -> list[str]:
    """Fichiers des chemins contrôlés (D18) qui diffèrent entre le premier commit et les autres."""
    changed: set[str] = set()
    for commit in commits[1:]:
        output = subprocess.run(
            ["git", "diff", "--name-only", commits[0], commit],
            cwd=repo, capture_output=True, text=True, check=True,
        ).stdout
        changed.update(path for path in output.splitlines() if is_controlled(path))
    return sorted(changed)


def requalify(exp_dir: Path, repo: Path = REPO_ROOT) -> None:
    """Recalcule `arbre_propre` des results_*.json selon D18, sans toucher aux métriques."""
    executions = sorted(exp_dir.glob("execution_*.json"))
    if not executions:
        sys.exit(f"Aucun execution_*.json dans {exp_dir}")
    runs = [json.loads(path.read_text()) for path in executions]
    commits = list(dict.fromkeys(run["git_commit"] for run in runs))
    extra: dict = {}
    if len(commits) == 1:
        new_value = runs_are_clean(runs)
    else:
        # Amendement du 28/10/2026 de D18 : trois conditions, sinon refus.
        dirty = {p.name: [f for f in run["fichiers_non_commites"] if is_controlled(f)]
                 for p, run in zip(executions, runs) if not tree_is_clean(run["fichiers_non_commites"])}
        if dirty:
            sys.exit(f"Requalification refusée : exécution non propre ({dirty})")
        diff = controlled_diff(commits, repo)
        if diff:
            sys.exit(f"Requalification refusée : git diff non vide sur les chemins contrôlés "
                     f"entre {commits} ({diff})")
        hashes = {p.name: run.get("config_sha256") for p, run in zip(executions, runs)}
        if len(set(hashes.values())) != 1:
            sys.exit(f"Requalification refusée : config_sha256 différents ({hashes})")
        new_value = True
        extra = {"commits": commits, "diff_chemins_controles": "vide"}
    results_files = sorted(exp_dir.glob("results_*.json"))
    if not results_files:
        sys.exit(f"Aucun results_*.json dans {exp_dir} : rien à requalifier")
    date = datetime.now().astimezone().isoformat(timespec="seconds")
    for path in results_files:
        results = json.loads(path.read_text())
        if results.get("requalification") is not None:
            sys.exit(f"{path.name} a déjà été requalifié")
        old_value = results["arbre_propre"]
        block = {
            "date": date,
            "regle": REQUALIFICATION_RULE,
            "ancienne_valeur": old_value,
            "nouvelle_valeur": new_value,
            "sources": [p.name for p in executions],
            **extra,
        }
        # Le bloc est inséré juste après `arbre_propre` ; l'ordre des autres clés est conservé.
        updated = {}
        for key, value in results.items():
            updated[key] = new_value if key == "arbre_propre" else value
            if key == "arbre_propre":
                updated["requalification"] = block
        path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n")
        print(f"[requalification] {path.name} : arbre_propre {old_value} -> {new_value}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Voir l'en-tête du script et docs/decisions/D18-arbre-propre-et-precisions-protocole.md.",
    )
    parser.add_argument("--exp", required=True, type=Path, help="dossier de l'expérience")
    parser.add_argument(
        "--leaderboard", type=Path, default=LEADERBOARD,
        help="leaderboard à alimenter (défaut : results/leaderboard.csv) ; un autre chemin sert "
             "aux essais à blanc, sans toucher au leaderboard du dépôt",
    )
    parser.add_argument(
        "--requalifier", action="store_true",
        help="recalcule arbre_propre d'une expérience déjà évaluée selon D18, à partir des "
             "fichiers_non_commites de ses execution_*.json (et, si les commits diffèrent, du "
             "git diff sur les chemins contrôlés et des config_sha256), et ajoute un bloc "
             "requalification aux results_*.json ; métriques et leaderboard inchangés",
    )
    args = parser.parse_args()
    leaderboard = args.leaderboard

    exp_dir = args.exp.resolve()
    if args.requalifier:
        requalify(exp_dir)
        return
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
    check_config(exp_dir, {
        path.name: json.loads(path.read_text()) for path in sorted(exp_dir.glob("execution_*.json"))
    })
    state = git_state()
    commits = {run["git_commit"] for run in runs}
    clean = runs_are_clean(runs) and commits == {state["commit"]} and state["clean"]
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
            "temps_cpu": cpu_block(cpu_run, (config.get("mesure_cpu") or {}).get("liste")),
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
