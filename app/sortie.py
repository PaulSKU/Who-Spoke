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
    reference, uem = _evaluation_inputs(reference, hypothesis, duration_s)
    if reference.get_timeline().duration() == 0.0:
        raise ValueError("La référence ne contient aucune parole dans l'audio analysé")
    result = DiarizationEvaluator().add(reference, hypothesis, uem=uem)
    return {name: result[name] for name in CONDITIONS} | {
        "zones": result["zones"],
        "n_locuteurs": result["n_locuteurs"],
    }


# Carte des erreurs (D26, chantier I4) : statuts de pyannote.metrics et noms affichés.
ERROR_TYPES = {"missed detection": "manquee", "false alarm": "fausse_alarme", "confusion": "confusion"}


def _evaluation_inputs(reference: Annotation, hypothesis: Annotation, duration_s: float):
    """Référence coupée à l'audio et UEM, exactement comme `der_report`."""
    uem = Timeline([Segment(0.0, duration_s)])
    reference = reference.crop(uem, mode="intersection")
    reference.uri = hypothesis.uri
    return reference, uem


class _Matching:
    """Entrées de la carte des erreurs et de l'appariement : référence et hypothèse
    restreintes à l'UEM comme le fait le DER, étiquettes renommées, appariement hongrois."""

    def __init__(self, reference: Annotation, hypothesis: Annotation, duration_s: float) -> None:
        from pyannote.metrics.diarization import DiarizationErrorRate

        reference, uem = _evaluation_inputs(reference, hypothesis, duration_s)
        self.metric = DiarizationErrorRate(collar=0.0, skip_overlap=False)
        self.reference, self.hypothesis, self.uem = self.metric.uemify(
            reference, hypothesis, uem=uem, collar=0.0, skip_overlap=False, returns_uem=True)
        self.ref_names: dict = {}
        self.renamed_ref = self.reference.rename_labels(generator="string")
        for (_, _, label), (_, _, new) in zip(self.reference.itertracks(yield_label=True),
                                              self.renamed_ref.itertracks(yield_label=True)):
            self.ref_names[new] = label
        self.hyp_names: dict = {}
        self.renamed_hyp = self.hypothesis.rename_labels(generator="int")
        for (_, _, label), (_, _, new) in zip(self.hypothesis.itertracks(yield_label=True),
                                              self.renamed_hyp.itertracks(yield_label=True)):
            self.hyp_names[new] = label
        # Appariement optimal de pyannote.metrics, celui du DER : étiquette d'hypothèse -> de référence.
        self.mapping = self.metric.optimal_mapping(self.renamed_ref, self.renamed_hyp)

    def pairs(self) -> dict[str, str]:
        """Locuteur de référence -> locuteur trouvé apparié (noms d'origine)."""
        return {self.ref_names[ref]: self.hyp_names[hyp] for hyp, ref in self.mapping.items()}


def pairing(reference: Annotation, hypothesis: Annotation, duration_s: float) -> dict[str, str]:
    """Appariement optimal utilisé par le DER : locuteur de référence -> locuteur trouvé.
    Un locuteur absent du dictionnaire n'est pas apparié."""
    return _Matching(reference, hypothesis, duration_s).pairs()


def matching_report(reference: Annotation, hypothesis: Annotation, duration_s: float) -> list[dict]:
    """Tableau d'appariement (audit R-U4), sans recoder les métriques de pyannote.metrics.

    Une ligne par locuteur de référence (apparié ou non), puis une par locuteur trouvé non
    apparié. `commun_s` : temps où les deux locuteurs appariés parlent ensemble
    (cooccurrence de pyannote.core) ; `couverture` : `DiarizationCoverage` restreinte au
    locuteur de référence (part de sa parole couverte par le locuteur trouvé qui en couvre
    le plus) ; `purete` : `DiarizationPurity` restreinte au locuteur trouvé (part de sa
    parole attribuable au locuteur de référence qui y domine). Fractions entre 0 et 1.
    """
    from pyannote.metrics.diarization import DiarizationCoverage, DiarizationPurity

    match = _Matching(reference, hypothesis, duration_s)
    ref, hyp = match.reference, match.hypothesis
    purity, coverage = DiarizationPurity(), DiarizationCoverage()
    pairs = match.pairs()

    def purity_of(label):
        return float(purity(ref, hyp.subset([label])))

    rows = []
    for label in sorted(ref.labels(), key=str):
        found = pairs.get(label)
        common = float((ref.subset([label]) * hyp.subset([found]))[0, 0]) if found is not None else 0.0
        rows.append({"reference": label, "hypothese": found, "commun_s": common,
                     "duree_reference_s": float(ref.label_duration(label)),
                     "couverture": float(coverage(ref.subset([label]), hyp)),
                     "purete": purity_of(found) if found is not None else None})
    for label in sorted(set(hyp.labels()) - set(pairs.values()), key=str):
        rows.append({"reference": None, "hypothese": label, "commun_s": 0.0, "duree_reference_s": 0.0,
                     "couverture": None, "purete": purity_of(label)})
    return rows


# Contexte d'une zone d'erreur (« Expliquer cette erreur », audit R-U4) : seuils affichés.
SHORT_TURN_S = 0.5      # tour de référence court
SHORT_PAUSE_S = 1.0     # pause courte entre deux plages de parole de la référence
BOUNDARY_S = 0.25       # proximité d'une frontière de tour (la valeur du collar du protocole)
TOUCH_S = 0.05          # une pause « contiguë » à la zone


class _Context:
    """Faits de la référence autour d'une zone : chevauchement, tours courts, pauses
    courtes, frontières de tour. Calculés une fois par carte, en tableaux triés."""

    def __init__(self, reference: Annotation, duration_s: float) -> None:
        overlap = reference.get_overlap()
        self.overlap = np.array([[s.start, s.end] for s in overlap]).reshape(-1, 2)
        turns = [(s.start, s.end, str(label)) for s, _, label in reference.itertracks(yield_label=True)]
        self.short = [(a, b, label) for a, b, label in turns if b - a < SHORT_TURN_S]
        speech = reference.get_timeline().support()
        gaps = speech.gaps(support=Segment(0.0, duration_s))
        # Pauses entre deux plages de parole (ni avant la première ni après la dernière).
        first, last = (speech[0].start, speech[-1].end) if len(speech) else (0.0, 0.0)
        self.pauses = [(g.start, g.end) for g in gaps
                       if g.duration < SHORT_PAUSE_S and g.start >= first and g.end <= last]
        self.boundaries = np.array(sorted({t for a, b, _ in turns for t in (a, b)}))

    def describe(self, start: float, end: float) -> dict:
        overlap = 0.0
        if len(self.overlap):
            overlap = float(np.clip(np.minimum(self.overlap[:, 1], end) - np.maximum(self.overlap[:, 0], start),
                                    0.0, None).sum())
        short = next(((label, b - a) for a, b, label in self.short if min(b, end) - max(a, start) > 0), None)
        pause = None
        for a, b in self.pauses:
            if min(b, end) - max(a, start) > 0:
                pause = (b - a, "recoupe")
                break
            if pause is None and (abs(a - end) <= TOUCH_S or abs(b - start) <= TOUCH_S):
                pause = (b - a, "contigue")
        boundary = None
        if len(self.boundaries):
            boundary = float(min(np.abs(self.boundaries - start).min(), np.abs(self.boundaries - end).min()))
            boundary = boundary if boundary <= BOUNDARY_S else None
        return {"chevauchement_s": round(overlap, 3),
                "tour_court": None if short is None else {"locuteur": short[0], "duree_s": round(short[1], 3)},
                "pause": None if pause is None else {"duree_s": round(pause[0], 3), "relation": pause[1]},
                "frontiere_s": None if boundary is None else round(boundary, 3)}


def error_map(reference: Annotation, hypothesis: Annotation, duration_s: float) -> dict:
    """Carte des erreurs sans collar, chevauchements comptés, après appariement optimal.

    Reprend pas à pas `DiarizationErrorRate.compute_components` de pyannote.metrics
    (restriction à l'UEM, étiquettes renommées, appariement hongrois `optimal_mapping`),
    puis `IdentificationErrorAnalysis.difference` sur l'hypothèse appariée, qui donne le
    statut de chaque segment. Les durées sont cumulées segment par segment comme le fait
    le DER (durée × nombre d'erreurs du segment) : elles redonnent ses composantes.

    Renvoie `{"totaux": {manquee, fausse_alarme, confusion, reference} en s,
    "zones": [{type, debut, fin, reference, hypothese, contexte}],
    "appariement": {référence: trouvé}}` ; zones contiguës de même type et de mêmes
    locuteurs fusionnées pour l'affichage ; noms d'origine des locuteurs ; `contexte` :
    faits de la référence autour de la zone (`_Context.describe`).
    """
    from pyannote.metrics.errors.identification import IdentificationErrorAnalysis

    match = _Matching(reference, hypothesis, duration_s)
    metric, mapping, ref_names, hyp_names = match.metric, match.mapping, match.ref_names, match.hyp_names
    mapped = match.renamed_hyp.rename_labels(mapping=mapping)
    errors = IdentificationErrorAnalysis(collar=0.0, skip_overlap=False).difference(
        match.renamed_ref, mapped, uem=match.uem)

    # Étiquette de l'hypothèse appariée -> nom d'origine (appariée : étiquette de référence).
    inverse = {ref: hyp for hyp, ref in mapping.items()}

    def hyp_name(label):
        if label is None:
            return None
        return hyp_names.get(inverse.get(label, label), str(label))

    totals = {"manquee": 0.0, "fausse_alarme": 0.0, "confusion": 0.0}
    counts: dict[Segment, dict[str, int]] = {}
    zones: list[dict] = []
    for segment, _, (status, ref, hyp) in errors.itertracks(yield_label=True):
        kind = ERROR_TYPES.get(status)
        if kind is None:
            continue
        counts.setdefault(segment, {}).setdefault(kind, 0)
        counts[segment][kind] += 1
        zone = {"type": kind, "debut": segment.start, "fin": segment.end,
                "reference": ref_names.get(ref) if ref is not None else None, "hypothese": hyp_name(hyp)}
        previous = next((z for z in reversed(zones) if z["type"] == kind
                         and z["reference"] == zone["reference"] and z["hypothese"] == zone["hypothese"]), None)
        if previous is not None and abs(previous["fin"] - zone["debut"]) < 1e-9:
            previous["fin"] = zone["fin"]
        else:
            zones.append(zone)
    for segment, by_kind in counts.items():
        for kind, count in by_kind.items():
            totals[kind] += segment.duration * count
    totals["reference"] = metric(match.reference, match.hypothesis, uem=match.uem, detailed=True)["total"]
    context = _Context(match.reference, duration_s)
    for zone in zones:
        zone["contexte"] = context.describe(zone["debut"], zone["fin"])
        zone["debut"], zone["fin"] = round(zone["debut"], 3), round(zone["fin"], 3)
    return {"totaux": totals, "zones": sorted(zones, key=lambda z: (z["debut"], z["type"])),
            "appariement": match.pairs()}


EXCERPT_MAX_S = 10.0


def typical_excerpts(annotation: Annotation, max_s: float = EXCERPT_MAX_S) -> dict[str, tuple[float, float] | None]:
    """Extrait typique de chaque locuteur (audit R-U6) : son plus long tour hors de tout
    chevauchement, limité à ses `max_s` premières secondes ; None si toute sa parole est
    en chevauchement."""
    overlap = annotation.get_overlap()
    excerpts: dict[str, tuple[float, float] | None] = {}
    for label in speaker_labels(annotation):
        clean = annotation.label_timeline(label).support().extrude(overlap)
        longest = max(clean, key=lambda s: (s.duration, -s.start), default=None)
        excerpts[label] = (None if longest is None or longest.duration <= 0
                           else (round(longest.start, 3), round(min(longest.end, longest.start + max_s), 3)))
    return excerpts


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
