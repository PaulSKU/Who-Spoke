"""Application de démonstration « Who Spoke? » (D17), onglet « Analyse ».

Lancement :
    uv run python -m app.app                # moteurs réels
    uv run python -m app.app --factice      # moteur factice, sans aucune inférence

Tout audio déposé est normalisé en WAV 16 kHz mono (D15, D16) dans un dossier de travail
temporaire, hors du dépôt, supprimé à la fermeture (D17, amendement 1). L'interface
fonctionne hors ligne : wavesurfer.js est servi depuis app/static/, le thème n'utilise que
des polices système, la télémétrie de Gradio est désactivée et, hors mode factice, les
modèles sont lus dans le cache local (HF_HUB_OFFLINE=1, voir app/travail.py).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

if __package__ in (None, ""):  # uv run python app/app.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import travail

if __name__ == "__main__":
    # Avant tout import de gradio, huggingface_hub, pyannote ou speechbrain.
    RUN_DIR = travail.configure_environment(os.environ, sys.argv[1:])
else:
    RUN_DIR = travail.run_dir()   # télémétrie déjà coupée par l'import de `app` (D27)

import argparse
import atexit
import json
import signal
import threading
import time
from datetime import datetime
from html import escape

import gradio as gr

from app import avancement, glossaire, moteurs, pipeline, sortie, temps, theme
from whospoke.audio import AudioError, load_waveform, normalize
from whospoke.device import select_device
from whospoke.experiment import REPO_ROOT
from whospoke.pipelines.base import load_catalogue

STATIC_DIR = Path(__file__).resolve().with_name("static")
WAVESURFER_DIR = STATIC_DIR / "wavesurfer-7.12.12"

# Palette catégorielle validée (skill dataviz, ordre fixe), clair et sombre ; au-delà de
# huit locuteurs, un gris neutre : chaque piste porte le nom, la couleur n'est pas seule.
PALETTE_LIGHT = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
PALETTE_DARK = ("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767")
OTHER_LIGHT, OTHER_DARK = "#8a8985", "#a3a29c"

SPEAKER_MODES = ("Automatique", "Imposé", "Fourchette")
DEVICES = ("auto", "cpu", "mps", "cuda")
PRE_STEPS = ("normalisation_audio", "chargement")
PRE_LABELS = {"normalisation_audio": "Normalisation audio (ffmpeg)", "chargement": "Chargement du modèle"}

# Résolution de l'enveloppe de la forme d'onde : 10 valeurs par seconde, pour le zoom.
PEAKS_PER_S = 10

STEP_LABELS = {key: value["libelle"] for key, value in load_catalogue()["etapes"].items()}


def _file_url(path: Path) -> str:
    return f"/gradio_api/file={path}"


def _speaker_colors(labels: list[str]) -> dict[str, tuple[str, str]]:
    return {
        label: (PALETTE_LIGHT[i], PALETTE_DARK[i]) if i < len(PALETTE_LIGHT) else (OTHER_LIGHT, OTHER_DARK)
        for i, label in enumerate(labels)
    }


def _pct(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f}".replace(".", ",") + " %"


def _num(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


class ModelMissing(RuntimeError):
    """Modèle absent du cache local, en fonctionnement hors ligne."""


class EngineCache:
    """Moteurs chargés une seule fois par (moteur, périphérique), comme dans les expériences."""

    def __init__(self, fake: bool, fake_max_s: float, experiments: Path = moteurs.EXPERIMENTS_DIR) -> None:
        self.fake = fake
        self.experiments = experiments
        self.fake_max_s = fake_max_s
        self._engines: dict[tuple[str, str], object] = {}
        self.lock = threading.Lock()

    def get(self, spec: moteurs.EngineSpec, device: str) -> tuple[object, float | None]:
        """(moteur, durée de chargement en s, None s'il était déjà chargé)."""
        key = (spec.key, device)
        if key in self._engines:
            return self._engines[key], None
        start = time.perf_counter()
        try:
            engine = (moteurs.FakeEngine(spec, self.experiments) if self.fake
                      else moteurs.build_engine(spec, device, self.experiments))
        except Exception as error:
            message = moteurs.missing_model_message(error, spec)
            if message is None:
                raise
            raise ModelMissing(message) from error
        self._engines[key] = engine
        return engine, time.perf_counter() - start


def _availability(fake: bool, experiments: Path = moteurs.EXPERIMENTS_DIR) -> dict[str, str | None]:
    """Raison de l'indisponibilité de chaque moteur (None s'il est utilisable)."""
    reasons: dict[str, str | None] = {}
    for key, spec in moteurs.SPECS.items():
        try:
            moteurs.engine_params(spec, experiments)
            if fake and not (moteurs.experiment_dir(spec.source_exp, experiments) / "rttm").is_dir():
                raise moteurs.EngineUnavailable(f"{spec.source_exp} n'a encore produit aucun RTTM")
            reasons[key] = None
        except moteurs.EngineUnavailable as error:
            reasons[key] = str(error)
    return reasons


# --- Affichage de la progression ------------------------------------------------------


def _status_html(steps: list[str], state: dict[str, float], title: str, detail: str = "",
                 fraction: float | None = None, labels: dict[str, str] | None = None,
                 failed: str | None = None, error: str | None = None) -> str:
    """Panneau d'avancement : l'état de chaque étape est écrit, pas seulement dessiné.

    `labels` donne le libellé d'étapes composées (« 2:segmentation » en comparaison).
    `failed` : étape en échec, marquée « échec » ; `error` : message affiché dans le panneau."""
    rows = []
    for step in steps:
        value = state.get(step, 0.0)
        if step == failed:
            cls, text = "fail", "échec"
        elif value >= 1.0:
            cls, text = "done", "terminé"
        elif value > 0.0:
            cls, text = "run", f"{int(100 * value)} %"
        else:
            cls, text = "todo", "en attente"
        label = (labels or {}).get(step) or PRE_LABELS.get(step) or STEP_LABELS.get(step, step)
        rows.append(f'<li class="st-{cls}"><span class="st-mark" aria-hidden="true"></span>'
                    f'<span class="st-label">{escape(label)}</span><span class="st-val">{text}</span></li>')
    bar = ""
    if fraction is not None:
        percent = int(100 * min(1.0, fraction))
        bar = (f'<div class="st-bar" role="progressbar" aria-label="Avancement" aria-valuemin="0" '
               f'aria-valuemax="100" aria-valuenow="{percent}"><div style="width:{percent}%"></div></div>')
    steps_html = f'<ol class="st-steps">{"".join(rows)}</ol>' if rows else ""
    error_html = (f'<p class="st-error" role="alert">{escape(error)}</p>' if error else "")
    root = "st-root st-failed" if failed or error else "st-root"
    return (f'<div class="{root}"><div class="st-head" aria-live="polite">'
            f'<p class="st-title">{escape(title)}</p><span class="st-detail">{escape(detail)}</span></div>'
            f'{error_html}{bar}{steps_html}</div>')


def _estimate_source(run: dict, fake: bool) -> str:
    """Provenance de l'estimation du temps restant : RTF mesuré et surcoût fixe daté."""
    text = f"RTF {_num(run['rtf'], 4)} mesuré par {run['measured'].exp_id}"
    overhead = run.get("overhead")
    if overhead is not None:
        day = datetime.strptime(overhead.measured_on, "%Y-%m-%d").strftime("%d/%m/%Y")
        return f"{text}, surcoût fixe {_num(overhead.seconds, 1)} s mesuré le {day}"
    return text if fake else f"{text}, surcoût fixe non mesuré"


def _step_fraction(steps: list[str], state: dict[str, float]) -> float:
    return sum(min(1.0, state.get(step, 0.0)) for step in steps) / len(steps)


def _failed_step(steps: list[str], state: dict[str, float]) -> str | None:
    """Étape en cause après une erreur : celle en cours (commencée, non terminée), à défaut la
    première non commencée, à défaut la dernière ; None sans étape."""
    for step in steps:
        if 0.0 < state.get(step, 0.0) < 1.0:
            return step
    for step in steps:
        if state.get(step, 0.0) < 1.0:
            return step
    return steps[-1] if steps else None


# --- Résultats ------------------------------------------------------------------------


def _title(text: str, note: str = "") -> str:
    note_html = f'<p class="ws-note">{note}</p>' if note else ""
    return f'<h2 class="ws-section-title">{escape(text)}</h2>{note_html}'


def _empty(text: str) -> str:
    return f'<p class="ws-empty-note">{escape(text)}</p>'


def _stats_html(result: dict | None) -> str:
    if result is None:
        return _empty("Les statistiques par locuteur s'afficheront après l'analyse.")
    stats = sortie.speaker_stats(result["annotation"], result["names"])
    total = sum(row["temps_parole_s"] for row in stats) or 1.0
    colors = _speaker_colors([row["id"] for row in stats])
    rows = []
    for row in stats:
        color = colors[row["id"]][0]
        share = 100 * row["temps_parole_s"] / total
        sub = f'<span class="sub">{escape(row["id"])}</span>' if row["nom"] != row["id"] else ""
        rows.append(
            f'<tr><td><span class="ws-swatch" style="background:{color}" aria-hidden="true"></span>'
            f'<span class="strong">{escape(row["nom"])}</span>{sub}</td>'
            f'<td class="num">{temps.format_duration(row["temps_parole_s"])}</td>'
            f'<td class="num"><span class="ws-share"><span class="ws-share-bar" aria-hidden="true">'
            f'<span style="width:{share:.1f}%;background:{color}"></span></span>{_pct(share)}</span></td>'
            f'<td class="num">{row["n_interventions"]}</td>'
            f'<td class="num">{_pct(100 * row["part_chevauchement"])}</td></tr>'
        )
    return (
        '<div class="ws-table-wrap"><table class="ws-table"><thead><tr><th scope="col">Locuteur</th>'
        '<th scope="col" class="num">Temps de parole</th><th scope="col" class="num">Part</th>'
        '<th scope="col" class="num">Interventions</th><th scope="col" class="num">Chevauchement</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        '<p class="ws-caption">Chevauchement : part du temps de parole du locuteur pendant laquelle '
        'au moins une autre personne parle.</p>'
    )


def _times_all_html(times_html, result: dict) -> str:
    """Temps de traitement ; en comparaison, ceux des deux moteurs l'un sous l'autre."""
    other = result.get("comparaison") if result else None
    if not other:
        return times_html(result)
    return (f'<h3 class="ws-subtitle">{escape(result["libelle"])}</h3>{times_html(result)}'
            f'<h3 class="ws-subtitle">{escape(other["libelle"])}</h3>{times_html(other)}')


def _der_all_html(der_html, result: dict | None, reference_path: str | None) -> str:
    """DER face à la référence ; en comparaison, celui de chacun des deux moteurs."""
    other = result.get("comparaison") if result else None
    if not other or not reference_path:
        return der_html(result, reference_path)
    return (f'<h3 class="ws-subtitle">{escape(result["libelle"])}</h3>{der_html(result, reference_path)}'
            f'<h3 class="ws-subtitle">{escape(other["libelle"])}</h3>{der_html(other, reference_path)}')


# Groupes de la timeline autres que le premier moteur : gris neutre (la même couleur dans
# deux groupes laisserait croire au même locuteur ; la piste nommée porte l'identité).
NEUTRAL_LIGHT, NEUTRAL_DARK = "#7d7f86", "#8f908a"


def _group(group_id: str, title: str, annotation, names: dict, colored: bool, errors: dict | None) -> dict:
    labels = sortie.speaker_labels(annotation)
    resolved = sortie.resolve_names(labels, names)
    colors = (_speaker_colors(labels) if colored
              else {label: (NEUTRAL_LIGHT, NEUTRAL_DARK) for label in labels})
    return {
        "id": group_id, "titre": title,
        "locuteurs": [{"id": label, "nom": resolved[label], "couleur": colors[label][0],
                       "couleur_sombre": colors[label][1]} for label in labels],
        "segments": sortie.segments(annotation),
        "erreurs": errors,
    }


def _viewer_value(result: dict) -> dict:
    """Timeline : premier moteur, second moteur éventuel, référence éventuelle (D26, I5),
    chacun avec sa carte des erreurs ; tous dans le même canevas, donc le même zoom."""
    groups = [_group("a", result.get("libelle", ""), result["annotation"], result["names"], True,
                     result.get("erreurs"))]
    other = result.get("comparaison")
    if other:
        groups.append(_group("b", other["libelle"], other["annotation"], other.get("names", {}), False,
                             other.get("erreurs")))
    if result.get("reference") is not None:
        groups.append(_group("ref", "Référence", result["reference"], {}, False, None))
    return {
        "audio_url": _file_url(result["wav"]),
        "duree_s": result["duree_s"],
        "peaks": result["peaks"],
        "groupes": groups,
    }


ERROR_LABELS = {"manquee": "Parole manquée", "fausse_alarme": "Fausse alarme", "confusion": "Confusion"}


def _errors_for(reference, result: dict) -> dict | None:
    """Carte des erreurs d'un résultat face à une référence déjà lue (D26, I4)."""
    if reference is None:
        return None
    try:
        errors = sortie.error_map(reference, result["annotation"], result["duree_s"])
    except ValueError:
        return None
    totals = errors["totaux"]
    total = totals["reference"] or 1.0
    errors["rangees"] = [
        {"type": kind, "libelle": label, "duree": f"{_num(totals[kind], 2)} s",
         "part": _pct(100 * totals[kind] / total, 2)}
        for kind, label in ERROR_LABELS.items()
    ]
    return errors


def _read_reference(reference_path: str | None):
    if not reference_path:
        return None
    try:
        return sortie.read_reference(reference_path)
    except ValueError:
        return None


def _error_map(result: dict, reference_path: str | None) -> dict | None:
    """Carte des erreurs pour le visualiseur, ou None sans référence utilisable.

    Totaux en secondes et en part de la parole de référence, formatés comme le tableau du
    DER (sans collar) : les deux affichent les mêmes nombres.
    """
    return _errors_for(_read_reference(reference_path), result)


def _with_reference(result: dict, reference_path: str | None) -> dict:
    """Résultat complété de la référence (coupée à l'audio) et des cartes des erreurs."""
    from pyannote.core import Segment

    reference = _read_reference(reference_path)
    result = dict(result)
    result["reference"] = (reference.crop(Segment(0.0, result["duree_s"]), mode="intersection")
                           if reference is not None else None)
    result["erreurs"] = _errors_for(reference, result)
    if result.get("comparaison"):
        result["comparaison"] = dict(result["comparaison"], erreurs=_errors_for(reference, result["comparaison"]))
    return result


def _export_one(result: dict, stem: str) -> list[str]:
    data = sortie.to_json(result["annotation"], result["uri"], result["duree_s"], result["moteur"],
                          result["configuration"], result["calcul_s"], result.get("names", {}))
    rttm = sortie.to_rttm(result["annotation"], result["uri"], result.get("names", {}))
    paths = sortie.write_exports(result["dir"] / "exports", stem, rttm, json.dumps(data, ensure_ascii=False, indent=2))
    return [str(path) for path in paths]


def _exports(result: dict) -> list[str]:
    """RTTM et JSON du résultat ; en comparaison, ceux des deux moteurs, suffixés par moteur."""
    stem = sortie.rttm_name(result["uri"])
    other = result.get("comparaison")
    if not other:
        return _export_one(result, stem)
    return (_export_one(result, f"{stem}_{result['moteur_cle']}")
            + _export_one(other, f"{stem}_{other['moteur_cle']}"))


def _comparison_html(result: dict | None) -> str:
    """Tableau côte à côte des deux moteurs (D26, I5) ; vide hors comparaison."""
    if not result or not result.get("comparaison"):
        return ""
    reference = result.get("reference")
    rows = []
    for item in (result, result["comparaison"]):
        n_speakers = len(sortie.speaker_labels(item["annotation"]))
        der_c0 = der_c025 = "—"
        if reference is not None:
            try:
                report = sortie.der_report(reference, item["annotation"], item["duree_s"])
                der_c0, der_c025 = _pct(report["collar_0"]["der"], 2), _pct(report["collar_0_25"]["der"], 2)
            except ValueError:
                pass
        rtf = item["calcul_s"] / item["duree_s"] if item["duree_s"] else 0.0
        rows.append(f'<tr><td class="strong">{escape(item["libelle"])}</td><td class="num">{n_speakers}</td>'
                    f'<td class="num strong">{der_c0}</td><td class="num">{der_c025}</td>'
                    f'<td class="num">{_num(item["calcul_s"], 2)} s</td><td class="num">{_num(rtf, 4)}</td></tr>')
    if reference is not None:
        rows.append(f'<tr><td>Référence</td><td class="num">{len(reference.labels())}</td>'
                    '<td class="num">—</td><td class="num">—</td><td class="num">—</td><td class="num">—</td></tr>')
    note = ("" if reference is not None
            else '<p class="ws-caption">Déposez une référence RTTM pour comparer les DER.</p>')
    return ('<div class="ws-table-wrap"><table class="ws-table"><thead><tr><th scope="col">Moteur</th>'
            '<th scope="col" class="num">Locuteurs</th><th scope="col" class="num">DER sans collar</th>'
            '<th scope="col" class="num">DER collar 0,25 s</th><th scope="col" class="num">Temps de calcul</th>'
            f'<th scope="col" class="num">RTF</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            f'{note}<p class="ws-caption">DER sur toute la durée du fichier, sans UEM : non comparable aux '
            'résultats sur corpus. Temps de calcul sans le chargement du modèle.</p>')


def _times_html(result: dict | None) -> str:
    if result is None:
        return _empty("Les durées de chaque étape s'afficheront après l'analyse.")
    rows = [("Normalisation audio (ffmpeg)", f"{_num(result['normalisation_s'], 2)} s")]
    rows.append(("Chargement du modèle", "déjà chargé" if result["chargement_s"] is None
                 else f"{_num(result['chargement_s'], 2)} s"))
    rows += [(STEP_LABELS.get(step, step), f"{_num(seconds, 2)} s")
             for step, seconds in result["durees_etapes"].items()]
    body = "".join(f'<tr><td>{escape(label)}</td><td class="num">{value}</td></tr>' for label, value in rows)
    body += f'<tr><td class="strong">Calcul total</td><td class="num strong">{_num(result["calcul_s"], 2)} s</td></tr>'
    rtf = result["calcul_s"] / result["duree_s"] if result["duree_s"] else 0.0
    measured = result["rtf_mesure"]
    caption = (f"Audio de {temps.format_duration(result['duree_s'])} sur <code>{escape(result['device'])}</code> : "
               f"RTF obtenu {_num(rtf, 4)}"
               + (f", RTF mesuré {_num(measured['rtf'], 4)} ({escape(measured['source'])})" if measured else "")
               + ". Le chargement du modèle n'entre pas dans le RTF.")
    callout = ""
    if result["factice"]:
        ignored = result["configuration"]["nombre_locuteurs"]["mode"] != "automatique"
        callout = ('<div class="ws-callout">Moteur factice : aucune inférence. Segments repris de '
                   f'<code>{escape(result["rttm_source"] or "")}</code>, temps de calcul simulé'
                   + (", contrainte sur le nombre de locuteurs ignorée." if ignored else ".") + "</div>")
    return (f'{callout}<div class="ws-table-wrap"><table class="ws-table"><thead><tr><th scope="col">Étape</th>'
            f'<th scope="col" class="num">Durée</th></tr></thead><tbody>{body}</tbody></table></div>'
            f'<p class="ws-caption">{caption}</p>')


def _der_html(result: dict | None, reference_path: str | None) -> str:
    if not reference_path:
        return _empty("Déposez une référence RTTM dans les réglages pour afficher le DER décomposé.")
    if result is None:
        return _empty("Référence chargée : le DER s'affichera après l'analyse.")
    try:
        reference = sortie.read_reference(reference_path)
        report = sortie.der_report(reference, result["annotation"], result["duree_s"])
    except ValueError as error:
        return f'<div class="ws-callout">Référence inutilisable : {escape(str(error))}</div>'
    rows = []
    for name, title in (("collar_0", "Sans collar (principale)"), ("collar_0_25", "Collar ± 0,25 s")):
        r = report[name]
        rows.append(
            f'<tr><td>{title}</td><td class="num strong">{_pct(r["der"], 2)}</td>'
            f'<td class="num">{_pct(r["manquee"], 2)}</td><td class="num">{_pct(r["fausse_alarme"], 2)}</td>'
            f'<td class="num">{_pct(r["confusion"], 2)}</td><td class="num">{_pct(r["jer"], 2)}</td></tr>'
        )
    zone = {key: None if value is None else value["der"] for key, value in report["zones"].items()}
    counts = report["n_locuteurs"]
    return (
        f'<p class="ws-scope">{DER_SCOPE}</p>'
        '<div class="ws-table-wrap"><table class="ws-table"><thead><tr><th scope="col">Condition</th><th scope="col" class="num">DER</th>'
        '<th scope="col" class="num">Parole manquée</th><th scope="col" class="num">Fausse alarme</th>'
        '<th scope="col" class="num">Confusion</th><th scope="col" class="num">JER</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
        f'<p class="ws-caption">DER sans collar par zone : {_pct(zone["sans_chevauchement"], 2)} hors '
        f'chevauchement, {_pct(zone["chevauchement"], 2)} en chevauchement. {counts["hypothese"]} locuteurs '
        f'estimés pour {counts["reference"]} dans la référence. Référence coupée à la durée de l\'audio, '
        'chevauchements comptés, deux conditions de collar (protocole §3.1).</p>'
    )


# Onglet Avancement : un clic sur « notes.md » demande au serveur le contenu des notes.
NOTES_JS = """
element.addEventListener('click', (event) => {
  const button = event.target.closest('.av-notes');
  if (!button) return;
  trigger('click', { notes: button.dataset.id });
  // Les notes s'affichent sous la frise : on les amène à l'écran une fois chargées.
  setTimeout(() => {
    const view = document.querySelector('.av-notes-view');
    if (view) view.scrollIntoView({ block: 'start' });
  }, 500);
});
"""

DER_SCOPE = "Durée entière du fichier, sans UEM : non comparable aux résultats sur corpus."


def _header_html(fake: bool) -> str:
    badge = '<span class="ws-badge">Moteur factice : aucune inférence</span>' if fake else ""
    return ('<header class="ws-header"><div><h1>Who Spoke?</h1>'
            "<p>Qui parle, et quand. L'analyse tourne sur cette machine : l'audio ne la quitte pas.</p>"
            f"</div>{badge}</header>")


VIEWER_TEMPLATE = (
    '<div class="wsp-root wsp-empty">'
    '<p class="wsp-placeholder">Déposez un fichier audio puis lancez l\'analyse : '
    'la forme d\'onde et une piste par locuteur s\'afficheront ici.</p>'
    '<div class="wsp-body"><div class="wsp-toolbar">'
    '<button type="button" class="wsp-play">Lecture</button>'
    '<span class="wsp-time" aria-live="off"></span>'
    '<div class="wsp-zoom" role="group" aria-label="Zoom de la timeline">'
    '<button type="button" class="wsp-zoom-out" aria-label="Dézoomer">−</button>'
    '<input type="range" class="wsp-zoom-range" min="0" max="100" step="1" value="0" '
    'aria-label="Niveau de zoom">'
    '<button type="button" class="wsp-zoom-in" aria-label="Zoomer">+</button>'
    '<button type="button" class="wsp-zoom-fit">Tout afficher</button></div></div>'
    '<div class="wsp-wave"></div>'
    '<div class="wsp-rows"><div class="wsp-labels"></div>'
    '<div class="wsp-viewport"><div class="wsp-canvas"><div class="wsp-lanes"></div>'
    '<div class="wsp-axis" aria-hidden="true"></div><div class="wsp-playhead"></div></div></div></div>'
    '<p class="wsp-errsum" hidden></p>'
    '<p class="wsp-hint">Cliquez sur un segment pour l\'écouter et le repérer sur la forme d\'onde. Zoom : curseur, boutons, ou Ctrl + molette ; '
    'défilement : pavé tactile, Maj + molette ou barre de défilement de la forme d\'onde.</p></div></div>'
)

ENGINE_INFO_DEVICE = "auto : CUDA, puis MPS, puis CPU (D15)."


# --- Application ----------------------------------------------------------------------


# Rendus dont la sortie passe par le glossaire (D26, I3) dans build_app.
LINKED_RENDERERS = ("_title", "_status_html", "_stats_html", "_times_html", "_der_html")


def _linked(linker: glossaire.Linker) -> tuple:
    """Versions des rendus de LINKED_RENDERERS dont les termes renvoient au glossaire."""
    def wrap(render):
        return lambda *args, **kwargs: linker.link(render(*args, **kwargs))
    return tuple(wrap(globals()[name]) for name in LINKED_RENDERERS)


def build_app(fake: bool = False, fake_max_s: float = 20.0, repo_root: Path = REPO_ROOT) -> gr.Blocks:
    """Application ; expériences, résultats, catalogue et documents lus sous `repo_root` (lecture seule)."""
    glossary = glossaire.read_glossary(repo_root / glossaire.GLOSSARY_RELATIVE)
    linker = glossaire.Linker(glossary)
    _title, _status_html, _stats_html, _times_html, _der_html = _linked(linker)

    def _times_all(result):
        return _times_all_html(_times_html, result)

    def _der_all(result, reference_path):
        return _der_all_html(_der_html, result, reference_path)
    experiments = repo_root / "experiments"
    leaderboard = repo_root / "results" / "leaderboard.csv"
    cache = EngineCache(fake, fake_max_s, experiments)
    availability = _availability(fake, experiments)
    choices = [
        (spec.label + ("" if availability[key] is None else " (indisponible)"), key)
        for key, spec in moteurs.SPECS.items()
    ]
    head = "".join(f'<script src="{_file_url(WAVESURFER_DIR / name)}"></script>'
                   for name in ("wavesurfer.min.js", "regions.min.js"))

    def pipeline_page(key: str) -> str:
        try:
            return linker.link(pipeline.render(pipeline.load_page(moteurs.SPECS[key], repo_root)))
        except (OSError, ValueError, KeyError, moteurs.EngineUnavailable) as error:
            return _empty(f"Page indisponible : {error}")

    def progress_sections() -> dict[str, str]:
        return {name: linker.link(html) for name, html in avancement.render(repo_root).items()}

    def engine_info(key: str) -> str:
        spec = moteurs.SPECS[key]
        reason = availability[key]
        return f"Indisponible : {reason}" if reason else f"Configuration reprise de {spec.source_exp}."

    def engine_changed(key: str):
        spec = moteurs.SPECS[key]
        modes = list(SPEAKER_MODES if spec.supports_range else SPEAKER_MODES[:2])
        device = (gr.update(value="cpu", interactive=False, info="CPU seul pour ce moteur (D19, D22).")
                  if spec.cpu_only else gr.update(interactive=True, info=ENGINE_INFO_DEVICE))
        return gr.update(info=engine_info(key)), gr.update(choices=modes, value="Automatique"), device

    def mode_changed(mode: str):
        return gr.update(visible=mode == "Imposé"), gr.update(visible=mode == "Fourchette")

    def speaker_options(spec, mode, k, k_min, k_max):
        """(nombre imposé, configuration consignée) ; erreur explicite si le moteur ne suit pas."""
        if mode == "Imposé":
            if not k or int(k) < 1:
                raise gr.Error("Nombre de locuteurs imposé : saisissez un entier supérieur ou égal à 1.")
            return int(k), {"mode": "impose", "valeur": int(k)}
        if mode == "Fourchette":
            if not spec.supports_range:
                raise gr.Error(f"{spec.label} ne prend pas en charge une fourchette : imposez un nombre.")
            if not k_min or not k_max or int(k_min) < 1 or int(k_min) > int(k_max):
                raise gr.Error("Fourchette : le minimum doit valoir au moins 1 et ne pas dépasser le maximum.")
            return None, {"mode": "fourchette", "min": int(k_min), "max": int(k_max)}
        return None, {"mode": "automatique"}

    def analyse(audio_path, key, compare, key2, mode, k, k_min, k_max, device_choice, reference_path):
        if not audio_path:
            raise gr.Error("Aucun fichier audio : déposez-en un dans les réglages, puis relancez.")
        keys = [key] + ([key2] if compare and key2 else [])
        if len(keys) == 2 and key2 == key:
            raise gr.Error("Choisissez un second moteur différent du premier.")
        runs = []   # un dictionnaire par moteur, dans l'ordre d'exécution
        for index, engine_key in enumerate(keys, start=1):
            spec = moteurs.SPECS[engine_key]
            if availability[engine_key] is not None:
                raise gr.Error(f"{spec.label} est indisponible ({availability[engine_key]}). "
                               "Choisissez un autre moteur.")
            num_speakers, speaker_conf = speaker_options(spec, mode, k, k_min, k_max)
            try:
                device = "cpu" if spec.cpu_only else select_device(device_choice).type
            except (RuntimeError, ValueError) as error:
                raise gr.Error(f"{error}. Choisissez « auto » ou « cpu ».") from error
            runs.append({"index": index, "spec": spec, "device": device, "num_speakers": num_speakers,
                         "speaker_conf": speaker_conf, "elapsed": None, "done": False})

        prefix = len(runs) > 1
        steps, labels = list(PRE_STEPS[:1]), {}
        for run in runs:
            for step in ("chargement", *run["spec"].steps):
                step_id = f"{run['index']}:{step}"
                steps.append(step_id)
                label = PRE_LABELS.get(step) or STEP_LABELS.get(step, step)
                labels[step_id] = f"{run['spec'].label} : {label}" if prefix else label
        state: dict[str, float] = {}

        def status(title, detail="", fraction=None):
            return _status_html(steps, state, title, detail, fraction, labels=labels)

        skip = (gr.skip(),) * 10
        empty = (None, _stats_html(None), gr.update(value=[], visible=False), _times_html(None),
                 _der_html(None, reference_path), gr.update(value=None, visible=False),
                 gr.update(visible=True), "", gr.update(visible=False), None)
        yield (status("Normalisation de l'audio", fraction=0.0), *empty)

        try:
            uri = Path(audio_path).stem
            work = sortie.new_work_dir(RUN_DIR)
            start = time.perf_counter()
            try:
                wav = normalize(audio_path, work / f"{sortie.rttm_name(uri)}.wav")
            except AudioError as error:
                raise gr.Error(f"Ce fichier n'a pas pu être lu comme de l'audio. Détail : {error}") from error
            normalisation_s = time.perf_counter() - start
            state["normalisation_audio"] = 1.0
            waveform, sample_rate = load_waveform(wav)
            duration_s = waveform.shape[1] / sample_rate
            for run in runs:
                run["measured"] = temps.measured_rtf(run["spec"].source_exp, run["device"],
                                                     moteurs.source_device(run["spec"], experiments), leaderboard)
                run["rtf"] = run["measured"].rtf if run["measured"] else None
                run["overhead"] = None if fake else moteurs.fixed_overhead(run["spec"].key, run["device"])

            def remaining_text() -> str:
                remaining = temps.cumulative_remaining_s(
                    [(run["rtf"], run["overhead"].seconds if run["overhead"] else 0.0, run["elapsed"], run["done"])
                     for run in runs], duration_s)
                scope = " pour les deux moteurs" if prefix and not runs[0]["done"] else ""
                if remaining is None:
                    return "temps restant inconnu (RTF non mesuré sur ce périphérique)"
                if remaining > 0:
                    return f"environ {temps.format_duration(remaining)} restantes{scope}"
                return "estimation dépassée, calcul en cours"

            results = []
            with cache.lock:
                for run in runs:
                    spec, index = run["spec"], run["index"]
                    yield (status(f"Chargement de {spec.label}", fraction=_step_fraction(steps, state)), *skip)
                    try:
                        engine, loading_s = cache.get(spec, run["device"])
                    except ModelMissing as error:
                        raise gr.Error(str(error), duration=None) from error
                    except Exception as error:  # chargement des modèles : message affiché tel quel
                        raise gr.Error(f"Le modèle n'a pas pu être chargé. Détail : {error}") from error
                    state[f"{index}:chargement"] = 1.0
                    if fake:
                        engine.simulated_s = min(fake_max_s, max(2.0, (run["rtf"] or 0.05) * duration_s))
                    if spec.supports_range:
                        engine.min_speakers = run["speaker_conf"].get("min")
                        engine.max_speakers = run["speaker_conf"].get("max")
                    outcome: dict = {}

                    def progress(step: str, fraction: float, index=index) -> None:
                        step_id = f"{index}:{step}"
                        state[step_id] = max(state.get(step_id, 0.0), fraction)

                    def work_thread(engine=engine, run=run, progress=progress, outcome=outcome) -> None:
                        try:
                            outcome["result"] = engine.run(waveform, sample_rate, uri=uri,
                                                           num_speakers=run["num_speakers"], progress=progress)
                        except Exception as error:  # remonté à l'interface ci-dessous
                            outcome["error"] = error

                    t0 = time.perf_counter()
                    thread = threading.Thread(target=work_thread, daemon=True)
                    thread.start()
                    while thread.is_alive():
                        run["elapsed"] = time.perf_counter() - t0
                        measured = run["measured"]
                        detail = (f"{temps.format_duration(run['elapsed'])} écoulées, {remaining_text()}"
                                  + (f" ({_estimate_source(run, fake)})" if measured else ""))
                        title = f"Analyse de {Path(audio_path).name} avec {spec.label}"
                        if prefix:
                            title += f" ({index}/{len(runs)})"
                        yield (status(title, detail, _step_fraction(steps, state)), *skip)
                        thread.join(0.3)
                    calcul_s = time.perf_counter() - t0
                    run["elapsed"], run["done"] = calcul_s, True
                    if "error" in outcome:
                        raise gr.Error(f"L'analyse avec {spec.label} a échoué. Détail : {outcome['error']}")
                    resultat = outcome["result"]
                    measured = run["measured"]
                    results.append({
                        "uri": uri, "dir": work, "wav": wav, "duree_s": duration_s, "libelle": spec.label,
                        "moteur_cle": spec.key, "annotation": resultat.annotation, "names": {},
                        "moteur": f"factice ({spec.key})" if fake else spec.key,
                        "configuration": {
                            "experience_source": spec.source_exp, "peripherique": run["device"],
                            "nombre_locuteurs": run["speaker_conf"], "moteur_factice": fake,
                            "reglages": engine.describe_dict(),
                        },
                        "calcul_s": calcul_s, "normalisation_s": normalisation_s, "chargement_s": loading_s,
                        "durees_etapes": resultat.durees_etapes, "device": run["device"], "factice": fake,
                        "rttm_source": resultat.infos.get("rttm_source"),
                        "rtf_mesure": {"rtf": measured.rtf, "source": measured.source()} if measured else None,
                    })

            result = dict(results[0], peaks=sortie.peaks(waveform[0].numpy(),
                                                        n_points=max(4000, int(PEAKS_PER_S * duration_s))))
            if len(results) > 1:
                result["comparaison"] = results[1]
            result = _with_reference(result, reference_path)
            summary = ", ".join(
                f"{item['libelle']} : {len(sortie.speaker_labels(item['annotation']))} locuteur(s) en "
                f"{temps.format_duration(item['calcul_s'])}" for item in results)
            total_s = sum(item["calcul_s"] for item in results)
            done = _status_html(
                steps, {step: 1.0 for step in steps},
                summary if prefix else
                f"{len(sortie.speaker_labels(result['annotation']))} locuteur(s) en {temps.format_duration(total_s)}",
                f"{Path(audio_path).name}, {temps.format_duration(duration_s)} d'audio"
                + ("" if prefix else f", {result['libelle']}, RTF {_num(total_s / duration_s, 4)}"),
                1.0, labels=labels)
            names_rows = [[label, ""] for label in sortie.speaker_labels(result["annotation"])]
            yield (done, _viewer_value(result), _stats_html(result),
                   gr.update(value=names_rows, visible=True, row_limits=(len(names_rows), len(names_rows))),
                   _times_all(result), _der_all(result, reference_path),
                   gr.update(value=_exports(result), visible=True), gr.update(visible=False),
                   _comparison_html(result), gr.update(visible=bool(result.get("comparaison"))), result)
        except Exception as error:
            # Le panneau passe à l'état « échec » sur l'étape en cause, message visible dans la page ;
            # la notification de Gradio est conservée.
            failed = _failed_step(steps, state)
            message = error.message if isinstance(error, gr.Error) else f"{type(error).__name__}: {error}"
            label = labels.get(failed) or PRE_LABELS.get(failed) or STEP_LABELS.get(failed, failed)
            yield (_status_html(steps, state, f"Échec : {label}", fraction=_step_fraction(steps, state),
                                labels=labels, failed=failed, error=str(message)), *skip)
            if isinstance(error, gr.Error):
                raise
            raise gr.Error(f"L'analyse a échoué. Détail : {message}") from error

    def rename(rows, result):
        if result is None:
            return gr.skip(), gr.skip(), gr.skip(), gr.skip()
        names = {str(row[0]): str(row[1] or "") for row in (rows.values.tolist() if hasattr(rows, "values") else rows)}
        try:
            sortie.resolve_names(sortie.speaker_labels(result["annotation"]), names)
        except ValueError as error:
            gr.Warning(f"{error} : choisissez un nom différent pour chaque locuteur.")
            return gr.skip(), gr.skip(), gr.skip(), gr.skip()
        result = dict(result, names=names)
        return _viewer_value(result), _stats_html(result), _exports(result), result

    with gr.Blocks(title="Who Spoke?") as app:
        result_state = gr.State(None)
        gr.HTML(_header_html(fake), js_on_load=None)
        with gr.Tabs():
            with gr.Tab("Analyse"):
                with gr.Row(equal_height=False):
                    with gr.Column(scale=4, min_width=300, elem_classes="ws-card"):
                        gr.HTML(_title("Nouvelle analyse",
                                       "Tout format audio ou vidéo, normalisé en WAV 16 kHz mono."),
                                js_on_load=None)
                        audio = gr.File(label="Fichier audio", file_count="single", type="filepath", height=150)
                        engine = gr.Dropdown(choices, value="pyannote-community-1", label="Moteur",
                                             info=engine_info("pyannote-community-1"))
                        compare = gr.Checkbox(value=False, label="Comparer avec un second moteur",
                                              info="Les deux moteurs tournent l'un après l'autre sur le même fichier.")
                        engine2 = gr.Dropdown(choices, value="baseline-ecapa", label="Second moteur",
                                              visible=False)
                        mode = gr.Radio(list(SPEAKER_MODES), value="Automatique", label="Nombre de locuteurs")
                        k = gr.Number(value=2, precision=0, minimum=1, label="Nombre imposé", visible=False)
                        with gr.Row(visible=False) as range_row:
                            k_min = gr.Number(value=2, precision=0, minimum=1, label="Minimum")
                            k_max = gr.Number(value=6, precision=0, minimum=1, label="Maximum")
                        device = gr.Dropdown(list(DEVICES), value="auto", label="Périphérique",
                                             info=ENGINE_INFO_DEVICE)
                        reference = gr.File(label="Référence RTTM (facultative, pour le DER)",
                                            file_types=[".rttm"], type="filepath", height=96)
                        run = gr.Button("Analyser", variant="primary", size="lg", elem_classes="ws-run")
                    with gr.Column(scale=8, min_width=360):
                        with gr.Column(elem_classes="ws-card"):
                            status = gr.HTML(
                                _status_html([], {}, "Prêt", "Déposez un fichier audio, choisissez un "
                                             "moteur, puis lancez l'analyse."),
                                js_on_load=None)
                        with gr.Column(elem_classes="ws-card"):
                            gr.HTML(_title("Timeline"), js_on_load=None)
                            viewer = gr.HTML(
                                None, html_template=VIEWER_TEMPLATE,
                                css_template=(STATIC_DIR / "visualiseur.css").read_text(),
                                js_on_load=(STATIC_DIR / "visualiseur.js").read_text(), head=head,
                            )
                        with gr.Column(elem_classes="ws-card", visible=False) as comparison_card:
                            gr.HTML(_title("Comparaison", "Les deux moteurs sur le même fichier."),
                                    js_on_load=None)
                            comparison = gr.HTML("", js_on_load=None)
                        with gr.Column(elem_classes="ws-card"):
                            gr.HTML(_title("Locuteurs", "Statistiques et renommage ; en comparaison, du premier moteur."),
                                    js_on_load=None)
                            stats = gr.HTML(_stats_html(None), js_on_load=None)
                            names = gr.Dataframe(
                                headers=["Identifiant", "Nom"], datatype=["str", "str"], interactive=True,
                                static_columns=[0], label="Renommer : saisissez un nom dans la colonne Nom",
                                elem_classes="ws-names", visible=False,
                            )
                        with gr.Column(elem_classes="ws-card"):
                            gr.HTML(_title("Évaluation", "DER face à la référence déposée."), js_on_load=None)
                            der = gr.HTML(_der_html(None, None), js_on_load=None)
                        with gr.Row(equal_height=False):
                            with gr.Column(elem_classes="ws-card"):
                                gr.HTML(_title("Temps de traitement"), js_on_load=None)
                                times = gr.HTML(_times_html(None), js_on_load=None)
                            with gr.Column(elem_classes="ws-card"):
                                gr.HTML(_title("Exports", "RTTM et JSON, avec les noms choisis."),
                                        js_on_load=None)
                                exports = gr.File(show_label=False, file_count="multiple", interactive=False,
                                                  visible=False, elem_classes="ws-exports")
                                exports_empty = gr.HTML(_empty("Disponibles après l'analyse."), js_on_load=None)

            with gr.Tab("Pipeline"):
                with gr.Column(elem_classes="ws-card"):
                    gr.HTML(_title("Pipeline", "Consultation en lecture seule : réglages effectifs de "
                                   "l'expérience source de chaque moteur, expliqués par le catalogue."),
                            js_on_load=None)
                    pipeline_engine = gr.Dropdown(
                        [(spec.label, key) for key, spec in moteurs.SPECS.items()],
                        value="pyannote-community-1", label="Moteur", elem_classes="pl-engine")
                    pipeline_view = gr.HTML(
                        pipeline_page("pyannote-community-1"),
                        js_on_load=(STATIC_DIR / "pipeline.js").read_text(), elem_classes="pl-view")

            with gr.Tab("Avancement") as progress_tab:
                sections = progress_sections()
                with gr.Column(elem_classes="ws-card"):
                    gr.HTML(_title("Avancement", "Généré depuis le dépôt à chaque ouverture de l'onglet : "
                                   "en-têtes des notes.md, results, fiches de décision, planning."),
                            js_on_load=None)
                    progress_summary = gr.HTML(sections["resume"], js_on_load=None)
                with gr.Column(elem_classes="ws-card"):
                    gr.HTML(_title("Expériences et analyses", "Dans l'ordre chronologique. DER sans collar, "
                                   "chevauchements comptés ; en dessous, avec collar de 0,25 s."), js_on_load=None)
                    progress_timeline = gr.HTML(sections["frise"], js_on_load=NOTES_JS)
                with gr.Column(elem_classes="ws-card", visible=False) as notes_card:
                    notes_view = gr.Markdown(elem_classes="av-notes-view")
                with gr.Column(elem_classes="ws-card"):
                    gr.HTML(_title("Décomposition de l'erreur par les oracles",
                                   "Chaque expérience ne change qu'une variable par rapport à sa référence."),
                            js_on_load=None)
                    progress_oracles = gr.HTML(sections["oracles"], js_on_load=None)
                with gr.Column(elem_classes="ws-card"):
                    gr.HTML(_title("Décisions"), js_on_load=None)
                    progress_decisions = gr.HTML(sections["decisions"], js_on_load=None)
                with gr.Column(elem_classes="ws-card"):
                    gr.HTML(_title("File d'attente (D23)"), js_on_load=None)
                    progress_queue = gr.HTML(sections["file"], js_on_load=None)

            with gr.Tab(glossaire.TAB_LABEL):
                with gr.Column(elem_classes="ws-card"):
                    gr.HTML(_title("Glossaire", "Généré depuis docs/glossaire.md. Les termes soulignés en "
                                   "pointillé dans les autres onglets renvoient ici."), js_on_load=None)
                    gr.HTML(glossaire.render(glossary, linker), js_on_load=None)

        engine.change(engine_changed, engine, [engine, mode, device])
        pipeline_engine.change(pipeline_page, pipeline_engine, pipeline_view)

        def refresh_progress():
            sections = progress_sections()
            return (sections["resume"], sections["frise"], sections["oracles"], sections["decisions"],
                    sections["file"])

        def show_notes(evt: gr.EventData):
            item_id = (getattr(evt, "_data", None) or {}).get("notes")
            if not item_id:
                return gr.skip(), gr.skip()
            return avancement.notes_markdown(repo_root, item_id), gr.update(visible=True)

        progress_tab.select(refresh_progress, None, [progress_summary, progress_timeline, progress_oracles,
                                                     progress_decisions, progress_queue])
        progress_timeline.click(show_notes, None, [notes_view, notes_card])
        mode.change(mode_changed, mode, [k, range_row])
        run.click(
            analyse, [audio, engine, compare, engine2, mode, k, k_min, k_max, device, reference],
            [status, viewer, stats, names, times, der, exports, exports_empty, comparison, comparison_card,
             result_state],
            concurrency_limit=1, show_progress="hidden",  # l'avancement est dans le panneau d'état
        )
        names.input(rename, [names, result_state], [viewer, stats, exports, result_state])
        def reference_changed(path, result):
            if result is None:
                return _der_html(None, path), gr.skip(), gr.skip(), gr.skip()
            result = _with_reference(result, path)
            return _der_all(result, path), _viewer_value(result), _comparison_html(result), result

        reference.change(reference_changed, [reference, result_state], [der, viewer, comparison, result_state])
        compare.change(lambda on: gr.update(visible=on), compare, engine2)
    return app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Application de démonstration Who Spoke? (D17).")
    parser.add_argument("--factice", action="store_true",
                        help="moteur factice : étapes simulées et RTTM des expériences, aucune inférence")
    parser.add_argument("--factice-max-s", type=float, default=20.0,
                        help="durée maximale simulée d'une analyse en mode factice (s)")
    parser.add_argument("--port", type=int, default=7860, help="port local (défaut : 7860)")
    parser.add_argument("--depot", type=Path, default=REPO_ROOT,
                        help="racine du dépôt dont sont lus expériences, résultats et catalogue, en lecture "
                             "seule (défaut : ce dépôt ; en développement : ~/Dev/Who-Spoke)")
    args = parser.parse_args(argv)
    for stale in travail.remove_stale():
        print(f"Dossier temporaire d'un lancement interrompu supprimé : {stale}")
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    # Suppression à la fermeture : sortie normale, Ctrl+C ou SIGTERM.
    atexit.register(travail.cleanup, RUN_DIR)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    gr.set_static_paths([STATIC_DIR])
    depot = args.depot.expanduser().resolve()
    if not (depot / "experiments").is_dir():
        parser.error(f"--depot : {depot} ne contient pas de dossier experiments/")
    app = build_app(fake=args.factice, fake_max_s=args.factice_max_s, repo_root=depot)
    app.launch(
        server_name="127.0.0.1", server_port=args.port, share=False,
        allowed_paths=[str(RUN_DIR)], theme=theme.build_theme(), css=theme.css(),
        head=f"<script>{(STATIC_DIR / 'glossaire.js').read_text()}</script>",
        footer_links=["settings"], mcp_server=False, ssr_mode=False,
    )


if __name__ == "__main__":
    main()
