"""Glossaire intégré (D26, chantier I3) : onglet généré depuis `docs/glossaire.md`, et
renvois automatiques des autres onglets vers les définitions.

Lecture du glossaire (format de methode.md §4.6) : chaque terme est un titre
`### Terme français (*terme anglais*, SIGLE)` suivi de ses champs (`Définition : …`).
Les titres `##` sont des parties ; le texte qui précède la première partie est
l'introduction.

Correspondance automatique, sans liste tenue à la main. Variantes d'un terme : le terme
français, les termes anglais en italique, et les éléments entre parenthèses qui
contiennent une majuscule (sigles, noms propres : VAD, EEND, Sortformer) ; un qualificatif
en minuscules, comme « (système) » dans « Hybride (système) », n'en est pas une. Chaque mot
peut prendre la marque du pluriel (s, x). Un terme n'est reconnu que comme mot entier :
jamais à l'intérieur d'un identifiant ou d'une expression (`der_c0`, `clustering.threshold`,
`VBxClustering`, `collar=0.5`).
À une même position, la variante la plus longue l'emporte. Les sigles (au moins deux
majuscules) sont sensibles à la casse, les autres termes non.

Renvois (`link`) : dans un fragment HTML, chaque terme est lié à sa définition à sa
première occurrence dans chaque bloc (paragraphe, cellule, élément de liste, titre…) ;
jamais dans du code, un bouton, un lien existant ni un attribut.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser
from pathlib import Path

GLOSSARY_RELATIVE = Path("docs") / "glossaire.md"
TAB_LABEL = "Glossaire"

BLOCK_TAGS = {"p", "li", "td", "th", "h1", "h2", "h3", "h4", "h5", "dt", "dd", "caption", "summary",
              "label", "div", "section", "article", "header", "nav"}
SKIP_TAGS = {"a", "code", "button", "pre", "script", "style", "textarea", "select", "option", "svg", "kbd"}
VOID_TAGS = {"br", "img", "input", "hr", "meta", "link", "wbr", "source", "col", "area", "base", "embed"}
_FIELD = re.compile(r"^([A-ZÀ-Ý][^:]{1,40}) : (.*)$")
_HEADING = re.compile(r"^###\s+(.+?)\s*$")


def slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "gl-" + re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


@dataclass
class Term:
    title: str                      # titre complet, tel qu'écrit
    name: str                       # terme français
    english: list[str]
    aliases: list[str]
    part: str
    fields: list[tuple[str, str]] = field(default_factory=list)

    @property
    def anchor(self) -> str:
        return slug(self.name)

    @property
    def variants(self) -> list[str]:
        return [self.name, *self.english, *self.aliases]

    @property
    def definition(self) -> str:
        return next((value for key, value in self.fields if key == "Définition"), "")


@dataclass
class Glossary:
    intro: str = ""
    sections: list[tuple[str, str]] = field(default_factory=list)   # parties sans terme (titre, texte)
    terms: list[Term] = field(default_factory=list)


def parse_heading(title: str) -> tuple[str, list[str], list[str]]:
    """(terme français, termes anglais, alias) d'un titre `### …`."""
    match = re.match(r"^(.*?)\s*\((.*)\)\s*$", title)
    if not match:
        return title.strip(), [], []
    name, inside = match.group(1).strip(), match.group(2)
    english, aliases = [], []
    for item in (part.strip() for part in inside.split(",")):
        if not item:
            continue
        italic = re.fullmatch(r"\*(.+)\*", item)
        if italic:
            english.append(italic.group(1).strip())
        elif any(c.isupper() for c in item):
            aliases.append(item)
        # sinon : qualificatif (« système »), pas une variante
    return name, english, aliases


def read_glossary(path: Path) -> Glossary:
    """Glossaire lu dans `path` ; vide si le fichier manque.

    Une partie `##` peut porter un texte (avant ses termes) ; une ligne `---` clôt la
    partie en cours : les termes qui suivent n'appartiennent à aucune partie.
    """
    glossary = Glossary()
    if not path.is_file():
        return glossary
    part = ""
    intro: list[str] = []
    section_text: list[str] = []
    current: Term | None = None

    def flush_section() -> None:
        if part and section_text:
            glossary.sections.append((part, " ".join(section_text).strip()))
        section_text.clear()

    for line in path.read_text(encoding="utf-8").splitlines():
        heading = _HEADING.match(line)
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            flush_section()
            part, current = line[3:].strip(), None
            continue
        if line.strip() == "---":
            flush_section()
            part, current = "", None
            continue
        if heading:
            flush_section()
            name, english, aliases = parse_heading(heading.group(1))
            current = Term(heading.group(1), name, english, aliases, part)
            glossary.terms.append(current)
            continue
        if current is not None:
            match = _FIELD.match(line)
            if match:
                current.fields.append((match.group(1), match.group(2)))
            elif line.strip() and current.fields:
                key, value = current.fields[-1]
                current.fields[-1] = (key, f"{value} {line.strip()}")
        elif part:
            if line.strip():
                section_text.append(line.strip())
        elif line.strip() and not glossary.terms:
            intro.append(line.strip())
    flush_section()
    glossary.intro = " ".join(intro)
    return glossary


def _is_acronym(text: str) -> bool:
    return sum(c.isupper() for c in text) >= 2


def _variant_pattern(variant: str) -> str:
    """Motif d'une variante : pluriel facultatif par mot, apostrophes typographiques."""
    tokens = re.split(r"(\s+|['’])", variant)
    out = []
    for token in tokens:
        if not token:
            continue
        if token.isspace():
            out.append(r"\s+")
        elif token in ("'", "’"):
            out.append("['’]")
        elif token.isalpha() and len(token) >= 3 and not _is_acronym(token):
            out.append(re.escape(token) + "(?:s|x)?")
        else:
            out.append(re.escape(token))
    return "".join(out)


class Linker:
    """Lie les termes du glossaire dans des fragments HTML."""

    def __init__(self, glossary: Glossary) -> None:
        self.glossary = glossary
        entries = []
        for term in glossary.terms:
            for variant in term.variants:
                if len(variant) >= 2:
                    entries.append((variant, term))
        # Variante la plus longue d'abord : l'alternative regex s'arrête à la première qui convient.
        entries.sort(key=lambda e: len(e[0]), reverse=True)
        self._entries = entries
        self._regex = None
        if entries:
            alternatives = "|".join(f"(?P<v{i}>{_variant_pattern(v)})" for i, (v, _) in enumerate(entries))
            # Ni lettre, chiffre, _, - ou = avant ou après ; ni « . » collé à un mot (identifiant
            # pointé, `clustering.threshold`) : un terme n'est jamais lié à l'intérieur de code.
            self._regex = re.compile(rf"(?<![\w\-.=])(?:{alternatives})(?![\w\-=]|\.\w)", re.IGNORECASE)

    def matches(self, text: str):
        """(début, fin, terme) de chaque occurrence, de gauche à droite."""
        if self._regex is None:
            return
        position = 0
        while True:
            match = self._regex.search(text, position)
            if match is None:
                return
            index = int(match.lastgroup[1:])
            variant, term = self._entries[index]
            if _is_acronym(variant) and match.group(0) != variant:
                position = match.start() + 1     # sigle en mauvaise casse : on ignore
                continue
            yield match.start(), match.end(), term
            position = match.end()

    def link(self, html: str, exclude: str | None = None) -> str:
        """Fragment `html` avec les termes liés (première occurrence par bloc)."""
        if self._regex is None or not html:
            return html
        parser = _LinkingParser(self, exclude)
        parser.feed(html)
        parser.close()
        return "".join(parser.out)


class _LinkingParser(HTMLParser):
    def __init__(self, linker: Linker, exclude: str | None) -> None:
        super().__init__(convert_charrefs=True)
        self.linker = linker
        self.exclude = exclude
        self.out: list[str] = []
        self.blocks: list[set[str]] = [set()]
        self.skip = 0
        self.open: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.out.append(self.get_starttag_text())
        if tag in VOID_TAGS:
            return
        self.open.append(tag)
        if tag in SKIP_TAGS:
            self.skip += 1
        if tag in BLOCK_TAGS:
            self.blocks.append(set())

    def handle_startendtag(self, tag, attrs):
        self.out.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        self.out.append(f"</{tag}>")
        if tag in VOID_TAGS or tag not in self.open:
            return
        # Ferme aussi les éléments laissés ouverts à l'intérieur (HTML tolérant).
        while self.open:
            closed = self.open.pop()
            if closed in SKIP_TAGS:
                self.skip = max(0, self.skip - 1)
            if closed in BLOCK_TAGS and len(self.blocks) > 1:
                self.blocks.pop()
            if closed == tag:
                break

    def handle_data(self, data):
        if self.skip:
            self.out.append(escape(data, quote=False))
            return
        used = self.blocks[-1]
        position = 0
        for start, end, term in self.linker.matches(data):
            if term.anchor in used or term.anchor == self.exclude:
                continue
            used.add(term.anchor)
            self.out.append(escape(data[position:start], quote=False))
            title = escape(f"{term.name} : {_plain(term.definition)}"[:300])
            self.out.append(f'<a class="gl-link" href="#{term.anchor}" data-term="{term.anchor}" '
                            f'title="{title}">{escape(data[start:end], quote=False)}</a>')
            position = end
        self.out.append(escape(data[position:], quote=False))

    def handle_comment(self, data):
        self.out.append(f"<!--{data}-->")

    def handle_decl(self, decl):
        self.out.append(f"<!{decl}>")


def _plain(markdown: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*|\*(.+?)\*|`([^`]+)`", lambda m: next(g for g in m.groups() if g), markdown)


def _inline(markdown: str) -> str:
    """Markdown en ligne du glossaire : `code`, **gras**, *italique*."""
    html = escape(markdown, quote=False)
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    return re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", html)


def render(glossary: Glossary, linker: Linker | None = None) -> str:
    """Onglet Glossaire : index, introduction, parties, une ancre par terme."""
    if not glossary.terms:
        return '<p class="ws-empty-note">Glossaire introuvable ou vide (docs/glossaire.md).</p>'
    link = (lambda html, exclude=None: linker.link(html, exclude)) if linker else (lambda html, exclude=None: html)
    index = "".join(f'<a class="gl-index" href="#{t.anchor}" data-term="{t.anchor}">{escape(t.name)}</a>'
                    for t in sorted(glossary.terms, key=lambda t: _sort_key(t.name)))
    order: list[str] = []
    for title, _ in glossary.sections:
        order.append(title)
    for term in glossary.terms:
        if term.part not in order:
            order.append(term.part)
    texts = dict(glossary.sections)
    body = []
    for part in order:
        if part:
            body.append(f'<h3 class="gl-part">{escape(part)}</h3>')
        if texts.get(part):
            body.append(link(f'<p class="gl-part-text">{_inline(texts[part])}</p>'))
        for term in (t for t in glossary.terms if t.part == part):
            english = "".join(f' <span class="gl-en">({escape(e)})</span>' for e in term.english)
            aliases = (f' <span class="gl-alias">{escape(", ".join(term.aliases))}</span>' if term.aliases else "")
            fields = "".join(f"<dt>{escape(k)}</dt>{link(f'<dd>{_inline(v)}</dd>', term.anchor)}" for k, v in term.fields)
            body.append(f'<article class="gl-term" id="{term.anchor}"><h4>{escape(term.name)}{english}{aliases}</h4>'
                        f'<dl>{fields}</dl></article>')
    intro = f'<p class="pl-meta">{_inline(glossary.intro)}</p>' if glossary.intro else ""
    return (f'<div class="gl-root">{intro}<nav class="gl-indexes" aria-label="Index du glossaire">{index}</nav>'
            + "".join(body) + "</div>")


def _sort_key(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
