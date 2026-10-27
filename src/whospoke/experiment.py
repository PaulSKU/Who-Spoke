"""Emplacements des données, lecture des RTTM et UEM, état git (methode.md §2, protocole §2)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from pyannote.core import Annotation, Segment, Timeline

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"


def processed_wav(corpus: str, uri: str) -> Path:
    return DATA_DIR / "processed" / corpus / f"{uri}.wav"


def reference_rttm(corpus: str, uri: str) -> Path:
    return DATA_DIR / "processed" / corpus / "rttm" / f"{uri}.rttm"


def uem_path(corpus: str, uri: str) -> Path:
    return DATA_DIR / "splits" / corpus / "uem" / f"{uri}.uem"


def dataset_uris(list_path: str | Path) -> list[str]:
    """Identifiants d'une liste de partition (une ligne par fichier, chemin relatif au dépôt)."""
    path = REPO_ROOT / list_path
    uris = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if len(set(uris)) != len(uris):
        raise ValueError(f"{list_path} : identifiants en double")
    return uris


def load_rttm(path: Path, uri: str) -> Annotation:
    """Annotation d'un fichier RTTM ; chaque ligne doit porter l'uri attendu."""
    annotation = Annotation(uri=uri)
    for index, line in enumerate(path.read_text().splitlines()):
        fields = line.split()
        if not fields or fields[0] != "SPEAKER":
            continue
        if fields[1] != uri:
            raise ValueError(f"{path} : uri {fields[1]!r} au lieu de {uri!r}")
        start, duration = float(fields[3]), float(fields[4])
        annotation[Segment(start, start + duration), index] = fields[7]
    return annotation


def load_uem(path: Path, uri: str) -> Timeline:
    timeline = Timeline(uri=uri)
    for line in path.read_text().splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] != uri:
            raise ValueError(f"{path} : uri {fields[0]!r} au lieu de {uri!r}")
        timeline.add(Segment(float(fields[2]), float(fields[3])))
    return timeline


def git_state(exclude: Path | None = None) -> dict:
    """Commit courant et propreté de l'arbre.

    Les chemins sous `exclude` (le dossier de l'expérience en cours, produit par
    l'exécution elle-même) et `results/leaderboard.csv` (alimenté par l'évaluation) ne
    comptent pas : l'arbre est propre si rien d'autre n'est modifié ni non suivi.
    """
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout

    commit = git("rev-parse", "HEAD").strip()
    ignored = {"results/leaderboard.csv"}
    prefix = None
    if exclude is not None and exclude.resolve().is_relative_to(REPO_ROOT):
        prefix = exclude.resolve().relative_to(REPO_ROOT).as_posix().rstrip("/") + "/"
    dirty = []
    for line in git("status", "--porcelain", "--untracked-files=all").splitlines():
        path = line[3:].strip().strip('"')
        if path in ignored or (prefix and (path + "/").startswith(prefix)):
            continue
        dirty.append(path)
    return {"commit": commit, "clean": not dirty, "dirty": dirty}
