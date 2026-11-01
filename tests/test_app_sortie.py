"""Statistiques, renommage, exports et DER de l'onglet « Analyse » (D17, app/sortie.py)."""

import json

import numpy as np
import pytest
from pyannote.core import Annotation, Segment

from app import sortie
from whospoke.experiment import load_rttm


def annotation(turns, uri="essai"):
    result = Annotation(uri=uri)
    for index, (start, end, label) in enumerate(turns):
        result[Segment(start, end), index] = label
    return result


# B commence avant A : l'ordre des locuteurs est celui de leur première prise de parole.
HYP = annotation([(1.0, 4.0, "SPK_01"), (5.0, 6.0, "SPK_01"), (0.0, 2.0, "SPK_00"), (3.0, 8.0, "SPK_00")])


def test_ordre_de_premiere_prise_de_parole():
    assert sortie.speaker_labels(HYP) == ["SPK_00", "SPK_01"]


def test_statistiques_par_locuteur():
    stats = {row["id"]: row for row in sortie.speaker_stats(HYP)}
    # SPK_00 : [0, 2] ∪ [3, 8] = 7 s, 2 interventions ; recouvert par SPK_01 sur [1, 2], [3, 4], [5, 6].
    assert stats["SPK_00"]["temps_parole_s"] == pytest.approx(7.0)
    assert stats["SPK_00"]["n_interventions"] == 2
    assert stats["SPK_00"]["part_chevauchement"] == pytest.approx(3.0 / 7.0, abs=1e-4)
    # SPK_01 : [1, 4] ∪ [5, 6] = 4 s, recouvert sur [1, 2], [3, 4], [5, 6] = 3 s.
    assert stats["SPK_01"]["temps_parole_s"] == pytest.approx(4.0)
    assert stats["SPK_01"]["n_interventions"] == 2
    assert stats["SPK_01"]["part_chevauchement"] == pytest.approx(0.75)


def test_segments_contigus_d_un_meme_locuteur_forment_une_intervention():
    stats = sortie.speaker_stats(annotation([(0.0, 2.0, "A"), (2.0, 3.0, "A"), (5.0, 6.0, "A")]))
    assert stats[0]["n_interventions"] == 2
    assert stats[0]["part_chevauchement"] == 0.0


def test_renommage_nom_vide_et_doublon():
    names = sortie.resolve_names(["SPK_00", "SPK_01"], {"SPK_00": "  Alice ", "SPK_01": ""})
    assert names == {"SPK_00": "Alice", "SPK_01": "SPK_01"}
    with pytest.raises(ValueError, match="double"):
        sortie.resolve_names(["SPK_00", "SPK_01"], {"SPK_00": "Alice", "SPK_01": "Alice"})
    # « Jean Dupont » et « Jean_Dupont » donneraient le même locuteur RTTM.
    with pytest.raises(ValueError, match="double"):
        sortie.resolve_names(["A", "B"], {"A": "Jean Dupont", "B": "Jean_Dupont"})


def test_export_rttm_avec_noms(tmp_path):
    text = sortie.to_rttm(HYP, "essai", {"SPK_00": "Jean Dupont"})
    path = tmp_path / "essai.rttm"
    path.write_text(text)
    loaded = load_rttm(path, "essai")
    assert sorted(loaded.labels()) == ["Jean_Dupont", "SPK_01"]
    assert loaded.label_duration("Jean_Dupont") == pytest.approx(HYP.label_duration("SPK_00"))
    assert all(line.split()[0] == "SPEAKER" and len(line.split()) == 10 for line in text.splitlines())


def test_export_json_au_format_convenu():
    data = sortie.to_json(HYP, "essai", 10.0, "baseline-mfcc", {"device": "cpu"}, 1.5, {"SPK_01": "Bob"})
    assert list(data) == ["uri", "duree_s", "moteur", "configuration", "temps_calcul_s", "locuteurs", "segments"]
    assert list(data["locuteurs"][0]) == ["id", "nom", "temps_parole_s", "n_interventions", "part_chevauchement"]
    assert [s["nom"] for s in data["locuteurs"]] == ["SPK_00", "Bob"]
    # Les segments gardent l'identifiant du moteur, triés par début.
    assert data["segments"][0] == {"debut": 0.0, "fin": 2.0, "locuteur": "SPK_00"}
    assert [s["debut"] for s in data["segments"]] == sorted(s["debut"] for s in data["segments"])
    json.dumps(data)


def test_enveloppe_de_la_forme_d_onde():
    y = np.zeros(16000, dtype=np.float32)
    y[8000] = -0.5
    values = sortie.peaks(y, n_points=100)
    assert len(values) == 100
    assert max(values) == 1.0 and values[50] == 1.0 and values[0] == 0.0
    assert sortie.peaks(np.zeros(10), n_points=100) == [0.0] * 10
    assert sortie.peaks(np.zeros(0)) == []


def test_der_nul_pour_une_hypothese_identique():
    report = sortie.der_report(HYP, HYP, duration_s=10.0)
    for condition in ("collar_0", "collar_0_25"):
        assert report[condition]["der"] == pytest.approx(0.0)
    assert report["n_locuteurs"] == {"reference": 2, "hypothese": 2}


def test_der_decompose_et_reference_coupee_a_l_audio():
    reference = annotation([(0.0, 4.0, "A"), (4.0, 8.0, "B"), (20.0, 30.0, "C")])
    hypothesis = annotation([(0.0, 8.0, "X")])
    report = sortie.der_report(reference, hypothesis, duration_s=10.0)
    # C, au-delà de l'audio analysé, est ignoré : seule reste la confusion sur B.
    assert report["collar_0"]["manquee"] == pytest.approx(0.0)
    assert report["collar_0"]["confusion"] == pytest.approx(50.0)
    assert report["n_locuteurs"] == {"reference": 2, "hypothese": 1}


def test_lecture_d_une_reference(tmp_path):
    path = tmp_path / "ref.rttm"
    path.write_text("SPEAKER f1 1 0.0 1.0 <NA> <NA> A <NA> <NA>\nSPEAKER f1 1 1.0 1.0 <NA> <NA> B <NA> <NA>\n")
    assert sorted(sortie.read_reference(path).labels()) == ["A", "B"]
    path.write_text("SPEAKER f1 1 0.0 1.0 <NA> <NA> A <NA> <NA>\nSPEAKER f2 1 1.0 1.0 <NA> <NA> B <NA> <NA>\n")
    with pytest.raises(ValueError, match="plusieurs"):
        sortie.read_reference(path)
    path.write_text("")
    with pytest.raises(ValueError, match="aucune"):
        sortie.read_reference(path)


# --- Carte des erreurs (D26, chantier I4) -----------------------------------------------


def assert_same_as_der(reference, hypothesis, duration):
    """Les durées de la carte, sans collar, redonnent exactement les composantes du DER."""
    errors = sortie.error_map(reference, hypothesis, duration)
    der = sortie.der_report(reference, hypothesis, duration)["collar_0"]
    totals = errors["totaux"]
    assert totals["manquee"] == der["manquee_s"]
    assert totals["fausse_alarme"] == der["fausse_alarme_s"]
    assert totals["confusion"] == der["confusion_s"]
    assert totals["reference"] == der["duree_reference_s"]
    return errors, der


def test_carte_des_erreurs_cas_construit():
    # A parle 0–4, B 3–8 (chevauchement 3–4) ; l'hypothèse ne voit qu'un locuteur X sur
    # 0–6, puis Y sur 7–10 (B jusqu'à 8, puis silence de référence).
    reference = annotation([(0.0, 4.0, "A"), (3.0, 8.0, "B")], uri="ref")
    hypothesis = annotation([(0.0, 6.0, "X"), (7.0, 10.0, "Y")])
    errors, der = assert_same_as_der(reference, hypothesis, 12.0)
    totals = errors["totaux"]
    # Appariement optimal : X↔A (4 s communes), Y↔B (1 s commune).
    # Manquée : B pendant le chevauchement 3–4 (X n'en couvre qu'un) et B sur 6–7 ; fausse
    # alarme : Y sur 8–10 ; confusion : X attribué à A pendant que seul B parle (4–6).
    assert totals["manquee"] == pytest.approx(2.0)
    assert totals["fausse_alarme"] == pytest.approx(2.0)
    assert totals["confusion"] == pytest.approx(2.0)
    kinds = {(z["type"], z["debut"], z["fin"]) for z in errors["zones"]}
    assert ("confusion", 4.0, 6.0) in kinds and ("fausse_alarme", 8.0, 10.0) in kinds
    confusion = next(z for z in errors["zones"] if z["type"] == "confusion")
    assert confusion["reference"] == "B" and confusion["hypothese"] == "X"   # noms d'origine


def test_carte_vide_pour_une_hypothese_parfaite():
    errors, _ = assert_same_as_der(HYP, HYP, 10.0)
    assert errors["zones"] == []


def test_carte_des_erreurs_annotations_aleatoires():
    rng = np.random.default_rng(0)
    for case in range(25):
        def random_annotation(labels, uri):
            turns = []
            for _ in range(int(rng.integers(3, 12))):
                start = float(np.round(rng.uniform(0, 55), 3))
                turns.append((start, round(start + float(rng.uniform(0.2, 8)), 3), str(rng.choice(labels))))
            return annotation(turns, uri=uri)
        reference = random_annotation(["A", "B", "C"], "ref")
        hypothesis = random_annotation(["S0", "S1", "S2", "S3"], "hyp")
        assert_same_as_der(reference, hypothesis, 50.0)        # la référence déborde : coupée
