"""Représentation neuronale de la baseline (D22) sur signaux synthétiques.

Les tests du découpage, des fenêtres trop courtes et de la normalisation utilisent un
modèle d'empreintes factice ; ceux des vrais modèles (ECAPA, WeSpeaker) vérifient leur
chargement, leur dimension et la séparation de deux voix synthétiques très différentes.
"""

import os

import numpy as np
import pytest
from dotenv import load_dotenv
from pyannote.core import Segment, Timeline

from test_baseline import SR, as_tensor, high_voice, low_voice, silence, two_speakers
from whospoke.experiment import REPO_ROOT
from whospoke.pipelines import baseline as baseline_module
from whospoke.pipelines.baseline import Baseline

load_dotenv(REPO_ROOT / ".env")


class FakeEmbedder:
    """Empreinte = (énergie sous 1 kHz, énergie au-dessus de 3 kHz, 1) ; NaN sous min_samples."""

    def __init__(self, model, device=None):
        import torch

        self.model, self.device = model, torch.device("cpu")
        self.min_samples, self.dimension = 4000, 3
        self.checkpoint, self.architecture = "factice", "Fake"
        self.calls = []

    def embed(self, signals):
        self.calls.append([len(s) for s in signals])
        out = np.full((len(signals), self.dimension), np.nan)
        for i, s in enumerate(signals):
            if len(s) >= self.min_samples:
                spectrum = np.abs(np.fft.rfft(s)) ** 2
                freqs = np.fft.rfftfreq(len(s), 1 / SR)
                out[i] = [spectrum[freqs < 1000].sum(), spectrum[freqs > 3000].sum(), 1.0]
        return out

    def synchronize(self):
        pass


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(baseline_module, "SpeakerEmbedder", FakeEmbedder)


def test_signal_des_seules_trames_de_parole(fake):
    engine = Baseline(representation="ecapa", theta=1.0)
    y = np.arange(3 * SR, dtype=np.float32)
    speech = np.zeros(301, dtype=bool)
    speech[50:100] = True    # 0,5 à 1,0 s
    speech[150:200] = True   # 1,5 à 2,0 s
    (signal,) = engine.speech_signals(y, speech, np.array([[0.0, 3.0]]))
    assert len(signal) == SR  # 2 × 0,5 s, trous retirés
    assert signal[0] == pytest.approx(0.495 * SR) and signal[-1] == pytest.approx(1.995 * SR - 1)
    (inner,) = engine.speech_signals(y, speech, np.array([[0.6, 0.8]]))
    assert len(inner) == int(0.2 * SR) and inner[0] == 0.6 * SR  # bornée à la fenêtre


def test_fenetres_trop_courtes_retirees_et_comptees(fake):
    """Deux régions de 3 s (4 fenêtres chacune) et une de 0,22 s (fenêtre unique, sous les
    4 000 échantillons du modèle factice), en détection oracle : seule la dernière est retirée."""
    rng = np.random.default_rng(0)
    y = np.concatenate([silence(1.0, rng), low_voice(3.0, rng), silence(1.0, rng),
                        high_voice(3.0, rng), silence(1.0, rng)])
    speech = Timeline([Segment(1.0, 4.0), Segment(5.0, 8.0), Segment(8.5, 8.72)])
    engine = Baseline(representation="ecapa", theta=1.0, min_region_s=0.2)
    result = engine.run(as_tensor(y), SR, speech=speech, num_speakers=2)
    assert result.infos["fenetres_trop_courtes"] == 1
    assert result.infos["fenetres"] == 4 + 4
    # Les trames de la fenêtre retirée prennent l'étiquette de la fenêtre retenue la plus proche.
    assert result.annotation.get_timeline().support().duration() == pytest.approx(3 + 3 + 0.22, abs=0.03)


def test_deux_voix_separees_avec_empreintes_factices(fake):
    waveform, turns = two_speakers()
    annotation = Baseline(representation="ecapa", theta=1.0).run(waveform, SR, num_speakers=2).annotation
    labels = [annotation.argmax(Segment(start + 0.5, end - 0.5)) for start, end, _ in turns]
    assert labels[0] == labels[2] != labels[1] == labels[3]


@pytest.mark.parametrize("normalisation", ["fichier", "l2"])
def test_normalisation(fake, normalisation):
    engine = Baseline(representation="ecapa", theta=1.0, normalisation=normalisation)
    rng = np.random.default_rng(1)
    y = rng.standard_normal(4 * SR).astype(np.float32)
    windows = np.array([[0.0, 1.5], [1.0, 2.5], [2.0, 3.5], [3.0, 3.1]])
    features = engine.embed(y, np.ones(401, dtype=bool), windows)
    assert np.isnan(features[3]).all()  # 0,1 s < 4 000 échantillons
    kept = features[:3]
    if normalisation == "l2":
        assert np.linalg.norm(kept, axis=1) == pytest.approx(1.0)
    else:
        assert kept.mean(axis=0) == pytest.approx(0.0, abs=1e-9)


def test_representation_inconnue_refusee():
    with pytest.raises(ValueError, match="Représentation"):
        Baseline(representation="xvector")
    with pytest.raises(ValueError, match="Normalisation"):
        Baseline(normalisation="max")


def test_mfcc_inchange_et_cpu_seul():
    engine = Baseline(theta=1.0)
    assert engine.embedder is None
    assert [s.name for s in engine.describe()["representation"]] == ["representation"]
    with pytest.raises(ValueError, match="CPU"):
        Baseline(device="mps")


def check_real_model(model, dimension):
    engine = Baseline(representation=model, device="cpu", theta=1.0)
    assert engine.embedder.dimension == dimension
    assert 0 < engine.embedder.min_samples < SR // 2
    waveform, turns = two_speakers()
    result = engine.run(waveform, SR, num_speakers=2)
    labels = [result.annotation.argmax(Segment(start + 0.5, end - 0.5)) for start, end, _ in turns]
    assert labels[0] == labels[2] != labels[1] == labels[3]
    assert result.infos["fenetres_trop_courtes"] == 0
    names = [s.name for s in engine.describe()["representation"]]
    assert names[:2] == ["representation", "empreintes.modele"]


@pytest.mark.modele
def test_ecapa():
    check_real_model("ecapa", 192)


@pytest.mark.skipif(not os.environ.get("HF_TOKEN"), reason="HF_TOKEN absent")
def test_wespeaker():
    check_real_model("wespeaker", 256)
