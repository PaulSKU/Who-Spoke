"""Métriques du protocole d'évaluation (docs/protocole-eval.md §3 et §4).

Les chevauchements sont toujours comptés (`skip_overlap=False`). Dans pyannote.metrics,
`collar` est la largeur totale de la zone exclue autour de chaque frontière de référence :
une tolérance de 0,25 s de part et d'autre correspond donc à `collar=0.5`. Ce point est
vérifié par tests/test_protocole_eval.py (test « collar »).

L'agrégation sur plusieurs fichiers somme les durées d'erreur et de référence, puis fait
le rapport (§4) : c'est le comportement cumulatif natif des métriques pyannote. Les
métriques du nombre de locuteurs (§3.4) donnent au contraire un poids égal à chaque fichier.

Décomposition par zone (§3.2), en condition `collar_0` : la zone « chevauchement » est
l'intersection de l'UEM avec les instants où au moins deux locuteurs de référence parlent ;
la zone « sans chevauchement » est le reste de l'UEM (silences compris, où se produisent
les fausses alarmes).

Nombre de locuteurs (§3.4) : on compte les étiquettes distinctes de la référence et de
l'hypothèse après restriction à l'UEM.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from pyannote.core import Annotation, Segment, Timeline
from pyannote.metrics.diarization import DiarizationErrorRate, JaccardErrorRate

# Nom de condition -> valeur du paramètre `collar` de pyannote.metrics.
CONDITIONS: dict[str, float] = {"collar_0": 0.0, "collar_0_25": 0.5}

# Zones de la décomposition §3.2, toujours en collar_0.
ZONES = ("sans_chevauchement", "chevauchement")

_TOTAL = "total"
_MISSED = "missed detection"
_FALSE_ALARM = "false alarm"
_CONFUSION = "confusion"


def _rates(components: dict[str, float], jer: float | None = None) -> dict[str, float]:
    """Convertit des durées (s) en taux (%) rapportés à la parole de référence."""
    total = components[_TOTAL]
    if total == 0.0:
        raise ValueError("Durée de parole de référence nulle : DER indéfini")
    missed = components[_MISSED]
    false_alarm = components[_FALSE_ALARM]
    confusion = components[_CONFUSION]
    rates = {
        "der": 100.0 * (missed + false_alarm + confusion) / total,
        "manquee": 100.0 * missed / total,
        "fausse_alarme": 100.0 * false_alarm / total,
        "confusion": 100.0 * confusion / total,
    }
    if jer is not None:
        rates["jer"] = 100.0 * jer
    return rates


def _durations(components: dict[str, float]) -> dict[str, float]:
    return {
        "duree_reference_s": components[_TOTAL],
        "manquee_s": components[_MISSED],
        "fausse_alarme_s": components[_FALSE_ALARM],
        "confusion_s": components[_CONFUSION],
    }


def round_rates(rates: dict[str, float], ndigits: int = 2) -> dict[str, float]:
    """Arrondi à deux décimales, pour l'écriture de results.json (methode.md §4.3)."""
    return {key: round(value, ndigits) for key, value in rates.items()}


def full_uem(reference: Annotation, hypothesis: Annotation) -> Timeline:
    """UEM par défaut (protocole §2) : du début à la fin de ce qui est annoté."""
    extent = (reference.get_timeline() | hypothesis.get_timeline()).extent()
    return Timeline([Segment(0.0, extent.end)], uri=reference.uri)


def overlap_zones(reference: Annotation, uem: Timeline) -> dict[str, Timeline]:
    """Zones de chevauchement de la référence et leur complément, dans l'UEM (§3.2)."""
    uem = uem.support()
    overlap = reference.get_overlap().crop(uem, mode="intersection").support()
    return {"sans_chevauchement": uem.extrude(overlap).support(), "chevauchement": overlap}


def speaker_counts(reference: Annotation, hypothesis: Annotation, uem: Timeline) -> tuple[int, int]:
    """(K, K̂) : nombre de locuteurs distincts de la référence et de l'hypothèse dans l'UEM."""
    k_ref = len(reference.crop(uem, mode="intersection").labels())
    k_hyp = len(hypothesis.crop(uem, mode="intersection").labels())
    return k_ref, k_hyp


def speaker_count_metrics(counts: Sequence[tuple[int, int]]) -> dict[str, float]:
    """Erreur absolue moyenne |K̂ − K| et taux exact (%), poids égal par fichier (§3.4)."""
    if not counts:
        raise ValueError("Aucun fichier évalué")
    errors = np.array([abs(k_hyp - k_ref) for k_ref, k_hyp in counts], dtype=float)
    return {
        "erreur_absolue_moyenne": float(errors.mean()),
        "taux_exact": 100.0 * float((errors == 0).mean()),
    }


class DiarizationEvaluator:
    """Accumule les métriques fichier par fichier (DER, JER, zones, nombre de locuteurs)."""

    def __init__(self) -> None:
        self._der = {
            name: DiarizationErrorRate(collar=collar, skip_overlap=False)
            for name, collar in CONDITIONS.items()
        }
        self._jer = {
            name: JaccardErrorRate(collar=collar, skip_overlap=False)
            for name, collar in CONDITIONS.items()
        }
        self._zone_der = {zone: DiarizationErrorRate(collar=0.0, skip_overlap=False) for zone in ZONES}
        self._counts: list[tuple[int, int]] = []
        self._rows: list[dict] = []

    def add(
        self,
        reference: Annotation,
        hypothesis: Annotation,
        uem: Timeline | None = None,
    ) -> dict[str, dict]:
        """Évalue un fichier.

        Renvoie, par condition, les taux (%) et les durées (s) ; sous `zones`, la même
        chose pour chaque zone de la décomposition §3.2 (None si la zone est vide) ; sous
        `n_locuteurs`, les nombres de locuteurs de la référence et de l'hypothèse.
        """
        if uem is None:
            uem = full_uem(reference, hypothesis)
        result: dict[str, dict] = {}
        for name in CONDITIONS:
            components = self._der[name](reference, hypothesis, uem=uem, detailed=True)
            jer = self._jer[name](reference, hypothesis, uem=uem)
            result[name] = _rates(components, jer) | _durations(components)

        result["zones"] = {}
        for zone, timeline in overlap_zones(reference, uem).items():
            if timeline.duration() == 0.0:
                result["zones"][zone] = None
                continue
            components = self._zone_der[zone](reference, hypothesis, uem=timeline, detailed=True)
            if components[_TOTAL] == 0.0:
                # Zone sans parole de référence (fichier entièrement silencieux).
                result["zones"][zone] = None
                continue
            result["zones"][zone] = _rates(components) | _durations(components)

        k_ref, k_hyp = speaker_counts(reference, hypothesis, uem)
        self._counts.append((k_ref, k_hyp))
        result["n_locuteurs"] = {"reference": k_ref, "hypothese": k_hyp}

        self._rows.append(_flatten(reference.uri, result))
        return result

    def report(self) -> dict:
        """Métriques globales (%), en rapport des sommes sur tous les fichiers (§4).

        Clés : une par condition, `der_zones_sans_chevauchement`, `der_zones_chevauchement`
        (None si aucune parole dans la zone) et `n_locuteurs`.
        """
        report: dict = {
            name: _rates(self._der[name][:], abs(self._jer[name])) for name in CONDITIONS
        }
        for zone in ZONES:
            components = self._zone_der[zone][:]
            report[f"der_zones_{zone}"] = (
                _rates(components)["der"] if components.get(_TOTAL, 0.0) > 0.0 else None
            )
        report["n_locuteurs"] = speaker_count_metrics(self._counts)
        return report

    def per_file(self) -> list[dict]:
        """Une ligne par fichier évalué, dans l'ordre d'ajout (pour per_file_*.csv)."""
        return [dict(row) for row in self._rows]


# Suffixe de colonne par condition dans les tables par fichier et le leaderboard.
_SUFFIX = {"collar_0": "c0", "collar_0_25": "c025"}


def _flatten(uri: str | None, result: dict) -> dict:
    """Ligne plate d'un fichier : taux en %, durées en s, nombres de locuteurs."""
    row: dict = {"uri": uri}
    for name, suffix in _SUFFIX.items():
        values = result[name]
        for key in ("der", "manquee", "fausse_alarme", "confusion", "jer"):
            row[f"{key}_{suffix}"] = values[key]
        for key in ("manquee_s", "fausse_alarme_s", "confusion_s"):
            row[f"{key.removesuffix('_s')}_{suffix}_s"] = values[key]
        row[f"duree_reference_{suffix}_s"] = values["duree_reference_s"]
    for zone in ZONES:
        values = result["zones"][zone]
        row[f"der_{zone}"] = None if values is None else values["der"]
        row[f"duree_reference_{zone}_s"] = 0.0 if values is None else values["duree_reference_s"]
    row["n_locuteurs_reference"] = result["n_locuteurs"]["reference"]
    row["n_locuteurs_hypothese"] = result["n_locuteurs"]["hypothese"]
    row["erreur_n_locuteurs"] = row["n_locuteurs_hypothese"] - row["n_locuteurs_reference"]
    return row


# --- Comparaisons entre expériences (§4) -------------------------------------------


def _pooled_der(errors: np.ndarray, totals: np.ndarray) -> np.ndarray:
    """DER (%) en rapport des sommes, sur la dernière dimension."""
    return 100.0 * errors.sum(axis=-1) / totals.sum(axis=-1)


def bootstrap_der_ci(
    errors: Sequence[float],
    totals: Sequence[float],
    errors_b: Sequence[float] | None = None,
    totals_b: Sequence[float] | None = None,
    n_resamples: int = 1000,
    seed: int = 0,
    confidence: float = 0.95,
) -> dict[str, float]:
    """Intervalle de confiance par bootstrap sur les fichiers (§4, méthode des percentiles).

    `errors[i]` est la durée d'erreur (manquée + fausse alarme + confusion, en s) du
    fichier i et `totals[i]` sa durée de parole de référence. À chaque tirage, on tire
    les fichiers avec remise et on recalcule le DER en rapport des sommes.

    Si `errors_b` et `totals_b` sont fournis (même ordre de fichiers), l'intervalle porte
    sur la différence appariée DER(a) − DER(b) : les mêmes fichiers sont tirés pour a et b.
    Renvoie `{"estimation", "borne_inf", "borne_sup"}` en points de pourcentage.
    """
    errors_a = np.asarray(errors, dtype=float)
    totals_a = np.asarray(totals, dtype=float)
    n = len(errors_a)
    if n == 0 or len(totals_a) != n:
        raise ValueError("Listes d'erreurs et de durées vides ou de longueurs différentes")
    paired = errors_b is not None or totals_b is not None
    if paired:
        if errors_b is None or totals_b is None:
            raise ValueError("errors_b et totals_b vont ensemble")
        errors_b_arr = np.asarray(errors_b, dtype=float)
        totals_b_arr = np.asarray(totals_b, dtype=float)
        if len(errors_b_arr) != n or len(totals_b_arr) != n:
            raise ValueError("Les deux systèmes doivent porter sur les mêmes fichiers")

    def statistic(index: np.ndarray) -> np.ndarray:
        value = _pooled_der(errors_a[index], totals_a[index])
        if paired:
            value = value - _pooled_der(errors_b_arr[index], totals_b_arr[index])
        return value

    rng = np.random.default_rng(seed)
    samples = statistic(rng.integers(0, n, size=(n_resamples, n)))
    tail = 100.0 * (1.0 - confidence) / 2.0
    low, high = np.percentile(samples, [tail, 100.0 - tail])
    return {
        "estimation": float(statistic(np.arange(n))),
        "borne_inf": float(low),
        "borne_sup": float(high),
    }


def count_wins(der_a: Sequence[float], der_b: Sequence[float]) -> dict[str, int]:
    """Nombre de fichiers où a fait mieux que b, moins bien, ou égal (§4)."""
    a, b = np.asarray(der_a, dtype=float), np.asarray(der_b, dtype=float)
    if a.shape != b.shape:
        raise ValueError("Les deux systèmes doivent porter sur les mêmes fichiers")
    return {
        "a_meilleur": int((a < b).sum()),
        "b_meilleur": int((a > b).sum()),
        "egalite": int((a == b).sum()),
    }
