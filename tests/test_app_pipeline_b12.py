"""Onglet Pipeline, nouvelle représentation (audit visuel du 02/11, §6 ; chantier B12), et
retours du cockpit sur B11 (préchauffage visible, panneau « Détails »). Lecture du dépôt de
ce code (expériences sources des moteurs), aucun modèle chargé."""

import re

import pytest

from app import app as interface
from app import moteurs, pipeline
from whospoke.experiment import REPO_ROOT
from whospoke.pipelines.base import load_catalogue

CSS = (interface.STATIC_DIR / "interface.css").read_text()
JS = (interface.STATIC_DIR / "pipeline.js").read_text()


def page_of(key):
    page = pipeline.load_page(moteurs.SPECS[key], REPO_ROOT)
    if page.unavailable:
        pytest.skip(page.unavailable)
    return page


# --- Formes des données -------------------------------------------------------------------


def test_formes_lues_dans_la_configuration_effective():
    shapes = {stage.id: stage.shape for stage in page_of("pyannote-community-1").stages}
    assert shapes["normalisation"] == "signal 16 000 Hz, 1 canal"
    assert shapes["segmentation_neuronale"] == "fenêtres de 10 s, 3 locuteurs locaux"
    assert shapes["empreintes"] == "vecteurs de dimension 256"
    ecapa = {stage.id: stage.shape for stage in page_of("baseline-ecapa").stages}
    assert ecapa["representation"] == "vecteurs de dimension 192"
    assert ecapa["analyse"] == "trames de 0,025 s tous les 0,01 s, 20 MFCC"


def test_forme_generique_et_ecart_signale_si_un_reglage_manque():
    page = page_of("baseline-mfcc")      # pas d'empreinte neuronale : aucune dimension consignée
    representation = next(stage for stage in page.stages if stage.id == "representation")
    assert representation.shape == "un vecteur par fenêtre"
    assert any("empreintes.dimension absent" in gap for gap in page.shape_gaps)
    assert "Formes des données : " in pipeline.render(page)


def test_modeles_du_catalogue_ne_renvoient_qu_a_des_reglages_connus():
    """Aucune valeur écrite à la main : chaque {réglage} est un réglage du catalogue."""
    catalogue = load_catalogue()
    for engine, templates in catalogue["formes"].items():
        known = set(catalogue["communs"]) if engine == "communs" else set(catalogue["moteurs"][engine])
        for step, entry in templates.items():
            assert entry["generique"] and not re.search(r"\d", entry["modele"].replace("RTTM", "")), (engine, step)
            assert set(re.findall(r"\{([^{}]+)\}", entry["modele"])) <= known, (engine, step)


def test_formes_du_catalogue_de_ce_code_si_le_depot_n_en_a_pas(tmp_path):
    (tmp_path / "src" / "whospoke" / "pipelines").mkdir(parents=True)
    catalogue = load_catalogue()
    del catalogue["formes"]
    import yaml

    (tmp_path / pipeline.CATALOGUE_RELATIVE).write_text(yaml.safe_dump(catalogue, allow_unicode=True))
    (tmp_path / "experiments").symlink_to(REPO_ROOT / "experiments")
    page = pipeline.load_page(moteurs.SPECS["pyannote-community-1"], tmp_path)
    assert page.stages[0].shape.startswith("signal") and not page.shape_gaps


# --- Schéma ---------------------------------------------------------------------------------


def test_schema_en_onglets_accessibles():
    html = pipeline.render(page_of("pyannote-community-1"))
    assert html.count('role="tablist"') == 1 and '<svg class="pl-diagram" role="none"' in html
    tabs = re.findall(r'<g class="pl-node" role="tab" id="pl-tab-([a-z_]+)" data-stage="\1" '
                      r'aria-selected="(true|false)" aria-controls="pl-sheet-\1" tabindex="(0|-1)"', html)
    assert [t[0] for t in tabs] == ["normalisation", "segmentation_neuronale", "empreintes", "regroupement",
                                    "sortie", "evaluation"]
    assert [t[1] for t in tabs].count("true") == 1 and [t[2] for t in tabs].count("0") == 1
    for stage, *_ in tabs:
        assert f'id="pl-sheet-{stage}" role="tabpanel" aria-labelledby="pl-tab-{stage}"' in html
    for key in ("ArrowRight:", "ArrowLeft:", "Home:", "End:", "aria-selected", "tabindex"):
        assert key in JS


def test_anatomie_d_une_etape():
    html = pipeline.render(page_of("baseline-ecapa"))
    node = re.search(r'<g class="pl-node" role="tab" id="pl-tab-representation".*?</g>', html).group(0)
    assert 'class="pl-num-text"' in node and ">6</text>" in node                     # numéro
    assert "Représentation" in node and "ECAPA_TDNN" in node and ">0f99f2d</text>" in node   # modèle, révision
    assert 'class="pl-pv-ink"' in node                                                # aperçu
    assert 'class="pl-n-badge"' in node and "confusion" in node                       # badge en texte


def test_un_seul_reseau_pour_pyannote_etapes_separees_pour_la_baseline():
    pyannote = pipeline.render(page_of("pyannote-community-1"))
    assert pyannote.count('class="pl-frame"') == 1 and "Un seul réseau : PyanNet" in pyannote
    baseline = pipeline.render(page_of("baseline-ecapa"))
    assert 'class="pl-frame"' not in baseline
    assert re.findall(r'id="pl-tab-([a-z_]+)"', baseline)[3:5] == ["detection", "segmentation"]


def test_evaluation_detachee_et_fleche_pointillee():
    html = pipeline.render(page_of("pyannote-community-1"))
    assert html.count('class="pl-sep-line"') == 1 and 'class="pl-arrow pl-arrow-dash"' in html
    assert 'class="pl-box pl-box-eval"' in html and "mesure seulement" in html


def test_couleurs_des_locuteurs_seulement_en_segmentation_et_regroupement():
    for key in ("pyannote-community-1", "baseline-ecapa"):
        html = pipeline.render(page_of(key))
        for stage, content in re.findall(r'<g class="pl-node" role="tab" id="pl-tab-([a-z_]+)".*?>(.*?)</g>', html):
            if "pl-spk-" in content:
                assert stage in ("segmentation_neuronale", "segmentation", "regroupement"), (key, stage)


# --- Naissance des erreurs -------------------------------------------------------------------


def test_barre_de_la_naissance_des_erreurs():
    page = page_of("baseline-ecapa")
    html = pipeline.render(page)
    data = page.errors
    assert data["exp"] == "EXP-0012" and data["der"] == pytest.approx(sum(data["composantes"].values()), abs=0.02)
    segments = re.findall(r'class="pl-errseg pl-err-([a-z_]+)" style="flex-grow: ([\d.]+)" data-stage="([a-z_]+)"', html)
    # Confusion : empreintes (ici la représentation) sélectionnées, regroupement mis en évidence
    # (retour du cockpit sur B12, constat C05).
    assert [(k, s) for k, _, s in segments] == [("manquee", "detection"), ("fausse_alarme", "detection"),
                                                ("confusion", "representation")]
    assert 'data-stage="representation" aria-controls="pl-sheet-representation" data-also="regroupement"' in html
    assert "→ Représentation et regroupement" in html and "dataset.also" in JS and "pl-also" in JS
    assert float(segments[0][1]) == pytest.approx(data["composantes"]["manquee"])
    assert "Attribution simplifiée" in html and "pl-errseg[data-stage]" in JS
    pyannote = pipeline.render(page_of("pyannote-community-1"))
    assert 'data-stage="segmentation_neuronale" aria-controls="pl-sheet-segmentation_neuronale"' in pyannote
    assert "→ Détection de parole" in pyannote       # l'étape du bloc où l'erreur naît
    assert "→ Empreintes vocales et regroupement" in pyannote
    assert 'data-stage="empreintes" aria-controls="pl-sheet-empreintes" data-also="regroupement"' in pyannote


# --- Petit écran et mode présentation ---------------------------------------------------------


def test_stepper_pour_petit_ecran():
    html = pipeline.render(page_of("baseline-ecapa"))
    stepper = html[html.index('<ol class="pl-stepper"'):]
    assert stepper.count('class="pl-st-toggle" aria-expanded="false"') == 10      # 9 étapes et l'Évaluation
    assert stepper.count(" hidden>") == 10 and '<dl class="pl-kv">' in stepper
    assert "↓</span> fenêtres de 1,5 s" in stepper
    narrow = CSS[CSS.index(".pl-stepper { display: none;"):]
    assert ".pl-diagram-wrap, .pl-sheets { display: none; }" in narrow and ".pl-stepper { display: block; }" in narrow
    assert "pl-st-toggle" in JS


def test_mode_presentation():
    for rule in ("html.ws-presentation .pl-n-rev, html.ws-presentation .pl-rev { display: none; }",
                 "html.ws-presentation .pl-errors { order: -1; }", "html.ws-presentation .pl-n-title { font-size: 12.5px; }"):
        assert rule in CSS
    assert pipeline.FONT["title"] >= 12.5        # texte coupé pour les tailles du mode présentation


# --- Retours de B11 ----------------------------------------------------------------------------


def test_prechauffage_visible_en_presentation_et_details_gardes_ouverts():
    assert "html.ws-presentation .ws-badge:not(.ws-engines) { display: none !important; }" in CSS
    assert "event.target.matches('details.ws-details')" in interface.DETAILS_JS
    assert "watch('value'" in interface.DETAILS_JS
