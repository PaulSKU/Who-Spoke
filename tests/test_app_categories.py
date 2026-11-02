"""Catégories des erreurs (décisions du cockpit du 02/11 : ordre de priorité, puis option b ;
app/sortie.py) : sur le temps, la partie dans ±0,25 s d'une frontière de tour de la référence
en « décalage de frontière », le reste selon l'ordre de priorité ; une seule définition."""

from pathlib import Path

import numpy as np
import pytest
from pyannote.core import Annotation, Segment

from app import app as interface
from app import sortie


def annotation(turns, uri="essai"):
    result = Annotation(uri=uri)
    for start, end, label in turns:
        result[Segment(start, end)] = label
    return result


def error_seconds(report: dict) -> float:
    return report["manquee_s"] + report["fausse_alarme_s"] + report["confusion_s"]


def categories_of(reference, hypothesis, duration):
    errors = sortie.error_map(reference, hypothesis, duration)
    return errors, {(z["type"], z["debut"], z["fin"]): z["categorie"] for z in errors["zones"]}


def test_categories_somment_aux_composantes_du_der_sans_collar():
    """Partition : chaque segment d'erreur dans une seule catégorie ; les sommes redonnent les
    composantes du DER sans collar (à l'arrondi de l'ordre des additions près, < 1e-12 s)."""
    rng = np.random.default_rng(0)
    seen = set()
    for _ in range(60):
        def random_annotation(labels, uri):
            turns = []
            for _ in range(int(rng.integers(3, 14))):
                start = float(np.round(rng.uniform(0, 55), 3))
                turns.append((start, round(start + float(rng.uniform(0.1, 8)), 3), str(rng.choice(labels))))
            return annotation(turns, uri=uri)
        reference = random_annotation(["A", "B", "C"], "ref")
        hypothesis = random_annotation(["S0", "S1", "S2", "S3"], "hyp")
        errors = sortie.error_map(reference, hypothesis, 50.0)
        der = sortie.der_report(reference, hypothesis, 50.0)["collar_0"]
        for kind, key in (("manquee", "manquee_s"), ("fausse_alarme", "fausse_alarme_s"),
                          ("confusion", "confusion_s")):
            by_category = errors["categories"][kind]
            assert list(by_category) == list(sortie.ERROR_CATEGORIES)
            assert sum(by_category.values()) == pytest.approx(der[key], abs=1e-12)
            assert errors["totaux"][kind] == der[key]                 # inchangé : égalité stricte
        for zone in errors["zones"]:
            assert zone["categorie"] in sortie.ERROR_CATEGORIES
            seen.add(zone["categorie"])
    # Toutes les catégories sont atteintes, « tour court » compris (seuil de 1 s : un tour de
    # 0,5 à 1 s garde une partie centrale hors tolérance ; D28, amendement du 02/11).
    assert seen == set(sortie.ERROR_CATEGORIES)


def test_egalite_stricte_sur_des_durees_exactes():
    # Durées en multiples de 1/8 s, exactes en binaire : pas d'arrondi, égalité stricte.
    reference = annotation([(0.0, 4.0, "A"), (3.0, 8.0, "B"), (9.0, 9.375, "C"), (9.375, 12.0, "A")])
    hypothesis = annotation([(0.125, 6.0, "X"), (7.0, 10.0, "Y"), (13.0, 14.5, "Z")])
    errors = sortie.error_map(reference, hypothesis, 16.0)
    der = sortie.der_report(reference, hypothesis, 16.0)["collar_0"]
    for kind, key in (("manquee", "manquee_s"), ("fausse_alarme", "fausse_alarme_s"), ("confusion", "confusion_s")):
        assert sum(errors["categories"][kind].values()) == der[key]


def test_ordre_de_priorite():
    # A 0–10, B 8–20 (chevauchement 8–10) ; C 22–24 sans locuteur trouvé ; pause de 0,8 s 30–30,8.
    reference = annotation([(0.0, 10.0, "A"), (8.0, 20.0, "B"), (22.0, 24.0, "C"),
                            (26.0, 30.0, "A"), (30.8, 40.0, "B"), (45.0, 50.0, "D")])
    hypothesis = annotation([
        (0.0, 8.0, "X"),            # A et B manquées sur 8–10 et 8–10,15 (chevauchement)
        (10.15, 20.0, "Y"),
        (26.1, 30.0, "X"),          # A manquée sur 26–26,1 : entièrement dans la tolérance
        (30.8, 40.0, "Y"),
        (30.0, 30.8, "Y"),          # fausse alarme dans la pause de 0,8 s
        (45.0, 50.0, "W"),          # W apparié à D
        (52.0, 54.0, "V"),          # fausse alarme loin de tout, V non apparié : trouvé en trop
    ])
    errors, cats = categories_of(reference, hypothesis, 60.0)
    assert cats[("manquee", 8.0, 10.0)] == "chevauchement"
    assert cats[("manquee", 8.0, 10.15)] == "chevauchement"
    assert cats[("manquee", 22.0, 24.0)] == "reference_non_appariee"
    assert cats[("manquee", 26.0, 26.1)] == "frontiere"
    assert cats[("fausse_alarme", 30.0, 30.8)] == "pause"             # partie hors tolérance : 30,25–30,55
    assert cats[("fausse_alarme", 52.0, 54.0)] == "trouve_en_trop"
    assert errors["appariement"].get("C") is None and "V" not in errors["appariement"].values()
    by_zone = {(z["type"], z["debut"], z["fin"]): z for z in errors["zones"]}
    # 8–10,15 : tolérances 7,75–8,25 et 9,75–10,25, soit 0,25 + 0,4 s ; reste 8,25–9,75.
    assert by_zone[("manquee", 8.0, 10.15)]["tolerance_s"] == pytest.approx(0.65)
    assert by_zone[("manquee", 8.0, 10.15)]["contexte_hors_tolerance"]["duree_s"] == pytest.approx(1.5)
    assert by_zone[("manquee", 22.0, 24.0)]["tolerance_s"] == pytest.approx(0.5)
    assert by_zone[("fausse_alarme", 52.0, 54.0)]["tolerance_s"] == 0.0
    assert by_zone[("manquee", 26.0, 26.1)]["contexte_hors_tolerance"] is None


def test_decoupage_sur_le_temps():
    # A 0–10 manquée en entier, A non apparié : 0,25 s de tolérance à chaque bout, le reste en
    # « locuteur de référence non apparié ».
    reference = annotation([(0.0, 10.0, "A"), (12.0, 20.0, "B")])
    hypothesis = annotation([(12.0, 20.0, "X")])
    errors = sortie.error_map(reference, hypothesis, 22.0)
    missed = errors["categories"]["manquee"]
    assert missed["frontiere"] == pytest.approx(0.5)        # 0–0,25 et 9,75–10
    assert missed["reference_non_appariee"] == pytest.approx(9.5)


def test_tours_courts_et_pauses_courtes_absorbes_par_la_tolerance():
    # Tour de 0,3 s et pause de 0,4 s : entièrement dans la tolérance de leurs frontières.
    reference = annotation([(0.0, 5.0, "A"), (5.0, 5.3, "B"), (5.3, 10.0, "A"), (10.4, 14.0, "B")])
    hypothesis = annotation([(0.0, 10.0, "X"), (10.0, 10.4, "X"), (10.4, 14.0, "Y")])
    errors, cats = categories_of(reference, hypothesis, 16.0)
    assert cats[("confusion", 5.0, 5.3)] == "frontiere"
    assert cats[("fausse_alarme", 10.0, 10.4)] == "frontiere"
    zone = next(z for z in errors["zones"] if z["debut"] == 5.0)
    assert zone["contexte"]["tour_court"] == {"locuteur": "B", "duree_s": 0.3}   # constat gardé
    assert errors["categories"]["confusion"]["tour_court"] == 0.0


def test_tour_court_compte_hors_tolerance():
    # B répond « oui » en 0,8 s (5–5,8), attribué à A : la partie centrale 5,25–5,55 est hors
    # tolérance et recoupe un tour de moins de 1 s ; le reste est un décalage de frontière.
    assert sortie.SHORT_TURN_S == 1.0
    reference = annotation([(0.0, 5.0, "A"), (5.0, 5.8, "B"), (5.8, 10.0, "A"), (12.0, 20.0, "B")])
    hypothesis = annotation([(0.0, 10.0, "X"), (12.0, 20.0, "Y")])
    errors, cats = categories_of(reference, hypothesis, 22.0)
    assert cats[("confusion", 5.0, 5.8)] == "tour_court"
    assert errors["categories"]["confusion"]["tour_court"] == pytest.approx(0.3)
    assert errors["categories"]["confusion"]["frontiere"] == pytest.approx(0.5)
    # Un tour de 1 s exactement n'est pas « de moins de 1 s ».
    reference = annotation([(0.0, 5.0, "A"), (5.0, 6.0, "B"), (6.0, 10.0, "A"), (12.0, 20.0, "B")])
    errors, cats = categories_of(reference, hypothesis, 22.0)
    assert cats[("confusion", 5.0, 6.0)] == "autre"


def _removed_by_collar(report: dict) -> dict[str, float]:
    return {kind: report["collar_0"][key] - report["collar_0_25"][key]
            for kind, key in (("manquee", "manquee_s"), ("fausse_alarme", "fausse_alarme_s"),
                              ("confusion", "confusion_s"))}


def assert_boundary_is_what_the_collar_removes(reference, hypothesis, duration):
    errors = sortie.error_map(reference, hypothesis, duration)
    removed = _removed_by_collar(sortie.der_report(reference, hypothesis, duration))
    for kind, seconds in removed.items():
        assert errors["categories"][kind]["frontiere"] == pytest.approx(seconds, abs=1e-9), kind
    return errors, removed


def test_decalage_de_frontiere_egal_a_l_erreur_retiree_par_le_collar():
    """Cas construits : en secondes, type par type, « décalage de frontière » est l'erreur que
    retire le collar, y compris les morceaux de zones plus longues."""
    cases = [
        (annotation([(0.0, 5.0, "A"), (5.0, 10.0, "B"), (12.0, 20.0, "C")]),
         annotation([(0.1, 5.2, "X"), (5.2, 10.1, "Y"), (12.0, 15.0, "Z"), (16.0, 19.8, "Z")]), 22.0),
        (annotation([(1.0, 4.0, "A"), (4.0, 8.0, "B"), (8.0, 12.0, "A"), (14.0, 18.0, "B")]),
         annotation([(1.2, 4.1, "X"), (3.9, 7.85, "Y"), (8.0, 12.25, "X"), (13.8, 18.0, "Y"), (20.0, 21.0, "Y")]), 24.0),
        # Zones longues qui débordent des tolérances, chevauchement, tour court, locuteur en trop.
        (annotation([(0.0, 10.0, "A"), (8.0, 20.0, "B"), (22.0, 22.3, "A"), (22.3, 30.0, "B")]),
         annotation([(0.0, 7.0, "X"), (11.0, 20.0, "Y"), (21.0, 30.0, "Y"), (32.0, 34.0, "Z")]), 36.0),
    ]
    for reference, hypothesis, duration in cases:
        errors, removed = assert_boundary_is_what_the_collar_removes(reference, hypothesis, duration)
        assert sum(removed.values()) > 0


def _same_mapping_under_collar(reference, hypothesis, duration) -> bool:
    from pyannote.core import Timeline
    from pyannote.metrics.diarization import DiarizationErrorRate

    uem = Timeline([Segment(0.0, duration)])
    cropped = reference.crop(uem, mode="intersection")
    cropped.uri = hypothesis.uri
    mappings = []
    for collar in (0.0, 2 * sortie.BOUNDARY_S):
        metric = DiarizationErrorRate(collar=collar, skip_overlap=False)
        ref, hyp = metric.uemify(cropped, hypothesis, uem=uem, collar=collar, skip_overlap=False)
        mappings.append(metric.optimal_mapping(ref, hyp))
    return mappings[0] == mappings[1]


def test_egalite_tant_que_le_collar_ne_change_pas_l_appariement():
    """Paires aléatoires : l'égalité tient chaque fois que le DER avec collar garde l'appariement
    du DER sans collar ; elle ne peut pas tenir sinon (l'erreur hors tolérance change aussi)."""
    rng = np.random.default_rng(0)
    kept = changed = 0
    for _ in range(80):
        def random_annotation(labels, uri):
            turns = []
            for _ in range(int(rng.integers(3, 14))):
                start = float(np.round(rng.uniform(0, 55), 3))
                turns.append((start, round(start + float(rng.uniform(0.1, 8)), 3), str(rng.choice(labels))))
            return annotation(turns, uri=uri)
        reference = random_annotation(["A", "B", "C"], "ref")
        hypothesis = random_annotation(["S0", "S1", "S2", "S3"], "hyp")
        if _same_mapping_under_collar(reference, hypothesis, 50.0):
            assert_boundary_is_what_the_collar_removes(reference, hypothesis, 50.0)
            kept += 1
        else:
            changed += 1
    assert kept > 60 and changed > 0


MAIN = Path.home() / "Dev" / "Who-Spoke"


def test_decalage_de_frontiere_sur_007a_ecrh():
    """SUMM-RE 007a_ECRH, sortie d'EXP-0007, toute la durée (comme l'interface) : écart nul."""
    from whospoke.experiment import REPO_ROOT, load_rttm

    reference_path = MAIN / "data" / "processed" / "summre" / "rttm" / "summre__007a_ECRH.rttm"
    hypotheses = sorted((REPO_ROOT / "experiments").glob("EXP-0007_*/rttm/summre__007a_ECRH.rttm"))
    if not reference_path.is_file() or not hypotheses:
        pytest.skip("référence de SUMM-RE ou sortie d'EXP-0007 absente")
    reference = sortie.read_reference(reference_path)
    hypothesis = load_rttm(hypotheses[0], "summre__007a_ECRH")
    errors, removed = assert_boundary_is_what_the_collar_removes(reference, hypothesis, 1210.595)
    assert sum(removed.values()) == pytest.approx(155.625, abs=1e-3)


def test_carte_affiche_la_categorie_puis_les_autres_constats():
    reference = annotation([(0.0, 10.0, "A"), (8.0, 20.0, "B"), (22.0, 24.0, "C"), (26.0, 30.0, "A"),
                            (30.8, 40.0, "B")])
    hypothesis = annotation([(0.0, 8.0, "X"), (10.15, 20.0, "Y"), (26.1, 30.0, "X"), (30.8, 40.0, "Y"),
                             (30.0, 30.8, "Y"), (52.0, 54.0, "V")])
    errors = interface._errors_for(reference, {"annotation": hypothesis, "duree_s": 60.0})
    by_zone = {(z["type"], z["debut"], z["fin"]): z for z in errors["zones"]}
    overlap = by_zone[("manquee", 8.0, 10.15)]
    assert overlap["categorie_libelle"] == "Chevauchement"
    assert overlap["categorie_texte"] == ("Hors de la tolérance d'une frontière : la zone tombe dans un "
                                          "chevauchement de la référence.")
    assert overlap["categorie_tolerance"] == "Dont 0,65\u202fs dans la tolérance d'une frontière (pardonnés par le collar)."
    assert not any("chevauchement" in text for text in overlap["constats"])   # pas répété
    assert not any("Un de ses bords" in text for text in overlap["constats"])  # remplacé par la part pardonnée
    boundary = by_zone[("manquee", 26.0, 26.1)]
    assert boundary["categorie_libelle"] == "Décalage de frontière" and boundary["categorie_tolerance"] == ""
    assert "le collar la pardonne" in boundary["categorie_texte"]
    unmatched = by_zone[("manquee", 22.0, 24.0)]
    assert unmatched["categorie_texte"] == ("Hors de la tolérance d'une frontière : le locuteur de référence C "
                                            "n'est apparié à aucun locuteur trouvé.")
    pause = by_zone[("fausse_alarme", 30.0, 30.8)]
    assert pause["categorie_texte"].startswith("Hors de la tolérance d'une frontière : elle recoupe une pause "
                                               "de la référence de 1\u202fs au plus (0,80\u202fs)")
    extra = by_zone[("fausse_alarme", 52.0, 54.0)]
    assert extra["categorie_libelle"] == "Locuteur trouvé en trop" and extra["constats"] == []
    assert extra["categorie_texte"] == "Le locuteur trouvé n'est apparié à aucun locuteur de la référence."
    for zone in errors["zones"]:
        for text in [zone["categorie_texte"], zone["categorie_tolerance"], *zone["constats"]]:
            for word in ("parce", "cause", "car ", "due", "dû"):
                assert word not in text.lower(), text


def test_gabarit_et_script_de_la_carte():
    template = interface.VIEWER_TEMPLATE
    for name in ("wsp-explain-cat", "wsp-explain-cat-name", "wsp-explain-cat-text", "wsp-explain-cat-tol",
                 "Catégorie principale", "Autres constats dans la référence", "pas une cause établie"):
        assert name in template
    script = (interface.STATIC_DIR / "visualiseur.js").read_text()
    for name in ("zone.categorie_libelle", "zone.categorie_texte", "zone.categorie_tolerance"):
        assert name in script
