"""A-0002 — robustesse sur SUMM-RE test dégradé (D24 §3), par condition et par sous-groupe.

Usage :
    uv run python scripts/analyses/a0002_robustesse_d24.py --config analyses/A-0002_robustesse-d24/config.yaml

Analyse a posteriori (D21 §1, methode.md §4.7) : aucun système n'est exécuté. Les métriques
par fichier (`per_file_<corpus>_test.csv`) des expériences sources sont regroupées :

- `resultats.csv` : pour chaque moteur, condition (dont `propre`) et sous-groupe (`tous`,
  `zoom`, `autres` ; décision du cockpit du 02/11 : une réunion Zoom réverbérée dans une seule
  salle est moins plausible), le DER et ses composantes en rapport des sommes (protocole §4),
  dans les deux conditions de collar, l'écart à `propre` par bootstrap apparié (1 000
  tirages, graine 0) et le décompte des fichiers améliorés, dégradés et égaux ;
- `comparaison_moteurs.csv` : à condition et sous-groupe égaux, écart entre deux moteurs
  (premier moins second), bootstrap apparié, décompte des fichiers ;
- `rt60.csv` : par condition réverbérée, RT60 des réponses impulsionnelles simulées, lu dans
  `data/manifests/summre_degrade.csv` : T20 (valeur rapportée) et T60 sur toute la
  décroissance (annexe), médiane, minimum et maximum (décision du cockpit du 02/11) ;
- `execution.json` : commit, état de l'arbre (D18), empreinte de la configuration et des
  per_file sources.

Les fichiers de chaque sous-groupe sont ceux de la liste du sous-groupe ; `autres` est le
complément dans la liste de la partition.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

import whospoke  # noqa: F401  (D27 : télémétrie coupée avant tout import tiers)
import yaml

from whospoke.evaluation.metrics import bootstrap_der_ci, count_wins
from whospoke.experiment import REPO_ROOT, dataset_uris, git_state
from whospoke.partage import experiment_dir

COMPONENTS = ("manquee", "fausse_alarme", "confusion")
COLLARS = ("c0", "c025")


def read_per_file(path: Path) -> dict[str, dict]:
    with path.open() as handle:
        return {row["uri"]: row for row in csv.DictReader(handle)}


def errors(rows: dict, uris: list[str], collar: str) -> tuple[list[float], list[float]]:
    err = [sum(float(rows[u][f"{c}_{collar}_s"]) for c in COMPONENTS) for u in uris]
    total = [float(rows[u][f"duree_reference_{collar}_s"]) for u in uris]
    return err, total


def pooled(rows: dict, uris: list[str], collar: str) -> dict:
    total = sum(float(rows[u][f"duree_reference_{collar}_s"]) for u in uris)
    values = {c: 100.0 * sum(float(rows[u][f"{c}_{collar}_s"]) for u in uris) / total for c in COMPONENTS}
    return {"der": sum(values.values()), **values}


def compare(a: dict, b: dict, uris: list[str], spec: dict) -> dict:
    """Écart a − b (points de DER) par bootstrap apparié, et décompte des fichiers (a contre b)."""
    out = {}
    for collar in COLLARS:
        ea, ta = errors(a, uris, collar)
        eb, tb = errors(b, uris, collar)
        ci = bootstrap_der_ci(ea, ta, eb, tb, n_resamples=spec["tirages"], seed=spec["graine"])
        out[f"ecart_{collar}"] = round(ci["estimation"], 2)
        out[f"ic_inf_{collar}"] = round(ci["borne_inf"], 2)
        out[f"ic_sup_{collar}"] = round(ci["borne_sup"], 2)
    wins = count_wins([float(a[u]["der_c0"]) for u in uris], [float(b[u]["der_c0"]) for u in uris])
    out.update({"a_meilleur_c0": wins["a_meilleur"], "b_meilleur_c0": wins["b_meilleur"], "egalite_c0": wins["egalite"]})
    return out


def rt60_rows(manifest: Path, conditions: dict) -> list[dict]:
    with manifest.open() as handle:
        rows = list(csv.DictReader(handle))
    out = []
    for condition, spec in conditions.items():
        reverb = spec.get("reverberation")
        if not reverb:
            continue
        details = [json.loads(r["details"])["reverberation"] for r in rows if r["condition"] == condition]
        t20 = [v for d in details for v in d["rt60_mesure_t20_s"]]
        t60 = [v for d in details for v in d["rt60_mesure_t60_s"]]
        out.append({
            "condition": condition, "rt60_cible_s": reverb["rt60_s"], "n_reponses": len(t20),
            "t20_mediane_s": round(statistics.median(t20), 3), "t20_min_s": min(t20), "t20_max_s": max(t20),
            "annexe_t60_mediane_s": round(statistics.median(t60), 3), "annexe_t60_min_s": min(t60),
            "annexe_t60_max_s": max(t60),
        })
    return out


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

    partition = config["partition"]
    all_uris = dataset_uris(config["liste"])
    groups = {"tous": all_uris}
    for name, liste in config["sous_groupes"].items():
        members = set(dataset_uris(liste))
        groups[name] = [u for u in all_uris if u in members]
    groups["autres"] = [u for u in all_uris if not any(u in groups[g] for g in config["sous_groupes"])]

    sources: dict[str, dict[str, dict]] = {}
    fingerprints = {}
    for engine in config["moteurs"]:
        tables = {}
        clean = experiment_dir(engine["propre"]["exp_id"]) / f"per_file_{engine['propre']['corpus']}_{partition}.csv"
        tables["propre"] = read_per_file(clean)
        fingerprints[str(clean.relative_to(REPO_ROOT))] = hashlib.sha256(clean.read_bytes()).hexdigest()
        for condition in config["conditions"]:
            path = experiment_dir(engine["degrade"]) / f"per_file_summre-{condition}_{partition}.csv"
            tables[condition] = read_per_file(path)
            fingerprints[str(path.relative_to(REPO_ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        sources[engine["nom"]] = tables

    spec = config["bootstrap"]
    rows = []
    for engine, tables in sources.items():
        for condition in ["propre", *config["conditions"]]:
            for group, uris in groups.items():
                metrics = {collar: pooled(tables[condition], uris, collar) for collar in COLLARS}
                row = {"moteur": engine, "condition": condition, "sous_groupe": group, "n_fichiers": len(uris)}
                for collar in COLLARS:
                    for key, value in metrics[collar].items():
                        row[f"{key}_{collar}"] = round(value, 2)
                if condition == "propre":
                    row.update({k: "" for k in compare(tables["propre"], tables["propre"], uris, spec)})
                else:
                    row.update(compare(tables[condition], tables["propre"], uris, spec))
                rows.append(row)
    write_csv(out_dir / "resultats.csv", rows)

    engines = list(sources)
    comparisons = []
    for i, first in enumerate(engines):
        for second in engines[i + 1:]:
            for condition in ["propre", *config["conditions"]]:
                for group, uris in groups.items():
                    comparisons.append({
                        "moteur_a": first, "moteur_b": second, "condition": condition, "sous_groupe": group,
                        "n_fichiers": len(uris),
                        **compare(sources[first][condition], sources[second][condition], uris, spec),
                    })
    write_csv(out_dir / "comparaison_moteurs.csv", comparisons)

    manifest = REPO_ROOT / config["manifeste"]
    degrade_config = yaml.safe_load((REPO_ROOT / config["configuration_degradation"]).read_text())
    write_csv(out_dir / "rt60.csv", rt60_rows(manifest, degrade_config["conditions"]))

    execution = {
        "analyse_id": config["analyse_id"],
        "date": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_commit": state["commit"], "arbre_propre": state["clean"], "fichiers_non_commites": state["dirty"],
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "sources_sha256": fingerprints,
        "manifeste_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "sous_groupes": {group: len(uris) for group, uris in groups.items()},
    }
    (out_dir / "execution.json").write_text(json.dumps(execution, ensure_ascii=False, indent=2) + "\n")
    print(f"[A-0002] {len(rows)} lignes, {len(comparisons)} comparaisons, rt60.csv, execution.json")


if __name__ == "__main__":
    main()
