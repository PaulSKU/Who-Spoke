"""Enveloppe de pyannote/speaker-diarization-community-1 au contrat D19 (signal en mémoire, D16).

Aucun chemin de fichier n'est passé à la pipeline : le décodage par torchcodec n'est pas
utilisé. Le nombre de locuteurs est estimé par la pipeline, sauf s'il est imposé à
l'appel (`num_speakers`, par fichier) ou à la construction (`num_speakers`,
`min_speakers`, `max_speakers`, tous à None par défaut). La détection de parole oracle
n'est pas prise en charge : la détection est faite par le réseau de segmentation.

Sorties (D25) : chaque exécution produit la sortie habituelle (`speaker_diarization`, avec
chevauchements) et la sortie exclusive (`exclusive_speaker_diarization`, au plus un
locuteur par trame). Le réglage `sortie` désigne celle qui est évaluée (`annotation` du
résultat) ; l'autre est rendue dans `autres_sorties`.

Nombre de locuteurs (D23, rang A2) : pour chaque fichier, le nombre de groupes retenus par
VBx avant l'application des bornes (`n_locuteurs_vbx`) et le recours éventuel au KMeans
(`kmeans`, `n_locuteurs_kmeans`) sont relevés dans `infos`, sans changer le calcul.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path

import torch
from pyannote.core import Timeline

from whospoke.audio import SAMPLE_RATE, as_pipeline_input
from whospoke.device import select_device
from whospoke.pipelines.base import Engine, Progress, Resultat, Setting

MODEL_ID = "pyannote/speaker-diarization-community-1"
# Révision figée (D18, amendement du 01/11) : seul instantané du cache local, celui
# d'EXP-0001 et d'EXP-0007 et de la baseline WeSpeaker. pyannote la transmet à chaque
# sous-modèle (segmentation, empreintes, PLDA), consignée dans describe() en `…@commit`.
MODEL_REVISION = "3533c8cf8e369892e6b79ff1bf80f7b0286a54ee"
REPO_ROOT = Path(__file__).resolve().parents[3]

# Sorties de la pipeline (D25) : nom dans la configuration -> attribut de DiarizeOutput.
SORTIES = {
    "habituelle": "speaker_diarization",
    "exclusive": "exclusive_speaker_diarization",
}

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


@contextmanager
def _clustering_probe(record: dict):
    """Relève le nombre de groupes de VBx et le recours au KMeans pendant un appel.

    Remplace temporairement `cluster_vbx` et `KMeans` dans le module de regroupement de
    pyannote par des enveloppes qui transmettent les arguments et les résultats tels
    quels : le calcul est inchangé. Le nombre de groupes de VBx est celui que pyannote
    retient (poids `sp` > 1e-7), avant toute borne sur le nombre de locuteurs.
    """
    import pyannote.audio.pipelines.clustering as module

    original_vbx, original_kmeans = module.cluster_vbx, module.KMeans

    def cluster_vbx(*args, **kwargs):
        q, sp = original_vbx(*args, **kwargs)
        record["n_locuteurs_vbx"] = int((sp > 1e-7).sum())
        return q, sp

    def KMeans(*args, **kwargs):  # fabrique, pas une sous-classe (paramètres de scikit-learn)
        record["kmeans"] = True
        record["n_locuteurs_kmeans"] = int(kwargs.get("n_clusters", args[0] if args else 8))
        return original_kmeans(*args, **kwargs)

    module.cluster_vbx, module.KMeans = cluster_vbx, KMeans
    try:
        yield record
    finally:
        module.cluster_vbx, module.KMeans = original_vbx, original_kmeans


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
        sortie: str | None = None,
    ) -> None:
        from pyannote.audio import Pipeline

        super().__init__(speaker_mode=speaker_mode, trace=trace)
        if sortie is not None and sortie not in SORTIES:
            raise ValueError(f"Sortie inconnue : {sortie!r} (attendu : {', '.join(SORTIES)})")
        self._sortie_imposee = sortie is not None
        self.sortie = sortie or "habituelle"
        self.device = select_device(device)
        self.num_speakers = num_speakers
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers
        pipeline = Pipeline.from_pretrained(MODEL_ID, revision=MODEL_REVISION, token=_hf_token())
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

        record = {"n_locuteurs_vbx": None, "kmeans": False, "n_locuteurs_kmeans": None}
        with _clustering_probe(record):
            output = self._pipeline(
                as_pipeline_input(waveform, sample_rate),
                num_speakers=num_speakers if num_speakers is not None else self.num_speakers,
                min_speakers=self.min_speakers,
                max_speakers=self.max_speakers,
                hook=hook,
            )
        self.synchronize()
        # pyannote.audio 4 renvoie un DiarizeOutput portant les deux sorties (D25) : la
        # sortie habituelle garde les chevauchements, la sortie exclusive n'en a pas.
        sorties = {name: getattr(output, attribute) for name, attribute in SORTIES.items()}
        for annotation in sorties.values():
            if uri is not None:
                annotation.uri = uri
        annotation = sorties.pop(self.sortie)
        durations["sortie"] = time.perf_counter() - last[0]
        if progress is not None:
            progress("sortie", 1.0)
        return Resultat(annotation=annotation, durees_etapes=durations, infos=record,
                        autres_sorties=sorties)

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
                Setting("sortie.exclusive", self.sortie == "exclusive",
                        "experience" if self._sortie_imposee else "defaut"),
            ],
        }
