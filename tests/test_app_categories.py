"""Catégorie principale des zones d'erreur (décision du cockpit du 02/11, retour de B9 et E8 ;
app/sortie.py, `main_category`) : exclusive, par ordre de priorité, une seule définition."""

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
    assert seen == set(sortie.ERROR_CATEGORIES)                        # toutes atteintes


def test_egalite_stricte_sur_des_durees_exactes():
    # Durées en multiples de 1/8 s, exactes en binaire : pas d'arrondi, égalité stricte.
    reference = annotation([(0.0, 4.0, "A"), (3.0, 8.0, "B"), (9.0, 9.375, "C"), (9.375, 12.0, "A")])
    hypothesis = annotation([(0.125, 6.0, "X"), (7.0, 10.0, "Y"), (13.0, 14.5, "Z")])
    errors = sortie.error_map(reference, hypothesis, 16.0)
    der = sortie.der_report(reference, hypothesis, 16.0)["collar_0"]
    for kind, key in (("manquee", "manquee_s"), ("fausse_alarme", "fausse_alarme_s"), ("confusion", "confusion_s")):
        assert sum(errors["categories"][kind].values()) == der[key]


def test_ordre_de_priorite():
    # A 0–10, B 10–20 avec chevauchement A+B 8–10 ; C, tour court 25–25,3 ; pause de 0,8 s 30–30,8.
    reference = annotation([(0.0, 10.0, "A"), (8.0, 20.0, "B"), (25.0, 25.3, "C"),
                            (26.0, 30.0, "A"), (30.8, 40.0, "B"), (45.0, 50.0, "D")])
    hypothesis = annotation([
        (0.0, 8.0, "X"),            # A et B manquées sur 8–10 et 8–10,15 (chevauchement)
        (10.15, 20.0, "Y"),
        (26.1, 30.0, "X"),          # A manquée sur 26–26,1 : frontière, et contiguë à une pause
        (30.8, 40.0, "Y"),
        (30.0, 30.8, "Y"),          # fausse alarme dans la pause de 0,8 s
        (45.0, 50.0, "W"),          # W apparié à D
        (52.0, 54.0, "V"),          # fausse alarme loin de tout, V non apparié : trouvé en trop
    ])
    errors, cats = categories_of(reference, hypothesis, 60.0)
    assert cats[("manquee", 8.0, 10.0)] == "chevauchement"
    assert cats[("manquee", 8.0, 10.15)] == "chevauchement"            # déborde de ±0,25 s de 10 : pas frontière
    assert cats[("manquee", 26.0, 26.1)] == "frontiere"                # passe avant la pause contiguë
    assert cats[("manquee", 25.0, 25.3)] == "reference_non_appariee"     # C non apparié, avant « tour court »
    assert cats[("fausse_alarme", 30.0, 30.8)] == "pause"
    assert cats[("fausse_alarme", 52.0, 54.0)] == "trouve_en_trop"
    assert errors["appariement"].get("C") is None and "V" not in errors["appariement"].values()


def test_frontiere_stricte_et_tour_court():
    # Zone de 0,4 s qui touche une frontière mais déborde de ±0,25 s : pas un décalage de frontière.
    reference = annotation([(0.0, 5.0, "A"), (5.0, 5.3, "B"), (5.3, 10.0, "A")])
    hypothesis = annotation([(0.0, 10.0, "X"), (20.0, 21.0, "Y")])
    errors, cats = categories_of(reference, hypothesis, 22.0)
    # Zone 5–5,3 (B attribué à X) : ni dans 4,75–5,25 (autour de 5) ni dans 5,05–5,55 (autour de 5,3).
    zone = next(z for z in errors["zones"] if z["debut"] == 5.0)
    assert not zone["contexte"]["dans_collar"] and zone["contexte"]["frontiere_s"] == 0.0
    # Même chose, B apparié (il parle aussi ailleurs, couvert par Y) : tour court.
    reference = annotation([(0.0, 5.0, "A"), (5.0, 5.3, "B"), (5.3, 10.0, "A"), (12.0, 15.0, "B")])
    hypothesis = annotation([(0.0, 10.0, "X"), (12.0, 15.0, "Y")])
    errors, cats = categories_of(reference, hypothesis, 16.0)
    assert cats[("confusion", 5.0, 5.3)] == "tour_court"
    # Zone de 0,2 s dans ±0,25 s d'une frontière : décalage, même si c'est aussi un tour court.
    reference = annotation([(0.0, 5.0, "A"), (5.0, 5.2, "B"), (5.2, 10.0, "A"), (12.0, 15.0, "B")])
    errors, cats = categories_of(reference, hypothesis, 16.0)
    assert cats[("confusion", 5.0, 5.2)] == "frontiere"


def test_part_decalage_de_frontiere_egale_l_ecart_entre_conditions_de_collar():
    """Cas construits où toute erreur proche d'une frontière tient dans ±0,25 s et où les autres
    en sont loin : la part « décalage de frontière » est exactement ce que le collar retire."""
    cases = [
        # Frontières décalées de 0,1 à 0,2 s, et une erreur loin des frontières (15–16).
        (annotation([(0.0, 5.0, "A"), (5.0, 10.0, "B"), (12.0, 20.0, "C")]),
         annotation([(0.1, 5.2, "X"), (5.2, 10.1, "Y"), (12.0, 15.0, "Z"), (16.0, 19.8, "Z")]), 22.0),
        # Fins de tours avancées et retardées, chevauchement bref de l'hypothèse à une frontière.
        (annotation([(1.0, 4.0, "A"), (4.0, 8.0, "B"), (8.0, 12.0, "A"), (14.0, 18.0, "B")]),
         annotation([(1.2, 4.1, "X"), (3.9, 7.85, "Y"), (8.0, 12.25, "X"), (13.8, 18.0, "Y"), (20.0, 21.0, "Y")]), 24.0),
    ]
    for reference, hypothesis, duration in cases:
        errors = sortie.error_map(reference, hypothesis, duration)
        report = sortie.der_report(reference, hypothesis, duration)
        boundary = sum(errors["categories"][kind]["frontiere"] for kind in errors["categories"])
        removed = error_seconds(report["collar_0"]) - error_seconds(report["collar_0_25"])
        assert boundary > 0
        assert boundary == pytest.approx(removed, abs=1e-9)


def test_carte_affiche_la_categorie_puis_les_autres_constats():
    reference = annotation([(0.0, 10.0, "A"), (8.0, 20.0, "B"), (25.0, 25.3, "C"), (26.0, 30.0, "A"),
                            (30.8, 40.0, "B")])
    hypothesis = annotation([(0.0, 8.0, "X"), (10.15, 20.0, "Y"), (26.1, 30.0, "X"), (30.8, 40.0, "Y"),
                             (30.0, 30.8, "Y"), (52.0, 54.0, "V")])
    errors = interface._errors_for(reference, {"annotation": hypothesis, "duree_s": 60.0})
    by_start = {(z["type"], z["debut"], z["fin"]): z for z in errors["zones"]}
    overlap = by_start[("manquee", 8.0, 10.0)]
    assert overlap["categorie_libelle"] == "Chevauchement"
    assert overlap["categorie_texte"] == "La zone tombe dans un chevauchement de la référence."
    assert overlap["categorie_texte"] not in overlap["constats"]          # pas répété dans les constats
    assert by_start[("manquee", 8.0, 10.15)]["categorie_texte"].startswith("La zone recoupe un chevauchement")
    boundary = by_start[("manquee", 26.0, 26.1)]
    assert boundary["categorie_libelle"] == "Décalage de frontière"
    assert "le collar de 0,25 s la pardonne" in boundary["categorie_texte"]
    assert not any("Un de ses bords" in text for text in boundary["constats"])
    assert any(text.startswith("Elle est contiguë à une pause") for text in boundary["constats"])
    unmatched = by_start[("manquee", 25.0, 25.3)]
    assert unmatched["categorie_texte"] == "Le locuteur de référence C n'est apparié à aucun locuteur trouvé."
    assert any(text.startswith("Elle recoupe un tour de la référence de moins de 0,5 s") for text in unmatched["constats"])
    pause = by_start[("fausse_alarme", 30.0, 30.8)]
    assert pause["categorie_texte"].startswith("Elle recoupe une pause de la référence de 1 s au plus (0,80 s)")
    extra = by_start[("fausse_alarme", 52.0, 54.0)]
    assert extra["categorie_libelle"] == "Locuteur trouvé en trop" and extra["constats"] == []
    for zone in errors["zones"]:
        for text in [zone["categorie_texte"], *zone["constats"]]:
            for word in ("parce", "cause", "car ", "due", "dû"):
                assert word not in text.lower(), text


def test_gabarit_et_script_de_la_carte():
    template = interface.VIEWER_TEMPLATE
    for name in ("wsp-explain-cat", "wsp-explain-cat-name", "wsp-explain-cat-text", "Catégorie principale",
                 "Autres constats dans la référence", "pas une cause établie"):
        assert name in template
    script = (interface.STATIC_DIR / "visualiseur.js").read_text()
    assert "zone.categorie_libelle" in script and "zone.categorie_texte" in script
