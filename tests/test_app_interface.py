"""Construction de l'onglet « Analyse » (D17, app/app.py), sans lancer de serveur ni de modèle."""

import os

from app import app as interface


def test_telemetrie_de_gradio_desactivee():
    assert os.environ["GRADIO_ANALYTICS_ENABLED"] == "False"


def test_construction_en_mode_factice():
    blocks = interface.build_app(fake=True)
    assert blocks.title == "Who Spoke?"


def test_bibliotheques_javascript_embarquees():
    for name in ("wavesurfer.min.js", "regions.min.js", "LICENSE"):
        assert (interface.WAVESURFER_DIR / name).is_file()
    for path in interface.STATIC_DIR.rglob("*.js"):
        assert "http://" not in path.read_text() and "https://" not in path.read_text(), path


def test_noms_saisis_echappes_dans_les_tableaux():
    from pyannote.core import Annotation, Segment

    annotation = Annotation(uri="essai")
    annotation[Segment(0.0, 2.0)] = "SPK_00"
    result = {"annotation": annotation, "names": {"SPK_00": "<b>Alice</b>"}}
    html = interface._stats_html(result)
    assert "&lt;b&gt;Alice&lt;/b&gt;" in html and "<b>Alice</b>" not in html


def test_couleurs_en_ordre_fixe_puis_gris():
    colors = interface._speaker_colors([f"S{i}" for i in range(10)])
    assert colors["S0"] == (interface.PALETTE_LIGHT[0], interface.PALETTE_DARK[0])
    assert colors["S8"] == colors["S9"] == (interface.OTHER_LIGHT, interface.OTHER_DARK)


def test_etat_d_avancement():
    html = interface._status_html(["analyse", "detection", "attribution"],
                                  {"analyse": 1.0, "detection": 0.5}, "En cours", fraction=0.5)
    # L'état de chaque étape est écrit en toutes lettres, pas porté par la seule couleur.
    assert "terminé" in html and "50 %" in html and "en attente" in html and "Détection de parole" in html
    assert 'aria-live="polite"' in html and 'aria-valuenow="50"' in html
    assert interface._step_fraction(["analyse", "detection"], {"analyse": 1.0, "detection": 0.5}) == 0.75
