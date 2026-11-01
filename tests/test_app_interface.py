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


def test_der_dans_les_deux_conditions_avec_mention_sans_uem(tmp_path):
    from pyannote.core import Annotation, Segment

    hypothesis = Annotation(uri="essai")
    hypothesis[Segment(0.0, 4.0)] = "SPK_00"
    hypothesis[Segment(4.0, 8.0)] = "SPK_01"
    reference = tmp_path / "ref.rttm"
    reference.write_text("SPEAKER ref 1 0.0 4.0 <NA> <NA> A <NA> <NA>\n"
                         "SPEAKER ref 1 4.0 4.0 <NA> <NA> B <NA> <NA>\n")
    html = interface._der_html({"annotation": hypothesis, "duree_s": 10.0}, str(reference))
    assert "Durée entière du fichier, sans UEM : non comparable aux résultats sur corpus." in html
    assert "Sans collar (principale)" in html and "Collar ± 0,25 s" in html
    assert "0,00 %" in html


def test_visualiseur_avec_zoom():
    template = interface.VIEWER_TEMPLATE
    for name in ("wsp-zoom-in", "wsp-zoom-out", "wsp-zoom-range", "wsp-zoom-fit"):
        assert name in template
    script = (interface.STATIC_DIR / "visualiseur.js").read_text()
    assert "ws.zoom(" in script and "setScroll" in script


def test_forme_d_onde_neutre_seul_le_segment_selectionne():
    """D26, « Couleurs » : aucune teinte par locuteur sur la forme d'onde ; une seule
    bande, d'encre, pour le segment sélectionné."""
    script = (interface.STATIC_DIR / "visualiseur.js").read_text()
    assert script.count("addRegion(") == 1
    region = script[script.index("addRegion("):script.index("addRegion(") + 200]
    assert "_colors" not in region and "couleur" not in region
    assert "function selectSegment" in script and "aria-pressed" in script


def test_carte_des_erreurs_affiche_les_nombres_du_der(tmp_path):
    """Les totaux de la carte, formatés pour l'écran, sont ceux du tableau du DER sans collar."""
    from pyannote.core import Annotation, Segment

    hypothesis = Annotation(uri="essai")
    hypothesis[Segment(0.0, 5.5)] = "X"
    hypothesis[Segment(7.0, 11.0)] = "Y"
    reference = tmp_path / "ref.rttm"
    reference.write_text("SPEAKER ref 1 0.0 4.0 <NA> <NA> A <NA> <NA>\n"
                         "SPEAKER ref 1 3.0 5.0 <NA> <NA> B <NA> <NA>\n")
    result = {"annotation": hypothesis, "duree_s": 12.0, "names": {}}
    errors = interface._error_map(result, str(reference))
    import re

    der_row = interface._der_html(result, str(reference)).split("Sans collar (principale)")[1].split("</tr>")[0]
    cells = re.findall(r'<td class="num[^"]*">([^<]+)</td>', der_row)   # DER, manquée, FA, confusion, JER
    # Manquée 2,5 s, fausse alarme 3 s, confusion 1,5 s, sur 9 s de parole de référence
    # (A 4 s et B 5 s : le chevauchement 3–4 compte pour chacun).
    assert [row["part"] for row in errors["rangees"]] == cells[1:4] == ["27,78 %", "33,33 %", "16,67 %"]
    assert [row["duree"] for row in errors["rangees"]] == ["2,50 s", "3,00 s", "1,50 s"]
    assert [row["libelle"] for row in errors["rangees"]] == ["Parole manquée", "Fausse alarme", "Confusion"]
    assert interface._error_map(result, None) is None
    assert "wsp-errsum" in interface.VIEWER_TEMPLATE
    script = (interface.STATIC_DIR / "visualiseur.js").read_text()
    assert "function drawErrors" in script and "selectSegment(bar._seg)" in script
    assert "selectables(v).some(isSelected)" in script
    # La carte est sans collar seulement, et l'écran le dit à côté d'elle (légende et totaux).
    assert "const title = 'Erreurs sans collar'" in script
    assert script.count("erreurs sans collar : ") + script.count("Erreurs sans collar : ") >= 2   # une zone d'erreur se repère aussi sur la forme d'onde
