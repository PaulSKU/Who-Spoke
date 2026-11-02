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

Fusion (audit R-U9) : `merge_speakers` verse la parole d'un locuteur dans celle d'un
autre, sur une copie de l'annotation ; l'annotation du moteur (et le cache) n'est jamais
modifiée, et chaque fusion s'annule en la retirant de la liste.

Étiquettes Audacity (audit R-U11) : une ligne par tour, `début<TAB>fin<TAB>code`, le
code `S1`, `S2`… étant attribué dans l'ordre de première prise de parole ; c'est le
format que lit la chaîne du corpus maison (`whospoke.maison.reference.read_labels`,
conventions-annotation.md §3), qui tire le locuteur du texte de chaque étiquette.
"""

from __future__ import annotations

import io
import re
import tempfile
from pathlib import Path

import numpy as np
from pyannote.core import Annotation, Segment, Timeline

from whospoke.evaluation.metrics import CONDITIONS, DiarizationEvaluator

from app import formatage

_DECIMALS = 3


def speaker_labels(annotation: Annotation) -> list[str]:
    """Identifiants des locuteurs, dans l'ordre de leur première prise de parole."""
    first: dict[str, float] = {}
    for segment, _, label in annotation.itertracks(yield_label=True):
        first[label] = min(first.get(label, segment.start), segment.start)
    return sorted(first, key=lambda label: (first[label], label))


def resolve_names(labels: list[str], names: dict[str, str] | None = None) -> dict[str, str]:
    """Nom affiché de chaque identifiant : le nom saisi, ou l'identifiant s'il est vide.

    Lève `ValueError` si deux locuteurs reçoivent le même nom, aux blancs, à « _ » et à
    la casse près : le RTTM exporté les fusionnerait sans le dire (« Alice Martin » et
    « Alice_Martin » y deviennent le même locuteur), et l'œil les confondrait.
    """
    names = names or {}
    resolved = {label: (names.get(label) or "").strip() or label for label in labels}
    seen: dict[str, str] = {}
    for label, name in resolved.items():
        # Noms égaux aux blancs, à « _ » et à la casse près : confondus dans le RTTM, ou à l'œil.
        key = rttm_name(name).casefold()
        if key in seen:
            other = resolved[seen[key]]
            shown = f"« {name} »" if other == name else f"« {other} » et « {name} »"
            raise ValueError(f"Nom en double : {shown} ({seen[key]} et {label})"
                             + ("" if other == name else ", égaux aux espaces, « _ » et majuscules près"))
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


def merge_speakers(annotation: Annotation, fusions: list[tuple[str, str]]) -> Annotation:
    """Copie de `annotation` où chaque fusion `(source, cible)`, dans l'ordre, verse la
    parole de la source dans la cible (qui garde son identifiant). La parole de chaque
    locuteur ayant reçu une fusion est réunie (segments qui se recouvrent ou se touchent
    fusionnés) ; celle des autres locuteurs est gardée telle quelle.

    Lève `ValueError` pour une fusion d'un locuteur avec lui-même ou absent."""
    mapping: dict[str, str] = {}
    present = set(annotation.labels())
    for source, target in fusions:
        current = {mapping.get(label, label) for label in present}
        if source == target or source not in current or target not in current:
            raise ValueError(f"Fusion impossible : {source!r} dans {target!r}")
        mapping = {label: (target if mapped == source else mapped) for label, mapped in mapping.items()}
        mapping[source] = target
    if not mapping:
        return annotation.copy()
    renamed = annotation.rename_labels(mapping)
    targets = set(mapping.values())
    merged = Annotation(uri=annotation.uri)
    for segment, track, label in renamed.itertracks(yield_label=True):
        if label not in targets:
            merged[segment, track] = label
    for label in sorted(targets):
        for index, segment in enumerate(renamed.label_timeline(label, copy=True).support()):
            merged[segment, f"fusion-{label}-{index}"] = label
    return merged


def audacity_codes(annotation: Annotation) -> dict[str, str]:
    """Code `S1`, `S2`… de chaque locuteur, dans l'ordre de première prise de parole."""
    return {label: f"S{index}" for index, label in enumerate(speaker_labels(annotation), start=1)}


def to_audacity(annotation: Annotation) -> str:
    """Étiquettes Audacity : une ligne par tour (plage disjointe de la parole d'un
    locuteur), triées par début, `début<TAB>fin<TAB>code` en secondes à six décimales."""
    codes = audacity_codes(annotation)
    rows = [(segment.start, segment.end, codes[label])
            for label in codes for segment in annotation.label_timeline(label, copy=True).support()]
    return "".join(f"{start:.6f}\t{end:.6f}\t{code}\n" for start, end, code in sorted(rows))


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


RTTM_FORMAT = "SPEAKER fichier canal début durée <NA> <NA> locuteur <NA> <NA>"
_AUDACITY_LINE = re.compile(r"^\s*\d+([.,]\d+)?\t\d+([.,]\d+)?(\t.*)?$")


def read_reference(path: str | Path) -> Annotation:
    """Annotation d'une référence RTTM déposée (un seul fichier, un seul uri).

    Chaque ligne `SPEAKER` est contrôlée (champs, nombres, durée positive) ; tout défaut
    lève `ValueError` avec un message qui dit quoi faire (chantier B7). Les lignes qui ne
    commencent pas par `SPEAKER` (commentaires, autres types RTTM) sont ignorées."""
    path = Path(path)
    name = path.name
    raw = path.read_bytes()
    if not raw.strip():
        raise ValueError(f"{name} est vide. Déposez le fichier RTTM de la référence, une ligne « SPEAKER … » "
                         "par tour de parole.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError(f"{name} n'est pas un fichier texte. Une référence RTTM est un fichier texte, une ligne "
                         f"« {RTTM_FORMAT} » par tour de parole : déposez le fichier .rttm de la référence.") from None
    rows: list[tuple[str, float, float, str]] = []
    lines = text.splitlines()
    for number, line in enumerate(lines, start=1):
        fields = line.split()
        if not fields or fields[0] != "SPEAKER":
            continue
        if len(fields) < 8:
            raise ValueError(f"{name}, ligne {number} : {len(fields)} champs au lieu de 10 (« {RTTM_FORMAT} »). "
                             "Corrigez cette ligne, ou exportez de nouveau la référence au format RTTM.")
        try:
            start, duration = float(fields[3]), float(fields[4])
        except ValueError:
            raise ValueError(f"{name}, ligne {number} : début « {fields[3]} » ou durée « {fields[4]} » illisible. "
                             "Les instants s'écrivent en secondes, avec un point décimal (12.5) : corrigez "
                             "cette ligne.") from None
        if not (np.isfinite(start) and np.isfinite(duration)) or start < 0 or duration < 0:
            raise ValueError(f"{name}, ligne {number} : début {fields[3]} s, durée {fields[4]} s. Le début et la "
                             "durée doivent être positifs (la 5e colonne est une durée, pas un instant de fin) : "
                             "corrigez cette ligne.")
        rows.append((fields[1], start, duration, fields[7]))
    if not rows:
        if any(_AUDACITY_LINE.match(line) for line in lines):
            raise ValueError(f"{name} ressemble à des étiquettes Audacity (début, fin, texte), pas à un RTTM. "
                             "Convertissez-les d'abord en RTTM (chaîne du corpus maison, conventions-annotation.md "
                             "§4), puis déposez le .rttm obtenu.")
        raise ValueError(f"{name} ne contient aucune ligne « SPEAKER … » : ce n'est pas un RTTM. Déposez le "
                         f"fichier .rttm de la référence (« {RTTM_FORMAT} » par ligne).")
    uris = sorted({uri for uri, *_ in rows})
    if len(uris) > 1:
        shown = ", ".join(uris[:4]) + (", …" if len(uris) > 4 else "")
        raise ValueError(f"{name} décrit {len(uris)} enregistrements ({shown}). Gardez seulement les lignes de "
                         "l'enregistrement analysé, ou déposez la référence de cet enregistrement seul.")
    reference = Annotation(uri=uris[0])
    for index, (_, start, duration, label) in enumerate(rows):
        if duration > 0:
            reference[Segment(start, start + duration), index] = label
    return reference


def _clock(seconds: float) -> str:
    seconds = int(round(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _same_recording(a: str, b: str) -> bool:
    """Vrai si deux noms désignent sans doute le même enregistrement (`summre__007a_ECRH`
    et `007a_ECRH`, ou le même nom aux blancs et à la casse près)."""
    a, b = rttm_name(a).casefold(), rttm_name(b).casefold()
    return bool(a and b) and (a == b or a.endswith("__" + b) or b.endswith("__" + a) or a in b or b in a)


LONGER_MIN_S = 1.0          # parole de la référence après la fin de l'audio, avant d'avertir
SHORTER_MIN_S = 10.0        # parole trouvée après la fin de la référence, avant d'avertir
SHORTER_MIN_SHARE = 0.05    # … et part de toute la parole trouvée


def reference_warnings(reference: Annotation, hypothesis: Annotation, audio_uri: str | None,
                       duration_s: float) -> list[str]:
    """Avertissements sur une référence lisible mais peut-être mal assortie à l'audio
    (chantier B7) : autre enregistrement (`audio_uri` connu), référence plus longue ou plus
    courte que l'audio. Ce sont des constats, le DER est calculé quand même."""
    warnings = []
    if audio_uri and not _same_recording(reference.uri or "", audio_uri):
        warnings.append(f"La référence décrit l'enregistrement « {reference.uri} », l'audio déposé s'appelle "
                        f"« {audio_uri} ». Vérifiez qu'il s'agit du même enregistrement : sinon le DER n'a pas de "
                        "sens. Si vous avez seulement renommé le fichier, ignorez ce message.")
    speech = reference.get_timeline().support()
    if not len(speech):
        return warnings
    end = speech.extent().end
    beyond = speech.crop(Segment(duration_s, max(end, duration_s)), mode="intersection").duration() if end > duration_s else 0.0
    if beyond > LONGER_MIN_S:
        warnings.append(f"La référence va jusqu'à {_clock(end)}, l'audio s'arrête à {_clock(duration_s)} : "
                        f"{formatage.unite(beyond, 's', 1)} de parole de la référence, après la fin de l'audio, "
                        "sont ignorées. Vérifiez que l'audio est complet (enregistrement coupé ?) et que c'est la bonne référence.")
    found = hypothesis.get_timeline().support()
    after = found.crop(Segment(end, duration_s), mode="intersection").duration() if end < duration_s else 0.0
    if after >= SHORTER_MIN_S and after >= SHORTER_MIN_SHARE * (found.duration() or 1.0):
        warnings.append(f"La référence s'arrête à {_clock(end)} sur {_clock(duration_s)} d'audio : les "
                        f"{formatage.unite(after, 's')} de parole trouvées après comptent en fausse alarme et gonflent le DER. "
                        f"Si la référence n'annote que le début de l'enregistrement, coupez l'audio à {_clock(end)} "
                        "avant de le déposer.")
    return warnings


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
SHORT_TURN_S = 0.5      # tour de référence court (strictement moins de)
SHORT_PAUSE_S = 1.0     # pause courte entre deux plages de parole de la référence (au plus)
BOUNDARY_S = 0.25       # frontière de tour : ce que pardonne le collar du protocole (collar=0.5, ±0,25 s)
TOUCH_S = 0.05          # une pause « contiguë » à la zone
_EPS = 1e-9

# Catégories des erreurs (décisions du cockpit du 02/11 : ordre de priorité, puis option b).
# Une seule définition, reprise par la carte « Expliquer cette erreur » et par l'analyse
# A-0003. La catégorisation se fait sur le temps : chaque segment d'erreur est découpé aux
# bords des intervalles de ±0,25 s autour des frontières de tour de la référence (ceux que
# retire le collar du protocole). La partie dans ces intervalles est un « décalage de
# frontière » ; le reste de la zone reçoit la première catégorie vraie dans l'ordre qui
# suit, évaluée sur ce reste. Les catégories somment aux composantes du DER sans collar, et
# « décalage de frontière » est exactement l'erreur que retire le collar (même appariement).
ERROR_CATEGORIES = {
    "frontiere": "Décalage de frontière",
    "chevauchement": "Chevauchement",
    "reference_non_appariee": "Locuteur de référence non apparié",
    "trouve_en_trop": "Locuteur trouvé en trop",
    "tour_court": "Tour court",
    "pause": "Pause courte",
    "autre": "Autre",
}


def main_category(zone: dict, context: dict | None, pairs: dict) -> str:
    """Catégorie affichée d'une zone : « frontiere » si elle tient entièrement dans la
    tolérance (`context` None), sinon celle de sa partie hors tolérance, par priorité :

    2. chevauchement : cette partie recoupe un chevauchement de la référence ;
    3. locuteur de référence non apparié (parole manquée ou confusion) ;
    4. locuteur trouvé en trop, non apparié (fausse alarme ou confusion) ;
    5. tour court : elle recoupe un tour de la référence de moins de 0,5 s ;
    6. pause courte : elle recoupe une pause de la référence de 1 s au plus, ou la touche ;
    7. autre.

    `zone` : type et locuteurs (noms d'origine) ; `context` : faits de la référence sur la
    partie hors tolérance (`_Context.describe_parts`) ; `pairs` : appariement du DER.
    Un tour de moins de 0,5 s ou une pause de 0,5 s au plus tiennent dans la tolérance de
    leurs propres frontières : hors tolérance, « tour court » ne s'applique jamais et
    « pause courte » seulement aux pauses de plus de 0,5 s.
    """
    if context is None:
        return "frontiere"
    if context["chevauchement_s"] > 0:
        return "chevauchement"
    if zone["reference"] is not None and zone["reference"] not in pairs:
        return "reference_non_appariee"
    if zone["hypothese"] is not None and zone["hypothese"] not in pairs.values():
        return "trouve_en_trop"
    if context["tour_court"] is not None:
        return "tour_court"
    if context["pause"] is not None:
        return "pause"
    return "autre"


def _covered(intervals: np.ndarray, start: float, end: float) -> list[tuple[float, float]]:
    """Morceaux de [start, end] couverts par `intervals` (n × 2, triés, disjoints)."""
    if not len(intervals) or end <= start:
        return []
    lo = int(np.searchsorted(intervals[:, 1], start, side="right"))
    hi = int(np.searchsorted(intervals[:, 0], end, side="left"))
    pieces = []
    for a, b in intervals[lo:hi]:
        a, b = max(float(a), start), min(float(b), end)
        if b > a:
            pieces.append((a, b))
    return pieces


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
                       if g.duration <= SHORT_PAUSE_S + _EPS and g.start >= first and g.end <= last]
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
            boundary = boundary if boundary <= BOUNDARY_S + _EPS else None
        return {"chevauchement_s": round(overlap, 3),
                "tour_court": None if short is None else {"locuteur": short[0], "duree_s": round(short[1], 3)},
                "pause": None if pause is None else {"duree_s": round(pause[0], 3), "relation": pause[1]},
                "frontiere_s": None if boundary is None else round(boundary, 3)}

    def describe_parts(self, parts: list[tuple[float, float]]) -> dict:
        """Mêmes faits sur plusieurs morceaux (partie d'une zone hors tolérance) : chevauchement
        cumulé ; premier tour court ; pause qu'un morceau recoupe, sinon à laquelle il touche."""
        facts = [self.describe(a, b) for a, b in parts]
        pauses = [f["pause"] for f in facts if f["pause"]]
        return {"chevauchement_s": round(sum(f["chevauchement_s"] for f in facts), 3),
                "tour_court": next((f["tour_court"] for f in facts if f["tour_court"]), None),
                "pause": next((p for p in pauses if p["relation"] == "recoupe"), pauses[0] if pauses else None),
                "duree_s": round(sum(b - a for a, b in parts), 3)}


def error_map(reference: Annotation, hypothesis: Annotation, duration_s: float) -> dict:
    """Carte des erreurs sans collar, chevauchements comptés, après appariement optimal.

    Reprend pas à pas `DiarizationErrorRate.compute_components` de pyannote.metrics
    (restriction à l'UEM, étiquettes renommées, appariement hongrois `optimal_mapping`),
    puis `IdentificationErrorAnalysis.difference` sur l'hypothèse appariée, qui donne le
    statut de chaque segment. Les durées sont cumulées segment par segment comme le fait
    le DER (durée × nombre d'erreurs du segment) : elles redonnent ses composantes.

    Renvoie `{"totaux": {manquee, fausse_alarme, confusion, reference} en s,
    "zones": [{type, debut, fin, reference, hypothese, contexte, categorie}],
    "categories": {type: {catégorie: s}}, "appariement": {référence: trouvé}}` ; zones
    contiguës de même type et de mêmes locuteurs fusionnées pour l'affichage ; noms
    d'origine des locuteurs ; `contexte` : faits de la référence autour de la zone
    (`_Context.describe`) ; `tolerance_s` : part de la zone dans ±0,25 s d'une frontière de
    tour de la référence (pardonnée par le collar) ; `contexte_hors_tolerance` : faits sur
    le reste (None si la zone tient entièrement dans la tolérance) ; `categorie` : catégorie
    affichée (`main_category`). `categories` : secondes par type et par catégorie, cumulées
    segment par segment comme les totaux, la partie dans la tolérance en « frontiere ».
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
    tracks: list[tuple[Segment, dict]] = []   # (segment, zone) de chaque segment d'erreur
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
            zone = previous
        else:
            zones.append(zone)
        tracks.append((segment, zone))
    for segment, by_kind in counts.items():
        for kind, count in by_kind.items():
            totals[kind] += segment.duration * count
    totals["reference"] = metric(match.reference, match.hypothesis, uem=match.uem, detailed=True)["total"]
    context = _Context(match.reference, duration_s)
    pairs = match.pairs()
    # Hors tolérance : l'UEM privée des collars, construite par pyannote.metrics comme pour le
    # DER avec collar (`extrude`, collar = 2 × 0,25 s autour de chaque frontière de tour).
    kept = metric.extrude(match.uem, match.reference, collar=2 * BOUNDARY_S)
    kept = np.array([[s.start, s.end] for s in kept]).reshape(-1, 2)
    for zone in zones:
        zone["contexte"] = context.describe(zone["debut"], zone["fin"])
        outside = _covered(kept, zone["debut"], zone["fin"])
        rest = sum(b - a for a, b in outside)
        zone["tolerance_s"] = round(max(0.0, zone["fin"] - zone["debut"] - rest), 3)
        zone["contexte_hors_tolerance"] = context.describe_parts(outside) if rest > _EPS else None
        zone["categorie"] = main_category(zone, zone["contexte_hors_tolerance"], pairs)
    categories = {kind: dict.fromkeys(ERROR_CATEGORIES, 0.0) for kind in ERROR_TYPES.values()}
    for segment, zone in tracks:
        by_category = categories[zone["type"]]
        if zone["categorie"] == "frontiere":
            by_category["frontiere"] += segment.duration
            continue
        rest = sum(b - a for a, b in _covered(kept, segment.start, segment.end))
        by_category["frontiere"] += segment.duration - rest
        by_category[zone["categorie"]] += rest
    for zone in zones:
        zone["debut"], zone["fin"] = round(zone["debut"], 3), round(zone["fin"], 3)
    return {"totaux": totals, "zones": sorted(zones, key=lambda z: (z["debut"], z["type"])),
            "categories": categories, "appariement": pairs}


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


def write_exports(directory: Path, stem: str, rttm: str, json_text: str,
                  extra: dict[str, str] | None = None) -> tuple[Path, ...]:
    """Écrit les exports dans `directory` et renvoie leurs chemins : RTTM, JSON, puis un
    fichier `<stem><suffixe>` par entrée de `extra` (suffixe → contenu)."""
    directory.mkdir(parents=True, exist_ok=True)
    files = {f"{stem}.rttm": rttm, f"{stem}.json": json_text}
    files.update({f"{stem}{suffix}": text for suffix, text in (extra or {}).items()})
    paths = []
    for name, text in files.items():
        path = directory / name
        path.write_text(text, encoding="utf-8")
        paths.append(path)
    return tuple(paths)


def new_work_dir(root: Path | None = None) -> Path:
    """Dossier de travail d'une analyse (audio normalisé, exports), hors du dépôt."""
    return Path(tempfile.mkdtemp(prefix="analyse-", dir=root))
