"""Choix du périphérique de calcul (D15) : CUDA, puis MPS, puis CPU, forçable."""

from __future__ import annotations

import torch

VALID_DEVICES = ("auto", "cuda", "mps", "cpu")


def _is_available(name: str) -> bool:
    if name == "cuda":
        return torch.cuda.is_available()
    if name == "mps":
        return torch.backends.mps.is_available()
    return name == "cpu"


def select_device(requested: str | None = "auto") -> torch.device:
    """Renvoie le périphérique à utiliser.

    `requested` vaut `"auto"` (ou `None`) pour le choix automatique CUDA > MPS > CPU,
    ou force `"cuda"`, `"mps"` ou `"cpu"`. Un périphérique forcé mais indisponible
    lève une erreur plutôt que de basculer silencieusement sur un autre.
    """
    name = (requested or "auto").lower()
    if name not in VALID_DEVICES:
        raise ValueError(f"Périphérique inconnu : {requested!r} (attendu : {', '.join(VALID_DEVICES)})")
    if name == "auto":
        for candidate in ("cuda", "mps"):
            if _is_available(candidate):
                return torch.device(candidate)
        return torch.device("cpu")
    if not _is_available(name):
        raise RuntimeError(f"Périphérique {name!r} demandé mais indisponible sur cette machine")
    return torch.device(name)
