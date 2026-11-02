"""Onglet Analyse (audit visuel du 02/11, §5 ; chantier B11) : en-tête et détails (V6), barre
d'outils (V5), étapes repliées (V7), carte « Comment ça marche » (V8), étiquettes de la
référence (V9), phrase des zones (V10), exports (V11), aides repliées (V13), identifiant (V3)."""

import re
from pathlib import Path

from app import app as interface
from app import moteurs
from tests.test_app_appariement import HYPOTHESIS, full_result

STATIC = interface.STATIC_DIR
CSS = (STATIC / "interface.css").read_text()
VIEWER_CSS = (STATIC / "visualiseur.css").read_text()


def test_en_tete_sans_configuration_et_panneau_details():
    header = interface._header_html(True, None, moteurs.demo_config(), "pyannote-community-1")
    assert "Configuration :" not in header and 'class="ws-tagline"' in header
    details = interface._details_html(moteurs.demo_config(), "baseline-mfcc")
    assert details.startswith('<details class="ws-details"><summary>Détails : configuration et moteur</summary>')
    assert "Baseline MFCC</span> (EXP-0009)" in details and "<details open" not in details
    # Mode présentation : titre et interrupteurs seulement.
    assert ("html.ws-presentation .ws-tagline, html.ws-presentation .ws-details-wrap,\n"
            "html.ws-presentation .ws-badge { display: none !important; }") in CSS


def test_carte_comment_ca_marche():
    html = interface._howto_html()
    assert html.count('<span class="ws-howto-num"') == 3 and "Ce que vous obtiendrez" in html
    assert 'data-ws-tab="Pipeline"' in html
    assert "[data-ws-tab]" in (STATIC / "glossaire.js").read_text()


def test_etapes_repliees_une_fois_l_analyse_finie():
    steps = [f"s{i}" for i in range(7)]
    done = {step: 1.0 for step in steps}
    folded = interface._status_html(steps, done, "4 locuteurs en 3 s", done_s=3.2)
    assert '<details class="st-fold"><summary>7 étapes terminées en 3 s</summary>' in folded
    assert 'style="--st-rows: 3"' in folded
    running = interface._status_html(steps, {**done, "s6": 0.5}, "Analyse", done_s=3.2)
    assert "st-fold" not in running and "<ol class=\"st-steps\"" in running
    failed = interface._status_html(steps, done, "Échec", failed="s6", done_s=3.2)
    assert "st-fold" not in failed
    assert ".st-steps li .st-val::before { content: \"· \"; }" in CSS       # statut collé à l'étape


def test_barre_d_outils_en_groupes():
    template = interface.VIEWER_TEMPLATE
    groups = re.findall(r'class="wsp-group (wsp-g-[a-z]+)', template)
    assert groups == ["wsp-g-play", "wsp-g-view", "wsp-g-zoom", "wsp-g-help"]
    assert 'class="ws-btn ws-btn-icon wsp-zoom-toggle" aria-expanded="false" aria-controls="wsp-zoom"' in template
    # Libellés courts sur petit écran, le libellé long restant le nom accessible.
    assert '<span class="wsp-short" aria-hidden="true">Suivre</span>' in template
    assert ".wsp-group { display: flex; flex-wrap: nowrap;" in VIEWER_CSS
    narrow = VIEWER_CSS[VIEWER_CSS.index("@media (max-width: 640px)"):]
    for rule in (".wsp-g-zoom { order: 4; flex: 1 1 100%; display: none; }", ".wsp-zoom-open .wsp-g-zoom { display: flex; }",
                 ".wsp-root:not(.wsp-zoom-open) .wsp-energy-toggle { display: none; }"):
        assert rule in narrow
    assert "wsp-zoom-open" in (STATIC / "visualiseur.js").read_text()


def test_phrase_des_zones():
    assert interface._zone_text({"sans_chevauchement": 12.96, "chevauchement": None}) == (
        "12,96 % ; pas de chevauchement dans la référence")
    assert interface._zone_text({"sans_chevauchement": 5.0, "chevauchement": 30.0}) == (
        "5,00 % hors chevauchement, 30,00 % en chevauchement")
    assert "—" not in interface._zone_text({"sans_chevauchement": None, "chevauchement": 30.0})


def test_aides_repliees_et_masquees_en_presentation(tmp_path):
    stats = interface._stats_html({"annotation": HYPOTHESIS, "names": {}})
    assert '<details class="ws-howto-read"><summary>Comment lire ce tableau</summary>' in stats
    assert stats.index("ws-howto-read") > stats.index("</table>")
    assert "html.ws-presentation .ws-howto-read { display: none !important; }" in CSS


def test_identifiant_seulement_apres_renommage():
    plain = interface._stats_html({"annotation": HYPOTHESIS, "names": {}})
    assert '<span class="sub">S0</span>' not in plain
    renamed = interface._stats_html({"annotation": HYPOTHESIS, "names": {"S0": "Alice"}})
    assert '<span class="sub">S0</span>' in renamed and '<span class="sub">S1</span>' not in renamed


def test_exports_en_html_et_tailles_en_francais(tmp_path):
    result = full_result(tmp_path)
    result["annotation_origine"] = result["annotation"]
    html = interface._exports_html(result)
    links = re.findall(r'href="/gradio_api/file=([^"]+)" download="([^"]+)"', html)
    assert [Path(path).name for path, _ in links] == [name for _, name in links] == [
        "essai.rttm", "essai.json", "essai_audacity.txt", "essai_timeline.svg"]
    assert "RTTM · " in html and "Étiquettes Audacity · " in html
    sizes = re.findall(r"· ([^<]+)</span>", html)
    assert sizes and all(re.fullmatch(r"\d+(,\d)? (o|Ko|Mo)", size) for size in sizes)
    assert "KB" not in html


def test_bouton_nouvelle_analyse_a_la_largeur_de_son_libelle():
    rule = CSS[CSS.index(".ws-band-button {"):CSS.index("}", CSS.index(".ws-band-button {"))]
    assert "min-width: max-content !important" in rule and "padding: 0 var(--ws-space-4) !important" in rule
