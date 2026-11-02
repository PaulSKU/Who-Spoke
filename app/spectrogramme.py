"""Vue spectrogramme de l'onglet Analyse (D28 §2), calculée côté serveur.

Le greffon Spectrogram de wavesurfer 7.12.12 ne tient pas sur 30 min à 150 px/s (gels de
0,6 à 0,9 s au défilement et à chaque pas de zoom, mesurés le 02/11 : app/README.md, B9) ;
D28 prévoit alors une image calculée côté serveur. Elle l'est ici, à résolution adaptée au
zoom : spectrogramme mel en dB sur 8 bits, puis une pyramide de résolutions (moyenne sur 2,
4, 8… trames). Le navigateur ne fait que la mise en couleurs et le découpage à la partie
visible (`visualiseur.js`), sans décoder l'audio.

Le spectrogramme est celui dont la baseline tire ses MFCC (D19) : mêmes trames (25 ms),
même pas (10 ms), mêmes 40 bandes mel, même appel à librosa (`Baseline.analyse`). On voit
ainsi ce que voit la baseline.

Palette : rampe d'encre neutre à une seule teinte, interpolée en OKLab, donc à pas de
clarté réguliers (perceptuellement uniforme), du fond des pistes à l'encre ; une rampe par
mode (D26 : la couleur reste réservée aux locuteurs).

Option de la baseline (D28 §2) : courbe d'énergie, seuil et régions de parole de sa
détection (D19), tirés de la trace du moteur (`detection_from_trace`), écrits dans un
fichier binaire à côté de l'audio normalisé.
"""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

import librosa
import numpy as np

from whospoke.audio import SAMPLE_RATE
from whospoke.pipelines.baseline import BaselineParams

RANGE_DB = 60.0          # plage affichée sous le maximum du fichier (Praat : 50 dB par défaut)
MIN_LEVEL_FRAMES = 256   # dernier niveau de la pyramide : au plus ce nombre de trames
TICKS_HZ = (500, 1000, 2000, 4000, 8000)   # 250 Hz : collé à 500 Hz sur 112 px
SUFFIX = ".spectrogramme.bin"

# Rampes du fond des pistes à l'encre (app/static/interface.css : --ws-track, --ws-ink).
RAMP_LIGHT = ("#f0f0ed", "#18191d")
RAMP_DARK = ("#232428", "#ecece9")


# --- Palette ---------------------------------------------------------------------------


def _srgb_to_linear(c: np.ndarray) -> np.ndarray:
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)


_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005]])
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660]])


def _hex_rgb(color: str) -> np.ndarray:
    return np.array([int(color[i:i + 2], 16) for i in (1, 3, 5)]) / 255.0


def to_oklab(rgb: np.ndarray) -> np.ndarray:
    """sRGB dans [0, 1] (…, 3) vers OKLab (Björn Ottosson, 2020)."""
    lms = _srgb_to_linear(np.asarray(rgb, dtype=float)) @ _M1.T
    return np.cbrt(lms) @ _M2.T


def from_oklab(lab: np.ndarray) -> np.ndarray:
    lms = (np.asarray(lab, dtype=float) @ np.linalg.inv(_M2).T) ** 3
    return _linear_to_srgb(lms @ np.linalg.inv(_M1).T)


def ramp(low: str, high: str, n: int = 256) -> list[list[int]]:
    """`n` couleurs RVB (0–255) de `low` à `high`, interpolées linéairement en OKLab."""
    a, b = to_oklab(_hex_rgb(low)), to_oklab(_hex_rgb(high))
    steps = np.linspace(0.0, 1.0, n)[:, None]
    rgb = from_oklab(a + steps * (b - a))
    return np.round(rgb * 255).astype(int).tolist()


def palettes() -> dict[str, list[list[int]]]:
    return {"clair": ramp(*RAMP_LIGHT), "sombre": ramp(*RAMP_DARK)}


# --- Spectrogramme -----------------------------------------------------------------------


def mel_power(y: np.ndarray, sample_rate: int = SAMPLE_RATE, params: BaselineParams | None = None) -> np.ndarray:
    """Spectrogramme mel en puissance (n_mels, n_trames), avec les réglages de `Baseline.analyse` :
    celui dont `librosa.feature.mfcc` tire les MFCC de la baseline ; trames centrées en i × pas."""
    p = params or BaselineParams()
    frame, hop = int(round(p.frame_s * sample_rate)), int(round(p.hop_s * sample_rate))
    return librosa.feature.melspectrogram(
        y=np.asarray(y, dtype=np.float32), sr=sample_rate, n_fft=frame, hop_length=hop, win_length=frame,
        n_mels=p.n_mels, center=True, pad_mode="constant")


def mel_db(y: np.ndarray, sample_rate: int = SAMPLE_RATE, params: BaselineParams | None = None) -> np.ndarray:
    """Spectrogramme mel en dB (n_mels, n_trames), relatif au maximum du fichier, sur RANGE_DB."""
    power = mel_power(y, sample_rate, params)
    if not np.any(power > 0):
        return np.full(power.shape, -RANGE_DB, dtype=np.float32)
    return librosa.power_to_db(power, ref=np.max, top_db=RANGE_DB).astype(np.float32)


def quantize(db: np.ndarray) -> np.ndarray:
    """dB dans [−RANGE_DB, 0] vers 0–255."""
    return np.round((np.clip(db, -RANGE_DB, 0.0) + RANGE_DB) / RANGE_DB * 255).astype(np.uint8)


def pyramid(frames: np.ndarray) -> list[np.ndarray]:
    """Niveaux (n_trames_k, n_mels) : niveau k = moyenne de 2^k trames du niveau 0."""
    levels = [frames]
    while len(levels[-1]) > MIN_LEVEL_FRAMES:
        last = levels[-1].astype(np.uint16)
        if len(last) % 2:
            last = np.concatenate([last, last[-1:]])
        levels.append(((last[0::2] + last[1::2] + 1) // 2).astype(np.uint8))
    return levels


def band_ticks(params: BaselineParams | None = None, sample_rate: int = SAMPLE_RATE) -> list[dict]:
    """Graduations de l'axe des fréquences : position verticale (0 en haut, 1 en bas) du
    centre de bande correspondant, interpolée sur l'échelle mel des bandes."""
    p = params or BaselineParams()
    centers = librosa.mel_frequencies(n_mels=p.n_mels + 2, fmax=sample_rate / 2)[1:-1]
    mels = librosa.hz_to_mel(centers)
    ticks = []
    for hz in TICKS_HZ:
        if not centers[0] <= hz <= sample_rate / 2:
            continue
        index = float(np.interp(librosa.hz_to_mel(hz), mels, np.arange(p.n_mels)))
        label = f"{hz // 1000} kHz" if hz >= 1000 else f"{hz} Hz"
        ticks.append({"hz": hz, "libelle": label, "y": round(1.0 - (index + 0.5) / p.n_mels, 4)})
    return ticks


def compute(wav: Path, y: np.ndarray, sample_rate: int = SAMPLE_RATE) -> dict:
    """Écrit le fichier binaire de la pyramide à côté de `wav` ; description pour le navigateur.

    Fichier : niveaux à la suite, chacun en octets (n_trames_k × n_mels), trame par trame,
    bande la plus grave d'abord."""
    p = BaselineParams()
    frames = quantize(mel_db(y, sample_rate, p)).T.copy()   # (n_trames, n_mels)
    levels = pyramid(frames)
    path = Path(wav).with_name(Path(wav).stem + SUFFIX)
    offsets, offset = [], 0
    with open(path, "wb") as handle:
        for level in levels:
            handle.write(np.ascontiguousarray(level).tobytes())
            offsets.append({"decalage": offset, "trames": int(len(level))})
            offset += level.nbytes
    return {
        "fichier": path, "bandes": p.n_mels, "pas_s": p.hop_s, "trame_s": p.frame_s,
        "plage_db": RANGE_DB, "niveaux": offsets, "graduations": band_ticks(p, sample_rate),
        "palettes": palettes(),
    }


# Calcul lancé dès la normalisation du fichier déposé, dans un fil à part : il est en
# général fini quand l'analyse se termine (3 s pour 30 min). Un seul calcul à la fois.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="spectrogramme")
_jobs: dict[str, Future] = {}
_lock = threading.Lock()


def start(wav: Path, y: np.ndarray, sample_rate: int = SAMPLE_RATE) -> Future:
    with _lock:
        key = str(wav)
        if key not in _jobs:
            _jobs[key] = _executor.submit(compute, Path(wav), np.asarray(y, dtype=np.float32).copy(), sample_rate)
        return _jobs[key]


def result(wav: Path, y: np.ndarray | None = None, sample_rate: int = SAMPLE_RATE) -> dict | None:
    """Description du spectrogramme de `wav` (calcul lancé s'il ne l'a pas été et que `y`
    est fourni) ; None si le calcul a échoué : la vue spectrogramme est alors indisponible."""
    with _lock:
        job = _jobs.get(str(wav))
    if job is None:
        if y is None:
            return None
        job = start(wav, y, sample_rate)
    try:
        return job.result()
    except Exception:  # vue facultative : jamais bloquante pour l'analyse
        return None


# --- Détection de parole de la baseline (D19) ---------------------------------------------


def detection_from_trace(trace: dict | None, factice: bool = False) -> dict | None:
    """Énergie (dB par trame), seuil et régions de parole tirés de la trace d'un moteur ;
    None si la trace n'en contient pas (autre moteur, détection oracle sans seuil)."""
    if not trace or trace.get("energie_db") is None or trace.get("seuil_db") is None:
        return None
    regions = np.asarray(trace.get("regions_parole", np.zeros((0, 2))), dtype=float).reshape(-1, 2)
    return {
        "energie_db": np.asarray(trace["energie_db"], dtype=np.float32),
        "seuil_db": float(trace["seuil_db"]),
        "pas_s": float(trace["pas_trame_s"]),
        "regions": [[round(float(a), 3), round(float(b), 3)] for a, b in regions],
        "factice": bool(trace.get("factice", factice)),
    }


def write_energy(detection: dict, path: Path) -> dict:
    """Écrit l'énergie (float32) dans `path` ; description pour le navigateur, sans le tableau."""
    energy = np.asarray(detection["energie_db"], dtype=np.float32)
    energy.tofile(path)
    finite = energy[np.isfinite(energy)]
    low, high = (float(np.percentile(finite, 1)), float(finite.max())) if len(finite) else (-100.0, 0.0)
    low = min(low, detection["seuil_db"] - 3.0)
    return {"fichier": path, "trames": int(len(energy)), "pas_s": detection["pas_s"],
            "seuil_db": round(detection["seuil_db"], 2), "min_db": round(low, 2), "max_db": round(high, 2),
            "regions": detection["regions"], "factice": detection["factice"]}


def encode_energy(detection: dict) -> dict:
    """Forme JSON de la détection pour le cache des résultats : énergie au dixième de dB."""
    import base64

    tenths = np.round(np.nan_to_num(detection["energie_db"], nan=-1000.0, neginf=-1000.0) * 10)
    data = np.clip(tenths, -32768, 32767).astype("<i2").tobytes()
    return {"energie_ddb": base64.b64encode(data).decode("ascii"), "seuil_db": detection["seuil_db"],
            "pas_s": detection["pas_s"], "regions": detection["regions"], "factice": detection["factice"]}


def decode_energy(entry: dict | None) -> dict | None:
    import base64

    if not entry or "energie_ddb" not in entry:
        return None
    energy = np.frombuffer(base64.b64decode(entry["energie_ddb"]), dtype="<i2").astype(np.float32) / 10
    return {"energie_db": energy, "seuil_db": float(entry["seuil_db"]), "pas_s": float(entry["pas_s"]),
            "regions": entry["regions"], "factice": bool(entry.get("factice", False))}
