"""Contrat commun des moteurs de diarisation (D19 §1, D17).

Chaque moteur charge ses modèles une seule fois à la construction, puis traite des
signaux en mémoire (D16) par `run(waveform, sample_rate, uri, num_speakers, speech,
progress)`, qui renvoie un `Resultat`. `describe()` renvoie la configuration effective,
étape par étape : pour chaque réglage, son nom, sa valeur et son origine. Le texte
explicatif de chaque réglage (libellé, effet, composante du DER, décision) vient du
catalogue `catalogue.yaml`, jamais du moteur.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import torch
import yaml
from pyannote.core import Annotation, Timeline

from whospoke.audio import SAMPLE_RATE

CATALOGUE_PATH = Path(__file__).with_name("catalogue.yaml")

SPEAKER_MODES = ("estime", "borne", "oracle")

# Origine d'un réglage dans describe().
ORIGINS = (
    "experience",  # fixé par la configuration de l'expérience (ou par son balayage)
    "defaut",      # valeur par défaut du moteur (fiche D19 pour la baseline, pipeline pré-entraînée pour pyannote)
    "modele",      # lu dans les spécifications d'un modèle pré-entraîné
    "code",        # imposé par le code, non réglable
)

Progress = Callable[[str, float], None]


@dataclass
class Setting:
    """Un réglage effectif : nom (clé du catalogue), valeur et origine."""

    name: str
    value: object
    origin: str

    def __post_init__(self) -> None:
        if self.origin not in ORIGINS:
            raise ValueError(f"Origine inconnue : {self.origin!r}")

    def as_dict(self) -> dict:
        return {"nom": self.name, "valeur": self.value, "origine": self.origin}


@dataclass
class Resultat:
    """Sortie d'un moteur : annotation, durée par étape (s) et trace facultative."""

    annotation: Annotation
    durees_etapes: dict[str, float] = field(default_factory=dict)
    trace: dict | None = None


def load_catalogue(path: Path = CATALOGUE_PATH) -> dict:
    return yaml.safe_load(path.read_text())


class Engine(ABC):
    """Moteur de diarisation au contrat D19."""

    name: str

    def __init__(self, speaker_mode: str | None = None, trace: bool = False) -> None:
        if speaker_mode is not None and speaker_mode not in SPEAKER_MODES:
            raise ValueError(f"Mode du nombre de locuteurs inconnu : {speaker_mode!r}")
        self._speaker_mode = speaker_mode
        self.trace = trace

    @property
    def speaker_mode(self) -> str:
        """`estime`, `borne` ou `oracle`, d'après la configuration de l'expérience."""
        return self._speaker_mode or "estime"

    @staticmethod
    def check_input(waveform: torch.Tensor, sample_rate: int) -> None:
        if waveform.ndim != 2 or waveform.shape[0] != 1:
            raise ValueError(f"Signal (1, n) attendu, reçu {tuple(waveform.shape)}")
        if sample_rate != SAMPLE_RATE:
            raise ValueError(f"{SAMPLE_RATE} Hz attendus, {sample_rate} Hz reçus")

    @abstractmethod
    def run(
        self,
        waveform: torch.Tensor,
        sample_rate: int = SAMPLE_RATE,
        uri: str | None = None,
        num_speakers: int | None = None,
        speech: Timeline | None = None,
        progress: Progress | None = None,
    ) -> Resultat:
        """Diarise un signal (1, n) à 16 kHz.

        `num_speakers` impose le nombre de locuteurs de ce fichier ; `speech` impose les
        régions de parole (détection oracle) ; `progress(étape, fraction)` est appelé au
        fil du traitement.
        """

    @abstractmethod
    def describe(self) -> dict[str, list[Setting]]:
        """Configuration effective, par étape (clés : étapes du catalogue)."""

    def describe_dict(self) -> dict[str, list[dict]]:
        """describe() sérialisable (JSON, YAML)."""
        return {step: [s.as_dict() for s in settings] for step, settings in self.describe().items()}

    def synchronize(self) -> None:
        """Attend la fin des calculs asynchrones (mesure à l'horloge murale)."""
