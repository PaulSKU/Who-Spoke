"""Onglet « Avancement » : récapitulatif généré de la conduite du projet (D26, chantier I2).

Tout est lu sous une racine de dépôt configurable (`--depot` de app/app.py), en lecture
seule, sans rien exécuter :

- frise des expériences (`experiments/EXP-…`) et des analyses (`analyses/A-…`) : en-tête
  YAML de `notes.md` (D26 §2 : id, question, verdict, décisions), DER des
  `results_<corpus>_<partition>.json` dans les deux conditions de collar, partition test
  en premier ; un `notes.md` sans en-tête s'affiche « en-tête manquant » ;
- décomposition de l'erreur par les oracles : expériences de `ORACLE_SERIES`, comparées
  à leur expérience de référence (`reference` et `variable_modifiee` de results.json) ;
- décisions : D1 à D15 depuis le tableau de `docs/cadrage.md` et sa phrase « Statut »,
  D16 et suivantes depuis la ligne « Statut : » de chaque fiche et de ses amendements ;
- « Ce que nous avons appris » (audit R-U7) : constats `cle: true` de `docs/constats.yaml`,
  avec leur confiance et un lien vers chaque expérience ou analyse source ; bouton qui
  affiche `docs/synthese.md` dans la page ;
- graphique des systèmes de référence (`reference_systems`, `app/graphique.py`) ;
- file d'attente de la piste A (D23, amendement du 01/11) : tableau « File d'attente » de
  `docs/planning.md` (Rang, Contenu, Calcul estimé, Prérequis), complété d'un état calculé
  (fiches de décision citées présentes ou non).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

import yaml

from app import formatage
from app import constats as constats_file
from app import graphique

VERDICTS = {
    "reference": "référence",
    "retenu": "retenu",
    "ecarte": "écarté",
    "informatif": "informatif",
    "en_cours": "en cours",
}
MISSING_HEADER = "en-tête manquant"
# Nombre de locuteurs dans results.json (mode_n_locuteurs) : libellés affichés.
MODE_LABELS = {"estime": "estimé", "oracle": "oracle", "impose": "imposé", "fourchette": "fourchette"}
# Décomposition de l'erreur par les oracles (D9, D19 §4, D22).
ORACLE_SERIES = ("EXP-0002", "EXP-0003", "EXP-0004", "EXP-0005", "EXP-0006", "EXP-0010", "EXP-0011")
PARTITION_ORDER = {"test": 0, "dev": 1}
_ID = re.compile(r"^(EXP|A)-(\d{4})")
_DECISION = re.compile(r"\bD(\d+)\b")


# --- Lecture ------------------------------------------------------------------------


@dataclass
class Header:
    status: str                     # "ok", "manquant", "illisible"
    question: str | None = None
    verdict: str | None = None
    decisions: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def read_header(path: Path, expected_id: str) -> Header:
    """En-tête YAML d'un notes.md (D26 §2), sans jamais lever d'exception."""
    if not path.is_file():
        return Header("manquant", problems=["notes.md absent"])
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return Header("manquant")
    match = re.match(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(\r?\n|$)", text, flags=re.S)
    if not match:
        return Header("illisible", problems=["en-tête non fermé"])
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as error:
        return Header("illisible", problems=[f"YAML invalide ({type(error).__name__})"])
    if not isinstance(data, dict):
        return Header("illisible", problems=["l'en-tête n'est pas un dictionnaire"])
    header = Header("ok", question=data.get("question"), verdict=data.get("verdict"))
    decisions = data.get("decisions") or []
    header.decisions = [str(d) for d in (decisions if isinstance(decisions, list) else [decisions])]
    if data.get("id") != expected_id:
        header.problems.append(f"id {data.get('id')!r} au lieu de {expected_id}")
    if header.verdict is not None and header.verdict not in VERDICTS:
        header.problems.append(f"verdict inconnu : {header.verdict!r}")
    if not header.question:
        header.problems.append("question absente")
    return header


@dataclass
class Result:
    corpus: str
    partition: str
    der_c0: float | None
    der_c025: float | None
    components: dict          # manquee, fausse_alarme, confusion (collar 0)
    invalidated: bool = False


@dataclass
class Item:
    id: str
    kind: str                 # "experience" ou "analyse"
    slug: str
    directory: Path
    header: Header
    date: str = ""
    results: list[Result] = field(default_factory=list)
    reference: str | None = None
    variable: str | None = None
    pipeline: str | None = None
    mode: str | None = None
    vad: str | None = None
    representation: str | None = None

    @property
    def notes(self) -> Path:
        return self.directory / "notes.md"

    @property
    def corpora(self) -> list[str]:
        return sorted({r.corpus for r in self.results})

    def result(self, partition: str, corpus: str | None = None) -> Result | None:
        for r in self.results:
            if r.partition == partition and (corpus is None or r.corpus == corpus):
                return r
        return None


def _read_results(directory: Path) -> list[Result]:
    results = []
    for path in sorted(directory.glob("results_*.json")):
        try:
            data = json.loads(path.read_text())
            metrics = data["metriques"]
            c0, c025 = metrics.get("collar_0") or {}, metrics.get("collar_0_25") or {}
            results.append(Result(
                corpus=data["donnees"]["corpus"], partition=data["donnees"]["partition"],
                der_c0=c0.get("der"), der_c025=c025.get("der"),
                components={k: c0.get(k) for k in ("manquee", "fausse_alarme", "confusion")},
                invalidated=bool(data.get("invalidee")),
            ))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return sorted(results, key=lambda r: (r.corpus, PARTITION_ORDER.get(r.partition, 9), r.partition))


def _first_result_json(directory: Path) -> dict:
    for path in sorted(directory.glob("results_*.json")):
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            continue
    return {}


def read_items(root: Path) -> list[Item]:
    """Expériences et analyses, dans l'ordre chronologique (date de résultat ou d'exécution)."""
    items = []
    for kind, folder in (("experience", "experiments"), ("analyse", "analyses")):
        base = root / folder
        if not base.is_dir():
            continue
        for directory in sorted(p for p in base.iterdir() if p.is_dir()):
            match = _ID.match(directory.name)
            if not match:
                continue
            item_id = f"{match.group(1)}-{match.group(2)}"
            item = Item(item_id, kind, directory.name[len(item_id) + 1:], directory,
                        read_header(directory / "notes.md", item_id))
            first = _first_result_json(directory)
            item.results = _read_results(directory)
            item.reference = first.get("reference")
            item.variable = first.get("variable_modifiee")
            item.pipeline = (first.get("systeme") or {}).get("pipeline")
            item.mode = (first.get("systeme") or {}).get("mode_n_locuteurs")
            item.vad = (first.get("systeme") or {}).get("vad")
            item.representation = _representation(directory)
            item.date = first.get("date") or _execution_date(directory)
            items.append(item)
    return sorted(items, key=lambda i: (i.date or "9999", i.id))


def _representation(directory: Path) -> str | None:
    """Représentation de la baseline (`pipeline.parametres.representation` de config.yaml)."""
    try:
        config = yaml.safe_load((directory / "config.yaml").read_text()) or {}
    except (OSError, yaml.YAMLError):
        return None
    return ((config.get("pipeline") or {}).get("parametres") or {}).get("representation")


# Systèmes de référence du graphique (R-U7), dans l'ordre d'affichage : (pipeline,
# représentation) -> libellé. La baseline sans représentation déclarée est celle des MFCC.
REFERENCE_SYSTEMS = {
    ("baseline", "mfcc"): "Baseline MFCC",
    ("baseline", "ecapa"): "Baseline ECAPA",
    ("baseline", "wespeaker"): "Baseline WeSpeaker",
    ("pyannote-community-1", None): "pyannote community-1",
}
CORPUS_LABELS = {"summre": "SUMM-RE", "ami": "AMI (SDM)"}
CORPUS_ORDER = ("summre", "ami")       # SUMM-RE, jeu prioritaire (D3), en premier
CHART_VERDICTS = ("retenu", "reference")


def _system(item: Item) -> tuple[str | None, str | None]:
    if item.pipeline == "baseline":
        return "baseline", item.representation or "mfcc"
    return item.pipeline, item.representation


def reference_systems(items: list[Item]) -> list[tuple[str, list[graphique.Bar]]]:
    """Barres du graphique, par corpus : pour chaque système de `REFERENCE_SYSTEMS`, sa
    première expérience en condition réaliste (nombre de locuteurs estimé, détection non
    oracle) ayant un résultat de test non invalidé sur le corpus ; puis, automatiquement,
    toute autre expérience dont le verdict est « retenu » ou « référence »."""
    experiments = sorted((i for i in items if i.kind == "experience"), key=lambda i: i.id)

    def usable(item: Item, corpus: str):
        result = item.result("test", corpus)
        ok = (result is not None and not result.invalidated and result.der_c0 is not None
              and all(v is not None for v in result.components.values()))
        return result if ok else None

    corpora = sorted({r.corpus for i in experiments for r in i.results if r.partition == "test"},
                     key=lambda c: (CORPUS_ORDER.index(c) if c in CORPUS_ORDER else len(CORPUS_ORDER), c))
    groups = []
    for corpus in corpora:
        bars, chosen = [], set()
        for system, label in REFERENCE_SYSTEMS.items():
            item = next((i for i in experiments if _system(i) == system and i.mode == "estime"
                         and i.vad != "oracle" and usable(i, corpus)), None)
            if item is None:
                continue
            result = usable(item, corpus)
            chosen.add(item.id)
            bars.append(graphique.Bar(label, item.id, item.id, dict(result.components), result.der_c0))
        for item in experiments:
            result = usable(item, corpus)
            if item.id in chosen or result is None or item.header.verdict not in CHART_VERDICTS:
                continue
            label = REFERENCE_SYSTEMS.get(_system(item), item.pipeline or item.slug)
            bars.append(graphique.Bar(label, f"{item.id}, {VERDICTS[item.header.verdict]}", item.id,
                                      dict(result.components), result.der_c0))
        if bars:
            groups.append((CORPUS_LABELS.get(corpus, corpus), bars))
    return groups


def _execution_date(directory: Path) -> str:
    for path in sorted(directory.glob("execution*.json")):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if data.get("date") or data.get("date_fin"):
            return data.get("date") or data.get("date_fin")
    return ""


@dataclass
class Decision:
    number: int
    title: str
    status: str
    source: str
    amendments: list[tuple[str, str]] = field(default_factory=list)   # (titre, statut)


def _cadrage_decisions(path: Path) -> list[Decision]:
    """D1 à D15 : tableau du §0 et phrase « Statut » de docs/cadrage.md."""
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    status_line = next((line for line in text.splitlines() if line.startswith("**Statut.**")), "")
    acted = re.search(r"D(\d+) à D(\d+) actées le ([0-9/]+)", status_line)
    open_points: dict[int, list[str]] = {}
    if "Restent ouverts" in status_line:
        clause = status_line.split("Restent ouverts", 1)[1].lstrip(" :").rstrip(". ")
        for part in re.split(r",\s*|\s+et\s+", clause):
            part = re.sub(r"^et\s+", "", part.strip())
            for number in _DECISION.findall(part):
                open_points.setdefault(int(number), []).append(part)
    decisions = []
    for row in markdown_table(text, after="## 0."):
        match = re.fullmatch(r"D(\d+)", row.get("ID", "").strip())
        if not match:
            continue
        number = int(match.group(1))
        status = "actée" if acted and int(acted.group(1)) <= number <= int(acted.group(2)) else "—"
        if acted and status == "actée":
            status += f" le {acted.group(3)}"
        if number in open_points:
            status += " ; ouvert : " + " ; ".join(open_points[number])
        title = re.sub(r"\*\*(.+?)\*\*", r"\1", row.get("Décision", ""))
        decisions.append(Decision(number, title, status, "docs/cadrage.md"))
    return decisions


def _fiche_decision(path: Path) -> Decision | None:
    lines = path.read_text(encoding="utf-8").splitlines()
    match = re.match(r"#\s*D(\d+)\s*[—-]\s*(.+)", lines[0]) if lines else None
    if not match:
        return None
    statuses = [(i, line.split(":", 1)[1].strip()) for i, line in enumerate(lines) if line.startswith("Statut :")]
    status = statuses[0][1] if statuses else "statut non indiqué"
    decision = Decision(int(match.group(1)), match.group(2).strip(), status, f"docs/decisions/{path.name}")
    for index, line in enumerate(lines):
        if line.startswith("## Amendement"):
            following = next((s for i, s in statuses if i > index and i < index + 6), "statut non indiqué")
            decision.amendments.append((line.lstrip("# ").strip(), following))
    return decision


def read_decisions(root: Path) -> list[Decision]:
    decisions = _cadrage_decisions(root / "docs" / "cadrage.md")
    folder = root / "docs" / "decisions"
    if folder.is_dir():
        for path in sorted(folder.glob("D*.md")):
            decision = _fiche_decision(path)
            if decision is not None:
                decisions.append(decision)
    return sorted(decisions, key=lambda d: d.number)


def markdown_table(text: str, after: str) -> list[dict[str, str]]:
    """Premier tableau Markdown qui suit la ligne commençant par `after`."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(after)), None)
    if start is None:
        return []
    rows: list[list[str]] = []
    for line in lines[start + 1:]:
        if line.startswith("|"):
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
        elif rows:
            break
        elif line.startswith("#"):
            return []
    if len(rows) < 2:
        return []
    header = rows[0]
    return [dict(zip(header, row)) for row in rows[2:]]


@dataclass
class QueueRow:
    rank: str
    content: str
    estimate: str
    prerequisites: str
    state: str


QUEUE_COLUMNS = ("Rang", "Contenu", "Calcul estimé", "Prérequis")


def read_queue(root: Path) -> list[QueueRow]:
    """Tableau « File d'attente » de docs/planning.md (colonnes de `QUEUE_COLUMNS`).

    L'état constaté ne retient que les fiches de décision citées (D16 et suivantes),
    présentes ou absentes : les expériences de la file n'ont pas encore de numéro, et
    celles qui sont citées le sont comme référence (EXP-0007 à reproduire en A1), pas
    comme travail fait.
    """
    path = root / "docs" / "planning.md"
    if not path.is_file():
        return []
    fiches = {d.number for d in read_decisions(root) if d.source.startswith("docs/decisions/")}
    rows = []
    for row in markdown_table(path.read_text(encoding="utf-8"), after="## File d'attente"):
        rank, content, estimate, prerequisites = (row.get(column, "") for column in QUEUE_COLUMNS)
        cited = dict.fromkeys(int(n) for n in _DECISION.findall(f"{content} {prerequisites}") if int(n) > 15)
        states = [f"fiche D{n} " + ("présente" if n in fiches else "absente") for n in cited]
        rows.append(QueueRow(rank, content, estimate, prerequisites, " ; ".join(states) or "—"))
    return rows


# --- Rendu -------------------------------------------------------------------------


def _inline(text: str) -> str:
    """Texte échappé, avec le code Markdown en ligne (`…`) rendu en <code>."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", escape(text))


def _pct(value: float | None) -> str:
    return formatage.pourcentage(value, 2)


def _row(cells: list[tuple[str, str, str]], row_class: str = "") -> str:
    """Ligne de tableau ; chaque cellule porte son en-tête (`data-label`), affiché devant la
    valeur quand le tableau s'empile en fiches sur petit écran (B13)."""
    opening = f'<tr class="{row_class}">' if row_class else "<tr>"
    return opening + "".join(f'<td data-label="{escape(label, quote=True)}"{f" class={chr(34)}{cls}{chr(34)}" if cls else ""}>'
                            f"{html}</td>" for label, html, cls in cells) + "</tr>"


def _corpus(corpus: str) -> str:
    return escape(CORPUS_LABELS.get(corpus, corpus))


def _der_cell(result: Result | None) -> str:
    if result is None:
        return "—"
    flag = ' <span class="av-flag">invalidée</span>' if result.invalidated else ""
    return (f'<span class="strong">{_pct(result.der_c0)}</span>'
            f'<span class="sub">collar 0,25\u202fs : {_pct(result.der_c025)}</span>{flag}')


def _header_cells(item: Item) -> tuple[str, str, str]:
    header = item.header
    if header.status != "ok":
        label = MISSING_HEADER if header.status == "manquant" else "en-tête illisible"
        detail = f'<span class="sub">{escape("; ".join(header.problems))}</span>' if header.problems else ""
        missing = f'<span class="av-missing">{label}</span>{detail}'
        return missing, missing, "—"
    problems = (f'<span class="av-flag">{escape("; ".join(header.problems))}</span>' if header.problems else "")
    question = escape(header.question or "—") + problems
    verdict = VERDICTS.get(header.verdict, header.verdict or "—")
    verdict_html = f'<span class="av-verdict av-{escape(str(header.verdict))}">{escape(verdict)}</span>'
    return question, verdict_html, escape(", ".join(header.decisions) or "—")


# Frise sous 840 px : les dernières seulement, les autres derrière un bouton (retour du
# cockpit sur B13) ; au-delà, tout est affiché.
TIMELINE_RECENT = 5


def _timeline_html(items: list[Item], root: Path) -> str:
    rows = []
    older = max(0, len(items) - TIMELINE_RECENT)
    for index, item in enumerate(items):
        question, verdict, decisions = _header_cells(item)
        if item.kind == "analyse":
            der_test = der_dev = '<span class="sub">analyse a posteriori</span>'
            corpus = "—"
        else:
            corpus = ", ".join(_corpus(c) for c in item.corpora) or "—"
            # Une ligne par corpus quand une expérience en compte plusieurs.
            der_test = "<br>".join(_der_cell(item.result("test", c)) for c in item.corpora) or "—"
            der_dev = "<br>".join(_der_cell(item.result("dev", c)) for c in item.corpora) or "—"
        notes = (f'<button type="button" class="ws-btn ws-btn-sm av-notes" data-id="{item.id}">notes.md</button>'
                 if item.notes.is_file() else '<span class="sub">pas de notes</span>')
        rows.append(_row([
            ("Identifiant", f'<span class="strong">{item.id}</span><span class="sub">{escape(item.slug)}</span>'
                            f'<span class="sub">{escape(formatage.date(item.date))}</span>', ""),
            ("Question", question, ""), ("Corpus", corpus, ""), ("DER test", der_test, "num"),
            ("DER dev", der_dev, "num"), ("Verdict", verdict, ""), ("Décisions", decisions, ""), ("Notes", notes, ""),
        ], "av-older" if index < older else ""))
    return (
        '<div class="ws-table-wrap"><table class="ws-table av-table av-stack av-frise" id="av-frise"><thead><tr>'
        '<th scope="col">Identifiant</th><th scope="col">Question</th><th scope="col">Corpus</th>'
        '<th scope="col" class="num">DER test</th><th scope="col" class="num">DER dev</th>'
        '<th scope="col">Verdict</th><th scope="col">Décisions</th><th scope="col">Notes</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        + (f'<button type="button" class="ws-btn ws-btn-sm av-more" aria-expanded="false" aria-controls="av-frise" '
           f'data-more="Afficher les {older} autres" data-less="Masquer les {older} autres">'
           f'Afficher les {older} autres</button>' if older else "")
    )


def _oracles_html(items: list[Item]) -> str:
    by_id = {item.id: item for item in items}
    rows = []
    for exp_id in ORACLE_SERIES:
        item = by_id.get(exp_id)
        if item is None:
            rows.append(f'<tr><td data-label="Expérience">{exp_id}</td><td colspan="7" data-label="État">'
                        '<span class="sub">absente de ce dépôt</span></td></tr>')
            continue
        for corpus in item.corpora or ["—"]:
            result = item.result("test", corpus)
            reference = by_id.get(item.reference) if item.reference else None
            ref_result = reference.result("test", corpus) if reference else None
            delta = "—"
            if result and ref_result and result.der_c0 is not None and ref_result.der_c0 is not None:
                diff = result.der_c0 - ref_result.der_c0
                delta = (formatage.unite(diff, "pt", 2, sign=True)
                         + f' <span class="sub">face à {escape(item.reference)}</span>')
            c = result.components if result else {}
            variable = f"<code>{escape(item.variable)}</code>" if item.variable else "— (référence)"
            mode = MODE_LABELS.get(item.mode or "", item.mode or "—")
            rows.append(_row([
                ("Expérience", f'<span class="strong">{exp_id}</span><span class="sub">{escape(item.slug)}</span>', ""),
                ("Moteur", f'{escape(item.pipeline or "—")}<span class="sub">locuteurs : {escape(mode)}</span>', ""),
                ("Variable modifiée", variable, ""), ("DER", _pct(result.der_c0 if result else None), "num strong"),
                ("Parole manquée", _pct(c.get("manquee")), "num"), ("Fausse alarme", _pct(c.get("fausse_alarme")), "num"),
                ("Confusion", _pct(c.get("confusion")), "num"), ("Écart", delta, "num"),
            ]))
    return (
        '<div class="ws-table-wrap"><table class="ws-table av-table av-stack"><thead><tr>'
        '<th scope="col">Expérience</th><th scope="col">Moteur</th><th scope="col">Variable modifiée</th>'
        '<th scope="col" class="num">DER</th><th scope="col" class="num">Parole manquée</th>'
        '<th scope="col" class="num">Fausse alarme</th><th scope="col" class="num">Confusion</th>'
        f'<th scope="col" class="num">Écart</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        '<details class="ws-howto-read"><summary>Comment lire ce tableau</summary><p class="ws-caption">Partition '
        'test, sans collar, chevauchements comptés. Écart : différence de DER avec l\'expérience de référence, '
        'une seule variable modifiée (D9).</p></details>'
    )


def _decisions_table(decisions: list[Decision]) -> str:
    rows = []
    for d in decisions:
        amendments = "".join(f'<span class="sub">{_inline(t)} : {_inline(s)}</span>' for t, s in d.amendments)
        rows.append(_row([("Fiche", f"D{d.number}", "strong"),
                          ("Décision", f'{_inline(d.title)}<span class="sub av-path"><code>{escape(d.source)}</code></span>', ""),
                          ("Statut", f"{_inline(d.status)}{amendments}", "")]))
    return ('<div class="ws-table-wrap"><table class="ws-table av-table av-stack"><thead><tr><th scope="col">Fiche</th>'
            '<th scope="col">Décision</th><th scope="col">Statut</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def _decisions_html(decisions: list[Decision]) -> str:
    """D16 et suivantes visibles ; D1 à D15 (cadrage) repliées par défaut (R-U7)."""
    framing = [d for d in decisions if d.number <= 15]
    later = [d for d in decisions if d.number > 15]
    html = _decisions_table(later) if later else ""
    if framing:
        open_ones = sum(1 for d in framing if "ouvert" in d.status)
        summary = (f"Décisions de cadrage D1 à D15 ({len(framing)}, dont {open_ones} avec un point ouvert)"
                   if open_ones else f"Décisions de cadrage D1 à D15 ({len(framing)})")
        html += (f'<details class="av-framing ws-fold"><summary>{escape(summary)}</summary>'
                 f'{_decisions_table(framing)}</details>')
    return html


# --- « Ce que nous avons appris » et synthèse (R-U7) ----------------------------------

CONFIDENCE_LABELS = {"certain": "certain", "probable": "probable", "incertain": "incertain"}
SYNTHESIS = Path("docs") / "synthese.md"
SYNTHESIS_ID = "synthese"


def _source_html(source: str, items: dict[str, Item]) -> str:
    item = items.get(source)
    if item is not None and item.notes.is_file():
        return f'<button type="button" class="ws-btn ws-btn-sm av-notes av-source" data-id="{escape(source)}">{escape(source)}</button>'
    return f'<span class="av-source av-source-missing" title="Absente de ce dépôt">{escape(source)}</span>'


def _learned_html(root: Path, items: list[Item]) -> str:
    data = constats_file.read(root)
    by_id = {item.id: item for item in items}
    synthesis = ""
    if (root / SYNTHESIS).is_file():
        synthesis = (f'<button type="button" class="ws-btn ws-btn-sm av-notes av-synthesis" data-id="{SYNTHESIS_ID}">'
                     'Lire la synthèse (docs/synthese.md)</button>')
    if not data.present:
        return (f'<p class="ws-empty-note">docs/constats.yaml absent de ce dépôt.</p>{synthesis}')
    key = [c for c in data.items if c.cle]
    items_html = "".join(
        f'<li class="av-learned-item"><p>{escape(c.texte)}</p><p class="av-learned-meta">'
        f'<span class="ws-conf ws-conf-{escape(c.confiance)}">'
        f'{escape(CONFIDENCE_LABELS.get(c.confiance, c.confiance))}</span>'
        f'<span class="sub">{escape(c.id)} · sources :</span> '
        + " ".join(_source_html(s, by_id) for s in c.sources) + "</p></li>"
        for c in key)
    problems = "".join(f"<li>{escape(p)}</li>" for p in data.problems)
    return (
        '<div class="av-learned"><h3 class="av-learned-title">Ce que nous avons appris</h3>'
        + (f'<ul class="av-learned-list">{items_html}</ul>' if key else
           '<p class="ws-empty-note">Aucun constat clé pour l\'instant.</p>')
        + (f'<div class="pl-issues" role="note"><p class="strong">docs/constats.yaml : à corriger</p><ul>{problems}</ul></div>'
           if problems else "")
        + f'<p class="ws-caption">{len(key)} constats clés sur {len(data.items)}, tirés de docs/constats.yaml '
        f'(version {escape(data.version)} du {escape(formatage.date(data.date))}), tenu par le cockpit.</p>'
        '<details class="ws-howto-read"><summary>Comment lire ces constats</summary><p class="ws-caption">Confiance : '
        'certain, mesuré dans nos expériences ; probable, déduit de plusieurs mesures ; incertain, hypothèse non '
        f'testée. Un clic sur une source affiche ses notes.</p></details>{synthesis}</div>'
    )


def _queue_html(queue: list[QueueRow]) -> str:
    if not queue:
        return '<p class="ws-empty-note">Tableau « File d\'attente » introuvable dans docs/planning.md.</p>'
    rows = "".join(_row([("Rang", escape(q.rank), "strong"), ("Contenu", _inline(q.content), ""),
                         ("Calcul estimé", _inline(q.estimate), "av-estimate"),
                         ("Prérequis", _inline(q.prerequisites), ""), ("État constaté", escape(q.state), "")])
                   for q in queue)
    return ('<div class="ws-table-wrap"><table class="ws-table av-table av-queue av-stack"><thead><tr>'
            '<th scope="col">Rang</th><th scope="col">Contenu</th><th scope="col">Calcul estimé</th>'
            f'<th scope="col">Prérequis</th><th scope="col">État constaté</th></tr></thead><tbody>{rows}</tbody>'
            '</table></div><p class="ws-caption">Tableau de docs/planning.md, dans l\'ordre de la file ; '
            '« État constaté » est calculé depuis les fiches de décision présentes.</p>')


def _count(n: int, word: str) -> str:
    return f"{n} {word}{'s' if n > 1 else ''}"


def render(root: Path) -> dict[str, str]:
    """Sections HTML de l'onglet, chacune autonome."""
    items = read_items(root)
    decisions = read_decisions(root)
    queue = read_queue(root)
    experiments = [i for i in items if i.kind == "experience"]
    missing = [i.id for i in items if i.header.status != "ok"]
    analyses = len(items) - len(experiments)
    summary = (f"{_count(len(experiments), 'expérience')}, {_count(analyses, 'analyse')}, "
               f"{_count(len(decisions), 'décision')}. En-têtes de notes.md manquants ou illisibles : "
               f"{len(missing)} sur {len(items)}.")
    return {
        # Chemin local du dépôt masqué (R-U7) : seul compte ce qui est lu, pas où.
        "resume": f'<p class="pl-meta">{escape(summary)} Lu en lecture seule dans le dépôt.</p>',
        "appris": _learned_html(root, items),
        "graphique": graphique.figure(reference_systems(items)),
        "frise": _timeline_html(items, root),
        "oracles": _oracles_html(items),
        "decisions": _decisions_html(decisions),
        "file": _queue_html(queue),
    }


def notes_markdown(root: Path, item_id: str) -> str:
    """Contenu de notes.md d'une expérience ou d'une analyse (en-tête YAML retiré)."""
    if item_id == SYNTHESIS_ID:
        path = root / SYNTHESIS
        return (f"`{SYNTHESIS.as_posix()}`\n\n{path.read_text(encoding='utf-8', errors='replace')}"
                if path.is_file() else f"*{SYNTHESIS.as_posix()} absent de ce dépôt.*")
    if not re.fullmatch(r"(EXP|A)-\d{4}", item_id or ""):
        return "*Identifiant invalide.*"
    folder = root / ("experiments" if item_id.startswith("EXP") else "analyses")
    matches = sorted(folder.glob(f"{item_id}_*"))
    if not matches or not (matches[0] / "notes.md").is_file():
        return f"*Pas de notes.md pour {item_id}.*"
    path = matches[0] / "notes.md"
    text = path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"^---[ \t]*\r?\n.*?\r?\n---[ \t]*\r?\n", "", text, count=1, flags=re.S)
    return f"`{path.relative_to(root)}`\n\n{text}"
