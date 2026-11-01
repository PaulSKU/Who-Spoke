"""Indicateurs d'interaction, sans transcription (audit R-U10, chantier B6).

Calculés sur l'annotation du moteur (après fusion éventuelle), donc avec ses erreurs.

- Tour : plage disjointe de la réunion des segments d'un locuteur, comme une
  « intervention » du tableau des locuteurs (`sortie.speaker_stats`) : deux segments
  contigus ou qui se recouvrent forment un seul tour ; aucune pause n'est comblée.
- Plus long monologue : le plus long tour. La parole d'un autre locuteur pendant ce tour
  (acquiescement, chevauchement) ne l'interrompt pas.
- Passage de parole : un locuteur prend la parole quand son tour finit après celui du
  locuteur qui l'avait (Heldner et Edlund, 2010, « floor transfer offset »). Un tour
  entièrement inclus dans celui d'un autre (acquiescement, chevauchement bref) n'est pas
  un passage ; un locuteur qui reprend après sa propre pause non plus.
- Latence de réponse : début du tour qui prend la parole moins fin du tour précédent,
  en secondes ; négative si le nouveau locuteur commence avant que l'autre ait fini.
  Médiane par locuteur qui répond.
- Matrice « qui suit qui » : effectif des passages de parole, du locuteur qui avait la
  parole (ligne) au locuteur qui la prend (colonne) ; diagonale vide par définition.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from pyannote.core import Annotation

from app import sortie


@dataclass(frozen=True)
class Turn:
    speaker: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def turns(annotation: Annotation) -> list[Turn]:
    """Tours de tous les locuteurs, triés par début (puis fin, puis locuteur)."""
    result = [Turn(label, segment.start, segment.end)
              for label in annotation.labels()
              for segment in annotation.label_timeline(label, copy=True).support()]
    return sorted(result, key=lambda t: (t.start, t.end, t.speaker))


def transitions(all_turns: list[Turn]) -> list[tuple[str, str, float]]:
    """Passages de parole : (locuteur qui avait la parole, locuteur qui la prend, latence)."""
    floor: Turn | None = None
    found = []
    for turn in all_turns:
        if floor is None:
            floor = turn
            continue
        if turn.end <= floor.end:
            continue                      # tour inclus dans celui qui a la parole
        if turn.speaker != floor.speaker:
            found.append((floor.speaker, turn.speaker, turn.start - floor.end))
        floor = turn
    return found


def report(annotation: Annotation) -> dict:
    """Indicateurs par locuteur, plus long monologue et matrice « qui suit qui ».

    Locuteurs dans l'ordre de première prise de parole (`sortie.speaker_labels`)."""
    labels = sortie.speaker_labels(annotation)
    all_turns = turns(annotation)
    moves = transitions(all_turns)
    by_speaker = {label: [t for t in all_turns if t.speaker == label] for label in labels}
    speakers = []
    for label in labels:
        own = by_speaker[label]
        latencies = [latency for _, to, latency in moves if to == label]
        longest = max(own, key=lambda t: (t.duration, -t.start)) if own else None
        speakers.append({
            "id": label,
            "n_tours": len(own),
            "duree_moyenne_tour_s": round(sum(t.duration for t in own) / len(own), 3) if own else None,
            "plus_long_tour_s": round(longest.duration, 3) if longest else None,
            "latence_mediane_s": round(median(latencies), 3) if latencies else None,
            "n_reponses": len(latencies),
        })
    longest = max(all_turns, key=lambda t: (t.duration, -t.start), default=None)
    matrix = [[0] * len(labels) for _ in labels]
    index = {label: i for i, label in enumerate(labels)}
    for before, after, _ in moves:
        matrix[index[before]][index[after]] += 1
    return {
        "locuteurs": speakers,
        "plus_long_monologue": (None if longest is None else
                                {"locuteur": longest.speaker, "debut": round(longest.start, 3),
                                 "fin": round(longest.end, 3), "duree_s": round(longest.duration, 3)}),
        "ordre": labels,
        "qui_suit_qui": matrix,
        "n_passages": len(moves),
    }
