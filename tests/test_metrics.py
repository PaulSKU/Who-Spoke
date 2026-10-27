"""Métriques complémentaires (protocole §3.2, §3.4, §4) sur des cas calculables à la main."""

import pytest
from pyannote.core import Annotation, Segment, Timeline

from whospoke.evaluation.metrics import (
    DiarizationEvaluator,
    bootstrap_der_ci,
    count_wins,
    overlap_zones,
    speaker_count_metrics,
)


def make_annotation(segments, uri="fichier"):
    annotation = Annotation(uri=uri)
    for i, (start, end, speaker) in enumerate(segments):
        annotation[Segment(start, end), i] = speaker
    return annotation


def make_uem(start, end):
    return Timeline([Segment(start, end)])


# --- Décomposition par zone (§3.2) --------------------------------------------------


def test_zones_construction():
    ref = make_annotation([(0, 10, "A"), (8, 12, "B")])
    zones = overlap_zones(ref, make_uem(0, 15))
    assert list(zones["chevauchement"]) == [Segment(8, 10)]
    assert list(zones["sans_chevauchement"]) == [Segment(0, 8), Segment(10, 15)]


def test_zones_erreur_localisee_dans_le_chevauchement():
    """Un seul locuteur produit sur 8–10 s, où A et B parlent.

    Zone de chevauchement : 4 s de référence (2 s × 2 locuteurs), 2 s manquées → 50 %.
    Zone sans chevauchement : A sur 0–8 s et B sur 10–12 s, parfaitement couverts → 0 %.
    """
    ref = make_annotation([(0, 10, "A"), (8, 12, "B")])
    hyp = make_annotation([(0, 10, "s1"), (10, 12, "s2")])
    evaluator = DiarizationEvaluator()
    result = evaluator.add(ref, hyp, uem=make_uem(0, 12))
    overlap = result["zones"]["chevauchement"]
    assert overlap["duree_reference_s"] == pytest.approx(4.0)
    assert overlap["manquee_s"] == pytest.approx(2.0)
    assert overlap["der"] == pytest.approx(50.0)
    assert result["zones"]["sans_chevauchement"]["der"] == pytest.approx(0.0)
    assert result["zones"]["sans_chevauchement"]["duree_reference_s"] == pytest.approx(10.0)
    report = evaluator.report()
    assert report["der_zones_chevauchement"] == pytest.approx(50.0)
    assert report["der_zones_sans_chevauchement"] == pytest.approx(0.0)


def test_zones_fausse_alarme_dans_le_silence_et_zone_vide():
    """Fausse alarme de 2 s dans un silence : comptée hors chevauchement (2/4 = 50 %)."""
    ref = make_annotation([(0, 4, "A")])
    hyp = make_annotation([(0, 6, "s1")])
    evaluator = DiarizationEvaluator()
    result = evaluator.add(ref, hyp, uem=make_uem(0, 10))
    assert result["zones"]["chevauchement"] is None
    assert result["zones"]["sans_chevauchement"]["fausse_alarme_s"] == pytest.approx(2.0)
    assert result["zones"]["sans_chevauchement"]["der"] == pytest.approx(50.0)
    report = evaluator.report()
    assert report["der_zones_chevauchement"] is None
    assert report["der_zones_sans_chevauchement"] == pytest.approx(50.0)


def test_zones_agregation_rapport_des_sommes():
    """Fichier 1 : chevauchement 4 s de référence, 2 s manquées. Fichier 2 : chevauchement
    6 s (3 s × 2), entièrement manqué. Global : (2 + 6) / (4 + 6) = 80 %, pas (50 + 100) / 2."""
    evaluator = DiarizationEvaluator()
    evaluator.add(
        make_annotation([(0, 10, "A"), (8, 12, "B")], uri="f1"),
        make_annotation([(0, 10, "s1"), (10, 12, "s2")], uri="f1"),
        uem=make_uem(0, 12),
    )
    evaluator.add(
        make_annotation([(0, 5, "A"), (2, 5, "B")], uri="f2"),
        make_annotation([(0, 2, "s1")], uri="f2"),
        uem=make_uem(0, 5),
    )
    assert evaluator.report()["der_zones_chevauchement"] == pytest.approx(80.0)


# --- Nombre de locuteurs (§3.4) -----------------------------------------------------


def test_nombre_locuteurs_formules():
    metrics = speaker_count_metrics([(4, 3), (2, 2), (3, 5)])
    assert metrics["erreur_absolue_moyenne"] == pytest.approx(1.0)  # (1 + 0 + 2) / 3
    assert metrics["taux_exact"] == pytest.approx(100.0 / 3)


def test_nombre_locuteurs_restreint_a_l_uem_et_poids_egal():
    evaluator = DiarizationEvaluator()
    # Fichier long : 2 locuteurs de référence, 3 en hypothèse dans l'UEM, un 4e hors UEM.
    result = evaluator.add(
        make_annotation([(0, 500, "A"), (500, 1000, "B")], uri="long"),
        make_annotation(
            [(0, 400, "s1"), (400, 500, "s3"), (500, 1000, "s2"), (1100, 1200, "s4")], uri="long"
        ),
        uem=make_uem(0, 1000),
    )
    assert result["n_locuteurs"] == {"reference": 2, "hypothese": 3}
    # Fichier court : nombre exact.
    evaluator.add(
        make_annotation([(0, 5, "A")], uri="court"),
        make_annotation([(0, 5, "s1")], uri="court"),
        uem=make_uem(0, 5),
    )
    metrics = evaluator.report()["n_locuteurs"]
    assert metrics["erreur_absolue_moyenne"] == pytest.approx(0.5)
    assert metrics["taux_exact"] == pytest.approx(50.0)


# --- Métriques par fichier ----------------------------------------------------------


def test_lignes_par_fichier():
    evaluator = DiarizationEvaluator()
    evaluator.add(
        make_annotation([(0, 10, "A"), (8, 12, "B")], uri="f1"),
        make_annotation([(0, 10, "s1"), (10, 12, "s2")], uri="f1"),
        uem=make_uem(0, 12),
    )
    evaluator.add(make_annotation([(0, 6, "A")], uri="f2"), Annotation(uri="f2"), uem=make_uem(0, 6))
    rows = evaluator.per_file()
    assert [row["uri"] for row in rows] == ["f1", "f2"]
    f1, f2 = rows
    assert f1["duree_reference_c0_s"] == pytest.approx(14.0)
    assert f1["manquee_c0_s"] == pytest.approx(2.0)
    assert f1["der_c0"] == pytest.approx(100.0 * 2 / 14)
    assert f1["der_chevauchement"] == pytest.approx(50.0)
    assert f1["erreur_n_locuteurs"] == 0
    assert f2["der_c0"] == pytest.approx(100.0)
    assert f2["der_chevauchement"] is None
    assert f2["n_locuteurs_hypothese"] == 0
    assert f2["erreur_n_locuteurs"] == -1


# --- Bootstrap et comparaison (§4) --------------------------------------------------


def test_bootstrap_der_constant():
    """Tous les fichiers ont un DER de 10 % : l'intervalle est réduit à 10 %."""
    ci = bootstrap_der_ci([1.0, 2.0, 3.0], [10.0, 20.0, 30.0])
    assert ci["estimation"] == pytest.approx(10.0)
    assert ci["borne_inf"] == pytest.approx(10.0)
    assert ci["borne_sup"] == pytest.approx(10.0)


def test_bootstrap_estimation_rapport_des_sommes_et_bornes():
    """Fichiers à 0 % (10 s) et 11,1 % (90 s) : estimation 10/100 = 10 %, intervalle inclus
    dans [0 ; 11,1] et contenant l'estimation."""
    ci = bootstrap_der_ci([0.0, 10.0], [10.0, 90.0])
    assert ci["estimation"] == pytest.approx(10.0)
    assert 0.0 <= ci["borne_inf"] <= 10.0 <= ci["borne_sup"] <= 100.0 * 10 / 90 + 1e-9


def test_bootstrap_graine_fixee_reproductible():
    errors, totals = [1.0, 5.0, 2.0, 8.0, 0.5], [10.0, 20.0, 15.0, 30.0, 5.0]
    assert bootstrap_der_ci(errors, totals, seed=0) == bootstrap_der_ci(errors, totals, seed=0)
    assert bootstrap_der_ci(errors, totals, seed=0) != bootstrap_der_ci(errors, totals, seed=1)


def test_bootstrap_difference_appariee():
    errors, totals = [1.0, 5.0, 2.0], [10.0, 20.0, 15.0]
    same = bootstrap_der_ci(errors, totals, errors, totals)
    assert same == {"estimation": 0.0, "borne_inf": 0.0, "borne_sup": 0.0}
    # b fait exactement 1 s d'erreur de moins sur chaque fichier de 10 s : écart constant 10 points.
    shifted = bootstrap_der_ci([2.0, 3.0], [10.0, 10.0], [1.0, 2.0], [10.0, 10.0])
    assert shifted["estimation"] == pytest.approx(10.0)
    assert shifted["borne_inf"] == pytest.approx(10.0)
    assert shifted["borne_sup"] == pytest.approx(10.0)
    with pytest.raises(ValueError):
        bootstrap_der_ci([1.0], [10.0], [1.0, 2.0], [10.0, 10.0])


def test_count_wins():
    assert count_wins([10, 20, 30, 5], [12, 20, 25, 6]) == {
        "a_meilleur": 2,
        "b_meilleur": 1,
        "egalite": 1,
    }
