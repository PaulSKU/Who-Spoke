"""Tests obligatoires du protocole d'évaluation (docs/protocole-eval.md §6).

Ces tests ne sont jamais désactivés (CLAUDE.md, règle 10).
"""

import pytest
from pyannote.core import Annotation, Segment, Timeline
from pyannote.metrics.diarization import DiarizationErrorRate

from whospoke.evaluation.metrics import CONDITIONS, DiarizationEvaluator


def make_annotation(segments, uri="fichier"):
    """Construit une annotation à partir de triplets (début, fin, locuteur)."""
    annotation = Annotation(uri=uri)
    for i, (start, end, speaker) in enumerate(segments):
        annotation[Segment(start, end), i] = speaker
    return annotation


def make_uem(start, end):
    return Timeline([Segment(start, end)])


def test_identite():
    """Hypothèse égale à la référence, étiquettes renommées : DER = 0, JER = 0."""
    ref = make_annotation([(0, 5, "A"), (5, 9, "B"), (9, 15, "C"), (12, 14, "A")])
    hyp = make_annotation([(0, 5, "s1"), (5, 9, "s2"), (9, 15, "s3"), (12, 14, "s1")])
    result = DiarizationEvaluator().add(ref, hyp, uem=make_uem(0, 15))
    for condition in CONDITIONS:
        assert result[condition]["der"] == pytest.approx(0.0)
        assert result[condition]["jer"] == pytest.approx(0.0)


def test_appariement():
    """Deux locuteurs dont les étiquettes sont permutées : DER = 0."""
    ref = make_annotation([(0, 4, "A"), (4, 10, "B"), (10, 13, "A")])
    hyp = make_annotation([(0, 4, "B"), (4, 10, "A"), (10, 13, "B")])
    result = DiarizationEvaluator().add(ref, hyp, uem=make_uem(0, 13))
    for condition in CONDITIONS:
        assert result[condition]["der"] == pytest.approx(0.0)


def test_silence():
    """Hypothèse vide : DER = 100 %, entièrement en parole manquée."""
    ref = make_annotation([(0, 6, "A"), (6, 10, "B")])
    hyp = Annotation(uri="fichier")
    result = DiarizationEvaluator().add(ref, hyp, uem=make_uem(0, 10))
    for condition in CONDITIONS:
        assert result[condition]["der"] == pytest.approx(100.0)
        assert result[condition]["manquee"] == pytest.approx(100.0)
        assert result[condition]["fausse_alarme"] == pytest.approx(0.0)
        assert result[condition]["confusion"] == pytest.approx(0.0)


def test_collar():
    """Frontières de l'hypothèse décalées de 0,2 s : DER > 0 en collar_0, DER = 0 en collar_0_25.

    Vérifie aussi que `collar` est une largeur totale (moitié de chaque côté) :
    collar=0.3 (±0,15 s) ne suffit pas à absorber un décalage de 0,2 s, alors qu'un
    collar appliqué de chaque côté l'absorberait.
    """
    ref = make_annotation([(0, 10, "A"), (10, 20, "B")])
    hyp = make_annotation([(0.2, 10.2, "A"), (10.2, 20.2, "B")])
    uem = make_uem(0, 21)

    result = DiarizationEvaluator().add(ref, hyp, uem=uem)
    assert CONDITIONS["collar_0_25"] == 0.5
    assert result["collar_0"]["der"] > 0.0
    assert result["collar_0"]["manquee_s"] == pytest.approx(0.2)
    assert result["collar_0"]["confusion_s"] == pytest.approx(0.2)
    assert result["collar_0"]["fausse_alarme_s"] == pytest.approx(0.2)
    assert result["collar_0_25"]["der"] == pytest.approx(0.0)

    # Sémantique « largeur totale » : seuil de nullité du DER à collar = 2 × 0,2 = 0,4 s.
    def der(collar):
        return DiarizationErrorRate(collar=collar, skip_overlap=False)(ref, hyp, uem=uem)

    assert der(0.3) > 0.0
    assert der(0.4) == pytest.approx(0.0)


def test_chevauchement():
    """Référence avec 2 s de chevauchement, hypothèse à un seul locuteur sur cette zone :
    2 s de parole manquée exactement."""
    ref = make_annotation([(0, 10, "A"), (8, 12, "B")])
    hyp = make_annotation([(0, 10, "s1"), (10, 12, "s2")])
    result = DiarizationEvaluator().add(ref, hyp, uem=make_uem(0, 12))
    collar_0 = result["collar_0"]
    assert collar_0["manquee_s"] == pytest.approx(2.0)
    assert collar_0["fausse_alarme_s"] == pytest.approx(0.0)
    assert collar_0["confusion_s"] == pytest.approx(0.0)
    assert collar_0["duree_reference_s"] == pytest.approx(14.0)


def test_agregation():
    """Deux fichiers de durées très différentes : le DER global égale le rapport des sommes,
    pas la moyenne des DER."""
    evaluator = DiarizationEvaluator()
    court = evaluator.add(
        make_annotation([(0, 10, "A")], uri="court"),
        Annotation(uri="court"),
        uem=make_uem(0, 10),
    )
    long = evaluator.add(
        make_annotation([(0, 1000, "A")], uri="long"),
        make_annotation([(0, 1000, "s1")], uri="long"),
        uem=make_uem(0, 1000),
    )
    global_der = evaluator.report()["collar_0"]["der"]

    moyenne = (court["collar_0"]["der"] + long["collar_0"]["der"]) / 2
    rapport_des_sommes = 100.0 * 10.0 / 1010.0
    assert moyenne == pytest.approx(50.0)
    assert global_der == pytest.approx(rapport_des_sommes)
    assert global_der != pytest.approx(moyenne)
