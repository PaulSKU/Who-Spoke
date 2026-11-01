"""Enveloppe de DiariZen au contrat D19 (D23, amendement du 01/11, rang A5 ; chantier E4).

DiariZen (BUT Speech@FIT) : segmentation de bout en bout (WavLM Large élagué à 80 % et
Conformer, 4 locuteurs simultanés au plus) sur fenêtres de 16 s, empreintes WeSpeaker
ResNet34, regroupement VBx avec PLDA ; même principe que pyannote 3.1, dont il reprend un
fork. Il tourne dans `envs/diarizen/` (Python 3.10, torch 2.1.1 ; `scripts/envs/diarizen.sh`),
appelé en sous-processus (`whospoke.pipelines.externe`, exécutant `runners/executant_diarizen.py`).
Poids sous CC BY-NC 4.0 : usage non commercial seulement.

Nombre de locuteurs : estimé (bornes de config.toml, 1 à 20), imposé par fichier
(`num_speakers`) ou borné à la construction (`min_speakers`, `max_speakers`), passés au
regroupement. La détection de parole oracle n'est pas prise en charge.
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

MODEL_ID = "BUT-FIT/diarizen-wavlm-large-s80-md-v2"
MODEL_REVISION = "027b3e221b9d81dce2be794084f1dbd3ba2da403"        # vérifiée sur le Hub le 01/11/2026
EMBEDDING_ID = "pyannote/wespeaker-voxceleb-resnet34-LM"
EMBEDDING_REVISION = "837717ddb9ff5507820346191109dc79c958d614"
CODE_COMMIT = "844f5555b0a98acd0931511fc641a8c5b8ba92c7"            # BUTSpeechFIT/DiariZen, 04/08/2026
DEVICES = ("cpu", "mps")


class DiariZen(Engine):
    name = "diarizen"

    def __init__(self, device: str = "cpu", num_speakers: int | None = None, min_speakers: int | None = None,
                 max_speakers: int | None = None, speaker_mode: str | None = None, trace: bool = False,
                 python=None, runner=None, process_factory=ExternalProcess) -> None:
        super().__init__(speaker_mode=speaker_mode, trace=trace)
        device = str(device)
        if device not in DEVICES:
            raise ValueError(f"Périphérique {device!r} : cpu ou mps")
        self.device = device
        self.num_speakers, self.min_speakers, self.max_speakers = num_speakers, min_speakers, max_speakers
        python = python or env_python("diarizen", "venv/bin/python")
        runner = runner or RUNNERS_DIR / "executant_diarizen.py"
        config = {"modele": MODEL_ID, "revision": MODEL_REVISION, "empreintes": EMBEDDING_ID,
                  "revision_empreintes": EMBEDDING_REVISION, "peripherique": device}
        try:
            self._process = process_factory([python, runner, json.dumps(config)])
        except ExternalError as error:
            raise ExternalError(f"{error}\nPoids absents du cache ? Les télécharger une fois, avec accès réseau : "
                                "sh scripts/envs/diarizen.sh --modeles") from error
        self.ready = self._process.ready

    @property
    def speaker_mode(self) -> str:
        if self._speaker_mode is not None:
            return self._speaker_mode
        if self.num_speakers is not None:
            return "oracle"
        if self.min_speakers is not None or self.max_speakers is not None:
            return "borne"
        return "estime"

    def _bounds(self, num_speakers: int | None) -> tuple[int | None, int | None]:
        count = num_speakers if num_speakers is not None else self.num_speakers
        if count is not None:
            return count, count
        return self.min_speakers, self.max_speakers

    def run(self, waveform: torch.Tensor, sample_rate: int = SAMPLE_RATE, uri: str | None = None,
            num_speakers: int | None = None, speech: Timeline | None = None,
            progress: Progress | None = None) -> Resultat:
        self.check_input(waveform, sample_rate)
        if speech is not None:
            raise ValueError("DiariZen ne prend pas de détection de parole oracle")
        uri = uri or "fichier"
        low, high = self._bounds(num_speakers)
        if progress is not None:
            progress("segmentation", 0.0)
        wav = write_wav(self._process.workdir / "entree.wav", waveform[0].numpy())
        rttm = self._process.workdir / "sortie.rttm"
        start = time.perf_counter()
        response = self._process.request({"entree": str(wav), "sortie": str(rttm), "uri": uri,
                                          "min_speakers": low, "max_speakers": high})
        total = time.perf_counter() - start
        annotation = load_rttm(rttm, uri)
        if progress is not None:
            progress("segmentation", 1.0)
        durations = dict(response.get("durees", {}))
        durations["sous_processus"] = total
        return Resultat(annotation=annotation, durees_etapes=durations,
                        infos={"n_locuteurs_bornes": response.get("n_locuteurs_bornes"),
                               "chargement_s": self.ready.get("chargement_s")})

    def describe(self) -> dict[str, list[Setting]]:
        versions = self.ready.get("versions", {})
        config = self.ready.get("configuration", {})
        inference, clustering = config.get("inference", {}), config.get("regroupement", {})
        environment = ", ".join(f"{name} {version}" for name, version in versions.items())
        if self.speaker_mode == "borne":
            speakers = f"borne [{self.min_speakers}, {self.max_speakers}]"
        elif self.speaker_mode == "oracle":
            speakers = "imposé par fichier" if self.num_speakers is None else f"imposé ({self.num_speakers})"
        else:
            speakers = f"estimé (entre {clustering.get('min_speakers')} et {clustering.get('max_speakers')})"
        return {
            "segmentation": [
                Setting("diarizen.modele", f"{MODEL_ID}@{MODEL_REVISION[:12]}", "experience"),
                Setting("diarizen.code", f"BUTSpeechFIT/DiariZen@{CODE_COMMIT[:12]}", "experience"),
                Setting("diarizen.duree_fenetre_s", inference.get("seg_duration"), "modele"),
                Setting("diarizen.pas_fenetre", inference.get("segmentation_step"), "modele"),
                Setting("diarizen.filtre_median", inference.get("apply_median_filtering"), "modele"),
            ],
            "empreintes": [
                Setting("diarizen.empreintes", f"{EMBEDDING_ID}@{EMBEDDING_REVISION[:12]}", "experience"),
                Setting("diarizen.empreintes_hors_chevauchement", True, "code"),
            ],
            "regroupement": [
                Setting("diarizen.regroupement", clustering.get("method"), "modele"),
                Setting("diarizen.seuil_ahc", clustering.get("ahc_threshold"), "modele"),
                Setting("diarizen.vbx_fa_fb", f"Fa={clustering.get('Fa')}, Fb={clustering.get('Fb')}", "modele"),
                Setting("diarizen.n_locuteurs", speakers, "experience"),
            ],
            "sortie": [
                Setting("diarizen.environnement", f"envs/diarizen ({environment}), {self.device}", "code"),
            ],
        }

    def close(self) -> None:
        self._process.close()
