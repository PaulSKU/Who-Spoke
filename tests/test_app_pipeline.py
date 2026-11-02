"""Onglet « Pipeline » (D17, D26 ; app/pipeline.py), sans modèle : page générée depuis
configuration_effective et le catalogue, lus sous une racine de dépôt configurable."""

import json

import pytest
import yaml

from app import moteurs, pipeline
from whospoke.experiment import REPO_ROOT

SPEC = moteurs.EngineSpec("essai", "Essai", "pyannote-community-1", "EXP-0099", moteurs.PYANNOTE_STEPS, False, True)

CATALOGUE = {
    "etapes": {
        "detection": {"libelle": "Détection de parole", "role": "Décider s'il y a de la voix."},
        "empreintes": {"libelle": "Empreintes vocales", "role": "Un vecteur par voix."},
    },
    "moteurs": {"pyannote-community-1": {
        "segmentation.modele": {"libelle": "Modèle de segmentation", "etape": "detection",
                                "effet": "Détecte la parole.", "composantes": ["parole manquée"], "decision": "D6"},
        "embedding.modele": {"libelle": "Modèle", "etape": "empreintes", "effet": "Empreintes.",
                             "composantes": ["confusion"], "decision": "D6"},
        "embedding_batch_size": {"libelle": "Lots", "etape": "empreintes", "effet": "Vitesse.",
                                 "composantes": ["temps"], "decision": "D6"},
        "plda.modele": {"libelle": "PLDA", "etape": "empreintes", "effet": "x", "composantes": [], "decision": "D6"},
        "seulement_au_catalogue": {"libelle": "Orphelin", "etape": "detection", "effet": "x",
                                   "composantes": [], "decision": "D6"},
    }},
}
EFFECTIVE = {
    "detection": [
        {"nom": "segmentation.modele", "valeur": "pyannote/sdc1/segmentation (PyanNet)", "origine": "modele"},
        {"nom": "plda.modele", "valeur": "pyannote/sdc1/plda", "origine": "modele"},  # étape différente
    ],
    "empreintes": [
        {"nom": "embedding.modele", "valeur": "pyannote/sdc1/embedding@3533c8cf8e36 (WeSpeakerResNet34)",
         "origine": "modele"},
        {"nom": "embedding_batch_size", "valeur": 32, "origine": "defaut"},
        {"nom": "hors_catalogue", "valeur": "<b>x</b>", "origine": "code"},
    ],
}


def _with_common(catalogue):
    """Catalogue fabriqué complété des entrées communes du vrai catalogue (normalisation)."""
    from whospoke.pipelines.base import load_catalogue

    real = load_catalogue()
    catalogue = json.loads(json.dumps(catalogue))
    catalogue["etapes"]["normalisation"] = real["etapes"]["normalisation"]
    catalogue["communs"] = real["communs"]
    return catalogue


def make_root(tmp_path, execution=True, catalogue=None):
    root = tmp_path / "depot"
    directory = root / "experiments" / "EXP-0099_essai"
    directory.mkdir(parents=True)
    (directory / "config.yaml").write_text(yaml.safe_dump({
        "device": "mps", "pipeline": {"nom": "pyannote-community-1", "parametres": {}},
        "evaluation": {"references": "data/processed/summre/rttm"},
    }))
    if execution:
        (directory / "execution_mps.json").write_text(json.dumps({
            "device": "mps", "date_fin": "2026-10-29T14:11:49+01:00", "git_commit": "568efbb7730f",
            "versions": {"python": "3.11", "pyannote.audio": "4.0.7"}, "configuration_effective": EFFECTIVE,
        }))
    catalogue_path = root / pipeline.CATALOGUE_RELATIVE
    catalogue_path.parent.mkdir(parents=True, exist_ok=True)
    catalogue_path.write_text(yaml.safe_dump(catalogue or _with_common(CATALOGUE), allow_unicode=True))
    return root


def snapshot(root):
    return sorted((str(p.relative_to(root)), p.stat().st_mtime_ns) for p in root.rglob("*"))


def test_page_generee_depuis_la_configuration_et_le_catalogue(tmp_path):
    root = make_root(tmp_path)
    page = pipeline.load_page(SPEC, root)
    assert page.unavailable is None
    assert page.execution == "experiments/EXP-0099_essai/execution_mps.json"
    assert [stage.id for stage in page.stages] == ["normalisation", "detection", "empreintes"]
    rows = {row.name: row for stage in page.stages for row in stage.rows}
    assert rows["embedding_batch_size"].value == "32" and rows["embedding_batch_size"].origin == "defaut"
    assert rows["segmentation.modele"].label == "Modèle de segmentation"
    assert rows["segmentation.modele"].decision == "D6" and rows["segmentation.modele"].components == ["parole manquée"]
    detection = page.stages[1]
    assert detection.label == "Détection de parole" and detection.family == "Détection"
    assert detection.errors == ["parole manquée"]


def test_revisions_des_modeles(tmp_path):
    page = pipeline.load_page(SPEC, make_root(tmp_path))
    rows = {row.name: row for stage in page.stages for row in stage.rows}
    assert rows["embedding.modele"].revision == "3533c8cf8e36"
    assert rows["segmentation.modele"].revision == pipeline.NO_REVISION
    assert rows["embedding_batch_size"].revision is None
    # Révision consignée dans un réglage séparé `*.revision`.
    settings = [{"nom": "plda.modele", "valeur": "pyannote/sdc1/plda"},
                {"nom": "plda.revision", "valeur": "abcdef1234567"}]
    assert pipeline.revision_of(settings[0], settings) == "abcdef1234567"


def test_ecarts_entre_configuration_et_catalogue(tmp_path):
    page = pipeline.load_page(SPEC, make_root(tmp_path))
    assert page.not_catalogued == ["hors_catalogue (empreintes)"]
    assert page.not_configured == ["seulement_au_catalogue"]
    assert len(page.wrong_step) == 1 and "plda.modele" in page.wrong_step[0]
    html = pipeline.render(page)
    assert "Écarts entre la configuration et le catalogue" in html
    assert "seulement_au_catalogue" in html and "hors_catalogue" in html


def test_etape_evaluation_separee_et_lue_dans_le_code(tmp_path):
    page = pipeline.load_page(SPEC, make_root(tmp_path))
    rows = {row.name: row for row in page.evaluation.rows}
    assert rows["collar"].value == "0 (principale) et 0,5 (± 0,25\u202fs)"
    assert rows["skip_overlap"].value == "non : chevauchements comptés"
    assert rows["references"].value == "data/processed/summre/rttm"
    assert page.evaluation not in page.stages
    html = pipeline.render(page)
    assert 'class="pl-step pl-eval" data-stage="evaluation"' in html


def test_rendu_echappe_et_revision_non_consignee(tmp_path):
    html = pipeline.render(pipeline.load_page(SPEC, make_root(tmp_path)))
    assert "révision non consignée" in html and "révision 3533c8c" in html
    assert "&lt;b&gt;x&lt;/b&gt;" in html and "<b>x</b>" not in html
    # Une seule fiche visible au départ, la première étape du moteur.
    assert html.count('class="pl-sheet"') == 4 and html.count(" hidden>") == 3
    assert "fonts.googleapis" not in html and "http" not in html


def test_experience_non_executee(tmp_path):
    page = pipeline.load_page(SPEC, make_root(tmp_path, execution=False))
    assert "pas encore été exécutée" in page.unavailable
    assert "indisponible" in pipeline.render(page)


def test_lecture_seule(tmp_path):
    root = make_root(tmp_path)
    before = snapshot(root)
    pipeline.render(pipeline.load_page(SPEC, root))
    assert snapshot(root) == before


@pytest.mark.parametrize("key, expected_missing", [
    ("pyannote-community-1", []),
    ("baseline-ecapa", []),
    # La baseline MFCC n'a pas les réglages des empreintes neuronales (D22), que le
    # catalogue du moteur « baseline » décrit aussi.
    ("baseline-mfcc", ["empreintes.dimension", "empreintes.duree_min_s", "empreintes.modele",
                       "empreintes.peripherique", "normalisation"]),
])
def test_experiences_reelles_du_depot(key, expected_missing):
    page = pipeline.load_page(moteurs.SPECS[key], REPO_ROOT)
    assert page.unavailable is None
    assert page.not_catalogued == [] and page.wrong_step == []
    assert page.not_configured == expected_missing


def test_normalisation_lue_dans_le_code_et_le_catalogue(tmp_path):
    """D26, amendement du 01/11 : valeurs de whospoke.audio, textes du catalogue."""
    from whospoke import audio

    page = pipeline.load_page(SPEC, make_root(tmp_path))
    stage = page.stages[0]
    rows = {row.name: row for row in stage.rows}
    assert [s["nom"] for s in audio.describe_normalisation()] == list(rows)
    assert rows["audio.frequence_hz"].value == "16\u202f000\u202fHz"
    assert rows["audio.canaux"].value == str(audio.CHANNELS)
    assert rows["audio.codec"].value == f"WAV {audio.CODEC}"
    assert rows["audio.entree_moteurs"].value == "signal en mémoire (waveform, sample_rate)"
    assert rows["audio.canaux"].label == "Canaux" and rows["audio.canaux"].decision == "D15"
    assert stage.label == "Normalisation" and stage.role and stage.defined_in.startswith("src/whospoke/audio.py")
    assert all(row.catalogued for row in stage.rows)


def test_normalisation_sans_entree_au_catalogue_signalee(tmp_path):
    catalogue = _with_common(CATALOGUE)
    del catalogue["communs"]["audio.canaux"]
    catalogue["communs"]["audio.ancien_reglage"] = dict(catalogue["communs"]["audio.codec"])
    page = pipeline.load_page(SPEC, make_root(tmp_path, catalogue=catalogue))
    assert "audio.canaux (normalisation)" in page.not_catalogued
    assert "audio.ancien_reglage (communs)" in page.not_configured
