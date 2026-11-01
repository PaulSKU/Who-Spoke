"""Environnement de lancement et dossiers temporaires de l'application (D17, amendement 1).

Ce module est importé avant gradio, huggingface_hub, pyannote et speechbrain : il ne doit
importer que la bibliothèque standard (et `whospoke.telemetry`, qui n'importe qu'elle).

- Hors mode factice, `HF_HUB_OFFLINE=1` : les modèles sont lus dans le cache local, sans
  aucune requête au Hub. La variable doit être posée avant l'import de huggingface_hub,
  qui la lit une fois pour toutes.
- Toujours, les variables de `whospoke.telemetry.TELEMETRY_OFF` (D27) : télémétrie de
  pyannote.audio, de huggingface_hub, de Gradio et d'OpenTelemetry coupée. Elles sont déjà
  posées par l'import de `app` (qui importe `whospoke`) ; elles le sont aussi dans
  l'environnement passé ici, qui peut ne pas être `os.environ`.
- Chaque lancement travaille dans `<tmp>/whospoke-app/run-<pid>/` : audio normalisé,
  exports, et fichiers déposés ou servis par Gradio (`GRADIO_TEMP_DIR`). Le dossier est
  supprimé à la fermeture ; ceux d'un lancement interrompu brutalement (processus absent)
  le sont au lancement suivant.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from collections.abc import MutableMapping, Sequence
from pathlib import Path

from whospoke.telemetry import disable_telemetry

ROOT = Path(tempfile.gettempdir()) / "whospoke-app"
_RUN = re.compile(r"^run-(\d+)$")


def run_dir(root: Path = ROOT, pid: int | None = None) -> Path:
    """Dossier de travail du lancement `pid` (le processus courant par défaut)."""
    return root / f"run-{pid if pid is not None else os.getpid()}"


def configure_environment(environ: MutableMapping[str, str], argv: Sequence[str],
                          root: Path = ROOT) -> Path:
    """Pose les variables d'environnement du lancement et renvoie son dossier de travail."""
    work = run_dir(root)
    disable_telemetry(environ)
    environ["GRADIO_TEMP_DIR"] = str(work / "gradio")
    if "--factice" not in argv:
        environ["HF_HUB_OFFLINE"] = "1"
    return work


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # processus d'un autre utilisateur : on n'y touche pas
        return True
    return True


def remove_stale(root: Path = ROOT) -> list[Path]:
    """Supprime les dossiers `run-<pid>` dont le processus n'existe plus."""
    removed = []
    if not root.is_dir():
        return removed
    for path in sorted(root.iterdir()):
        match = _RUN.match(path.name)
        if path.is_dir() and match and int(match.group(1)) != os.getpid() and not _alive(int(match.group(1))):
            shutil.rmtree(path, ignore_errors=True)
            removed.append(path)
    return removed


def cleanup(work: Path, root: Path = ROOT) -> None:
    """Supprime le dossier de travail d'un lancement (jamais en dehors de `root`)."""
    work = Path(work)
    if work.resolve().parent != root.resolve() or not _RUN.match(work.name):
        raise ValueError(f"Dossier de travail inattendu : {work}")
    shutil.rmtree(work, ignore_errors=True)
