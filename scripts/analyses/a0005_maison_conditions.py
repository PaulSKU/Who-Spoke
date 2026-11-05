"""A-0005 — corpus maison : métriques par condition d'UEM et catégories d'erreur (A9).

Usage :
    uv run python scripts/analyses/a0005_maison_conditions.py --config analyses/A-0005_maison-m01/config.yaml

Analyse a posteriori (D21 §1, methode.md §4.7) : aucun moteur n'est exécuté. Pour chaque
expérience de la configuration, chaque condition d'UEM et chaque fichier de la liste, les
hypothèses déjà écrites (`rttm/` de l'expérience, gardé en local pour le corpus maison) sont
évaluées face à la référence (`data/processed/<corpus>/rttm/`) avec les métriques du
protocole (`DiarizationEvaluator` : DER et composantes, JER, dans les deux conditions de
collar, chevauchements comptés ; nombres de locuteurs).

Une condition d'UEM est un dossier d'UEM (`<dossier>/<uri>.uem`). Pour le corpus maison, les
UEM restent hors de git (conventions d'annotation) : une condition réduite (par exemple sans
une zone de bruit notée dans la fiche de séance) est un second dossier sous
`data/processed/maison/`, et seule son empreinte est consignée.

Catégories d'erreur : carte des erreurs de l'application (`app.sortie.error_map`, décisions
du cockpit du 02/11), sans collar, référence et hypothèse coupées à l'UEM comme dans A-0003.
Elles sont données en points de DER (secondes / parole de la référence × 100), par type
d'erreur ; elles somment aux composantes du DER sans collar (contrôlé à 0,01 point près).

Confidentialité : les sorties ne contiennent que des taux agrégés par fichier, en
pourcentage. Ni horaire, ni zone d'erreur, ni durée.

Sorties : `resultats.csv` (une ligne par expérience × condition × fichier, plus une ligne
`ensemble` en rapport des sommes s'il y a plusieurs fichiers), `categories.csv` (une ligne
par expérience × condition × fichier × type × catégorie), `execution.json` (commit, état
de l'arbre, empreintes de la configuration, des hypothèses, des références et des UEM).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import whospoke  # noqa: F401  (D27 : télémétrie coupée avant tout import tiers)
import yaml
from pyannote.core import Annotation, Timeline

from whospoke.evaluation.metrics import CONDITIONS, DiarizationEvaluator, round_rates
from whospoke.experiment import REPO_ROOT, dataset_uris, git_state, load_rttm, load_uem, reference_rttm
from whospoke.partage import experiment_dir

sys.path.insert(0, str(REPO_ROOT))   # paquet `app` (carte des erreurs de l'application)
from app import sortie  # noqa: E402

ERROR_TYPES = ("manquee", "fausse_alarme", "confusion")
SUFFIX = {"collar_0": "c0", "collar_0_25": "c025"}
RATES = ("der", "manquee", "fausse_alarme", "confusion", "jer")
TOLERANCE_POINTS = 0.01


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT))


def metric_row(result: dict) -> dict:
    """Taux (%) des deux conditions de collar, aplatis (`der_c0`, …, `jer_c025`)."""
    return {f"{key}_{SUFFIX[name]}": round(result[name][key], 2) for name in CONDITIONS for key in RATES}


def category_points(reference: Annotation, hypothesis: Annotation, uem: Timeline) -> dict[str, dict[str, float]]:
    """Points de DER sans collar par type et catégorie (carte des erreurs, comme A-0003)."""
    ref = reference.crop(uem, mode="intersection")
    hyp = hypothesis.crop(uem, mode="intersection")
    ref.uri = hyp.uri = reference.uri
    errors = sortie.error_map(ref, hyp, uem.extent().end)
    total = errors["totaux"]["reference"]
    return {kind: {cat: 100.0 * seconds / total for cat, seconds in errors["categories"][kind].items()}
            for kind in ERROR_TYPES}


def evaluate(config: dict) -> tuple[list[dict], list[dict], dict[str, str]]:
    corpus = config["corpus"]
    uris = dataset_uris(config["liste"])
    rows, categories, sources = [], [], {}
    for experiment in config["experiences"]:
        hyp_dir = experiment_dir(experiment["exp_id"]) / "rttm"
        for condition in config["conditions"]:
            uem_dir = REPO_ROOT / condition["uem"]
            pooled = DiarizationEvaluator()
            for uri in uris:
                paths = {"hypothese": hyp_dir / f"{uri}.rttm", "reference": reference_rttm(corpus, uri),
                         "uem": uem_dir / f"{uri}.uem"}
                for path in paths.values():
                    sources[relative(path)] = sha256(path)
                reference = load_rttm(paths["reference"], uri)
                hypothesis = load_rttm(paths["hypothese"], uri)
                uem = load_uem(paths["uem"], uri)
                result = DiarizationEvaluator().add(reference, hypothesis, uem=uem)
                pooled.add(reference, hypothesis, uem=uem)
                base = {"exp_id": experiment["exp_id"], "systeme": experiment["systeme"],
                        "condition": condition["nom"], "uri": uri}
                rows.append(base | metric_row(result) | {
                    "n_locuteurs_reference": result["n_locuteurs"]["reference"],
                    "n_locuteurs_hypothese": result["n_locuteurs"]["hypothese"]})
                points = category_points(reference, hypothesis, uem)
                for kind in ERROR_TYPES:
                    gap = abs(sum(points[kind].values()) - result["collar_0"][kind])
                    if gap > TOLERANCE_POINTS:
                        sys.exit(f"{experiment['exp_id']} {condition['nom']} {uri} : catégories de {kind} "
                                 f"à {gap:.3f} point de la composante du DER")
                    for cat, value in points[kind].items():
                        categories.append(base | {"type": kind, "categorie": cat,
                                                  "libelle": sortie.ERROR_CATEGORIES[cat],
                                                  "points_der_c0": round(value, 2)})
            if len(uris) > 1:
                report = pooled.report()
                rows.append({"exp_id": experiment["exp_id"], "systeme": experiment["systeme"],
                             "condition": condition["nom"], "uri": "ensemble"}
                            | {f"{key}_{SUFFIX[name]}": round_rates(report[name])[key]
                               for name in CONDITIONS for key in RATES}
                            | {"n_locuteurs_reference": "", "n_locuteurs_hypothese": ""})
    return rows, categories, sources


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True, type=Path, help="config.yaml de l'analyse (dans analyses/A-…)")
    args = parser.parse_args()
    config_path = args.config.resolve()
    out_dir = config_path.parent
    config = yaml.safe_load(config_path.read_text())
    if (out_dir / "execution.json").exists():
        sys.exit(f"{out_dir.name}/execution.json existe déjà : une analyse exécutée est immuable")
    state = git_state()
    rows, categories, sources = evaluate(config)
    write_csv(out_dir / "resultats.csv", rows)
    write_csv(out_dir / "categories.csv", categories)
    execution = {
        "analyse_id": config["analyse_id"],
        "date": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_commit": state["commit"],
        "arbre_propre": state["clean"],
        "fichiers_non_commites": state["dirty"],
        "config_sha256": sha256(config_path),
        "sources_sha256": sources,
        "app_sortie_sha256": sha256(Path(sortie.__file__)),
        "seuils_carte": {"tour_court_s": sortie.SHORT_TURN_S, "pause_courte_s": sortie.SHORT_PAUSE_S,
                         "frontiere_s": sortie.BOUNDARY_S, "contigu_s": sortie.TOUCH_S},
    }
    (out_dir / "execution.json").write_text(json.dumps(execution, ensure_ascii=False, indent=2) + "\n")
    print(f"[{config['analyse_id']}] {len(rows)} lignes de résultats, {len(categories)} lignes de catégories")


if __name__ == "__main__":
    main()
