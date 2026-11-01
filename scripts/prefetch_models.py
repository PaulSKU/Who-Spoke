"""Préchargement des modèles de l'application de démonstration (D15 ; D17, amendement 1).

Usage :
    uv run python scripts/prefetch_models.py              # téléchargement, puis vérification hors ligne
    uv run python scripts/prefetch_models.py --verifier   # vérification hors ligne seule

L'application fonctionne hors ligne (`HF_HUB_OFFLINE=1`) : les modèles de tous ses moteurs
doivent donc se trouver dans le cache Hugging Face (`~/.cache/huggingface/hub`, ou
`$HF_HOME/hub`). Ce script, à lancer une fois avec accès réseau :

1. télécharge les dépôts nécessaires, avec le jeton `HF_TOKEN` lu dans `.env` (jamais
   affiché) :
   - `pyannote/speaker-diarization-community-1`, révision `main` : pipeline pyannote
     (segmentation, empreintes, PLDA) ;
   - le même dépôt à la révision figée de la baseline WeSpeaker : les empreintes
     WeSpeakerResNet34 sont le sous-dossier `embedding` de community-1 (pas de dépôt
     séparé ; `embedding: $model/embedding` dans son config.yaml) ;
   - `speechbrain/spkrec-ecapa-voxceleb` à sa révision figée : baseline ECAPA.
   La baseline MFCC n'utilise aucun modèle.
2. vérifie le chargement de chaque modèle dans un processus séparé, avec
   `HF_HUB_OFFLINE=1` posé avant tout import et un dossier courant vide, exactement comme
   l'application le fera : aucun accès réseau, aucun fichier écrit dans le dossier de
   lancement. Le chargement des empreintes (ECAPA, WeSpeaker) passe une seconde de bruit
   dans le réseau pour mesurer sa dimension, comme dans les expériences.

Option interne `--verification-hors-ligne` : étape 2, dans le processus enfant.
Code de sortie : 0 si tout est en cache et se charge, 1 si un téléchargement échoue,
2 si une vérification échoue.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from whospoke.embeddings import ECAPA_REVISION, ECAPA_SOURCE, WESPEAKER_REVISION, WESPEAKER_SOURCE
from whospoke.pipelines.pyannote_community1 import MODEL_ID as PYANNOTE_ID

SCRIPT = Path(__file__).resolve()


@dataclass(frozen=True)
class Repo:
    """Un dépôt du Hub à placer dans le cache, et les moteurs qui s'en servent."""

    repo_id: str
    revision: str
    used_by: str


REPOS = (
    Repo(PYANNOTE_ID, "main", "pyannote community-1 (segmentation, empreintes WeSpeaker, PLDA)"),
    Repo(WESPEAKER_SOURCE, WESPEAKER_REVISION, "baseline WeSpeaker (sous-dossier embedding de community-1)"),
    Repo(ECAPA_SOURCE, ECAPA_REVISION, "baseline ECAPA"),
)


def read_token() -> str:
    """HF_TOKEN lu dans .env (jamais affiché) ; erreur explicite s'il manque."""
    from whospoke.pipelines.pyannote_community1 import _hf_token

    return _hf_token()


def download(repos=REPOS, token: str | None = None,
             downloader: Callable | None = None, out=print) -> list[str]:
    """Télécharge chaque dépôt dans le cache ; renvoie la liste des échecs."""
    if downloader is None:
        from huggingface_hub import snapshot_download as downloader
    failures = []
    for repo in repos:
        out(f"Téléchargement : {repo.repo_id}@{repo.revision[:12]} ({repo.used_by})")
        try:
            path = downloader(repo_id=repo.repo_id, revision=repo.revision, token=token)
        except Exception as error:  # message du Hub affiché tel quel (jamais le jeton)
            failures.append(f"{repo.repo_id}@{repo.revision[:12]} : {type(error).__name__}: {error}")
            out(f"  échec : {type(error).__name__}: {error}")
        else:
            out(f"  en cache : {path}")
    return failures


def default_loaders() -> dict[str, Callable[[], object]]:
    """Chargements à vérifier, identiques à ceux des moteurs de l'application (CPU)."""

    def pyannote():
        from whospoke.pipelines.pyannote_community1 import PyannoteCommunity1

        return PyannoteCommunity1(device="cpu")

    def wespeaker():
        from whospoke.embeddings import SpeakerEmbedder

        return SpeakerEmbedder("wespeaker", device="cpu")

    def ecapa():
        from whospoke.embeddings import SpeakerEmbedder

        return SpeakerEmbedder("ecapa", device="cpu")

    return {"pyannote community-1": pyannote, "baseline WeSpeaker": wespeaker, "baseline ECAPA": ecapa}


def verify_offline(loaders: dict[str, Callable[[], object]] | None = None, out=print) -> list[str]:
    """Charge chaque modèle sans réseau (processus enfant) ; renvoie la liste des échecs."""
    if os.environ.get("HF_HUB_OFFLINE") != "1":
        raise RuntimeError("Vérification à lancer avec HF_HUB_OFFLINE=1 (processus enfant de ce script)")
    import huggingface_hub.constants

    if not huggingface_hub.constants.HF_HUB_OFFLINE:
        raise RuntimeError("huggingface_hub importé avant HF_HUB_OFFLINE=1")
    failures = []
    for name, load in (loaders or default_loaders()).items():
        try:
            load()
        except Exception as error:
            failures.append(f"{name} : {type(error).__name__}: {error}")
            out(f"Hors ligne, {name} : ÉCHEC ({type(error).__name__}: {error})")
        else:
            out(f"Hors ligne, {name} : chargé depuis le cache")
    return failures


def run_offline_check(runner: Callable = subprocess.run, out=print) -> bool:
    """Lance la vérification dans un processus enfant hors ligne, depuis un dossier vide.

    Vrai si le chargement réussit et si le dossier courant de l'enfant est resté vide
    (aucun `pretrained_models/` ni autre fichier écrit à côté du lancement).
    """
    env = dict(os.environ, HF_HUB_OFFLINE="1")
    with tempfile.TemporaryDirectory(prefix="prefetch-") as launch:
        completed = runner([sys.executable, str(SCRIPT), "--verification-hors-ligne"],
                           cwd=launch, env=env)
        leftovers = sorted(path.name for path in Path(launch).iterdir())
    if leftovers:
        out(f"Fichiers écrits dans le dossier de lancement : {', '.join(leftovers)}")
    return completed.returncode == 0 and not leftovers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Télécharge les modèles de l'application, puis vérifie leur chargement hors ligne.")
    parser.add_argument("--verifier", action="store_true",
                        help="vérification hors ligne seule, sans téléchargement")
    parser.add_argument("--verification-hors-ligne", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.verification_hors_ligne:
        return 2 if verify_offline() else 0

    if not args.verifier:
        failures = download(token=read_token())
        if failures:
            print("Téléchargement incomplet :\n- " + "\n- ".join(failures))
            return 1
    if not run_offline_check():
        print("Vérification hors ligne : échec (voir ci-dessus).")
        return 2
    print("Tous les modèles de l'application sont en cache et se chargent hors ligne.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
