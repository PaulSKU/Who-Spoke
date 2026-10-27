"""Entrée audio unique du projet (D15, D16).

Tout audio entrant suit le même chemin : normalisation par l'exécutable ffmpeg, en
sous-processus, vers un WAV PCM 16 bits, 16 kHz, mono ; puis lecture en Python et
passage d'un signal en mémoire aux pipelines. Seul l'exécutable `ffmpeg` est requis,
et non ses bibliothèques partagées (torchcodec n'est pas utilisé).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import torch
from scipy.io import wavfile

SAMPLE_RATE = 16000


class AudioError(RuntimeError):
    """Échec de normalisation ou fichier qui ne respecte pas le format normalisé."""


def normalize(
    src: str | Path,
    dst: str | Path,
    duration: float | None = None,
    ffmpeg: str = "ffmpeg",
) -> Path:
    """Convertit `src` (tout format lu par ffmpeg) en WAV PCM 16 bits, 16 kHz, mono.

    `duration` (s) tronque la sortie, par exemple pour un extrait de préchauffage.
    Le code de retour de ffmpeg est contrôlé : un échec lève `AudioError` avec la fin
    de la sortie d'erreur, et aucun fichier partiel n'est laissé à `dst`.
    """
    src, dst = Path(src), Path(dst)
    if not src.is_file():
        raise AudioError(f"Fichier source introuvable : {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".part.wav")
    command = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src)]
    if duration is not None:
        command += ["-t", str(duration)]
    command += ["-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(tmp)]
    try:
        completed = subprocess.run(command, capture_output=True, text=True)
    except FileNotFoundError as error:
        raise AudioError(f"Exécutable ffmpeg introuvable : {ffmpeg!r}") from error
    if completed.returncode != 0 or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        raise AudioError(
            f"ffmpeg a échoué sur {src} (code {completed.returncode}) : "
            f"{completed.stderr.strip()[-2000:]}"
        )
    tmp.replace(dst)
    return dst


def load_waveform(path: str | Path) -> tuple[torch.Tensor, int]:
    """Lit un WAV normalisé et renvoie (signal (1, n) float32 dans [-1, 1], 16000).

    Lève `AudioError` si le fichier n'est pas en PCM 16 bits, 16 kHz, mono : la
    normalisation doit avoir eu lieu avant (`normalize`).
    """
    path = Path(path)
    try:
        sample_rate, data = wavfile.read(path)
    except (OSError, ValueError) as error:
        raise AudioError(f"Lecture WAV impossible : {path} ({error})") from error
    if sample_rate != SAMPLE_RATE:
        raise AudioError(f"{path} : {SAMPLE_RATE} Hz attendus, {sample_rate} Hz trouvés")
    if data.ndim != 1:
        raise AudioError(f"{path} : mono attendu, {data.shape[1]} canaux trouvés")
    if data.dtype != np.int16:
        raise AudioError(f"{path} : PCM 16 bits attendu, {data.dtype} trouvé")
    waveform = torch.from_numpy(data.astype(np.float32) / 32768.0).unsqueeze(0)
    return waveform, int(sample_rate)


def as_pipeline_input(waveform: torch.Tensor, sample_rate: int) -> dict:
    """Dictionnaire d'entrée en mémoire accepté par les pipelines pyannote (D16)."""
    return {"waveform": waveform, "sample_rate": sample_rate}
