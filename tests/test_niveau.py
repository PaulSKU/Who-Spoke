"""Normalisation du niveau en entrée (D29 §1 ; whospoke.niveau) et sa clé dans run_experiment."""

import importlib.util

import numpy as np
import pytest
import torch

from whospoke.experiment import REPO_ROOT
from whospoke.niveau import integrated_loudness, normalize_level

spec = importlib.util.spec_from_file_location("run_experiment", REPO_ROOT / "scripts" / "run_experiment.py")
run_experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_experiment)


def sine(amplitude, seconds=5.0, rate=48000, freq=997.0):
    t = np.arange(int(seconds * rate)) / rate
    return amplitude * np.sin(2 * np.pi * freq * t)


def test_valeurs_de_reference_bs1770():
    """Sinus à 997 Hz de pleine échelle : −3,01 LUFS (BS.1770-4, mono) ; −20 dB : −23,01."""
    assert integrated_loudness(sine(1.0), 48000) == pytest.approx(-3.01, abs=0.01)
    assert integrated_loudness(sine(0.1), 48000) == pytest.approx(-23.01, abs=0.01)
    assert integrated_loudness(sine(0.1, rate=16000), 16000) == pytest.approx(-23.01, abs=0.1)


def test_portes_ecartent_le_silence():
    loud = sine(0.1, seconds=4.0, rate=16000)
    with_silence = np.concatenate([loud, np.zeros(16000 * 20)])
    assert integrated_loudness(with_silence, 16000) == pytest.approx(integrated_loudness(loud, 16000), abs=0.2)
    assert integrated_loudness(np.zeros(16000 * 3), 16000) is None


def test_gain_lineaire_et_garde_de_crete():
    x = torch.from_numpy(sine(0.01, rate=16000).astype(np.float32)).unsqueeze(0)
    y, info = normalize_level(x, 16000, -23.0)
    assert info["gain_db"] == pytest.approx(20.0, abs=0.15) and info["gain_reduit_db"] == 0.0
    assert integrated_loudness(y[0].double().numpy(), 16000) == pytest.approx(-23.0, abs=0.05)
    nonzero = np.abs(x.numpy()) > 1e-4
    ratio = y.numpy()[nonzero] / x.numpy()[nonzero]
    assert ratio.std() / ratio.mean() < 1e-5                                   # un seul gain linéaire
    assert ratio.mean() == pytest.approx(10 ** (info["gain_db"] / 20), rel=1e-3)  # gain consigné arrondi
    z, info = normalize_level(x, 16000, 0.0)                     # crête limitée à −1 dBFS
    assert float(z.abs().max()) == pytest.approx(10 ** (-1 / 20), rel=1e-3) and info["gain_reduit_db"] > 0
    silent, info = normalize_level(torch.zeros(1, 16000 * 3), 16000, -23.0)
    assert info["sonie_lufs"] is None and torch.equal(silent, torch.zeros(1, 16000 * 3))


def test_cle_de_configuration():
    assert run_experiment.level_step({}) is None
    step = run_experiment.level_step({"normalisation_niveau": {"methode": "bs1770", "cible_lufs": -29.3}})
    x = torch.from_numpy(sine(0.01, rate=16000).astype(np.float32)).unsqueeze(0)
    _, info = step(x, 16000)
    assert set(info) == {"niveau_sonie_lufs", "niveau_gain_db", "niveau_gain_reduit_db"}
    with pytest.raises(SystemExit):
        run_experiment.level_step({"normalisation_niveau": {"methode": "rms", "cible_lufs": -20}})
