"""Baseline MFCC sur signaux synthétiques (D19 §2) : détection, regroupement, attribution."""

import numpy as np
import pytest
import torch
from pyannote.core import Segment, Timeline
from scipy.signal import butter, sosfilt

from whospoke.pipelines.baseline import Baseline, save_trace

SR = 16000


def as_tensor(y):
    return torch.from_numpy(np.asarray(y, dtype=np.float32)).unsqueeze(0)


def silence(seconds, rng):
    return 3e-3 * rng.standard_normal(int(seconds * SR))


def envelope(n, rng):
    """Enveloppe syllabique de 4 à 6 Hz, de phase aléatoire."""
    x = np.arange(n) / SR
    return 0.6 + 0.4 * np.sin(2 * np.pi * rng.uniform(4, 6) * x + rng.uniform(0, 6))


def low_voice(seconds, rng):
    """Son harmonique grave (f0 ≈ 120 Hz), filtré sous 1 kHz."""
    n = int(seconds * SR)
    x = np.arange(n) / SR
    phase = 2 * np.pi * np.cumsum(120 * (1 + 0.05 * np.sin(2 * np.pi * 0.7 * x))) / SR
    sos = butter(4, 1000, btype="low", fs=SR, output="sos")
    return 0.3 * sosfilt(sos, sum(np.sin(k * phase) / k for k in range(1, 15))) * envelope(n, rng)


def high_voice(seconds, rng):
    """Bruit filtré entre 3 et 6 kHz : spectre sans recouvrement avec la voix grave."""
    n = int(seconds * SR)
    sos = butter(6, [3000, 6000], btype="band", fs=SR, output="sos")
    return 0.5 * sosfilt(sos, rng.standard_normal(n)) * envelope(n, rng)


def two_speakers():
    """A, B, A, B de 3 s chacun, séparés de silences ; renvoie le signal et les tours."""
    rng = np.random.default_rng(0)
    parts, turns, t = [silence(1.0, rng)], [], 1.0
    for index, voice in enumerate((low_voice, high_voice, low_voice, high_voice)):
        parts.append(voice(3.0, rng))
        turns.append((t, t + 3.0, "AB"[index % 2]))
        t += 3.0
        parts.append(silence(0.5 if index < 3 else 1.0, rng))
        t += 0.5
    return as_tensor(np.concatenate(parts)), turns


def test_detection_frontieres_silence_puis_ton():
    rng = np.random.default_rng(0)
    tone = 0.5 * np.sin(2 * np.pi * 440 * np.arange(2 * SR) / SR)
    y = np.concatenate([silence(1.5, rng), tone, silence(1.5, rng)])
    engine = Baseline()
    prepared = engine.prepare(as_tensor(y), SR)
    assert prepared.regions.shape == (1, 2)
    start, end = prepared.regions[0]
    assert start == pytest.approx(1.5, abs=0.02)
    assert end == pytest.approx(3.5, abs=0.02)
    assert prepared.threshold_db is not None


def test_deux_spectres_tres_differents_donnent_deux_groupes():
    waveform, turns = two_speakers()
    annotation = Baseline(theta=1.0).run(waveform, SR, uri="synthetique").annotation
    assert len(annotation.labels()) == 2
    # Chaque tour de référence est attribué à un seul locuteur, et A ≠ B.
    labels = []
    for start, end, _ in turns:
        inside = annotation.crop(Segment(start + 0.1, end - 0.1)).labels()
        assert len(inside) == 1
        labels.append(inside[0])
    assert labels[0] == labels[2] and labels[1] == labels[3] and labels[0] != labels[1]


@pytest.mark.parametrize("k", [1, 2, 3, 4])
def test_nombre_de_locuteurs_impose_respecte(k):
    waveform, _ = two_speakers()
    engine = Baseline(theta=1.0)
    annotation = engine.run(waveform, SR, num_speakers=k).annotation
    assert len(annotation.labels()) == k


def test_fusion_des_pauses_de_200_ms_ou_moins():
    """Détection oracle sur un ton continu : pause de 0,2 s fusionnée, pause de 0,5 s gardée."""
    y = 0.3 * np.sin(2 * np.pi * 220 * np.arange(7 * SR) / SR)
    speech = Timeline([Segment(0.0, 2.0), Segment(2.2, 4.0), Segment(4.5, 6.0)])
    annotation = Baseline().run(as_tensor(y), SR, num_speakers=1, speech=speech).annotation
    turns = [(round(s.start, 3), round(s.end, 3)) for s in annotation.itersegments()]
    assert turns == [(0.0, 3.995), (4.495, 5.995)]


def test_pauses_plus_longues_non_fusionnees():
    y = 0.3 * np.sin(2 * np.pi * 220 * np.arange(5 * SR) / SR)
    speech = Timeline([Segment(0.0, 2.0), Segment(2.21, 4.0)])
    annotation = Baseline().run(as_tensor(y), SR, num_speakers=1, speech=speech).annotation
    assert len(list(annotation.itersegments())) == 2


def test_sortie_sans_chevauchement_et_balayage_coherent():
    waveform, _ = two_speakers()
    engine = Baseline(theta=0.8)
    prepared = engine.prepare(waveform, SR)
    direct = engine.run(waveform, SR).annotation
    assert direct.get_overlap().duration() == 0.0
    # finish() sur la préparation donne le même résultat que run() pour le même θ.
    assert engine.finish(prepared, theta=0.8).annotation == direct


def test_theta_requis_sans_nombre_impose():
    waveform, _ = two_speakers()
    with pytest.raises(ValueError, match="θ"):
        Baseline().run(waveform, SR)


def test_signal_silencieux():
    annotation = Baseline(theta=1.0).run(torch.zeros(1, 3 * SR), SR).annotation
    assert len(annotation) == 0


def test_trace(tmp_path):
    waveform, _ = two_speakers()
    result = Baseline(theta=1.0, trace=True).run(waveform, SR)
    trace = result.trace
    for key in ("energie_db", "seuil_db", "regions_parole", "fenetres", "representations",
                "liaison", "theta", "etiquettes_fenetres"):
        assert key in trace
    assert trace["representations"].shape == (len(trace["fenetres"]), 40)
    assert trace["liaison"].shape == (len(trace["fenetres"]) - 1, 4)
    save_trace(trace, tmp_path / "uri")
    assert (tmp_path / "uri" / "trace.npz").exists() and (tmp_path / "uri" / "trace.json").exists()
    assert Baseline(theta=1.0).run(waveform, SR).trace is None


def test_progression_et_durees():
    waveform, _ = two_speakers()
    steps = []
    result = Baseline(theta=1.0).run(waveform, SR, progress=lambda s, f: steps.append(s))
    expected = ["analyse", "normalisation_cepstrale", "detection", "segmentation",
                "representation", "regroupement", "attribution"]
    assert steps == expected
    assert set(result.durees_etapes) == set(expected)


def test_cpu_seul():
    with pytest.raises(ValueError, match="CPU"):
        Baseline(device="mps")
