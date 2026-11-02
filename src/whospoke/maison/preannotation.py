"""Pré-annotation à partir des pistes d'aide alignées (E2, étape 2).

Principe (protocole §2) : chaque participant a un téléphone à 20–40 cm de lui ; sur sa
piste, sa propre voix domine celles des voisins. Trame par trame :

1. énergie de chaque piste en dB, ramenée à son plancher de bruit (percentile bas de la
   piste sur la zone annotée) : les gains différents des téléphones s'annulent ;
2. lissage de ce rapport signal sur bruit sur une courte durée ;
3. parole si la piste la plus forte dépasse `seuil_activite_db` au-dessus de son
   plancher ; le locuteur est celui de cette piste (un seul locuteur par trame) ;
4. trame « à vérifier » si la deuxième piste est à moins de `marge_db` de la première :
   chevauchement probable ou attribution incertaine ;
5. par locuteur, fusion des pauses de `fusion_s` ou moins (même règle que la
   référence), puis retrait des segments plus courts que `duree_min_s`.

La pré-annotation ne produit aucun chevauchement : ils sont ajoutés à la main, aidés
par la piste « à vérifier ». Les seuils sont choisis a priori et validés sur signaux de
synthèse seulement ; ils peuvent être changés par session (option de
`scripts/data/maison.py`), et la valeur employée est consignée avec les étiquettes.
Aucun système évalué dans le projet n'intervient (conventions §4).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy.ndimage import uniform_filter1d

from whospoke.audio import SAMPLE_RATE
from whospoke.maison.reference import Interval, merge_intervals


@dataclass(frozen=True)
class PreannotationParams:
    """Réglages de la pré-annotation. Durées en secondes, niveaux en dB."""

    trame_s: float = 0.032            # fenêtre d'analyse de l'énergie
    pas_s: float = 0.010              # pas entre deux trames
    percentile_plancher: float = 10.0 # plancher de bruit de chaque piste : 10e percentile de ses trames
    lissage_s: float = 0.10           # moyenne glissante du rapport signal sur bruit
    seuil_activite_db: float = 10.0   # parole si la piste la plus forte dépasse son plancher de 10 dB
    marge_db: float = 3.0             # « à vérifier » si la deuxième piste est à moins de 3 dB
    fusion_s: float = 0.2             # fusion des pauses de 200 ms ou moins (conventions §2)
    duree_min_s: float = 0.10         # segments plus courts retirés (pré-annotation seulement)
    verifier_min_s: float = 0.30      # zones « à vérifier » plus courtes ignorées

    def as_dict(self) -> dict:
        return asdict(self)


def frame_db(signal: np.ndarray, params: PreannotationParams, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Énergie moyenne (dB) des trames centrées sur (k + 0,5) × pas."""
    hop = int(round(params.pas_s * sample_rate))
    half = int(round(params.trame_s * sample_rate)) // 2
    n = len(signal) // hop
    squares = np.concatenate([[0.0], np.cumsum(np.asarray(signal, dtype=np.float64) ** 2)])
    centers = np.arange(n) * hop + hop // 2
    lo = np.clip(centers - half, 0, len(signal))
    hi = np.clip(centers + half, 0, len(signal))
    energy = (squares[hi] - squares[lo]) / np.maximum(hi - lo, 1)
    return 10.0 * np.log10(energy + 1e-12)


@dataclass
class Preannotation:
    """Résultat : segments par piste, zones à vérifier, planchers (dB) par piste."""

    segments: dict[str, list[Interval]]
    a_verifier: list[tuple[float, float, str]]
    planchers_db: dict[str, float]


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Plages [début, fin) des valeurs vraies de `mask`."""
    edges = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)))


def preannotate(tracks: dict[str, np.ndarray], start_s: float, end_s: float,
                params: PreannotationParams = PreannotationParams(),
                sample_rate: int = SAMPLE_RATE) -> Preannotation:
    """Pré-annotation des pistes alignées (`{"S1": signal, …}`, même longueur) entre
    `start_s` et `end_s` (bornes de l'UEM avant exclusions)."""
    if not tracks:
        raise ValueError("Aucune piste d'aide")
    names = sorted(tracks, key=lambda name: (len(name), name))
    hop = params.pas_s
    db = np.stack([frame_db(tracks[name], params, sample_rate) for name in names])
    n = db.shape[1]
    times = (np.arange(n) + 0.5) * hop
    inside = (times >= start_s) & (times < end_s)
    if not inside.any():
        raise ValueError("Zone annotée vide")
    floors = np.percentile(db[:, inside], params.percentile_plancher, axis=1)
    snr = uniform_filter1d(db - floors[:, None], size=max(1, int(round(params.lissage_s / hop))), axis=1)
    order = np.argsort(-snr, axis=0)
    best = order[0]
    top = np.take_along_axis(snr, order[:1], axis=0)[0]
    second = np.take_along_axis(snr, order[1:2], axis=0)[0] if len(names) > 1 else np.full(n, -np.inf)
    active = inside & (top >= params.seuil_activite_db)

    segments: dict[str, list[Interval]] = {}
    for index, name in enumerate(names):
        intervals = [(a * hop, b * hop) for a, b in _runs(active & (best == index))]
        merged = merge_intervals(intervals, params.fusion_s)
        segments[name] = [(a, b) for a, b in merged if b - a >= params.duree_min_s]

    doubtful = active & (top - second < params.marge_db)
    zones = merge_intervals([(a * hop, b * hop) for a, b in _runs(doubtful)], params.fusion_s)
    to_check = []
    for a, b in zones:
        if b - a < params.verifier_min_s:
            continue
        frames = slice(int(round(a / hop)), int(round(b / hop)))
        pairs = [tuple(sorted((names[i], names[j]), key=lambda s: (len(s), s)))
                 for i, j in zip(order[0, frames], order[1, frames])]
        first, other = max(set(pairs), key=pairs.count)
        to_check.append((a, b, f"à vérifier : {first} ou {other}"))
    return Preannotation(segments, to_check, {name: float(floors[i]) for i, name in enumerate(names)})
