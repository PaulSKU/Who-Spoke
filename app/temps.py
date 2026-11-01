"""Estimation du temps restant d'une analyse, à partir du RTF mesuré (D17, protocole §3.5).

Le RTF d'un moteur est lu dans `results/leaderboard.csv`, sur les lignes dev et test de
l'expérience qui sert de source à ce moteur (`app/moteurs.py`), dans la colonne du
périphérique choisi (D17, amendement 1) : `rtf_cpu` pour le CPU seul, `rtf` pour le
périphérique de l'exécution principale de l'expérience. Pour une expérience exécutée en
CPU, `rtf` sert de repli si `rtf_cpu` est vide (même périphérique). On prend la plus
grande valeur entre dev et test, pour ne pas annoncer un temps trop court. Le RTF exclut
le chargement des modèles et un préchauffage, et porte sur des réunions longues.

Estimation (D17, amendement 2) : une fourchette, de surcoût + RTF × durée à surcoût +
1,3 × RTF × durée (`HIGH_FACTOR`). Le surcoût fixe, mesuré au premier appel après
chargement (`scripts/measure_overhead.py`), est rangé avec sa date à côté de la
correspondance des moteurs (`app.moteurs.FIXED_OVERHEAD`) ; il n'est compté que pour un
moteur froid, c'est-à-dire ni chargé ni préchauffé. Une fois l'analyse lancée,
l'estimation est recalée sur la vitesse observée depuis le début de l'étape la plus longue
(`recalibrated_remaining_s`), dont le poids relatif est lu dans les durées par étape de
l'expérience source (`step_shares`). C'est un affichage, pas une mesure au sens de D21 :
un temps non conforme peut l'alimenter.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

from whospoke.experiment import REPO_ROOT

LEADERBOARD = REPO_ROOT / "results" / "leaderboard.csv"
PARTITIONS = ("dev", "test")
HIGH_FACTOR = 1.3          # borne haute = surcoût + 1,3 × RTF × durée (D17, amendement 2)
MIN_OBSERVED_S = 1.0       # durée minimale observée dans l'étape la plus longue avant recalage
MIN_OBSERVED_FRACTION = 0.02


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


def announced_s(rtf: float | None, duration_s: float, overhead_s: float = 0.0) -> float | None:
    """Borne basse du temps annoncé (s) : surcoût fixe + RTF × durée ; None sans RTF mesuré."""
    if rtf is None:
        return None
    return overhead_s + rtf * duration_s


def announced_range_s(rtf: float | None, duration_s: float,
                      overhead_s: float = 0.0) -> tuple[float, float] | None:
    """Fourchette annoncée (s) : (surcoût + RTF × durée, surcoût + 1,3 × RTF × durée)."""
    if rtf is None:
        return None
    return overhead_s + rtf * duration_s, overhead_s + HIGH_FACTOR * rtf * duration_s


def remaining_s(rtf: float | None, duration_s: float, elapsed_s: float,
                overhead_s: float = 0.0) -> float | None:
    """Temps de calcul restant estimé (s), borne basse ; None sans RTF mesuré.

    Estimation : surcoût fixe + RTF × durée de l'audio − temps déjà écoulé, jamais
    négative. Une fois l'estimation dépassée, la valeur reste à 0 : l'interface l'indique
    comme telle.
    """
    announced = announced_s(rtf, duration_s, overhead_s)
    return None if announced is None else max(0.0, announced - elapsed_s)


def remaining_range_s(rtf: float | None, duration_s: float, elapsed_s: float,
                      overhead_s: float = 0.0) -> tuple[float, float] | None:
    """Fourchette du temps restant (s), chaque borne diminuée du temps écoulé, jamais négative."""
    announced = announced_range_s(rtf, duration_s, overhead_s)
    if announced is None:
        return None
    return max(0.0, announced[0] - elapsed_s), max(0.0, announced[1] - elapsed_s)


def step_shares(execution: Path) -> dict[str, float]:
    """Part de chaque étape dans le temps de calcul de l'expérience source.

    Somme des `etapes_s` de tous les fichiers de `execution_<périphérique>.json`, divisée
    par le total ; dictionnaire vide si le fichier ou les durées manquent.
    """
    try:
        files = json.loads(execution.read_text()).get("fichiers") or []
    except (OSError, ValueError):
        return {}
    totals: dict[str, float] = {}
    for item in files:
        for step, seconds in (item.get("etapes_s") or {}).items():
            totals[step] = totals.get(step, 0.0) + float(seconds)
    grand = sum(totals.values())
    return {step: value / grand for step, value in totals.items()} if grand > 0 else {}


def longest_step(steps: list[str] | tuple[str, ...], shares: dict[str, float]) -> str | None:
    """Étape la plus longue de l'expérience source parmi `steps`, ou None sans durées."""
    known = [step for step in steps if shares.get(step, 0.0) > 0.0]
    return max(known, key=lambda step: shares[step]) if known else None


def recalibrated_remaining_s(steps: list[str] | tuple[str, ...], shares: dict[str, float],
                             fractions: dict[str, float], in_longest_s: float | None) -> float | None:
    """Temps restant recalé sur la vitesse observée dans l'étape la plus longue (s).

    `fractions` : avancement de chaque étape (0 à 1) ; `in_longest_s` : temps écoulé
    depuis le début de l'étape la plus longue (None si elle n'a pas commencé). La durée
    complète de cette étape est extrapolée de la fraction faite ; les étapes suivantes
    sont comptées à proportion de leur part dans l'expérience source. None tant que
    l'observation est trop courte (moins de `MIN_OBSERVED_S` ou de `MIN_OBSERVED_FRACTION`).
    """
    longest = longest_step(steps, shares)
    if longest is None or in_longest_s is None:
        return None
    done = min(1.0, fractions.get(longest, 0.0))
    if in_longest_s < MIN_OBSERVED_S or done < MIN_OBSERVED_FRACTION:
        return None
    full_s = in_longest_s / done
    after = steps[list(steps).index(longest) + 1:]
    rest_share = sum(shares.get(step, 0.0) * (1.0 - min(1.0, fractions.get(step, 0.0))) for step in after)
    return max(0.0, full_s * (1.0 - done) + full_s * rest_share / shares[longest])


Range = tuple[float, float]


def cumulative_remaining_s(runs: list[tuple[float | None, float, float | None, bool]],
                           duration_s: float, recalibrated: list[float | None] | None = None) -> Range | None:
    """Fourchette du temps restant cumulé de moteurs exécutés l'un après l'autre (D26, I5).

    `runs` : pour chaque moteur, (RTF mesuré, surcoût fixe compté, temps écoulé depuis son
    démarrage ou None s'il n'a pas démarré, terminé ?). Un moteur terminé ne compte plus ;
    un moteur en cours compte pour sa fourchette moins le temps écoulé (jamais négative),
    ou pour son temps recalé s'il est connu (`recalibrated`, même ordre) ; un moteur à
    venir pour sa fourchette complète. None si un moteur non terminé n'a ni RTF mesuré ni
    temps recalé.
    """
    low = high = 0.0
    for index, (rtf, overhead_s, elapsed, done) in enumerate(runs):
        if done:
            continue
        fixed = recalibrated[index] if recalibrated else None
        if fixed is not None:
            low, high = low + fixed, high + fixed
            continue
        span = remaining_range_s(rtf, duration_s, elapsed or 0.0, overhead_s)
        if span is None:
            return None
        low, high = low + span[0], high + span[1]
    return low, high


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


def format_range(span: Range | None) -> str:
    """« entre 15 s et 19 s » ; « environ 15 s » si les deux bornes s'affichent pareil."""
    if span is None:
        return "—"
    low, high = format_duration(span[0]), format_duration(span[1])
    return f"environ {low}" if low == high else f"entre {low} et {high}"
