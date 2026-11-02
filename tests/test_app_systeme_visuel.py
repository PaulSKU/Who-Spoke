"""Système visuel (audit visuel du 02/11, §3 et §4 ; chantier B10) : thème, jetons, règles des
feuilles de style, composants communs, formatage français. Sans navigateur ; les captures de
référence, axe-core et stylelint sont dans tests/visuel (Node, app/README.md)."""

import re

import gradio as gr
import pytest

from app import app as interface
from app import formatage, theme
from app.icones import PATHS, icon

STATIC = theme.STATIC_DIR
TOKENS = (STATIC / "jetons.css").read_text()
SHEETS = {name: (STATIC / name).read_text() for name in ("interface.css", "visualiseur.css")}


def _block(selector: str) -> str:
    start = TOKENS.index(selector + " {")
    return TOKENS[start:TOKENS.index("\n}", start)]


def _value(block: str, name: str) -> str:
    return re.search(rf"{re.escape(name)}:\s*([^;]+);", block).group(1).strip()


# --- Thème ----------------------------------------------------------------------------


def test_toutes_les_variantes_sombres_definies():
    """Gradio reprend la valeur claire d'une variante _dark non définie (cause de V1)."""
    base = gr.themes.Base()
    dark = {k[:-5] for k in vars(base) if k.endswith("_dark") and not k.startswith("_")}
    assert len(dark) > 100 and set(theme.WITH_DARK) == dark
    built = theme.build_theme()
    for name in dark:
        assert getattr(built, f"{name}_dark") == getattr(built, name) == theme.WITH_DARK[name], name


def test_valeurs_du_theme_par_jetons():
    allowed = re.compile(r"^(var\(--ws-[a-z0-9-]+\)|none|transparent|\d+(\.\d+)?px|\d{3}|\d+(\.\d+)?rem"
                         r"|var\(--ws-space-\d\) var\(--ws-space-\d\)|radial-gradient\(.*\))$")
    for name, value in {**theme.WITH_DARK, **theme.WITHOUT_DARK}.items():
        assert allowed.match(value), (name, value)
    assert "#" not in "".join(theme.WITH_DARK.values()) + "".join(theme.WITHOUT_DARK.values())
    # Aucune ombre sur les contrôles ; point du radio de la couleur du fond.
    assert all(v == "none" for k, v in theme.WITH_DARK.items() if "shadow" in k and k != "shadow_spread")
    assert theme.WITHOUT_DARK["radio_circle"].startswith("radial-gradient(circle, var(--background-fill-primary)")
    assert ".gradio-container input[type=\"radio\"]:checked" in TOKENS and "var(--radio-circle) !important" in TOKENS


def test_jetons_dans_l_en_tete_hors_reecriture():
    head = interface.page_head()
    assert head.startswith("<style>") and TOKENS in head
    for selector in (":root {", ".dark {", ":root, .dark {", "html.ws-presentation {"):
        assert selector in TOKENS


def test_jetons_employes_tous_definis():
    defined = set(re.findall(r"(--ws-[a-z0-9-]+)\s*:", TOKENS))
    used = set()
    for text in [*SHEETS.values(), (STATIC / "visualiseur.js").read_text(),
                 *theme.WITH_DARK.values(), *theme.WITHOUT_DARK.values()]:
        used |= set(re.findall(r"var\((--ws-[a-z0-9-]+)", text)) | set(re.findall(r"token\('(--ws-[a-z0-9-]+)'\)", text))
    assert used and used <= defined, sorted(used - defined)


def test_jetons_composes_recalcules_en_sombre():
    """Un jeton qui renvoie à un autre est résolu là où il est déclaré : déclaré sur :root
    seulement, il garderait les teintes claires en sombre."""
    composite = _block(":root, .dark")
    for block in (_block(":root"), _block(".dark")):
        for name, value in re.findall(r"(--ws-[a-z0-9-]+):\s*([^;]+);", block):
            if name != "--ws-shadow-card":     # redéfini en entier dans chaque mode
                assert "var(" not in value, name
    assert "--ws-ring: 0 0 0 1px var(--ws-line);" in composite


# --- Feuilles de style ----------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(SHEETS))
def test_feuilles_sans_valeur_en_dur_ni_regle_reecrite(name):
    css = re.sub(r"/\*.*?\*/", "", SHEETS[name], flags=re.S)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
    assert not re.search(r"\b(rgba?|hsla?)\(", css)
    assert "svelte-" not in css and "prefers-color-scheme" not in css
    assert set(re.findall(r"@([a-z-]+)", css)) <= {"media", "keyframes", "font-face"}
    assert not re.search(r"(^|[\s,>+~(])(:root|body)\b", css, re.M)
    for value in re.findall(r"box-shadow:\s*([^;!]+)", css):
        assert re.fullmatch(r"none|var\(--ws-[a-z-]+\)(,\s*var\(--ws-[a-z-]+\))*", value.strip()), value
    for value in re.findall(r"border-radius:\s*([^;!]+)", css):
        assert re.fullmatch(r"0|var\(--ws-radius-[a-z]+\)|calc\(var\(--ws-radius-[a-z]+\) - \d+px\)", value.strip()), value
    assert "transition: all" not in css


def test_anneau_de_focus_sur_les_radios_et_cases():
    assert "label:has(input:focus-visible) { outline: 2px solid var(--ws-ink); outline-offset: 2px; }" in SHEETS["interface.css"]


def _luminance(color: str) -> float:
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("selector", [":root", ".dark"])
def test_contrastes_wcag_aa(selector):
    block = _block(selector)
    for surface in ("--ws-surface", "--ws-canvas", "--ws-track"):
        assert _contrast(_value(block, "--ws-control-line"), _value(block, surface)) >= 3.0   # WCAG 1.4.11
        assert _contrast(_value(block, "--ws-ink"), _value(block, surface)) >= 7.0
    for surface in ("--ws-surface", "--ws-canvas"):
        assert _contrast(_value(block, "--ws-slate"), _value(block, surface)) >= 4.5             # WCAG 1.4.3
    assert _contrast(_value(block, "--ws-on-ink"), _value(block, "--ws-ink")) >= 7.0


# --- Composants communs --------------------------------------------------------------


def test_composants_communs():
    css = SHEETS["interface.css"]
    for selector in (".ws-btn {", ".ws-btn-primary {", ".ws-btn-icon {", ".ws-switch[aria-pressed=\"true\"]",
                     ".ws-segmented {", ".ws-callout,", ".ws-attention,"):
        assert selector in css, selector
    template = interface.VIEWER_TEMPLATE
    assert 'class="ws-segmented wsp-view"' in template
    assert 'class="ws-btn ws-switch wsp-follow" aria-pressed="true"' in template
    assert 'class="ws-btn ws-switch wsp-energy-toggle"' in template
    assert template.count("ws-btn-icon") == 4      # −, +, ?, ×
    assert "ws-icon-lecture" in template and "ws-icon-pause" in template


def test_icone_de_lecture_centree_optiquement():
    """V4 : triangle centré sur son centre de gravité, donc décalé vers la droite de sa boîte."""
    numbers = [float(x) for x in re.findall(r"[\d.]+", PATHS["lecture"])]
    xs = numbers[0::2]
    assert sum(xs) / 3 == pytest.approx(8.0, abs=0.1)               # centre de gravité au centre
    assert (min(xs) + max(xs)) / 2 - 8.0 == pytest.approx(1.2, abs=0.05)
    svg = icon("lecture")
    assert 'aria-hidden="true"' in svg and 'fill="currentColor"' in svg


def test_boutons_d_extrait_en_bouton_icone():
    from tests.test_app_appariement import HYPOTHESIS

    html = interface._stats_html({"annotation": HYPOTHESIS, "names": {}})
    buttons = re.findall(r"<button[^>]*ws-excerpt[^>]*>.*?</button>", html)
    assert buttons and all("ws-btn ws-btn-icon" in b and "<svg" in b and "aria-label=" in b for b in buttons)
    assert "▶" not in "".join(buttons)


# --- Formatage français --------------------------------------------------------------


@pytest.mark.parametrize("call, expected", [
    (lambda: formatage.nombre(1234567.891, 2), "1 234 567,89"),
    (lambda: formatage.nombre(-0.004, 2), "0,00"),
    (lambda: formatage.nombre(-3.5, 1), "−3,5"),
    (lambda: formatage.nombre(0.8, 2, sign=True), "+0,80"),
    (lambda: formatage.pourcentage(26.594, 2), "26,59 %"),
    (lambda: formatage.pourcentage(None), "—"),
    (lambda: formatage.unite(2.98, "s", 2), "2,98 s"),
    (lambda: formatage.duree(0.05), "0,05 s"),
    (lambda: formatage.duree(125), "2 min 05 s"),
    (lambda: formatage.duree(3720), "1 h 02 min"),
    (lambda: formatage.taille(512), "512 o"),
    (lambda: formatage.taille(7200), "7,2 Ko"),
    (lambda: formatage.taille(3_400_000), "3,4 Mo"),
    (lambda: formatage.general(1e-5), "1e−05"),
    (lambda: formatage.general(0.7045), "0,7045"),
])
def test_formatage_francais(call, expected):
    assert call() == expected


def test_formatage_employe_partout():
    """Plus de formatage de nombres à la main dans l'application."""
    from pathlib import Path

    for path in Path(interface.__file__).parent.glob("*.py"):
        if path.name == "formatage.py":
            continue
        text = path.read_text()
        assert 'replace(".", ",")' not in text, path.name
    assert "NNBSP" in (STATIC / "visualiseur.js").read_text()
