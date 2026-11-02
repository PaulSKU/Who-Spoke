"""Charge moyenne de la machine (D21, amendement du 01/11 : charge et campagne de temps).

La charge moyenne est celle de `sysctl vm.loadavg` sur macOS, lue par `os.getloadavg()`
(mêmes valeurs, sur 1, 5 et 15 minutes ; sans sous-processus). Une charge est
« concurrente » si la charge sur 1 minute dépasse le nombre de cœurs de performance à un
relevé au moins (règle 1 de l'amendement). Le nombre de cœurs de performance est lu par
`sysctl -n hw.perflevel0.physicalcpu` (Apple Silicon) ; à défaut, le nombre de cœurs.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from datetime import datetime

from whospoke import power

SOURCE = "os.getloadavg() (sysctl vm.loadavg)"
PERF_CORES_COMMAND = ["sysctl", "-n", "hw.perflevel0.physicalcpu"]

LoadReader = Callable[[], tuple[float, float, float] | None]


def load_average() -> tuple[float, float, float] | None:
    """Charge moyenne sur 1, 5 et 15 min, ou None si elle ne peut pas être lue."""
    try:
        return os.getloadavg()
    except OSError:
        return None


def performance_cores() -> int:
    """Cœurs de performance (Apple Silicon), sinon nombre de cœurs logiques."""
    if sys.platform == "darwin":
        try:
            out = subprocess.run(PERF_CORES_COMMAND, capture_output=True, text=True, timeout=10, check=True)
            return int(out.stdout.strip())
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    return os.cpu_count() or 1


def reading(moment: str, power_reader: Callable[[], str | None] = power.read_pmset,
            load_reader: LoadReader = load_average) -> dict:
    """Un relevé daté : alimentation (comme `whospoke.power`) et charge moyenne."""
    record = power.power_reading(moment, power_reader)
    load = load_reader()
    record["horodatage"] = time.time()
    record["charge_1min"] = None if load is None else round(load[0], 2)
    record["charge_5min"] = None if load is None else round(load[1], 2)
    record["charge_15min"] = None if load is None else round(load[2], 2)
    return record


def concurrent_load(readings: list[dict], cores: int) -> bool | None:
    """Vrai si la charge sur 1 min dépasse `cores` à un relevé au moins ; None sans relevé lisible."""
    values = [r["charge_1min"] for r in readings if r.get("charge_1min") is not None]
    if not values:
        return None
    return any(value > cores for value in values)


class MachineMonitor:
    """Relevés d'alimentation et de charge au début, toutes les `interval_s` secondes, à la
    demande (`mark`) et à la fin, dans un fil d'arrière-plan."""

    def __init__(self, interval_s: float = 30.0, power_reader: Callable[[], str | None] = power.read_pmset,
                 load_reader: LoadReader = load_average) -> None:
        self.interval_s = interval_s
        self.power_reader = power_reader
        self.load_reader = load_reader
        self.readings: list[dict] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def mark(self, moment: str) -> dict:
        record = reading(moment, self.power_reader, self.load_reader)
        with self._lock:
            self.readings.append(record)
        return record

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_s):
            self.mark("periodique")

    def start(self) -> dict:
        record = self.mark("debut")
        self._thread = threading.Thread(target=self._loop, name="releves-machine", daemon=True)
        self._thread.start()
        return record

    def stop(self) -> dict:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        return self.mark("fin")

    def between(self, start: float, end: float) -> list[dict]:
        """Relevés dont l'horodatage est dans [start, end]."""
        with self._lock:
            return [r for r in self.readings if start <= r["horodatage"] <= end]


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
