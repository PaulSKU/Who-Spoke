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
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    RUN_DIR = travail.run_dir()

import argparse
import atexit
import json
import signal
import threading
import time
from html import escape

import gradio as gr

from app import moteurs, sortie, temps, theme
from whospoke.audio import AudioError, load_waveform, normalize
from whospoke.device import select_device
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

    def __init__(self, fake: bool, fake_max_s: float) -> None:
        self.fake = fake
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
            engine = moteurs.FakeEngine(spec) if self.fake else moteurs.build_engine(spec, device)
        except Exception as error:
            message = moteurs.missing_model_message(error, spec)
            if message is None:
                raise
            raise ModelMissing(message) from error
        self._engines[key] = engine
        return engine, time.perf_counter() - start


def _availability(fake: bool) -> dict[str, str | None]:
    """Raison de l'indisponibilité de chaque moteur (None s'il est utilisable)."""
    reasons: dict[str, str | None] = {}
    for key, spec in moteurs.SPECS.items():
        try:
            moteurs.engine_params(spec)
            if fake and not (moteurs.experiment_dir(spec.source_exp) / "rttm").is_dir():
                raise moteurs.EngineUnavailable(f"{spec.source_exp} n'a encore produit aucun RTTM")
            reasons[key] = None
        except moteurs.EngineUnavailable as error:
            reasons[key] = str(error)
    return reasons


# --- Affichage de la progression ------------------------------------------------------


def _status_html(steps: list[str], state: dict[str, float], title: str, detail: str = "",
                 fraction: float | None = None) -> str:
    """Panneau d'avancement : l'état de chaque étape est écrit, pas seulement dessiné."""
    rows = []
    for step in steps:
        value = state.get(step, 0.0)
        if value >= 1.0:
            cls, text = "done", "terminé"
        elif value > 0.0:
            cls, text = "run", f"{int(100 * value)} %"
        else:
            cls, text = "todo", "en attente"
        label = PRE_LABELS.get(step) or STEP_LABELS.get(step, step)
        rows.append(f'<li class="st-{cls}"><span class="st-mark" aria-hidden="true"></span>'
                    f'<span class="st-label">{escape(label)}</span><span class="st-val">{text}</span></li>')
    bar = ""
    if fraction is not None:
        percent = int(100 * min(1.0, fraction))
        bar = (f'<div class="st-bar" role="progressbar" aria-label="Avancement" aria-valuemin="0" '
               f'aria-valuemax="100" aria-valuenow="{percent}"><div style="width:{percent}%"></div></div>')
    steps_html = f'<ol class="st-steps">{"".join(rows)}</ol>' if rows else ""
    return (f'<div class="st-root"><div class="st-head" aria-live="polite">'
            f'<p class="st-title">{escape(title)}</p><span class="st-detail">{escape(detail)}</span></div>'
            f'{bar}{steps_html}</div>')


def _step_fraction(steps: list[str], state: dict[str, float]) -> float:
    return sum(min(1.0, state.get(step, 0.0)) for step in steps) / len(steps)


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


def _viewer_value(result: dict) -> dict:
    labels = sortie.speaker_labels(result["annotation"])
    names = sortie.resolve_names(labels, result["names"])
    colors = _speaker_colors(labels)
    return {
        "audio_url": _file_url(result["wav"]),
        "duree_s": result["duree_s"],
        "peaks": result["peaks"],
        "locuteurs": [{"id": label, "nom": names[label], "couleur": colors[label][0],
                       "couleur_sombre": colors[label][1]} for label in labels],
        "segments": sortie.segments(result["annotation"]),
    }


def _exports(result: dict) -> list[str]:
    data = sortie.to_json(result["annotation"], result["uri"], result["duree_s"], result["moteur"],
                          result["configuration"], result["calcul_s"], result["names"])
    rttm = sortie.to_rttm(result["annotation"], result["uri"], result["names"])
    paths = sortie.write_exports(result["dir"] / "exports", sortie.rttm_name(result["uri"]), rttm,
                                 json.dumps(data, ensure_ascii=False, indent=2))
    return [str(path) for path in paths]


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
    '<p class="wsp-hint">Cliquez sur un segment pour l\'écouter. Zoom : curseur, boutons, ou Ctrl + molette ; '
    'défilement : pavé tactile, Maj + molette ou barre de défilement de la forme d\'onde.</p></div></div>'
)

ENGINE_INFO_DEVICE = "auto : CUDA, puis MPS, puis CPU (D15)."


# --- Application ----------------------------------------------------------------------


def build_app(fake: bool = False, fake_max_s: float = 20.0) -> gr.Blocks:
    cache = EngineCache(fake, fake_max_s)
    availability = _availability(fake)
    choices = [
        (spec.label + ("" if availability[key] is None else " (indisponible)"), key)
        for key, spec in moteurs.SPECS.items()
    ]
    head = "".join(f'<script src="{_file_url(WAVESURFER_DIR / name)}"></script>'
                   for name in ("wavesurfer.min.js", "regions.min.js"))

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

    def analyse(audio_path, key, mode, k, k_min, k_max, device_choice, reference_path):
        spec = moteurs.SPECS[key]
        if not audio_path:
            raise gr.Error("Aucun fichier audio : déposez-en un dans les réglages, puis relancez.")
        if availability[key] is not None:
            raise gr.Error(f"{spec.label} est indisponible ({availability[key]}). Choisissez un autre moteur.")
        num_speakers = None
        speaker_conf: dict = {"mode": "automatique"}
        if mode == "Imposé":
            if not k or int(k) < 1:
                raise gr.Error("Nombre de locuteurs imposé : saisissez un entier supérieur ou égal à 1.")
            num_speakers = int(k)
            speaker_conf = {"mode": "impose", "valeur": num_speakers}
        elif mode == "Fourchette":
            if not spec.supports_range:
                raise gr.Error(f"{spec.label} ne prend pas en charge une fourchette : imposez un nombre.")
            if not k_min or not k_max or int(k_min) < 1 or int(k_min) > int(k_max):
                raise gr.Error("Fourchette : le minimum doit valoir au moins 1 et ne pas dépasser le maximum.")
            speaker_conf = {"mode": "fourchette", "min": int(k_min), "max": int(k_max)}
        try:
            device = "cpu" if spec.cpu_only else select_device(device_choice).type
        except (RuntimeError, ValueError) as error:
            raise gr.Error(f"{error}. Choisissez « auto » ou « cpu ».") from error

        steps = list(PRE_STEPS) + list(spec.steps)
        state: dict[str, float] = {}
        skip = (gr.skip(),) * 8
        empty = (None, _stats_html(None), gr.update(value=[], visible=False), _times_html(None),
                 _der_html(None, reference_path), gr.update(value=None, visible=False),
                 gr.update(visible=True), None)
        yield (_status_html(steps, state, "Normalisation de l'audio", fraction=0.0), *empty)

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

        measured = temps.measured_rtf(spec.source_exp, device, moteurs.source_device(spec))
        rtf = measured.rtf if measured else None
        estimate = temps.format_duration(rtf * duration_s) if rtf else None

        with cache.lock:
            yield (_status_html(steps, state, f"Chargement de {spec.label}",
                                fraction=_step_fraction(steps, state)), *skip)
            try:
                engine, loading_s = cache.get(spec, device)
            except ModelMissing as error:
                raise gr.Error(str(error), duration=None) from error
            except Exception as error:  # chargement des modèles : message affiché tel quel
                raise gr.Error(f"Le modèle n'a pas pu être chargé. Détail : {error}") from error
            state["chargement"] = 1.0
            if fake:
                engine.simulated_s = min(fake_max_s, max(2.0, (rtf or 0.05) * duration_s))
            if spec.supports_range:
                engine.min_speakers = speaker_conf.get("min")
                engine.max_speakers = speaker_conf.get("max")

            outcome: dict = {}

            def progress(step: str, fraction: float) -> None:
                state[step] = max(state.get(step, 0.0), fraction)

            def work_thread() -> None:
                try:
                    outcome["result"] = engine.run(waveform, sample_rate, uri=uri,
                                                   num_speakers=num_speakers, progress=progress)
                except Exception as error:  # remonté à l'interface ci-dessous
                    outcome["error"] = error

            t0 = time.perf_counter()
            thread = threading.Thread(target=work_thread, daemon=True)
            thread.start()
            while thread.is_alive():
                elapsed = time.perf_counter() - t0
                remaining = temps.remaining_s(rtf, duration_s, elapsed)
                if remaining is None:
                    left = "temps restant inconnu (RTF non mesuré sur ce périphérique)"
                elif remaining > 0:
                    left = f"environ {temps.format_duration(remaining)} restantes"
                else:
                    left = "estimation dépassée, calcul en cours"
                detail = (f"{temps.format_duration(elapsed)} écoulées, {left}"
                          + (f" (estimation {estimate}, RTF {_num(rtf, 4)} mesuré par {measured.exp_id})"
                             if measured else ""))
                yield (_status_html(steps, state, f"Analyse de {Path(audio_path).name} avec {spec.label}",
                                    detail, _step_fraction(steps, state)), *skip)
                thread.join(0.3)
            calcul_s = time.perf_counter() - t0
            describe = engine.describe_dict()
        if "error" in outcome:
            raise gr.Error(f"L'analyse a échoué. Détail : {outcome['error']}")
        resultat = outcome["result"]

        result = {
            "uri": uri, "dir": work, "wav": wav, "duree_s": duration_s,
            "peaks": sortie.peaks(waveform[0].numpy(), n_points=max(4000, int(PEAKS_PER_S * duration_s))),
            "annotation": resultat.annotation, "names": {},
            "moteur": f"factice ({spec.key})" if fake else spec.key,
            "configuration": {
                "experience_source": spec.source_exp, "peripherique": device,
                "nombre_locuteurs": speaker_conf, "moteur_factice": fake, "reglages": describe,
            },
            "calcul_s": calcul_s, "normalisation_s": normalisation_s, "chargement_s": loading_s,
            "durees_etapes": resultat.durees_etapes, "device": device, "factice": fake,
            "rttm_source": resultat.infos.get("rttm_source"),
            "rtf_mesure": {"rtf": measured.rtf, "source": measured.source()} if measured else None,
        }
        n_speakers = len(sortie.speaker_labels(result["annotation"]))
        done = _status_html(
            steps, {step: 1.0 for step in steps},
            f"{n_speakers} locuteur{'s' if n_speakers > 1 else ''} en {temps.format_duration(calcul_s)}",
            f"{Path(audio_path).name}, {temps.format_duration(duration_s)} d'audio, {spec.label}, "
            f"RTF {_num(calcul_s / duration_s, 4)}", 1.0)
        names_rows = [[label, ""] for label in sortie.speaker_labels(result["annotation"])]
        yield (done, _viewer_value(result), _stats_html(result),
               gr.update(value=names_rows, visible=True, row_limits=(len(names_rows), len(names_rows))),
               _times_html(result), _der_html(result, reference_path),
               gr.update(value=_exports(result), visible=True), gr.update(visible=False), result)

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
                        with gr.Column(elem_classes="ws-card"):
                            gr.HTML(_title("Locuteurs"), js_on_load=None)
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

        engine.change(engine_changed, engine, [engine, mode, device])
        mode.change(mode_changed, mode, [k, range_row])
        run.click(
            analyse, [audio, engine, mode, k, k_min, k_max, device, reference],
            [status, viewer, stats, names, times, der, exports, exports_empty, result_state],
            concurrency_limit=1, show_progress="hidden",  # l'avancement est dans le panneau d'état
        )
        names.input(rename, [names, result_state], [viewer, stats, exports, result_state])
        reference.change(lambda path, result: _der_html(result, path), [reference, result_state], der)
    return app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Application de démonstration Who Spoke? (D17).")
    parser.add_argument("--factice", action="store_true",
                        help="moteur factice : étapes simulées et RTTM des expériences, aucune inférence")
    parser.add_argument("--factice-max-s", type=float, default=20.0,
                        help="durée maximale simulée d'une analyse en mode factice (s)")
    parser.add_argument("--port", type=int, default=7860, help="port local (défaut : 7860)")
    args = parser.parse_args(argv)
    for stale in travail.remove_stale():
        print(f"Dossier temporaire d'un lancement interrompu supprimé : {stale}")
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    # Suppression à la fermeture : sortie normale, Ctrl+C ou SIGTERM.
    atexit.register(travail.cleanup, RUN_DIR)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    gr.set_static_paths([STATIC_DIR])
    app = build_app(fake=args.factice, fake_max_s=args.factice_max_s)
    app.launch(
        server_name="127.0.0.1", server_port=args.port, share=False,
        allowed_paths=[str(RUN_DIR)], theme=theme.build_theme(), css=theme.css(),
        footer_links=["settings"], mcp_server=False, ssr_mode=False,
    )


if __name__ == "__main__":
    main()
