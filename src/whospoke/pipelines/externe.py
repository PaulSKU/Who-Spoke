"""Moteurs externes en sous-processus, dans un environnement séparé (D23 §1, D10, D27 ; chantier E4).

Un moteur dont les dépendances sont incompatibles avec l'environnement principal tourne
dans son propre environnement (`envs/<moteur>/`, créé par `scripts/envs/<moteur>.sh`).
L'enveloppe lance une fois, à sa construction, un processus « exécutant »
(`whospoke/pipelines/runners/executant_<moteur>.py`, nommé ainsi pour ne pas masquer le paquet du moteur) qui charge le modèle puis traite les fichiers
un par un : le chargement n'est donc pas compté dans le temps de calcul (D19 §1,
protocole §3.5).

Échanges : une ligne JSON par message. L'exécutant annonce `{"pret": true, …}` (versions,
configuration effective) ou `{"erreur": …}` ; chaque requête `{"entree": wav, "sortie":
rttm, "uri": …}` reçoit `{"ok": true, …}` ou `{"erreur": …}` ; `{"commande": "fin"}`
l'arrête. L'audio passe par un WAV PCM 16 bits, 16 kHz, mono (sans perte depuis le signal
normalisé, D15) et le résultat par un RTTM relu ici.

Hors ligne et sans télémétrie (D27) : l'environnement de l'exécutant reçoit les variables
de `TELEMETRY_OFF`, `HF_HUB_OFFLINE=1` et les coupures propres aux piles externes
(`CHILD_ENV`), perd les jetons Hugging Face et les configurations d'exportation de
télémétrie, et s'exécute dans un dossier temporaire vide (OneLogger de NeMo y cherche ses
fichiers de configuration).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from whospoke.audio import SAMPLE_RATE
from whospoke.experiment import REPO_ROOT
from whospoke.telemetry import TELEMETRY_OFF

ENVS_DIR = REPO_ROOT / "envs"
RUNNERS_DIR = Path(__file__).with_name("runners")

# Variables imposées à l'exécutant, en plus de TELEMETRY_OFF (inventaire du 01/11/2026, E4).
CHILD_ENV: dict[str, str] = {
    "HF_HUB_OFFLINE": "1",            # aucun téléchargement : modèles lus dans le cache local
    "WANDB_MODE": "disabled",         # wandb (installé avec NeMo) : jamais initialisé à l'inférence
    "WANDB_DISABLED": "true",
    "TOKENIZERS_PARALLELISM": "false",
}
# Variables retirées : jetons (inutiles hors ligne) et configuration d'exportation de OneLogger.
CHILD_ENV_REMOVED = ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "ONE_LOGGER_EXPORTER_CONFIG_PATH")


class ExternalError(RuntimeError):
    """Échec de l'exécutant (démarrage, chargement ou traitement), avec la fin de sa sortie d'erreur."""


class EnvironmentMissing(ExternalError):
    """Environnement séparé absent : le créer avec scripts/envs/<moteur>.sh."""


def child_environment(base: Mapping[str, str] = os.environ) -> dict[str, str]:
    env = {key: value for key, value in base.items() if key not in CHILD_ENV_REMOVED}
    env.update(TELEMETRY_OFF)
    env.update(CHILD_ENV)
    return env


def env_python(name: str, relative: str = "bin/python", root: Path = ENVS_DIR) -> Path:
    """Interpréteur de l'environnement séparé `name`, ou `EnvironmentMissing`."""
    python = root / name / relative
    if not python.exists():
        raise EnvironmentMissing(f"Environnement {root / name} absent : le créer avec "
                                 f"`sh scripts/envs/{name}.sh --modeles` (avec accès réseau)")
    return python


def write_wav(path: Path, waveform) -> Path:
    """Signal (1, n) dans [-1, 1] → WAV PCM 16 bits, 16 kHz, mono."""
    data = np.asarray(waveform, dtype=np.float32).reshape(-1)
    wavfile.write(path, SAMPLE_RATE, np.round(np.clip(data, -1.0, 32767 / 32768) * 32768).astype(np.int16))
    return path


class ExternalProcess:
    """Exécutant lancé une fois ; requêtes JSON une par ligne sur ses entrée et sortie standard."""

    def __init__(self, command: list[str]) -> None:
        self.workdir = Path(tempfile.mkdtemp(prefix="whospoke-externe-"))
        self.stderr_path = self.workdir / "stderr.log"
        self._stderr = self.stderr_path.open("w")
        self.process = subprocess.Popen(
            [str(part) for part in command], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self._stderr, text=True, bufsize=1, env=child_environment(), cwd=self.workdir)
        self.ready = self._receive("démarrage")

    def _stderr_tail(self, n: int = 3000) -> str:
        self._stderr.flush()
        text = self.stderr_path.read_text(errors="replace") if self.stderr_path.exists() else ""
        return text.strip()[-n:]

    def _receive(self, step: str) -> dict:
        line = self.process.stdout.readline()
        if not line:
            code = self.process.wait()
            raise ExternalError(f"Exécutant arrêté pendant le {step} (code {code}) :\n{self._stderr_tail()}")
        message = json.loads(line)
        if "erreur" in message:
            raise ExternalError(f"{message['erreur']}\n{self._stderr_tail()}")
        return message

    def request(self, payload: dict) -> dict:
        if self.process.poll() is not None:
            raise ExternalError(f"Exécutant déjà arrêté (code {self.process.returncode}) :\n{self._stderr_tail()}")
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()
        return self._receive("traitement")

    def close(self) -> None:
        if getattr(self, "process", None) is None:
            return
        if self.process.poll() is None:
            try:
                self.process.stdin.write(json.dumps({"commande": "fin"}) + "\n")
                self.process.stdin.flush()
                self.process.wait(timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                self.process.kill()
                self.process.wait()
        self._stderr.close()
        shutil.rmtree(self.workdir, ignore_errors=True)
        self.process = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
