"""Cache des résultats d'analyse, plan de repli de la démonstration (audit R-D3, chantier C5).

Un résultat est réaffiché sans calcul quand on relance le même audio avec le même moteur,
les mêmes réglages et le même code. La clé est l'empreinte SHA-256 de :

- l'audio normalisé (échantillons du WAV 16 kHz mono, D15) : un même enregistrement
  déposé sous un autre nom ou un autre format donne la même clé ;
- le moteur (clé de `app.moteurs.SPECS`, et le mode factice) ;
- les réglages : périphérique, nombre de locuteurs, paramètres effectifs repris de
  l'expérience source (θ retenu compris) ;
- le commit du code, suffixé « +modifie » si l'arbre n'est pas propre (D18).

Le cache est rangé hors du dépôt, dans `~/.cache/whospoke/resultats/` (ou
`$WHOSPOKE_CACHE_DIR/resultats/`), un fichier JSON par résultat. Il ne contient ni audio
ni nom de fichier : seulement les segments, les durées et les réglages consignés. Il se
vide depuis l'interface ou par `--vider-cache`.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np

FORMAT_VERSION = 1


def default_dir() -> Path:
    base = os.environ.get("WHOSPOKE_CACHE_DIR")
    return (Path(base).expanduser() if base else Path.home() / ".cache" / "whospoke") / "resultats"


def code_version(repo_root: Path) -> str:
    """Commit du code, « +modifie » si l'arbre n'est pas propre (D18) ; « inconnu » hors git."""
    from whospoke.experiment import tree_is_clean

    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True,
                              check=True, timeout=10).stdout

    try:
        commit = git("rev-parse", "HEAD").strip()
        dirty = [line[3:].strip().strip('"') for line in git("status", "--porcelain").splitlines()]
    except (OSError, subprocess.SubprocessError):
        return "inconnu"
    return commit + ("" if tree_is_clean(dirty) else "+modifie")


def audio_fingerprint(samples: np.ndarray) -> str:
    """Empreinte SHA-256 des échantillons de l'audio normalisé."""
    return hashlib.sha256(np.ascontiguousarray(samples).tobytes()).hexdigest()


def result_key(fingerprint: str, engine: str, fake: bool, settings: dict, code: str) -> str:
    """Clé d'un résultat : empreinte de l'audio, moteur, réglages et commit."""
    parts = {"audio": fingerprint, "moteur": engine, "factice": fake, "reglages": settings, "code": code}
    canonical = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def annotation_tracks(annotation) -> list[list]:
    """Pistes d'une annotation : [début, fin, piste, locuteur], chevauchements compris.

    Les identifiants de piste entiers ou textuels sont gardés tels quels (JSON les
    restitue à l'identique) : l'annotation relue est égale à l'originale."""
    return [[segment.start, segment.end, track if isinstance(track, (int, str)) else str(track), str(label)]
            for segment, track, label in annotation.itertracks(yield_label=True)]


def annotation_from_tracks(tracks: list[list], uri: str):
    from pyannote.core import Annotation, Segment

    annotation = Annotation(uri=uri)
    for start, end, track, label in tracks:
        annotation[Segment(start, end), track] = label
    return annotation


class ResultCache:
    """Résultats rangés dans `directory`, un fichier `<clé>.json` chacun."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = Path(directory) if directory is not None else default_dir()

    def _path(self, key: str) -> Path:
        if len(key) != 64 or not all(c in "0123456789abcdef" for c in key):
            raise ValueError(f"Clé de cache invalide : {key!r}")
        return self.directory / f"{key}.json"

    def get(self, key: str) -> dict | None:
        """Entrée enregistrée, ou None (absente, illisible ou d'un autre format)."""
        try:
            entry = json.loads(self._path(key).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return entry if entry.get("version") == FORMAT_VERSION else None

    def put(self, key: str, entry: dict) -> Path:
        """Enregistre une entrée (écriture atomique) ; la date est ajoutée."""
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path(key)
        data = dict(entry, version=FORMAT_VERSION, date=datetime.now().isoformat(timespec="seconds"))
        tmp = path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
        return path

    def entries(self) -> list[Path]:
        return sorted(self.directory.glob("*.json")) if self.directory.is_dir() else []

    def stats(self) -> tuple[int, int]:
        """(nombre de résultats, taille totale en octets)."""
        paths = self.entries()
        return len(paths), sum(path.stat().st_size for path in paths)

    def clear(self) -> int:
        """Supprime tous les résultats (seulement les `<clé>.json` du dossier) ; renvoie leur nombre."""
        removed = 0
        for path in self.entries():
            if len(path.stem) == 64:
                path.unlink(missing_ok=True)
                removed += 1
        for tmp in self.directory.glob("*.tmp") if self.directory.is_dir() else []:
            tmp.unlink(missing_ok=True)
        return removed
