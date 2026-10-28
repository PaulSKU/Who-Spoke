"""Enveloppe de pyannote/speaker-diarization-community-1 au contrat D19 (signal en mémoire, D16).

Aucun chemin de fichier n'est passé à la pipeline : le décodage par torchcodec n'est pas
utilisé. Le nombre de locuteurs est estimé par la pipeline, sauf s'il est imposé à
l'appel (`num_speakers`, par fichier) ou à la construction (`num_speakers`,
`min_speakers`, `max_speakers`, tous à None par défaut). La détection de parole oracle
n'est pas prise en charge : la détection est faite par le réseau de segmentation.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import torch
from pyannote.core import Timeline

from whospoke.audio import SAMPLE_RATE, as_pipeline_input
from whospoke.device import select_device
from whospoke.pipelines.base import Engine, Progress, Resultat, Setting

MODEL_ID = "pyannote/speaker-diarization-community-1"
REPO_ROOT = Path(__file__).resolve().parents[3]

# Étape du contrat atteinte quand pyannote appelle son hook avec un artefact non nul.
_HOOK_STEPS = {
    "segmentation": "segmentation",
    "speaker_counting": "detection",
    "embeddings": "empreintes",
    "discrete_diarization": "regroupement",
}


def _hf_token() -> str:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
    token = os.environ.get("HF_TOKEN") or None
    if token is None:
        raise RuntimeError("HF_TOKEN absent ou vide dans .env (modèle à accès restreint)")
    return token


def _checkpoint(spec: dict | str) -> str:
    """Identifiant lisible d'un modèle chargé (jamais le jeton d'accès)."""
    if isinstance(spec, str):
        return spec
    name = spec["checkpoint"] + (f"/{spec['subfolder']}" if spec.get("subfolder") else "")
    return name + (f"@{spec['revision']}" if spec.get("revision") else "")


class PyannoteCommunity1(Engine):
    """Charge la pipeline une fois, puis diarise des signaux (1, n) à 16 kHz."""

    name = "pyannote-community-1"

    def __init__(
        self,
        device: str | None = "auto",
        num_speakers: int | None = None,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
        speaker_mode: str | None = None,
        trace: bool = False,
    ) -> None:
        from pyannote.audio import Pipeline

        super().__init__(speaker_mode=speaker_mode, trace=trace)
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
        if self._speaker_mode is not None:
            return self._speaker_mode
        if self.num_speakers is not None:
            return "oracle"
        if self.min_speakers is not None or self.max_speakers is not None:
            return "borne"
        return "estime"

    def synchronize(self) -> None:
        if self.device.type == "mps":
            torch.mps.synchronize()
        elif self.device.type == "cuda":
            torch.cuda.synchronize()

    def run(
        self,
        waveform: torch.Tensor,
        sample_rate: int = SAMPLE_RATE,
        uri: str | None = None,
        num_speakers: int | None = None,
        speech: Timeline | None = None,
        progress: Progress | None = None,
    ) -> Resultat:
        """Diarisation d'un signal ; l'annotation garde les chevauchements."""
        self.check_input(waveform, sample_rate)
        if speech is not None:
            raise NotImplementedError(
                f"{self.name} : détection de parole oracle non prise en charge "
                "(la détection est faite par le réseau de segmentation)"
            )
        durations: dict[str, float] = {}
        last = [time.perf_counter()]

        def hook(step_name, step_artifact, file=None, total=None, completed=None):
            if total and completed is not None and progress is not None:
                step = "segmentation" if step_name == "segmentation" else "empreintes"
                progress(step, min(1.0, completed / total))
            if step_artifact is None or step_name not in _HOOK_STEPS:
                return
            now = time.perf_counter()
            step = _HOOK_STEPS[step_name]
            durations[step] = durations.get(step, 0.0) + now - last[0]
            last[0] = now
            if progress is not None:
                progress(step, 1.0)

        output = self._pipeline(
            as_pipeline_input(waveform, sample_rate),
            num_speakers=num_speakers if num_speakers is not None else self.num_speakers,
            min_speakers=self.min_speakers,
            max_speakers=self.max_speakers,
            hook=hook,
        )
        self.synchronize()
        # pyannote.audio 4 renvoie un DiarizeOutput ; on garde la diarisation avec
        # chevauchements (et non `exclusive_speaker_diarization`), conformément au
        # protocole qui compte les chevauchements.
        annotation = getattr(output, "speaker_diarization", output)
        if uri is not None:
            annotation.uri = uri
        durations["sortie"] = time.perf_counter() - last[0]
        if progress is not None:
            progress("sortie", 1.0)
        return Resultat(annotation=annotation, durees_etapes=durations)

    def describe(self) -> dict[str, list[Setting]]:
        """Paramètres effectifs lus sur la pipeline chargée."""
        p = self._pipeline
        params = p.parameters(instantiated=True)
        seg_model = p._segmentation.model
        specs = seg_model.specifications
        clustering = p.clustering
        if self.speaker_mode == "borne":
            speakers = f"borne [{self.min_speakers}, {self.max_speakers}]"
        elif self.speaker_mode == "oracle":
            speakers = "imposé par fichier" if self.num_speakers is None else f"imposé ({self.num_speakers})"
        else:
            speakers = "estimé"
        return {
            "detection": [
                Setting("segmentation.modele", f"{_checkpoint(p.segmentation_model)} ({type(seg_model).__name__})", "modele"),
                Setting("segmentation.powerset", bool(specs.powerset), "modele"),
                Setting("segmentation.min_duration_off", params["segmentation"]["min_duration_off"], "defaut"),
            ],
            "segmentation": [
                Setting("segmentation.duree_fenetre_s", float(specs.duration), "modele"),
                Setting("segmentation_step", float(p.segmentation_step), "defaut"),
                Setting("segmentation.locuteurs_par_fenetre", len(specs.classes), "modele"),
                Setting("segmentation.locuteurs_simultanes", specs.powerset_max_classes, "modele"),
                Setting("segmentation_batch_size", int(p.segmentation_batch_size), "defaut"),
            ],
            "empreintes": [
                Setting("embedding.modele", f"{_checkpoint(p.embedding)} ({type(p._embedding.model_).__name__})", "modele"),
                Setting("embedding.dimension", int(p._embedding.dimension), "modele"),
                Setting("embedding_exclude_overlap", bool(p.embedding_exclude_overlap), "defaut"),
                Setting("embedding_batch_size", int(p.embedding_batch_size), "defaut"),
            ],
            "regroupement": [
                Setting("clustering.methode", p.klustering, "defaut"),
                Setting("clustering.metric", clustering.metric, "defaut"),
                Setting("clustering.threshold", params["clustering"]["threshold"], "defaut"),
                Setting("clustering.Fa", params["clustering"]["Fa"], "defaut"),
                Setting("clustering.Fb", params["clustering"]["Fb"], "defaut"),
                Setting("clustering.constrained_assignment", bool(clustering.constrained_assignment), "defaut"),
                Setting("plda.modele", _checkpoint(p.plda), "modele"),
                Setting("plda.lda_dimension", int(p._plda.lda_dimension), "modele"),
                Setting("n_locuteurs", speakers, "experience"),
            ],
            "sortie": [
                Setting("sortie.exclusive", False, "code"),
            ],
        }
