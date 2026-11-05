"""A-0005 (corpus maison, conditions d'UEM et catégories d'erreur) et confidentialité des
expériences maison : données synthétiques, aucun moteur ni fichier du corpus maison lu."""

import csv
import importlib.util
import json
import subprocess

import pytest
import yaml
from pyannote.core import Annotation, Segment

from whospoke.evaluation.metrics import DiarizationEvaluator
from whospoke.experiment import REPO_ROOT

spec = importlib.util.spec_from_file_location("a0005", REPO_ROOT / "scripts" / "analyses" / "a0005_maison_conditions.py")
a0005 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a0005)

URI = "maison__T01"


def rttm(segments):
    return "".join(f"SPEAKER {URI} 1 {a:.3f} {b - a:.3f} <NA> <NA> {spk} <NA> <NA>\n" for a, b, spk in segments)


REFERENCE = [(1.0, 10.0, "T01_S1"), (10.5, 20.0, "T01_S2"), (21.0, 30.0, "T01_S1"), (30.2, 40.0, "T01_S3")]
# Parole manquée (1,0–1,2 s et 39–40 s), confusion de S2 (15–20 s, attribuée à A, apparié à S1),
# fausse alarme d'un quatrième locuteur (41–45 s).
HYPOTHESIS = [(1.2, 10.0, "A"), (10.5, 15.0, "B"), (15.0, 20.0, "A"), (21.0, 30.0, "A"), (30.2, 39.0, "C"),
              (41.0, 45.0, "D")]


@pytest.fixture
def depot(tmp_path, monkeypatch):
    """Dépôt factice : une expérience, une référence, deux dossiers d'UEM, une liste."""
    root = tmp_path
    (root / "experiments" / "EXP-9999_essai-maison" / "rttm").mkdir(parents=True)
    (root / "experiments" / "EXP-9999_essai-maison" / "rttm" / f"{URI}.rttm").write_text(rttm(HYPOTHESIS))
    (root / "ref").mkdir()
    (root / "ref" / f"{URI}.rttm").write_text(rttm(REFERENCE))
    for name, lines in {"uem": ["0.5 46.0"], "uem_reduite": ["0.5 12.0", "18.0 46.0"]}.items():
        (root / name).mkdir()
        (root / name / f"{URI}.uem").write_text("".join(f"{URI} 1 {line}\n" for line in lines))
    (root / "liste.txt").write_text(URI + "\n")
    monkeypatch.setattr(a0005, "REPO_ROOT", root)
    monkeypatch.setattr(a0005, "reference_rttm", lambda corpus, uri: root / "ref" / f"{uri}.rttm")
    monkeypatch.setattr(a0005, "experiment_dir", lambda exp_id: root / "experiments" / f"{exp_id}_essai-maison")
    monkeypatch.setattr(a0005, "dataset_uris", lambda path: [line for line in (root / path).read_text().split()])
    return root


CONFIG = {"analyse_id": "A-9999", "corpus": "maison", "liste": "liste.txt",
          "experiences": [{"exp_id": "EXP-9999", "systeme": "essai"}],
          "conditions": [{"nom": "uem_complete", "uem": "uem"}, {"nom": "reduite", "uem": "uem_reduite"}]}


def test_conditions_d_uem_et_metriques_du_protocole(depot):
    rows, categories, sources = a0005.evaluate(CONFIG)
    assert [(r["condition"], r["uri"]) for r in rows] == [("uem_complete", URI), ("reduite", URI)]
    reference = a0005.load_rttm(depot / "ref" / f"{URI}.rttm", URI)
    hypothesis = a0005.load_rttm(depot / "experiments" / "EXP-9999_essai-maison" / "rttm" / f"{URI}.rttm", URI)
    for row, uem_dir in zip(rows, ("uem", "uem_reduite")):
        expected = DiarizationEvaluator().add(reference, hypothesis,
                                              uem=a0005.load_uem(depot / uem_dir / f"{URI}.uem", URI))
        assert row["der_c0"] == pytest.approx(expected["collar_0"]["der"], abs=0.005)
        assert row["der_c025"] == pytest.approx(expected["collar_0_25"]["der"], abs=0.005)
        assert row["jer_c0"] == pytest.approx(expected["collar_0"]["jer"], abs=0.005)
        assert (row["n_locuteurs_reference"], row["n_locuteurs_hypothese"]) == (3, 4)
    # Retirer la zone de confusion (12 à 18 s) fait baisser la confusion.
    assert rows[1]["confusion_c0"] < rows[0]["confusion_c0"]
    assert len(sources) == 4 and all(len(v) == 64 for v in sources.values())


def test_categories_somment_aux_composantes(depot):
    rows, categories, _ = a0005.evaluate(CONFIG)
    for row in rows:
        for kind in a0005.ERROR_TYPES:
            total = sum(c["points_der_c0"] for c in categories
                        if c["condition"] == row["condition"] and c["type"] == kind)
            assert total == pytest.approx(row[f"{kind}_c0"], abs=0.05)
    assert {c["categorie"] for c in categories} == set(a0005.sortie.ERROR_CATEGORIES)


def test_sorties_sans_horaire_ni_duree(depot):
    config_path = depot / "analyse" / "config.yaml"
    config_path.parent.mkdir()
    config_path.write_text(yaml.safe_dump(CONFIG))
    import sys

    argv = sys.argv
    sys.argv = ["a0005", "--config", str(config_path)]
    monkey = a0005.git_state
    a0005.git_state = lambda: {"commit": "0" * 40, "clean": True, "dirty": []}
    try:
        a0005.main()
        with pytest.raises(SystemExit):     # analyse exécutée : immuable
            a0005.main()
    finally:
        sys.argv, a0005.git_state = argv, monkey
    for name in ("resultats.csv", "categories.csv"):
        header = next(csv.reader((config_path.parent / name).open()))
        assert not [column for column in header if column.endswith("_s") or "debut" in column or "fin" in column]
    execution = json.loads((config_path.parent / "execution.json").read_text())
    assert execution["analyse_id"] == "A-9999" and execution["arbre_propre"] is True


def test_hypotheses_des_experiences_maison_ignorees_par_git():
    """Aucune sortie par segment du corpus maison versionnée (consentements non recueillis)."""
    for path in ("experiments/EXP-0036_pyannote-c1-maison-borne-2-6/rttm/maison__M01.rttm",
                 "experiments/EXP-0036_pyannote-c1-maison-borne-2-6/rttm_exclusive/maison__M01.rttm",
                 "experiments/EXP-0037_nemotron3-maison-seuil/rttm/maison__M01.rttm",
                 "data/processed/maison/uem_sans_musique/maison__M01.uem"):
        assert subprocess.run(["git", "check-ignore", "-q", path], cwd=REPO_ROOT).returncode == 0, path
    for path in ("experiments/EXP-0037_nemotron3-maison-seuil/notes.md",
                 "experiments/EXP-0037_nemotron3-maison-seuil/results_maison_test.json",
                 "data/splits/maison/test.txt"):
        assert subprocess.run(["git", "check-ignore", "-q", path], cwd=REPO_ROOT).returncode == 1, path
