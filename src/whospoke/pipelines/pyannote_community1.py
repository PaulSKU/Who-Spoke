"""Enveloppe de pyannote/speaker-diarization-community-1 (signal en mémoire, D16).

Aucun chemin de fichier n'est passé à la pipeline : le décodage par torchcodec n'est pas
utilisé. Le nombre de locuteurs est estimé par la pipeline sauf si `num_speakers`,
`min_speakers` ou `max_speakers` sont fournis (tous à None par défaut).
"""

from __future__ import annotations

import os
from pathlib import Path

import torch
from pyannote.core import Annotation

from whospoke.audio import SAMPLE_RATE, as_pipeline_input
from whospoke.device import select_device

MODEL_ID = "pyannote/speaker-diarization-community-1"
REPO_ROOT = Path(__file__).resolve().parents[3]


def _hf_token() -> str:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
    token = os.environ.get("HF_TOKEN") or None
    if token is None:
        raise RuntimeError("HF_TOKEN absent ou vide dans .env (modèle à accès restreint)")
    return token


class PyannoteCommunity1:
    """Charge la pipeline une fois, puis diarise des signaux (1, n) à 16 kHz."""

    name = "pyannote-community-1"

    def __init__(
        self,
        device: str | None = "auto",
        num_speakers: int | None = None,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> None:
        from pyannote.audio import Pipeline

        self.device = select_device(device)
        self.num_speakers = num_speakers
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers
        pipeline = Pipeline.from_pretrained(MODEL_ID, token=_hf_token())
        if pipeline is None:
            raise RuntimeError(f"Chargement de {MODEL_ID} impossible (accès au modèle ?)")
        pipeline.to(self.device)
        self._pipeline = pipeline

    @property
    def speaker_mode(self) -> str:
        """Mode du nombre de locuteurs consigné dans results.json."""
        if self.num_speakers is not None:
            return "oracle"
        if self.min_speakers is not None or self.max_speakers is not None:
            return "borne"
        return "estime"

    def synchronize(self) -> None:
        """Attend la fin des calculs asynchrones (mesure de temps à l'horloge murale)."""
        if self.device.type == "mps":
            torch.mps.synchronize()
        elif self.device.type == "cuda":
            torch.cuda.synchronize()

    def __call__(self, waveform: torch.Tensor, sample_rate: int = SAMPLE_RATE, uri: str | None = None) -> Annotation:
        """Diarisation d'un signal ; renvoie l'annotation avec chevauchements."""
        if waveform.ndim != 2 or waveform.shape[0] != 1:
            raise ValueError(f"Signal (1, n) attendu, reçu {tuple(waveform.shape)}")
        if sample_rate != SAMPLE_RATE:
            raise ValueError(f"{SAMPLE_RATE} Hz attendus, {sample_rate} Hz reçus")
        output = self._pipeline(
            as_pipeline_input(waveform, sample_rate),
            num_speakers=self.num_speakers,
            min_speakers=self.min_speakers,
            max_speakers=self.max_speakers,
        )
        self.synchronize()
        # pyannote.audio 4 renvoie un DiarizeOutput ; on garde la diarisation avec
        # chevauchements (et non `exclusive_speaker_diarization`), conformément au
        # protocole qui compte les chevauchements.
        annotation = getattr(output, "speaker_diarization", output)
        if uri is not None:
            annotation.uri = uri
        return annotation
