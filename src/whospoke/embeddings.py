"""Empreintes vocales neuronales pour la représentation de la baseline (D22).

Deux modèles pré-entraînés, chargés une seule fois à la construction :

- `ecapa` : ECAPA-TDNN de SpeechBrain (`speechbrain/spkrec-ecapa-voxceleb`), dimension 192 ;
- `wespeaker` : empreintes de pyannote community-1 (`WeSpeakerResNet34`, sous-dossier
  `embedding`), dimension 256, c'est-à-dire la même représentation que pyannote.

Les deux attendent un signal à 16 kHz mono. `embed(signals)` prend une liste de signaux
1-D (les seules trames de parole de chaque fenêtre, mises bout à bout par l'appelant) et
renvoie une matrice (n, dimension), dans l'ordre. Les signaux de même longueur sont traités
par lots, sans aucun complément de zéros : le résultat d'un signal ne dépend pas des autres.
Lots de 8 : en CPU, au-delà, le temps par signal d'ECAPA est multiplié par 30 (mesuré le
31/10/2026 : 18 ms par fenêtre de 1,5 s en lots de 8, 680 ms en lots de 16).

Périphérique : sur le MPS de la machine principale (torch 2.14.1), les deux modèles
renvoient par intermittence des NaN pour une même entrée, ce qui n'arrive jamais en CPU
(constaté le 31/10/2026) ; une empreinte non finie lève donc une erreur.

Un signal plus court que `min_samples` (longueur minimale que le modèle accepte, mesurée
au chargement par essais sur bruit blanc) n'est pas traité : sa ligne vaut NaN, et c'est à
l'appelant de le signaler (D22 : ni ignoré silencieusement, ni complété).
"""

from __future__ import annotations

import numpy as np
import torch

from whospoke.audio import SAMPLE_RATE
from whospoke.device import select_device

ECAPA_SOURCE = "speechbrain/spkrec-ecapa-voxceleb"
ECAPA_REVISION = "0f99f2d0ebe89ac095bcc5903c4dd8f72b367286"
WESPEAKER_SOURCE = "pyannote/speaker-diarization-community-1"
WESPEAKER_REVISION = "3533c8cf8e369892e6b79ff1bf80f7b0286a54ee"
EMBEDDING_MODELS = ("ecapa", "wespeaker")


class SpeakerEmbedder:
    """Modèle d'empreintes chargé une fois sur un périphérique."""

    def __init__(self, model: str, device: str | None = "auto", batch_size: int = 8) -> None:
        if model not in EMBEDDING_MODELS:
            raise ValueError(f"Modèle d'empreintes inconnu : {model!r} (attendu : {', '.join(EMBEDDING_MODELS)})")
        self.model = model
        self.device = select_device(device)
        self.batch_size = batch_size
        if model == "ecapa":
            from speechbrain.inference.speaker import EncoderClassifier
            from speechbrain.utils.fetching import FetchConfig

            self._net = EncoderClassifier.from_hparams(
                source=ECAPA_SOURCE, run_opts={"device": str(self.device)},
                fetch_config=FetchConfig(revision=ECAPA_REVISION),
            )
            self._net.eval()
            self.checkpoint = f"{ECAPA_SOURCE}@{ECAPA_REVISION}"
            self.architecture = "ECAPA_TDNN"
        else:
            from pyannote.audio import Model

            from whospoke.pipelines.pyannote_community1 import _hf_token

            net = Model.from_pretrained(WESPEAKER_SOURCE, subfolder="embedding",
                                        revision=WESPEAKER_REVISION, token=_hf_token())
            if net is None:
                raise RuntimeError(f"Chargement de {WESPEAKER_SOURCE}/embedding impossible")
            self._net = net.eval().to(self.device)
            self.checkpoint = f"{WESPEAKER_SOURCE}/embedding@{WESPEAKER_REVISION}"
            self.architecture = type(net).__name__
        self.dimension = int(self._forward(torch.randn(1, SAMPLE_RATE)).shape[1])
        self.min_samples = self._min_samples()

    @torch.inference_mode()
    def _forward(self, batch: torch.Tensor) -> torch.Tensor:
        """(B, n) sur CPU → (B, dimension) sur CPU, en float64 non normalisé."""
        batch = batch.to(self.device, dtype=torch.float32)
        if self.model == "ecapa":
            out = self._net.encode_batch(batch).squeeze(1)
        else:
            out = self._net(batch.unsqueeze(1))
        return out.detach().to("cpu", dtype=torch.float64)

    def _accepts(self, n: int) -> bool:
        generator = torch.Generator().manual_seed(0)
        try:
            out = self._forward(torch.randn(1, n, generator=generator))
        except RuntimeError:
            return False
        return bool(torch.isfinite(out).all())

    def _min_samples(self) -> int:
        """Plus petite longueur acceptée (recherche dichotomique entre 1 et 1 s)."""
        low, high = 1, SAMPLE_RATE
        if not self._accepts(high):
            raise RuntimeError(f"{self.model} : 1 s de signal refusée")
        while low < high:
            mid = (low + high) // 2
            if self._accepts(mid):
                high = mid
            else:
                low = mid + 1
        return high

    def synchronize(self) -> None:
        if self.device.type == "mps":
            torch.mps.synchronize()
        elif self.device.type == "cuda":
            torch.cuda.synchronize()

    def embed(self, signals: list[np.ndarray]) -> np.ndarray:
        """Empreintes (n, dimension) ; NaN pour un signal plus court que `min_samples`."""
        out = np.full((len(signals), self.dimension), np.nan)
        by_length: dict[int, list[int]] = {}
        for index, signal in enumerate(signals):
            if len(signal) >= self.min_samples:
                by_length.setdefault(len(signal), []).append(index)
        for length in sorted(by_length):
            indices = by_length[length]
            for k in range(0, len(indices), self.batch_size):
                chunk = indices[k:k + self.batch_size]
                batch = torch.from_numpy(np.stack([signals[i] for i in chunk]).astype(np.float32))
                values = self._forward(batch).numpy()
                if not np.isfinite(values).all():
                    raise RuntimeError(f"{self.model} sur {self.device.type} : empreinte non finie "
                                       f"pour un signal de {length} échantillons")
                out[chunk] = values
        return out
