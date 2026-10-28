"""Test d'intégration de l'enveloppe community-1 sur un extrait court (D18).

Ignoré automatiquement en l'absence de HF_TOKEN (variable d'environnement ou .env), le
modèle étant à accès restreint.
"""

import os

import numpy as np
import pytest
import torch
from dotenv import load_dotenv

from whospoke.experiment import REPO_ROOT

load_dotenv(REPO_ROOT / ".env")
pytestmark = pytest.mark.skipif(not os.environ.get("HF_TOKEN"), reason="HF_TOKEN absent")

SAMPLE_RATE = 16000


def synthetic_signal(seconds=12.0):
    """Deux « voix » synthétiques alternées (sons harmoniques modulés) séparées de silences."""
    rng = np.random.default_rng(0)
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    signal = np.zeros_like(t)
    for start, f0 in ((0.5, 120.0), (4.5, 220.0), (8.5, 120.0)):
        mask = (t >= start) & (t < start + 3.0)
        tone = sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 6))
        signal[mask] = 0.3 * tone[mask] * (1 + 0.5 * np.sin(2 * np.pi * 4 * t[mask]))
    signal += 0.003 * rng.standard_normal(len(t))
    return torch.from_numpy(signal.astype(np.float32)).unsqueeze(0)


@pytest.fixture(scope="module")
def pipeline():
    from whospoke.pipelines.pyannote_community1 import PyannoteCommunity1

    return PyannoteCommunity1(device="cpu")


def test_enveloppe_signal_en_memoire(pipeline):
    from pyannote.core import Annotation

    annotation = pipeline(synthetic_signal(), SAMPLE_RATE, uri="extrait")
    assert isinstance(annotation, Annotation)
    assert annotation.uri == "extrait"
    assert pipeline.speaker_mode == "estime"
    extent = annotation.get_timeline().extent() if annotation else None
    assert extent is None or extent.end <= 12.0 + 0.1


def test_enveloppe_refuse_mauvais_format(pipeline):
    with pytest.raises(ValueError, match="1, n"):
        pipeline(torch.zeros(2, SAMPLE_RATE), SAMPLE_RATE)
    with pytest.raises(ValueError, match="16000"):
        pipeline(torch.zeros(1, 8000), 8000)


def test_enveloppe_nombre_impose(pipeline):
    pipeline.num_speakers = 2
    try:
        assert pipeline.speaker_mode == "oracle"
        annotation = pipeline(synthetic_signal(), SAMPLE_RATE)
        assert len(annotation.labels()) <= 2
    finally:
        pipeline.num_speakers = None
