"""Comparaison de deux moteurs (D26, chantier I5 ; app/app.py), sans modèle : résultats
fabriqués, comme les produit l'analyse en mode factice."""

import json
from pathlib import Path

import pytest
from pyannote.core import Annotation, Segment

from app import app as interface
from app import sortie


def annotation(turns, uri="essai"):
    result = Annotation(uri=uri)
    for index, (start, end, label) in enumerate(turns):
        result[Segment(start, end), index] = label
    return result


def engine_result(tmp_path, key, label, turns, calcul_s):
    return {
        "uri": "essai", "dir": tmp_path, "wav": tmp_path / "essai.wav", "duree_s": 12.0, "libelle": label,
        "moteur_cle": key, "annotation": annotation(turns), "names": {}, "moteur": f"factice ({key})",
        "configuration": {"experience_source": "EXP-0000", "peripherique": "cpu",
                          "nombre_locuteurs": {"mode": "automatique"}, "moteur_factice": True, "reglages": {}},
        "calcul_s": calcul_s, "normalisation_s": 0.1, "chargement_s": None,
        "durees_etapes": {"segmentation": calcul_s}, "device": "cpu", "factice": True,
        "rttm_source": "experiments/x.rttm", "rtf_mesure": None,
    }


@pytest.fixture
def reference(tmp_path):
    path = tmp_path / "ref.rttm"
    path.write_text("SPEAKER ref 1 0.0 4.0 <NA> <NA> A <NA> <NA>\n"
                    "SPEAKER ref 1 3.0 5.0 <NA> <NA> B <NA> <NA>\n"
                    "SPEAKER ref 1 20.0 2.0 <NA> <NA> C <NA> <NA>\n")   # au-delà de l'audio : coupé
    return str(path)


@pytest.fixture
def compared(tmp_path):
    first = engine_result(tmp_path, "pyannote-community-1", "pyannote community-1",
                          [(0.0, 4.0, "S0"), (4.0, 8.0, "S1")], 2.0)
    second = engine_result(tmp_path, "baseline-mfcc", "Baseline MFCC", [(0.0, 5.5, "SPK_00"), (7.0, 11.0, "SPK_01")], 0.5)
    return dict(first, peaks=[0.0], comparaison=second)


def test_un_seul_moteur_un_seul_groupe(tmp_path):
    result = dict(engine_result(tmp_path, "baseline-mfcc", "Baseline MFCC", [(0.0, 2.0, "S0")], 1.0), peaks=[0.0])
    value = interface._viewer_value(interface._with_reference(result, None))
    assert [g["id"] for g in value["groupes"]] == ["a"]
    assert value["groupes"][0]["locuteurs"][0]["couleur"] == interface.PALETTE_LIGHT[0]
    assert value["groupes"][0]["erreurs"] is None


def test_groupes_superposes_avec_reference_et_deux_cartes(compared, reference):
    value = interface._viewer_value(interface._with_reference(compared, reference))
    groups = {g["id"]: g for g in value["groupes"]}
    assert list(groups) == ["a", "b", "ref"]
    assert groups["b"]["titre"] == "Baseline MFCC" and groups["ref"]["titre"] == "Référence"
    # Premier moteur en couleurs ; second moteur et référence en gris neutre.
    assert groups["a"]["locuteurs"][0]["couleur"] == interface.PALETTE_LIGHT[0]
    assert {s["couleur"] for s in groups["b"]["locuteurs"] + groups["ref"]["locuteurs"]} == {interface.NEUTRAL_LIGHT}
    # Référence coupée à la durée de l'audio : C disparaît.
    assert [s["id"] for s in groups["ref"]["locuteurs"]] == ["A", "B"]
    assert groups["a"]["erreurs"] and groups["b"]["erreurs"] and groups["ref"]["erreurs"] is None
    # Chaque carte égale les composantes du DER de son moteur.
    for key, item in (("a", compared), ("b", compared["comparaison"])):
        der = sortie.der_report(sortie.read_reference(reference), item["annotation"], 12.0)["collar_0"]
        assert groups[key]["erreurs"]["totaux"]["confusion"] == der["confusion_s"]


def test_tableau_cote_a_cote(compared, reference):
    result = interface._with_reference(compared, reference)
    html = interface._comparison_html(result)
    for item in (compared, compared["comparaison"]):
        report = sortie.der_report(sortie.read_reference(reference), item["annotation"], 12.0)
        assert interface._pct(report["collar_0"]["der"], 2) in html
        assert interface._pct(report["collar_0_25"]["der"], 2) in html
    assert "pyannote community-1" in html and "Baseline MFCC" in html and "Référence" in html
    assert "2,00 s" in html and "0,50 s" in html                  # temps de calcul
    without = interface._comparison_html(interface._with_reference(compared, None))
    assert "Déposez une référence" in without and "—" in without
    assert interface._comparison_html(dict(compared, comparaison=None)) == ""


def test_exports_des_deux_resultats(compared):
    paths = [Path(p) for p in interface._exports(compared)]
    assert sorted(p.name for p in paths) == ["essai_baseline-mfcc.json", "essai_baseline-mfcc.rttm",
                                             "essai_pyannote-community-1.json", "essai_pyannote-community-1.rttm"]
    data = {p.name: json.loads(p.read_text()) for p in paths if p.suffix == ".json"}
    assert data["essai_baseline-mfcc.json"]["moteur"] == "factice (baseline-mfcc)"
    assert data["essai_pyannote-community-1.json"]["moteur"] == "factice (pyannote-community-1)"
    # Hors comparaison, le nom reste celui du fichier.
    single = [Path(p).name for p in interface._exports(dict(compared, comparaison=None))]
    assert sorted(single) == ["essai.json", "essai.rttm"]


def test_avancement_temps_et_der_des_deux_moteurs(compared, reference):
    steps = ["normalisation_audio", "1:chargement", "1:segmentation", "2:chargement", "2:analyse"]
    labels = {"1:segmentation": "pyannote community-1 : Segmentation locale",
              "2:analyse": "Baseline MFCC : Analyse"}
    html = interface._status_html(steps, {"1:segmentation": 1.0, "2:analyse": 0.5}, "En cours", labels=labels)
    assert "pyannote community-1 : Segmentation locale" in html and "Baseline MFCC : Analyse" in html
    assert "50 %" in html
    times = interface._times_all_html(interface._times_html, compared)
    assert times.count('class="ws-subtitle"') == 2 and "Baseline MFCC" in times
    result = interface._with_reference(compared, reference)
    der = interface._der_all_html(interface._der_html, result, reference)
    assert der.count("Sans collar (principale)") == 2
