"""Chantier B6 (audit R-U9, R-U10, R-U11, R-D5 ; app/sortie.py, app/interactions.py,
app/image.py, app/reproductibilite.py, app/app.py) : fusion de locuteurs annulable, indicateurs
d'interaction, étiquettes Audacity, image de la timeline, fiche de reproductibilité. Sans modèle."""

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import app as interface
from app import image, interactions, reproductibilite, sortie
from app.cache import ResultCache, annotation_tracks
from tests.test_app_appariement import (DURATION, HYPOTHESIS, REFERENCE, annotation, full_result, handler,
                                        write_reference)
from tests.test_app_demonstration import _wav, ffmpeg

# A parle, B lui répond 0,5 s après ; A reprend 0,5 s avant que B ait fini ; B acquiesce
# pendant le tour de A (inclus) ; C enchaîne sans pause ; A répond 1 s après C.
TALK = annotation([(0.0, 5.0, "A"), (5.5, 8.0, "B"), (7.5, 12.0, "A"), (9.0, 9.5, "B"), (12.0, 13.0, "C"),
                   (14.0, 15.0, "A"), (15.0, 16.0, "A")])


# --- Fusion (R-U9) -----------------------------------------------------------------------

def test_fusion_sur_une_copie():
    merged = sortie.merge_speakers(HYPOTHESIS, [("S2", "S0")])
    assert sorted(merged.labels()) == ["S0", "S1"]
    assert merged.label_duration("S0") == pytest.approx(HYPOTHESIS.label_duration("S0") + 1.0)
    assert sorted(HYPOTHESIS.labels()) == ["S0", "S1", "S2"]          # l'original est intact
    # Fusions en chaîne : S2 dans S1, puis S1 dans S0 ; la parole qui se touche est réunie.
    chained = sortie.merge_speakers(HYPOTHESIS, [("S2", "S1"), ("S1", "S0")])
    assert chained.labels() == ["S0"]
    assert [(s.start, s.end) for s in chained.label_timeline("S0")] == [(0.0, 12.4), (12.6, 20.0), (22.0, 23.0)]
    assert sortie.merge_speakers(HYPOTHESIS, []) == HYPOTHESIS
    for wrong in ([("S0", "S0")], [("S9", "S0")], [("S2", "S0"), ("S2", "S1")]):
        with pytest.raises(ValueError):
            sortie.merge_speakers(HYPOTHESIS, wrong)


def test_fusion_depuis_le_tableau_puis_annulation(tmp_path):
    blocks = interface.build_app(fake=True, cache_dir=tmp_path / "cache")
    changed = handler(blocks, "speakers_changed")
    reference = write_reference(tmp_path)
    result = full_result(tmp_path, {"S0": "Alice", "S1": "Bob"})
    original = annotation_tracks(result["annotation_origine"])
    # Le cache contient le résultat du moteur : la fusion n'y touche jamais.
    store = ResultCache(tmp_path / "cache")
    entry = store.put("a" * 64, {"pistes": original})
    before_bytes = entry.read_bytes()

    viewer, stats, inter, exports, der, _, image_html, merged = changed(
        result, str(reference), SimpleNamespace(_data={"merge": {"source": "S0", "target": "S1"}}))
    assert merged["fusions"] == [("S0", "S1")] and sorted(merged["annotation"].labels()) == ["S1", "S2"]
    assert annotation_tracks(merged["annotation_origine"]) == original
    assert entry.read_bytes() == before_bytes and len(store.entries()) == 1
    # La couleur suit le locuteur, pas son rang : Bob garde la deuxième couleur.
    colors = interface._speaker_colors(["S0", "S1", "S2"])
    group = {s["id"]: s for s in viewer["groupes"][0]["locuteurs"]}
    assert group["S1"]["couleur"] == colors["S1"][0] and group["S2"]["couleur"] == colors["S2"][0]
    # Statistiques, interactions, exports et DER recalculés, avec le DER avant → après.
    assert "Alice → Bob" in stats and "Annuler la dernière fusion (Alice → Bob)" in stats
    assert 'data-id="S0"' not in stats and "Alice" not in inter
    before = sortie.der_report(REFERENCE, HYPOTHESIS, DURATION)["collar_0"]["der"]
    after = sortie.der_report(REFERENCE, merged["annotation"], DURATION)["collar_0"]["der"]
    plain = re.sub(r"<[^>]+>", "", der)                                  # termes liés au glossaire
    assert f"sans collar {interface._pct(before, 2)} → {interface._pct(after, 2)}" in plain
    assert "Après 1 fusion" in der and ("hausse" in der if after > before else "baisse" in der)
    # Le DER d'avant (annotation du moteur, même référence) est gardé : calculé une seule fois.
    assert merged["der_avant"]["reference"] == str(reference)
    assert merged["der_avant"]["rapport"]["collar_0"]["der"] == pytest.approx(before)
    data = json.loads(Path(next(p for p in exports if p.endswith(".json"))).read_text())
    assert {row["id"] for row in data["locuteurs"]} == {"S1", "S2"}
    assert data["reproductibilite"]["fusions"] == [{"source": "S0", "cible": "S1"}]
    assert "SPEAKER essai 1 0.000 12.400" in Path(next(p for p in exports if p.endswith(".rttm"))).read_text()
    # La carte des erreurs suit la fusion.
    assert merged["erreurs"]["appariement"] != result["erreurs"]["appariement"]

    # Annulation : retour à l'annotation du moteur, sans fusion.
    _, stats, _, _, der, _, _, undone = changed(merged, str(reference), SimpleNamespace(_data={"undo": True}))
    assert undone["fusions"] == [] and annotation_tracks(undone["annotation"]) == original
    assert "Fusions en vigueur" not in stats and "Après" not in der
    # Rien à annuler : ignoré.
    assert all(v.get("__type__") == "update" for v in changed(undone, None, SimpleNamespace(_data={"undo": True})))


def test_annulation_d_une_fusion_et_nom_deja_pris(tmp_path):
    changed = handler(interface.build_app(fake=True, cache_dir=tmp_path), "speakers_changed")
    result = full_result(tmp_path, {"S0": "Alice"})
    merged = changed(result, None, SimpleNamespace(_data={"merge": {"source": "S0", "target": "S1"}}))[-1]
    renamed = changed(merged, None, SimpleNamespace(_data={"names": {"S1": "Alice", "S2": ""}}))[-1]
    assert renamed["names"]["S1"] == "Alice"
    with pytest.warns(UserWarning, match="déjà pris"):
        undone = changed(renamed, None, SimpleNamespace(_data={"undo": True}))[-1]
    assert "S0" not in undone["names"] and undone["names"]["S1"] == "Alice"
    # Fusion refusée (locuteur absent) : le tableau revient à l'état en vigueur.
    with pytest.warns(UserWarning, match="Fusion impossible"):
        refused = changed(result, None, SimpleNamespace(_data={"merge": {"source": "S9", "target": "S1"}}))
    assert refused[-1].get("__type__") == "update" and "ws-merge" in refused[1]


def test_liste_de_fusion_echappee():
    html = interface._stats_html({"annotation": HYPOTHESIS, "names": {"S1": "<b>Bob</b>"}})
    assert html.count('class="ws-merge"') == 3 and "Fusionner avec…" in html
    assert '<option value="S1">&lt;b&gt;Bob&lt;/b&gt;</option>' in html and "<b>Bob</b>" not in html
    single = interface._stats_html({"annotation": annotation([(0.0, 1.0, "S0")]), "names": {}})
    assert 'class="ws-merge"' not in single


# --- Indicateurs d'interaction (R-U10) -----------------------------------------------------

def test_tours_et_passages_de_parole():
    turns = interactions.turns(TALK)
    assert [(t.speaker, t.start, t.end) for t in turns] == [
        ("A", 0.0, 5.0), ("B", 5.5, 8.0), ("A", 7.5, 12.0), ("B", 9.0, 9.5), ("C", 12.0, 13.0), ("A", 14.0, 16.0)]
    moves = interactions.transitions(turns)
    assert moves == [("A", "B", 0.5), ("B", "A", -0.5), ("A", "C", 0.0), ("C", "A", 1.0)]


def test_indicateurs_d_interaction():
    data = interactions.report(TALK)
    rows = {row["id"]: row for row in data["locuteurs"]}
    assert rows["A"]["n_tours"] == 3 and rows["A"]["duree_moyenne_tour_s"] == pytest.approx(11.5 / 3, abs=1e-3)
    assert rows["A"]["plus_long_tour_s"] == 5.0
    assert rows["A"]["latence_mediane_s"] == pytest.approx(0.25) and rows["A"]["n_reponses"] == 2
    assert rows["B"]["latence_mediane_s"] == 0.5 and rows["C"]["latence_mediane_s"] == 0.0
    assert data["plus_long_monologue"] == {"locuteur": "A", "debut": 0.0, "fin": 5.0, "duree_s": 5.0}
    assert data["ordre"] == ["A", "B", "C"]
    assert data["qui_suit_qui"] == [[0, 1, 1], [1, 0, 0], [1, 0, 0]] and data["n_passages"] == 4
    alone = interactions.report(annotation([(0.0, 2.0, "A")]))
    assert alone["locuteurs"][0]["latence_mediane_s"] is None and alone["qui_suit_qui"] == [[0]]


def test_matrice_qui_suit_qui_accessible():
    html = interface._interactions_html({"annotation": TALK, "names": {"B": "<i>Bob</i>"}})
    assert '<table class="ws-table ws-matrix">' in html and '<caption class="ws-sr">Qui suit qui' in html
    assert html.count('<th scope="row"') == 3 and "4 passages en tout" in html
    assert "&lt;i&gt;Bob&lt;/i&gt;" in html and "<i>Bob</i>" not in html
    cells = re.findall(r'<td class="num ws-mx"(?: style="--mx:(\d+)%")?>(\d+)</td>', html)
    assert [int(count) for _, count in cells] == [1, 1, 1, 0, 1, 0]   # effectif écrit dans chaque case
    assert html.count("ws-mx-diag") == 3 and "sans objet" in html
    assert "Plus long monologue" in html and 'data-debut="0.0" data-fin="5.0"' in html
    assert "−0,50\u202fs" not in html and "+0,25\u202fs" in html and "2 réponses" in html
    assert "Les indicateurs" in interface._interactions_html(None)


# --- Étiquettes Audacity et image de la timeline (R-U11) -----------------------------------

CORPUS_SPEAKER = re.compile(r"^(?:(M\d{2})_)?(S\d+)$")   # whospoke.maison.reference (branche outils)


def test_etiquettes_audacity_lisibles_par_la_chaine_du_corpus():
    text = sortie.to_audacity(TALK)
    lines = text.splitlines()
    assert len(lines) == 6 and text.endswith("\n")                  # une ligne par tour
    assert lines[0] == "0.000000\t5.000000\tS1" and lines[-1] == "14.000000\t16.000000\tS1"
    for line in lines:
        start, end, code = line.split("\t")
        assert float(start) <= float(end) and CORPUS_SPEAKER.match(code)
    assert sortie.audacity_codes(TALK) == {"A": "S1", "B": "S2", "C": "S3"}


def test_image_de_la_timeline():
    result = {"annotation": HYPOTHESIS, "names": {"S0": "<Alice>"}, "duree_s": DURATION, "libelle": "pyannote",
              "reference": REFERENCE, "erreurs": interface._errors_for(REFERENCE, {"annotation": HYPOTHESIS,
                                                                                  "duree_s": DURATION}),
              "wav": Path("essai.wav"), "peaks": [], "uri": "essai"}
    svg = interface._timeline_svg(result)
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"') and 'role="img"' in svg
    assert "<title id=\"titre\">essai : qui parle, et quand</title>" in svg and "&lt;Alice&gt;" in svg
    assert "<Alice>" not in svg and 'id="hachures"' in svg and "Erreurs sans collar" in svg
    colors = interface._speaker_colors(["S0", "S1", "S2"])
    # Deux segments de S0, et deux de A, apparié à S0, dans la référence.
    assert svg.count(f'fill="{colors["S0"][0]}"') == 4
    assert "url(" not in svg.replace("url(#hachures)", "") and "http" not in svg.replace(
        "http://www.w3.org/2000/svg", "")
    assert image.clock(65) == "1:05" and image.clock(3725) == "1:02:05"
    assert image.tick_step(24) == 5 and image.tick_step(3600) == 600
    html = interface._image_html(result)
    assert 'data-name="essai_timeline.png"' in html and "<svg" not in html and "&lt;svg" in html


# --- Fiche de reproductibilité (R-D5) ------------------------------------------------------

def test_fiche_de_reproductibilite(tmp_path):
    result = full_result(tmp_path)
    sheet = reproductibilite.sheet(result)
    assert sheet["commit"] == "abc" and sheet["empreinte_audio"] == "f" * 64
    assert sheet["versions"]["python"] and sheet["versions"]["gradio"] != "absent" and "ffmpeg" in sheet["versions"]
    assert sheet["machine"]["peripherique"] == "cpu" and sheet["machine"]["coeurs"]
    assert sheet["durees_s"] == {"audio": DURATION, "normalisation": 0.1, "chargement_modele": None,
                                 "etapes": {"segmentation": 0.5}, "calcul": 1.0, "rtf": round(1.0 / DURATION, 5)}
    assert sheet["experience_source"] == "EXP-0001" and sheet["fusions"] == []
    exports = interface._exports(result)
    assert [Path(p).name for p in exports] == ["essai.rttm", "essai.json", "essai_audacity.txt", "essai_timeline.svg"]
    text = Path(exports[1]).read_text()
    data = json.loads(text)
    assert set(data["reproductibilite"]) >= {"versions", "commit", "revisions_modeles", "configuration_effective",
                                             "reglages", "machine", "durees_s"}
    assert data["etiquettes_audacity"]["S1"] == {"id": "S0", "nom": "S0"}
    assert str(tmp_path) not in text                                    # aucun chemin local


@ffmpeg
def test_tracabilite_consignee_a_l_analyse(tmp_path, monkeypatch):
    """Analyse complète en mode factice : la fiche porte commit, empreintes, révisions et
    configuration effective ; un résultat réaffiché garde le commit et la date de son calcul ;
    les indicateurs et l'image suivent l'analyse."""
    (tmp_path / "run").mkdir()
    monkeypatch.setattr(interface, "RUN_DIR", tmp_path / "run")
    blocks = interface.build_app(fake=True, fake_max_s=0.2, cache_dir=tmp_path / "cache")
    analyse = handler(blocks, "analyse")
    audio = _wav(tmp_path / "004c_PAPH.wav")
    settings = ("pyannote-community-1", False, "baseline-ecapa", "Automatique", 2, 2, 6, "cpu")
    final = list(analyse(None, audio, *settings, None, True))[-1]
    result = next(v for v in final.values() if isinstance(v, dict) and "annotation" in v)
    trace = result["tracabilite"]
    assert len(trace["empreinte_audio"]) == 64 and len(trace["empreinte_code_moteurs"]) == 64
    assert trace["commit"] and trace["revisions_modeles"]
    assert trace["configuration_effective"]
    texts = [v for v in final.values() if isinstance(v, str)]
    assert any("ws-matrix" in t or "Plus long monologue" in t for t in texts)
    assert any('class="ws-btn ws-png"' in t for t in texts)
    sheet = json.loads(Path(next(p for p in interface._exports(result) if p.endswith(".json"))).read_text())
    assert sheet["reproductibilite"]["reaffiche_depuis_le_cache"] is False
    again = next(v for v in list(analyse(None, audio, *settings, None, True))[-1].values()
                 if isinstance(v, dict) and "annotation" in v)
    assert again["cache"] and again["tracabilite"]["commit"] == trace["commit"]
    assert reproductibilite.sheet(again)["date_calcul"] == again["cache"]
