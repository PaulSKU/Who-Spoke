"""Estimation du temps restant d'une analyse, à partir du RTF mesuré (D17, protocole §3.5).

Le RTF d'un moteur est lu dans `results/leaderboard.csv`, sur les lignes dev et test de
l'expérience qui sert de source à ce moteur (`app/moteurs.py`), dans la colonne du
périphérique choisi (D17, amendement 1) : `rtf_cpu` pour le CPU seul, `rtf` pour le
périphérique de l'exécution principale de l'expérience. Pour une expérience exécutée en
CPU, `rtf` sert de repli si `rtf_cpu` est vide (même périphérique). On prend la plus
grande valeur entre dev et test, pour ne pas annoncer un temps trop court. Le RTF exclut
le chargement des modèles : l'estimation ne porte que sur le calcul. C'est un affichage,
pas une mesure au sens de D21 : un temps non conforme peut l'alimenter.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

from whospoke.experiment import REPO_ROOT

LEADERBOARD = REPO_ROOT / "results" / "leaderboard.csv"
PARTITIONS = ("dev", "test")


@dataclass(frozen=True)
class MeasuredRtf:
    """RTF mesuré et sa provenance (affichée à côté de l'estimation)."""

    rtf: float
    exp_id: str
    device: str
    column: str

    def source(self) -> str:
        return f"{self.exp_id}, {self.device}, colonne {self.column}"


def measured_rtf(
    exp_id: str,
    device: str,
    exp_device: str,
    leaderboard: Path = LEADERBOARD,
) -> MeasuredRtf | None:
    """RTF mesuré de l'expérience `exp_id` sur `device`, ou None s'il n'a pas été mesuré.

    `exp_device` est le périphérique de l'exécution principale de l'expérience (clé
    `device` de son config.yaml).
    """
    if device == "cpu":
        columns = ["rtf_cpu"] + (["rtf"] if exp_device == "cpu" else [])
    elif device == exp_device:
        columns = ["rtf"]
    else:
        return None
    if not leaderboard.is_file():
        return None
    with leaderboard.open(newline="") as handle:
        rows = [row for row in csv.DictReader(handle)
                if row["exp_id"] == exp_id and row["partition"] in PARTITIONS]
    for column in columns:
        values = [float(row[column]) for row in rows if row.get(column) not in ("", None)]
        if values:
            return MeasuredRtf(max(values), exp_id, device, column)
    return None


def remaining_s(rtf: float | None, duration_s: float, elapsed_s: float) -> float | None:
    """Temps de calcul restant estimé (s) ; None sans RTF mesuré.

    Estimation : RTF × durée de l'audio − temps déjà écoulé, jamais négative. Une fois
    l'estimation dépassée, la valeur reste à 0 : l'interface l'indique comme telle.
    """
    if rtf is None:
        return None
    return max(0.0, rtf * duration_s - elapsed_s)


def format_duration(seconds: float | None) -> str:
    """« 4 s », « 2 min 05 s », « 1 h 02 min » ; « — » pour une valeur inconnue."""
    if seconds is None or math.isnan(seconds):
        return "—"
    seconds = max(0, int(round(seconds)))
    if seconds < 60:
        return f"{seconds} s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} min {seconds:02d} s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min"
