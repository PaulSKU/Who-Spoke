"""Normalisation du niveau en entrée (D29 §1, hypothèse 1 ; analyse A-0004).

Appliquée au signal déjà normalisé (D16 : 16 kHz mono), avant le moteur. Le niveau est la
sonie intégrée de la recommandation ITU-R BS.1770-4 : pondération K (filtre en plateau puis
passe-haut, dont les coefficients sont recalculés pour la fréquence d'échantillonnage à
partir des prototypes analogiques, comme dans pyloudnorm), puissance moyenne par blocs de
400 ms recouvrants à 75 %, porte absolue à −70 LUFS puis porte relative à −10 LU sous la
sonie des blocs retenus. Les portes écartent les silences : la mesure suit le niveau de la
parole sans connaître la référence, ce qu'exige un usage réel.

Le gain est linéaire et unique par fichier (aucune compression) : gain = cible − sonie. Une
garde de crête le réduit si la crête dépasserait `PEAK_MAX_DBFS` ; le gain appliqué et la
réduction éventuelle sont rendus pour être consignés. Un fichier sans bloc retenu (silence)
n'est pas modifié.
"""

from __future__ import annotations

import math

import numpy as np
import torch
from scipy.signal import lfilter

BLOCK_S = 0.4
OVERLAP = 0.75
ABSOLUTE_GATE_LUFS = -70.0
RELATIVE_GATE_LU = -10.0
PEAK_MAX_DBFS = -1.0


def k_weighting(sample_rate: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """Deux biquads de la pondération K (BS.1770-4), pour `sample_rate`."""
    # Plateau haut (effet de tête) : G = 4 dB, f0 = 1 681,97 Hz, Q = 0,7072.
    gain_db, f0, q = 3.999843853973347, 1681.974450955533, 0.7071752369554196
    k = math.tan(math.pi * f0 / sample_rate)
    vh = 10 ** (gain_db / 20.0)
    vb = vh ** 0.4996667741545416
    a0 = 1.0 + k / q + k * k
    shelf = (np.array([(vh + vb * k / q + k * k) / a0, 2.0 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0]),
             np.array([1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0]))
    # Passe-haut (RLB) : f0 = 38,14 Hz, Q = 0,5003.
    f0, q = 38.13547087602444, 0.5003270373238773
    k = math.tan(math.pi * f0 / sample_rate)
    a0 = 1.0 + k / q + k * k
    highpass = (np.array([1.0, -2.0, 1.0]),
                np.array([1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0]))
    return [shelf, highpass]


def integrated_loudness(signal: np.ndarray, sample_rate: int) -> float | None:
    """Sonie intégrée (LUFS) d'un signal mono en flottant (pleine échelle 1,0) ; None si silence."""
    weighted = np.asarray(signal, dtype=np.float64)
    for b, a in k_weighting(sample_rate):
        weighted = lfilter(b, a, weighted)
    block = int(round(BLOCK_S * sample_rate))
    step = int(round(block * (1.0 - OVERLAP)))
    if len(weighted) < block:
        return None
    squares = np.square(weighted)
    cumulative = np.concatenate([[0.0], np.cumsum(squares)])
    starts = np.arange(0, len(weighted) - block + 1, step)
    powers = (cumulative[starts + block] - cumulative[starts]) / block
    loudness = -0.691 + 10.0 * np.log10(np.maximum(powers, 1e-20))
    kept = powers[loudness > ABSOLUTE_GATE_LUFS]
    if kept.size == 0:
        return None
    relative = -0.691 + 10.0 * np.log10(kept.mean()) + RELATIVE_GATE_LU
    kept = powers[(loudness > ABSOLUTE_GATE_LUFS) & (loudness > relative)]
    return float(-0.691 + 10.0 * np.log10(kept.mean()))


def normalize_level(waveform: torch.Tensor, sample_rate: int, target_lufs: float) -> tuple[torch.Tensor, dict]:
    """Signal (1, n) ramené à la sonie cible, gain linéaire unique, garde de crête.

    Renvoie le signal et `{sonie_lufs, gain_db, gain_reduit_db}` (gain appliqué ; réduction
    imposée par la garde de crête, 0 sinon)."""
    signal = waveform[0].double().numpy()
    loudness = integrated_loudness(signal, sample_rate)
    if loudness is None:
        return waveform, {"sonie_lufs": None, "gain_db": 0.0, "gain_reduit_db": 0.0}
    gain_db = target_lufs - loudness
    peak = float(np.max(np.abs(signal)))
    reduction = 0.0
    if peak > 0:
        headroom = PEAK_MAX_DBFS - 20.0 * math.log10(peak)
        if gain_db > headroom:
            reduction, gain_db = gain_db - headroom, headroom
    scaled = (waveform.double() * 10 ** (gain_db / 20.0)).to(waveform.dtype)
    return scaled, {"sonie_lufs": round(loudness, 2), "gain_db": round(gain_db, 2),
                    "gain_reduit_db": round(reduction, 2)}
