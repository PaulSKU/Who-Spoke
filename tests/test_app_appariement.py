"""Chantier B4 (audit R-U4, R-U6 ; app/sortie.py, app/app.py) : appariement visible,
« Expliquer cette erreur », extrait typique, renommage dans le tableau. Sans modèle."""

from types import SimpleNamespace

import pytest
from pyannote.core import Annotation, Segment

from app import app as interface
from app import sortie


def annotation(turns, uri="essai"):
    result = Annotation(uri=uri)
    for index, (start, end, label) in enumerate(turns):
        result[Segment(start, end), index] = label
    return result


# Référence : A et B se chevauchent de 9 à 10 s ; C ne parle que 0,3 s ; pause de 0,6 s entre 12 et 12,6 s.
REFERENCE = annotation([(0.0, 10.0, "A"), (9.0, 12.0, "B"), (12.6, 20.0, "A"), (20.0, 20.3, "C")])
# Hypothèse : S0 ≈ A, S1 ≈ B, S2 en trop (fausse alarme), C manqué.
HYPOTHESIS = annotation([(0.0, 9.5, "S0"), (9.5, 12.4, "S1"), (12.6, 19.0, "S0"), (19.0, 20.0, "S1"),
                         (22.0, 23.0, "S2")])
DURATION = 24.0


def test_appariement_celui_du_der():
    pairs = sortie.pairing(REFERENCE, HYPOTHESIS, DURATION)
    assert pairs == {"A": "S0", "B": "S1"}                      # C n'est apparié à personne
    assert sortie.error_map(REFERENCE, HYPOTHESIS, DURATION)["appariement"] == pairs
    # La confusion de la carte (calculée avec cet appariement) égale celle du DER.
    der = sortie.der_report(REFERENCE, HYPOTHESIS, DURATION)["collar_0"]
    assert sortie.error_map(REFERENCE, HYPOTHESIS, DURATION)["totaux"]["confusion"] == der["confusion_s"]


def test_tableau_d_appariement_avec_pyannote_metrics():
    from pyannote.metrics.diarization import DiarizationCoverage, DiarizationPurity

    rows = {(r["reference"], r["hypothese"]): r for r in sortie.matching_report(REFERENCE, HYPOTHESIS, DURATION)}
    assert list(rows) == [("A", "S0"), ("B", "S1"), ("C", None), (None, "S2")]
    a = rows[("A", "S0")]
    assert a["commun_s"] == pytest.approx(9.5 + 6.4)            # 0–9,5 et 12,6–19
    assert a["couverture"] == pytest.approx((9.5 + 6.4) / 17.4)
    assert rows[("B", "S1")]["commun_s"] == pytest.approx(2.5)  # 9,5–12
    assert rows[("C", None)]["couverture"] == pytest.approx(0.0) and rows[("C", None)]["purete"] is None
    assert rows[(None, "S2")]["purete"] == pytest.approx(0.0) and rows[(None, "S2")]["couverture"] is None
    # Pondérées par la durée, les puretés et couvertures par locuteur redonnent les valeurs
    # globales de pyannote.metrics : rien n'est recodé.
    hyp_duration = {label: HYPOTHESIS.label_duration(label) for label in HYPOTHESIS.labels()}
    purity = sum(r["purete"] * hyp_duration[r["hypothese"]] for r in rows.values() if r["purete"] is not None)
    assert purity / sum(hyp_duration.values()) == pytest.approx(DiarizationPurity()(REFERENCE, HYPOTHESIS))
    coverage = sum(r["couverture"] * r["duree_reference_s"] for r in rows.values() if r["couverture"] is not None)
    total = sum(r["duree_reference_s"] for r in rows.values())
    assert coverage / total == pytest.approx(DiarizationCoverage()(REFERENCE, HYPOTHESIS))


def test_tableau_d_appariement_affiche_et_echappe():
    rows = sortie.matching_report(REFERENCE, HYPOTHESIS, DURATION)
    html = interface._matching_html(rows, {"S0": "<b>Alice</b>"})
    assert "&lt;b&gt;Alice&lt;/b&gt;" in html and "<b>Alice</b>" not in html
    assert "non apparié" in html and "aucun" in html and "Pureté" in html and "Couverture" in html


def _result(names=None):
    return {"annotation": HYPOTHESIS, "names": names or {}, "duree_s": DURATION, "libelle": "pyannote community-1",
            "reference": REFERENCE, "erreurs": sortie.error_map(REFERENCE, HYPOTHESIS, DURATION)}


def test_pistes_de_reference_aux_couleurs_de_l_appariement():
    group = interface._reference_group(_result({"S1": "Bob"}))
    speakers = {s["id"]: s for s in group["locuteurs"]}
    colors = interface._speaker_colors(sortie.speaker_labels(HYPOTHESIS))
    assert speakers["A"]["nom"] == "A ↔ S0" and speakers["A"]["couleur"] == colors["S0"][0]
    assert speakers["B"]["nom"] == "B ↔ Bob" and speakers["B"]["couleur_sombre"] == colors["S1"][1]
    assert speakers["C"]["nom"] == "C (non apparié)" and speakers["C"]["couleur"] == interface.NEUTRAL_LIGHT
    assert group["titre"] == "Référence, appariée à pyannote community-1"
    # Sans carte des erreurs (référence inutilisable) : gris, sans mention d'appariement.
    plain = interface._reference_group(dict(_result(), erreurs=None))
    assert {s["nom"] for s in plain["locuteurs"]} == {"A", "B", "C"} and plain["titre"] == "Référence"


def test_contexte_des_zones():
    zones = sortie.error_map(REFERENCE, HYPOTHESIS, DURATION)["zones"]
    by_type = {}
    for zone in zones:
        by_type.setdefault(zone["type"], []).append(zone)
    # Parole de C manquée (20–20,3) : tour court, frontière de tour à 0 s.
    missed_c = next(z for z in by_type["manquee"] if z["reference"] == "C")
    assert missed_c["contexte"]["tour_court"] == {"locuteur": "C", "duree_s": 0.3}
    assert missed_c["contexte"]["frontiere_s"] == 0.0
    # Parole manquée dans le chevauchement A+B (9–9,5 pour B) : dans un chevauchement.
    in_overlap = next(z for z in by_type["manquee"] if z["debut"] == 9.0)
    assert in_overlap["contexte"]["chevauchement_s"] == pytest.approx(0.5)
    # Fausse alarme de S1 entre 12 et 12,4 : dans la pause de 0,6 s de la référence.
    pause = next(z for z in by_type["fausse_alarme"] if z["debut"] == 12.0)
    assert pause["contexte"]["pause"] == {"duree_s": 0.6, "relation": "recoupe"}
    # Fausse alarme de S2 (22–23), loin de tout : aucun contexte.
    far = next(z for z in by_type["fausse_alarme"] if z["debut"] == 22.0)
    assert far["contexte"] == {"chevauchement_s": 0.0, "tour_court": None, "pause": None, "frontiere_s": None}


def test_constats_factuels_jamais_une_cause():
    errors = interface._errors_for(REFERENCE, {"annotation": HYPOTHESIS, "duree_s": DURATION})
    sentences = [text for zone in errors["zones"] for text in zone["constats"]]
    assert "La zone tombe dans un chevauchement de la référence." in sentences
    assert any(t.startswith("Elle recoupe un tour de la référence de moins de 0,5 s (C, 0,30 s)") for t in sentences)
    assert any(t.startswith("Elle recoupe une pause de la référence de moins de 1 s (0,60 s)") for t in sentences)
    assert any("Aucun de ces contextes" in t for t in sentences)
    for text in sentences:
        for word in ("parce", "cause", "car ", "à cause", "due", "dû"):
            assert word not in text.lower(), text
    assert "pas une cause établie" in interface.VIEWER_TEMPLATE


def test_extrait_typique():
    hyp = annotation([(0.0, 4.0, "S0"), (3.0, 30.0, "S1"), (31.0, 33.0, "S0"), (40.0, 41.0, "S2"),
                      (40.0, 41.0, "S3")])
    excerpts = sortie.typical_excerpts(hyp)
    assert excerpts["S0"] == (0.0, 3.0)            # 0–3 (hors chevauchement) bat 31–33
    assert excerpts["S1"] == (4.0, 14.0)           # 4–30 hors chevauchement, limité à 10 s
    assert excerpts["S2"] is None and excerpts["S3"] is None    # toute leur parole se chevauche
    html = interface._stats_html({"annotation": hyp, "names": {}})
    assert 'data-debut="4.0" data-fin="14.0"' in html and html.count("disabled") == 2


def test_renommage_dans_le_tableau_et_echappement():
    hostile = '"><img src=x onerror=alert(1)><b>Alice</b>'
    html = interface._stats_html({"annotation": HYPOTHESIS, "names": {"S0": hostile}})
    assert 'class="ws-name-input" data-id="S0"' in html and 'placeholder="S1"' in html
    assert "<img" not in html and "<b>Alice</b>" not in html
    assert 'value="&quot;&gt;&lt;img src=x onerror=alert(1)&gt;&lt;b&gt;Alice&lt;/b&gt;"' in html
    assert "gr.Dataframe" not in (interface.STATIC_DIR.parent / "app.py").read_text()


def handler(blocks, name):
    return next(f.fn for f in blocks.fns.values() if getattr(f.fn, "__name__", "") == name)


def full_result(tmp_path, names=None):
    """Résultat complet d'une analyse (sans audio), tel que `analyse` le range dans l'état."""
    return dict(_result(names), uri="essai", wav=tmp_path / "essai.wav", dir=tmp_path, peaks=[0.0],
                moteur="factice", configuration={"experience_source": "EXP-0001", "peripherique": "cpu",
                                                 "nombre_locuteurs": {"mode": "automatique"},
                                                 "moteur_factice": True, "reglages": {}},
                calcul_s=1.0, moteur_cle="pyannote-community-1", annotation_origine=HYPOTHESIS, fusions=[],
                factice=True, device="cpu", normalisation_s=0.1, chargement_s=None,
                durees_etapes={"segmentation": 0.5}, cache=None,
                tracabilite={"date_analyse": "2026-11-01T10:00:00", "commit": "abc", "empreinte_audio": "f" * 64})


def write_reference(tmp_path):
    reference = tmp_path / "ref.rttm"
    reference.write_text("".join(f"SPEAKER essai 1 {s.start} {s.duration} <NA> <NA> {label} <NA> <NA>\n"
                                 for s, _, label in REFERENCE.itertracks(yield_label=True)))
    return reference


def test_renommage_envoye_par_le_tableau(tmp_path):
    blocks = interface.build_app(fake=True, cache_dir=tmp_path)
    changed = handler(blocks, "speakers_changed")
    result = full_result(tmp_path)
    reference = write_reference(tmp_path)
    viewer, stats, inter, exports, der, comparison, image_html, updated = changed(
        result, str(reference), SimpleNamespace(_data={"names": {"S0": "  Alice ", "S9": "x"}}))
    assert updated["names"] == {"S0": "Alice", "S1": "", "S2": ""}
    assert any(s["nom"] == "Alice" for s in viewer["groupes"][0]["locuteurs"])
    assert "A ↔ Alice" in {s["nom"] for s in viewer["groupes"][-1]["locuteurs"]}
    assert "Alice" in der and "Alice" in inter and len(exports) == 4
    # Noms en double refusés : le tableau revient aux noms en vigueur, rien d'autre ne change.
    refused = changed(updated, str(reference), SimpleNamespace(_data={"names": {"S0": "Alice", "S1": "Alice"}}))
    assert 'value="Alice"' in refused[1] and 'value=""' in refused[1]
    assert all(refused[i].get("__type__") == "update" for i in (0, 2, 3, 4, 5, 6, 7))
    # Évènement sans données (mise à jour du composant) : ignoré.
    ignored = changed(updated, None, SimpleNamespace(_data=None))
    assert all(isinstance(value, dict) and value.get("__type__") == "update" for value in ignored)
