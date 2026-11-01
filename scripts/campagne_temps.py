"""Campagne de temps (D21, amendement du 01/11 ; chantier E3a ; planning : jeudi 12/11).

Chaque moteur retenu traite le même sous-ensemble fixe de réunions, une réunion après
l'autre, machine au repos et sur secteur. Les temps du README, de la synthèse et de la
démonstration viennent de cette campagne, et non des expériences (D21, amendement, règle 3).

    uv run python scripts/campagne_temps.py --mesurer-repos   # 5 min, toutes applications fermées
    uv run python scripts/campagne_temps.py --plan            # sous-ensemble, moteurs, durée estimée ; rien ne tourne
    uv run python scripts/campagne_temps.py --repos results/campagne_temps/repos_….json --charge-max 1.5
    uv run python scripts/campagne_temps.py … --peripheriques mps,cpu   # pyannote aussi en CPU seul (long)

Déroulé :

0. Le jour de la campagne, `--mesurer-repos` relève la charge moyenne pendant 5 min, machine
   au repos (toutes applications fermées), et l'écrit dans
   `results/campagne_temps/repos_<date>_<heure>.json`. Le seuil de charge est un réglage
   (`--charge-max`), fixé à partir de cette mesure ; la mesure (`--repos`) et le seuil sont
   consignés dans la sortie de la campagne (journal du cockpit du 01/11).
1. Sous-ensemble : celui du protocole §3.5, `data/splits/<corpus>/temps.txt` (SUMM-RE puis
   AMI), seule définition du sous-ensemble de mesure du temps.
2. Conditions de départ : alimentation sur secteur (`pmset -g batt`) et charge moyenne sur
   1 min au plus `--charge-max`. Le script attend jusqu'à `--attente-max-s` qu'elles soient
   réunies, puis renonce, sauf avec `--ignorer-conditions` (résultats alors marqués non
   conformes).
3. Relevés d'alimentation et de charge toutes les `--intervalle-s` secondes pendant toute la
   campagne, plus un au début et à la fin de chaque réunion.
4. Pour chaque moteur et périphérique : chargement (mesuré à part), préchauffage sur les 60
   premières secondes de la première réunion (protocole §3.5, non compté), puis chaque
   réunion : temps de calcul = lecture de l'audio normalisé + exécution complète, à
   l'horloge murale. Une réunion est conforme si tous ses relevés sont sur secteur et sans
   charge concurrente (charge sur 1 min au-dessus du nombre de cœurs de performance).
5. Synthèse par moteur et périphérique : RTF en rapport des sommes (Σ calcul / Σ durée),
   par corpus, minimum et maximum par réunion ; temps pour 30 min = RTF × 1 800 s ;
   surcoût fixe = durée du préchauffage − RTF × durée de l'extrait (premier appel après
   chargement, comme `scripts/measure_overhead.py`) ; valeurs à reporter dans l'interface
   (`app.moteurs.FIXED_OVERHEAD` et RTF par moteur et périphérique).

Sorties dans `--sortie` (par défaut `results/campagne_temps/<date>_<heure>/`) :
`campagne.json` (tout : sous-ensemble, état git, relevés, mesures, synthèse),
`mesures.csv` (une ligne par réunion), `tableau.md` (tableau et valeurs pour l'interface).

`--factice` : moteur factice de l'application (`app.moteurs.FakeEngine`, aucune inférence),
qui simule un RTF de `--factice-rtf` ; sert à répéter la campagne et aux tests. Ses
résultats sont marqués factices et ne sont jamais reportables ; par défaut ils vont dans un
dossier temporaire. Le moteur factice relit les RTTM de l'expérience source : une réunion
sans RTTM dans cette expérience est consignée en erreur.
"""

from __future__ import annotations

import whospoke  # noqa: F401  (D27 : télémétrie coupée avant tout import tiers)

import argparse
import csv
import gc
import json
import os
import platform
import random
import sys
import tempfile
import time
import wave
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))   # paquet `app` (moteurs de l'application)

from app import moteurs, temps  # noqa: E402
from whospoke import charge, power  # noqa: E402
from whospoke.audio import load_waveform  # noqa: E402
from whospoke.experiment import dataset_uris, git_state, processed_wav  # noqa: E402

CORPORA = ("summre", "ami")
REST_S = 300.0               # mesure de la charge au repos : 5 min
REST_INTERVAL_S = 5.0
WARMUP_S = 60.0              # préchauffage : 60 premières secondes du premier fichier (protocole §3.5)
HALF_HOUR_S = 1800.0

Say = Callable[[str], None]


def say(message: str = "") -> None:
    print(message, flush=True)


# --- Sous-ensemble, moteurs ------------------------------------------------------------------


def select_subset(corpora=CORPORA, splits: Path = REPO_ROOT / "data" / "splits"
                  ) -> tuple[list[tuple[str, str]], dict]:
    """[(corpus, uri)…] dans l'ordre de passage (protocole §3.5 : `temps.txt`), et sa description."""
    chosen = [(corpus, uri) for corpus in corpora for uri in dataset_uris(splits / corpus / "temps.txt")]
    description = {"source": "data/splits/<corpus>/temps.txt (protocole §3.5)",
                   "fichiers": [{"corpus": corpus, "uri": uri} for corpus, uri in chosen]}
    return chosen, description


def engine_plan(keys: list[str], devices: list[str], root: Path = moteurs.EXPERIMENTS_DIR
                ) -> tuple[list[tuple[moteurs.EngineSpec, str]], list[str]]:
    """Couples (moteur, périphérique) à mesurer, et moteurs écartés avec leur motif."""
    pairs, skipped = [], []
    for key in keys:
        spec = moteurs.SPECS[key]
        try:
            moteurs.engine_params(spec, root)
        except moteurs.EngineUnavailable as error:
            skipped.append(f"{spec.label} : {error}")
            continue
        for device in (["cpu"] if spec.cpu_only else devices):
            pairs.append((spec, device))
    return pairs, skipped


def audio_duration(path: Path) -> float | None:
    """Durée d'un WAV d'après son en-tête, sans le lire."""
    try:
        with wave.open(str(path)) as handle:
            return handle.getnframes() / handle.getframerate()
    except (OSError, wave.Error):
        return None


# --- Conditions de départ --------------------------------------------------------------------


def measure_rest(duration_s: float = REST_S, interval_s: float = REST_INTERVAL_S,
                 read: Callable[[], dict] | None = None, sleep: Callable[[float], None] = time.sleep,
                 cores: int | None = None, out: Say = say) -> dict:
    """Charge moyenne relevée toutes les `interval_s` secondes pendant `duration_s`, machine au repos."""
    read = read or (lambda: charge.reading("repos"))
    cores = cores or charge.performance_cores()
    out(f"Mesure de la charge au repos pendant {duration_s / 60:.0f} min : fermer toutes les applications…")
    readings = []
    for index in range(int(duration_s // interval_s) + 1):
        if index:
            sleep(interval_s)
        readings.append(read())
    values = [r["charge_1min"] for r in readings if r.get("charge_1min") is not None]
    summary = {"moyenne": round(sum(values) / len(values), 2), "min": min(values), "max": max(values)} if values else None
    result = {"date": charge.now_iso(), "duree_s": duration_s, "intervalle_s": interval_s,
              "source_charge": charge.SOURCE, "coeurs_performance": cores, "charge_1min": summary,
              "alimentation_conforme": power.is_compliant(readings), "releves": readings}
    if summary:
        out(f"Charge sur 1 min au repos : moyenne {summary['moyenne']}, de {summary['min']} à {summary['max']} "
            f"({cores} cœurs de performance). Fixer --charge-max à partir de ces valeurs.")
    return result


def wait_for_conditions(read: Callable[[], dict], load_max: float, wait_max_s: float, poll_s: float = 15.0,
                        sleep: Callable[[float], None] = time.sleep, out: Say = say) -> tuple[bool, list[dict]]:
    """Attend secteur et charge basse ; (conditions réunies, relevés faits pendant l'attente)."""
    readings: list[dict] = []
    waited = 0.0
    while True:
        record = read()
        readings.append(record)
        on_mains = record.get("source") == "secteur"
        load = record.get("charge_1min")
        quiet = load is not None and load <= load_max
        if on_mains and quiet:
            return True, readings
        problems = ([] if on_mains else [f"alimentation : {record.get('source') or 'illisible'}"]) + \
                   ([] if quiet else [f"charge sur 1 min : {load} > {load_max}"])
        if waited >= wait_max_s:
            out(f"Conditions non réunies après {waited:.0f} s : {', '.join(problems)}")
            return False, readings
        out(f"En attente ({', '.join(problems)})…")
        sleep(poll_s)
        waited += poll_s


# --- Campagne ----------------------------------------------------------------------------------


def run_pair(spec: moteurs.EngineSpec, device: str, subset: list[tuple[str, str]],
             wav_path: Callable[[str, str], Path], factory: Callable, monitor: charge.MachineMonitor,
             cores: int, factice_rtf: float | None = None, out: Say = say) -> dict:
    """Chargement, préchauffage, puis chaque réunion du sous-ensemble, l'une après l'autre."""
    out(f"{spec.label} ({device}) : chargement…")
    start = time.perf_counter()
    engine = factory(spec, device)
    loading_s = time.perf_counter() - start

    def prepare(duration_s: float) -> None:
        if factice_rtf is not None:
            engine.simulated_s = factice_rtf * duration_s

    first_corpus, first_uri = subset[0]
    waveform, sample_rate = load_waveform(wav_path(first_corpus, first_uri))
    excerpt = waveform[:, : int(WARMUP_S * sample_rate)]
    warmup_duration = excerpt.shape[1] / sample_rate
    prepare(warmup_duration)
    start = time.perf_counter()
    engine.run(excerpt, sample_rate, uri=first_uri)
    engine.synchronize()
    warmup_s = time.perf_counter() - start
    del waveform, excerpt

    meetings = []
    for corpus, uri in subset:
        wall_start = time.time()
        monitor.mark("debut_reunion")
        row = {"corpus": corpus, "uri": uri, "debut": charge.now_iso()}
        waveform = None
        try:
            start = time.perf_counter()
            waveform, sample_rate = load_waveform(wav_path(corpus, uri))
            duration_s = waveform.shape[1] / sample_rate
            prepare(duration_s)
            result = engine.run(waveform, sample_rate, uri=uri)
            engine.synchronize()
            compute_s = time.perf_counter() - start
            row |= {"duree_s": round(duration_s, 3), "calcul_s": round(compute_s, 3),
                    "rtf": round(compute_s / duration_s, 5),
                    "n_locuteurs": len(result.annotation.labels()), "erreur": None}
        except Exception as error:  # consignée ; la campagne continue avec la réunion suivante
            row |= {"duree_s": None, "calcul_s": None, "rtf": None, "n_locuteurs": None,
                    "erreur": f"{type(error).__name__}: {error}"}
        waveform = None   # libère le signal avant la réunion suivante
        monitor.mark("fin_reunion")
        readings = monitor.between(wall_start, time.time())
        mains = power.is_compliant(readings)
        concurrent = charge.concurrent_load(readings, cores)
        row |= {"fin": charge.now_iso(), "alimentation_conforme": mains, "charge_concurrente": concurrent,
                "charge_1min_max": max((r["charge_1min"] for r in readings if r.get("charge_1min") is not None),
                                       default=None),
                "conforme": bool(row["erreur"] is None and mains is True and concurrent is False)}
        meetings.append(row)
        rtf_text = f"RTF {row['rtf']:.4f}" if row["rtf"] is not None else f"ERREUR {row['erreur']}"
        out(f"  {uri} : {rtf_text}" + ("" if row["conforme"] else " (non conforme)"))
    del engine
    gc.collect()
    return {"moteur": spec.key, "libelle": spec.label, "experience_source": spec.source_exp, "peripherique": device,
            "chargement_s": round(loading_s, 3), "prechauffage": {"uri": first_uri, "duree_s": round(warmup_duration, 3),
                                                                 "calcul_s": round(warmup_s, 3)},
            "reunions": meetings}


def summarize(run: dict) -> dict:
    """RTF en rapport des sommes, par corpus, extrêmes ; temps pour 30 min ; surcoût fixe."""
    ok = [m for m in run["reunions"] if m["erreur"] is None]
    if not ok:
        return {"rtf": None, "rtf_par_corpus": {}, "rtf_min": None, "rtf_max": None, "temps_30min_s": None,
                "surcout_fixe_s": None, "n_reunions": 0, "n_erreurs": len(run["reunions"]), "conforme": False}
    rtf = sum(m["calcul_s"] for m in ok) / sum(m["duree_s"] for m in ok)
    by_corpus = {}
    for corpus in dict.fromkeys(m["corpus"] for m in ok):
        rows = [m for m in ok if m["corpus"] == corpus]
        by_corpus[corpus] = round(sum(m["calcul_s"] for m in rows) / sum(m["duree_s"] for m in rows), 5)
    warmup = run["prechauffage"]
    return {
        "rtf": round(rtf, 5), "rtf_par_corpus": by_corpus,
        "rtf_min": min(m["rtf"] for m in ok), "rtf_max": max(m["rtf"] for m in ok),
        "temps_30min_s": round(rtf * HALF_HOUR_S, 1),
        "surcout_fixe_s": round(max(0.0, warmup["calcul_s"] - rtf * warmup["duree_s"]), 2),
        "n_reunions": len(ok), "n_erreurs": len(run["reunions"]) - len(ok),
        "conforme": all(m["conforme"] for m in run["reunions"]),
    }


def interface_values(runs: list[dict], date: str) -> dict:
    """Valeurs à reporter dans l'interface : RTF et surcoût fixe par (moteur, périphérique)."""
    rows = [(run["moteur"], run["peripherique"], run["synthese"]) for run in runs if run["synthese"]["rtf"] is not None]
    lines = [f"# Campagne de temps du {date} (scripts/campagne_temps.py)."]
    lines.append("FIXED_OVERHEAD: dict[tuple[str, str], FixedOverhead] = {")
    lines += [f"    ({key!r}, {device!r}): FixedOverhead({s['surcout_fixe_s']}, {date!r}),"
              for key, device, s in rows]
    lines.append("}")
    lines.append("CAMPAIGN_RTF: dict[tuple[str, str], float] = {")
    lines += [f"    ({key!r}, {device!r}): {s['rtf']}," for key, device, s in rows]
    lines.append("}")
    return {"rtf": {f"{key}/{device}": s["rtf"] for key, device, s in rows},
            "surcout_fixe_s": {f"{key}/{device}": s["surcout_fixe_s"] for key, device, s in rows},
            "code": "\n".join(lines)}


def _duration_text(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    minutes, rest = divmod(round(seconds), 60)
    return f"{minutes} min {rest:02d} s" if minutes else f"{rest} s"


def _rest_text(campaign: dict) -> str:
    rest = (campaign.get("charge_au_repos") or {}).get("charge_1min")
    measured = (f"charge sur 1 min au repos mesurée le {campaign['charge_au_repos']['date'][:16]} : moyenne "
                f"{rest['moyenne']}, de {rest['min']} à {rest['max']}" if rest else "charge au repos non mesurée")
    return f"Seuil de charge au départ : {campaign['conditions_depart']['charge_max']} ; {measured}."


def markdown(campaign: dict) -> str:
    """Tableau de la campagne et valeurs pour l'interface."""
    head = ["# Campagne de temps", ""]
    if campaign["factice"]:
        head += ["**ESSAI AVEC LE MOTEUR FACTICE : aucune inférence, temps simulés, non reportables.**", ""]
    if not campaign["conditions_depart"]["reunies"]:
        head += ["**Conditions de départ non réunies (`--ignorer-conditions`) : résultats non reportables.**", ""]
    subset = ", ".join(f["uri"] for f in campaign["sous_ensemble"]["fichiers"])
    head += [f"Date : {campaign['date']}. Commit : `{campaign['git']['commit'][:12]}`"
             f"{'' if campaign['git']['clean'] else ' (arbre non propre)'}. "
             f"Machine : {campaign['machine']['plateforme']}, {campaign['machine']['coeurs_performance']} cœurs "
             f"de performance.", "",
             f"Sous-ensemble ({campaign['sous_ensemble']['source']}) : {subset}.", "",
             _rest_text(campaign), "",
             "| Moteur | Périphérique | RTF | RTF par réunion (min–max) | Temps pour 30 min | Surcoût fixe | "
             "Chargement | Réunions | Conforme |",
             "|---|---|---|---|---|---|---|---|---|"]
    for run in campaign["mesures"]:
        s = run["synthese"]
        head.append(
            f"| {run['libelle']} | {run['peripherique']} | {s['rtf'] if s['rtf'] is not None else '—'} | "
            f"{s['rtf_min'] if s['rtf_min'] is not None else '—'}–{s['rtf_max'] if s['rtf_max'] is not None else '—'} | "
            f"{_duration_text(s['temps_30min_s'])} | {s['surcout_fixe_s'] if s['surcout_fixe_s'] is not None else '—'} s | "
            f"{run['chargement_s']:.1f} s | {s['n_reunions']}" + (f" ({s['n_erreurs']} en erreur)" if s["n_erreurs"] else "")
            + f" | {'oui' if s['conforme'] else 'non'} |")
    head += ["", "Temps pour 30 min = RTF × 1 800 s, hors chargement des modèles et surcoût du premier appel. "
             "Une ligne non conforme (batterie, charge concurrente ou erreur) n'est jamais reportée (D21).", "",
             "## Valeurs pour l'interface", "", "```python", campaign["interface"]["code"], "```", ""]
    return "\n".join(head)


def write_outputs(directory: Path, campaign: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "campagne.json").write_text(json.dumps(campaign, ensure_ascii=False, indent=2) + "\n")
    fields = ["moteur", "peripherique", "corpus", "uri", "duree_s", "calcul_s", "rtf", "n_locuteurs",
              "alimentation_conforme", "charge_concurrente", "charge_1min_max", "conforme", "debut", "fin", "erreur"]
    with (directory / "mesures.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for run in campaign["mesures"]:
            for row in run["reunions"]:
                writer.writerow({key: row.get(key) for key in fields} | {"moteur": run["moteur"],
                                                                         "peripherique": run["peripherique"]})
    (directory / "tableau.md").write_text(markdown(campaign))


def campaign(pairs: list[tuple[moteurs.EngineSpec, str]], subset: list[tuple[str, str]], subset_info: dict,
             factory: Callable, wav_path: Callable[[str, str], Path] = processed_wav,
             monitor: charge.MachineMonitor | None = None, cores: int | None = None,
             load_max: float = 1.0, rest: dict | None = None, wait_max_s: float = 600.0,
             ignore_conditions: bool = False,
             factice_rtf: float | None = None, sleep: Callable[[float], None] = time.sleep, out: Say = say) -> dict:
    """Campagne complète ; renvoie le dictionnaire écrit dans campagne.json."""
    cores = cores or charge.performance_cores()
    monitor = monitor or charge.MachineMonitor()
    reached, waiting = wait_for_conditions(lambda: charge.reading("attente", monitor.power_reader, monitor.load_reader),
                                           load_max, wait_max_s, sleep=sleep, out=out)
    if not reached and not ignore_conditions:
        raise RuntimeError("Conditions de départ non réunies (secteur, charge basse) : campagne non lancée")
    state = git_state()
    result = {
        "date": charge.now_iso(), "factice": factice_rtf is not None,
        "git": {"commit": state["commit"], "clean": state["clean"], "fichiers_non_commites": state["dirty"]},
        "machine": {"plateforme": platform.platform(), "processeur": platform.processor(),
                    "coeurs_performance": cores, "coeurs": os.cpu_count()},
        "charge_au_repos": rest,
        "conditions_depart": {"reunies": reached, "charge_max": load_max, "releves": waiting},
        "sous_ensemble": subset_info, "regles": {
            "rtf": "Σ temps de calcul / Σ durée, réunions sans erreur",
            "temps_calcul": "lecture de l'audio normalisé + exécution complète, horloge murale (protocole §3.5)",
            "prechauffage_s": WARMUP_S, "temps_30min": "RTF × 1 800 s",
            "surcout_fixe": "durée du préchauffage − RTF × durée de l'extrait",
            "conforme": "tous les relevés d'une réunion sur secteur et charge sur 1 min ≤ cœurs de performance"},
    }
    monitor.start()
    runs = []
    try:
        for spec, device in pairs:
            run = run_pair(spec, device, subset, wav_path, factory, monitor, cores, factice_rtf, out)
            run["synthese"] = summarize(run)
            if not reached:
                run["synthese"]["conforme"] = False
            runs.append(run)
    finally:
        monitor.stop()
    result["mesures"] = runs
    result["releves"] = {"intervalle_s": monitor.interval_s, "source_charge": charge.SOURCE,
                         "commande_alimentation": " ".join(power.COMMAND), "releves": monitor.readings}
    result["interface"] = interface_values(runs, result["date"][:10])
    return result


# --- Ligne de commande ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Campagne de temps (D21, amendement du 01/11) : chaque moteur "
                                                 "retenu sur un sous-ensemble fixe, machine au repos, sur secteur.")
    parser.add_argument("--plan", action="store_true", help="affiche le plan et la durée estimée, sans rien lancer")
    parser.add_argument("--moteurs", default=",".join(moteurs.SPECS),
                        help="moteurs de l'application, séparés par des virgules (défaut : tous les disponibles)")
    parser.add_argument("--peripheriques", default="mps",
                        help="périphériques des moteurs qui ne sont pas en CPU seul (défaut : mps ; ex. mps,cpu)")
    parser.add_argument("--mesurer-repos", action="store_true",
                        help="mesure la charge au repos pendant 5 min et l'écrit dans results/campagne_temps/")
    parser.add_argument("--repos", type=Path, default=None,
                        help="fichier de la mesure au repos du jour (--mesurer-repos), consigné ; obligatoire hors --factice")
    parser.add_argument("--charge-max", type=float, default=None,
                        help="seuil : charge sur 1 min maximale au départ, fixé d'après la mesure au repos ; "
                             "obligatoire hors --factice")
    parser.add_argument("--attente-max-s", type=float, default=600.0,
                        help="attente maximale des conditions de départ (s, défaut : 600)")
    parser.add_argument("--intervalle-s", type=float, default=30.0, help="intervalle des relevés (s, défaut : 30)")
    parser.add_argument("--ignorer-conditions", action="store_true",
                        help="lance même hors conditions ; résultats marqués non conformes")
    parser.add_argument("--sortie", type=Path, default=None,
                        help="dossier des résultats (défaut : results/campagne_temps/<date>_<heure>/)")
    parser.add_argument("--factice", action="store_true",
                        help="moteur factice de l'application, aucune inférence (répétition, tests)")
    parser.add_argument("--factice-rtf", type=float, default=0.002, help="RTF simulé en mode factice (défaut : 0,002)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    keys = [key.strip() for key in args.moteurs.split(",") if key.strip()]
    unknown = [key for key in keys if key not in moteurs.SPECS]
    if unknown:
        say(f"Moteurs inconnus : {', '.join(unknown)} (connus : {', '.join(moteurs.SPECS)})")
        return 2
    if args.mesurer_repos:
        rest = measure_rest()
        path = (args.sortie or REPO_ROOT / "results" / "campagne_temps") / f"repos_{datetime.now():%Y-%m-%d_%Hh%M}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rest, ensure_ascii=False, indent=2) + "\n")
        say(f"Écrit : {path}")
        return 0
    devices = [d.strip() for d in args.peripheriques.split(",") if d.strip()]
    subset, info = select_subset()
    pairs, skipped = engine_plan(keys, devices)
    for reason in skipped:
        say(f"Écarté : {reason}")
    if not pairs:
        say("Aucun moteur disponible")
        return 1
    missing = [str(processed_wav(c, u)) for c, u in subset if not processed_wav(c, u).is_file()]
    durations = [audio_duration(processed_wav(c, u)) for c, u in subset]
    total_audio = sum(d for d in durations if d)
    say(f"Sous-ensemble ({info['source']}) : " + ", ".join(u for _, u in subset)
        + (f" ; {total_audio / 60:.0f} min d'audio" if total_audio else ""))
    estimate = 0.0
    for spec, device in pairs:
        measured = temps.measured_rtf(spec.source_exp, device, moteurs.source_device(spec))
        guess = f"≈ {_duration_text(measured.rtf * total_audio)}" if measured and total_audio else "durée inconnue"
        estimate += measured.rtf * total_audio if measured and total_audio else 0.0
        say(f"  {spec.label} ({device}) : {guess}")
    if estimate:
        say(f"Durée estimée (RTF des expériences, hors chargements) : {_duration_text(estimate)}")
    if args.plan:
        if missing:
            say("Audio normalisé absent : " + ", ".join(missing))
        return 0
    if not args.factice and (args.repos is None or args.charge_max is None):
        say("Arrêt : --repos (mesure au repos du jour, --mesurer-repos) et --charge-max sont obligatoires.")
        return 2
    if missing and not args.factice:
        say("Audio normalisé absent : " + ", ".join(missing))
        return 1
    rest = json.loads(args.repos.read_text()) if args.repos else None
    load_max = args.charge_max if args.charge_max is not None else float(charge.performance_cores())
    say("Rappel : machine au repos, sur secteur, aucune autre session ni expérience ouverte (D21).")
    if args.factice:
        factory = lambda spec, device: moteurs.FakeEngine(spec, simulated_s=1.0, ticks_per_step=1)  # noqa: E731
    else:
        factory = moteurs.build_engine
    output = args.sortie or (Path(tempfile.mkdtemp(prefix="campagne-factice-")) if args.factice else
                             REPO_ROOT / "results" / "campagne_temps" / datetime.now().strftime("%Y-%m-%d_%Hh%M"))
    try:
        result = campaign(pairs, subset, info, factory, monitor=charge.MachineMonitor(args.intervalle_s),
                          load_max=load_max, rest=rest, wait_max_s=args.attente_max_s,
                          ignore_conditions=args.ignorer_conditions,
                          factice_rtf=args.factice_rtf if args.factice else None)
    except RuntimeError as error:
        say(f"Arrêt : {error}")
        return 1
    write_outputs(output, result)
    say(f"Écrit : {output}/campagne.json, mesures.csv, tableau.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
