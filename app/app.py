"""Application de démonstration « Who Spoke? » (D17), onglet « Analyse ».

Lancement :
    uv run python -m app.app                # moteurs réels
    uv run python -m app.app --factice      # moteur factice, sans aucune inférence

Tout audio déposé est normalisé en WAV 16 kHz mono (D15, D16) dans un dossier de travail
temporaire, hors du dépôt. L'interface fonctionne hors ligne : wavesurfer.js est servi
depuis app/static/, le thème n'utilise que des polices locales et la télémétrie de Gradio
est désactivée.
"""

from __future__ import annotations

import os

# Avant l'import de gradio : aucune télémétrie (D17, hors ligne).
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import argparse
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

if __package__ in (None, ""):  # uv run python app/app.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gradio as gr

from app import moteurs, sortie, temps
from whospoke.audio import AudioError, load_waveform, normalize
from whospoke.device import select_device
from whospoke.pipelines.base import load_catalogue

STATIC_DIR = Path(__file__).resolve().with_name("static")
WAVESURFER_DIR = STATIC_DIR / "wavesurfer-7.12.12"
WORK_ROOT = Path(tempfile.gettempdir()) / "whospoke-app"

# Palette catégorielle validée (skill dataviz, ordre fixe), clair et sombre ; au-delà de
# huit locuteurs, un gris neutre : chaque piste porte le nom, la couleur n'est pas seule.
PALETTE_LIGHT = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
PALETTE_DARK = ("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767")
OTHER_LIGHT, OTHER_DARK = "#8a8985", "#a3a29c"

SPEAKER_MODES = ("Automatique", "Imposé", "Fourchette")
DEVICES = ("auto", "cpu", "mps", "cuda")
PRE_STEPS = ("normalisation_audio", "chargement")
PRE_LABELS = {"normalisation_audio": "Normalisation audio (ffmpeg)", "chargement": "Chargement du modèle"}

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
        engine = moteurs.FakeEngine(spec) if self.fake else moteurs.build_engine(spec, device)
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


def _status_html(steps: list[str], state: dict[str, float], headline: str, detail: str = "",
                 fraction: float | None = None) -> str:
    rows = []
    for step in steps:
        value = state.get(step, 0.0)
        if value >= 1.0:
            icon, cls, text = "✓", "done", "terminé"
        elif value > 0.0:
            icon, cls, text = "◐", "run", f"{int(100 * value)} %"
        else:
            icon, cls, text = "○", "todo", ""
        label = PRE_LABELS.get(step) or STEP_LABELS.get(step, step)
        rows.append(f'<li class="st-{cls}"><span class="st-icon">{icon}</span>{label}'
                    f'<span class="st-val">{text}</span></li>')
    bar = ""
    if fraction is not None:
        bar = (f'<div class="st-bar" role="progressbar" aria-valuenow="{int(100 * fraction)}">'
               f'<div style="width:{100 * min(1.0, fraction):.1f}%"></div></div>')
    return (f'<div class="st-root"><div class="st-head">{headline}</div>{bar}'
            f'<div class="st-detail">{detail}</div><ol class="st-steps">{"".join(rows)}</ol></div>')


def _step_fraction(steps: list[str], state: dict[str, float]) -> float:
    return sum(min(1.0, state.get(step, 0.0)) for step in steps) / len(steps)


# --- Résultats ------------------------------------------------------------------------


def _stats_rows(result: dict) -> list[list]:
    stats = sortie.speaker_stats(result["annotation"], result["names"])
    total = sum(row["temps_parole_s"] for row in stats) or 1.0
    colors = _speaker_colors([row["id"] for row in stats])
    rows = []
    for row in stats:
        swatch = (f'<span style="display:inline-block;width:10px;height:10px;border-radius:2px;'
                  f'background:{colors[row["id"]][0]};margin-right:6px"></span>')
        rows.append([
            swatch + row["nom"], row["id"], temps.format_duration(row["temps_parole_s"]),
            _pct(100 * row["temps_parole_s"] / total), row["n_interventions"],
            _pct(100 * row["part_chevauchement"]),
        ])
    return rows


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


def _times_md(result: dict) -> str:
    lines = [
        "| Étape | Durée |", "|---|---|",
        f"| Normalisation audio (ffmpeg) | {_num(result['normalisation_s'], 2)} s |",
        "| Chargement du modèle | " + ("déjà chargé" if result["chargement_s"] is None
                                     else f"{_num(result['chargement_s'], 2)} s (non compté dans le RTF)") + " |",
    ]
    for step, seconds in result["durees_etapes"].items():
        lines.append(f"| {STEP_LABELS.get(step, step)} | {_num(seconds, 2)} s |")
    rtf = result["calcul_s"] / result["duree_s"] if result["duree_s"] else 0.0
    lines.append(f"| **Calcul total** | **{_num(result['calcul_s'], 2)} s** |")
    measured = result["rtf_mesure"]
    summary = (f"Audio de {temps.format_duration(result['duree_s'])}, RTF obtenu **{_num(rtf, 4)}**"
               + (f" (RTF mesuré : {_num(measured['rtf'], 4)}, {measured['source']})" if measured else "")
               + f", périphérique `{result['device']}`.")
    note = ""
    if result["factice"]:
        note = (f"\n\n> **Moteur factice** : aucune inférence ; segments repris de "
                f"`{result['rttm_source']}`, temps de calcul simulé"
                + (", contrainte sur le nombre de locuteurs ignorée."
                   if result["configuration"]["nombre_locuteurs"]["mode"] != "automatique" else "."))
    return summary + note + "\n\n" + "\n".join(lines)


def _der_md(result: dict | None, reference_path: str | None) -> str:
    if not reference_path:
        return "*Déposer une référence RTTM pour afficher le DER décomposé.*"
    if result is None:
        return "*Référence chargée : le DER s'affichera après l'analyse.*"
    try:
        reference = sortie.read_reference(reference_path)
        report = sortie.der_report(reference, result["annotation"], result["duree_s"])
    except ValueError as error:
        return f"**Référence inutilisable** : {error}"
    lines = [
        "| Condition | DER | Parole manquée | Fausse alarme | Confusion | JER |",
        "|---|---|---|---|---|---|",
    ]
    for name, title in (("collar_0", "Sans collar (principale)"), ("collar_0_25", "Collar ± 0,25 s")):
        r = report[name]
        lines.append(f"| {title} | **{_pct(r['der'], 2)}** | {_pct(r['manquee'], 2)} | "
                     f"{_pct(r['fausse_alarme'], 2)} | {_pct(r['confusion'], 2)} | {_pct(r['jer'], 2)} |")
    zones = report["zones"]
    zone = {key: None if value is None else value["der"] for key, value in zones.items()}
    counts = report["n_locuteurs"]
    return (
        "\n".join(lines)
        + f"\n\nDER sans collar par zone : sans chevauchement {_pct(zone['sans_chevauchement'], 2)}, "
        + f"chevauchement {_pct(zone['chevauchement'], 2)}. "
        + f"Locuteurs : {counts['hypothese']} estimés pour {counts['reference']} dans la référence. "
        + "Évaluation sur toute la durée de l'audio analysé, chevauchements comptés (protocole §3)."
    )


# --- Application ----------------------------------------------------------------------


def build_app(fake: bool = False, fake_max_s: float = 20.0) -> gr.Blocks:
    cache = EngineCache(fake, fake_max_s)
    availability = _availability(fake)
    choices = [
        (spec.label + ("" if availability[key] is None else " — indisponible"), key)
        for key, spec in moteurs.SPECS.items()
    ]
    head = "".join(f'<script src="{_file_url(WAVESURFER_DIR / name)}"></script>'
                   for name in ("wavesurfer.min.js", "regions.min.js"))

    def engine_changed(key: str):
        spec = moteurs.SPECS[key]
        modes = list(SPEAKER_MODES if spec.supports_range else SPEAKER_MODES[:2])
        info = availability[key] or f"Configuration reprise de {spec.source_exp}."
        device = (gr.update(value="cpu", interactive=False, info="CPU seul pour ce moteur (D19, D22).")
                  if spec.cpu_only else gr.update(interactive=True, info="auto : CUDA, puis MPS, puis CPU (D15)."))
        return gr.update(choices=modes, value="Automatique"), device, gr.update(value=f"*{info}*")

    def mode_changed(mode: str):
        return gr.update(visible=mode == "Imposé"), gr.update(visible=mode == "Fourchette")

    def analyse(audio_path, key, mode, k, k_min, k_max, device_choice, reference_path):
        spec = moteurs.SPECS[key]
        if not audio_path:
            raise gr.Error("Déposer d'abord un fichier audio.")
        if availability[key] is not None:
            raise gr.Error(f"{spec.label} indisponible : {availability[key]}")
        num_speakers = None
        speaker_conf: dict = {"mode": "automatique"}
        if mode == "Imposé":
            if not k or int(k) < 1:
                raise gr.Error("Nombre de locuteurs imposé : entier ≥ 1 attendu.")
            num_speakers = int(k)
            speaker_conf = {"mode": "impose", "valeur": num_speakers}
        elif mode == "Fourchette":
            if not spec.supports_range:
                raise gr.Error(f"{spec.label} : fourchette non prise en charge.")
            if not k_min or not k_max or int(k_min) < 1 or int(k_min) > int(k_max):
                raise gr.Error("Fourchette : 1 ≤ minimum ≤ maximum attendu.")
            speaker_conf = {"mode": "fourchette", "min": int(k_min), "max": int(k_max)}
        try:
            device = "cpu" if spec.cpu_only else select_device(device_choice).type
        except (RuntimeError, ValueError) as error:
            raise gr.Error(str(error)) from error

        steps = list(PRE_STEPS) + list(spec.steps)
        state: dict[str, float] = {}
        skip = (gr.skip(),) * 7
        empty = (None, [], [], "", _der_md(None, reference_path), None, None)
        yield (_status_html(steps, state, "Normalisation de l'audio…"), *empty)

        uri = Path(audio_path).stem
        work = sortie.new_work_dir(WORK_ROOT)
        start = time.perf_counter()
        try:
            wav = normalize(audio_path, work / f"{sortie.rttm_name(uri)}.wav")
        except AudioError as error:
            raise gr.Error(f"Audio illisible : {error}") from error
        normalisation_s = time.perf_counter() - start
        state["normalisation_audio"] = 1.0
        waveform, sample_rate = load_waveform(wav)
        duration_s = waveform.shape[1] / sample_rate

        measured = temps.measured_rtf(spec.source_exp, device, moteurs.source_device(spec))
        rtf = measured.rtf if measured else None
        estimate = temps.format_duration(rtf * duration_s) if rtf else "inconnue (RTF non mesuré)"

        with cache.lock:
            yield (_status_html(steps, state, f"Chargement du modèle {spec.label}…"), *skip)
            try:
                engine, loading_s = cache.get(spec, device)
            except Exception as error:  # chargement des modèles : message affiché tel quel
                raise gr.Error(f"Chargement impossible : {error}") from error
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
                    left = "temps restant inconnu (RTF non mesuré pour ce périphérique)"
                elif remaining > 0:
                    left = f"≈ {temps.format_duration(remaining)} restantes"
                else:
                    left = "estimation dépassée, calcul en cours"
                detail = (f"Écoulé : {temps.format_duration(elapsed)} · {left} · durée estimée {estimate}"
                          + (f" (RTF {_num(rtf, 4)}, {measured.source()})" if measured else ""))
                yield (_status_html(steps, state, f"Analyse de {Path(audio_path).name} — {spec.label}",
                                    detail, _step_fraction(steps, state)), *skip)
                thread.join(0.3)
            calcul_s = time.perf_counter() - t0
            describe = engine.describe_dict()
        if "error" in outcome:
            raise gr.Error(f"Échec de l'analyse : {outcome['error']}")
        resultat = outcome["result"]

        result = {
            "uri": uri, "dir": work, "wav": wav, "duree_s": duration_s,
            "peaks": sortie.peaks(waveform[0].numpy()),
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
        done = _status_html(steps, {step: 1.0 for step in steps},
                            f"Analyse terminée : {n_speakers} locuteur(s) en {temps.format_duration(calcul_s)}",
                            f"Audio de {temps.format_duration(duration_s)} · RTF obtenu {_num(calcul_s / duration_s, 4)}",
                            1.0)
        names_rows = [[label, ""] for label in sortie.speaker_labels(result["annotation"])]
        yield (done, _viewer_value(result), _stats_rows(result), names_rows, _times_md(result),
               _der_md(result, reference_path), _exports(result), result)

    def rename(rows, result):
        if result is None:
            return gr.skip(), gr.skip(), gr.skip(), gr.skip()
        names = {str(row[0]): str(row[1] or "") for row in (rows.values.tolist() if hasattr(rows, "values") else rows)}
        try:
            sortie.resolve_names(sortie.speaker_labels(result["annotation"]), names)
        except ValueError as error:
            gr.Warning(str(error))
            return gr.skip(), gr.skip(), gr.skip(), gr.skip()
        result = dict(result, names=names)
        return _viewer_value(result), _stats_rows(result), _exports(result), result

    with gr.Blocks(title="Who Spoke?") as app:
        result_state = gr.State(None)
        gr.Markdown("# Who Spoke? — qui parle, et quand ?"
                    + ("\n\n**Mode factice** : aucune inférence, résultats repris des expériences."
                       if fake else ""))
        with gr.Tabs():
            with gr.Tab("Analyse"):
                with gr.Row(equal_height=False):
                    with gr.Column(scale=1, min_width=300):
                        audio = gr.File(label="Fichier audio (tout format : wav, mp3, m4a, mp4, ogg…)",
                                        file_count="single", type="filepath")
                        engine = gr.Dropdown(choices, value="pyannote-community-1", label="Moteur")
                        engine_info = gr.Markdown(f"*Configuration reprise de "
                                                  f"{moteurs.SPECS['pyannote-community-1'].source_exp}.*")
                        mode = gr.Radio(list(SPEAKER_MODES), value="Automatique", label="Nombre de locuteurs")
                        k = gr.Number(value=2, precision=0, minimum=1, label="Nombre imposé", visible=False)
                        with gr.Row(visible=False) as range_row:
                            k_min = gr.Number(value=2, precision=0, minimum=1, label="Minimum")
                            k_max = gr.Number(value=6, precision=0, minimum=1, label="Maximum")
                        device = gr.Dropdown(list(DEVICES), value="auto", label="Périphérique",
                                             info="auto : CUDA, puis MPS, puis CPU (D15).")
                        reference = gr.File(label="Référence RTTM (facultative)", file_types=[".rttm"],
                                            type="filepath")
                        run = gr.Button("Analyser", variant="primary")
                    with gr.Column(scale=2, min_width=360):
                        status = gr.HTML(_status_html([], {}, "En attente d'un fichier audio."),
                                         js_on_load=None, elem_classes="st-panel")
                        viewer = gr.HTML(
                            None,
                            html_template=(
                                '<div class="wsp-root wsp-empty">'
                                '<div class="wsp-placeholder">La timeline des locuteurs apparaîtra ici.</div>'
                                '<div class="wsp-body"><div class="wsp-toolbar">'
                                '<button type="button" class="wsp-play">Lecture</button>'
                                '<span class="wsp-time"></span>'
                                '<span class="wsp-hint">Cliquer sur un segment pour l\'écouter</span></div>'
                                '<div class="wsp-wave"></div>'
                                '<div class="wsp-lanes-wrap"><div class="wsp-lanes"></div>'
                                '<div class="wsp-overlay"><div class="wsp-playhead"></div></div></div>'
                                '<div class="wsp-axis"></div></div></div>'
                            ),
                            css_template=(STATIC_DIR / "visualiseur.css").read_text(),
                            js_on_load=(STATIC_DIR / "visualiseur.js").read_text(),
                            head=head,
                        )
                        stats = gr.Dataframe(
                            headers=["Locuteur", "Identifiant", "Temps de parole", "Part du temps",
                                     "Interventions", "Chevauchement"],
                            datatype=["html", "str", "str", "str", "number", "str"],
                            interactive=False, label="Statistiques par locuteur",
                        )
                        names = gr.Dataframe(
                            headers=["Identifiant", "Nom"], datatype=["str", "str"], interactive=True,
                            static_columns=[0], label="Renommer les locuteurs (colonne Nom)",
                        )
                        with gr.Accordion("Temps de traitement", open=True):
                            times = gr.Markdown()
                        with gr.Accordion("DER face à la référence", open=True):
                            der = gr.Markdown(_der_md(None, None))
                        exports = gr.File(label="Exports (RTTM et JSON)", file_count="multiple",
                                          interactive=False)

        engine.change(engine_changed, engine, [mode, device, engine_info])
        mode.change(mode_changed, mode, [k, range_row])
        run.click(
            analyse, [audio, engine, mode, k, k_min, k_max, device, reference],
            [status, viewer, stats, names, times, der, exports, result_state],
            concurrency_limit=1,
        )
        names.input(rename, [names, result_state], [viewer, stats, exports, result_state])
        reference.change(lambda path, result: _der_md(result, path), [reference, result_state], der)
    return app


STATUS_CSS = """
.st-root { padding: 4px 2px; }
.st-head { font-weight: 600; margin-bottom: 6px; }
.st-detail { color: var(--body-text-color-subdued); font-size: 0.9em; margin: 4px 0 8px; }
.st-bar { height: 6px; border-radius: 3px; background: var(--border-color-primary); overflow: hidden; }
.st-bar > div { height: 100%; background: var(--color-accent); transition: width 0.3s; }
.st-steps { list-style: none; padding: 0; margin: 0; columns: 2; font-size: 0.92em; }
.st-steps li { padding: 2px 0; break-inside: avoid; }
.st-icon { display: inline-block; width: 1.4em; }
.st-val { color: var(--body-text-color-subdued); margin-left: 6px; font-variant-numeric: tabular-nums; }
.st-todo { color: var(--body-text-color-subdued); }
.st-run { font-weight: 600; }
"""


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Application de démonstration Who Spoke? (D17).")
    parser.add_argument("--factice", action="store_true",
                        help="moteur factice : étapes simulées et RTTM des expériences, aucune inférence")
    parser.add_argument("--factice-max-s", type=float, default=20.0,
                        help="durée maximale simulée d'une analyse en mode factice (s)")
    parser.add_argument("--port", type=int, default=7860, help="port local (défaut : 7860)")
    args = parser.parse_args(argv)
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    gr.set_static_paths([STATIC_DIR])
    app = build_app(fake=args.factice, fake_max_s=args.factice_max_s)
    app.launch(
        server_name="127.0.0.1", server_port=args.port, share=False,
        allowed_paths=[str(WORK_ROOT)], css=STATUS_CSS,
        theme=gr.themes.Default(),  # polices locales uniquement (LocalFont et polices système)
        footer_links=["settings"], mcp_server=False, ssr_mode=False,
    )


if __name__ == "__main__":
    main()
