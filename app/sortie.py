"""Résultat d'une analyse : statistiques par locuteur, renommage, exports, DER (D17).

Logique hors affichage de l'onglet « Analyse », testée dans tests/test_app_sortie.py.

Statistiques d'un locuteur, calculées sur l'annotation du moteur :
- temps de parole : durée de la réunion de ses segments ;
- nombre d'interventions : nombre de plages disjointes de cette réunion (deux segments
  contigus ou qui se recouvrent forment une seule intervention) ;
- part de chevauchement : part de son temps de parole pendant laquelle au moins un autre
  locuteur parle aussi (fraction entre 0 et 1).

Renommage : les identifiants du moteur (`SPK_00`, `SPEAKER_00`…) restent la clé des
segments dans le JSON ; le nom choisi n'apparaît que dans `locuteurs[].nom` et dans le
RTTM exporté, où les blancs sont remplacés par `_` (un champ RTTM ne contient pas d'espace).
"""

from __future__ import annotations

import io
import re
import tempfile
from pathlib import Path

import numpy as np
from pyannote.core import Annotation, Segment, Timeline

from whospoke.evaluation.metrics import CONDITIONS, DiarizationEvaluator
from whospoke.experiment import load_rttm

_DECIMALS = 3


def speaker_labels(annotation: Annotation) -> list[str]:
    """Identifiants des locuteurs, dans l'ordre de leur première prise de parole."""
    first: dict[str, float] = {}
    for segment, _, label in annotation.itertracks(yield_label=True):
        first[label] = min(first.get(label, segment.start), segment.start)
    return sorted(first, key=lambda label: (first[label], label))


def resolve_names(labels: list[str], names: dict[str, str] | None = None) -> dict[str, str]:
    """Nom affiché de chaque identifiant : le nom saisi, ou l'identifiant s'il est vide.

    Lève `ValueError` si deux locuteurs reçoivent le même nom : le RTTM exporté les
    fusionnerait sans le dire.
    """
    names = names or {}
    resolved = {label: (names.get(label) or "").strip() or label for label in labels}
    seen: dict[str, str] = {}
    for label, name in resolved.items():
        key = rttm_name(name)
        if key in seen:
            raise ValueError(f"Nom en double : {name!r} ({seen[key]} et {label})")
        seen[key] = label
    return resolved


def rttm_name(name: str) -> str:
    """Nom utilisable dans un champ RTTM (sans blanc)."""
    return re.sub(r"\s+", "_", name.strip())


def speaker_stats(annotation: Annotation, names: dict[str, str] | None = None) -> list[dict]:
    """Une entrée par locuteur, dans l'ordre de première prise de parole."""
    labels = speaker_labels(annotation)
    resolved = resolve_names(labels, names)
    timelines = {label: annotation.label_timeline(label, copy=True).support() for label in labels}
    stats = []
    for label in labels:
        own = timelines[label]
        others = Timeline(
            [segment for other in labels if other != label for segment in timelines[other]]
        ).support()
        speech = own.duration()
        overlap = own.crop(others, mode="intersection").support().duration() if len(others) else 0.0
        stats.append({
            "id": label,
            "nom": resolved[label],
            "temps_parole_s": round(speech, _DECIMALS),
            "n_interventions": len(own),
            "part_chevauchement": round(overlap / speech, 4) if speech > 0 else 0.0,
        })
    return stats


def segments(annotation: Annotation) -> list[dict]:
    """Segments triés par début : `{debut, fin, locuteur}` (identifiant du moteur)."""
    rows = [
        {"debut": round(segment.start, _DECIMALS), "fin": round(segment.end, _DECIMALS), "locuteur": label}
        for segment, _, label in annotation.itertracks(yield_label=True)
    ]
    return sorted(rows, key=lambda row: (row["debut"], row["fin"], row["locuteur"]))


def to_json(
    annotation: Annotation,
    uri: str,
    duration_s: float,
    engine: str,
    configuration: dict,
    compute_s: float,
    names: dict[str, str] | None = None,
) -> dict:
    """Export JSON du résultat, au format convenu pour l'onglet « Analyse »."""
    return {
        "uri": uri,
        "duree_s": round(duration_s, _DECIMALS),
        "moteur": engine,
        "configuration": configuration,
        "temps_calcul_s": round(compute_s, _DECIMALS),
        "locuteurs": speaker_stats(annotation, names),
        "segments": segments(annotation),
    }


def to_rttm(annotation: Annotation, uri: str, names: dict[str, str] | None = None) -> str:
    """Export RTTM, avec les noms choisis à la place des identifiants."""
    resolved = resolve_names(speaker_labels(annotation), names)
    renamed = annotation.rename_labels({label: rttm_name(name) for label, name in resolved.items()})
    renamed.uri = rttm_name(uri)
    buffer = io.StringIO()
    renamed.write_rttm(buffer)
    return buffer.getvalue()


def peaks(waveform: np.ndarray, n_points: int = 4000) -> list[float]:
    """Enveloppe de la forme d'onde (maximum absolu par tranche), pour l'affichage.

    Évite de faire décoder tout le fichier par le navigateur : la forme d'onde est
    dessinée à partir de ces valeurs, le son étant lu en flux.
    """
    y = np.abs(np.asarray(waveform, dtype=np.float32).reshape(-1))
    if len(y) == 0:
        return []
    n_points = max(1, min(n_points, len(y)))
    edges = np.linspace(0, len(y), n_points + 1).astype(int)
    values = np.maximum.reduceat(y, edges[:-1])
    top = float(values.max())
    if top > 0:
        values = values / top
    return [round(float(v), 4) for v in values]


def read_reference(path: str | Path) -> Annotation:
    """Annotation d'une référence RTTM déposée (un seul fichier, un seul uri)."""
    path = Path(path)
    rows = [line.split() for line in path.read_text().splitlines()]
    uris = {fields[1] for fields in rows if len(fields) > 1 and fields[0] == "SPEAKER"}
    if not uris:
        raise ValueError(f"{path.name} : aucune ligne SPEAKER")
    if len(uris) > 1:
        raise ValueError(f"{path.name} : plusieurs fichiers dans la référence ({', '.join(sorted(uris))})")
    return load_rttm(path, uris.pop())


def der_report(reference: Annotation, hypothesis: Annotation, duration_s: float) -> dict:
    """DER décomposé de l'hypothèse face à une référence, sur tout le fichier analysé.

    Mêmes métriques que le protocole (`DiarizationEvaluator`), dans les deux conditions
    de collar, chevauchements comptés ; l'UEM est l'audio analysé, de 0 à sa durée.
    """
    uem = Timeline([Segment(0.0, duration_s)])
    reference = reference.crop(uem, mode="intersection")
    reference.uri = hypothesis.uri
    if reference.get_timeline().duration() == 0.0:
        raise ValueError("La référence ne contient aucune parole dans l'audio analysé")
    result = DiarizationEvaluator().add(reference, hypothesis, uem=uem)
    return {name: result[name] for name in CONDITIONS} | {
        "zones": result["zones"],
        "n_locuteurs": result["n_locuteurs"],
    }


def write_exports(directory: Path, stem: str, rttm: str, json_text: str) -> tuple[Path, Path]:
    """Écrit les deux exports dans `directory` et renvoie leurs chemins."""
    directory.mkdir(parents=True, exist_ok=True)
    rttm_path = directory / f"{stem}.rttm"
    json_path = directory / f"{stem}.json"
    rttm_path.write_text(rttm)
    json_path.write_text(json_text)
    return rttm_path, json_path


def new_work_dir(root: Path | None = None) -> Path:
    """Dossier de travail d'une analyse (audio normalisé, exports), hors du dépôt."""
    return Path(tempfile.mkdtemp(prefix="analyse-", dir=root))
