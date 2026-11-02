"""Chantier B13 (audit visuel du 02/11, §7) : onglets Avancement et Glossaire au système
visuel de B10, quatre onglets à 375 px sans le menu « … », correctifs de la passe break-ui.
Sans navigateur ; les captures et axe-core sont dans tests/visuel."""

import re
from pathlib import Path

import pytest

from app import app as interface
from app import avancement as av
from app import formatage
from app import glossaire as g
from whospoke.experiment import REPO_ROOT

STATIC = interface.STATIC_DIR
CSS = (STATIC / "interface.css").read_text()
TOKENS = (STATIC / "jetons.css").read_text()
VIEWER_JS = (STATIC / "visualiseur.js").read_text()


def test_quatre_onglets_a_375_px():
    """Gradio mesure une copie masquée de la barre (boutons sans rôle « tab ») : la règle
    réduite doit viser les deux copies, sinon les derniers onglets passent dans « … »."""
    narrow = CSS[CSS.index("@media (max-width: 640px) {\n  .tab-container > button"):]
    assert ".tab-container > button { padding: 0 var(--ws-space-2) !important; font-size: 13px !important; }" in narrow


def test_date_en_francais():
    assert formatage.date("2026-10-27") == "27/10/2026"
    assert formatage.date("2026-10-29T14:11:49+01:00") == "29/10/2026"
    assert formatage.date(None) == "—" and formatage.date("hier") == "hier"


def test_petit_bouton_et_etiquette_de_confiance_communs():
    assert "--ws-control-h-sm: 28px;" in TOKENS and "--ws-control-h-sm: 36px;" in TOKENS
    assert ".ws-btn-sm { height: var(--ws-control-h-sm);" in CSS
    assert ".ws-conf {" in CSS and "av-confidence" not in CSS
    assert ".ws-fold > summary {" in CSS


@pytest.fixture(scope="module")
def sections():
    return av.render(REPO_ROOT)


def test_avancement_tableaux_empilables_et_formates(sections):
    for key in ("frise", "oracles", "file"):
        assert "av-stack" in sections[key], key
        cells = re.findall(r"<td( [^>]*)?>", sections[key])
        assert cells and all("data-label=" in (attrs or "") for attrs in cells), key
    assert "av-stack" in sections["decisions"]
    frise = sections["frise"]
    assert not re.search(r">\d{4}-\d{2}-\d{2}<", frise)                       # dates en français
    assert "ws-btn ws-btn-sm av-notes" in frise
    narrow = CSS[CSS.index(".ws-table-wrap:has(> .av-stack)") - 40:]
    assert "content: attr(data-label)" in narrow


def test_avancement_aides_repliees(sections):
    assert '<details class="ws-howto-read"><summary>Comment lire ce tableau</summary>' in sections["oracles"]
    if "av-learned-list" in sections["appris"]:
        assert "<summary>Comment lire ces constats</summary>" in sections["appris"]
    assert 'class="av-values ws-fold"' in sections["graphique"] or "Aucun résultat" in sections["graphique"]


def test_corpus_et_mode_en_clair():
    assert av.MODE_LABELS["estime"] == "estimé"
    assert av._corpus("ami") == "AMI (SDM)" and av._corpus("summre") == "SUMM-RE"


def test_glossaire_intro_repliee_confiance_et_source():
    path = REPO_ROOT / g.GLOSSARY_RELATIVE
    if not path.is_file():
        pytest.skip("docs/glossaire.md absent")
    glossary = g.read_glossary(path)
    html = g.render(glossary, g.Linker(glossary))
    assert '<details class="ws-howto-read gl-about"><summary>À propos de ce glossaire</summary>' in html
    assert html.index("gl-indexes") < html.index("gl-about")
    # Étiquette dans le texte ; les infobulles (title), en texte brut, gardent « [probable] ».
    assert "[probable]" not in re.sub(r'title="[^"]*"', "", html)
    assert '<span class="ws-conf ws-conf-probable">probable</span>' in html
    assert '<dt class="gl-source">Source</dt>' in html
    assert g._inline("**[certain]** : vérifié") == '<span class="ws-conf ws-conf-certain">certain</span> : vérifié'


def test_mode_presentation_masque_chemins_et_sources():
    assert "html.ws-presentation .av-path, html.ws-presentation .gl-source { display: none !important; }" in CSS


def test_filet_du_glossaire_sans_arrondi():
    rule = CSS[CSS.index(".gl-term {"):CSS.index("}", CSS.index(".gl-term {"))]
    assert "border-radius" not in rule and "box-shadow: var(--ws-rule-top)" in rule


# --- Passe break-ui -----------------------------------------------------------------------


def test_noms_de_pistes_coupes_au_milieu():
    """12 locuteurs aux noms longs : « Marie-Hélène … » partout ; la fin gardée les distingue."""
    assert "function splitName(text)" in VIEWER_JS and "wsp-label-tail" in VIEWER_JS
    assert ", true);" in VIEWER_JS[VIEWER_JS.index("tracks[spk.id] = addRow("):]   # locuteurs seulement
    viewer_css = (STATIC / "visualiseur.css").read_text()
    assert ".wsp-label-tail { flex: none; white-space: pre; }" in viewer_css


def test_noms_de_la_matrice_sur_deux_lignes():
    assert "-webkit-line-clamp: 2" in CSS[CSS.index(".ws-mx-who {"):]
    source = Path(interface.__file__).read_text()
    assert '<span class="ws-mx-who">{number}{who(before)}</span>' in source


def test_titre_de_comparaison_garde_la_casse_du_moteur():
    source = Path(interface.__file__).read_text()
    assert "if not prefix:          # en comparaison" in source


def test_frise_limitee_sous_840_px(sections):
    """Retour du cockpit sur B13 : sous 840 px, les cinq dernières lignes et « Afficher les N
    autres » ; au-delà, tout est affiché et le bouton masqué."""
    frise = sections["frise"]
    rows = frise.count("<tr") - 1                        # moins la ligne d'en-tête
    older = rows - av.TIMELINE_RECENT
    assert older > 0 and frise.count('<tr class="av-older">') == older
    assert f'aria-controls="av-frise" data-more="Afficher les {older} autres"' in frise
    assert "@media (min-width: 841px) { .av-more { display: none; } }" in CSS
    assert "@media (max-width: 840px) { .av-frise:not(.av-all) tr.av-older { display: none; } }" in CSS
    assert ".av-more" in interface.NOTES_JS and "av-all" in interface.NOTES_JS


def test_frise_courte_sans_bouton():
    assert av.TIMELINE_RECENT == 5
    assert "av-more" not in av._timeline_html([], REPO_ROOT)
