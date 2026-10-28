"""Tests d'intégration de l'enveloppe community-1 (D18, contrat D19).

Ignorés automatiquement en l'absence de HF_TOKEN (variable d'environnement ou .env), le
modèle étant à accès restreint. Le test de reproduction d'EXP-0001 exige en plus l'audio
normalisé d'ES2004a et le périphérique MPS de l'exécution d'origine.
"""

import io
import os

import numpy as np
import pytest
import torch
from dotenv import load_dotenv

from pyannote.core import Segment, Timeline

from whospoke.audio import load_waveform
from whospoke.experiment import REPO_ROOT, processed_wav

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

    steps = []
    result = pipeline.run(synthetic_signal(), SAMPLE_RATE, uri="extrait",
                          progress=lambda step, fraction: steps.append((step, fraction)))
    annotation = result.annotation
    assert isinstance(annotation, Annotation)
    assert annotation.uri == "extrait"
    assert pipeline.speaker_mode == "estime"
    extent = annotation.get_timeline().extent() if annotation else None
    assert extent is None or extent.end <= 12.0 + 0.1
    # Rappel de progression : chaque étape atteint 1, dans l'ordre de la pipeline.
    done = list(dict.fromkeys(step for step, fraction in steps if fraction == 1.0))
    assert done == ["segmentation", "detection", "empreintes", "regroupement", "sortie"]
    assert all(0.0 <= fraction <= 1.0 for _, fraction in steps)
    assert set(result.durees_etapes) == set(done)


def test_enveloppe_refuse_mauvais_format(pipeline):
    with pytest.raises(ValueError, match="1, n"):
        pipeline.run(torch.zeros(2, SAMPLE_RATE), SAMPLE_RATE)
    with pytest.raises(ValueError, match="16000"):
        pipeline.run(torch.zeros(1, 8000), 8000)


def test_enveloppe_refuse_detection_oracle(pipeline):
    with pytest.raises(NotImplementedError, match="oracle"):
        pipeline.run(synthetic_signal(), SAMPLE_RATE, speech=Timeline([Segment(0.5, 3.5)]))


def test_enveloppe_nombre_impose_par_fichier(pipeline):
    for k in (1, 2):
        annotation = pipeline.run(synthetic_signal(), SAMPLE_RATE, num_speakers=k).annotation
        assert len(annotation.labels()) <= k
    assert pipeline.speaker_mode == "estime"  # l'appel ne change pas le mode configuré


def test_enveloppe_nombre_impose_a_la_construction(pipeline):
    pipeline.num_speakers = 2
    try:
        assert pipeline.speaker_mode == "oracle"
        annotation = pipeline.run(synthetic_signal(), SAMPLE_RATE).annotation
        assert len(annotation.labels()) <= 2
    finally:
        pipeline.num_speakers = None


def test_describe_parametres_effectifs(pipeline):
    described = {s.name: s.value for settings in pipeline.describe().values() for s in settings}
    assert described["clustering.threshold"] == pytest.approx(0.6)
    assert described["clustering.Fa"] == pytest.approx(0.07)
    assert described["clustering.Fb"] == pytest.approx(0.8)
    assert described["segmentation.duree_fenetre_s"] == pytest.approx(10.0)
    assert described["segmentation.locuteurs_par_fenetre"] == 3
    assert described["segmentation.locuteurs_simultanes"] == 2
    # Le jeton d'accès n'apparaît jamais dans la description.
    assert "hf_" not in repr(pipeline.describe_dict())


EXP_0001_RTTM = REPO_ROOT / "experiments" / "EXP-0001_pyannote-c1-ami-sdm" / "rttm" / "ami__ES2004a.rttm"


@pytest.mark.skipif(not processed_wav("ami", "ami__ES2004a").exists(), reason="audio AMI absent")
@pytest.mark.skipif(not torch.backends.mps.is_available(), reason="MPS indisponible (EXP-0001 : mps)")
def test_mode_estime_reproduit_exp_0001():
    """Mise au contrat sans changement de comportement : même RTTM qu'EXP-0001 sur ES2004a."""
    from whospoke.pipelines.pyannote_community1 import PyannoteCommunity1

    engine = PyannoteCommunity1(device="mps")
    waveform, sample_rate = load_waveform(processed_wav("ami", "ami__ES2004a"))
    annotation = engine.run(waveform, sample_rate, uri="ami__ES2004a").annotation
    buffer = io.StringIO()
    annotation.write_rttm(buffer)
    assert buffer.getvalue() == EXP_0001_RTTM.read_text()
