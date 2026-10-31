"""Répartition des erreurs de A-0001 (D21 §2) sur des cas construits à la main."""

import importlib.util

import pytest
from pyannote.core import Annotation, Segment, Timeline

from whospoke.evaluation.metrics import DiarizationEvaluator
from whospoke.experiment import REPO_ROOT

spec = importlib.util.spec_from_file_location(
    "a0001", REPO_ROOT / "scripts" / "analyses" / "a0001_sensibilite_reference.py")
a0001 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a0001)


def annotation(*turns):
    result = Annotation(uri="f")
    for index, (start, end, label) in enumerate(turns):
        result[Segment(start, end), index] = label
    return result


def uem(start, end):
    return Timeline([Segment(start, end)], uri="f")


def check_against_pyannote(reference, hypothesis, zone, split):
    components = DiarizationEvaluator().add(reference, hypothesis, uem=zone)["collar_0"]
    a0001.check_split(split, components, "f")


# Référence : A 0–2, pause de A 0,5 s, A 2,5–4, pause vers B 0,8 s, B 4,8–6, silence de 2 s,
# A 8–9, puis bord de 1 s jusqu'à la fin de l'UEM (début : 0,5 s de bord avant le premier tour).
REFERENCE = annotation((0.5, 2.0, "A"), (2.5, 4.0, "A"), (4.8, 6.0, "B"), (8.0, 9.0, "A"))
ZONE = uem(0.0, 10.0)


def test_silences_classes():
    gaps = a0001.reference_gaps(REFERENCE, ZONE, pause_max_s=1.0)
    assert [(round(s, 3), round(e, 3), k) for s, e, k in gaps] == [
        (0.0, 0.5, "bords"), (2.0, 2.5, "pause_intra"), (4.0, 4.8, "pause_inter"),
        (6.0, 8.0, "silence_long"), (9.0, 10.0, "bords"),
    ]


def test_pause_d_une_seconde_exactement_incluse():
    reference = annotation((0.0, 1.0, "A"), (2.0, 3.0, "A"), (4.001, 5.0, "B"))
    gaps = a0001.reference_gaps(reference, uem(0.0, 5.0), pause_max_s=1.0)
    assert [k for _, _, k in gaps] == ["pause_intra", "silence_long"]


def test_fausse_alarme_par_categorie():
    hypothesis = annotation((0.0, 10.0, "X"))
    split = a0001.split_errors(REFERENCE, hypothesis, ZONE)
    assert split["fausse_alarme"] == pytest.approx(
        {"pause_intra": 0.5, "pause_inter": 0.8, "silence_long": 2.0, "bords": 1.5, "parole": 0.0})
    assert split["manquee"] == pytest.approx({"court": 0.0, "long": 0.0})
    assert split["pauses"]["pause_intra"] == pytest.approx((1, 0.5))
    assert split["pauses"]["pause_inter"] == pytest.approx((1, 0.8))
    check_against_pyannote(REFERENCE, hypothesis, ZONE, split)


def test_fausse_alarme_pendant_la_parole():
    # Deux locuteurs hypothèse pendant que seul A parle : 1 s de fausse alarme « parole ».
    reference = annotation((0.0, 2.0, "A"))
    hypothesis = annotation((0.0, 2.0, "X"), (1.0, 2.0, "Y"))
    split = a0001.split_errors(reference, hypothesis, uem(0.0, 2.0))
    assert split["fausse_alarme"]["parole"] == pytest.approx(1.0)
    assert sum(split["fausse_alarme"].values()) == pytest.approx(1.0)
    check_against_pyannote(reference, hypothesis, uem(0.0, 2.0), split)


def test_fausse_alarme_hors_uem_ignoree():
    reference = annotation((1.0, 2.0, "A"))
    hypothesis = annotation((0.0, 5.0, "X"))
    split = a0001.split_errors(reference, hypothesis, uem(0.5, 3.0))
    assert split["fausse_alarme"]["bords"] == pytest.approx(1.5)  # 0,5–1 et 2–3
    check_against_pyannote(reference, hypothesis, uem(0.5, 3.0), split)


def test_parole_manquee_tours_courts_et_longs():
    reference = annotation((0.0, 0.3, "A"), (1.0, 3.0, "B"), (3.5, 4.0, "A"))
    split = a0001.split_errors(reference, Annotation(uri="f"), uem(0.0, 4.0))
    # 0,5 s exactement n'est pas « moins de 0,5 s » : tour long.
    assert split["manquee"] == pytest.approx({"court": 0.3, "long": 2.5})
    assert split["tours"] == {"court": 1, "long": 2}
    check_against_pyannote(reference, Annotation(uri="f"), uem(0.0, 4.0), split)


def test_parole_manquee_en_chevauchement_partagee():
    # A 0–2 et B 1–1,4 (tour court) ; l'hypothèse n'a qu'un locuteur : 0,4 s manquée,
    # répartie à parts égales entre les deux tours actifs.
    reference = annotation((0.0, 2.0, "A"), (1.0, 1.4, "B"))
    hypothesis = annotation((0.0, 2.0, "X"))
    split = a0001.split_errors(reference, hypothesis, uem(0.0, 2.0))
    assert split["manquee"] == pytest.approx({"court": 0.2, "long": 0.2})
    check_against_pyannote(reference, hypothesis, uem(0.0, 2.0), split)


def test_controle_detecte_une_incoherence():
    split = {"fausse_alarme": {"bords": 1.0}, "manquee": {"long": 0.0}}
    with pytest.raises(RuntimeError, match="incohérente"):
        a0001.check_split(split, {"fausse_alarme_s": 2.0, "manquee_s": 0.0}, "f")
