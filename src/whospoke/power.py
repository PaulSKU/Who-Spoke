"""Contrôle de l'alimentation pendant une exécution (D21 §3, protocole §3.5).

Sur macOS, `pmset -g batt` indique la source d'alimentation sur sa première ligne :
« Now drawing from 'AC Power' » (secteur) ou « Now drawing from 'Battery Power' »
(batterie). Un relevé dont la source ne peut pas être lue (hors macOS, commande absente,
sortie inattendue) a une source `null`.

Règle de conformité d'un temps de calcul (D21 §3) : `true` si tous les relevés sont sur
secteur, `false` si au moins un relevé est sur batterie (ou sur une autre source que le
secteur), `null` sinon (aucun relevé, ou au moins un relevé illisible sans relevé hors
secteur).
"""

from __future__ import annotations

import re
import subprocess
import sys
import threading
from collections.abc import Callable
from datetime import datetime

COMMAND = ["pmset", "-g", "batt"]
INTERVAL_S = 60.0
SOURCES = {"AC Power": "secteur", "Battery Power": "batterie"}
_DRAWING = re.compile(r"Now drawing from '([^']+)'")


def parse_pmset(text: str | None) -> str | None:
    """Source d'alimentation lue dans la sortie de `pmset -g batt` (`None` si illisible).

    Une source autre que le secteur et la batterie (onduleur, par exemple) est rendue
    telle quelle : elle n'est pas le secteur, donc le relevé n'est pas conforme.
    """
    if not text:
        return None
    match = _DRAWING.search(text)
    if match is None:
        return None
    return SOURCES.get(match.group(1), match.group(1))


def read_pmset() -> str | None:
    """Sortie brute de `pmset -g batt`, ou `None` hors macOS ou en cas d'échec."""
    if sys.platform != "darwin":
        return None
    try:
        return subprocess.run(COMMAND, capture_output=True, text=True, timeout=10, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None


def power_reading(moment: str, reader: Callable[[], str | None] = read_pmset) -> dict:
    """Un relevé daté : moment (`debut`, `periodique`, `fin`), source et première ligne brute."""
    raw = reader()
    return {
        "date": datetime.now().astimezone().isoformat(timespec="seconds"),
        "moment": moment,
        "source": parse_pmset(raw),
        "brut": raw.strip().splitlines()[0] if raw and raw.strip() else None,
    }


def is_compliant(readings: list[dict] | None) -> bool | None:
    """Conformité d'un temps de calcul d'après les relevés (règle en tête du module)."""
    if not readings:
        return None
    sources = [reading.get("source") for reading in readings]
    if any(source is not None and source != "secteur" for source in sources):
        return False
    if any(source is None for source in sources):
        return None
    return True


class PowerMonitor:
    """Relevés au début, toutes les `interval_s` secondes dans un fil d'arrière-plan, et à la fin."""

    def __init__(self, interval_s: float = INTERVAL_S, reader: Callable[[], str | None] = read_pmset):
        self.interval_s = interval_s
        self.reader = reader
        self.readings: list[dict] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _record(self, moment: str) -> dict:
        reading = power_reading(moment, self.reader)
        with self._lock:
            self.readings.append(reading)
        return reading

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_s):
            self._record("periodique")

    def start(self) -> dict:
        reading = self._record("debut")
        self._thread = threading.Thread(target=self._loop, name="releves-alimentation", daemon=True)
        self._thread.start()
        return reading

    def stop(self) -> dict:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        return self._record("fin")

    def block(self) -> dict:
        """Bloc `alimentation` consigné dans `execution_<device>.json`."""
        with self._lock:
            readings = list(self.readings)
        return {
            "commande": " ".join(COMMAND),
            "intervalle_s": self.interval_s,
            "releves": readings,
            "conforme": is_compliant(readings),
        }
