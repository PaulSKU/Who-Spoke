"""Étiquettes Audacity, référence RTTM et UEM, contrôles et accord (E2, étapes 3 à 5).

Étiquettes Audacity : une ligne par étiquette, `début<TAB>fin<TAB>texte`, en secondes.
Les lignes de sélection spectrale (qui commencent par `\\`) sont ignorées. Le texte de
chaque étiquette porte le code du locuteur (`S1`, ou `M01_S1`), à la casse et aux espaces
près (`s1`, `S 2`) : la référence ne dépend donc pas de la façon dont Audacity répartit
les pistes dans les fichiers exportés. Une étiquette sans texte prend le code tiré du nom
de son fichier (`M01_S1.txt`, `S1.txt`) ; dans un fichier dont le nom ne donne pas de code
(export unique `M01.txt`), elle arrête la conversion. Le texte `exclusion` marque une zone
retirée de l'UEM (annonce, voix extérieure). Les repères ponctuels `début` et `fin` (à la
casse et aux accents près) bornent l'UEM d'une séance sans claquement. Les zones « à
vérifier » de la pré-annotation sont ignorées, avec un avertissement. Tout autre texte
arrête la conversion ; toutes les étiquettes fautives sont alors listées (fichier, ligne,
instants, texte), pour être corrigées dans Audacity.

Référence (conventions §2 et §4) : par locuteur, union des étiquettes avec fusion des
pauses de 200 ms ou moins (même règle que `scripts/data/get_summre.py`), coupée à l'UEM ;
locuteurs `M01_S1`… ; fichier `maison__M01` (methode.md §3). UEM : du claquement de
début + 1 s au claquement de fin − 1 s, moins les zones d'exclusion ; pour une séance sans
claquement ni piste d'aide (M01), du repère `début` au repère `fin`, moins les exclusions.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

Interval = tuple[float, float]

MERGE_GAP_S = 0.2       # conventions-annotation.md §2
UEM_MARGIN_S = 1.0      # conventions-annotation.md §2 : claquement + 1 s, claquement − 1 s
EXCLUSION_TEXTS = ("exclusion", "exclu", "exclue")
MARKERS = {"debut": "début", "fin": "fin"}   # repères de l'UEM d'une séance sans claquement

_SPEAKER = re.compile(r"^(?:(M\d{2})_)?(S\d+)$")
_SESSION = re.compile(r"^M\d{2}$")


class LabelError(ValueError):
    """Étiquette illisible ou de texte inconnu : à corriger dans Audacity."""


def merge_intervals(intervals: list[Interval], gap: float = MERGE_GAP_S) -> list[Interval]:
    """Union d'intervalles, en fusionnant ceux séparés de `gap` secondes ou moins."""
    merged: list[list[float]] = []
    for start, end in sorted(intervals):
        if merged and start - merged[-1][1] <= gap + 1e-9:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def subtract(base: list[Interval], removed: list[Interval]) -> list[Interval]:
    """`base` privé de l'union de `removed`."""
    result = []
    cuts = merge_intervals(removed, 0.0)
    for start, end in base:
        current = start
        for a, b in cuts:
            if b <= current or a >= end:
                continue
            if a > current:
                result.append((current, a))
            current = max(current, b)
        if current < end:
            result.append((current, end))
    return result


def intersect(intervals: list[Interval], window: list[Interval]) -> list[Interval]:
    """Intersection de deux unions d'intervalles (chacune supposée sans recouvrement)."""
    result = []
    for start, end in intervals:
        for a, b in window:
            lo, hi = max(start, a), min(end, b)
            if hi > lo:
                result.append((lo, hi))
    return result


# --- Étiquettes Audacity -------------------------------------------------------------


def write_labels(path: Path, labels: list[tuple[float, float, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{a:.6f}\t{b:.6f}\t{text}\n" for a, b, text in sorted(labels)))


def read_labels(path: Path) -> list[tuple[float, float, str]]:
    """Étiquettes d'un fichier exporté par Audacity (virgule décimale acceptée)."""
    return [(start, end, text) for _, start, end, text in numbered_labels(path)]


def numbered_labels(path: Path) -> list[tuple[int, float, float, str]]:
    """Comme `read_labels`, avec le numéro de ligne de chaque étiquette dans le fichier."""
    labels = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("\\"):
            continue
        fields = line.split("\t")
        if len(fields) < 2:
            raise LabelError(f"{path.name}, ligne {number} : « début<TAB>fin<TAB>texte » attendu")
        try:
            start, end = (float(value.strip().replace(",", ".")) for value in fields[:2])
        except ValueError as error:
            raise LabelError(f"{path.name}, ligne {number} : instants illisibles") from error
        if end < start:
            raise LabelError(f"{path.name}, ligne {number} : fin ({end}) avant le début ({start})")
        labels.append((number, start, end, fields[2].strip() if len(fields) > 2 else ""))
    return labels


def plain(text: str) -> str:
    """Texte comparé sans casse, sans accents et sans espaces (`Début` -> `debut`)."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c) and not c.isspace()).casefold()


def speaker_code(text: str, session: str) -> str | None:
    """`S1` ou `M01_S1` -> `M01_S1`, à la casse et aux espaces près (`s1`, `S 2`) ; None si
    le texte n'est pas un code de locuteur.

    Lève `LabelError` pour le code d'une autre session.
    """
    match = _SPEAKER.match(re.sub(r"\s+", "", text).upper())
    if not match:
        return None
    if match.group(1) and match.group(1) != session:
        raise LabelError(f"code {text!r} d'une autre session que {session}")
    return f"{session}_{match.group(2)}"


@dataclass
class Annotation:
    """Étiquettes relues : intervalles bruts par locuteur, exclusions, repères (`debut`,
    `fin` : instants et emplacements), avertissements."""

    speakers: dict[str, list[Interval]] = field(default_factory=dict)
    exclusions: list[Interval] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    markers: dict[str, list[tuple[float, str]]] = field(default_factory=dict)


def read_annotation(directory: Path, session: str) -> Annotation:
    """Toutes les étiquettes `*.txt` de `directory`, réparties par locuteur.

    Lève `LabelError` avec la liste de toutes les étiquettes fautives (texte inconnu, code
    d'une autre session, étiquette sans texte dans un fichier sans code), après lecture de
    tous les fichiers : aucune n'est écartée en silence."""
    if not _SESSION.match(session):
        raise ValueError(f"Session {session!r} : M01, M02… attendu")
    files = sorted(directory.glob("*.txt"))
    if not files:
        raise LabelError(f"Aucun fichier d'étiquettes (*.txt) dans {directory}")
    result = Annotation()
    faults = []
    for path in files:
        default = speaker_code(path.stem.removeprefix(f"{session}_"), session)
        for number, start, end, text in numbered_labels(path):
            where = f"{path.name} ({start:.2f}–{end:.2f} s)"
            key = plain(text)
            if key in EXCLUSION_TEXTS:
                result.exclusions.append((start, end))
                continue
            if key in MARKERS:
                instant = start if key == "debut" else end
                if end > start:
                    result.warnings.append(f"{where} : repère « {MARKERS[key]} » non ponctuel, instant "
                                           f"retenu {instant:.3f} s ({'début' if key == 'debut' else 'fin'} du label)")
                result.markers.setdefault(key, []).append((instant, f"{path.name}, ligne {number}"))
                continue
            if key.startswith("averifier"):
                result.warnings.append(f"{where} : zone « à vérifier » ignorée")
                continue
            fault = f"{path.name}, ligne {number}, {start:.3f}–{end:.3f} s : texte {text!r}"
            try:
                code = speaker_code(text, session) if text else default
            except LabelError as error:
                faults.append(f"{fault} ({error})")
                continue
            if code is None:
                faults.append(fault + (" ; étiquette sans texte, et le nom du fichier ne donne pas de code"
                                       if not text else " inconnu ; attendu un code (S1, S2…), « exclusion », "
                                                        "« début » ou « fin »"))
                continue
            if end - start <= 0.0:
                result.warnings.append(f"{where} : étiquette ponctuelle (durée nulle) ignorée")
                continue
            result.speakers.setdefault(code, []).append((start, end))
    if faults:
        raise LabelError(f"{len(faults)} étiquette(s) à corriger dans Audacity :\n"
                         + "\n".join(f"  - {fault}" for fault in faults))
    return result


# --- Référence et UEM ------------------------------------------------------------------


def uem_intervals(clap_start_s: float, clap_end_s: float, exclusions: list[Interval] = (),
                  margin_s: float = UEM_MARGIN_S) -> list[Interval]:
    """Du claquement de début + 1 s au claquement de fin − 1 s, moins les exclusions."""
    start, end = clap_start_s + margin_s, clap_end_s - margin_s
    if end <= start:
        raise ValueError("UEM vide : claquements trop proches")
    return subtract([(start, end)], list(exclusions))


def marker_bounds(annotation: Annotation) -> tuple[float, float]:
    """(début, fin) d'une séance sans claquement, lus dans ses repères ; `LabelError` s'il
    manque un repère, s'il y en a plusieurs du même nom ou si la fin précède le début."""
    problems = []
    for key, name in MARKERS.items():
        found = annotation.markers.get(key, [])
        if len(found) != 1:
            places = ", ".join(where for _, where in found)
            problems.append(f"{len(found)} repère(s) « {name} » au lieu d'un" + (f" ({places})" if places else ""))
    if not problems:
        start, end = annotation.markers["debut"][0][0], annotation.markers["fin"][0][0]
        if end <= start:
            problems.append(f"repère « fin » ({end:.3f} s) avant le repère « début » ({start:.3f} s)")
        else:
            return start, end
    raise LabelError("Séance sans claquement : UEM par repères impossible : " + " ; ".join(problems)
                     + ". Posez un label ponctuel « début » et un « fin » dans Audacity, puis exportez.")


@dataclass
class Reference:
    speakers: dict[str, list[Interval]]
    uem: list[Interval]
    cropped: list[str]      # parties d'étiquettes retirées car hors de l'UEM


def build_reference(annotation: Annotation, uem: list[Interval], gap: float = MERGE_GAP_S) -> Reference:
    """Fusion des pauses de `gap` ou moins par locuteur, puis coupe à l'UEM."""
    speakers, cropped = {}, []
    for code in sorted(annotation.speakers, key=lambda c: (len(c), c)):
        merged = merge_intervals(annotation.speakers[code], gap)
        kept = intersect(merged, uem)
        outside = sum(b - a for a, b in merged) - sum(b - a for a, b in kept)
        if outside > 1e-6:
            cropped.append(f"{code} : {outside:.2f} s hors de l'UEM retirées")
        speakers[code] = kept
    return Reference(speakers, uem, cropped)


def rttm_text(uri: str, speakers: dict[str, list[Interval]]) -> str:
    """Même écriture que les références de SUMM-RE (scripts/data/get_summre.py)."""
    rows = sorted((start, end, code) for code, intervals in speakers.items() for start, end in intervals)
    return "".join(f"SPEAKER {uri} 1 {start:.3f} {end - start:.3f} <NA> <NA> {code} <NA> <NA>\n"
                   for start, end, code in rows)


def uem_text(uri: str, uem: list[Interval]) -> str:
    return "".join(f"{uri} 1 {start:.3f} {end:.3f}\n" for start, end in uem)


def speech_stats(speakers: dict[str, list[Interval]], uem: list[Interval]) -> dict:
    """Parole (≥ 1 locuteur), chevauchement (≥ 2) et temps par locuteur, dans l'UEM (s)."""
    events = []
    per_speaker = {}
    for code, intervals in speakers.items():
        clipped = intersect(merge_intervals(intervals, 0.0), uem)
        per_speaker[code] = sum(b - a for a, b in clipped)
        for a, b in clipped:
            events += [(a, 1), (b, -1)]
    speech = overlap = 0.0
    active, previous = 0, None
    for time, delta in sorted(events):
        if previous is not None:
            if active >= 1:
                speech += time - previous
            if active >= 2:
                overlap += time - previous
        active += delta
        previous = time
    return {"uem_s": sum(b - a for a, b in uem), "parole_s": speech, "chevauchement_s": overlap,
            "par_locuteur_s": per_speaker}


# --- Contrôles automatiques (conventions §4, étape 5) ------------------------------------


@dataclass(frozen=True)
class CheckParams:
    """Seuils des avertissements de plausibilité (ils n'empêchent pas la conversion)."""

    part_parole_min: float = 0.40          # parole sur moins de 40 % de l'UEM : annotation incomplète ?
    part_parole_max: float = 0.98          # plus de 98 % : pauses oubliées ?
    taux_chevauchement_max: float = 0.25   # plus de 25 % de la parole en chevauchement : voix des voisins non retirée ?
    part_locuteur_min: float = 0.02        # un locuteur sous 2 % du temps de parole
    segment_max_s: float = 30.0            # segment plus long : pauses non découpées ?


def check_reference(reference: Reference, expected: list[str], params: CheckParams = CheckParams()) -> dict:
    """Contrôles bloquants (référence inutilisable en l'état) et avertissements, avec statistiques."""
    blocking, warnings = [], []
    for code, intervals in reference.speakers.items():
        for start, end in intervals:
            if end <= start:
                blocking.append(f"{code} : segment de durée nulle à {start:.3f} s")
            if not any(a - 1e-6 <= start and end <= b + 1e-6 for a, b in reference.uem):
                blocking.append(f"{code} : segment {start:.3f}–{end:.3f} s hors de l'UEM")
            if end - start > params.segment_max_s:
                warnings.append(f"{code} : segment de {end - start:.1f} s à {start:.1f} s "
                                f"(> {params.segment_max_s:.0f} s), pauses à découper ?")
    for code in expected:
        if not reference.speakers.get(code):
            blocking.append(f"{code} : aucun segment")
    unexpected = sorted(set(reference.speakers) - set(expected)) if expected else []
    for code in unexpected:
        warnings.append(f"{code} : locuteur absent des pistes d'aide (voix supplémentaire ?)")

    stats = speech_stats(reference.speakers, reference.uem)
    speech, uem = stats["parole_s"], stats["uem_s"]
    if uem > 0 and not params.part_parole_min <= speech / uem <= params.part_parole_max:
        warnings.append(f"parole sur {100 * speech / uem:.0f} % de l'UEM (plage plausible "
                        f"{100 * params.part_parole_min:.0f}–{100 * params.part_parole_max:.0f} %)")
    if speech > 0 and stats["chevauchement_s"] / speech > params.taux_chevauchement_max:
        warnings.append(f"chevauchement sur {100 * stats['chevauchement_s'] / speech:.0f} % de la parole "
                        f"(> {100 * params.taux_chevauchement_max:.0f} %) : voix des voisins non retirée ?")
    total = sum(stats["par_locuteur_s"].values())
    for code, seconds in stats["par_locuteur_s"].items():
        if total > 0 and 0 < seconds / total < params.part_locuteur_min:
            warnings.append(f"{code} : {100 * seconds / total:.1f} % du temps de parole")
    speakers = {
        code: {
            "temps_s": round(stats["par_locuteur_s"][code], 3),
            "part": round(stats["par_locuteur_s"][code] / total, 4) if total else 0.0,
            "n_segments": len(intervals),
            "duree_mediane_s": round(float(sorted(b - a for a, b in intervals)[len(intervals) // 2]), 3)
            if intervals else None,
        }
        for code, intervals in reference.speakers.items()
    }
    return {
        "bloquants": blocking,
        "avertissements": warnings,
        "statistiques": {
            "uem_s": round(uem, 3), "parole_s": round(speech, 3),
            "part_parole": round(speech / uem, 4) if uem else None,
            "chevauchement_s": round(stats["chevauchement_s"], 3),
            "taux_chevauchement": round(stats["chevauchement_s"] / speech, 4) if speech else None,
            "n_locuteurs": sum(1 for intervals in reference.speakers.values() if intervals),
            "locuteurs": speakers,
        },
        "seuils": asdict(params),
    }


# --- Accord entre deux annotations (conventions §5) --------------------------------------


def agreement(first: dict[str, list[Interval]], second: dict[str, list[Interval]], window: list[Interval],
              uri: str = "accord") -> dict:
    """DER de la seconde annotation face à la première, sur `window`, sans collar,
    chevauchements comptés (condition `collar_0` du protocole) ; appariement optimal des
    locuteurs, comme pour les systèmes."""
    from pyannote.core import Annotation as PyAnnotation
    from pyannote.core import Segment, Timeline

    from whospoke.evaluation.metrics import DiarizationEvaluator

    def to_pyannote(speakers):
        annotation = PyAnnotation(uri=uri)
        for code, intervals in speakers.items():
            for index, (start, end) in enumerate(intervals):
                annotation[Segment(start, end), f"{code}_{index}"] = code
        return annotation

    uem = Timeline([Segment(a, b) for a, b in window], uri=uri)
    result = DiarizationEvaluator().add(to_pyannote(first), to_pyannote(second), uem=uem)
    return {"collar_0": result["collar_0"], "collar_0_25": result["collar_0_25"],
            "n_locuteurs": result["n_locuteurs"]}
