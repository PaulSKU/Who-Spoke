"""A-0001 : sensibilité de l'évaluation de SUMM-RE à la convention de référence (D21 §2).

Usage :
    uv run python scripts/analyses/a0001_sensibilite_reference.py \
        --config analyses/A-0001_sensibilite-reference/config.yaml

Analyse a posteriori (D21 §1, methode.md §4.7) : aucun système n'est exécuté. Les RTTM
des expériences sources (`sources` de config.yaml) sont réévalués :

1. contre chaque variante de la référence (`variantes` : écarts de fusion × traitement
   des jetons non lexicaux), construite au préalable par
   `scripts/data/get_summre.py --variante ECART_MS JETONS`, avec l'UEM officiel pour
   toutes les variantes ; toutes les métriques du protocole (§3.1 à §3.4), dans les deux
   conditions de collar, en rapport des sommes sur les fichiers (§4) → `resultats.csv` ;
2. contre la référence officielle seulement, répartition des secondes de fausse alarme et
   de parole manquée (condition `collar_0`) → `repartition_erreurs.csv`.

Répartition de la fausse alarme. Elle est comptée comme dans pyannote.metrics : sur
chaque intervalle élémentaire de l'UEM, max(0, K̂ − K) fois sa durée, où K et K̂ sont les
nombres de locuteurs actifs dans la référence et l'hypothèse. Chaque intervalle est classé
d'après la référence :
- (a) `pause_intra` : silence de la référence (aucun locuteur) entre deux tours, de
  `pause_max_s` au plus, dont un locuteur qui termine un tour au début du silence en
  commence un au moment où il finit ;
- (b) `pause_inter` : silence de la référence entre deux tours, de `pause_max_s` au plus,
  entre locuteurs différents ;
- (c) `ailleurs` : tout le reste, détaillé en `silence_long` (silence entre deux tours de
  plus de `pause_max_s`), `bords` (silence de l'UEM avant le premier tour ou après le
  dernier) et `parole` (fausse alarme pendant que la référence parle, quand l'hypothèse
  compte plus de locuteurs actifs qu'elle).

Répartition de la parole manquée. Sur chaque intervalle élémentaire, la parole manquée
vaut max(0, K − K̂) fois sa durée. Elle est attribuée aux tours de référence actifs
(segments du RTTM officiel) à parts égales : chacun reçoit (K − K̂) / K de la durée, ce qui
est exact quand l'hypothèse est muette (K̂ = 0) et neutre sinon. Un tour est `court` s'il
dure moins de `tour_court_s`, `long` sinon.

La somme des catégories est contrôlée, fichier par fichier, contre les composantes de
pyannote.metrics (écart toléré : 1 ms).

Traçabilité (D18, D21 §1) : `execution.json` consigne le commit, l'état de l'arbre,
l'empreinte de config.yaml, la date, et une empreinte des RTTM de chaque variante. Une
analyse exécutée est immuable : le script refuse de réécrire un dossier qui contient déjà
`execution.json`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import yaml
from pyannote.core import Annotation, Timeline

from whospoke.evaluation.metrics import DiarizationEvaluator
from whospoke.experiment import REPO_ROOT, dataset_uris, git_state, load_rttm, load_uem

TOLERANCE_S = 1e-3  # écart toléré entre la répartition et les composantes de pyannote.metrics
EPS = 1e-6          # égalité de deux instants (RTTM à la milliseconde)

RESULT_COLUMNS = [
    "variante", "ecart_fusion_ms", "jetons_non_lexicaux", "officielle", "exp_id", "systeme",
    "partition", "n_fichiers", "parole_reference_s",
    "der_c0", "manquee_c0", "fausse_alarme_c0", "confusion_c0", "jer_c0",
    "der_c025", "manquee_c025", "fausse_alarme_c025", "confusion_c025", "jer_c025",
    "der_zones_sans_chevauchement", "der_zones_chevauchement",
    "mae_n_locuteurs", "taux_exact_n_locuteurs", "n_locuteurs_moyen_reference",
]

FA_CATEGORIES = ("pause_intra", "pause_inter", "silence_long", "bords", "parole")
MISSED_CATEGORIES = ("court", "long")

SPLIT_COLUMNS = [
    "exp_id", "systeme", "partition", "n_fichiers", "parole_reference_s",
    "fausse_alarme_s", "fa_a_pause_intra_s", "fa_b_pause_inter_s", "fa_c_ailleurs_s",
    "fa_c_dont_silence_long_s", "fa_c_dont_bords_s", "fa_c_dont_parole_s",
    "fa_a_pause_intra_pct", "fa_b_pause_inter_pct", "fa_c_ailleurs_pct",
    "duree_pauses_intra_s", "duree_pauses_inter_s", "n_pauses_intra", "n_pauses_inter",
    "manquee_s", "manquee_tours_courts_s", "manquee_tours_longs_s",
    "manquee_tours_courts_pct", "manquee_tours_longs_pct",
    "n_tours_courts", "n_tours_longs",
]


# --- Répartition des erreurs ----------------------------------------------------------------


def label_supports(annotation: Annotation, uem: Timeline) -> dict[str, list[tuple[float, float]]]:
    """Intervalles disjoints de chaque étiquette, restreints à l'UEM."""
    cropped = annotation.crop(uem, mode="intersection")
    return {
        label: [(s.start, s.end) for s in cropped.label_timeline(label).support()]
        for label in cropped.labels()
    }


def active_count(supports: dict[str, list[tuple[float, float]]], points: np.ndarray) -> np.ndarray:
    """Nombre d'étiquettes actives en chacun des `points` (intervalles semi-ouverts)."""
    count = np.zeros(len(points), dtype=int)
    for intervals in supports.values():
        starts = np.array([s for s, _ in intervals])
        ends = np.array([e for _, e in intervals])
        count += np.searchsorted(starts, points, side="right") - np.searchsorted(ends, points, side="right")
    return count


def reference_gaps(
    reference: Annotation, uem: Timeline, pause_max_s: float
) -> list[tuple[float, float, str]]:
    """Silences de la référence dans l'UEM, classés `pause_intra`, `pause_inter`, `silence_long` ou `bords`."""
    uem = uem.support()
    cropped = reference.crop(uem, mode="intersection")
    ends_at, starts_at = defaultdict(set), defaultdict(set)
    for segment, _, label in cropped.itertracks(yield_label=True):
        ends_at[round(segment.end, 3)].add(label)
        starts_at[round(segment.start, 3)].add(label)
    speech = cropped.get_timeline().support()
    gaps = []
    for region in uem:
        inside = [s for s in speech if s.end > region.start and s.start < region.end]
        if not inside:
            gaps.append((region.start, region.end, "bords"))
            continue
        if inside[0].start > region.start + EPS:
            gaps.append((region.start, inside[0].start, "bords"))
        for before, after in zip(inside, inside[1:]):
            start, end = before.end, after.start
            if end - start > pause_max_s + EPS:
                kind = "silence_long"
            else:
                same = ends_at[round(start, 3)] & starts_at[round(end, 3)]
                kind = "pause_intra" if same else "pause_inter"
            gaps.append((start, end, kind))
        if inside[-1].end < region.end - EPS:
            gaps.append((inside[-1].end, region.end, "bords"))
    return gaps


def locate(intervals: list[tuple[float, float]], points: np.ndarray) -> np.ndarray:
    """Indice de l'intervalle (disjoints, triés) qui contient chaque point, ou -1."""
    if not intervals:
        return np.full(len(points), -1)
    starts = np.array([s for s, _ in intervals])
    ends = np.array([e for _, e in intervals])
    index = np.searchsorted(starts, points, side="right") - 1
    inside = (index >= 0) & (points < ends[np.clip(index, 0, None)])
    return np.where(inside, index, -1)


def split_errors(
    reference: Annotation, hypothesis: Annotation, uem: Timeline,
    pause_max_s: float = 1.0, short_turn_s: float = 0.5,
) -> dict:
    """Secondes de fausse alarme par catégorie et de parole manquée par durée de tour (collar 0)."""
    uem = uem.support()
    ref = label_supports(reference, uem)
    hyp = label_supports(hypothesis, uem)
    gaps = reference_gaps(reference, uem, pause_max_s)
    # Tours de référence : intervalles disjoints de chaque locuteur (le RTTM officiel est déjà
    # fusionné par locuteur, donc ses segments).
    turns = [(start, end) for intervals in ref.values() for start, end in intervals]

    bounds = {t for s in uem for t in (s.start, s.end)}
    for supports in (ref, hyp):
        bounds.update(t for intervals in supports.values() for start, end in intervals for t in (start, end))
    bounds.update(t for start, end, _ in gaps for t in (start, end))
    bounds = np.array(sorted(bounds))
    mids = (bounds[:-1] + bounds[1:]) / 2
    widths = np.diff(bounds)
    in_uem = locate([(s.start, s.end) for s in uem], mids) >= 0
    k_ref = active_count(ref, mids)
    k_hyp = active_count(hyp, mids)

    gap_index = locate([(start, end) for start, end, _ in gaps], mids)
    gap_kind = np.array([kind for _, _, kind in gaps] + ["parole"], dtype=object)[gap_index]
    excess = np.where(in_uem, np.maximum(0, k_hyp - k_ref), 0) * widths
    false_alarm = {category: float(excess[gap_kind == category].sum()) for category in FA_CATEGORIES}

    # Parole manquée : (K − K̂) / K de chaque intervalle à chaque tour actif.
    share = np.where(in_uem & (k_ref > 0), np.maximum(0, k_ref - k_hyp) / np.maximum(k_ref, 1), 0.0) * widths
    missed = {category: 0.0 for category in MISSED_CATEGORIES}
    for intervals in ref.values():
        index = locate(intervals, mids)
        lengths = np.array([end - start for start, end in intervals])
        active = index >= 0
        short = np.zeros(len(mids), dtype=bool)
        short[active] = lengths[index[active]] < short_turn_s
        missed["court"] += float(share[active & short].sum())
        missed["long"] += float(share[active & ~short].sum())

    pauses = defaultdict(lambda: [0, 0.0])
    for start, end, kind in gaps:
        pauses[kind][0] += 1
        pauses[kind][1] += end - start
    tours = defaultdict(int)
    for start, end in turns:
        tours["court" if end - start < short_turn_s else "long"] += 1
    return {
        "fausse_alarme": false_alarm,
        "manquee": missed,
        "pauses": {kind: tuple(pauses[kind]) for kind in ("pause_intra", "pause_inter")},
        "tours": {kind: tours[kind] for kind in MISSED_CATEGORIES},
    }


def check_split(split: dict, components: dict, uri: str) -> None:
    """Contrôle : les catégories somment aux composantes de pyannote.metrics (collar 0)."""
    fa = sum(split["fausse_alarme"].values())
    missed = sum(split["manquee"].values())
    if abs(fa - components["fausse_alarme_s"]) > TOLERANCE_S or abs(missed - components["manquee_s"]) > TOLERANCE_S:
        raise RuntimeError(
            f"{uri} : répartition incohérente (fausse alarme {fa:.4f} contre {components['fausse_alarme_s']:.4f} s, "
            f"manquée {missed:.4f} contre {components['manquee_s']:.4f} s)"
        )


def split_row(source: dict, partition: str, n_files: int, speech_s: float, totals: dict) -> dict:
    fa, missed = totals["fausse_alarme"], totals["manquee"]
    fa_total, missed_total = sum(fa.values()), sum(missed.values())
    elsewhere = fa["silence_long"] + fa["bords"] + fa["parole"]

    def share(value: float, total: float) -> float | None:
        return None if total == 0 else round(100.0 * value / total, 2)

    return {
        "exp_id": source["exp_id"], "systeme": source["systeme"], "partition": partition,
        "n_fichiers": n_files, "parole_reference_s": round(speech_s, 3),
        "fausse_alarme_s": round(fa_total, 3),
        "fa_a_pause_intra_s": round(fa["pause_intra"], 3),
        "fa_b_pause_inter_s": round(fa["pause_inter"], 3),
        "fa_c_ailleurs_s": round(elsewhere, 3),
        "fa_c_dont_silence_long_s": round(fa["silence_long"], 3),
        "fa_c_dont_bords_s": round(fa["bords"], 3),
        "fa_c_dont_parole_s": round(fa["parole"], 3),
        "fa_a_pause_intra_pct": share(fa["pause_intra"], fa_total),
        "fa_b_pause_inter_pct": share(fa["pause_inter"], fa_total),
        "fa_c_ailleurs_pct": share(elsewhere, fa_total),
        "duree_pauses_intra_s": round(totals["pauses"]["pause_intra"][1], 3),
        "duree_pauses_inter_s": round(totals["pauses"]["pause_inter"][1], 3),
        "n_pauses_intra": totals["pauses"]["pause_intra"][0],
        "n_pauses_inter": totals["pauses"]["pause_inter"][0],
        "manquee_s": round(missed_total, 3),
        "manquee_tours_courts_s": round(missed["court"], 3),
        "manquee_tours_longs_s": round(missed["long"], 3),
        "manquee_tours_courts_pct": share(missed["court"], missed_total),
        "manquee_tours_longs_pct": share(missed["long"], missed_total),
        "n_tours_courts": totals["tours"]["court"],
        "n_tours_longs": totals["tours"]["long"],
    }


# --- Métriques par variante -------------------------------------------------------------------


def variant_name(gap_ms: int, tokens: str) -> str:
    """Même nommage que scripts/data/get_summre.py (`variant_name`)."""
    return f"ecart{gap_ms}ms_jetons-{tokens}"


def metrics_row(report: dict, counts: list[tuple[int, int]]) -> dict:
    row = {}
    for name, suffix in (("collar_0", "c0"), ("collar_0_25", "c025")):
        for key in ("der", "manquee", "fausse_alarme", "confusion", "jer"):
            row[f"{key}_{suffix}"] = round(report[name][key], 2)
    for zone in ("sans_chevauchement", "chevauchement"):
        value = report[f"der_zones_{zone}"]
        row[f"der_zones_{zone}"] = None if value is None else round(value, 2)
    row["mae_n_locuteurs"] = round(report["n_locuteurs"]["erreur_absolue_moyenne"], 2)
    row["taux_exact_n_locuteurs"] = round(report["n_locuteurs"]["taux_exact"], 2)
    row["n_locuteurs_moyen_reference"] = round(float(np.mean([k for k, _ in counts])), 2)
    return row


def rttm_fingerprint(directory: Path, uris: list[str]) -> str:
    """SHA-256 de la concaténation des RTTM des `uris`, dans l'ordre."""
    digest = hashlib.sha256()
    for uri in uris:
        digest.update((directory / f"{uri}.rttm").read_bytes())
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Voir l'en-tête du script et docs/decisions/D21-analyses-et-alimentation.md.",
    )
    parser.add_argument("--config", required=True, type=Path, help="config.yaml de l'analyse (dans analyses/A-…)")
    args = parser.parse_args()

    config_path = args.config.resolve()
    out_dir = config_path.parent
    config = yaml.safe_load(config_path.read_text())
    if not out_dir.name.startswith(config["analyse_id"]):
        sys.exit(f"Dossier {out_dir.name} incohérent avec analyse_id {config['analyse_id']}")
    if (out_dir / "execution.json").exists():
        sys.exit(f"{out_dir.name}/execution.json existe déjà : une analyse exécutée est immuable")

    state = git_state()
    print(f"[A-0001] commit {state['commit'][:7]}, arbre propre (D18) : {state['clean']}")
    if state["dirty"]:
        print(f"[A-0001] fichiers non commités : {', '.join(state['dirty'])}", file=sys.stderr)

    official_dir = REPO_ROOT / config["reference_officielle"]
    uem_dir = REPO_ROOT / config["uem"]
    variants_dir = REPO_ROOT / config["variantes"]["dossier"]
    split_cfg = config["repartition"]
    jeux = {jeu["partition"]: dataset_uris(jeu["liste"]) for jeu in config["jeux"]}
    all_uris = [uri for uris in jeux.values() for uri in uris]

    variants = []
    for gap_ms in config["variantes"]["ecarts_ms"]:
        for tokens in config["variantes"]["jetons"]:
            name = variant_name(gap_ms, tokens)
            directory = variants_dir / name
            missing = [uri for uri in all_uris if not (directory / f"{uri}.rttm").exists()]
            if missing:
                sys.exit(f"Variante {name} incomplète ({len(missing)} RTTM absents) : "
                         f"uv run python scripts/data/get_summre.py --variante {gap_ms} {tokens}")
            variants.append((name, gap_ms, tokens, directory))

    uems = {uri: load_uem(uem_dir / f"{uri}.uem", uri) for uri in all_uris}
    hypotheses = {
        source["exp_id"]: {uri: load_rttm(REPO_ROOT / source["rttm"] / f"{uri}.rttm", uri) for uri in all_uris}
        for source in config["sources"]
    }

    result_rows = []
    for name, gap_ms, tokens, directory in variants:
        official = gap_ms == config["variantes"]["officielle"]["ecart_ms"] and tokens == config["variantes"]["officielle"]["jetons"]
        for partition, uris in jeux.items():
            references = {uri: load_rttm(directory / f"{uri}.rttm", uri) for uri in uris}
            for source in config["sources"]:
                evaluator = DiarizationEvaluator()
                counts = []
                for uri in uris:
                    result = evaluator.add(references[uri], hypotheses[source["exp_id"]][uri], uem=uems[uri])
                    counts.append((result["n_locuteurs"]["reference"], result["n_locuteurs"]["hypothese"]))
                speech = sum(row["duree_reference_c0_s"] for row in evaluator.per_file())
                row = {
                    "variante": name, "ecart_fusion_ms": gap_ms, "jetons_non_lexicaux": tokens,
                    "officielle": official, "exp_id": source["exp_id"], "systeme": source["systeme"],
                    "partition": partition, "n_fichiers": len(uris), "parole_reference_s": round(speech, 3),
                } | metrics_row(evaluator.report(), counts)
                result_rows.append(row)
                print(f"[A-0001] {name} {source['exp_id']} {partition} : DER c0 {row['der_c0']:.2f} % "
                      f"(M {row['manquee_c0']:.2f}, FA {row['fausse_alarme_c0']:.2f}, C {row['confusion_c0']:.2f}), "
                      f"c025 {row['der_c025']:.2f} %", flush=True)

    split_rows = []
    for partition, uris in jeux.items():
        references = {uri: load_rttm(official_dir / f"{uri}.rttm", uri) for uri in uris}
        for source in config["sources"]:
            totals = {"fausse_alarme": defaultdict(float), "manquee": defaultdict(float),
                      "pauses": {k: [0, 0.0] for k in ("pause_intra", "pause_inter")},
                      "tours": defaultdict(int)}
            speech = 0.0
            for uri in uris:
                reference, hypothesis = references[uri], hypotheses[source["exp_id"]][uri]
                split = split_errors(reference, hypothesis, uems[uri],
                                     split_cfg["pause_max_s"], split_cfg["tour_court_s"])
                components = DiarizationEvaluator().add(reference, hypothesis, uem=uems[uri])["collar_0"]
                check_split(split, components, uri)
                speech += components["duree_reference_s"]
                for key in ("fausse_alarme", "manquee"):
                    for category, value in split[key].items():
                        totals[key][category] += value
                for kind, (n, duration) in split["pauses"].items():
                    totals["pauses"][kind][0] += n
                    totals["pauses"][kind][1] += duration
                for kind, n in split["tours"].items():
                    totals["tours"][kind] += n
            row = split_row(source, partition, len(uris), speech, totals)
            split_rows.append(row)
            print(f"[A-0001] répartition {source['exp_id']} {partition} : FA {row['fausse_alarme_s']:.0f} s "
                  f"(a {row['fa_a_pause_intra_pct']} %, b {row['fa_b_pause_inter_pct']} %, "
                  f"c {row['fa_c_ailleurs_pct']} %), manquée {row['manquee_s']:.0f} s "
                  f"(courts {row['manquee_tours_courts_pct']} %)", flush=True)

    for filename, columns, rows in (("resultats.csv", RESULT_COLUMNS, result_rows),
                                    ("repartition_erreurs.csv", SPLIT_COLUMNS, split_rows)):
        with (out_dir / filename).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)

    variant_info = {}
    for name, _, _, directory in variants:
        info_path = directory / "variante.json"
        info = json.loads(info_path.read_text()) if info_path.exists() else {}
        variant_info[name] = {"date_generation": info.get("date"), "revision": info.get("revision"),
                              "rttm_sha256": rttm_fingerprint(directory, all_uris)}
    execution = {
        "analyse_id": config["analyse_id"],
        "date": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_commit": state["commit"],
        "arbre_propre": state["clean"],
        "fichiers_non_commites": state["dirty"],
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "reference_officielle_rttm_sha256": rttm_fingerprint(official_dir, all_uris),
        "variantes": variant_info,
        "fichiers": ["resultats.csv", "repartition_erreurs.csv"],
    }
    (out_dir / "execution.json").write_text(json.dumps(execution, ensure_ascii=False, indent=2) + "\n")
    print(f"[A-0001] écrit : resultats.csv ({len(result_rows)} lignes), repartition_erreurs.csv "
          f"({len(split_rows)} lignes), execution.json")


if __name__ == "__main__":
    main()
