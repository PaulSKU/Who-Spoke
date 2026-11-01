"""Moteurs de l'interface et moteur factice (D17, D19 §1, app/moteurs.py).

Aucun modèle neuronal n'est chargé ici : seuls la baseline MFCC (sur un signal
synthétique de quelques secondes) et le moteur factice sont exécutés.
"""

import json

import numpy as np
import pytest
import torch
import yaml

from app import moteurs
from whospoke.pipelines.base import Engine
from whospoke.pipelines.baseline import Baseline

SR = 16000


def fake_experiment(root, exp_id="EXP-0099", rttm=None, execution=None, device="cpu", params=None):
    directory = root / f"{exp_id}_essai"
    directory.mkdir(parents=True)
    config = {"device": device, "pipeline": {"nom": "baseline", "parametres": params or {}}}
    (directory / "config.yaml").write_text(yaml.safe_dump(config))
    if execution is not None:
        (directory / f"execution_{device}.json").write_text(json.dumps(execution))
    if rttm is not None:
        (directory / "rttm").mkdir()
        for uri, text in rttm.items():
            (directory / "rttm" / f"{uri}.rttm").write_text(text)
    return directory


SPEC = moteurs.EngineSpec("essai", "Essai", "baseline", "EXP-0099", moteurs.BASELINE_STEPS, True, False)
RTTM = (
    "SPEAKER ami__ES2004a 1 0.500 3.000 <NA> <NA> SPK_00 <NA> <NA>\n"
    "SPEAKER ami__ES2004a 1 4.000 4.000 <NA> <NA> SPK_01 <NA> <NA>\n"
    "SPEAKER ami__ES2004a 1 12.000 3.000 <NA> <NA> SPK_02 <NA> <NA>\n"
)


def test_quatre_moteurs_proposes():
    assert set(moteurs.SPECS) == {"baseline-mfcc", "baseline-ecapa", "baseline-wespeaker", "pyannote-community-1"}
    assert [s.supports_range for s in moteurs.SPECS.values()] == [False, False, False, True]


def test_etapes_annoncees_par_la_baseline():
    rng = np.random.default_rng(0)
    waveform = torch.from_numpy((0.1 * rng.standard_normal(3 * SR)).astype(np.float32)).unsqueeze(0)
    steps = []
    Baseline(theta=1.0).run(waveform, SR, progress=lambda step, fraction: steps.append(step))
    assert tuple(dict.fromkeys(steps)) == moteurs.BASELINE_STEPS


def test_parametres_repris_des_experiences_sources():
    mfcc = moteurs.engine_params(moteurs.SPECS["baseline-mfcc"])
    ecapa = moteurs.engine_params(moteurs.SPECS["baseline-ecapa"])
    assert isinstance(mfcc["theta"], float) and "representation" not in mfcc
    assert ecapa["representation"] == "ecapa" and isinstance(ecapa["theta"], float)
    assert moteurs.engine_params(moteurs.SPECS["pyannote-community-1"]) == {}
    assert moteurs.source_device(moteurs.SPECS["pyannote-community-1"]) == "mps"


def test_source_wespeaker_exp_0015(tmp_path):
    spec = moteurs.SPECS["baseline-wespeaker"]
    assert spec.source_exp == "EXP-0015"
    # Indisponible tant qu'EXP-0015 n'existe pas.
    with pytest.raises(moteurs.EngineUnavailable, match="n'existe pas encore"):
        moteurs.engine_params(spec, tmp_path)


def test_message_si_modele_absent_du_cache():
    from huggingface_hub.errors import LocalEntryNotFoundError

    spec = moteurs.SPECS["pyannote-community-1"]
    try:
        try:
            raise LocalEntryNotFoundError("absent du cache")
        except LocalEntryNotFoundError as cause:
            raise RuntimeError("chargement impossible") from cause
    except RuntimeError as error:
        message = moteurs.missing_model_message(error, spec)
    assert "absent du cache local" in message and "HF_HUB_OFFLINE=1" in message
    assert "scripts/prefetch_models.py" in message
    assert moteurs.missing_model_message(ValueError("autre"), spec) is None


def test_moteur_indisponible_sans_execution(tmp_path):
    fake_experiment(tmp_path)
    with pytest.raises(moteurs.EngineUnavailable, match="pas encore"):
        moteurs.engine_params(SPEC, tmp_path)
    with pytest.raises(moteurs.EngineUnavailable, match="RTTM"):
        moteurs.FakeEngine(SPEC, tmp_path)
    with pytest.raises(moteurs.EngineUnavailable, match="n'existe pas encore"):
        moteurs.engine_params(SPEC, tmp_path / "vide")


def test_theta_retenu_par_le_balayage(tmp_path):
    fake_experiment(tmp_path, execution={"balayage": {"parametre": "theta", "valeur_retenue": 0.7}},
                    params={"representation": "ecapa"})
    assert moteurs.engine_params(SPEC, tmp_path) == {"representation": "ecapa", "theta": 0.7}


def test_recherche_du_rttm(tmp_path):
    directory = fake_experiment(tmp_path, rttm={"ami__ES2004a": RTTM, "ami__ES2004b": RTTM}) / "rttm"
    assert moteurs.find_rttm(directory, "ami__ES2004a").name == "ami__ES2004a.rttm"
    assert moteurs.find_rttm(directory, "ES2004a").name == "ami__ES2004a.rttm"
    (directory / "summre__ES2004a.rttm").write_text(RTTM)
    with pytest.raises(FileNotFoundError, match="ambigu"):
        moteurs.find_rttm(directory, "ES2004a")
    with pytest.raises(FileNotFoundError, match="aucun RTTM"):
        moteurs.find_rttm(directory, "inconnu")


def test_moteur_factice_respecte_le_contrat(tmp_path):
    fake_experiment(tmp_path, rttm={"ami__ES2004a": RTTM})
    engine = moteurs.FakeEngine(SPEC, tmp_path, simulated_s=0.0)
    assert isinstance(engine, Engine)
    calls = []
    result = engine.run(torch.zeros(1, 10 * SR), SR, uri="ES2004a",
                        progress=lambda step, fraction: calls.append((step, fraction)))
    assert tuple(dict.fromkeys(step for step, _ in calls)) == moteurs.BASELINE_STEPS
    assert calls[-1] == ("attribution", 1.0)
    # RTTM coupé à la durée de l'audio déposé (10 s) : SPK_02 disparaît.
    assert result.annotation.uri == "ES2004a"
    assert sorted(result.annotation.labels()) == ["SPK_00", "SPK_01"]
    assert set(result.durees_etapes) == set(moteurs.BASELINE_STEPS)
    assert result.infos["rttm_source"].endswith("ami__ES2004a.rttm")
    assert engine.describe_dict()["sortie"][0]["origine"] == "code"
    with pytest.raises(ValueError):
        engine.run(torch.zeros(2, SR), SR, uri="ES2004a")


def test_surcout_fixe_mesure_pour_chaque_moteur_et_peripherique():
    """Chaque moteur a un surcoût fixe daté sur ses périphériques mesurés (CPU, et MPS pour pyannote)."""
    from datetime import date

    for key, spec in moteurs.SPECS.items():
        for device in ("cpu",) if spec.cpu_only else ("cpu", "mps"):
            overhead = moteurs.fixed_overhead(key, device)
            assert overhead is not None and overhead.seconds >= 0.0, (key, device)
            date.fromisoformat(overhead.measured_on)
    assert moteurs.fixed_overhead("pyannote-community-1", "cuda") is None
