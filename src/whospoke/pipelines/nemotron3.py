"""Enveloppe de Nemotron 3 Diarization au contrat D19 (D23, rang A4 ; chantier E4).

Modèle de bout en bout de NVIDIA (Sortformer, cache de locuteurs par ordre d'arrivée) :
une sortie par locuteur, 8 au plus, trame de 10 ms, chevauchements compris. Il tourne
dans `envs/nemotron/` (Python 3.12, transformers ≥ 5.18 ; `scripts/envs/nemotron.sh`),
appelé en sous-processus (`whospoke.pipelines.externe`, exécutant
`runners/executant_nemotron3.py`). Voie retenue parmi les trois explorées le 01/11 : transformers,
poids fp32 (`model.safetensors`) ; NeMo 3.0 et NeMo-Speech.cpp s'installent aussi
(journal du 01/11), le second avec des poids quantifiés (q8_0).

Le nombre de locuteurs n'est pas réglable : il est estimé par le modèle, sans pouvoir
être imposé ni borné. La détection de parole oracle n'est pas prise en charge.
"""

from __future__ import annotations

import json
import time

import torch
from pyannote.core import Timeline

from whospoke.audio import SAMPLE_RATE
from whospoke.experiment import load_rttm
from whospoke.pipelines.base import Engine, Progress, Resultat, Setting
from whospoke.pipelines.externe import RUNNERS_DIR, ExternalError, ExternalProcess, env_python, write_wav

MODEL_ID = "nvidia/Nemotron-3-Diarization"
MODEL_REVISION = "f667ed73aee57d40cc39428eb768b4fd87a0a29e"   # vérifiée sur le Hub le 01/11/2026
MAX_SPEAKERS = 8
DEFAULT_THRESHOLD = 0.5                                       # valeur par défaut de extract_speaker_dict
DEVICES = ("cpu", "mps")


class Nemotron3Diarization(Engine):
    name = "nemotron3-diarization"

    def __init__(self, device: str = "cpu", threshold: float = DEFAULT_THRESHOLD, revision: str = MODEL_REVISION,
                 speaker_mode: str | None = None, trace: bool = False, python=None, runner=None,
                 process_factory=ExternalProcess) -> None:
        super().__init__(speaker_mode=speaker_mode, trace=trace)
        if self.speaker_mode != "estime":
            raise ValueError("Nemotron 3 Diarization estime seul le nombre de locuteurs (8 au plus) : "
                             "ni nombre imposé ni bornes")
        device = str(device)
        if device not in DEVICES:
            raise ValueError(f"Périphérique {device!r} : cpu ou mps")
        self.device, self.threshold, self.revision = device, float(threshold), revision
        self._threshold_origin = "defaut" if threshold == DEFAULT_THRESHOLD else "experience"
        python = python or env_python("nemotron")
        runner = runner or RUNNERS_DIR / "executant_nemotron3.py"
        config = {"modele": MODEL_ID, "revision": revision, "peripherique": device, "seuil": self.threshold}
        try:
            self._process = process_factory([python, runner, json.dumps(config)])
        except ExternalError as error:
            raise ExternalError(f"{error}\nPoids absents du cache ? Les télécharger une fois, avec accès réseau : "
                                "sh scripts/envs/nemotron.sh --modeles") from error
        self.ready = self._process.ready

    def run(self, waveform: torch.Tensor, sample_rate: int = SAMPLE_RATE, uri: str | None = None,
            num_speakers: int | None = None, speech: Timeline | None = None,
            progress: Progress | None = None) -> Resultat:
        self.check_input(waveform, sample_rate)
        if num_speakers is not None:
            raise ValueError("Nemotron 3 Diarization ne prend pas de nombre de locuteurs imposé")
        if speech is not None:
            raise ValueError("Nemotron 3 Diarization ne prend pas de détection de parole oracle")
        uri = uri or "fichier"
        if progress is not None:
            progress("detection", 0.0)
        wav = write_wav(self._process.workdir / "entree.wav", waveform[0].numpy())
        rttm = self._process.workdir / "sortie.rttm"
        start = time.perf_counter()
        response = self._process.request({"entree": str(wav), "sortie": str(rttm), "uri": uri})
        total = time.perf_counter() - start
        annotation = load_rttm(rttm, uri)
        if progress is not None:
            progress("detection", 1.0)
        durations = dict(response.get("durees", {}))
        durations["sous_processus"] = total
        return Resultat(annotation=annotation, durees_etapes=durations,
                        infos={"n_trames": response.get("n_trames"), "chargement_s": self.ready.get("chargement_s")})

    def describe(self) -> dict[str, list[Setting]]:
        versions = self.ready.get("versions", {})
        config = self.ready.get("configuration", {})
        environment = ", ".join(f"{name} {version}" for name, version in versions.items())
        return {
            "detection": [
                Setting("nemotron.modele", f"{MODEL_ID}@{self.revision[:12]}", "experience"),
                Setting("nemotron.seuil", self.threshold, self._threshold_origin),
                Setting("nemotron.trame_s", config.get("trame_s", 0.01), "modele"),
            ],
            "regroupement": [
                Setting("nemotron.locuteurs_max", config.get("locuteurs_max", MAX_SPEAKERS), "modele"),
                Setting("nemotron.n_locuteurs", "estimé (ni imposé ni borné)", "code"),
            ],
            "sortie": [
                Setting("nemotron.mode", config.get("mode", "hors ligne (is_streaming=False)"), "code"),
                Setting("nemotron.environnement", f"envs/nemotron ({environment}), {self.device}", "code"),
            ],
        }

    def close(self) -> None:
        self._process.close()
