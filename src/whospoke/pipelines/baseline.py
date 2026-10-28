"""Baseline classique : MFCC, détection par énergie, fenêtres fixes, regroupement agglomératif (D19 §2).

Étapes, dans l'ordre (valeurs initiales de la fiche D19) :

1. Analyse : trames de 25 ms au pas de 10 ms (trame i centrée en i × 10 ms) ; énergie
   logarithmique (dB, moyenne des carrés sur la trame) ; 20 MFCC (librosa).
2. Normalisation cepstrale : soustraction de la moyenne des MFCC sur le fichier.
3. Détection de parole : seuil = plancher + α × (niveau − plancher), avec plancher et
   niveau les 10e et 90e centiles de l'énergie ; filtre médian sur 11 trames ; les
   silences de moins de 0,2 s entre deux paroles sont comblés, puis les paroles de moins
   de 0,3 s supprimées.
4. Segmentation : fenêtres de 1,5 s au pas de 0,75 s posées sur chaque région de parole,
   bornées à leur région et gardées si au moins 50 % de leur durée nominale y tombe
   (une fenêtre ne mélange jamais deux régions ; lecture de D19 à confirmer) ; une
   région plus courte qu'une fenêtre, mais d'au moins 0,5 s, donne une fenêtre unique.
5. Représentation : moyenne et écart-type des MFCC sur la fenêtre (40 valeurs),
   centrés-réduits sur le fichier. Seules les trames de parole de la fenêtre sont
   prises en compte (lecture de D19 à confirmer).
6. Regroupement : agglomératif hiérarchique, distance cosinus, lien moyen ; coupe au
   seuil θ, ou au nombre de locuteurs s'il est donné.
7. Attribution : chaque trame de parole reçoit l'étiquette de la fenêtre dont le centre
   est le plus proche ; les tours d'un même locuteur séparés de 200 ms ou moins sont
   fusionnés. La sortie n'a pas de chevauchement, par construction.

Les étapes 1 à 5 et la matrice de liaison ne dépendent pas de θ : `prepare` les calcule
une fois, `finish` ne refait que la coupe et l'attribution (balayage de θ, D19 §4).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, replace
from pathlib import Path

import librosa
import numpy as np
import torch
from pyannote.core import Annotation, Segment, Timeline
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.ndimage import median_filter
from scipy.spatial.distance import pdist

from whospoke.audio import SAMPLE_RATE
from whospoke.pipelines.base import Engine, Progress, Resultat, Setting

_EPS = 1e-10


@dataclass(frozen=True)
class BaselineParams:
    """Réglages de la baseline ; valeurs initiales de D19 §2 (θ réglé sur dev)."""

    n_mfcc: int = 20
    n_mels: int = 40
    frame_s: float = 0.025
    hop_s: float = 0.010
    cmn: bool = True
    alpha: float = 0.3
    floor_percentile: float = 10.0
    level_percentile: float = 90.0
    median_frames: int = 11
    min_speech_s: float = 0.3
    min_silence_s: float = 0.2
    window_s: float = 1.5
    window_step_s: float = 0.75
    min_window_speech: float = 0.5
    min_region_s: float = 0.5
    metric: str = "cosine"
    linkage: str = "average"
    theta: float | None = None
    merge_gap_s: float = 0.2


@dataclass
class Prepared:
    """Ce qui ne dépend pas de θ : analyse, détection, fenêtres, représentations, liaison."""

    uri: str | None
    duration_s: float
    energy_db: np.ndarray        # (n_trames,)
    threshold_db: float | None   # None en détection oracle
    speech: np.ndarray           # (n_trames,) booléen
    regions: np.ndarray          # (n_régions, 2) en s
    windows: np.ndarray          # (n_fenêtres, 2) en s
    features: np.ndarray         # (n_fenêtres, 2 × n_mfcc), centrés-réduits
    linkage_matrix: np.ndarray   # (n_fenêtres − 1, 4), vide si moins de 2 fenêtres
    nearest_window: np.ndarray   # (n_trames,) indice de fenêtre, −1 hors parole
    durations: dict[str, float]


def _runs(mask: np.ndarray) -> list[tuple[int, int, bool]]:
    """Plages constantes d'un vecteur booléen : (début, fin exclue, valeur)."""
    if len(mask) == 0:
        return []
    change = np.flatnonzero(np.diff(mask.astype(np.int8))) + 1
    bounds = np.concatenate([[0], change, [len(mask)]])
    return [(int(a), int(b), bool(mask[a])) for a, b in zip(bounds[:-1], bounds[1:])]


class Baseline(Engine):
    """Baseline explicable de D19, au contrat commun des moteurs."""

    name = "baseline"

    def __init__(self, device: str | None = "cpu", speaker_mode: str | None = None,
                 trace: bool = False, **params) -> None:
        super().__init__(speaker_mode=speaker_mode, trace=trace)
        if device not in (None, "auto", "cpu"):
            raise ValueError("La baseline s'exécute en CPU seul (D19)")
        self.device = torch.device("cpu")
        self.params = BaselineParams(**params)
        self._defaults = BaselineParams()

    def set_param(self, name: str, value) -> None:
        """Change un réglage après construction (valeur retenue par un balayage)."""
        self.params = replace(self.params, **{name: value})

    # --- frames et temps ----------------------------------------------------------

    @property
    def _hop(self) -> int:
        return int(round(self.params.hop_s * SAMPLE_RATE))

    @property
    def _frame(self) -> int:
        return int(round(self.params.frame_s * SAMPLE_RATE))

    def _frames(self, seconds: float) -> int:
        return int(round(seconds / self.params.hop_s))

    def _frame_start(self, index) -> np.ndarray:
        return np.maximum(0.0, (np.asarray(index) - 0.5) * self.params.hop_s)

    def _frame_end(self, index, duration_s: float) -> np.ndarray:
        return np.minimum(duration_s, (np.asarray(index) + 0.5) * self.params.hop_s)

    # --- étapes -------------------------------------------------------------------

    def analyse(self, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(MFCC (n_trames, n_mfcc), énergie en dB (n_trames,)), trames centrées en i × pas."""
        p = self.params
        mfcc = librosa.feature.mfcc(
            y=y, sr=SAMPLE_RATE, n_mfcc=p.n_mfcc, n_fft=self._frame, hop_length=self._hop,
            win_length=self._frame, n_mels=p.n_mels, center=True, pad_mode="constant",
        ).T
        # Énergie sur les mêmes trames (signal complété de zéros comme pour les MFCC),
        # par somme cumulée des carrés pour ne pas matérialiser les trames.
        half = self._frame // 2
        padded = np.concatenate([np.zeros(half), y.astype(np.float64), np.zeros(half)])
        cumsum = np.concatenate([[0.0], np.cumsum(padded ** 2)])
        starts = np.arange(mfcc.shape[0]) * self._hop
        energy = (cumsum[starts + self._frame] - cumsum[starts]) / self._frame
        return mfcc, 10.0 * np.log10(energy + _EPS)

    def detect(self, energy_db: np.ndarray) -> tuple[np.ndarray, float]:
        """Masque de parole par seuil d'énergie, lissage médian et durées minimales."""
        p = self.params
        floor, level = np.percentile(energy_db, [p.floor_percentile, p.level_percentile])
        threshold = float(floor + p.alpha * (level - floor))
        speech = energy_db > threshold
        speech = median_filter(speech.astype(np.uint8), size=p.median_frames, mode="nearest").astype(bool)
        min_silence, min_speech = self._frames(p.min_silence_s), self._frames(p.min_speech_s)
        runs = _runs(speech)
        for k, (a, b, value) in enumerate(runs):
            inner = 0 < k < len(runs) - 1
            if not value and inner and b - a < min_silence:
                speech[a:b] = True
        for a, b, value in _runs(speech):
            if value and b - a < min_speech:
                speech[a:b] = False
        return speech, threshold

    def speech_from_timeline(self, speech: Timeline, n_frames: int) -> np.ndarray:
        """Masque de parole imposé (détection oracle) : trames dont le centre est dans une région."""
        centers = np.arange(n_frames) * self.params.hop_s
        mask = np.zeros(n_frames, dtype=bool)
        for segment in speech.support():
            mask |= (centers >= segment.start) & (centers < segment.end)
        return mask

    def regions(self, speech: np.ndarray, duration_s: float) -> np.ndarray:
        """Régions de parole (s), bornées par les intervalles des trames extrêmes."""
        rows = [(float(self._frame_start(a)), float(self._frame_end(b - 1, duration_s)))
                for a, b, value in _runs(speech) if value]
        return np.array(rows, dtype=float).reshape(-1, 2)

    def segment(self, regions: np.ndarray) -> np.ndarray:
        """Fenêtres fixes sur chaque région de parole (s), bornées à leur région.

        Une fenêtre est gardée si au moins `min_window_speech` de sa durée nominale tombe
        dans la région : une fenêtre ne mélange jamais deux régions de parole.
        """
        p = self.params
        windows = []
        for start, end in regions:
            length = end - start
            if length < p.window_s:
                if length >= p.min_region_s - 1e-9:
                    windows.append((start, end))
                continue
            k = 0
            while start + k * p.window_step_s < end - 1e-9:
                w_start = start + k * p.window_step_s
                w_end = min(w_start + p.window_s, end)
                if (w_end - w_start) / p.window_s >= p.min_window_speech - 1e-9:
                    windows.append((w_start, w_end))
                k += 1
        return np.array(windows, dtype=float).reshape(-1, 2)

    def represent(self, mfcc: np.ndarray, speech: np.ndarray, windows: np.ndarray) -> np.ndarray:
        """Moyenne et écart-type des MFCC des trames de parole de chaque fenêtre, centrés-réduits sur le fichier.

        Les fenêtres étant bornées à leur région, ce sont les trames de leur région ; le
        masque ne joue qu'en détection oracle, où une région peut contenir des trous.
        """
        centers = np.arange(mfcc.shape[0]) * self.params.hop_s
        rows = []
        for start, end in windows:
            frames = mfcc[(centers >= start) & (centers < end) & speech]
            rows.append(np.concatenate([frames.mean(axis=0), frames.std(axis=0)]))
        features = np.array(rows, dtype=float).reshape(-1, 2 * mfcc.shape[1])
        if len(features) > 1:
            std = features.std(axis=0)
            features = (features - features.mean(axis=0)) / np.where(std > 0, std, 1.0)
        return features

    def link(self, features: np.ndarray) -> np.ndarray:
        if len(features) < 2:
            return np.zeros((0, 4))
        distances = np.nan_to_num(pdist(features, metric=self.params.metric), nan=1.0)
        return linkage(distances, method=self.params.linkage)

    def cut(self, prepared: Prepared, theta: float | None, num_speakers: int | None) -> np.ndarray:
        """Étiquette (0, 1, …) de chaque fenêtre."""
        n = len(prepared.windows)
        if n == 0:
            return np.zeros(0, dtype=int)
        if n == 1:
            return np.zeros(1, dtype=int)
        if num_speakers is not None:
            if num_speakers >= n:
                return np.arange(n)
            labels = fcluster(prepared.linkage_matrix, t=num_speakers, criterion="maxclust")
        else:
            if theta is None:
                raise ValueError("θ ou le nombre de locuteurs doit être donné")
            labels = fcluster(prepared.linkage_matrix, t=theta, criterion="distance")
        return labels - 1

    def attribute(self, prepared: Prepared, window_labels: np.ndarray) -> Annotation:
        """Étiquette de la fenêtre la plus proche par trame, puis fusion des courtes pauses."""
        annotation = Annotation(uri=prepared.uri)
        if len(window_labels) == 0:
            return annotation
        frame_labels = np.where(prepared.nearest_window >= 0,
                                window_labels[np.maximum(prepared.nearest_window, 0)], -1)
        # Étiquettes renumérotées dans l'ordre d'apparition.
        order = {}
        for label in frame_labels[frame_labels >= 0]:
            order.setdefault(int(label), len(order))
        turns: list[list] = []
        change = np.flatnonzero(np.diff(frame_labels)) + 1
        bounds = np.concatenate([[0], change, [len(frame_labels)]])
        for a, b in zip(bounds[:-1], bounds[1:]):
            label = int(frame_labels[a])
            if label < 0:
                continue
            start = float(self._frame_start(a))
            end = float(self._frame_end(b - 1, prepared.duration_s))
            if turns and turns[-1][2] == label and start - turns[-1][1] <= self.params.merge_gap_s + 1e-9:
                turns[-1][1] = end
            else:
                turns.append([start, end, label])
        for start, end, label in turns:
            annotation[Segment(start, end)] = f"SPK_{order[label]:02d}"
        return annotation

    # --- contrat ------------------------------------------------------------------

    def prepare(self, waveform: torch.Tensor, sample_rate: int = SAMPLE_RATE,
                uri: str | None = None, speech: Timeline | None = None,
                progress: Progress | None = None) -> Prepared:
        """Étapes indépendantes de θ (analyse à représentation, et liaison)."""
        self.check_input(waveform, sample_rate)
        y = waveform[0].numpy().astype(np.float32)
        duration_s = len(y) / sample_rate
        durations: dict[str, float] = {}
        clock = [time.perf_counter()]

        def done(step: str) -> None:
            now = time.perf_counter()
            durations[step] = now - clock[0]
            clock[0] = now
            if progress is not None:
                progress(step, 1.0)

        mfcc, energy = self.analyse(y)
        done("analyse")
        if self.params.cmn:
            mfcc = mfcc - mfcc.mean(axis=0)
        done("normalisation_cepstrale")
        if speech is None:
            mask, threshold = self.detect(energy)
        else:
            mask, threshold = self.speech_from_timeline(speech, len(energy)), None
        regions = self.regions(mask, duration_s)
        done("detection")
        windows = self.segment(regions)
        done("segmentation")
        features = self.represent(mfcc, mask, windows)
        done("representation")
        linkage_matrix = self.link(features)
        nearest = np.full(len(mask), -1, dtype=int)
        if len(windows):
            centers = windows.mean(axis=1)
            frame_times = np.arange(len(mask)) * self.params.hop_s
            right = np.clip(np.searchsorted(centers, frame_times), 0, len(centers) - 1)
            left = np.clip(right - 1, 0, len(centers) - 1)
            closest = np.where(np.abs(frame_times - centers[left]) <= np.abs(centers[right] - frame_times),
                               left, right)
            nearest[mask] = closest[mask]
        durations["regroupement"] = time.perf_counter() - clock[0]
        return Prepared(uri, duration_s, energy, threshold, mask, regions, windows, features,
                        linkage_matrix, nearest, durations)

    def finish(self, prepared: Prepared, theta: float | None = None,
               num_speakers: int | None = None, progress: Progress | None = None) -> Resultat:
        """Coupe de la liaison et attribution (seules étapes qui dépendent de θ)."""
        durations = dict(prepared.durations)
        t0 = time.perf_counter()
        labels = self.cut(prepared, theta, num_speakers)
        durations["regroupement"] += time.perf_counter() - t0
        if progress is not None:
            progress("regroupement", 1.0)
        t0 = time.perf_counter()
        annotation = self.attribute(prepared, labels)
        durations["attribution"] = time.perf_counter() - t0
        if progress is not None:
            progress("attribution", 1.0)
        trace = None
        if self.trace:
            trace = {
                "energie_db": prepared.energy_db.astype(np.float32),
                "seuil_db": prepared.threshold_db,
                "pas_trame_s": self.params.hop_s,
                "regions_parole": prepared.regions,
                "fenetres": prepared.windows,
                "representations": prepared.features.astype(np.float32),
                "liaison": prepared.linkage_matrix,
                "theta": theta,
                "n_locuteurs_impose": num_speakers,
                "etiquettes_fenetres": labels,
            }
        return Resultat(annotation=annotation, durees_etapes=durations, trace=trace)

    def run(
        self,
        waveform: torch.Tensor,
        sample_rate: int = SAMPLE_RATE,
        uri: str | None = None,
        num_speakers: int | None = None,
        speech: Timeline | None = None,
        progress: Progress | None = None,
    ) -> Resultat:
        prepared = self.prepare(waveform, sample_rate, uri=uri, speech=speech, progress=progress)
        return self.finish(prepared, theta=self.params.theta, num_speakers=num_speakers, progress=progress)

    def describe(self) -> dict[str, list[Setting]]:
        p, d = self.params, self._defaults

        def s(name: str, value=None) -> Setting:
            value = getattr(p, name) if value is None else value
            origin = "defaut" if getattr(d, name, value) == getattr(p, name, value) else "experience"
            return Setting(name, value, origin)

        speakers = {"estime": "estimé (coupe à θ)", "oracle": "imposé par fichier",
                    "borne": "borné"}[self.speaker_mode]
        return {
            "analyse": [s("frame_s"), s("hop_s"), s("n_mfcc"), s("n_mels")],
            "normalisation_cepstrale": [s("cmn")],
            "detection": [s("alpha"), s("floor_percentile"), s("level_percentile"),
                          s("median_frames"), s("min_speech_s"), s("min_silence_s")],
            "segmentation": [s("window_s"), s("window_step_s"), s("min_window_speech"), s("min_region_s")],
            "representation": [Setting("representation", "moyenne et écart-type des MFCC des trames de parole, centrés-réduits", "code")],
            "regroupement": [s("metric"), s("linkage"),
                             Setting("theta", p.theta, "experience"),
                             Setting("n_locuteurs", speakers, "experience")],
            "attribution": [s("merge_gap_s")],
            "sortie": [Setting("sortie.chevauchement", False, "code")],
        }


def save_trace(trace: dict, directory: Path) -> None:
    """Écrit une trace : tableaux dans trace.npz, scalaires dans trace.json."""
    directory.mkdir(parents=True, exist_ok=True)
    arrays = {k: np.asarray(v) for k, v in trace.items() if isinstance(v, np.ndarray)}
    scalars = {k: v for k, v in trace.items() if k not in arrays}
    np.savez_compressed(directory / "trace.npz", **arrays)
    (directory / "trace.json").write_text(json.dumps(scalars, ensure_ascii=False, indent=2) + "\n")

