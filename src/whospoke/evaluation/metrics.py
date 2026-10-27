"""Métriques des conditions collar_0 et collar_0_25 (docs/protocole-eval.md §3.1, §3.3, §4).

Les chevauchements sont toujours comptés (`skip_overlap=False`). Dans pyannote.metrics,
`collar` est la largeur totale de la zone exclue autour de chaque frontière de référence :
une tolérance de 0,25 s de part et d'autre correspond donc à `collar=0.5`. Ce point est
vérifié par tests/test_protocole_eval.py (test « collar »).

L'agrégation sur plusieurs fichiers somme les durées d'erreur et de référence, puis fait
le rapport (§4) : c'est le comportement cumulatif natif des métriques pyannote.
"""

from __future__ import annotations

from pyannote.core import Annotation, Timeline
from pyannote.metrics.diarization import DiarizationErrorRate, JaccardErrorRate

# Nom de condition -> valeur du paramètre `collar` de pyannote.metrics.
CONDITIONS: dict[str, float] = {"collar_0": 0.0, "collar_0_25": 0.5}

_TOTAL = "total"
_MISSED = "missed detection"
_FALSE_ALARM = "false alarm"
_CONFUSION = "confusion"


def _rates(components: dict[str, float], jer: float) -> dict[str, float]:
    """Convertit des durées (s) en taux (%) rapportés à la parole de référence."""
    total = components[_TOTAL]
    if total == 0.0:
        raise ValueError("Durée de parole de référence nulle : DER indéfini")
    missed = components[_MISSED]
    false_alarm = components[_FALSE_ALARM]
    confusion = components[_CONFUSION]
    return {
        "der": 100.0 * (missed + false_alarm + confusion) / total,
        "manquee": 100.0 * missed / total,
        "fausse_alarme": 100.0 * false_alarm / total,
        "confusion": 100.0 * confusion / total,
        "jer": 100.0 * jer,
    }


def round_rates(rates: dict[str, float], ndigits: int = 2) -> dict[str, float]:
    """Arrondi à deux décimales, pour l'écriture de results.json (methode.md §4.3)."""
    return {key: round(value, ndigits) for key, value in rates.items()}


class DiarizationEvaluator:
    """Accumule les métriques fichier par fichier pour chaque condition de collar."""

    def __init__(self) -> None:
        self._der = {
            name: DiarizationErrorRate(collar=collar, skip_overlap=False)
            for name, collar in CONDITIONS.items()
        }
        self._jer = {
            name: JaccardErrorRate(collar=collar, skip_overlap=False)
            for name, collar in CONDITIONS.items()
        }

    def add(
        self,
        reference: Annotation,
        hypothesis: Annotation,
        uem: Timeline | None = None,
    ) -> dict[str, dict[str, float]]:
        """Évalue un fichier et renvoie, par condition, les taux (%) et les durées (s)."""
        result: dict[str, dict[str, float]] = {}
        for name in CONDITIONS:
            components = self._der[name](reference, hypothesis, uem=uem, detailed=True)
            jer = self._jer[name](reference, hypothesis, uem=uem)
            rates = _rates(components, jer)
            rates.update(
                {
                    "duree_reference_s": components[_TOTAL],
                    "manquee_s": components[_MISSED],
                    "fausse_alarme_s": components[_FALSE_ALARM],
                    "confusion_s": components[_CONFUSION],
                }
            )
            result[name] = rates
        return result

    def report(self) -> dict[str, dict[str, float]]:
        """Taux globaux (%) par condition, en rapport des sommes sur tous les fichiers."""
        return {
            name: _rates(self._der[name][:], abs(self._jer[name]))
            for name in CONDITIONS
        }
