"""Tests de l'entrée audio (D16) sur des fichiers synthétiques."""

import shutil
import subprocess

import numpy as np
import pytest
import torch
from scipy.io import wavfile

from whospoke.audio import SAMPLE_RATE, AudioError, load_waveform, normalize

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")


def write_stereo_44k(path, seconds=2.0):
    """Sinus de 440 Hz à gauche, 880 Hz à droite, 44,1 kHz, PCM 16 bits."""
    rate = 44100
    t = np.arange(int(rate * seconds)) / rate
    stereo = np.stack([np.sin(2 * np.pi * 440 * t), np.sin(2 * np.pi * 880 * t)], axis=1)
    wavfile.write(path, rate, (0.5 * stereo * 32767).astype(np.int16))
    return path


def test_stereo_44k_normalise(tmp_path):
    src = write_stereo_44k(tmp_path / "stereo.wav", seconds=2.0)
    dst = normalize(src, tmp_path / "out" / "norm.wav")
    waveform, rate = load_waveform(dst)
    assert rate == SAMPLE_RATE
    assert waveform.dtype == torch.float32
    assert waveform.ndim == 2 and waveform.shape[0] == 1
    assert waveform.shape[1] == pytest.approx(2 * SAMPLE_RATE, abs=SAMPLE_RATE // 100)
    assert waveform.abs().max() <= 1.0
    assert waveform.abs().max() > 0.1  # le signal n'est pas perdu


def test_m4a_normalise(tmp_path):
    src = write_stereo_44k(tmp_path / "stereo.wav", seconds=1.5)
    m4a = tmp_path / "stereo.m4a"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(src), "-c:a", "aac", str(m4a)],
        check=True,
    )
    waveform, rate = load_waveform(normalize(m4a, tmp_path / "m4a.wav"))
    assert rate == SAMPLE_RATE and waveform.shape[0] == 1
    # L'AAC ajoute un léger décalage d'encodeur : tolérance de 50 ms.
    assert waveform.shape[1] == pytest.approx(1.5 * SAMPLE_RATE, abs=0.05 * SAMPLE_RATE)


def test_duree_tronquee(tmp_path):
    src = write_stereo_44k(tmp_path / "stereo.wav", seconds=2.0)
    waveform, _ = load_waveform(normalize(src, tmp_path / "court.wav", duration=0.5))
    assert waveform.shape[1] == pytest.approx(0.5 * SAMPLE_RATE, abs=SAMPLE_RATE // 100)


def test_load_refuse_non_normalise(tmp_path):
    src = write_stereo_44k(tmp_path / "stereo.wav")
    with pytest.raises(AudioError, match="16000 Hz"):
        load_waveform(src)
    mono_8k = tmp_path / "mono8k.wav"
    wavfile.write(mono_8k, 8000, np.zeros(800, dtype=np.int16))
    with pytest.raises(AudioError, match="16000 Hz"):
        load_waveform(mono_8k)
    stereo_16k = tmp_path / "stereo16k.wav"
    wavfile.write(stereo_16k, SAMPLE_RATE, np.zeros((1600, 2), dtype=np.int16))
    with pytest.raises(AudioError, match="mono"):
        load_waveform(stereo_16k)
    float_16k = tmp_path / "float16k.wav"
    wavfile.write(float_16k, SAMPLE_RATE, np.zeros(1600, dtype=np.float32))
    with pytest.raises(AudioError, match="16 bits"):
        load_waveform(float_16k)


def test_echec_ffmpeg_controle(tmp_path):
    bad = tmp_path / "pas_un_audio.wav"
    bad.write_bytes(b"ceci n'est pas un fichier audio")
    dst = tmp_path / "sortie.wav"
    with pytest.raises(AudioError, match="ffmpeg a échoué"):
        normalize(bad, dst)
    assert not dst.exists()
    assert not list(tmp_path.glob("*.part.wav"))


def test_source_absente(tmp_path):
    with pytest.raises(AudioError, match="introuvable"):
        normalize(tmp_path / "absent.wav", tmp_path / "x.wav")
