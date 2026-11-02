"""Emplacements des données, lecture des RTTM et UEM, état git (methode.md §2, protocole §2)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from pyannote.core import Annotation, Segment, Timeline

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"


# Conditions dégradées de SUMM-RE test (D24) : corpus `summre-<condition>`, signal lu dans
# `data/processed/summre_degrade/<condition>/`, références et UEM de SUMM-RE inchangés.
DEGRADED_PREFIX = "summre-"
DEGRADED_DIR = DATA_DIR / "processed" / "summre_degrade"


def degraded_condition(corpus: str) -> str | None:
    """Condition de D24 d'un corpus `summre-<condition>`, sinon None."""
    return corpus.removeprefix(DEGRADED_PREFIX) if corpus.startswith(DEGRADED_PREFIX) else None


def annotation_corpus(corpus: str) -> str:
    """Corpus dont viennent les références et l'UEM (SUMM-RE pour une condition dégradée)."""
    return "summre" if degraded_condition(corpus) else corpus


def hypothesis_dir(exp_dir: Path, corpus: str, name: str = "rttm") -> Path:
    """Dossier des hypothèses d'un jeu dans une expérience : `<name>/`, ou `<name>/<corpus>/`
    pour une condition dégradée (D24), dont les fichiers portent les identifiants de SUMM-RE
    test, communs à toutes les conditions."""
    return exp_dir / name / corpus if degraded_condition(corpus) else exp_dir / name


def processed_wav(corpus: str, uri: str) -> Path:
    condition = degraded_condition(corpus)
    if condition:
        return DEGRADED_DIR / condition / f"{uri}.wav"
    return DATA_DIR / "processed" / corpus / f"{uri}.wav"


def reference_rttm(corpus: str, uri: str) -> Path:
    return DATA_DIR / "processed" / annotation_corpus(corpus) / "rttm" / f"{uri}.rttm"


def uem_path(corpus: str, uri: str) -> Path:
    """UEM d'un fichier : versionné dans `data/splits/`, sauf pour le corpus maison, dont les
    UEM restent dans `data/processed/maison/uem/` (conventions d'annotation du corpus maison,
    amendement du 01/11 : copie versionnée seulement avec l'accord de tous les participants)."""
    if corpus == "maison":
        return DATA_DIR / "processed" / corpus / "uem" / f"{uri}.uem"
    return DATA_DIR / "splits" / annotation_corpus(corpus) / "uem" / f"{uri}.uem"


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


# Chemins contrôlés par la règle de l'arbre propre (D18) : ceux qui peuvent changer un
# résultat (code, configuration, données de partition, dépendances).
CONTROLLED_PREFIXES = ("src/", "scripts/", "configs/", "tests/", "data/splits/", "data/manifests/")
CONTROLLED_FILES = ("pyproject.toml", "uv.lock")


def is_controlled(path: str) -> bool:
    """Vrai si `path` (relatif à la racine du dépôt) relève de la règle de l'arbre propre."""
    path = path.strip().strip('"').removeprefix("./")
    return path in CONTROLLED_FILES or path.startswith(CONTROLLED_PREFIXES)


def tree_is_clean(uncommitted: list[str]) -> bool:
    """Arbre propre (D18) : aucun fichier non commité sous un chemin contrôlé."""
    return not any(is_controlled(path) for path in uncommitted)


def git_state() -> dict:
    """Commit courant, fichiers non commités et propreté de l'arbre (D18).

    `dirty` liste tous les fichiers modifiés ou non suivis, où qu'ils soient ; `clean`
    ne dépend que de ceux situés sous les chemins contrôlés (`is_controlled`).
    """
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout

    commit = git("rev-parse", "HEAD").strip()
    output = git("status", "--porcelain", "--untracked-files=all")
    dirty = [line[3:].strip().strip('"') for line in output.splitlines()]
    return {"commit": commit, "clean": tree_is_clean(dirty), "dirty": dirty}
