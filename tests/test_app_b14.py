"""Chantier B14 (journal du cockpit du 03/11 ; défauts relevés par la candidate sur écran
Retina) : coins des champs, anneau de focus unique, cases et radios agrandies, zones de dépôt,
schéma du Pipeline, sélecteur de thème. Sans navigateur ; les captures à devicePixelRatio 2
sont dans tests/visuel/references.spec.ts."""

import re

import pytest

from app import app as interface
from app import moteurs, pipeline
from whospoke.experiment import REPO_ROOT

STATIC = interface.STATIC_DIR
CSS = (STATIC / "interface.css").read_text()
THEME_JS = (STATIC / "theme.js").read_text()
VIEWER_JS = (STATIC / "visualiseur.js").read_text()


def page_of(key):
    page = pipeline.load_page(moteurs.SPECS[key], REPO_ROOT)
    if page.unavailable:
        pytest.skip(page.unavailable)
    return page


# --- Champs ------------------------------------------------------------------------------


def test_conteneur_des_champs_sans_arrondi_ni_debordement_masque():
    """Cause commune des coins rognés : le .form de Gradio (arrondi des blocs, overflow-y
    masqué) rognait les coins inférieurs des champs placés à ses bords."""
    assert ".form { border-radius: 0 !important; overflow: visible !important; }" in CSS


def test_regles_compatibles_avec_le_reecrivain_de_gradio():
    """Gradio préfixe chaque sélecteur et coupe aux virgules, même dans :is() : ni virgule entre
    parenthèses, ni sélecteur qui commence par .gradio-container (sauf le conteneur lui-même
    et sa colonne, qui le visent par la copie non préfixée de la règle)."""
    css = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    for selector in re.findall(r"(?:^|})\s*([^{}@]+)\{", css):
        assert not re.search(r":(is|has|not|where)\([^()]*,", selector), selector
        if selector.strip() not in (".gradio-container", ".gradio-container .main"):
            assert not selector.strip().startswith(".gradio-container"), selector


def test_un_seul_anneau_de_focus():
    for rule in ('input[type="number"]:focus-visible,', 'input[role="combobox"]:focus-visible,',
                 "textarea:focus-visible { outline: none !important; }",
                 '.wrap:has(input[role="combobox"]:focus) { box-shadow: var(--ws-ring-focus) !important; }'):
        assert rule in CSS, rule


def test_cases_et_radios_agrandies():
    assert 'input[type="radio"] { width: 18px !important; height: 18px !important; flex: none; }' in CSS
    assert 'label:has(> input[type="radio"]) { min-height: 24px; cursor: pointer; }' in CSS


def test_zone_de_depot_sous_son_etiquette():
    assert ".block:has(> label.float) > .upload-container { padding-top: 30px; }" in CSS
    assert ".upload-container .wrap { min-height: 0 !important;" in CSS


# --- Schéma du Pipeline -------------------------------------------------------------------


def test_coupure_aux_seules_espaces_ordinaires():
    lines = pipeline._wrap("fenêtres de 1,5 s, pas de 0,75 s", 60, 12)
    assert all(not line.endswith("1,5") for line in lines) and any("1,5 s" in line for line in lines)


def test_nom_de_modele_coupe_en_fin_avec_infobulle():
    html = pipeline.render(page_of("baseline-wespeaker"))
    sub = re.search(r'<text class="pl-n-sub"[^>]*><title>WeSpeakerResNet34</title><tspan[^>]*>([^<]+)</tspan></text>', html)
    assert sub and sub.group(1).endswith("…")
    assert pipeline._wrap("Normalisation", 50, 12.5, bold=True) == ["Normalisation"]     # titre entier


@pytest.mark.parametrize("key", ["baseline-wespeaker", "baseline-mfcc", "pyannote-community-1"])
def test_formes_sur_deux_lignes_sans_chevauchement(key):
    page = page_of(key)
    html = pipeline.render(page)
    shapes = re.findall(r'<text class="pl-n-shape" x="([\d.]+)" y="([\d.]+)" text-anchor="middle">(.*?)</text>', html)
    assert shapes
    per_char = pipeline.FONT["shape"] * pipeline.CHAR_EM["text"]
    boxes = []
    for x, y, body in shapes:
        lines = re.findall(r"<tspan[^>]*>([^<]*)</tspan>", body)
        assert 1 <= len(lines) <= 2
        half = max(len(line) for line in lines) * per_char / 2
        boxes.append((float(y), float(x) - half, float(x) + half))
        assert float(x) - half >= 0 and float(x) + half <= pipeline.VIEW_W
    for row in {y for y, _, _ in boxes}:
        spans = sorted((a, b) for y, a, b in boxes if y == row)
        assert all(b1 <= a2 for (_, b1), (a2, _) in zip(spans, spans[1:])), (key, spans)


# --- Sélecteur de thème -------------------------------------------------------------------


def test_selecteur_de_theme_dans_l_en_tete():
    header = interface._header_html(True)
    assert '<div class="ws-segmented ws-theme" role="group" aria-label="Thème">' in header
    assert [key for key, _ in interface.THEMES] == ["clair", "sombre", "systeme"]
    assert all(f'data-theme="{key}"' in header for key, _ in interface.THEMES)
    assert "theme.js" not in header and THEME_JS in interface.page_head()
    # Visible en mode présentation : ce n'est pas un badge.
    assert "ws-badge" not in header[header.index("ws-theme"):header.index("</div>", header.index("ws-theme"))]


def test_theme_memorise_protege_et_coherent_avec_l_url():
    assert THEME_JS.count("try {") == 2 and "localStorage" in THEME_JS
    assert ".get('__theme')" in THEME_JS and "history.replaceState" in THEME_JS
    assert "return CHOICES.includes(stored) ? stored : 'systeme';" in THEME_JS
    assert "media.addEventListener('change'" in THEME_JS


def test_visualiseur_redessine_les_couleurs_au_changement_de_theme():
    observer = VIEWER_JS[VIEWER_JS.index("element._themeObserver = new MutationObserver"):]
    observer = observer[:observer.index("\n});")]
    for call in ("render();", "miniWavesurfer.setOptions", "setOptions({ cursorColor", "overlay.style.backgroundColor"):
        assert call in observer, call
