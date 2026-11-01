"""Moteurs proposés par l'application, et moteur factice de développement (D17, D19 §1).

Chaque moteur de l'interface reprend la configuration d'une expérience source : ses
paramètres (`pipeline.parametres` de config.yaml), le θ retenu par son balayage
(`execution_<périphérique>.json`) et son RTF mesuré (`results/leaderboard.csv`, voir
`app/temps.py`). Les sources sont les expériences sur SUMM-RE, jeu de validation
prioritaire (D3 ; D17, amendement 1) : EXP-0009 (MFCC), EXP-0012 (ECAPA), EXP-0007
(pyannote) et EXP-0015 (WeSpeaker), ce dernier moteur restant indisponible tant
qu'EXP-0015 n'existe pas ou n'a pas été exécutée. Au gel, cette correspondance passera
dans `configs/demo.yaml`.

Périphériques : la baseline MFCC s'exécute en CPU seul (D19) et les empreintes ECAPA et
WeSpeaker en CPU (D22, amendement 2 : NaN intermittents en MPS) ; seul pyannote suit le
choix de l'utilisateur.

Le moteur factice (`FakeEngine`) respecte le contrat de `base.py` sans aucune inférence :
il simule les étapes du moteur imité, puis renvoie le RTTM que l'expérience source a
produit pour le fichier déposé, reconnu à son nom (`ES2004a.mp3` ou `ami__ES2004a.wav`
pour `ami__ES2004a`), coupé à la durée de l'audio déposé.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import torch
import yaml
from pyannote.core import Segment, Timeline

from whospoke.audio import SAMPLE_RATE
from whospoke.experiment import REPO_ROOT, load_rttm
from whospoke.pipelines.base import Engine, Progress, Resultat, Setting

EXPERIMENTS_DIR = REPO_ROOT / "experiments"
PREFETCH_COMMAND = "uv run python scripts/prefetch_models.py"

BASELINE_STEPS = (
    "analyse", "normalisation_cepstrale", "detection", "segmentation",
    "representation", "regroupement", "attribution",
)
PYANNOTE_STEPS = ("segmentation", "detection", "empreintes", "regroupement", "sortie")


@dataclass(frozen=True)
class EngineSpec:
    """Un moteur de l'interface et l'expérience dont il reprend la configuration."""

    key: str
    label: str
    pipeline: str             # Engine.name du moteur réel
    source_exp: str           # EXP-NNNN
    steps: tuple[str, ...]    # étapes annoncées par progress(), dans l'ordre
    cpu_only: bool
    supports_range: bool      # fourchette min–max du nombre de locuteurs


SPECS: dict[str, EngineSpec] = {
    spec.key: spec
    for spec in (
        EngineSpec("baseline-mfcc", "Baseline MFCC", "baseline", "EXP-0009", BASELINE_STEPS, True, False),
        EngineSpec("baseline-ecapa", "Baseline ECAPA", "baseline", "EXP-0012", BASELINE_STEPS, True, False),
        EngineSpec("baseline-wespeaker", "Baseline WeSpeaker", "baseline", "EXP-0015", BASELINE_STEPS, True, False),
        EngineSpec("pyannote-community-1", "pyannote community-1", "pyannote-community-1", "EXP-0007",
                   PYANNOTE_STEPS, False, True),
    )
}


@dataclass(frozen=True)
class FixedOverhead:
    """Surcoût fixe du premier appel après chargement, ajouté à RTF × durée (app/temps.py)."""

    seconds: float
    measured_on: str          # AAAA-MM-JJ


# Surcoût fixe par (moteur, périphérique) : durée du premier appel après chargement − RTF ×
# durée, moyenne de 3 lancements (scripts/measure_overhead.py, 60 s de summre__004c_PAPH,
# partition dev). À remesurer quand l'expérience source ou son RTF change. Mesure du
# 01/11/2026 sur secteur, charge moyenne de la machine de 2,7 à 3,8 (8,8 au plus pendant
# pyannote en CPU, d'où sa dispersion : 2,7 à 9,8 s selon le lancement).
FIXED_OVERHEAD: dict[tuple[str, str], FixedOverhead] = {
    ("baseline-mfcc", "cpu"): FixedOverhead(1.5, "2026-11-01"),
    ("baseline-ecapa", "cpu"): FixedOverhead(1.3, "2026-11-01"),
    ("baseline-wespeaker", "cpu"): FixedOverhead(1.6, "2026-11-01"),
    ("pyannote-community-1", "mps"): FixedOverhead(1.1, "2026-11-01"),
    ("pyannote-community-1", "cpu"): FixedOverhead(6.6, "2026-11-01"),
}


def fixed_overhead(key: str, device: str) -> FixedOverhead | None:
    """Surcoût fixe mesuré du moteur `key` sur `device`, ou None s'il n'a pas été mesuré."""
    return FIXED_OVERHEAD.get((key, device))


class EngineUnavailable(RuntimeError):
    """Moteur non utilisable en l'état (expérience source absente ou non exécutée)."""


def experiment_dir(exp_id: str, root: Path = EXPERIMENTS_DIR) -> Path:
    matches = sorted(root.glob(f"{exp_id}_*"))
    if not matches:
        raise EngineUnavailable(f"{exp_id} n'existe pas encore")
    if len(matches) > 1:
        raise EngineUnavailable(f"Plusieurs dossiers pour {exp_id}")
    return matches[0]


def source_config(spec: EngineSpec, root: Path = EXPERIMENTS_DIR) -> dict:
    """config.yaml de l'expérience source."""
    return yaml.safe_load((experiment_dir(spec.source_exp, root) / "config.yaml").read_text())


def source_device(spec: EngineSpec, root: Path = EXPERIMENTS_DIR) -> str:
    """Périphérique de l'exécution principale de l'expérience source."""
    return source_config(spec, root)["device"]


def execution_path(spec: EngineSpec, root: Path = EXPERIMENTS_DIR) -> Path:
    """execution_<périphérique>.json de l'exécution principale de l'expérience source (à
    défaut, la première exécution trouvée)."""
    directory = experiment_dir(spec.source_exp, root)
    main = directory / f"execution_{source_device(spec, root)}.json"
    if main.is_file():
        return main
    others = sorted(directory.glob("execution_*.json"))
    if not others:
        raise EngineUnavailable(f"{spec.source_exp} n'a pas encore été exécutée")
    return others[0]


def effective_configuration(spec: EngineSpec, root: Path = EXPERIMENTS_DIR) -> dict:
    """`configuration_effective` de l'exécution principale de l'expérience source, celle
    qu'affiche la page Pipeline (D17) ; dictionnaire vide si elle n'est pas consignée."""
    try:
        return json.loads(execution_path(spec, root).read_text()).get("configuration_effective") or {}
    except (OSError, ValueError, EngineUnavailable):
        return {}


def model_revisions(spec: EngineSpec, root: Path = EXPERIMENTS_DIR) -> dict[str, str]:
    """Révisions figées des modèles pré-entraînés du moteur (D18, amendement du 01/11) :
    {dépôt : commit}. La baseline MFCC n'en utilise aucun."""
    from whospoke import embeddings
    from whospoke.pipelines import pyannote_community1

    if spec.pipeline == pyannote_community1.PyannoteCommunity1.name:
        return {pyannote_community1.MODEL_ID: pyannote_community1.MODEL_REVISION}
    representation = (source_config(spec, root)["pipeline"].get("parametres") or {}).get("representation")
    return {
        "ecapa": {embeddings.ECAPA_SOURCE: embeddings.ECAPA_REVISION},
        "wespeaker": {embeddings.WESPEAKER_SOURCE: embeddings.WESPEAKER_REVISION},
    }.get(representation, {})


def engine_params(spec: EngineSpec, root: Path = EXPERIMENTS_DIR) -> dict:
    """Paramètres de construction repris de l'expérience source (θ retenu compris)."""
    config = source_config(spec, root)
    params = dict(config["pipeline"].get("parametres") or {})
    if spec.pipeline == "baseline":
        execution = experiment_dir(spec.source_exp, root) / f"execution_{config['device']}.json"
        if not execution.is_file():
            raise EngineUnavailable(f"{spec.source_exp} n'a pas encore été exécutée : θ inconnu")
        sweep = json.loads(execution.read_text()).get("balayage") or {}
        if sweep.get("parametre") != "theta" or sweep.get("valeur_retenue") is None:
            raise EngineUnavailable(f"{spec.source_exp} : aucun θ retenu par balayage")
        params["theta"] = sweep["valeur_retenue"]
    else:
        # Contraintes sur le nombre de locuteurs : fixées à chaque analyse, pas ici.
        for key in ("num_speakers", "min_speakers", "max_speakers"):
            params.pop(key, None)
    return params


def build_engine(spec: EngineSpec, device: str, root: Path = EXPERIMENTS_DIR) -> Engine:
    """Moteur réel, modèles chargés (long : à mettre en cache par l'appelant)."""
    params = engine_params(spec, root)
    if spec.pipeline == "baseline":
        from whospoke.pipelines.baseline import Baseline

        return Baseline(device="cpu", **params)
    from whospoke.pipelines.pyannote_community1 import PyannoteCommunity1

    return PyannoteCommunity1(device=device, **params)


def _shown(path: Path) -> str:
    """Chemin relatif au dépôt quand c'est possible (affichage, JSON)."""
    return str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)


def missing_model_message(error: BaseException, spec: EngineSpec) -> str | None:
    """Message clair si `error` vient d'un modèle absent du cache local (mode hors ligne).

    Parcourt la chaîne des causes à la recherche des erreurs de huggingface_hub levées
    quand `HF_HUB_OFFLINE=1` et que le fichier manque dans le cache ; None sinon.
    """
    from huggingface_hub.errors import LocalEntryNotFoundError, OfflineModeIsEnabled

    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (LocalEntryNotFoundError, OfflineModeIsEnabled)):
            return (
                f"Modèle de {spec.label} absent du cache local. L'application fonctionne hors ligne "
                "(HF_HUB_OFFLINE=1) et ne télécharge rien. Remplissez le cache une fois, avec accès "
                f"réseau et HF_TOKEN dans .env : {PREFETCH_COMMAND}, puis relancez l'application."
            )
        current = current.__cause__ or current.__context__
    return None


def find_rttm(rttm_dir: Path, name: str) -> Path:
    """RTTM de `rttm_dir` correspondant à un nom de fichier déposé (sans extension).

    Accepte l'uri complet (`summre__007a_ECRH`) ou l'identifiant d'origine (`007a_ECRH`).
    """
    exact = rttm_dir / f"{name}.rttm"
    if exact.is_file():
        return exact
    matches = sorted(rttm_dir.glob(f"*__{name}.rttm"))
    if len(matches) == 1:
        return matches[0]
    raise FileNotFoundError(
        f"Moteur factice : aucun RTTM pour {name!r} dans {_shown(rttm_dir)}"
        if not matches else f"Moteur factice : nom ambigu {name!r} ({len(matches)} RTTM)"
    )


class FakeEngine(Engine):
    """Moteur factice au contrat D19 : étapes simulées, RTTM d'une expérience existante."""

    name = "factice"

    def __init__(self, spec: EngineSpec, root: Path = EXPERIMENTS_DIR,
                 simulated_s: float = 6.0, ticks_per_step: int = 4) -> None:
        super().__init__()
        self.spec = spec
        self.rttm_dir = experiment_dir(spec.source_exp, root) / "rttm"
        if not self.rttm_dir.is_dir():
            raise EngineUnavailable(f"{spec.source_exp} n'a encore produit aucun RTTM")
        self.simulated_s = simulated_s
        self.ticks_per_step = ticks_per_step
        self._source: Path | None = None

    def run(
        self,
        waveform: torch.Tensor,
        sample_rate: int = SAMPLE_RATE,
        uri: str | None = None,
        num_speakers: int | None = None,
        speech: Timeline | None = None,
        progress: Progress | None = None,
    ) -> Resultat:
        self.check_input(waveform, sample_rate)
        if uri is None:
            raise ValueError("Moteur factice : uri requis pour retrouver le RTTM")
        path = find_rttm(self.rttm_dir, uri)
        self._source = path
        duration_s = waveform.shape[1] / sample_rate
        pause = self.simulated_s / (len(self.spec.steps) * self.ticks_per_step)
        durations: dict[str, float] = {}
        for step in self.spec.steps:
            start = time.perf_counter()
            for tick in range(1, self.ticks_per_step + 1):
                time.sleep(pause)
                if progress is not None:
                    progress(step, tick / self.ticks_per_step)
            durations[step] = time.perf_counter() - start
        source_uri = path.stem
        annotation = load_rttm(path, source_uri).crop(Segment(0.0, duration_s), mode="intersection")
        annotation.uri = uri
        infos = {"rttm_source": _shown(path), "n_locuteurs_ignore": num_speakers}
        return Resultat(annotation=annotation, durees_etapes=durations, infos=infos)

    def describe(self) -> dict[str, list[Setting]]:
        source = _shown(self._source or self.rttm_dir)
        return {"sortie": [Setting("factice.rttm_source", source, "code")]}
