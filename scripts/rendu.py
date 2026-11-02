"""Tableaux et figures du rendu (chantier E7), générés dans `docs/rendu/` (versionné).

    uv run python scripts/rendu.py              # régénère docs/rendu/
    uv run python scripts/rendu.py --verifier   # code 1 si docs/rendu/ n'est plus à jour

Sources, toutes lues en lecture seule sous `--racine` (le dépôt par défaut) :

- `results/leaderboard.csv` : contrôle de concordance avec les results_*.json (DER dans
  les deux conditions de collar, à 0,005 point près) ;
- `experiments/EXP-…/results_<corpus>_<partition>.json` et `per_file_<corpus>_<partition>.csv`,
  lus par le code de l'onglet Avancement (`app.avancement.read_items`) ;
- `docs/constats.yaml` (`app.constats.read`) : sous chaque tableau, les constats dont une
  source est une expérience du tableau ;
- `configs/summre_degrade.yaml` : conditions de D24 et liste des réunions Zoom ;
- `results/campagne_temps/<date>_<heure>/campagne.json` : campagne de temps du 12/11 (D21).

Fichiers produits :

- `README.md` : index, contrôles ;
- `systemes.md` : systèmes en condition réaliste, par corpus, partition test ;
- `oracles.md` : décomposition de l'erreur par les oracles (`app.avancement.ORACLE_SERIES`) ;
- `robustesse.md` : D24, moteur × condition, écart à `propre`, sous-groupes Zoom et autres ;
- `temps.md` : campagne de temps ;
- `figures/systemes_reference.svg` et `figures/systemes_reference_etroit.svg` : le
  graphique de l'onglet Avancement (`app.graphique.svg`, mêmes barres que
  `app.avancement.reference_systems`), rendu autonome : les règles `.av-chart` et les
  teintes de `app/static/interface.css` y sont recopiées à la génération, en clair et en
  sombre (`prefers-color-scheme`).

Écarts à la référence : bootstrap apparié sur les fichiers (protocole §4 ;
`whospoke.evaluation.metrics.bootstrap_der_ci`, 1 000 tirages, graine 0), DER en rapport
des sommes, à partir des durées d'erreur des per_file. Pas d'intervalle sous
`MIN_BOOTSTRAP_FILES` fichiers (même seuil que `scripts/rapport_maison.py`) : c'est le cas
du sous-groupe Zoom de SUMM-RE test (3 réunions). La sortie ne contient ni date de
génération ni chemin local : deux générations sur les mêmes sources sont identiques.
"""

from __future__ import annotations

import whospoke  # noqa: F401  (D27 : télémétrie coupée avant tout import tiers)

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))   # paquet `app` (code de l'onglet Avancement)

from app import avancement as av  # noqa: E402
from app import constats as constats_file  # noqa: E402
from app import graphique  # noqa: E402
from whospoke.evaluation.metrics import bootstrap_der_ci, count_wins  # noqa: E402

OUTPUT = Path("docs") / "rendu"
LEADERBOARD = Path("results") / "leaderboard.csv"
CAMPAIGNS = Path("results") / "campagne_temps"
DEGRADE_CONFIG = Path("configs") / "summre_degrade.yaml"
CSS = Path("app") / "static" / "interface.css"
TOLERANCE = 0.005                # concordance leaderboard / results_*.json, en points
MIN_BOOTSTRAP_FILES = 5          # pas d'intervalle de confiance en dessous (scripts/rapport_maison.py)
N_RESAMPLES, SEED = 1000, 0      # protocole §4
RESAMPLES_TEXT = "1 000"
PARTITION = "test"
# Conditions de collar : (clé du per_file, clé de results.json, libellé).
COLLARS = (("c0", "collar_0", "sans collar"), ("c025", "collar_0_25", "collar 0,25 s"))
ROBUSTNESS_CORPUS = re.compile(r"^summre-(?P<condition>[a-z0-9]+)$")    # D24 §2 : results_summre-<condition>_test.json
CLEAN = "propre"
FONT = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"   # app/theme.py


# --- Mise en forme ------------------------------------------------------------------


def num(value: float | None, digits: int = 2, sign: bool = False) -> str:
    if value is None:
        return "—"
    text = f"{value:{'+' if sign else ''}.{digits}f}".replace(".", ",")
    return text.replace("-", "\u2212", 1) if text.startswith("-") else text


def pct(value: float | None) -> str:
    return "—" if value is None else f"{num(value)} %"


def cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def md_table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(cell(c) for c in row) + " |" for row in rows]
    return lines


def duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    minutes, rest = divmod(round(seconds), 60)
    return f"{minutes} min {rest:02d} s" if minutes else f"{rest} s"


# --- Lecture ------------------------------------------------------------------------


@dataclass(eq=False)
class Run:
    """Une expérience évaluée sur un corpus et une partition."""
    item: av.Item
    corpus: str
    partition: str
    data: dict
    per_file: dict[str, dict[str, float]] | None    # uri -> valeurs numériques

    @property
    def metrics(self) -> dict:
        return self.data.get("metriques") or {}

    def der(self, collar: str) -> float | None:
        return (self.metrics.get(collar) or {}).get("der")

    @property
    def commit(self) -> str:
        return str(self.data.get("git_commit") or "?")

    @property
    def invalidated(self) -> bool:
        return bool(self.data.get("invalidee"))


def _numbers(row: dict[str, str]) -> dict[str, float]:
    values = {}
    for key, text in row.items():
        try:
            values[key] = float(text)
        except (TypeError, ValueError):
            continue
    return values


def read_per_file(directory: Path, corpus: str, partition: str) -> dict[str, dict[str, float]] | None:
    path = directory / f"per_file_{corpus}_{partition}.csv"
    if not path.is_file():
        return None
    with path.open(newline="") as handle:
        return {row["uri"]: _numbers(row) for row in csv.DictReader(handle) if row.get("uri")}


class Repository:
    """Expériences du dépôt (code de l'onglet Avancement), results et per_file indexés."""

    def __init__(self, root: Path):
        self.root = root
        self.items = av.read_items(root)
        self.by_id = {item.id: item for item in self.items}
        self.runs: dict[tuple[str, str, str], Run] = {}
        for item in self.items:
            if item.kind != "experience":
                continue
            for path in sorted(item.directory.glob("results_*.json")):
                try:
                    data = json.loads(path.read_text())
                    corpus, partition = data["donnees"]["corpus"], data["donnees"]["partition"]
                except (OSError, ValueError, KeyError, TypeError):
                    continue
                self.runs[(item.id, corpus, partition)] = Run(
                    item, corpus, partition, data, read_per_file(item.directory, corpus, partition))
        self.constats = constats_file.read(root)
        self.leaderboard = self._read_leaderboard()

    def run(self, exp_id: str | None, corpus: str, partition: str = PARTITION) -> Run | None:
        return self.runs.get((exp_id, corpus, partition)) if exp_id else None

    def _read_leaderboard(self) -> list[dict[str, str]]:
        path = self.root / LEADERBOARD
        if not path.is_file():
            return []
        with path.open(newline="") as handle:
            return list(csv.DictReader(handle))

    def checks(self) -> list[str]:
        """Écarts entre le leaderboard et les results_*.json, dans les deux sens."""
        problems, seen = [], set()
        if not self.leaderboard:
            return [f"{LEADERBOARD.as_posix()} absent ou vide"]
        for row in self.leaderboard:
            key = (row.get("exp_id"), row.get("corpus"), row.get("partition"))
            seen.add(key)
            run = self.runs.get(key)
            if run is None:
                problems.append(f"{key[0]} {key[1]} {key[2]} : ligne du leaderboard sans results_*.json")
                continue
            for column, collar in (("der_c0", "collar_0"), ("der_c025", "collar_0_25")):
                try:
                    expected = float(row[column])
                except (KeyError, TypeError, ValueError):
                    problems.append(f"{key[0]} {key[1]} {key[2]} : {column} illisible dans le leaderboard")
                    continue
                if run.der(collar) is None or abs(run.der(collar) - expected) > TOLERANCE:
                    problems.append(f"{key[0]} {key[1]} {key[2]} : {column} {expected} au leaderboard, "
                                    f"{run.der(collar)} dans results")
        problems += [f"{e} {c} {p} : results_*.json absent du leaderboard"
                     for (e, c, p) in sorted(self.runs) if (e, c, p) not in seen]
        return problems


# --- Comparaisons appariées ----------------------------------------------------------


@dataclass
class Gap:
    """Écart de DER (a − b, en points) sur les fichiers communs, dans une condition de collar."""
    estimate: float
    low: float | None
    high: float | None
    better: int
    worse: int
    n: int

    def text(self) -> str:
        ci = f" [{num(self.low, sign=True)} ; {num(self.high, sign=True)}]" if self.low is not None else ""
        return num(self.estimate, sign=True) + ci


def _durations(rows: dict[str, dict[str, float]], uris: list[str], key: str) -> tuple[list[float], list[float]]:
    errors = [sum(rows[u][f"{kind}_{key}_s"] for kind in ("manquee", "fausse_alarme", "confusion")) for u in uris]
    totals = [rows[u][f"duree_reference_{key}_s"] for u in uris]
    return errors, totals


def compare(a: dict | None, b: dict | None, subset: set[str] | None = None) -> tuple[dict[str, Gap] | None, str]:
    """Écart apparié a − b par condition de collar ; (None, raison) s'il n'est pas calculable."""
    if a is None or b is None:
        return None, "per_file absent"
    if set(a) != set(b):
        return None, f"fichiers différents ({len(a)} et {len(b)})"
    uris = sorted(u for u in a if subset is None or u in subset)
    if not uris:
        return None, "aucun fichier"
    gaps = {}
    try:
        for key, _, _ in COLLARS:
            errors_a, totals_a = _durations(a, uris, key)
            errors_b, totals_b = _durations(b, uris, key)
            pooled = (100.0 * sum(errors_a) / sum(totals_a)) - (100.0 * sum(errors_b) / sum(totals_b))
            low = high = None
            if len(uris) >= MIN_BOOTSTRAP_FILES:
                ci = bootstrap_der_ci(errors_a, totals_a, errors_b, totals_b, n_resamples=N_RESAMPLES, seed=SEED)
                pooled, low, high = ci["estimation"], ci["borne_inf"], ci["borne_sup"]
            wins = count_wins([a[u][f"der_{key}"] for u in uris], [b[u][f"der_{key}"] for u in uris])
            gaps[key] = Gap(pooled, low, high, wins["a_meilleur"], wins["b_meilleur"], len(uris))
    except (KeyError, ZeroDivisionError) as error:
        return None, f"per_file incomplet ({error})"
    return gaps, ""


# --- Sources et constats -------------------------------------------------------------


def sources_lines(runs: list[Run], extra: list[str] | None = None) -> list[str]:
    """Expériences du tableau, avec le commit de leur exécution et celui de leur évaluation."""
    by_exp: dict[str, set[str]] = {}
    evaluated: dict[str, set[str]] = {}
    for run in runs:
        by_exp.setdefault(run.item.id, set()).add(run.commit)
        evaluation = str((run.data.get("evaluation") or {}).get("git_commit") or "")[:7]
        if evaluation:
            evaluated.setdefault(run.item.id, set()).add(evaluation)
    parts = []
    for exp_id in sorted(by_exp):
        text = f"{exp_id} (`{'`, `'.join(sorted(by_exp[exp_id]))}`"
        if evaluated.get(exp_id) and evaluated[exp_id] != by_exp[exp_id]:
            text += f", évaluée à `{'`, `'.join(sorted(evaluated[exp_id]))}`"
        parts.append(text + ")")
    lines = ["**Sources.** " + ("Expériences (commit d'exécution) : " + ", ".join(parts) + "."
                                if parts else "Aucune expérience.")]
    lines.append(f"Fichiers : `{LEADERBOARD.as_posix()}` (contrôle), `results_<corpus>_<partition>.json` et "
                 "`per_file_<corpus>_<partition>.csv` de chaque expérience.")
    lines += extra or []
    return lines


def constats_lines(repo: Repository, exp_ids: set[str]) -> list[str]:
    related = [c for c in repo.constats.items if exp_ids & set(c.sources)]
    if not related:
        return []
    lines = ["", f"**Constats liés** (`docs/constats.yaml`, version {repo.constats.version} du "
                 f"{repo.constats.date}) :", ""]
    lines += [f"- {c.id} ({c.confiance}) : {c.texte} Sources : {', '.join(c.sources)}." for c in related]
    return lines


# --- Tableau des systèmes -------------------------------------------------------------


def system_label(item: av.Item) -> str:
    return av.REFERENCE_SYSTEMS.get(av._system(item), item.pipeline or item.slug)


def verdict(item: av.Item) -> str:
    if item.header.status != "ok":
        return av.MISSING_HEADER
    return av.VERDICTS.get(item.header.verdict, item.header.verdict or "—")


def corpus_order(corpora) -> list[str]:
    order = av.CORPUS_ORDER
    return sorted(corpora, key=lambda c: (order.index(c) if c in order else len(order), c))


def realistic(item: av.Item) -> bool:
    """Condition réaliste : nombre de locuteurs non donné, détection non oracle."""
    return item.mode != "oracle" and item.vad != "oracle"


def speakers_exact(run: Run) -> str:
    if run.per_file:
        exact = sum(1 for row in run.per_file.values() if row.get("erreur_n_locuteurs") == 0)
        return f"{exact}/{len(run.per_file)} ({num(100.0 * exact / len(run.per_file), 1)} %)"
    rate = (run.metrics.get("n_locuteurs") or {}).get("taux_exact")
    return "—" if rate is None else f"{num(rate, 1)} %"


def flagged(run: Run, text: str) -> str:
    return f"{text} (invalidée)" if run.invalidated else text


def gap_cells(repo: Repository, run: Run) -> list[str]:
    """Référence déclarée, écarts dans les deux conditions de collar, fichiers meilleurs et moins bons."""
    reference = repo.run(run.item.reference, run.corpus, run.partition)
    if not run.item.reference:
        return ["—", "—", "—", "—"]
    label = f"{run.item.reference} ({run.item.variable or '?'})"
    if reference is None:
        return [label, "référence absente", "—", "—"]
    gaps, reason = compare(run.per_file, reference.per_file)
    if gaps is None:
        return [label, reason, "—", "—"]
    c0 = gaps["c0"]
    return [label, gaps["c0"].text(), gaps["c025"].text(), f"{c0.better} / {c0.worse} sur {c0.n}"]


def systems_page(repo: Repository) -> str:
    lines = ["# Systèmes par corpus", "",
             "Partition test, condition réaliste (nombre de locuteurs non donné, détection non oracle). "
             "DER en %, chevauchements comptés ; composantes sans collar. Nombre de locuteurs exact : réunions "
             "où le nombre estimé égale celui de la référence.", ""]
    corpora = corpus_order({r.corpus for r in repo.runs.values()
                            if r.partition == PARTITION and not ROBUSTNESS_CORPUS.match(r.corpus)})
    used: list[Run] = []
    for corpus in corpora:
        runs = sorted((r for r in repo.runs.values() if r.corpus == corpus and r.partition == PARTITION
                       and realistic(r.item)), key=lambda r: r.item.id)
        if not runs:
            continue
        used += runs
        title = av.CORPUS_LABELS.get(corpus, corpus)
        labels = [system_label(r.item) for r in runs]
        # Un même système décliné (sortie, bornes…) : la variable modifiée distingue les lignes.
        labels = [f"{label} ({r.item.variable})" if labels.index(label) != index and r.item.variable else label
                  for index, (label, r) in enumerate(zip(labels, runs))]
        metrics = [[label, f"{r.item.id} ({r.item.slug})", verdict(r.item),
                    flagged(r, pct(r.der("collar_0"))), pct(r.der("collar_0_25")),
                    num((r.metrics.get("collar_0") or {}).get("manquee")),
                    num((r.metrics.get("collar_0") or {}).get("fausse_alarme")),
                    num((r.metrics.get("collar_0") or {}).get("confusion")), speakers_exact(r)]
                   for label, r in zip(labels, runs)]
        gaps = [[r.item.id, *gap_cells(repo, r)] for r in runs if r.item.reference]
        lines += [f"## {title}", ""]
        lines += md_table(["Système", "Expérience", "Verdict", "DER sans collar", "DER collar 0,25 s",
                           "Parole manquée", "Fausse alarme", "Confusion", "Nombre de locuteurs exact"], metrics)
        if gaps:
            lines += ["", f"Écart à la référence déclarée ({title}, test) : DER de l'expérience moins DER de sa "
                          "référence, en points, intervalle de confiance à 95 % par bootstrap apparié sur les "
                          f"fichiers ({RESAMPLES_TEXT} tirages, graine {SEED}). Un écart négatif est une amélioration.",
                      ""]
            lines += md_table(["Expérience", "Référence (variable modifiée)", "Écart sans collar [IC 95 %]",
                               "Écart collar 0,25 s [IC 95 %]", "Fichiers où l'expérience fait mieux / moins bien (sans collar)"],
                              gaps)
        lines.append("")
    if not used:
        lines += ["Aucun résultat de test.", ""]
    references = [repo.run(r.item.reference, r.corpus) for r in used]
    lines += sources_lines(used + [r for r in references if r and r not in used])
    lines += constats_lines(repo, {r.item.id for r in used})
    lines += ["", "Graphique : `figures/systemes_reference.svg` (systèmes de référence, comme l'onglet Avancement).", ""]
    return "\n".join(lines)


# --- Décomposition par les oracles --------------------------------------------------


def oracles_page(repo: Repository) -> str:
    lines = ["# Décomposition de l'erreur par les oracles", "",
             "Partition test, DER en %, chevauchements comptés ; composantes sans collar. Chaque expérience "
             "change une seule variable par rapport à sa référence (D9) : détection de parole oracle "
             "(`detection_oracle`), nombre de locuteurs oracle (`mode_n_locuteurs`) ou représentation. Écart : "
             "DER de l'expérience moins DER de sa référence, intervalle de confiance à 95 % par bootstrap "
             f"apparié sur les fichiers ({RESAMPLES_TEXT} tirages, graine {SEED}).", ""]
    rows, used = [], []
    for exp_id in av.ORACLE_SERIES:
        item = repo.by_id.get(exp_id)
        if item is None:
            rows.append([exp_id, "absente de ce dépôt", *["—"] * 9])
            continue
        for corpus in corpus_order(item.corpora):
            run = repo.run(exp_id, corpus)
            if run is None:
                continue
            used.append(run)
            reference = repo.run(item.reference, corpus)
            if reference is not None:
                used.append(reference)
            gaps, reason = compare(run.per_file, reference.per_file) if reference else (None, "—")
            c0 = run.metrics.get("collar_0") or {}
            engine = f"{item.pipeline or '—'} ; locuteurs : {item.mode or '—'} ; détection : {item.vad or '—'}"
            rows.append([f"{exp_id} ({item.slug})", engine, item.variable or "— (référence)",
                         flagged(run, pct(run.der("collar_0"))), pct(run.der("collar_0_25")),
                         num(c0.get("manquee")), num(c0.get("fausse_alarme")), num(c0.get("confusion")),
                         item.reference or "—",
                         gaps["c0"].text() if gaps else (reason if item.reference else "—"),
                         gaps["c025"].text() if gaps else "—"])
    lines += md_table(["Expérience", "Moteur", "Variable modifiée", "DER sans collar", "DER collar 0,25 s",
                       "Parole manquée", "Fausse alarme", "Confusion", "Référence", "Écart sans collar [IC 95 %]",
                       "Écart collar 0,25 s [IC 95 %]"], rows)
    lines += ["", f"Série : `app.avancement.ORACLE_SERIES` ({', '.join(av.ORACLE_SERIES)}), celle de l'onglet "
                  "Avancement.", ""]
    lines += sources_lines(list(dict.fromkeys(used)))
    lines += constats_lines(repo, {r.item.id for r in used})
    return "\n".join(lines) + "\n"


# --- Robustesse (D24) ---------------------------------------------------------------


def degrade_config(root: Path) -> dict:
    try:
        return yaml.safe_load((root / DEGRADE_CONFIG).read_text()) or {}
    except (OSError, yaml.YAMLError):
        return {}


def condition_label(spec: dict | None) -> str:
    """Libellé d'une condition, depuis configs/summre_degrade.yaml."""
    if not spec:
        return "condition hors configuration"
    parts = []
    if "reverberation" in spec:
        parts.append(f"réverbération, RT60 visé {num(spec['reverberation'].get('rt60_s'), 1)} s")
    if "bruit" in spec:
        parts.append(f"bruit, RSB {spec['bruit'].get('rsb_db')} dB")
    if "codec" in spec:
        parts.append(f"codec Opus {spec['codec'].get('debit_kbps')} kbit/s")
    return " et ".join(parts) or "—"


def read_uris(path: Path) -> set[str] | None:
    try:
        return {line.strip() for line in path.read_text().splitlines() if line.strip()}
    except OSError:
        return None


def clean_run(repo: Repository, item: av.Item) -> Run | None:
    """`propre` d'une expérience d'A3 : son propre jeu propre, sinon le test de SUMM-RE de sa référence."""
    for corpus in (f"summre-{CLEAN}", "summre"):
        run = repo.run(item.id, corpus)
        if run is not None:
            return run
    return repo.run(item.reference, "summre")


def robustness_page(repo: Repository) -> str:
    config = degrade_config(repo.root)
    specs = config.get("conditions") or {}
    zoom_path = (config.get("ecoute") or {}).get("liste_zoom")
    zoom = read_uris(repo.root / zoom_path) if zoom_path else None
    lines = ["# Robustesse (D24)", "",
             "SUMM-RE test dégradé, références et UEM inchangés ; une expérience par moteur, un jeu évalué par "
             "condition (`results_summre-<condition>_test.json`). Écart au propre : DER dans la condition moins "
             "DER sur l'audio propre, sur les mêmes réunions, en points, intervalle de confiance à 95 % par "
             f"bootstrap apparié sur les fichiers ({RESAMPLES_TEXT} tirages, graine {SEED}). Propre : le jeu propre "
             "de l'expérience s'il existe, sinon le test de SUMM-RE de sa référence déclarée.", ""]
    by_item: dict[str, list[Run]] = {}
    for run in repo.runs.values():
        match = ROBUSTNESS_CORPUS.match(run.corpus)
        if run.partition == PARTITION and match and match["condition"] != CLEAN:
            by_item.setdefault(run.item.id, []).append(run)
    if not by_item:
        lines += ["Aucun résultat d'A3 pour l'instant : ce tableau se remplit dès qu'une expérience contient des "
                  "`results_summre-<condition>_test.json`.", "",
                  "Conditions prévues (`configs/summre_degrade.yaml`) : "
                  + " ; ".join(f"`{code}` ({condition_label(spec)})" for code, spec in specs.items()) + ".", ""]
        lines += sources_lines([])
        return "\n".join(lines) + "\n"

    order = list(specs)

    def condition_key(run: Run) -> tuple:
        code = ROBUSTNESS_CORPUS.match(run.corpus)["condition"]
        return (order.index(code) if code in order else len(order), code)

    main_rows, group_rows, used = [], [], []
    for exp_id in sorted(by_item):
        item = repo.by_id[exp_id]
        clean = clean_run(repo, item)
        engine = f"{system_label(item)} — {exp_id}"
        if clean is not None:
            used.append(clean)
            main_rows.append([engine, f"{CLEAN} ({clean.item.id})", flagged(clean, pct(clean.der("collar_0"))),
                              pct(clean.der("collar_0_25")), "—", "—", "—"])
        for run in sorted(by_item[exp_id], key=condition_key):
            used.append(run)
            code = ROBUSTNESS_CORPUS.match(run.corpus)["condition"]
            gaps, reason = compare(run.per_file, clean.per_file if clean else None)
            main_rows.append([engine, f"`{code}` ({condition_label(specs.get(code))})",
                              flagged(run, pct(run.der("collar_0"))), pct(run.der("collar_0_25")),
                              gaps["c0"].text() if gaps else (reason if clean else "propre introuvable"),
                              gaps["c025"].text() if gaps else "—",
                              f"{gaps['c0'].better} / {gaps['c0'].worse} sur {gaps['c0'].n}" if gaps else "—"])
            if zoom is None or clean is None or run.per_file is None:
                continue
            others = set(run.per_file) - zoom
            row = [engine, f"`{code}`"]
            for subset in (zoom & set(run.per_file), others):
                sub, sub_reason = compare(run.per_file, clean.per_file, subset)
                row += ([sub["c0"].text(), sub["c025"].text(), str(sub["c0"].n)] if sub else [sub_reason, "—", "0"])
            group_rows.append(row)
    lines += md_table(["Moteur", "Condition", "DER sans collar", "DER collar 0,25 s", "Écart au propre sans "
                       "collar [IC 95 %]", "Écart au propre collar 0,25 s [IC 95 %]",
                       "Réunions améliorées / dégradées (sans collar)"], main_rows)
    lines += ["", "## Sous-groupes : réunions Zoom et autres", ""]
    if group_rows:
        lines += [f"Réunions Zoom : liste `{zoom_path}` ; autres : le reste de SUMM-RE test. Une réunion Zoom "
                  "réverbérée dans une seule salle est moins plausible : les deux groupes sont donnés à part "
                  f"(décision du cockpit du 02/11). Pas d'intervalle sous {MIN_BOOTSTRAP_FILES} réunions.", ""]
        lines += md_table(["Moteur", "Condition", "Zoom : écart sans collar", "Zoom : écart collar 0,25 s",
                           "Zoom : réunions", "Autres : écart sans collar [IC 95 %]",
                           "Autres : écart collar 0,25 s [IC 95 %]", "Autres : réunions"], group_rows)
    else:
        lines.append("Non calculables : liste des réunions Zoom, propre ou per_file absents.")
    lines.append("")
    lines += sources_lines(list(dict.fromkeys(used)),
                           [f"Conditions : `{DEGRADE_CONFIG.as_posix()}`."])
    lines += constats_lines(repo, {r.item.id for r in used})
    return "\n".join(lines) + "\n"


# --- Temps (campagne du 12/11) ------------------------------------------------------


def read_campaigns(root: Path) -> list[tuple[Path, dict]]:
    found = []
    for path in sorted((root / CAMPAIGNS).glob("*/campagne.json")):
        try:
            found.append((path, json.loads(path.read_text())))
        except (OSError, ValueError):
            continue
    return found


def times_page(root: Path, chosen: Path | None = None) -> str:
    lines = ["# Temps de calcul", "",
             "Campagne de temps (D21, amendement du 01/11 ; `scripts/campagne_temps.py`) : chaque moteur traite le "
             "même sous-ensemble fixe de réunions (`data/splits/<corpus>/temps.txt`), machine au repos et sur "
             "secteur. Les temps des expériences, mesurés pendant le travail en parallèle, ne sont pas comparables "
             "et ne sont pas repris ici.", ""]
    campaigns = [(p, c) for p, c in read_campaigns(root) if chosen is None or p.resolve() == chosen.resolve()]
    if chosen is not None and not campaigns:
        raise SystemExit(f"Campagne illisible : {chosen}")
    usable = [(p, c) for p, c in campaigns if not c.get("factice") and (c.get("conditions_depart") or {}).get("reunies")]
    skipped = len(campaigns) - len(usable)
    if not usable:
        lines += ["Campagne du 12/11 pas encore faite : ce tableau se remplit à partir de "
                  f"`{CAMPAIGNS.as_posix()}/<date>_<heure>/campagne.json`."]
        if skipped:
            lines.append(f"{skipped} campagne(s) ignorée(s) : moteur factice ou conditions de départ non réunies.")
        return "\n".join(lines) + "\n"
    path, campaign = max(usable, key=lambda pc: (pc[1].get("date") or "", pc[0].as_posix()))
    rows = []
    for run in campaign.get("mesures") or []:
        s = run.get("synthese") or {}
        meetings = f"{s.get('n_reunions', 0)}" + (f" ({s['n_erreurs']} en erreur)" if s.get("n_erreurs") else "")
        if not s.get("conforme") or s.get("rtf") is None:
            rows.append([run.get("libelle") or run.get("moteur"), run.get("peripherique", "—"),
                         "non conforme, non reporté (D21)", "—", "—", "—", "—", meetings])
            continue
        rows.append([run.get("libelle") or run.get("moteur"), run.get("peripherique", "—"), num(s["rtf"], 4),
                     f"{num(s.get('rtf_min'), 4)} – {num(s.get('rtf_max'), 4)}", duration(s.get("temps_30min_s")),
                     f"{num(s.get('surcout_fixe_s'), 1)} s", f"{num(run.get('chargement_s'), 1)} s", meetings])
    subset = campaign.get("sous_ensemble") or {}
    uris = ", ".join(f.get("uri", "?") for f in subset.get("fichiers") or [])
    git = campaign.get("git") or {}
    lines += md_table(["Moteur", "Périphérique", "RTF", "RTF par réunion (min – max)", "Temps pour 30 min",
                       "Surcoût fixe", "Chargement des modèles", "Réunions"], rows)
    lines += ["", "RTF : Σ temps de calcul / Σ durée. Temps pour 30 min = RTF × 1 800 s, hors chargement des modèles "
                  "et surcoût du premier appel. Une ligne non conforme (batterie, charge concurrente ou erreur) "
                  "n'est jamais reportée (D21).", "",
              f"**Sources.** Campagne `{path.relative_to(root).as_posix()}` du {str(campaign.get('date', '?'))[:16]}, "
              f"commit `{str(git.get('commit', '?'))[:7]}`{'' if git.get('clean') else ' (arbre non propre)'} ; "
              f"sous-ensemble `{subset.get('source', '?')}` : {uris or '—'}."]
    if skipped:
        lines.append(f"{skipped} autre(s) campagne(s) ignorée(s) : moteur factice ou conditions de départ non réunies.")
    return "\n".join(lines) + "\n"


# --- Figures ----------------------------------------------------------------------------


def chart_style() -> str:
    """Règles `.av-chart` et teintes de interface.css (code de ce dépôt), pour un SVG lu hors de l'application."""
    css = (REPO_ROOT / CSS).read_text()

    def variables(selector: str) -> str:
        match = re.search(rf"^{re.escape(selector)}\s*\{{(.*?)^\}}", css, flags=re.S | re.M)
        block = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.S) if match else ""
        return " ".join(f"{name}:{value.strip()};"
                        for name, value in re.findall(r"(--(?:ws|av)-[\w-]+)\s*:\s*([^;]+);", block)
                        if "shadow" not in name and "ease" not in name)

    rules = " ".join(line.strip() for line in css.splitlines()
                     if line.startswith(".av-chart .") or line.startswith(".av-chart text"))
    return (f"svg.av-chart{{--font:{FONT};{variables(':root')} background:var(--ws-surface);}}"
            f"@media (prefers-color-scheme: dark){{svg.av-chart{{{variables('.dark')}}}}}{rules}")


def standalone_svg(svg: str, style: str) -> str:
    """SVG de `app.graphique.svg` rendu autonome : feuille de style intégrée, taille explicite."""
    match = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    width, height = match.group(1), match.group(2)
    svg = svg.replace('width="100%"', f'width="{width}" height="{height}"', 1)
    svg = re.sub(r"(</desc>)", rf"\1<style>{style}</style>"
                 rf'<rect width="{width}" height="{height}" style="fill:var(--ws-surface)"/>', svg, count=1)
    return svg + "\n"


def figures(repo: Repository) -> dict[str, str]:
    groups = av.reference_systems(repo.items)
    if not groups:
        return {}
    style = chart_style()
    return {"figures/systemes_reference.svg": standalone_svg(graphique.svg(groups, False, "avw"), style),
            "figures/systemes_reference_etroit.svg": standalone_svg(graphique.svg(groups, True, "avn"), style)}


# --- Index et écriture --------------------------------------------------------------


def index_page(repo: Repository, pages: dict[str, str], problems: list[str]) -> str:
    lines = ["# Rendu : tableaux et figures", "",
             "Fichiers générés par `scripts/rendu.py` : ne pas les modifier à la main. Pour les régénérer :", "",
             "```bash", "uv run python scripts/rendu.py", "```", "",
             "`--verifier` signale (code 1) un dossier qui n'est plus à jour.", "",
             "| Fichier | Contenu |", "|---|---|",
             "| [systemes.md](systemes.md) | Systèmes par corpus : DER dans les deux conditions de collar, "
             "composantes, nombre de locuteurs exact, écart à la référence avec IC du bootstrap |",
             "| [oracles.md](oracles.md) | Décomposition de l'erreur par les oracles |",
             "| [robustesse.md](robustesse.md) | Robustesse (D24) : moteur × condition, écart au propre, "
             "sous-groupes Zoom et autres |",
             "| [temps.md](temps.md) | Temps de calcul de la campagne du 12/11 (D21) |"]
    if any(name.startswith("figures/") for name in pages):
        lines += ["| [figures/](figures/) | Graphique des systèmes de référence de l'onglet Avancement, en "
                  "mise en page large et étroite |", "", "![DER test sans collar des systèmes de référence]"
                  "(figures/systemes_reference.svg)", ""]
        bars = {bar.exp_id for _, group in av.reference_systems(repo.items) for bar in group}
        lines += sources_lines([run for (exp_id, _, partition), run in sorted(repo.runs.items(), key=lambda kv: kv[0])
                                if exp_id in bars and partition == PARTITION],
                               ["Barres : `app.avancement.reference_systems`, comme l'onglet Avancement."])
    lines += ["", "## Contrôles", ""]
    if problems:
        lines += [f"- {p}" for p in problems]
    else:
        lines.append(f"- `{LEADERBOARD.as_posix()}` et les results_*.json concordent "
                     f"({len(repo.leaderboard)} lignes, à {num(TOLERANCE, 3)} point près).")
    lines += [f"- `docs/constats.yaml` : {p}" for p in repo.constats.problems]
    missing = [i.id for i in repo.items if i.kind == "experience" and i.header.status != "ok"]
    if missing:
        lines.append(f"- En-têtes de notes.md manquants ou illisibles (verdict non affiché) : {', '.join(missing)}.")
    return "\n".join(lines) + "\n"


def build(root: Path, campaign: Path | None = None) -> dict[str, str]:
    """Contenu de chaque fichier de docs/rendu/, par chemin relatif."""
    repo = Repository(root)
    pages = {"systemes.md": systems_page(repo), "oracles.md": oracles_page(repo),
             "robustesse.md": robustness_page(repo), "temps.md": times_page(root, campaign)}
    pages |= figures(repo)
    pages["README.md"] = index_page(repo, pages, repo.checks())
    return pages


def stale(pages: dict[str, str], output: Path) -> list[str]:
    """Fichiers à créer, à mettre à jour ou à retirer pour que `output` corresponde à `pages`."""
    present = {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()} if output.is_dir() else set()
    changed = [name for name, text in pages.items()
               if name not in present or (output / name).read_text(encoding="utf-8") != text]
    return sorted(changed + [name for name in present - set(pages)])


def write(pages: dict[str, str], output: Path) -> list[str]:
    changes = stale(pages, output)
    for name in changes:
        path = output / name
        if name in pages:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(pages[name], encoding="utf-8")
        else:
            path.unlink()
    return changes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tableaux et figures du rendu dans docs/rendu/ (chantier E7).")
    parser.add_argument("--racine", type=Path, default=REPO_ROOT, help="racine du dépôt lu (défaut : ce dépôt)")
    parser.add_argument("--sortie", type=Path, help="dossier de sortie (défaut : <racine>/docs/rendu)")
    parser.add_argument("--campagne", type=Path, help="campagne.json à utiliser (défaut : la plus récente utilisable)")
    parser.add_argument("--verifier", action="store_true", help="n'écrit rien ; code 1 si la sortie n'est pas à jour")
    args = parser.parse_args(argv)
    root = args.racine.resolve()
    output = args.sortie or root / OUTPUT
    pages = build(root, args.campagne)
    if args.verifier:
        changes = stale(pages, output)
        for name in changes:
            print(f"pas à jour : {name}")
        print("docs/rendu à jour" if not changes else f"{len(changes)} fichier(s) à régénérer")
        return 1 if changes else 0
    changes = write(pages, output)
    print(f"{len(changes)} fichier(s) écrit(s) ou retiré(s) dans {output}" if changes else "Rien à changer")
    return 0


if __name__ == "__main__":
    sys.exit(main())
