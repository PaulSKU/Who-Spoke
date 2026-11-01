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
- file d'attente de D23 : tableau « File d'attente » de `docs/planning.md`, complété d'un
  état calculé (expériences citées ayant des résultats, fiches citées présentes ou non).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

import yaml

VERDICTS = {
    "reference": "référence",
    "retenu": "retenu",
    "ecarte": "écarté",
    "informatif": "informatif",
    "en_cours": "en cours",
}
MISSING_HEADER = "en-tête manquant"
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
            item.date = first.get("date") or _execution_date(directory)
            items.append(item)
    return sorted(items, key=lambda i: (i.date or "9999", i.id))


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
    task: str
    condition: str
    state: str


def _exp_ids(text: str) -> list[str]:
    ids = []
    for start, end in re.findall(r"EXP-(\d{4})\s*(?:à|-|–)\s*(?:EXP-)?(\d{4})", text):
        ids += [f"EXP-{n:04d}" for n in range(int(start), int(end) + 1)]
    ids += [f"EXP-{n}" for n in re.findall(r"EXP-(\d{4})", text) if f"EXP-{n}" not in ids]
    return ids


def read_queue(root: Path, items: list[Item]) -> list[QueueRow]:
    path = root / "docs" / "planning.md"
    if not path.is_file():
        return []
    by_id = {item.id: item for item in items}
    fiches = {d.number for d in read_decisions(root) if d.source.startswith("docs/decisions/")}
    rows = []
    for row in markdown_table(path.read_text(encoding="utf-8"), after="## File d'attente"):
        task = row.get("Expérience ou chantier", "")
        condition = row.get("Condition", "")
        states = []
        ids = _exp_ids(task)
        if ids:
            done = [i for i in ids if i in by_id and by_id[i].results]
            created = [i for i in ids if i in by_id]
            states.append(f"{len(done)}/{len(ids)} avec résultats, {len(created)}/{len(ids)} créées")
        for number in _DECISION.findall(f"{task} {condition}"):
            if int(number) > 15:
                states.append(f"fiche D{number} " + ("présente" if int(number) in fiches else "absente"))
        rows.append(QueueRow(row.get("Rang", ""), task, condition, " ; ".join(states) or "—"))
    return rows


# --- Rendu -------------------------------------------------------------------------


def _inline(text: str) -> str:
    """Texte échappé, avec le code Markdown en ligne (`…`) rendu en <code>."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", escape(text))


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}".replace(".", ",") + " %"


def _der_cell(result: Result | None) -> str:
    if result is None:
        return "—"
    flag = ' <span class="av-flag">invalidée</span>' if result.invalidated else ""
    return (f'<span class="strong">{_pct(result.der_c0)}</span>'
            f'<span class="sub">collar 0,25 s : {_pct(result.der_c025)}</span>{flag}')


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


def _timeline_html(items: list[Item], root: Path) -> str:
    rows = []
    for item in items:
        question, verdict, decisions = _header_cells(item)
        if item.kind == "analyse":
            der_test = der_dev = '<span class="sub">analyse a posteriori</span>'
            corpus = "—"
        else:
            corpus = escape(", ".join(item.corpora) or "—")
            # Une ligne par corpus quand une expérience en compte plusieurs.
            der_test = "<br>".join(_der_cell(item.result("test", c)) for c in item.corpora) or "—"
            der_dev = "<br>".join(_der_cell(item.result("dev", c)) for c in item.corpora) or "—"
        notes = (f'<button type="button" class="av-notes" data-id="{item.id}">notes.md</button>'
                 if item.notes.is_file() else '<span class="sub">pas de notes</span>')
        rows.append(
            f'<tr><td><span class="strong">{item.id}</span><span class="sub">{escape(item.slug)}</span>'
            f'<span class="sub">{escape(item.date[:10])}</span></td><td>{question}</td><td>{corpus}</td>'
            f'<td class="num">{der_test}</td><td class="num">{der_dev}</td><td>{verdict}</td>'
            f'<td>{decisions}</td><td>{notes}</td></tr>'
        )
    return (
        '<div class="ws-table-wrap"><table class="ws-table av-table"><thead><tr>'
        '<th scope="col">Identifiant</th><th scope="col">Question</th><th scope="col">Corpus</th>'
        '<th scope="col" class="num">DER test</th><th scope="col" class="num">DER dev</th>'
        '<th scope="col">Verdict</th><th scope="col">Décisions</th><th scope="col">Notes</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def _oracles_html(items: list[Item]) -> str:
    by_id = {item.id: item for item in items}
    rows = []
    for exp_id in ORACLE_SERIES:
        item = by_id.get(exp_id)
        if item is None:
            rows.append(f'<tr><td>{exp_id}</td><td colspan="7"><span class="sub">absente de ce dépôt</span></td></tr>')
            continue
        for corpus in item.corpora or ["—"]:
            result = item.result("test", corpus)
            reference = by_id.get(item.reference) if item.reference else None
            ref_result = reference.result("test", corpus) if reference else None
            delta = "—"
            if result and ref_result and result.der_c0 is not None and ref_result.der_c0 is not None:
                diff = result.der_c0 - ref_result.der_c0
                delta = f"{diff:+.2f}".replace(".", ",") + f" pt <span class=\"sub\">face à {escape(item.reference)}</span>"
            c = result.components if result else {}
            variable = escape(item.variable or "— (référence)")
            rows.append(
                f'<tr><td><span class="strong">{exp_id}</span><span class="sub">{escape(item.slug)}</span></td>'
                f'<td>{escape(item.pipeline or "—")}<span class="sub">locuteurs : {escape(item.mode or "—")}</span></td>'
                f'<td>{variable}</td><td class="num strong">{_pct(result.der_c0 if result else None)}</td>'
                f'<td class="num">{_pct(c.get("manquee"))}</td><td class="num">{_pct(c.get("fausse_alarme"))}</td>'
                f'<td class="num">{_pct(c.get("confusion"))}</td><td class="num">{delta}</td></tr>'
            )
    return (
        '<div class="ws-table-wrap"><table class="ws-table av-table"><thead><tr>'
        '<th scope="col">Expérience</th><th scope="col">Moteur</th><th scope="col">Variable modifiée</th>'
        '<th scope="col" class="num">DER</th><th scope="col" class="num">Parole manquée</th>'
        '<th scope="col" class="num">Fausse alarme</th><th scope="col" class="num">Confusion</th>'
        f'<th scope="col" class="num">Écart</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        '<p class="ws-caption">Partition test, sans collar, chevauchements comptés. Écart : différence de DER '
        'avec l\'expérience de référence, une seule variable modifiée (D9).</p>'
    )


def _decisions_html(decisions: list[Decision]) -> str:
    rows = []
    for d in decisions:
        amendments = "".join(f'<span class="sub">{_inline(t)} : {_inline(s)}</span>' for t, s in d.amendments)
        rows.append(f'<tr><td class="strong">D{d.number}</td><td>{_inline(d.title)}'
                    f'<span class="sub"><code>{escape(d.source)}</code></span></td>'
                    f'<td>{_inline(d.status)}{amendments}</td></tr>')
    return ('<div class="ws-table-wrap"><table class="ws-table av-table"><thead><tr><th scope="col">Fiche</th>'
            '<th scope="col">Décision</th><th scope="col">Statut</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def _queue_html(queue: list[QueueRow]) -> str:
    if not queue:
        return '<p class="ws-empty-note">Tableau « File d\'attente » introuvable dans docs/planning.md.</p>'
    rows = "".join(f'<tr><td class="num">{escape(q.rank)}</td><td>{_inline(q.task)}</td>'
                   f'<td>{_inline(q.condition)}</td><td>{escape(q.state)}</td></tr>' for q in queue)
    return ('<div class="ws-table-wrap"><table class="ws-table av-table"><thead><tr><th scope="col" class="num">Rang</th>'
            '<th scope="col">Expérience ou chantier</th><th scope="col">Condition</th>'
            f'<th scope="col">État constaté</th></tr></thead><tbody>{rows}</tbody></table></div>'
            '<p class="ws-caption">Tableau de docs/planning.md ; « État constaté » est calculé depuis les '
            'dossiers d\'expériences et les fiches présentes.</p>')


def _count(n: int, word: str) -> str:
    return f"{n} {word}{'s' if n > 1 else ''}"


def render(root: Path) -> dict[str, str]:
    """Sections HTML de l'onglet, chacune autonome."""
    items = read_items(root)
    decisions = read_decisions(root)
    queue = read_queue(root, items)
    experiments = [i for i in items if i.kind == "experience"]
    missing = [i.id for i in items if i.header.status != "ok"]
    analyses = len(items) - len(experiments)
    summary = (f"{_count(len(experiments), 'expérience')}, {_count(analyses, 'analyse')}, "
               f"{_count(len(decisions), 'décision')}. En-têtes de notes.md manquants ou illisibles : "
               f"{len(missing)} sur {len(items)}.")
    return {
        "resume": f'<p class="pl-meta">{escape(summary)} Lu dans <code>{escape(str(root))}</code>.</p>',
        "frise": _timeline_html(items, root),
        "oracles": _oracles_html(items),
        "decisions": _decisions_html(decisions),
        "file": _queue_html(queue),
    }


def notes_markdown(root: Path, item_id: str) -> str:
    """Contenu de notes.md d'une expérience ou d'une analyse (en-tête YAML retiré)."""
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
