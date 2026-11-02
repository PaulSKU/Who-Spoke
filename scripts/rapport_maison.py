"""Rapport d'évaluation du corpus maison, enregistrement par enregistrement (chantier E3b ; A9).

    uv run python scripts/rapport_maison.py --plan                                  # références et moteurs ; rien ne tourne
    uv run python scripts/rapport_maison.py --controle-reseau "journal du 09/11"    # évaluation

Le corpus maison est un **test qualitatif** (audit R-E3) : quelques enregistrements, aucun
réglage sur ce corpus, résultats rapportés fichier par fichier. Chaque enregistrement est
évalué dès que sa référence existe dans `data/processed/maison/` (audio normalisé,
`rttm/`, `uem/`, écrits par `scripts/data/maison.py convertir`), par tous les moteurs
retenus de l'application (`app/moteurs.py`, mêmes réglages que l'interface).

Pour chaque fichier et chaque moteur : toutes les métriques du protocole (DER et ses
composantes, JER, DER par zone avec et sans chevauchement) dans les deux conditions de
collar, chevauchements comptés (`DiarizationEvaluator`), le nombre de locuteurs de la
référence et de l'hypothèse, et la condition d'enregistrement (salle réverbérante, visio,
bruit de fond) lue dans `data/raw/maison/<Mxx>/metadonnees.yaml`. Les valeurs globales
(rapport des sommes, protocole §4) sont données à titre indicatif ; l'intervalle de
confiance par bootstrap (protocole §4) n'est calculé qu'à partir de 5 fichiers.

Hypothèses mises en cache dans `<sortie>/hypotheses/<moteur>/` avec leur signature
(moteur, expérience source, paramètres, périphérique) : une nouvelle référence ne fait
tourner les moteurs que sur le nouveau fichier ; `--recalculer` refait tout.

Confidentialité (D27, notice de consentement) : tout reste sur cette machine. Les sorties
vont par défaut dans `data/processed/maison/rapport/` (non versionné) : même une durée ou
un nombre de locuteurs décrit un enregistrement. Ce que le rendu en publie est décidé par
le cockpit. Les moteurs tournent hors ligne (`HF_HUB_OFFLINE=1`, télémétrie coupée), et
D27 exige une exécution courte sous relevé réseau avant toute exécution sur ce corpus :
`--controle-reseau` en consigne la référence (date ou entrée du journal) et est obligatoire.
"""

from __future__ import annotations

import whospoke  # noqa: F401  (D27 : télémétrie coupée avant tout import tiers)

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))   # paquet `app` (moteurs de l'application), importé à l'usage

from whospoke import charge, power  # noqa: E402
from whospoke.experiment import DATA_DIR, git_state, load_rttm, load_uem  # noqa: E402
from whospoke.maison import metadonnees as meta  # noqa: E402

PROCESSED = DATA_DIR / "processed" / "maison"
RAW = DATA_DIR / "raw" / "maison"
OUTPUT = PROCESSED / "rapport"
MIN_BOOTSTRAP_FILES = 5          # pas d'intervalle de confiance en dessous
QUALITATIVE = ("Test qualitatif : corpus maison de {n} enregistrement(s), évalué fichier par fichier, sans aucun "
               "réglage sur ce corpus. Les valeurs globales sont indicatives ; aucune conclusion statistique.")

Say = Callable[[str], None]


def say(message: str = "") -> None:
    print(message, flush=True)


# --- Enregistrements et moteurs -------------------------------------------------------------


def recordings(processed: Path = PROCESSED, raw: Path = RAW) -> tuple[list[dict], list[str]]:
    """Enregistrements dont la référence est complète (audio, RTTM, UEM), et motifs des autres."""
    found, incomplete = [], []
    for rttm in sorted((processed / "rttm").glob("maison__M*.rttm")):
        uri = rttm.stem
        session = uri.split("__", 1)[1]
        paths = {"wav": processed / f"{uri}.wav", "rttm": rttm, "uem": processed / "uem" / f"{uri}.uem"}
        missing = [kind for kind, path in paths.items() if not path.is_file()]
        if missing:
            incomplete.append(f"{uri} : {', '.join(missing)} absent(s)")
            continue
        try:
            metadata = meta.load_optional(raw / session, session)
            condition = metadata.condition_label if metadata else "non renseignée"
        except meta.MetadataError as error:
            condition = f"métadonnées invalides ({error})"
        found.append({"uri": uri, "session": session, "condition": condition} | {k: str(v) for k, v in paths.items()})
    return found, incomplete


def available_engines(keys: list[str], device: str, root: Path | None = None) -> tuple[list[tuple], list[str]]:
    """[(spec, périphérique, paramètres)…] des moteurs utilisables, et motifs des autres."""
    from app import moteurs

    root = root or moteurs.EXPERIMENTS_DIR
    pairs, skipped = [], []
    for key in keys:
        spec = moteurs.SPECS[key]
        try:
            params = moteurs.engine_params(spec, root)
        except moteurs.EngineUnavailable as error:
            skipped.append(f"{spec.label} : {error}")
            continue
        pairs.append((spec, "cpu" if spec.cpu_only else device, params))
    return pairs, skipped


def signature(spec, device: str, params: dict) -> tuple[dict, str]:
    """Ce qui détermine une hypothèse, et son empreinte (cache)."""
    data = {"moteur": spec.key, "experience_source": spec.source_exp, "peripherique": device, "parametres": params}
    digest = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return data, digest


# --- Hypothèses ------------------------------------------------------------------------------


def hypotheses(recs: list[dict], pairs: list[tuple], factory: Callable, output: Path,
               recompute: bool = False, out: Say = say) -> dict[tuple[str, str], Path]:
    """RTTM de chaque (moteur, fichier), calculés seulement s'ils manquent ou ont changé de signature."""
    from whospoke.audio import load_waveform

    commit = git_state()["commit"]
    paths: dict[tuple[str, str], Path] = {}
    for spec, device, params in pairs:
        sig, digest = signature(spec, device, params)
        directory = output / "hypotheses" / spec.key
        todo = []
        for rec in recs:
            rttm, info = directory / f"{rec['uri']}.rttm", directory / f"{rec['uri']}.json"
            paths[(spec.key, rec["uri"])] = rttm
            cached = info.is_file() and rttm.is_file() and json.loads(info.read_text()).get("empreinte") == digest
            if recompute or not cached:
                todo.append(rec)
        if not todo:
            out(f"{spec.label} : hypothèses déjà calculées ({len(recs)})")
            continue
        out(f"{spec.label} ({device}) : chargement, puis {len(todo)} fichier(s)…")
        engine = factory(spec, device)
        directory.mkdir(parents=True, exist_ok=True)
        for rec in todo:
            waveform, sample_rate = load_waveform(rec["wav"])
            start = time.perf_counter()
            result = engine.run(waveform, sample_rate, uri=rec["uri"])
            engine.synchronize()
            compute_s = time.perf_counter() - start
            annotation = result.annotation
            annotation.uri = rec["uri"]
            with (directory / f"{rec['uri']}.rttm").open("w") as handle:
                annotation.write_rttm(handle)
            (directory / f"{rec['uri']}.json").write_text(json.dumps(
                sig | {"empreinte": digest, "commit": commit, "date": charge.now_iso(),
                       "calcul_s": round(compute_s, 3), "infos": result.infos}, ensure_ascii=False, indent=2, default=str))
            out(f"  {rec['uri']} : {len(annotation.labels())} locuteur(s), {compute_s:.1f} s")
        del engine
    return paths


# --- Évaluation ------------------------------------------------------------------------------


def evaluate(recs: list[dict], pairs: list[tuple], hyp_paths: dict[tuple[str, str], Path]) -> list[dict]:
    """Par moteur : lignes par fichier (protocole), valeurs globales indicatives, bootstrap si ≥ 5 fichiers."""
    from whospoke.evaluation.metrics import CONDITIONS, DiarizationEvaluator, bootstrap_der_ci

    results = []
    for spec, device, _ in pairs:
        evaluator = DiarizationEvaluator()
        rows = []
        for rec in recs:
            reference = load_rttm(Path(rec["rttm"]), rec["uri"])
            uem = load_uem(Path(rec["uem"]), rec["uri"])
            hypothesis = load_rttm(hyp_paths[(spec.key, rec["uri"])], rec["uri"])
            evaluator.add(reference, hypothesis, uem=uem)
            rows.append({"session": rec["session"], "condition": rec["condition"],
                         "duree_uem_s": round(uem.duration(), 3)})
        per_file = [extra | row for extra, row in zip(rows, evaluator.per_file())]
        bootstrap = {}
        for name, suffix in (("collar_0", "c0"), ("collar_0_25", "c025")):
            if len(per_file) < MIN_BOOTSTRAP_FILES:
                bootstrap[name] = None
                continue
            errors = [r[f"manquee_{suffix}_s"] + r[f"fausse_alarme_{suffix}_s"] + r[f"confusion_{suffix}_s"]
                      for r in per_file]
            totals = [r[f"duree_reference_{suffix}_s"] for r in per_file]
            bootstrap[name] = bootstrap_der_ci(errors, totals)
        report = evaluator.report() if per_file else None
        results.append({"moteur": spec.key, "libelle": spec.label, "experience_source": spec.source_exp,
                        "peripherique": device, "par_fichier": per_file,
                        "global_indicatif": report and {name: report[name] for name in CONDITIONS}
                        | {"n_locuteurs": report["n_locuteurs"]},
                        "bootstrap": bootstrap})
    return results


def _pct(value) -> str:
    return "—" if value is None else f"{value:.1f}"


def markdown(report: dict) -> str:
    n = len(report["enregistrements"])
    lines = ["# Corpus maison : évaluation par enregistrement", "",
             f"**{QUALITATIVE.format(n=n)}**", "",
             f"Date : {report['date']}. Commit : `{report['git']['commit'][:12]}`"
             f"{'' if report['git']['clean'] else ' (arbre non propre)'}. Contrôle réseau D27 : "
             f"{report['controle_reseau_d27']}.", "",
             "Taux en %, chevauchements comptés ; c0 : sans collar ; c0,25 : collar de 0,25 s. "
             "Manquée, fausse alarme et confusion sont les composantes du DER sans collar.", ""]
    for result in report["resultats"]:
        lines += [f"## {result['libelle']} ({result['peripherique']}, réglages d'{result['experience_source']})", "",
                  "| Enregistrement | Condition | UEM | Locuteurs réf. / hyp. | DER c0 | Manquée | Fausse alarme | "
                  "Confusion | DER c0,25 | JER c0 | DER chevauchement | DER sans chevauchement |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in result["par_fichier"]:
            lines.append(
                f"| {r['session']} | {r['condition']} | {r['duree_uem_s'] / 60:.1f} min | "
                f"{r['n_locuteurs_reference']} / {r['n_locuteurs_hypothese']} | {_pct(r['der_c0'])} | "
                f"{_pct(r['manquee_c0'])} | {_pct(r['fausse_alarme_c0'])} | {_pct(r['confusion_c0'])} | "
                f"{_pct(r['der_c025'])} | {_pct(r['jer_c0'])} | {_pct(r['der_chevauchement'])} | "
                f"{_pct(r['der_sans_chevauchement'])} |")
        overall = result["global_indicatif"]
        if overall:
            lines += ["", f"Global indicatif (rapport des sommes) : DER c0 {_pct(overall['collar_0']['der'])} %, "
                          f"DER c0,25 {_pct(overall['collar_0_25']['der'])} %."]
        ci = result["bootstrap"].get("collar_0")
        lines += ["", (f"Intervalle de confiance à 95 % (bootstrap sur les fichiers), DER c0 : "
                       f"[{ci['borne_inf']:.1f} ; {ci['borne_sup']:.1f}]." if ci else
                       f"Pas d'intervalle de confiance : moins de {MIN_BOOTSTRAP_FILES} fichiers."), ""]
    if report["incomplets"]:
        lines += ["## Références incomplètes (non évaluées)", ""] + [f"- {item}" for item in report["incomplets"]] + [""]
    if report["moteurs_ecartes"]:
        lines += ["## Moteurs écartés", ""] + [f"- {item}" for item in report["moteurs_ecartes"]] + [""]
    return "\n".join(lines)


def write_outputs(output: Path, report: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "rapport.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n")
    rows = [{"moteur": r["moteur"], "peripherique": r["peripherique"]} | row
            for r in report["resultats"] for row in r["par_fichier"]]
    if rows:
        with (output / "par_fichier.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (output / "rapport.md").write_text(markdown(report))


def build_report(recs: list[dict], incomplete: list[str], pairs: list[tuple], skipped: list[str],
                 factory: Callable, output: Path, network_check: str, recompute: bool = False,
                 monitor: charge.MachineMonitor | None = None, out: Say = say) -> dict:
    """Hypothèses manquantes, évaluation, rapport (renvoyé et écrit dans `output`)."""
    monitor = monitor or charge.MachineMonitor(interval_s=60.0)
    monitor.start()
    try:
        hyp_paths = hypotheses(recs, pairs, factory, output, recompute, out)
    finally:
        monitor.stop()
    state = git_state()
    report = {
        "date": charge.now_iso(), "mention": QUALITATIVE.format(n=len(recs)),
        "git": {"commit": state["commit"], "clean": state["clean"]},
        "controle_reseau_d27": network_check,
        "enregistrements": [{k: rec[k] for k in ("uri", "session", "condition")} for rec in recs],
        "incomplets": incomplete, "moteurs_ecartes": skipped,
        "bootstrap_min_fichiers": MIN_BOOTSTRAP_FILES,
        "resultats": evaluate(recs, pairs, hyp_paths),
        "releves": {"alimentation_conforme": power.is_compliant(monitor.readings), "releves": monitor.readings},
    }
    write_outputs(output, report)
    return report


# --- Ligne de commande ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Évaluation par enregistrement du corpus maison (test qualitatif).")
    parser.add_argument("--plan", action="store_true", help="liste références et moteurs, sans rien lancer")
    parser.add_argument("--controle-reseau", default=None,
                        help="référence du contrôle réseau D27 fait avant l'exécution (date ou entrée du journal) ; "
                             "obligatoire hors --plan")
    parser.add_argument("--moteurs", default=None,
                        help="moteurs de l'application, séparés par des virgules (défaut : tous les disponibles)")
    parser.add_argument("--peripherique", default="auto", help="périphérique des moteurs hors CPU seul (défaut : auto)")
    parser.add_argument("--references", type=Path, default=PROCESSED, help="dossier des références (défaut : data/processed/maison/)")
    parser.add_argument("--sessions", type=Path, default=RAW, help="dossier des sessions (défaut : data/raw/maison/)")
    parser.add_argument("--sortie", type=Path, default=None,
                        help="dossier du rapport (défaut : data/processed/maison/rapport/, non versionné)")
    parser.add_argument("--recalculer", action="store_true", help="recalcule toutes les hypothèses")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from whospoke.cli import configure_environment

    configure_environment(os.environ)   # hors ligne avant tout import de huggingface_hub (D27)
    from app import moteurs
    from whospoke.device import select_device

    keys = [k.strip() for k in (args.moteurs or ",".join(moteurs.SPECS)).split(",") if k.strip()]
    unknown = [k for k in keys if k not in moteurs.SPECS]
    if unknown:
        say(f"Moteurs inconnus : {', '.join(unknown)}")
        return 2
    recs, incomplete = recordings(args.references, args.sessions)
    device = select_device(args.peripherique).type
    pairs, skipped = available_engines(keys, device)
    say(f"Références complètes : {', '.join(r['uri'] for r in recs) or 'aucune'}")
    for item in incomplete + skipped:
        say(f"  écarté : {item}")
    say("Moteurs : " + ", ".join(f"{spec.label} ({dev})" for spec, dev, _ in pairs))
    if args.plan:
        return 0
    if not recs or not pairs:
        say("Rien à évaluer.")
        return 1
    if not args.controle_reseau:
        say("Arrêt : --controle-reseau obligatoire (D27 : exécution courte sous relevé réseau avant toute "
            "exécution sur le corpus maison ; indiquer la date ou l'entrée du journal).")
        return 2
    output = args.sortie or args.references / "rapport"
    build_report(recs, incomplete, pairs, skipped, moteurs.build_engine, output, args.controle_reseau,
                 args.recalculer)
    say(f"Écrit : {output}/rapport.md, par_fichier.csv, rapport.json (non versionné)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
