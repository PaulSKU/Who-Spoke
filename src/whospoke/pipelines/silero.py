"""Détection fine en post-traitement par Silero VAD (D25, variantes V2 et V3 ; chantier E5).

La sortie d'un moteur (pyannote en pratique) est intersectée avec le masque de parole de
Silero VAD : chaque tour est coupé là où Silero n'entend pas de voix. Les pauses que la
segmentation de pyannote a pontées sont ainsi rouvertes. Le post-traitement ne crée jamais
de parole ni de locuteur : il ne peut que retirer du temps attribué.

Le masque est construit en deux temps :

1. probabilités de parole de Silero, une par fenêtre de 512 échantillons (32 ms), calculées
   en CPU comme dans `silero_vad.get_speech_timestamps` (`speech_probabilities`) ;
2. binarisation par la fonction de Silero elle-même, `get_speech_timestamps_from_probs`
   (`speech_mask`), avec trois réglages exposés au catalogue :
   - `seuil` : probabilité à partir de laquelle une fenêtre est de la parole (Silero
     referme un tour sous `seuil − 0,15`) ;
   - `silence_min_s` : durée minimale d'un silence rouvert, marge déduite ; Silero reçoit
     `min_silence_duration_ms = silence_min_s + 2 × marge_s` ;
   - `marge_s` : marge ajoutée de part et d'autre de chaque zone de parole.
   Les autres paramètres gardent la valeur par défaut de Silero (parole d'au moins 250 ms,
   durée de tour non bornée).

Les probabilités ne dépendent d'aucun réglage : le script de réglage
(`scripts/reglage_silero.py`) les met en cache (`cache_path`) et rebinarise à chaque point
de la grille sans relancer ni Silero ni pyannote.

Dépendance. `silero-vad` (licence MIT) n'est pas encore dans uv.lock : la piste A l'ajoute
à la fusion (`uv add silero-vad==6.2.3`, sans option : l'option `audio` exige
torchaudio < 2.10). Le modèle est lu dans le paquet installé ; aucun téléchargement, aucune
télémétrie (code de la version 6.2.3 lu le 01/11/2026). Version et empreinte SHA-256 du
fichier de poids sont contrôlées au chargement (révision figée, D18).

Effet de bord neutralisé : `import silero_vad` impose `torch.set_num_threads(1)` à tout le
processus, ce qui ralentirait pyannote ; `load_model` rétablit le nombre de fils d'avant
l'import. Les probabilités sont calculées sur un seul fil, comme le prévoit Silero.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from importlib import resources
from pathlib import Path

import numpy as np
import torch
from pyannote.core import Annotation, Segment, Timeline

from whospoke.audio import SAMPLE_RATE
from whospoke.experiment import DATA_DIR
from whospoke.pipelines.base import Engine, Progress, Resultat, Setting

SILERO_VERSION = "6.2.3"
MODEL_FILE = "silero_vad.jit"
MODEL_SHA256 = "e1122837f4154c511485fe0b9c64455f7b929c96fbb8d79fbdb336383ebd3720"   # roue PyPI 6.2.3, 01/11/2026
WINDOW = 512                                   # échantillons par probabilité à 16 kHz (32 ms)
FRAME_S = WINDOW / SAMPLE_RATE
MIN_SPEECH_S = 0.25                            # min_speech_duration_ms par défaut de Silero
CACHE_TAG = f"{SILERO_VERSION}-{MODEL_SHA256[:12]}"
INSTALL_HINT = f"uv add silero-vad=={SILERO_VERSION}"

# Fonction de binarisation au format de `silero_vad.get_speech_timestamps_from_probs`.
Binarize = Callable[..., list[dict]]


class SileroMissing(RuntimeError):
    """silero-vad absent de l'environnement, ou d'une autre version que celle figée."""


@dataclass(frozen=True)
class MaskParams:
    """Réglages du masque (catalogue : `silero.seuil`, `silero.silence_min_s`, `silero.marge_s`)."""

    seuil: float = 0.5
    silence_min_s: float = 0.2
    marge_s: float = 0.03

    def __post_init__(self) -> None:
        if not 0.0 < self.seuil < 1.0:
            raise ValueError(f"silero.seuil hors de ]0, 1[ : {self.seuil}")
        if self.silence_min_s < 0.0 or self.marge_s < 0.0:
            raise ValueError("silero.silence_min_s et silero.marge_s doivent être positifs ou nuls")

    def silero_kwargs(self) -> dict:
        """Arguments de `get_speech_timestamps_from_probs` (en millisecondes)."""
        return {
            "threshold": self.seuil,
            "min_silence_duration_ms": round(1000.0 * (self.silence_min_s + 2.0 * self.marge_s)),
            "speech_pad_ms": round(1000.0 * self.marge_s),
            "min_speech_duration_ms": round(1000.0 * MIN_SPEECH_S),
        }

    def as_dict(self) -> dict:
        return asdict(self)


@contextmanager
def torch_threads(n: int | None):
    """Fixe le nombre de fils de torch le temps d'un bloc, puis rétablit l'ancien."""
    before = torch.get_num_threads()
    if n is not None:
        torch.set_num_threads(n)
    try:
        yield
    finally:
        torch.set_num_threads(before)


def _import_silero():
    """Paquet silero_vad, après contrôle de sa version ; le nombre de fils de torch est
    rétabli après l'import, qui l'impose à un fil pour tout le processus."""
    with torch_threads(None):
        try:
            import silero_vad
        except ImportError as error:
            raise SileroMissing(f"silero-vad absent de l'environnement ({INSTALL_HINT})") from error
    version = getattr(silero_vad, "__version__", None)
    if version != SILERO_VERSION:
        raise SileroMissing(f"silero-vad {version} installé, {SILERO_VERSION} attendu ({INSTALL_HINT})")
    return silero_vad


def load_binarize() -> Binarize:
    """Binarisation de Silero seule (sans modèle) : suffit quand les probabilités sont en cache."""
    return _import_silero().get_speech_timestamps_from_probs


def load_model() -> tuple[object, Binarize]:
    """Modèle JIT de Silero (CPU) et sa fonction de binarisation, après contrôle de la
    version et de l'empreinte du fichier de poids."""
    silero_vad = _import_silero()
    weights = resources.files("silero_vad.data").joinpath(MODEL_FILE).read_bytes()
    digest = hashlib.sha256(weights).hexdigest()
    if digest != MODEL_SHA256:
        raise SileroMissing(f"{MODEL_FILE} : empreinte {digest[:12]}, {MODEL_SHA256[:12]} attendue")
    with torch_threads(None):
        model = silero_vad.load_silero_vad(onnx=False)
    return model, silero_vad.get_speech_timestamps_from_probs


def speech_probabilities(model, waveform: torch.Tensor, progress: Callable[[float], None] | None = None) -> np.ndarray:
    """Probabilité de parole par fenêtre de 512 échantillons, comme dans
    `get_speech_timestamps` (états remis à zéro, dernière fenêtre complétée par des zéros)."""
    audio = waveform.reshape(-1).to("cpu", torch.float32)
    n = audio.shape[0]
    probs = np.empty((n + WINDOW - 1) // WINDOW, dtype=np.float32)
    model.reset_states()
    with torch_threads(1), torch.inference_mode():
        for index, start in enumerate(range(0, n, WINDOW)):
            chunk = audio[start:start + WINDOW]
            if chunk.shape[0] < WINDOW:
                chunk = torch.nn.functional.pad(chunk, (0, WINDOW - chunk.shape[0]))
            probs[index] = model(chunk, SAMPLE_RATE).item()
            if progress is not None and index % 2000 == 0:
                progress(min(1.0, (start + WINDOW) / n))
    if progress is not None:
        progress(1.0)
    return probs


def speech_mask(probs: np.ndarray, n_samples: int, params: MaskParams, binarize: Binarize, uri: str | None = None) -> Timeline:
    """Masque de parole (secondes) : zones de parole de Silero pour ces réglages."""
    speeches = binarize(
        [float(p) for p in probs], sampling_rate=SAMPLE_RATE, audio_length_samples=int(n_samples),
        return_seconds=False, **params.silero_kwargs(),
    )
    segments = [Segment(s["start"] / SAMPLE_RATE, s["end"] / SAMPLE_RATE) for s in speeches if s["end"] > s["start"]]
    return Timeline(segments, uri=uri).support()


def refine(annotation: Annotation, mask: Timeline) -> Annotation:
    """Tours de `annotation` restreints au masque : ne retire que du temps, n'ajoute rien."""
    refined = annotation.crop(mask, mode="intersection")
    refined.uri = annotation.uri
    return refined


def removed_speech_s(before: Annotation, after: Annotation) -> float:
    """Durée de parole (toutes voix confondues) retirée par le post-traitement."""
    return before.get_timeline().support().duration() - after.get_timeline().support().duration()


# --- Cache des probabilités (script de réglage) -----------------------------------


def cache_path(corpus: str, uri: str, root: Path = DATA_DIR) -> Path:
    """Probabilités de Silero d'un fichier, sous data/processed/ (non versionné)."""
    return root / "processed" / corpus / "silero" / CACHE_TAG / f"{uri}.npz"


def save_probabilities(path: Path, probs: np.ndarray, n_samples: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        np.savez(handle, probs=probs.astype(np.float32), n_samples=np.int64(n_samples),
                 version=SILERO_VERSION, sha256=MODEL_SHA256)


def load_probabilities(path: Path) -> tuple[np.ndarray, int]:
    with np.load(path) as data:
        if str(data["version"]) != SILERO_VERSION or str(data["sha256"]) != MODEL_SHA256:
            raise ValueError(f"{path} : cache d'une autre version de Silero")
        probs, n_samples = data["probs"], int(data["n_samples"])
    if len(probs) != (n_samples + WINDOW - 1) // WINDOW:
        raise ValueError(f"{path} : {len(probs)} probabilités pour {n_samples} échantillons")
    return probs, n_samples


# --- Moteur composé -----------------------------------------------------------------


class SileroRefinement(Engine):
    """Moteur `inner` suivi du masque de Silero (D25, V2 ; V3 si `inner` rend sa sortie
    exclusive). Nom : celui du moteur suivi de `-silero`."""

    def __init__(self, inner: Engine, seuil: float | None = None, silence_min_s: float | None = None,
                 marge_s: float | None = None, model=None, binarize: Binarize | None = None) -> None:
        self.inner = inner
        given = {"seuil": seuil, "silence_min_s": silence_min_s, "marge_s": marge_s}
        self._origins = {key: "defaut" if value is None else "experience" for key, value in given.items()}
        self.params = MaskParams(**{key: value for key, value in given.items() if value is not None})
        super().__init__(speaker_mode=None, trace=inner.trace)
        self.name = f"{inner.name}-silero"
        if model is None:
            model, loaded = load_model()
            binarize = binarize or loaded
        if binarize is None:
            raise ValueError("binarize requis avec un modèle fourni")
        self.model, self.binarize = model, binarize

    # Attributs du moteur suivi, lus et écrits par scripts/run_experiment.py.
    @property
    def trace(self) -> bool:
        return self.inner.trace

    @trace.setter
    def trace(self, value: bool) -> None:
        self.inner.trace = value

    @property
    def speaker_mode(self) -> str:
        return self.inner.speaker_mode

    @property
    def device(self):
        return self.inner.device

    def synchronize(self) -> None:
        self.inner.synchronize()

    def run(self, waveform: torch.Tensor, sample_rate: int = SAMPLE_RATE, uri: str | None = None,
            num_speakers: int | None = None, speech: Timeline | None = None,
            progress: Progress | None = None) -> Resultat:
        self.check_input(waveform, sample_rate)
        if speech is not None:
            raise ValueError("Détection oracle : le masque de Silero n'a pas d'objet quand la parole est imposée")
        t0 = time.perf_counter()
        probs = speech_probabilities(self.model, waveform,
                                     None if progress is None else (lambda f: progress("detection", f)))
        mask = speech_mask(probs, waveform.shape[1], self.params, self.binarize, uri=uri)
        silero_s = time.perf_counter() - t0
        result = self.inner.run(waveform, sample_rate, uri=uri, num_speakers=num_speakers, progress=progress)
        before = result.annotation
        result.annotation = refine(before, mask)
        # Autres sorties du moteur suivi (sortie habituelle ou exclusive de pyannote) : même masque.
        others = getattr(result, "autres_sorties", None)
        if others:
            result.autres_sorties = {name: refine(other, mask) for name, other in others.items()}
        result.durees_etapes["detection_fine"] = silero_s
        result.infos["silero"] = {
            "parole_avant_s": round(before.get_timeline().support().duration(), 3),
            "parole_retiree_s": round(removed_speech_s(before, result.annotation), 3),
            "masque_parole_s": round(mask.duration(), 3),
        }
        return result

    def describe(self) -> dict[str, list[Setting]]:
        described = {step: list(settings) for step, settings in self.inner.describe().items()}
        described.setdefault("detection", []).extend([
            Setting("silero.modele", f"silero-vad=={SILERO_VERSION}@{MODEL_SHA256[:12]} ({MODEL_FILE})", "code"),
            Setting("silero.seuil", self.params.seuil, self._origins["seuil"]),
            Setting("silero.silence_min_s", self.params.silence_min_s, self._origins["silence_min_s"]),
            Setting("silero.marge_s", self.params.marge_s, self._origins["marge_s"]),
            Setting("silero.parole_min_s", MIN_SPEECH_S, "defaut"),
            Setting("silero.peripherique", "cpu, un fil", "code"),
        ])
        return described


def pyannote_silero(device: str | None = "auto", speaker_mode: str | None = None, trace: bool = False,
                    silero: dict | None = None, **params) -> SileroRefinement:
    """Fabrique pour `PIPELINES` de scripts/run_experiment.py : paramètres de pyannote dans
    `pipeline.parametres`, réglages du masque sous `pipeline.parametres.silero`
    (`seuil`, `silence_min_s`, `marge_s`)."""
    from whospoke.pipelines.pyannote_community1 import PyannoteCommunity1

    inner = PyannoteCommunity1(device=device, speaker_mode=speaker_mode, trace=trace, **params)
    return SileroRefinement(inner, **(silero or {}))


pyannote_silero.name = "pyannote-community-1-silero"
