"""Réglage de la détection fine par Silero VAD sur SUMM-RE dev (D25, V2 et V3 ; chantier E5).

Prêt pour la piste A, après `uv add silero-vad==6.2.3` (voir `whospoke.pipelines.silero`) :

    uv run python scripts/reglage_silero.py --probabilites    # Silero seul : remplit le cache
    uv run python scripts/reglage_silero.py                   # grille V2, puis V3 au point retenu

pyannote n'est pas relancé : les hypothèses sont les RTTM déjà écrits par les expériences
sources, sortie habituelle d'EXP-0007 pour V2 (`--source-v2`) et sortie exclusive
d'EXP-0016 pour V3 (`--source-v3`). Silero ne tourne qu'une fois par fichier : ses
probabilités sont mises en cache sous `data/processed/<corpus>/silero/<version>-<empreinte>/`
(non versionné), puis chaque point de la grille les rebinarise.

Déroulé :

1. Contrôle de reproduction : les hypothèses sources, évaluées sans post-traitement,
   doivent redonner les DER consignés dans `results_<corpus>_<partition>.json` de chaque
   expérience source (au centième). Sinon, arrêt.
2. Grille V2 (par défaut 3 × 3 × 3 = 27 points) : `--seuils`, `--silences` (durée minimale
   de silence rouvert, s) et `--marges` (s). Pour chaque point : masque de Silero,
   intersection avec chaque hypothèse, DER dans les deux conditions de collar, en rapport
   des sommes (protocole §4), et parole retirée.
3. Point retenu : DER sans collar le plus bas sur dev (premier dans l'ordre de la grille en
   cas d'égalité). Si son DER avec collar dépasse celui de la source, c'est signalé : la
   règle de choix de D25 se juge sur test, par le bootstrap apparié, pas ici.
4. V3 : sortie exclusive + le réglage retenu pour V2 (D25 : « réglage de V2 repris »).

Sorties dans `--sortie` (par défaut `results/reglage_silero/<date>_<heure>/`) :
`reglage.json` (tout : sources, fichiers, version de Silero, grille, lignes, choix, état
git), `grille.csv` (une ligne par point) et `reglage.md` (tableau à reporter dans le
journal et dans la configuration des expériences V2 et V3).
"""

from __future__ import annotations

import whospoke  # noqa: F401  (D27 : télémétrie coupée avant tout import tiers)

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from itertools import product
from pathlib import Path

from pyannote.core import Annotation, Timeline
from pyannote.metrics.diarization import DiarizationErrorRate

from whospoke.audio import load_waveform
from whospoke.evaluation.metrics import CONDITIONS
from whospoke.experiment import REPO_ROOT, git_state, load_rttm, load_uem, processed_wav, reference_rttm, uem_path
from whospoke.pipelines import silero

DEFAULT_V2 = Path("experiments/EXP-0007_pyannote-c1-summre")
DEFAULT_V3 = Path("experiments/EXP-0016_pyannote-c1-summre-exclusive")
GRID = {
    "seuil": (0.35, 0.5, 0.65),
    "silence_min_s": (0.2, 0.4, 0.8),
    "marge_s": (0.03, 0.1, 0.2),
}
COMPONENTS = {
    "der": "diarization error rate",
    "manquee": "missed detection",
    "fausse_alarme": "false alarm",
    "confusion": "confusion",
}
TOLERANCE = 0.005   # DER consignés au centième


def say(message: str = "") -> None:
    print(message, flush=True)


@dataclass
class Item:
    uri: str
    reference: Annotation
    uem: Timeline
    hypothesis: Annotation


def under(root: Path, path: Path) -> Path:
    """Chemin de `whospoke.experiment` (relatif à REPO_ROOT) ramené sous `root`."""
    return root / path.relative_to(REPO_ROOT)


def read_list(root: Path, corpus: str, partition: str) -> list[str]:
    path = root / "data" / "splits" / corpus / f"{partition}.txt"
    uris = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if len(set(uris)) != len(uris):
        raise ValueError(f"{path} : identifiants en double")
    return uris


def load_items(root: Path, corpus: str, uris: list[str], source: Path) -> list[Item]:
    items = []
    for uri in uris:
        hypothesis_path = source / "rttm" / f"{uri}.rttm"
        if not hypothesis_path.is_file():
            raise FileNotFoundError(f"Hypothèse absente : {hypothesis_path}")
        items.append(Item(
            uri,
            load_rttm(under(root, reference_rttm(corpus, uri)), uri),
            load_uem(under(root, uem_path(corpus, uri)), uri),
            load_rttm(hypothesis_path, uri),
        ))
    return items


def probabilities(root: Path, corpus: str, uris: list[str], model_loader=silero.load_model,
                  waveform_loader=load_waveform) -> tuple[dict[str, tuple], dict]:
    """Probabilités de Silero par fichier, lues dans le cache ou calculées puis écrites.
    Le modèle n'est chargé que si un fichier manque au cache."""
    cached, computed, seconds = {}, [], 0.0
    model = None
    for uri in uris:
        path = silero.cache_path(corpus, uri, root=root / "data")
        if path.is_file():
            cached[uri] = silero.load_probabilities(path)
            continue
        if model is None:
            model, _ = model_loader()
        waveform, _ = waveform_loader(under(root, processed_wav(corpus, uri)))
        t0 = time.perf_counter()
        probs = silero.speech_probabilities(model, waveform)
        seconds += time.perf_counter() - t0
        silero.save_probabilities(path, probs, waveform.shape[1])
        cached[uri] = (probs, int(waveform.shape[1]))
        computed.append(uri)
        say(f"  Silero : {uri} ({waveform.shape[1] / silero.SAMPLE_RATE / 60:.1f} min) en {time.perf_counter() - t0:.1f} s")
    info = {"cache": str(silero.cache_path(corpus, "x", root=root / "data").parent.relative_to(root)),
            "calcules": computed, "lus_en_cache": len(uris) - len(computed), "calcul_s": round(seconds, 1)}
    return cached, info


def der_report(items: list[Item], hypotheses: list[Annotation]) -> dict:
    """DER et composantes (%) par condition de collar, en rapport des sommes."""
    report = {}
    for name, collar in CONDITIONS.items():
        metric = DiarizationErrorRate(collar=collar, skip_overlap=False)
        for item, hypothesis in zip(items, hypotheses, strict=True):
            metric(item.reference, hypothesis, uem=item.uem)
        totals = metric[:]
        total = totals["total"]
        report[name] = {key: round(100.0 * (abs(metric) if key == "der" else totals[component] / total), 4)
                        for key, component in COMPONENTS.items()}
    return report


def apply_mask(items: list[Item], probs: dict[str, tuple], params: silero.MaskParams, binarize) -> tuple[list[Annotation], float]:
    refined, removed = [], 0.0
    for item in items:
        values, n_samples = probs[item.uri]
        mask = silero.speech_mask(values, n_samples, params, binarize, uri=item.uri)
        output = silero.refine(item.hypothesis, mask)
        removed += silero.removed_speech_s(item.hypothesis, output)
        refined.append(output)
    return refined, removed


def check_source(source: Path, corpus: str, partition: str, report: dict) -> dict:
    """DER recalculés sans post-traitement, comparés à ceux consignés par l'expérience source."""
    path = source / f"results_{corpus}_{partition}.json"
    if not path.is_file():
        return {"fichier": path.name, "conforme": None, "motif": "résultats de la source absents"}
    recorded = json.loads(path.read_text())["metriques"]
    gaps = {name: round(report[name]["der"] - recorded[name]["der"], 4) for name in CONDITIONS}
    return {"fichier": path.name, "consigne": {name: recorded[name]["der"] for name in CONDITIONS},
            "recalcule": {name: round(report[name]["der"], 2) for name in CONDITIONS},
            "conforme": all(abs(gap) <= TOLERANCE for gap in gaps.values())}


def grid(seuils, silences, marges) -> list[silero.MaskParams]:
    return [silero.MaskParams(seuil=s, silence_min_s=m, marge_s=g) for s, m, g in product(seuils, silences, marges)]


def choose(rows: list[dict]) -> dict:
    return min(rows, key=lambda row: row["metriques"]["collar_0"]["der"])


def _pct(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def cells(row: dict) -> list[str]:
    """Réglage, DER sans collar et composantes, DER avec collar, parole retirée."""
    p = row.get("reglage") or {}
    c0, c25 = row["metriques"]["collar_0"], row["metriques"]["collar_0_25"]
    return [*(str(p[k]).replace(".", ",") if k in p else "—" for k in ("seuil", "silence_min_s", "marge_s")),
            _pct(c0["der"]), _pct(c0["fausse_alarme"]), _pct(c0["manquee"]), _pct(c0["confusion"]), _pct(c25["der"]),
            "—" if "parole_retiree_s" not in row else f"{row['parole_retiree_s'] / 60:.1f}".replace(".", ",")]


def markdown(summary: dict) -> str:
    lines = [
        f"# Réglage de Silero VAD — {summary['corpus']} {summary['partition']} ({summary['date'][:10]})",
        "",
        f"Silero VAD {summary['silero']['version']} (`{summary['silero']['empreinte'][:12]}`) ; "
        f"{len(summary['fichiers'])} fichiers ; sources : V2 `{summary['sources']['v2']}`"
        + (f", V3 `{summary['sources']['v3']}`" if summary['sources'].get('v3') else "") + ".",
        "",
        "| Système | Seuil | Silence min. (s) | Marge (s) | DER sans collar | FA | Manquée | Confusion | DER collar 0,25 | Parole retirée (min) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    def line(label, row):
        return "| " + " | ".join([label, *cells(row)]) + " |"

    lines.append(line("Source V2 (sortie habituelle)", summary["sources_evaluees"]["v2"]))
    if summary["sources_evaluees"].get("v3"):
        lines.append(line("Source V3 (sortie exclusive, V1)", summary["sources_evaluees"]["v3"]))
    lines.append(line("**V2 retenue**", summary["v2_retenue"]))
    if summary.get("v3"):
        lines.append(line("**V3** (réglage de V2)", summary["v3"]))
    lines += ["", f"Point retenu : {summary['choix']['regle']}"]
    if summary["choix"]["alerte"]:
        lines += ["", f"**Alerte** : {summary['choix']['alerte']}"]
    lines += ["", "## Grille V2 (DER sans collar croissant)", "",
              "| Seuil | Silence min. (s) | Marge (s) | DER sans collar | FA | Manquée | Confusion | DER collar 0,25 |",
              "|---|---|---|---|---|---|---|---|"]
    for row in sorted(summary["grille"], key=lambda r: r["metriques"]["collar_0"]["der"]):
        lines.append("| " + " | ".join(cells(row)[:8]) + " |")
    lines += ["", "Pourcentages en rapport des sommes sur les fichiers (protocole §4) ; FA : fausse alarme. "
              "Réglage sur dev seulement : les conditions de D25 se jugent sur test, AMI et D24.", ""]
    return "\n".join(lines)


def write_outputs(output: Path, summary: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "reglage.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    with (output / "grille.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["seuil", "silence_min_s", "marge_s", "parole_retiree_s",
                         *(f"{key}_{suffix}" for suffix in ("c0", "c025") for key in COMPONENTS)])
        for row in summary["grille"]:
            p, m = row["reglage"], row["metriques"]
            writer.writerow([p["seuil"], p["silence_min_s"], p["marge_s"], row["parole_retiree_s"],
                             *(m[name][key] for name in CONDITIONS for key in COMPONENTS)])
    (output / "reglage.md").write_text(markdown(summary))


def floats(text: str) -> tuple[float, ...]:
    return tuple(float(value) for value in text.split(",") if value.strip())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", default="summre")
    parser.add_argument("--partition", default="dev", help="réglage sur dev seulement (D25) ; défaut : dev")
    parser.add_argument("--source-v2", type=Path, default=DEFAULT_V2, help="expérience dont rttm/ porte la sortie habituelle")
    parser.add_argument("--source-v3", type=Path, default=DEFAULT_V3,
                        help="expérience dont rttm/ porte la sortie exclusive ; « aucune » pour s'en passer")
    parser.add_argument("--seuils", type=floats, default=GRID["seuil"])
    parser.add_argument("--silences", type=floats, default=GRID["silence_min_s"], help="durée minimale de silence rouvert (s)")
    parser.add_argument("--marges", type=floats, default=GRID["marge_s"], help="marge autour de la parole (s)")
    parser.add_argument("--probabilites", action="store_true", help="remplit le cache de Silero, sans grille")
    parser.add_argument("--sortie", type=Path, default=None)
    parser.add_argument("--racine", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)  # tests
    return parser


def main(argv: list[str] | None = None, model_loader=silero.load_model, binarize=None) -> int:
    args = build_parser().parse_args(argv)
    root = args.racine.resolve()
    if args.partition != "dev":
        say(f"Attention : réglage sur {args.partition} ; D25 prévoit dev.")
    uris = read_list(root, args.corpus, args.partition)
    sources = {"v2": root / args.source_v2}
    if str(args.source_v3) != "aucune":
        sources["v3"] = root / args.source_v3
    for name, path in sources.items():
        if not (path / "rttm").is_dir():
            say(f"Arrêt : {path / 'rttm'} absent (source {name.upper()})")
            return 1
    say(f"{args.corpus} {args.partition} : {len(uris)} fichiers")
    t0 = time.perf_counter()
    try:
        probs, cache_info = probabilities(root, args.corpus, uris, model_loader=model_loader)
    except silero.SileroMissing as error:
        say(f"Arrêt : {error}")
        return 1
    if args.probabilites:
        say(f"Cache : {cache_info['cache']} ({len(cache_info['calcules'])} calculés, {cache_info['lus_en_cache']} déjà là)")
        return 0
    if binarize is None:
        try:
            binarize = silero.load_binarize()
        except silero.SileroMissing as error:
            say(f"Arrêt : {error}")
            return 1

    items = {name: load_items(root, args.corpus, uris, path) for name, path in sources.items()}
    evaluated, checks = {}, {}
    for name in sources:
        report = der_report(items[name], [item.hypothesis for item in items[name]])
        evaluated[name] = {"metriques": report}
        checks[name] = check_source(sources[name], args.corpus, args.partition, report)
        state = {True: "reproduit", False: "NON REPRODUIT", None: "non vérifiable"}[checks[name]["conforme"]]
        say(f"Source {name.upper()} sans post-traitement : DER {report['collar_0']['der']:.2f} / "
            f"{report['collar_0_25']['der']:.2f} % ({state})")
        if checks[name]["conforme"] is False:
            say(f"Arrêt : les RTTM de {sources[name].name} ne redonnent pas {checks[name]['fichier']} "
                f"(consigné {checks[name]['consigne']}, recalculé {checks[name]['recalcule']})")
            return 1

    points = grid(args.seuils, args.silences, args.marges)
    rows = []
    for index, params in enumerate(points, start=1):
        refined, removed = apply_mask(items["v2"], probs, params, binarize)
        row = {"reglage": params.as_dict(), "metriques": der_report(items["v2"], refined), "parole_retiree_s": round(removed, 1)}
        rows.append(row)
        say(f"  [{index}/{len(points)}] seuil {params.seuil}, silence {params.silence_min_s} s, marge {params.marge_s} s : "
            f"DER {row['metriques']['collar_0']['der']:.2f} / {row['metriques']['collar_0_25']['der']:.2f} %")
    best = choose(rows)
    source_c25 = evaluated["v2"]["metriques"]["collar_0_25"]["der"]
    alert = None
    if best["metriques"]["collar_0_25"]["der"] > source_c25:
        alert = (f"le DER avec collar du point retenu ({best['metriques']['collar_0_25']['der']:.2f} %) dépasse celui "
                 f"de la source ({source_c25:.2f} %) sur dev")
    v3 = None
    if "v3" in sources:
        params = silero.MaskParams(**best["reglage"])
        refined, removed = apply_mask(items["v3"], probs, params, binarize)
        v3 = {"reglage": params.as_dict(), "metriques": der_report(items["v3"], refined), "parole_retiree_s": round(removed, 1)}

    now = datetime.now().astimezone()
    summary = {
        "date": now.isoformat(timespec="seconds"),
        "corpus": args.corpus, "partition": args.partition, "fichiers": uris,
        "sources": {name: str(path.relative_to(root)) for name, path in sources.items()},
        "controle_sources": checks,
        "silero": {"version": silero.SILERO_VERSION, "fichier": silero.MODEL_FILE, "empreinte": silero.MODEL_SHA256,
                   "parole_min_s": silero.MIN_SPEECH_S, **cache_info},
        "conditions": CONDITIONS,
        "grille_definie": {"seuil": list(args.seuils), "silence_min_s": list(args.silences), "marge_s": list(args.marges)},
        "sources_evaluees": evaluated,
        "grille": rows,
        "v2_retenue": best,
        "v3": v3,
        "choix": {"regle": "DER sans collar le plus bas sur dev (premier de la grille en cas d'égalité).",
                  "alerte": alert},
        "duree_s": round(time.perf_counter() - t0, 1),
        "git": git_state() if root == REPO_ROOT else None,
    }
    output = args.sortie or root / "results" / "reglage_silero" / f"{now:%Y-%m-%d_%Hh%M}"
    if output.exists() and any(output.iterdir()):
        say(f"Arrêt : {output} n'est pas vide")
        return 1
    write_outputs(output, summary)
    p = best["reglage"]
    say(f"Retenu : seuil {p['seuil']}, silence {p['silence_min_s']} s, marge {p['marge_s']} s "
        f"(DER {best['metriques']['collar_0']['der']:.2f} / {best['metriques']['collar_0_25']['der']:.2f} %)")
    if alert:
        say(f"Alerte : {alert}")
    say(f"Écrit : {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
