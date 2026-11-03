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
import re
import signal
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from html import escape

import gradio as gr

from app import (avancement, formatage, glossaire, image, interactions, moteurs, pipeline, reproductibilite,
                 sortie, spectrogramme, temps, theme)
from app.icones import icon
from app.cache import (ResultCache, annotation_from_tracks, annotation_tracks, audio_fingerprint, code_version,
                       engine_code_fingerprint, result_key)
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
# Mode consigné (configuration, configs/demo.yaml) → libellé du choix dans l'interface.
MODE_LABELS = dict(zip(("automatique", "impose", "fourchette"), SPEAKER_MODES))
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


def _result_colors(result: dict) -> dict[str, tuple[str, str]]:
    """Couleurs des locuteurs du premier moteur, attribuées sur l'annotation d'origine : une
    fusion ne repeint pas les locuteurs restants (la couleur suit le locuteur, pas son rang)."""
    return _speaker_colors(sortie.speaker_labels(result.get("annotation_origine", result["annotation"])))


def _signed(value: float, digits: int = 2) -> str:
    """« +0,42 s », « −0,18 s » ; « 0,00 s », sans signe, pour une valeur qui s'arrondit à zéro."""
    return formatage.unite(value, "s", digits, sign=round(value, digits) != 0)


def _pct(value: float | None, digits: int = 1) -> str:
    return formatage.pourcentage(value, digits)


def _num(value: float, digits: int = 3) -> str:
    return formatage.nombre(value, digits)


class ModelMissing(RuntimeError):
    """Modèle absent du cache local, en fonctionnement hors ligne."""


WARMUP_S = 20.0           # durée du signal synthétique de l'appel à blanc
FAKE_WARMUP_PAUSE_S = 0.8  # préchauffage simulé d'un moteur en mode factice


def warmup_signal(duration_s: float = WARMUP_S, sample_rate: int = 16000):
    """Signal synthétique à allure de parole pour l'appel à blanc : deux voix harmoniques
    (120 et 210 Hz) qui alternent toutes les 2 s, modulées à 4 Hz, sur un bruit faible.
    Aucun fichier audio n'est lu : le préchauffage fonctionne sur une machine vierge."""
    import numpy as np
    import torch

    t = np.arange(int(duration_s * sample_rate)) / sample_rate
    f0 = np.where((t // 2.0) % 2 == 0, 120.0, 210.0)
    phase = 2 * np.pi * np.cumsum(f0) / sample_rate
    voice = sum(np.sin(k * phase) / k for k in range(1, 8))
    envelope = 0.5 * (1 + np.sin(2 * np.pi * 4.0 * t)) * ((t % 2.0) < 1.7)
    noise = np.random.default_rng(0).normal(0.0, 0.003, t.size)
    signal = (0.1 * voice * envelope + noise).astype(np.float32)
    return torch.from_numpy(signal).unsqueeze(0), sample_rate


@dataclass
class WarmupStatus:
    """État du préchauffage, lu par l'indicateur « moteurs prêts » de l'en-tête."""

    enabled: bool = False
    total: int = 0
    done: int = 0
    current: str | None = None
    finished: bool = False
    failures: dict[str, str] = field(default_factory=dict)


class EngineCache:
    """Moteurs chargés une seule fois par (moteur, périphérique), comme dans les expériences.

    Un moteur est « chaud » (`is_warm`) quand il est chargé et qu'il a déjà fait un appel :
    l'appel à blanc du préchauffage ou une analyse. Le surcoût fixe du premier appel n'est
    alors plus compté dans le temps annoncé (D17, amendement 2).
    """

    def __init__(self, fake: bool, fake_max_s: float, experiments: Path = moteurs.EXPERIMENTS_DIR,
                 fabricated: Path | None = None) -> None:
        self.fake = fake
        self.fabricated = fabricated
        self.experiments = experiments
        self.fake_max_s = fake_max_s
        self._engines: dict[tuple[str, str], object] = {}
        self._warm: set[tuple[str, str]] = set()
        self.lock = threading.Lock()
        self.warmup = WarmupStatus()

    def is_warm(self, key: str, device: str) -> bool:
        return (key, device) in self._warm

    def mark_warm(self, key: str, device: str) -> None:
        self._warm.add((key, device))

    def warm_up(self, targets: list[tuple[moteurs.EngineSpec, str]]) -> None:
        """Charge chaque moteur et fait un appel à blanc (R-D2) ; un échec est consigné
        dans `warmup.failures` sans arrêter les autres. Tient le verrou moteur par moteur :
        une analyse lancée pendant le préchauffage attend le moteur en cours."""
        status = self.warmup
        status.enabled, status.total, status.done, status.finished = True, len(targets), 0, False
        for spec, device in targets:
            status.current = spec.label
            with self.lock:
                try:
                    engine, _ = self.get(spec, device)
                    if not self.is_warm(spec.key, device):
                        if self.fake:
                            time.sleep(FAKE_WARMUP_PAUSE_S)
                        else:
                            waveform, sample_rate = warmup_signal()
                            engine.run(waveform, sample_rate, uri="prechauffage")
                        self.mark_warm(spec.key, device)
                except Exception as error:  # consigné, affiché par l'indicateur
                    status.failures[spec.label] = str(error).splitlines()[0][:200] if str(error) else type(error).__name__
            status.done += 1
        status.current, status.finished = None, True

    def get(self, spec: moteurs.EngineSpec, device: str) -> tuple[object, float | None]:
        """(moteur, durée de chargement en s, None s'il était déjà chargé)."""
        key = (spec.key, device)
        if key in self._engines:
            return self._engines[key], None
        start = time.perf_counter()
        try:
            engine = (moteurs.FakeEngine(spec, self.experiments, fabricated=self.fabricated) if self.fake
                      else moteurs.build_engine(spec, device, self.experiments))
        except Exception as error:
            message = moteurs.missing_model_message(error, spec)
            if message is None:
                raise
            raise ModelMissing(message) from error
        self._engines[key] = engine
        return engine, time.perf_counter() - start


def _availability(fake: bool, experiments: Path = moteurs.EXPERIMENTS_DIR,
                  specs: dict[str, moteurs.EngineSpec] | None = None) -> dict[str, str | None]:
    """Raison de l'indisponibilité de chaque moteur (None s'il est utilisable)."""
    reasons: dict[str, str | None] = {}
    for key, spec in (specs or moteurs.SPECS).items():
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
                 failed: str | None = None, error: str | None = None,
                 badges: list[str] | None = None, done_s: float | None = None) -> str:
    """Panneau d'avancement : l'état de chaque étape est écrit, pas seulement dessiné.

    `labels` donne le libellé d'étapes composées (« 2:segmentation » en comparaison).
    `failed` : étape en échec, marquée « échec » ; `error` : message affiché dans le panneau ;
    `badges` : pastilles sous le titre (résultat réaffiché depuis le cache) ; `done_s` : durée
    totale d'une analyse réussie, la liste se replie alors en une ligne dépliable (V7)."""
    rows = []
    for step in steps:
        value = state.get(step, 0.0)
        if step == failed:
            cls, text = "fail", "échec"
        elif value >= 1.0:
            cls, text = "done", "terminé"
        elif value > 0.0:
            cls, text = "run", formatage.pourcentage(int(100 * value), 0)
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
    # Lecture en colonnes de hauteur égale, de haut en bas puis colonne suivante (R-U5).
    rows_per_column = -(-len(rows) // 3)
    steps_html = (f'<ol class="st-steps" style="--st-rows: {rows_per_column}">{"".join(rows)}</ol>'
                  if rows else "")
    if rows and done_s is not None and not failed and all(state.get(step, 0.0) >= 1.0 for step in steps):
        summary = f"{_plural(len(rows), 'étape')} terminée{'s' if len(rows) > 1 else ''} en {temps.format_duration(done_s)}"
        steps_html = f'<details class="st-fold"><summary>{escape(summary)}</summary>{steps_html}</details>'
    error_html = (f'<p class="st-error" role="alert">{escape(error)}</p>' if error else "")
    if badges:
        error_html += ('<p class="st-badges">'
                       + "".join(f'<span class="ws-cache-badge">{escape(b)}</span>' for b in badges) + "</p>")
    root = "st-root st-failed" if failed or error else "st-root"
    return (f'<div class="{root}"><div class="st-head" aria-live="polite">'
            f'<p class="st-title">{escape(title)}</p><span class="st-detail">{escape(detail)}</span></div>'
            f'{error_html}{bar}{steps_html}</div>')


def _estimate_source(run: dict, fake: bool) -> str:
    """Provenance de l'estimation du temps restant : RTF mesuré et surcoût fixe daté,
    compté seulement pour un moteur froid (D17, amendement 2)."""
    text = f"RTF {_num(run['rtf'], 4)} mesuré par {run['measured'].exp_id}"
    if run.get("warm"):
        return f"{text}, moteur préchauffé : surcoût fixe non compté"
    overhead = run.get("overhead")
    if overhead is not None:
        day = datetime.strptime(overhead.measured_on, "%Y-%m-%d").strftime("%d/%m/%Y")
        return f"{text}, surcoût fixe {_num(overhead.seconds, 1)}\u202fs mesuré le {day}"
    return text if fake else f"{text}, surcoût fixe non mesuré"


def _remaining_text(span: tuple[float, float] | None, recalibrated: bool, scope: str = "") -> str:
    """Temps restant affiché pendant l'analyse : fourchette, ou valeur recalée."""
    if span is None:
        return "temps restant inconnu (RTF non mesuré sur ce périphérique)"
    if span[1] <= 0:
        return "estimation dépassée, calcul en cours"
    if recalibrated:
        return f"reste environ {temps.format_duration(span[1])}{scope}, recalé sur la vitesse observée"
    if span[0] <= 0:
        return f"reste au plus {temps.format_duration(span[1])}{scope}"
    return f"reste {temps.format_range(span)}{scope}"


def _longest_started_s(steps: tuple[str, ...], longest: str | None, state: dict[str, float],
                       ends: dict[str, float], t0: float, now: float) -> float | None:
    """Temps écoulé depuis le début de l'étape la plus longue, ou None si elle n'a pas
    commencé. Son début est la fin de l'étape qui la précède (le lancement à défaut)."""
    if longest is None:
        return None
    before = steps[:steps.index(longest)]
    if state.get(longest, 0.0) <= 0.0 and not all(step in ends for step in before):
        return None
    start = max([ends[step] for step in before if step in ends], default=t0)
    return max(0.0, now - start)


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


def _french(text: str) -> str:
    """Espaces insécables dans les guillemets français : « nom » ne se coupe pas en fin de ligne."""
    return text.replace("« ", "«\u00a0").replace(" »", "\u00a0»")


def _capital(text: str) -> str:
    return text[:1].upper() + text[1:]


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    """« 1 locuteur », « 3 locuteurs » ; « aucun locuteur » pour zéro."""
    if count == 0:
        return f"aucun {singular}"
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


# Messages d'échec de la normalisation (B7) : la cause probable et quoi faire, d'après la
# sortie d'erreur de ffmpeg ; le détail technique suit, sans chemin local.
AUDIO_FAILURES = (
    (("moov atom not found", "partial file", "End of file", "Truncating packet"),
     "est incomplet : l'enregistrement a sans doute été interrompu, ou le fichier mal copié. Récupérez le "
     "fichier complet (ou exportez-le de nouveau depuis l'appareil), puis déposez-le."),
    (("does not contain any stream", "matches no streams", "Output file is empty"),
     "ne contient pas de piste son (vidéo muette ?). Déposez un fichier qui contient l'audio de la réunion."),
    (("Invalid data found", "could not find codec parameters", "Unknown input format"),
     "n'est pas un fichier audio ou vidéo lisible, quelle que soit son extension. Vérifiez que c'est bien "
     "l'enregistrement, ou exportez-le de nouveau en WAV, MP3 ou M4A, puis déposez-le."),
)


def _audio_error(name: str, error: Exception) -> str:
    """Message d'un fichier que ffmpeg n'a pas pu normaliser : cause probable, quoi faire."""
    detail = str(error)
    if "ffmpeg introuvable" in detail:
        return ("ffmpeg est introuvable : il normalise tout audio déposé. Installez-le (macOS : brew install "
                "ffmpeg), puis relancez l'application.")
    found = next(((needles, text) for needles, text in AUDIO_FAILURES if any(n in detail for n in needles)), None)
    advice = found[1] if found else ("n'a pas pu être lu par ffmpeg. Convertissez-le en WAV ou en MP3 (avec "
                                     "Audacity, par exemple), puis déposez-le de nouveau.")
    # Lignes de ffmpeg sans préfixe « [in#0 @ 0x…] » ni chemin local ; celle de la cause d'abord.
    stderr = detail.split(") : ", 1)[-1]          # après « ffmpeg a échoué sur <chemin> (code n) : »
    lines = [re.sub(r"^\[[^\]]*@ 0x[0-9a-f]+\] ", "", line).strip() for line in stderr.splitlines()]
    lines = [line for line in lines if line and "/" not in line]
    cause = [line for line in lines if found and any(n in line for n in found[0])]
    technical = (cause or lines or [""])[0].rstrip(".")
    return _french(f"« {name} » {advice}" + (f" (Détail technique : {technical}.)" if technical else ""))


SILENT_PEAK = 10 ** (-80 / 20)   # niveau maximal sous −80 dB pleine échelle : fichier silencieux


def _title(text: str, note: str = "") -> str:
    note_html = f'<p class="ws-note">{note}</p>' if note else ""
    return f'<h2 class="ws-section-title">{escape(text)}</h2>{note_html}'


def _howto_html() -> str:
    """Carte « Comment ça marche » (V8) : seule carte de la colonne de droite avant toute
    analyse, à la place des cartes vides."""
    steps = (
        ("Déposer un enregistrement", "Tout format audio ou vidéo, normalisé en WAV 16 kHz mono. "
         "Le fichier reste sur cette machine."),
        ("Choisir un moteur et le nombre de locuteurs", "Automatique (le moteur l'estime), imposé, ou une "
         "fourchette pour pyannote. Une référence RTTM, facultative, permet de mesurer le DER."),
        ("Analyser", "La durée du calcul est annoncée avant le lancement, puis chaque étape s'affiche."),
    )
    items = "".join(f'<li><span class="ws-howto-num" aria-hidden="true">{n}</span><div>'
                    f'<p class="ws-howto-step">{escape(title)}</p><p class="ws-note">{escape(text)}</p></div></li>'
                    for n, (title, text) in enumerate(steps, 1))
    results = ("Une timeline par locuteur, à écouter segment par segment", "Les statistiques et les interactions",
               "Avec une référence : le DER et la carte des erreurs, chaque erreur expliquée",
               "Les exports : RTTM, JSON, étiquettes Audacity, image")
    return (f'<ol class="ws-howto-steps">{items}</ol>'
            '<p class="ws-subtitle">Ce que vous obtiendrez</p>'
            f'<ul class="ws-howto-results">{"".join(f"<li>{escape(r)}</li>" for r in results)}</ul>'
            '<p class="ws-howto-more"><button type="button" class="ws-btn" data-ws-tab="Pipeline">'
            'Voir les étapes de chaque moteur</button></p>')


def _how_to_read(caption_html: str, title: str = "Comment lire ce tableau") -> str:
    """Texte d'aide d'un tableau, replié (V13) ; masqué en mode présentation."""
    return f'<details class="ws-howto-read"><summary>{escape(title)}</summary>{caption_html}</details>'


def _empty(text: str) -> str:
    return f'<p class="ws-empty-note">{escape(text)}</p>'


NO_SPEAKER = ("Aucun locuteur détecté : le moteur n'a trouvé aucune parole dans ce fichier. Vérifiez que l'audio "
              "contient bien la réunion (niveau, piste ou micro choisis à l'enregistrement), ou essayez un autre moteur.")


def _stats_html(result: dict | None) -> str:
    """Statistiques par locuteur du premier moteur, avec le renommage dans le tableau (un
    champ par ligne, R-U6) et un bouton ▶ qui lit son extrait typique dans la timeline."""
    if result is None:
        return _empty("Les statistiques par locuteur s'afficheront après l'analyse.")
    if not len(result["annotation"]):
        return _empty(NO_SPEAKER)
    names = result["names"]
    stats = sortie.speaker_stats(result["annotation"], names)
    excerpts = sortie.typical_excerpts(result["annotation"])
    total = sum(row["temps_parole_s"] for row in stats) or 1.0
    colors = _result_colors(result)
    shown_names = {row["id"]: row["nom"] for row in stats}
    rows = []
    for row in stats:
        color = colors[row["id"]][0]
        share = 100 * row["temps_parole_s"] / total
        ident, shown = escape(row["id"], quote=True), escape(row["nom"], quote=True)
        excerpt = excerpts.get(row["id"])
        if excerpt is None:
            play = (f'<button type="button" class="ws-btn ws-btn-icon ws-excerpt" disabled '
                    f'aria-label="Pas d\'extrait de {shown} : toute sa parole est en chevauchement" '
                    f'title="Toute la parole de ce locuteur est en chevauchement">{icon("lecture")}</button>')
        else:
            length = f"{_num(excerpt[1] - excerpt[0], 1)}\u202fs"
            play = (f'<button type="button" class="ws-btn ws-btn-icon ws-excerpt" data-debut="{excerpt[0]}" '
                    f'data-fin="{excerpt[1]}" data-id="{ident}" '
                    f'aria-label="Écouter un extrait typique de {shown} ({length})" '
                    f'title="Plus long tour sans chevauchement, {length}">{icon("lecture")}</button>')
        rows.append(
            f'<tr><td class="ws-speaker"><span class="ws-swatch" style="background:{color}" aria-hidden="true"></span>'
            f'<span class="ws-speaker-name"><input type="text" class="ws-name-input" data-id="{ident}" '
            f'value="{escape(names.get(row["id"], ""), quote=True)}" placeholder="{ident}" maxlength="60" '
            f'autocomplete="off" spellcheck="false" aria-label="Nom de {ident}">'
            + (f'<span class="sub">{escape(row["id"])}</span>' if row["nom"] != row["id"] else "")   # V3
            + '</span></td>'
            f'<td class="ws-play-cell">{play}</td>'
            f'<td class="num">{temps.format_duration(row["temps_parole_s"])}</td>'
            f'<td class="num"><span class="ws-share"><span class="ws-share-bar" aria-hidden="true">'
            f'<span style="width:{share:.1f}%;background:{color}"></span></span>{_pct(share)}</span></td>'
            f'<td class="num">{row["n_interventions"]}</td>'
            f'<td class="num">{_pct(100 * row["part_chevauchement"])}</td>'
            f'<td>{_merge_select(row["id"], shown_names)}</td></tr>'
        )
    return (
        '<div class="ws-table-wrap"><table class="ws-table ws-speakers"><thead><tr><th scope="col">Locuteur</th>'
        '<th scope="col"><span class="ws-sr">Extrait</span></th>'
        '<th scope="col" class="num">Temps de parole</th><th scope="col" class="num">Part</th>'
        '<th scope="col" class="num">Interventions</th><th scope="col" class="num">Chevauchement</th>'
        '<th scope="col">Fusion</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        f'{_merges_html(result)}'
        + _how_to_read(
        '<p class="ws-caption">Renommer : saisissez un nom, puis Entrée ou quittez le champ ; vide, '
        "l'identifiant du moteur est gardé. ▶ : extrait typique, le plus long tour sans chevauchement "
        f'({_num(sortie.EXCERPT_MAX_S, 0)}\u202fs au plus), lu dans la timeline. Chevauchement : part du temps de parole '
        'du locuteur pendant laquelle au moins une autre personne parle. Fusionner : la parole du locuteur de la '
        'ligne rejoint celle du locuteur choisi, qui garde son nom et sa couleur ; statistiques, timeline, exports '
        'et DER sont recalculés, le résultat en cache reste celui du moteur.</p>')
    )


def _merge_select(ident: str, shown_names: dict[str, str]) -> str:
    """Liste « Fusionner avec… » d'une ligne du tableau des locuteurs (R-U9)."""
    others = [(other, name) for other, name in shown_names.items() if other != ident]
    if not others:
        return '<span class="sub">—</span>'
    options = "".join(f'<option value="{escape(other, quote=True)}">{escape(name)}</option>' for other, name in others)
    return (f'<select class="ws-merge" data-id="{escape(ident, quote=True)}" '
            f'aria-label="Fusionner {escape(shown_names[ident], quote=True)} avec un autre locuteur">'
            f'<option value="" selected>Fusionner avec…</option>{options}</select>')


def _merges_html(result: dict) -> str:
    """Fusions en vigueur, dans l'ordre, et bouton pour annuler la dernière."""
    fusions = result.get("fusions") or []
    if not fusions:
        return ""
    labels = sortie.speaker_labels(result.get("annotation_origine", result["annotation"]))
    names = {label: (result["names"].get(label) or "").strip() or label for label in labels}
    items = "".join(f"<li>{escape(names.get(source, source))} → {escape(names.get(target, target))}</li>"
                    for source, target in fusions)
    source, target = fusions[-1]
    return (f'<div class="ws-merges" role="status"><span class="ws-merges-title">Fusions en vigueur</span>'
            f'<ol class="ws-merges-list">{items}</ol>'
            f'<button type="button" class="ws-btn ws-merge-undo">Annuler la dernière fusion '
            f'({escape(names.get(source, source))} → {escape(names.get(target, target))})</button></div>')


def _interactions_html(result: dict | None) -> str:
    """Indicateurs d'interaction du premier moteur (R-U10) : plus long monologue, tours,
    latence médiane de réponse par locuteur et matrice « qui suit qui »."""
    if result is None:
        return _empty("Les indicateurs d'interaction s'afficheront après l'analyse.")
    if not len(result["annotation"]):
        return _empty("Aucun locuteur détecté : pas d'interaction à décrire.")
    data = interactions.report(result["annotation"])
    labels = data["ordre"]
    names = sortie.resolve_names(labels, result["names"])
    colors = _result_colors(result)

    def who(label: str) -> str:
        return (f'<span class="ws-swatch" style="background:{colors[label][0]}" aria-hidden="true"></span>'
                f'{escape(names[label])}')

    longest = data["plus_long_monologue"]
    head = ""
    if longest:
        end = min(longest["fin"], longest["debut"] + sortie.EXCERPT_MAX_S)
        heard = end - longest["debut"]
        heard = _num(heard, 2 if heard < 1 else 1)
        head = (f'<p class="ws-monologue"><span class="ws-monologue-label">Plus long monologue</span>'
                f'<span class="ws-who">{who(longest["locuteur"])}</span>'
                f'<span class="strong">{temps.format_duration(longest["duree_s"])}</span>'
                f'<span class="sub">à {image.clock(longest["debut"])}</span>'
                f'<button type="button" class="ws-btn ws-btn-icon ws-excerpt" data-debut="{longest["debut"]}" '
                f'data-fin="{end}" aria-label="Écouter le début du plus long monologue ({heard} s)" '
                f'title="Écouter le début ({heard} s)">{icon("lecture")}</button></p>')
    rows = []
    for row in data["locuteurs"]:
        latency = ("—" if row["latence_mediane_s"] is None
                   else f'{_signed(row["latence_mediane_s"])}<span class="sub">{row["n_reponses"]} réponse'
                        f'{"s" if row["n_reponses"] > 1 else ""}</span>')
        mean = ("—" if row["duree_moyenne_tour_s"] is None
                else f'{_num(row["duree_moyenne_tour_s"], 2 if row["duree_moyenne_tour_s"] < 1 else 1)}\u202fs')
        rows.append(f'<tr><td class="ws-who">{who(row["id"])}</td><td class="num">{row["n_tours"]}</td>'
                    f'<td class="num">{mean}</td>'
                    f'<td class="num">{temps.format_duration(row["plus_long_tour_s"])}</td>'
                    f'<td class="num ws-latency">{latency}</td></tr>')
    table = ('<div class="ws-table-wrap"><table class="ws-table ws-interactions"><thead><tr>'
             '<th scope="col">Locuteur</th><th scope="col" class="num">Tours</th>'
             '<th scope="col" class="num">Durée moyenne d\'un tour</th><th scope="col" class="num">Plus long tour</th>'
             '<th scope="col" class="num">Latence médiane de réponse</th></tr></thead>'
             f'<tbody>{"".join(rows)}</tbody></table></div>')
    return (head + table + _follow_matrix_html(data, names, who)
            + _how_to_read('<p class="ws-caption">Sans transcription, sur les tours du premier moteur (erreurs comprises). Tour : '
              'plage continue de parole d\'un locuteur, comme une intervention du tableau des locuteurs. Un locuteur '
              'prend la parole quand son tour finit après celui de qui l\'avait ; un tour inclus dans celui d\'un '
              'autre (acquiescement, chevauchement bref) ne compte pas. Latence : début du tour moins fin du tour '
              'précédent, négative quand le locuteur commence avant que l\'autre ait fini.</p>'))


MATRIX_NAMED_MAX = 4     # locuteurs au-delà desquels les colonnes de la matrice sont numérotées
MATRIX_NAME_MAX = 14     # longueur de nom au-delà de laquelle aussi


def _follow_matrix_html(data: dict, names: dict[str, str], who) -> str:
    """Matrice « qui suit qui » (R-U10) : un vrai tableau (en-têtes de ligne et de colonne),
    effectif écrit dans chaque case, teinte d'encre proportionnelle en plus."""
    labels, matrix = data["ordre"], data["qui_suit_qui"]
    if len(labels) < 2:
        return ""
    top = max((count for row in matrix for count in row), default=0) or 1
    # Plus de 4 locuteurs, ou un nom long : colonnes numérotées comme les lignes, nom complet
    # en info-bulle et pour les lecteurs d'écran ; sinon la matrice s'étale ou coupe les noms (B7).
    numbered = len(labels) > MATRIX_NAMED_MAX or any(len(names[label]) > MATRIX_NAME_MAX for label in labels)
    if numbered:
        head = "".join(f'<th scope="col" class="num" title="{escape(names[label], quote=True)}">'
                       f'<span aria-hidden="true">{index}</span><span class="ws-sr">{escape(names[label])}</span></th>'
                       for index, label in enumerate(labels, start=1))
    else:
        head = "".join(f'<th scope="col" class="num">{escape(names[label])}</th>' for label in labels)
    body = []
    for i, before in enumerate(labels):
        cells = []
        for j, after in enumerate(labels):
            if i == j:
                cells.append('<td class="num ws-mx-diag"><span aria-hidden="true">—</span>'
                             '<span class="ws-sr">sans objet</span></td>')
                continue
            count = matrix[i][j]
            shade = round(4 + 26 * count / top) if count else 0
            style = f' style="--mx:{shade}%"' if count else ""
            cells.append(f'<td class="num ws-mx"{style}>{count}</td>')
        number = f'<span class="ws-mx-num" aria-hidden="true">{i + 1}</span>' if numbered else ""
        # Nom coupé à deux lignes (nom complet en info-bulle) : la matrice reste lisible à 375 px.
        body.append(f'<tr><th scope="row" class="ws-who" title="{escape(names[before], quote=True)}">'
                    f'<span class="ws-mx-who">{number}{who(before)}</span></th>{"".join(cells)}</tr>')
    return ('<h3 class="ws-subtitle">Qui suit qui</h3>'
            '<div class="ws-table-wrap"><table class="ws-table ws-matrix">'
            f'<caption class="ws-sr">Qui suit qui : nombre de passages de parole, du locuteur de la ligne, qui avait '
            f'la parole, au locuteur de la colonne, qui la prend ; {_plural(data["n_passages"], "passage")} en tout.</caption>'
            '<thead><tr><th scope="col"><span class="ws-mx-corner">Avait la parole ↓ · prend la parole →</span></th>'
            f'{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
            + _how_to_read(f'<p class="ws-caption">{_capital(_plural(data["n_passages"], "passage"))} de parole. Ligne : qui avait la parole ; colonne : '
            + ('qui la prend, numérotée comme les lignes.' if numbered else 'qui la prend.') + ' Plus la case est marquée, plus le passage est fréquent ; l\'effectif est écrit dans la case.</p>',
                           "Comment lire la matrice"))


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


def _group(group_id: str, title: str, annotation, names: dict, colored: bool, errors: dict | None,
           colors: dict | None = None) -> dict:
    labels = sortie.speaker_labels(annotation)
    resolved = sortie.resolve_names(labels, names)
    colors = ((colors or _speaker_colors(labels)) if colored
              else {label: (NEUTRAL_LIGHT, NEUTRAL_DARK) for label in labels})
    return {
        "id": group_id, "titre": title,
        "locuteurs": [{"id": label, "nom": resolved[label], "couleur": colors[label][0],
                       "couleur_sombre": colors[label][1]} for label in labels],
        "segments": sortie.segments(annotation),
        "erreurs": errors,
    }


def _reference_group(result: dict) -> dict:
    """Groupe de la référence (R-U4) : chaque locuteur de référence prend la couleur du
    locuteur du premier moteur qui lui est apparié (appariement optimal du DER) et une
    étiquette courte « SPK_00 → S2 » (V9), S2 étant le rang du locuteur trouvé, comme les
    touches 1 à 9 et les codes Audacity ; nom complet en infobulle (`titre`). Non apparié,
    il reste gris et le dit."""
    reference = result["reference"]
    errors = result.get("erreurs")
    pairs = errors.get("appariement") if errors else None
    hyp_labels = sortie.speaker_labels(result["annotation"])
    hyp_colors = {label: color for label, color in _result_colors(result).items() if label in hyp_labels}
    hyp_names = sortie.resolve_names(hyp_labels, result["names"])
    speakers = []
    for label in sortie.speaker_labels(reference):
        found = pairs.get(label) if pairs else None
        if found in hyp_colors:
            (light, dark), text = hyp_colors[found], f"{label} → S{hyp_labels.index(found) + 1}"
            full = f"{label} (référence), apparié à {hyp_names[found]}"
        else:
            (light, dark), text = (NEUTRAL_LIGHT, NEUTRAL_DARK), (f"{label} → aucun" if pairs is not None else label)
            full = f"{label} (référence), apparié à aucun locuteur trouvé" if pairs is not None else f"{label} (référence)"
        speakers.append({"id": label, "nom": text, "titre": full, "couleur": light, "couleur_sombre": dark,
                         "apparie": found})
    title = "Référence" if pairs is None else f"Référence, appariée à {result.get('libelle', '')}"
    return {"id": "ref", "titre": title, "locuteurs": speakers, "segments": sortie.segments(reference),
            "erreurs": None}


def _viewer_value(result: dict) -> dict:
    """Timeline : premier moteur, second moteur éventuel, référence éventuelle (D26, I5),
    chacun avec sa carte des erreurs ; tous dans le même canevas, donc le même zoom."""
    groups = [_group("a", result.get("libelle", ""), result["annotation"], result["names"], True,
                     result.get("erreurs"), _result_colors(result))]
    other = result.get("comparaison")
    if other:
        groups.append(_group("b", other["libelle"], other["annotation"], other.get("names", {}), False,
                             other.get("erreurs")))
    if result.get("reference") is not None:
        groups.append(_reference_group(result))
    return {
        "audio_url": _file_url(result["wav"]),
        "duree_s": result["duree_s"],
        "peaks": result["peaks"],
        "groupes": groups,
        "spectrogramme": _with_url(result.get("spectrogramme")),
        "detection": _detection_view(result),
    }


def _with_url(description: dict | None, **extra) -> dict | None:
    """Description d'un fichier calculé côté serveur, son chemin remplacé par son URL."""
    if not description:
        return None
    shown = {key: value for key, value in description.items() if key != "fichier"}
    return dict(shown, url=_file_url(description["fichier"]), **extra)


def _detection_view(result: dict) -> dict | None:
    """Énergie et seuil de la baseline (D28 §2) : premier moteur, sinon second moteur."""
    for item in (result, result.get("comparaison")):
        if item and item.get("detection"):
            return _with_url(item["detection"], moteur=item.get("libelle", ""))
    return None


def _detection_file(detection: dict | None, prepared: dict, key: str) -> dict | None:
    """Écrit l'énergie de la détection à côté de l'audio normalisé ; sa description."""
    if detection is None:
        return None
    wav = Path(prepared["wav"])
    return spectrogramme.write_energy(detection, wav.with_name(f"{wav.stem}.{key}.energie.bin"))


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
        {"type": kind, "libelle": label, "duree": f"{_num(totals[kind], 2)}\u202fs",
         "part": _pct(100 * totals[kind] / total, 2)}
        for kind, label in ERROR_LABELS.items()
    ]
    for zone in errors["zones"]:
        _explain_zone(zone)
    return errors


def _explain_zone(zone: dict) -> None:
    """« Expliquer cette erreur » : catégorie de la partie hors tolérance de la zone
    (`sortie.main_category`, option b du 02/11) et sa phrase, la part pardonnée par le
    collar, puis les autres constats sur toute la zone (R-U4) ; jamais une cause affirmée."""
    found = _context_sentences(zone["contexte"], zone["fin"] - zone["debut"])
    found.pop("frontiere", None)          # remplacé par la part dans la tolérance, ci-dessous
    category = zone["categorie"]
    outside = zone["contexte_hors_tolerance"]
    partial = outside is not None and zone["tolerance_s"] > 0
    zone["categorie_libelle"] = sortie.ERROR_CATEGORIES[category]
    if category == "frontiere":
        text = (f"La zone tient entièrement dans la tolérance de {_num(sortie.BOUNDARY_S, 2)}\u202fs d'une frontière de tour "
                "de la référence : le collar la pardonne.")
    elif category == "reference_non_appariee":
        text = f"Le locuteur de référence {zone['reference']} n'est apparié à aucun locuteur trouvé."
    elif category == "trouve_en_trop":
        # Sans son nom : le locuteur trouvé peut avoir été renommé (ligne « Locuteur trouvé »).
        text = "Le locuteur trouvé n'est apparié à aucun locuteur de la référence."
    elif category == "autre":
        text = ("Aucune des catégories précédentes (chevauchement, locuteur non apparié, tour court, "
                "pause courte).")
    else:
        # Phrase calculée sur la partie hors tolérance ; le constat sur toute la zone n'est pas répété.
        text = _context_sentences(outside, outside["duree_s"])[category]
        found.pop(category, None)
    if partial:
        text = "Hors de la tolérance d'une frontière : " + text[0].lower() + text[1:]
        zone["categorie_tolerance"] = (f"Dont {_num(zone['tolerance_s'], 2)}\u202fs dans la tolérance d'une frontière "
                                       "(pardonnés par le collar).")
    else:
        zone["categorie_tolerance"] = ""
    zone["categorie_texte"] = text
    zone["constats"] = list(found.values())


def _context_sentences(context: dict, duration_s: float) -> dict[str, str]:
    """Constats factuels sur la référence autour d'une zone d'erreur (« Expliquer cette
    erreur », R-U4), par catégorie (`sortie.ERROR_CATEGORIES`) ; jamais une cause affirmée."""
    sentences = {}
    overlap = context["chevauchement_s"]
    if overlap > 0:
        if duration_s > 0 and overlap >= 0.99 * duration_s:
            sentences["chevauchement"] = "La zone tombe dans un chevauchement de la référence."
        else:
            share = _pct(100 * overlap / duration_s, 0) if duration_s > 0 else "—"
            sentences["chevauchement"] = (f"La zone recoupe un chevauchement de la référence sur {_num(overlap, 2)}\u202fs "
                                          f"({share} de sa durée).")
    short = context["tour_court"]
    if short:
        sentences["tour_court"] = (f"Elle recoupe un tour de la référence de moins de {formatage.general(sortie.SHORT_TURN_S)}\u202fs "
                                   f"({short['locuteur']}, {_num(short['duree_s'], 2)}\u202fs).")
    pause = context["pause"]
    if pause:
        verb = "recoupe" if pause["relation"] == "recoupe" else "est contiguë à"
        sentences["pause"] = (f"Elle {verb} une pause de la référence de {_num(sortie.SHORT_PAUSE_S, 0)}\u202fs au plus "
                              f"({_num(pause['duree_s'], 2)}\u202fs).")
    if context.get("frontiere_s") is not None:
        sentences["frontiere"] = (f"Un de ses bords est à {_num(sortie.BOUNDARY_S, 2)}\u202fs au plus d'une frontière de "
                                  f"tour de la référence (écart {_num(context['frontiere_s'], 2)}\u202fs).")
    return sentences


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
    """RTTM, JSON (avec la fiche de reproductibilité, R-D5) et étiquettes Audacity (R-U11)
    d'un moteur."""
    names = result.get("names", {})
    data = sortie.to_json(result["annotation"], result["uri"], result["duree_s"], result["moteur"],
                          result["configuration"], result["calcul_s"], names)
    labels = sortie.speaker_labels(result["annotation"])
    resolved = sortie.resolve_names(labels, names)
    data["etiquettes_audacity"] = {code: {"id": label, "nom": resolved[label]}
                                   for label, code in sortie.audacity_codes(result["annotation"]).items()}
    data["reproductibilite"] = reproductibilite.sheet(result)
    rttm = sortie.to_rttm(result["annotation"], result["uri"], names)
    paths = sortie.write_exports(result["dir"] / "exports", stem, rttm, json.dumps(data, ensure_ascii=False, indent=2),
                                 {"_audacity.txt": sortie.to_audacity(result["annotation"])})
    return [str(path) for path in paths]


def _timeline_svg(result: dict) -> str:
    """Image de la timeline (R-U11) : tous ses groupes, comme dans l'onglet Analyse."""
    title = f"{result['uri']} : qui parle, et quand"
    return image.timeline_svg(_viewer_value(result)["groupes"], result["duree_s"], title)


def _exports(result: dict) -> list[str]:
    """Exports du résultat ; en comparaison, ceux des deux moteurs, suffixés par moteur ;
    puis l'image de la timeline, une seule pour tous ses groupes."""
    stem = sortie.rttm_name(result["uri"])
    other = result.get("comparaison")
    if not other:
        paths = _export_one(result, stem)
    else:
        paths = (_export_one(result, f"{stem}_{result['moteur_cle']}")
                 + _export_one(other, f"{stem}_{other['moteur_cle']}"))
    picture = result["dir"] / "exports" / f"{stem}_timeline.svg"
    picture.write_text(_timeline_svg(result), encoding="utf-8")
    return paths + [str(picture)]


EXPORT_KINDS = {".rttm": "RTTM", ".json": "JSON, fiche de reproductibilité", ".txt": "Étiquettes Audacity",
                ".svg": "Image SVG de la timeline"}


def _exports_html(result: dict) -> str:
    """Liste des exports (V11) : lien de téléchargement, nature et taille en français, au lieu
    du composant de fichiers de Gradio (tailles à l'anglaise, « 7.2 KB »)."""
    items = []
    for path in map(Path, _exports(result)):
        kind = EXPORT_KINDS.get(path.suffix, path.suffix.lstrip(".").upper())
        items.append(f'<li><a class="ws-file" href="{_file_url(path)}" download="{escape(path.name, quote=True)}">'
                     f'<span class="ws-file-name">{escape(path.name)}</span>'
                     f'<span class="ws-file-meta">{escape(kind)} · {formatage.taille(path.stat().st_size)}</span></a></li>')
    return f'<ul class="ws-files">{"".join(items)}</ul>'


def _image_html(result: dict | None) -> str:
    """Bouton « Image PNG de la timeline » : le navigateur tire le PNG du SVG (canevas),
    sans dépendance (IMAGE_JS)."""
    if result is None:
        return ""
    name = f"{sortie.rttm_name(result['uri'])}_timeline.png"
    return (f'<div class="ws-image-export"><button type="button" class="ws-btn ws-png" data-name="{escape(name, quote=True)}" '
            f'data-svg="{escape(_timeline_svg(result), quote=True)}">Image PNG de la timeline</button>'
            '<span class="ws-png-status" role="status"></span></div>'
            + _how_to_read('<p class="ws-caption">Image en mode clair, toute la durée sur une seule échelle. Le SVG est '
                           'dans la liste ci-dessus ; le PNG (deux fois plus fin) est tiré de ce SVG par le navigateur.</p>',
                           "À propos de l'image"))


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
                    f'<td class="num">{_num(item["calcul_s"], 2)}\u202fs</td><td class="num">{_num(rtf, 4)}</td></tr>')
    if reference is not None:
        rows.append(f'<tr><td>Référence</td><td class="num">{len(reference.labels())}</td>'
                    '<td class="num">—</td><td class="num">—</td><td class="num">—</td><td class="num">—</td></tr>')
    note = ("" if reference is not None
            else '<p class="ws-caption">Déposez une référence RTTM pour comparer les DER.</p>')
    return ('<div class="ws-table-wrap"><table class="ws-table"><thead><tr><th scope="col">Moteur</th>'
            '<th scope="col" class="num">Locuteurs</th><th scope="col" class="num">DER sans collar</th>'
            '<th scope="col" class="num">DER collar 0,25\u202fs</th><th scope="col" class="num">Temps de calcul</th>'
            f'<th scope="col" class="num">RTF</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            f'{note}<p class="ws-caption">DER sur toute la durée du fichier, sans UEM : non comparable aux '
            'résultats sur corpus. Temps de calcul sans le chargement du modèle.</p>')


def _cache_date(iso: str) -> str:
    """« 01/11/2026 à 21:04 » pour la date ISO d'une entrée du cache."""
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y à %H:%M")
    except (TypeError, ValueError):
        return str(iso)


def _cache_badges(results: list[dict]) -> list[str]:
    """Pastilles des résultats réaffichés depuis le cache, avec la date du calcul d'origine ;
    préfixées par le moteur en comparaison."""
    several = len(results) > 1
    return [(f"{item['libelle']} : r" if several else "R")
            + f"ésultat réaffiché depuis le cache, calculé le {_cache_date(item['cache'])}"
            for item in results if item.get("cache")]


def _times_html(result: dict | None) -> str:
    if result is None:
        return _empty("Les durées de chaque étape s'afficheront après l'analyse.")
    rows = [("Normalisation audio (ffmpeg)", f"{_num(result['normalisation_s'], 2)}\u202fs")]
    if result.get("cache"):
        loading = "aucun (cache)"
    else:
        loading = "déjà chargé" if result["chargement_s"] is None else f"{_num(result['chargement_s'], 2)}\u202fs"
    rows.append(("Chargement du modèle", loading))
    spec = moteurs.SPECS.get(result.get("moteur_cle", ""))
    rows += [(spec.step_label(step, STEP_LABELS.get(step, step)) if spec else STEP_LABELS.get(step, step),
              f"{_num(seconds, 2)}\u202fs") for step, seconds in result["durees_etapes"].items()]
    body = "".join(f'<tr><td>{escape(label)}</td><td class="num">{value}</td></tr>' for label, value in rows)
    body += f'<tr><td class="strong">Calcul total</td><td class="num strong">{_num(result["calcul_s"], 2)}\u202fs</td></tr>'
    rtf = result["calcul_s"] / result["duree_s"] if result["duree_s"] else 0.0
    measured = result["rtf_mesure"]
    caption = (f"Audio de {temps.format_duration(result['duree_s'])} sur <code>{escape(result['device'])}</code> : "
               f"RTF obtenu {_num(rtf, 4)}"
               + (f", RTF mesuré {_num(measured['rtf'], 4)} ({escape(measured['source'])})" if measured else "")
               + ". Le chargement du modèle n'entre pas dans le RTF.")
    callout = ""
    if result.get("cache"):
        callout += ('<div class="ws-callout">Résultat réaffiché depuis le cache, sans calcul : durées de '
                    f'l\'analyse d\'origine, du {_cache_date(result["cache"])}.</div>')
    if result["factice"]:
        ignored = result["configuration"]["nombre_locuteurs"]["mode"] != "automatique"
        callout += ('<div class="ws-callout">Moteur factice : aucune inférence. Segments repris de '
                   f'<code>{escape(result["rttm_source"] or "")}</code>, temps de calcul simulé'
                   + (", contrainte sur le nombre de locuteurs ignorée." if ignored else ".") + "</div>")
    return (f'{callout}<div class="ws-table-wrap"><table class="ws-table"><thead><tr><th scope="col">Étape</th>'
            f'<th scope="col" class="num">Durée</th></tr></thead><tbody>{body}</tbody></table></div>'
            f'<p class="ws-caption">{caption}</p>')


def _der_html(result: dict | None, reference_path: str | None) -> str:
    if not reference_path:
        return _empty("Déposez une référence RTTM dans les réglages pour afficher le DER décomposé.")
    try:
        reference = sortie.read_reference(reference_path)
        if result is None:
            return _empty("Référence chargée : le DER s'affichera après l'analyse.")
        report = sortie.der_report(reference, result["annotation"], result["duree_s"])
    except ValueError as error:
        return f'<div class="ws-callout ws-alert" role="alert">Référence inutilisable : {escape(_french(str(error)))}</div>'
    except OSError:
        return ('<div class="ws-callout ws-alert" role="alert">Référence illisible : le fichier déposé n\'est plus '
                'disponible. Déposez-le de nouveau.</div>')
    rows = []
    for name, title in (("collar_0", "Sans collar (principale)"), ("collar_0_25", "Collar ± 0,25\u202fs")):
        r = report[name]
        rows.append(
            f'<tr><td>{title}</td><td class="num strong">{_pct(r["der"], 2)}</td>'
            f'<td class="num">{_pct(r["manquee"], 2)}</td><td class="num">{_pct(r["fausse_alarme"], 2)}</td>'
            f'<td class="num">{_pct(r["confusion"], 2)}</td><td class="num">{_pct(r["jer"], 2)}</td></tr>'
        )
    zone = {key: None if value is None else value["der"] for key, value in report["zones"].items()}
    counts = report["n_locuteurs"]
    return (
        f'<p class="ws-scope">{DER_SCOPE}</p>{_reference_warnings_html(reference, result)}'
        f'{_merge_der_html(result, reference, reference_path, report)}'
        '<div class="ws-table-wrap"><table class="ws-table"><thead><tr><th scope="col">Condition</th><th scope="col" class="num">DER</th>'
        '<th scope="col" class="num">Parole manquée</th><th scope="col" class="num">Fausse alarme</th>'
        '<th scope="col" class="num">Confusion</th><th scope="col" class="num">JER</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
        f'<p class="ws-caption">DER sans collar par zone : {_zone_text(zone)}. {counts["hypothese"]} locuteurs '
        f'estimés pour {counts["reference"]} dans la référence.</p>'
        + _how_to_read('<p class="ws-caption">Référence coupée à la durée de l\'audio, chevauchements comptés, '
                       'deux conditions de collar (protocole §3.1). Parole manquée, fausse alarme et confusion '
                       'en part de la parole de référence ; JER : erreur moyenne par locuteur.</p>')
        + _matching_html(sortie.matching_report(reference, result["annotation"], result["duree_s"]),
                         result.get("names", {}))
    )


def _zone_text(zone: dict) -> str:
    """DER par zone, en phrase (V10) : une zone vide est nommée, pas remplacée par un tiret."""
    if zone["chevauchement"] is None:
        return f"{_pct(zone['sans_chevauchement'], 2)} ; pas de chevauchement dans la référence"
    if zone["sans_chevauchement"] is None:
        return f"{_pct(zone['chevauchement'], 2)} ; toute la parole de la référence est en chevauchement"
    return f"{_pct(zone['sans_chevauchement'], 2)} hors chevauchement, {_pct(zone['chevauchement'], 2)} en chevauchement"


def _reference_warnings_html(reference, result: dict) -> str:
    """Avertissements sur une référence peut-être mal assortie à l'audio (B7)."""
    warnings = sortie.reference_warnings(reference, result["annotation"], result.get("uri"), result["duree_s"])
    return "".join(f'<div class="ws-callout ws-alert" role="status">À vérifier : {escape(_french(text[0].lower() + text[1:]))}</div>'
                   for text in warnings)


def _merge_der_html(result: dict, reference, reference_path: str, after: dict) -> str:
    """DER avant → après les fusions de locuteurs (R-U9) ; vide sans fusion. `after` : DER
    du résultat fusionné, déjà calculé. Le DER d'avant, celui de l'annotation du moteur, ne
    change pas tant que la référence est la même : il est gardé dans le résultat."""
    if not result.get("fusions") or result.get("annotation_origine") is None:
        return ""
    kept = result.get("der_avant")
    if kept and kept["reference"] == reference_path:
        before = kept["rapport"]
    else:
        before = sortie.der_report(reference, result["annotation_origine"], result["duree_s"])
        result["der_avant"] = {"reference": reference_path, "rapport": before}
    n = len(result["fusions"])
    parts = [f'{label} {_pct(before[name]["der"], 2)} → <span class="strong">{_pct(after[name]["der"], 2)}</span>'
             for name, label in (("collar_0", "sans collar"), ("collar_0_25", "collar ± 0,25\u202fs"))]
    delta = after["collar_0"]["der"] - before["collar_0"]["der"]
    trend = "baisse" if delta < 0 else ("hausse" if delta > 0 else "inchangé")
    return (f'<div class="ws-callout ws-merge-der" role="status">Après {n} fusion{"s" if n > 1 else ""} : DER '
            f'{parts[0]} ({trend}{"" if delta == 0 else " de " + _num(abs(delta), 2) + " point" + ("s" if abs(delta) >= 2 else "")})'
            f' ; {parts[1]}. Le tableau ci-dessous est celui d\'après les fusions.</div>')


def _matching_html(rows: list[dict], names: dict) -> str:
    """Tableau d'appariement (R-U4) : locuteur de référence, locuteur trouvé apparié,
    temps commun, couverture et pureté par locuteur (pyannote.metrics)."""
    hyp_names = sortie.resolve_names(sorted({r["hypothese"] for r in rows if r["hypothese"] is not None}), names)
    body = []
    for row in rows:
        ref = escape(str(row["reference"])) if row["reference"] is not None else '<span class="sub">aucun</span>'
        found = (escape(hyp_names[row["hypothese"]]) if row["hypothese"] is not None
                 else '<span class="sub">non apparié</span>')
        common = f"{_num(row['commun_s'], 1)}\u202fs" if row["reference"] is not None and row["hypothese"] is not None else "—"
        coverage = "—" if row["couverture"] is None else _pct(100 * row["couverture"])
        purity = "—" if row["purete"] is None else _pct(100 * row["purete"])
        body.append(f'<tr><td>{ref}</td><td>{found}</td><td class="num">{common}</td>'
                    f'<td class="num">{coverage}</td><td class="num">{purity}</td></tr>')
    return (
        '<h3 class="ws-subtitle">Appariement des locuteurs</h3>'
        '<div class="ws-table-wrap"><table class="ws-table ws-matching"><thead><tr><th scope="col">Référence</th>'
        '<th scope="col">Locuteur trouvé</th><th scope="col" class="num">Temps commun</th>'
        '<th scope="col" class="num">Couverture</th><th scope="col" class="num">Pureté</th></tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div>'
        + _how_to_read('<p class="ws-caption">Appariement optimal utilisé par le DER (pyannote.metrics), sans collar, '
        'chevauchements comptés ; c\'est lui qui colore les pistes de la référence. Couverture : part de la parole '
        'du locuteur de référence couverte par le locuteur trouvé qui en couvre le plus. Pureté : part de la '
        'parole du locuteur trouvé attribuable au locuteur de référence qui y domine.</p>')
    )


# Tableau des locuteurs : renommage dans le tableau (R-U6). Un nom validé (Entrée ou
# sortie du champ) envoie tous les noms au serveur ; Échap rétablit le nom affiché.
# Fusion (R-U9) : le choix d'un locuteur dans « Fusionner avec… » envoie la fusion ; le
# bouton d'annulation retire la dernière.
STATS_JS = """
const send = () => {
  const names = {};
  element.querySelectorAll('.ws-name-input').forEach((input) => { names[input.dataset.id] = input.value; });
  trigger('input', { names });
};
element.addEventListener('change', (event) => {
  if (event.target.matches('.ws-name-input')) send();
  else if (event.target.matches('.ws-merge') && event.target.value) {
    const merge = { source: event.target.dataset.id, target: event.target.value };
    // La liste revient à « Fusionner avec… » : le tableau redessiné peut réutiliser ce nœud.
    event.target.value = '';
    trigger('input', { merge });
  }
});
element.addEventListener('click', (event) => {
  if (event.target.closest('.ws-merge-undo')) trigger('input', { undo: true });
});
element.addEventListener('keydown', (event) => {
  if (!event.target.matches('.ws-name-input')) return;
  if (event.key === 'Enter') event.target.blur();
  else if (event.key === 'Escape') { event.target.value = event.target.defaultValue; event.target.blur(); }
});
"""

# Image PNG de la timeline (R-U11) : le SVG du serveur est dessiné dans un canevas, deux
# fois plus fin, puis enregistré ; aucune bibliothèque.
IMAGE_JS = """
element.addEventListener('click', (event) => {
  const button = event.target.closest('.ws-png');
  if (!button) return;
  const status = element.querySelector('.ws-png-status');
  const say = (text) => { if (status) status.textContent = text; };
  const source = URL.createObjectURL(new Blob([button.dataset.svg], { type: 'image/svg+xml;charset=utf-8' }));
  const picture = new Image();
  picture.onload = () => {
    const scale = 2;
    const canvas = document.createElement('canvas');
    canvas.width = picture.naturalWidth * scale;
    canvas.height = picture.naturalHeight * scale;
    const context = canvas.getContext('2d');
    context.scale(scale, scale);
    context.drawImage(picture, 0, 0);
    URL.revokeObjectURL(source);
    canvas.toBlob((png) => {
      if (!png) { say('Image PNG impossible dans ce navigateur : utilisez le SVG.'); return; }
      const link = document.createElement('a');
      link.href = URL.createObjectURL(png);
      link.download = button.dataset.name;
      element._lastPng = { size: png.size, width: canvas.width, height: canvas.height };
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(link.href), 10000);
      say(`Image enregistrée : ${button.dataset.name} (${canvas.width} × ${canvas.height} px).`);
    }, 'image/png');
  };
  picture.onerror = () => { URL.revokeObjectURL(source); say('Image PNG impossible : utilisez le SVG.'); };
  picture.src = source;
});
"""

# Onglet Avancement : un clic sur « notes.md » demande au serveur le contenu des notes.
NOTES_JS = """
element.addEventListener('click', (event) => {
  // Frise sous 840 px : « Afficher les N autres » déplie les expériences plus anciennes.
  const more = event.target.closest('.av-more');
  if (more) {
    const open = more.getAttribute('aria-expanded') !== 'true';
    more.setAttribute('aria-expanded', String(open));
    more.textContent = open ? more.dataset.less : more.dataset.more;
    element.querySelector('.av-frise').classList.toggle('av-all', open);
    return;
  }
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


def _engines_badge(status: WarmupStatus) -> str:
    """Indicateur « moteurs prêts » (R-D2) : état écrit en toutes lettres, pas seulement dessiné."""
    if not status.enabled:
        return ('<span class="ws-badge ws-engines" data-state="off">Préchauffage désactivé : '
                'moteurs chargés au premier usage</span>')
    if not status.finished:
        current = f" : {escape(status.current)}" if status.current else ""
        return (f'<span class="ws-badge ws-engines" data-state="run" role="status">Préchauffage des moteurs '
                f'({status.done}/{status.total}){current}…</span>')
    if status.failures:
        names = ", ".join(escape(name) for name in status.failures)
        detail = escape(" ; ".join(f"{name} : {reason}" for name, reason in status.failures.items()))
        return (f'<span class="ws-badge ws-engines" data-state="warn" role="status" title="{detail}">'
                f'Moteurs prêts, sauf {names} (chargé au premier usage)</span>')
    return '<span class="ws-badge ws-engines" data-state="ready" role="status">Moteurs prêts</span>'


def _speakers_text(speakers: dict) -> str:
    """Nombre de locuteurs d'une configuration consignée, en toutes lettres."""
    return {"automatique": "nombre de locuteurs automatique",
            "impose": f"{speakers.get('valeur')} locuteurs imposés",
            "fourchette": f"entre {speakers.get('min')} et {speakers.get('max')} locuteurs"}[speakers["mode"]]


def _config_html(demo: moteurs.DemoConfig, engine_key: str) -> str:
    """Configuration en vigueur (D17, amendement 1) et moteur choisi, sous le titre."""
    if demo.frozen:
        when = ""
        if demo.frozen_on:
            try:
                when = f", gel du {date.fromisoformat(demo.frozen_on).strftime('%d/%m/%Y')}"
            except ValueError:
                when = f", gel du {demo.frozen_on}"
        config = f'<code>{escape(demo.source)}</code>{escape(when)}'
    else:
        config = "correspondance de <code>app/moteurs.py</code>, avant le gel"
    spec = demo.specs.get(engine_key) or demo.specs[demo.default_engine]
    speakers = demo.speakers[spec.key]
    default = "" if speakers["mode"] == "automatique" else f", {escape(_speakers_text(speakers))} par défaut"
    excluded = ", ".join(moteurs.SPECS[key].label for key in demo.excluded)
    excluded = f' <span class="ws-excluded">Non retenu pour la démonstration : {escape(excluded)}</span>' if excluded else ""
    return (f'<p class="ws-config"><span>Configuration : {config}</span> <span>Moteur : '
            f'<span class="strong">{escape(spec.label)}</span> ({escape(spec.source_exp)}){default}</span>'
            f'{excluded}</p>')


# Comparaison proposée par défaut : Nemotron 3 contre pyannote (D29 : l'autre moteur reste
# proposé pour la comparaison, quel que soit le moteur de démonstration).
COMPARISON_PAIR = ("nemotron-3", "pyannote-community-1")


def _second_engine(specs: dict, default: str) -> str:
    """Second moteur proposé en comparaison : l'autre moteur de la paire Nemotron 3 –
    pyannote si les deux sont retenus et que le moteur par défaut en est un ; sinon la
    baseline ECAPA, sinon le premier autre moteur retenu (le moteur par défaut s'il est seul)."""
    if default in COMPARISON_PAIR and all(key in specs for key in COMPARISON_PAIR):
        return next(key for key in COMPARISON_PAIR if key != default)
    if "baseline-ecapa" in specs and default != "baseline-ecapa":
        return "baseline-ecapa"
    return next((key for key in specs if key != default), default)


def _auto_only_note(spec: moteurs.EngineSpec, mode: str) -> str | None:
    """Message quand un moteur qui estime seul le nombre de locuteurs reçoit « Imposé » ou
    « Fourchette » ; None sinon."""
    if not spec.auto_only or mode == "Automatique":
        return None
    return (f"{spec.label} estime seul le nombre de locuteurs ({spec.max_speakers} au plus) : "
            f"« {mode} » ne s'applique pas à lui, il analyse en automatique.")


THEMES = (("clair", "Clair"), ("sombre", "Sombre"), ("systeme", "Système"))


def _header_html(fake: bool, status: WarmupStatus | None = None, demo: moteurs.DemoConfig | None = None,
                 engine_key: str | None = None, presentation: bool = False) -> str:
    demo = demo or moteurs.demo_config()
    badges = _engines_badge(status or WarmupStatus())
    if fake:
        badges += '<span class="ws-badge">Moteur factice : aucune inférence</span>'
    # Mode présentation (B8) : l'état vit dans la classe de <html> (presentation.js), qui
    # resynchronise aria-pressed quand Gradio redessine l'en-tête.
    badges += ('<button type="button" class="ws-btn ws-switch ws-present" '
               f'aria-pressed="{"true" if presentation else "false"}" '
               'title="Texte et commandes agrandis, contrastes renforcés, réglages secondaires masqués">'
               '<span class="ws-switch-track" aria-hidden="true"></span>Mode présentation</button>')
    # Thème (B14) : à la place du bouton « Settings » de Gradio ; état posé par theme.js.
    badges += ('<div class="ws-segmented ws-theme" role="group" aria-label="Thème">'
               + "".join(f'<button type="button" data-theme="{key}" aria-pressed="false">{label}</button>'
                         for key, label in THEMES) + "</div>")
    # Configuration et moteur en vigueur : panneau « Détails » à part (V6, `_details_html`),
    # que le redessin de l'en-tête pendant le préchauffage ne referme pas.
    return ('<header class="ws-header"><div><h1>Who Spoke?</h1>'
            "<p class=\"ws-tagline\">Qui parle, et quand. L'analyse tourne sur cette machine : "
            "l'audio ne la quitte pas.</p>"
            f'</div><div class="ws-badges">{badges}</div></header>')


# Panneau « Détails » : redessiné au changement de moteur, il garde l'état ouvert ou fermé
# que la personne lui a donné (retour du cockpit sur B11).
DETAILS_JS = """
element.addEventListener('toggle', (event) => {
  if (event.target.matches('details.ws-details')) element._open = event.target.open;
}, true);
watch('value', () => setTimeout(() => {
  const panel = element.querySelector('details.ws-details');
  if (panel && element._open) panel.open = true;
}));
"""


def _details_html(demo: moteurs.DemoConfig, engine_key: str | None = None) -> str:
    """Panneau « Détails », replié : configuration de démonstration et moteur en vigueur (V6) ;
    masqué en mode présentation."""
    return ('<details class="ws-details"><summary>Détails : configuration et moteur</summary>'
            f'{_config_html(demo, engine_key or demo.default_engine)}</details>')


def _shown_path(path: Path) -> str:
    """Chemin affiché, avec ~ pour le dossier personnel."""
    home = Path.home()
    return f"~/{path.relative_to(home)}" if path.is_relative_to(home) else str(path)


def _cache_info_html(store: ResultCache) -> str:
    count, size = store.stats()
    amount = "aucun résultat" if not count else f"{count} résultat{'s' if count > 1 else ''}, {formatage.taille(size)}"
    # Classe ws-cache-info : masquée dans les captures de référence (le compte change).
    return (f'<p class="ws-caption ws-cache-info">Cache : {amount}, dans <code>{escape(_shown_path(store.directory))}</code>. '
            "Ni audio ni nom de fichier : segments, durées et réglages seulement.</p>")


def _band_html(prepared: dict, results: list[dict]) -> str:
    """Bandeau des réglages repliés (R-U1) : fichier, durée, moteurs et réglages de l'analyse."""
    engines = " puis ".join(escape(item["libelle"]) for item in results)
    counts = [_speakers_text(item["configuration"]["nombre_locuteurs"]) for item in results]
    # Comparaison où les moteurs n'ont pas le même réglage (fourchette du premier seulement) :
    # celui de chaque moteur.
    count = counts[0] if len(set(counts)) == 1 else " ; ".join(
        f'{item["libelle"]} : {text}' for item, text in zip(results, counts))
    devices = ", ".join(dict.fromkeys(item["device"] for item in results))
    return (f'<p class="ws-band-text"><span class="strong">{escape(prepared["nom"])}</span>'
            f'<span>{temps.format_duration(prepared["duree_s"])}</span><span>{engines}</span>'
            f'<span>{escape(count)}</span><span>{escape(devices)}</span></p>')


VIEWER_TEMPLATE = (
    '<div class="wsp-root wsp-empty">'
    '<p class="wsp-placeholder">Déposez un fichier audio puis lancez l\'analyse : '
    'la forme d\'onde et une piste par locuteur s\'afficheront ici.</p>'
    # Barre d'outils en groupes qui reviennent à la ligne d'un bloc (V5) : lecture ; vue ; zoom ;
    # aide à droite. Sur petit écran, le zoom (et « Énergie et seuil ») se replient derrière la
    # loupe, et les libellés longs laissent la place aux courts (le nom accessible reste long).
    '<div class="wsp-body"><div class="wsp-toolbar">'
    '<div class="wsp-group wsp-g-play" role="group" aria-label="Lecture">'
    f'<button type="button" class="ws-btn wsp-play">{icon("lecture")}{icon("pause")}'
    '<span class="wsp-play-text">Lecture</span></button>'
    '<span class="wsp-time" aria-live="off"></span>'
    '<span class="wsp-speaking" hidden></span>'
    '<span class="wsp-iso" role="status" hidden></span></div>'
    '<div class="wsp-group wsp-g-view" role="group" aria-label="Vue">'
    '<div class="ws-segmented wsp-view" role="group" aria-label="Vue de l\'audio (D28)">'
    '<button type="button" class="wsp-view-wave" aria-pressed="true"><span class="wsp-long">Forme d\'onde</span>'
    '<span class="wsp-short" aria-hidden="true">Onde</span></button>'
    '<button type="button" class="wsp-view-spec" aria-pressed="false"><span class="wsp-long">Spectrogramme</span>'
    '<span class="wsp-short" aria-hidden="true">Spectre</span></button></div>'
    '<button type="button" class="ws-btn ws-switch wsp-follow" aria-pressed="true">'
    '<span class="ws-switch-track" aria-hidden="true"></span><span class="wsp-long">Suivre la lecture</span>'
    '<span class="wsp-short" aria-hidden="true">Suivre</span></button>'
    '<button type="button" class="ws-btn ws-switch wsp-energy-toggle" aria-pressed="false" hidden>'
    '<span class="ws-switch-track" aria-hidden="true"></span>Énergie et seuil</button></div>'
    '<div class="wsp-group wsp-g-zoom wsp-zoom" id="wsp-zoom" role="group" aria-label="Zoom de la timeline">'
    f'<button type="button" class="ws-btn ws-btn-icon wsp-zoom-out" aria-label="Dézoomer">{icon("moins")}</button>'
    '<input type="range" class="wsp-zoom-range" min="0" max="100" step="1" value="0" '
    'aria-label="Niveau de zoom">'
    f'<button type="button" class="ws-btn ws-btn-icon wsp-zoom-in" aria-label="Zoomer">{icon("plus")}</button>'
    '<button type="button" class="ws-btn wsp-zoom-fit">Tout afficher</button></div>'
    '<div class="wsp-group wsp-g-help">'
    '<button type="button" class="ws-btn ws-btn-icon wsp-zoom-toggle" aria-expanded="false" aria-controls="wsp-zoom" '
    f'aria-label="Zoom et options d\'affichage" title="Zoom et options d\'affichage">{icon("loupe")}</button>'
    '<button type="button" class="ws-btn ws-btn-icon wsp-help-toggle" aria-expanded="false" aria-controls="wsp-help" '
    'aria-label="Raccourcis clavier" title="Raccourcis clavier (?)">?</button></div></div>'
    '<div class="wsp-help" id="wsp-help" role="region" aria-label="Raccourcis clavier" hidden>'
    '<dl><dt><kbd>Espace</kbd></dt><dd>Lecture ou pause</dd>'
    '<dt><kbd>←</kbd> <kbd>→</kbd></dt><dd>Tour de parole précédent ou suivant (du locuteur isolé, s\'il y en a un)</dd>'
    '<dt><kbd>1</kbd> à <kbd>9</kbd></dt><dd>Isoler un locuteur du premier moteur (ou cliquer sur son nom) :</dd>'
    '<dt></dt><dd><ol class="wsp-help-speakers"></ol></dd>'
    '<dt><kbd>0</kbd></dt><dd>Tous les locuteurs</dd>'
    '<dt><kbd>?</kbd></dt><dd>Afficher ou masquer cette aide (<kbd>Échap</kbd> la ferme)</dd></dl>'
    '<p>Inactifs pendant la saisie dans un champ (nom d\'un locuteur, réglages). Vue d\'ensemble : '
    'glisser la fenêtre pour déplacer la vue, ou cliquer ailleurs pour y amener la lecture.</p></div>'
    '<div class="wsp-overview"><span class="wsp-overview-label">Vue d\'ensemble</span>'
    '<div class="wsp-minimap"></div></div>'
    '<div class="wsp-wavebox"><div class="wsp-spec-axis" aria-hidden="true"></div>'
    '<canvas class="wsp-spec-canvas" role="img"></canvas><div class="wsp-wave"></div></div>'
    '<p class="wsp-spec-legend" hidden><span class="wsp-spec-swatch" aria-hidden="true"></span>'
    '<span class="wsp-spec-text"></span></p>'
    '<div class="wsp-energy" hidden><div class="wsp-energy-label"><span class="wsp-energy-title">Énergie (dB)</span>'
    '<span class="wsp-energy-sub"></span></div><div class="wsp-energy-plot">'
    '<canvas class="wsp-energy-canvas" role="img"></canvas><span class="wsp-energy-tip" hidden></span></div></div>'
    '<p class="wsp-energy-legend" hidden></p>'
    '<div class="wsp-rows"><div class="wsp-labels"></div>'
    '<div class="wsp-viewport"><div class="wsp-canvas"><div class="wsp-lanes"></div>'
    '<div class="wsp-axis" aria-hidden="true"></div><div class="wsp-playhead"></div></div></div></div>'
    '<p class="wsp-errsum" hidden></p>'
    '<section class="wsp-explain" id="wsp-explain" aria-live="polite" aria-label="Expliquer cette erreur" hidden>'
    '<div class="wsp-explain-head"><h3 class="wsp-explain-title"></h3>'
    f'<button type="button" class="ws-btn ws-btn-icon wsp-explain-close" aria-label="Fermer l\'explication">'
    f'{icon("fermer")}</button></div>'
    '<p class="wsp-explain-cat"><span class="wsp-explain-cat-label">Catégorie principale</span> '
    '<strong class="wsp-explain-cat-name"></strong><span class="wsp-explain-cat-text"></span> '
    '<span class="wsp-explain-cat-tol"></span></p>'
    '<dl class="wsp-explain-facts"></dl><p class="wsp-explain-sub">Autres constats dans la référence</p>'
    '<ul class="wsp-explain-context"></ul>'
    '<p class="wsp-explain-note">Catégorie et constats décrivent la référence et l\'appariement autour de la zone, '
    'pas une cause établie.</p></section>'
    '<p class="wsp-hint">Cliquez sur un segment pour l\'écouter et le repérer sur la forme d\'onde, sur une zone d\'erreur pour l\'expliquer. Zoom : curseur, boutons, ou Ctrl + molette ; '
    'défilement : vue d\'ensemble, pavé tactile ou Maj + molette. Raccourcis : <kbd>Espace</kbd>, <kbd>←</kbd> <kbd>→</kbd>, '
    '<kbd>1</kbd> à <kbd>9</kbd>, <kbd>0</kbd>, <kbd>?</kbd> pour l\'aide.</p></div></div>'
)

ENGINE_INFO_DEVICE = "auto : CUDA, puis MPS, puis CPU (D15)."
# Périphérique imposé, et pourquoi (clé None : baseline).
CPU_ONLY_INFO = {None: "CPU seul pour ce moteur (D19, D22).",
                 "nemotron-3": "CPU seul pour ce moteur (en MPS, exception Metal ; EXP-0027)."}


# --- Application ----------------------------------------------------------------------


# Rendus dont la sortie passe par le glossaire (D26, I3) dans build_app.
LINKED_RENDERERS = ("_title", "_status_html", "_stats_html", "_times_html", "_der_html")


def _linked(linker: glossaire.Linker) -> tuple:
    """Versions des rendus de LINKED_RENDERERS dont les termes renvoient au glossaire."""
    def wrap(render):
        return lambda *args, **kwargs: linker.link(render(*args, **kwargs))
    return tuple(wrap(globals()[name]) for name in LINKED_RENDERERS)


def build_app(fake: bool = False, fake_max_s: float = 20.0, repo_root: Path = REPO_ROOT,
              warm_up: bool = False, cache_dir: Path | None = None, fake_rttm: Path | None = None,
              demo: moteurs.DemoConfig | None = None, presentation: bool = False) -> gr.Blocks:
    """Application ; expériences, résultats, catalogue et documents lus sous `repo_root` (lecture seule).

    `warm_up` : préchauffage des moteurs disponibles dans un fil dédié (R-D2) ; `cache_dir` :
    dossier du cache des résultats (`app.cache.default_dir()` par défaut, R-D3) ; `fake_rttm` :
    sorties fabriquées du moteur factice (cas limites, B7) ; `demo` : configuration de
    démonstration (`moteurs.demo_config(repo_root)` par défaut : configs/demo.yaml s'il
    existe) ; `presentation` : mode présentation à l'ouverture (B8, la page le pose aussi)."""
    demo = demo or moteurs.demo_config(repo_root)
    specs = demo.specs
    glossary = glossaire.read_glossary(repo_root / glossaire.GLOSSARY_RELATIVE)
    linker = glossaire.Linker(glossary)
    _title, _status_html, _stats_html, _times_html, _der_html = _linked(linker)

    def _times_all(result):
        return _times_all_html(_times_html, result)

    def _der_all(result, reference_path):
        return _der_all_html(_der_html, result, reference_path)
    experiments = repo_root / "experiments"
    leaderboard = repo_root / "results" / "leaderboard.csv"
    engines = EngineCache(fake, fake_max_s, experiments, fake_rttm if fake else None)
    store = ResultCache(cache_dir)
    code = code_version(REPO_ROOT)   # consigné dans le cache, hors de la clé
    engine_code = engine_code_fingerprint(REPO_ROOT)   # dans la clé du cache
    availability = _availability(fake, experiments, specs)
    choices = [
        (spec.label + ("" if availability[key] is None else " (indisponible)"), key)
        for key, spec in specs.items()
    ]
    head = "".join(f'<script src="{_file_url(WAVESURFER_DIR / name)}"></script>'
                   for name in ("wavesurfer.min.js", "regions.min.js", "minimap.min.js"))

    if warm_up:
        # Moteur proposé par défaut en premier, sur le périphérique de « auto ».
        default_device = select_device("auto").type
        targets = sorted(((spec, "cpu" if spec.cpu_only else default_device)
                          for key, spec in specs.items() if availability[key] is None),
                         key=lambda target: target[0].key != demo.default_engine)
        engines.warmup.enabled, engines.warmup.total = True, len(targets)
        threading.Thread(target=engines.warm_up, args=(targets,), daemon=True, name="prechauffage").start()

    def pipeline_page(key: str) -> str:
        try:
            return linker.link(pipeline.render(pipeline.load_page(specs[key], repo_root)))
        except (OSError, ValueError, KeyError, moteurs.EngineUnavailable) as error:
            return _empty(f"Page indisponible : {error}")

    def progress_sections() -> dict[str, str]:
        return {name: linker.link(html) for name, html in avancement.render(repo_root).items()}

    def engine_info(key: str) -> str:
        spec = specs[key]
        reason = availability[key]
        return f"Indisponible : {reason}" if reason else f"Configuration reprise de {spec.source_exp}."

    def speaker_modes(key: str) -> list[str]:
        # Moteur à nombre estimé seulement : les trois choix restent, l'interface dit qu'Imposé
        # et Fourchette ne s'appliquent pas à lui (ils valent pour le second moteur en comparaison).
        return list(SPEAKER_MODES if specs[key].supports_range or specs[key].auto_only else SPEAKER_MODES[:2])

    def mode_info(key: str, mode: str) -> str | None:
        return _auto_only_note(specs[key], mode)

    def engine_changed(key: str):
        # Nombre de locuteurs : celui que la configuration en vigueur donne pour ce moteur.
        spec = specs[key]
        speakers = demo.speakers[key]
        device = (gr.update(value="cpu", interactive=False, info=CPU_ONLY_INFO.get(key, CPU_ONLY_INFO[None]))
                  if spec.cpu_only else gr.update(interactive=True, info=ENGINE_INFO_DEVICE))
        fixed = speakers["mode"] == "impose"
        span = speakers["mode"] == "fourchette"
        return (gr.update(info=engine_info(key)),
                gr.update(choices=speaker_modes(key), value=MODE_LABELS[speakers["mode"]],
                          info=mode_info(key, MODE_LABELS[speakers["mode"]])), device,
                gr.update(value=speakers["valeur"]) if fixed else gr.skip(),
                gr.update(value=speakers["min"]) if span else gr.skip(),
                gr.update(value=speakers["max"]) if span else gr.skip(),
                _details_html(demo, key))

    def mode_changed(mode: str, key: str):
        return (gr.update(visible=mode == "Imposé"), gr.update(visible=mode == "Fourchette"),
                gr.update(info=mode_info(key, mode)))

    def speaker_options(spec, mode, k, k_min, k_max):
        """(nombre imposé, configuration consignée) ; erreur explicite si le moteur ne suit pas."""
        if spec.auto_only:
            return None, {"mode": "automatique"}
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

    def plan_runs(key, compare, key2, mode, k, k_min, k_max, device_choice) -> list[dict]:
        """Un dictionnaire par moteur, dans l'ordre d'exécution ; gr.Error si un réglage est refusé."""
        keys = [key] + ([key2] if compare and key2 else [])
        if len(keys) == 2 and key2 == key:
            raise gr.Error("Choisissez un second moteur différent du premier.")
        runs = []
        for index, engine_key in enumerate(keys, start=1):
            spec = specs[engine_key]
            if availability[engine_key] is not None:
                raise gr.Error(f"{spec.label} est indisponible ({availability[engine_key]}). "
                               "Choisissez un autre moteur.")
            note = _auto_only_note(spec, mode)
            if note is not None:
                num_speakers, speaker_conf = None, {"mode": "automatique"}
            elif index > 1 and mode == "Fourchette" and not spec.supports_range:
                # Comparaison : la fourchette (pyannote seulement, D17, amendement 1) ne
                # s'applique pas au second moteur, qui estime le nombre de locuteurs (D19).
                num_speakers, speaker_conf = None, {"mode": "automatique"}
                note = (f"Fourchette appliquée à {specs[keys[0]].label} seulement : {spec.label} "
                        "estime lui-même le nombre de locuteurs.")
            else:
                num_speakers, speaker_conf = speaker_options(spec, mode, k, k_min, k_max)
            try:
                device = "cpu" if spec.cpu_only else select_device(device_choice).type
            except (RuntimeError, ValueError) as error:
                raise gr.Error(f"{error}. Choisissez « auto » ou « cpu ».") from error
            runs.append({"index": index, "spec": spec, "device": device, "num_speakers": num_speakers,
                         "speaker_conf": speaker_conf, "note": note, "elapsed": None, "done": False,
                         "recal": None})
        return runs

    def timing(run: dict) -> None:
        """RTF mesuré, état chaud ou froid, surcoût compté et parts des étapes d'un moteur."""
        spec = run["spec"]
        source_device = moteurs.source_device(spec, experiments)
        run["measured"] = temps.measured_rtf(spec.source_exp, run["device"], source_device, leaderboard)
        run["rtf"] = run["measured"].rtf if run["measured"] else None
        run["warm"] = engines.is_warm(spec.key, run["device"])
        run["overhead"] = None if fake else moteurs.fixed_overhead(spec.key, run["device"])
        # Surcoût fixe compté seulement pour un moteur froid (D17, amendement 2).
        run["overhead_s"] = 0.0 if run["warm"] or run["overhead"] is None else run["overhead"].seconds
        run["shares"] = temps.step_shares(moteurs.experiment_dir(spec.source_exp, experiments)
                                          / f"execution_{source_device}.json")

    def cache_key(run: dict, prepared: dict) -> str:
        spec = run["spec"]
        settings = {"peripherique": run["device"], "nombre_locuteurs": run["speaker_conf"],
                    "parametres": moteurs.engine_params(spec, experiments)}
        if fake and fake_rttm is not None:
            settings["sorties_fabriquees"] = str(fake_rttm)   # une sortie fabriquée n'est pas celle du moteur
        return result_key(prepared["empreinte"], spec.key, fake, settings,
                          moteurs.effective_configuration(spec, experiments),
                          moteurs.model_revisions(spec, experiments), engine_code)

    def prepare(audio_path: str) -> dict:
        """Audio normalisé (D15, D16) dans le dossier de travail, durée et empreinte."""
        uri = Path(audio_path).stem
        work = sortie.new_work_dir(RUN_DIR)
        start = time.perf_counter()
        name = Path(audio_path).name
        try:
            wav = normalize(audio_path, work / f"{sortie.rttm_name(uri)}.wav")
            waveform, sample_rate = load_waveform(wav)
        except AudioError as error:
            raise gr.Error(_audio_error(name, error), duration=None) from error
        normalisation_s = time.perf_counter() - start
        if waveform.shape[1] < sample_rate // 10:
            raise gr.Error(f"« {name} » ne contient pas d'audio (moins de 0,1 s une fois décodé). Déposez "
                           "l'enregistrement de la réunion.", duration=None)
        spectrogramme.start(wav, waveform[0].numpy())   # vue spectrogramme (D28 §2), en tâche de fond
        return {"source": audio_path, "nom": name, "uri": uri, "dir": work, "wav": wav,
                "duree_s": waveform.shape[1] / sample_rate, "normalisation_s": normalisation_s,
                "empreinte": audio_fingerprint(waveform[0].numpy()),
                "silencieux": float(waveform.abs().max()) < SILENT_PEAK}

    def estimate_html(prepared, key, compare, key2, mode, k, k_min, k_max, device_choice, use_cache) -> str:
        """Durée annoncée avant le lancement (R-D2 ; D17, amendement 2)."""
        if not prepared:
            return '<div class="ws-estimate"><p class="ws-estimate-head">La durée estimée s\'affichera une fois le fichier déposé.</p></div>'
        try:
            runs = plan_runs(key, compare, key2, mode, k, k_min, k_max, device_choice)
        except gr.Error as error:
            return f'<div class="ws-estimate" data-state="warn"><p class="ws-estimate-head">{escape(error.message)}</p></div>'
        low = high = 0.0
        unknown, computed, lines = False, 0, []
        for run in runs:
            timing(run)
            spec, where = run["spec"], f"{run['spec'].label} sur {run['device']}"
            cached = store.get(cache_key(run, prepared))
            if use_cache and cached:
                lines.append(f"{where} : résultat en cache, réaffichage immédiat")
                continue
            if cached:
                lines.append(f"{where} : un résultat du {_cache_date(cached['date'])} est en cache ; "
                             "nouveau calcul (case « Réafficher un résultat déjà calculé » décochée)")
            computed += 1
            span = temps.announced_range_s(run["rtf"], prepared["duree_s"], run["overhead_s"])
            if span is None:
                unknown = True
                lines.append(f"{where} : RTF non mesuré sur ce périphérique, durée inconnue")
                continue
            low, high = low + span[0], high + span[1]
            if run["warm"]:
                state = "moteur prêt, surcoût fixe non compté"
            elif run["overhead_s"]:
                state = f"moteur froid, surcoût fixe de {_num(run['overhead_s'], 1)}\u202fs compté"
            else:
                state = "moteur froid"
            lines.append(f"{where} : {state} ; RTF {_num(run['rtf'], 4)} ({run['measured'].exp_id})")
        audio = f"pour {temps.format_duration(prepared['duree_s'])} d'audio"
        if not computed:
            head = f"Résultat déjà calculé {audio} : réaffichage immédiat, sans calcul."
        elif unknown:
            head = f"Durée estimée du calcul {audio} : inconnue."
        else:
            head = f"Durée estimée du calcul : {temps.format_range((low, high))} {audio}."
        items = "".join(f"<li>{escape(line)}</li>" for line in lines)
        note = (f'<p class="ws-caption">Moteur factice : calcul simulé, {_num(fake_max_s, 0)}\u202fs au plus.</p>'
                if fake and computed else "")
        note += "".join(f'<p class="ws-caption">{escape(run["note"])}</p>' for run in runs if run["note"])
        if prepared.get("silencieux"):
            note = ('<p class="ws-estimate-alert" role="status">Ce fichier semble silencieux (niveau maximal sous '
                    '−80 dB) : l\'analyse ne trouvera sans doute aucun locuteur. Vérifiez la piste audio (micro '
                    'coupé, mauvais canal exporté) avant de lancer.</p>' + note)
        return linker.link(f'<div class="ws-estimate"><p class="ws-estimate-head">{escape(head)}</p>'
                           f'<ul class="ws-estimate-list">{items}</ul>{note}</div>')

    def audio_changed(audio_path, *settings):
        if not audio_path:
            yield None, estimate_html(None, *settings)
            return
        yield gr.skip(), ('<div class="ws-estimate"><p class="ws-estimate-head">Préparation du fichier '
                          '(normalisation en WAV 16 kHz mono)…</p></div>')
        try:
            prepared = prepare(audio_path)
        except gr.Error as error:
            yield None, f'<div class="ws-estimate" data-state="warn"><p class="ws-estimate-head">{escape(error.message)}</p></div>'
            raise
        yield prepared, estimate_html(prepared, *settings)

    def result_item(run: dict, prepared: dict, annotation, durations: dict, calcul_s: float,
                    loading_s: float | None, settings: dict, rttm_source: str | None,
                    cached: str | None = None, commit: str | None = None, detection: dict | None = None) -> dict:
        spec, measured = run["spec"], run["measured"]
        return {
            # Énergie et seuil de la détection de parole de la baseline (D28 §2), écrits à côté
            # de l'audio normalisé ; None pour un autre moteur.
            "detection": _detection_file(detection, prepared, spec.key),
            "uri": prepared["uri"], "dir": prepared["dir"], "wav": prepared["wav"], "duree_s": prepared["duree_s"],
            "libelle": spec.label, "moteur_cle": spec.key, "annotation": annotation, "names": {},
            # Annotation du moteur, jamais modifiée : les fusions (R-U9) s'appliquent à une copie.
            "annotation_origine": annotation, "fusions": [],
            "moteur": f"factice ({spec.key})" if fake else spec.key,
            "configuration": {
                "experience_source": spec.source_exp, "peripherique": run["device"],
                "nombre_locuteurs": run["speaker_conf"], "moteur_factice": fake, "reglages": settings,
            },
            "calcul_s": calcul_s, "normalisation_s": prepared["normalisation_s"], "chargement_s": loading_s,
            "durees_etapes": durations, "device": run["device"], "factice": fake, "rttm_source": rttm_source,
            "rtf_mesure": {"rtf": measured.rtf, "source": measured.source()} if measured else None,
            "cache": cached,
            # Fiche de reproductibilité (R-D5) : ce qui est connu au moment de l'analyse ; le
            # commit d'un résultat réaffiché est celui de son calcul.
            "tracabilite": {
                "date_analyse": datetime.now().isoformat(timespec="seconds"),
                "commit": commit or code, "empreinte_code_moteurs": engine_code,
                "empreinte_audio": prepared["empreinte"],
                "revisions_modeles": moteurs.model_revisions(spec, experiments),
                "configuration_effective": moteurs.effective_configuration(spec, experiments),
                "configuration_demo": demo.trace(),
            },
        }

    def analyse(prepared, audio_path, key, compare, key2, mode, k, k_min, k_max, device_choice,
                reference_path, use_cache):
        if not audio_path:
            raise gr.Error("Aucun fichier audio : déposez-en un dans les réglages, puis relancez.")
        runs = plan_runs(key, compare, key2, mode, k, k_min, k_max, device_choice)
        for run in runs:
            if run["note"]:
                gr.Info(run["note"])
        prefix = len(runs) > 1
        steps, labels = list(PRE_STEPS[:1]), {}
        for run in runs:
            for step in ("chargement", *run["spec"].steps):
                step_id = f"{run['index']}:{step}"
                steps.append(step_id)
                label = PRE_LABELS.get(step) or run["spec"].step_label(step, STEP_LABELS.get(step, step))
                labels[step_id] = f"{run['spec'].label} : {label}" if prefix else label
        state: dict[str, float] = {}

        def status(title, detail="", fraction=None):
            return _status_html(steps, state, title, detail, fraction, labels=labels)

        yield {howto_card: gr.update(visible=False), results_col: gr.update(visible=True),   # V8
               status_box: status("Normalisation de l'audio", fraction=0.0), viewer: None,
               stats: _stats_html(None), interactions_view: _interactions_html(None), times: _times_html(None),
               der: _der_html(None, reference_path), exports: gr.update(value="", visible=False),
               image_export: "",
               exports_empty: gr.update(visible=True), comparison: "", comparison_card: gr.update(visible=False),
               result_state: None}

        try:
            if not prepared or prepared.get("source") != audio_path:
                prepared = prepare(audio_path)
            state["normalisation_audio"] = 1.0
            waveform, sample_rate = load_waveform(prepared["wav"])
            duration_s = prepared["duree_s"]
            for run in runs:
                timing(run)
                run["cle"] = cache_key(run, prepared)
                run["cached"] = store.get(run["cle"]) if use_cache else None
                if run["cached"]:
                    run["done"] = True
                    for step in ("chargement", *run["spec"].steps):
                        state[f"{run['index']}:{step}"] = 1.0

            def remaining_text() -> str:
                span = temps.cumulative_remaining_s(
                    [(run["rtf"], run["overhead_s"], run["elapsed"], run["done"]) for run in runs], duration_s,
                    [run["recal"] for run in runs])
                scope = " pour les deux moteurs" if prefix and not runs[0]["done"] else ""
                recalibrated = any(run["recal"] is not None and not run["done"] for run in runs)
                if recalibrated and span is not None and span[1] - span[0] >= 0.5:
                    recalibrated = False   # un moteur à venir garde sa fourchette
                return _remaining_text(span, recalibrated, scope)

            results = []
            if engines.lock.locked():
                yield {status_box: status("En attente de la fin du préchauffage des moteurs",
                                          fraction=_step_fraction(steps, state))}
            with engines.lock:
                for run in runs:
                    spec, index = run["spec"], run["index"]
                    if run["cached"]:
                        entry = run["cached"]
                        results.append(result_item(
                            run, prepared, annotation_from_tracks(entry["pistes"], prepared["uri"]),
                            entry["durees_etapes"], entry["calcul_s"], None, entry["reglages"],
                            entry.get("rttm_source"), cached=entry["date"], commit=entry.get("code"),
                            detection=spectrogramme.decode_energy(entry.get("detection"))))
                        continue
                    yield {status_box: status(f"Chargement de {spec.label}", fraction=_step_fraction(steps, state))}
                    try:
                        engine, loading_s = engines.get(spec, run["device"])
                    except ModelMissing as error:
                        raise gr.Error(str(error), duration=None) from error
                    except Exception as error:  # chargement des modèles : message affiché tel quel
                        raise gr.Error(f"Le modèle n'a pas pu être chargé. Détail : {error}") from error
                    state[f"{index}:chargement"] = 1.0
                    # Trace de la détection de parole (D28 §2) : seulement pour la baseline.
                    engine.trace = spec.pipeline == "baseline"
                    if fake:
                        engine.simulated_s = min(fake_max_s, max(2.0, (run["rtf"] or 0.05) * duration_s))
                    if spec.supports_range:
                        engine.min_speakers = run["speaker_conf"].get("min")
                        engine.max_speakers = run["speaker_conf"].get("max")
                    outcome: dict = {}
                    ends: dict[str, float] = {}

                    def progress(step: str, fraction: float, index=index, ends=ends) -> None:
                        step_id = f"{index}:{step}"
                        state[step_id] = max(state.get(step_id, 0.0), fraction)
                        if fraction >= 1.0:
                            ends.setdefault(step, time.perf_counter())

                    def work_thread(engine=engine, run=run, progress=progress, outcome=outcome) -> None:
                        try:
                            outcome["result"] = engine.run(waveform, sample_rate, uri=prepared["uri"],
                                                           num_speakers=run["num_speakers"], progress=progress)
                        except Exception as error:  # remonté à l'interface ci-dessous
                            outcome["error"] = error

                    longest = temps.longest_step(spec.steps, run["shares"])
                    t0 = time.perf_counter()
                    thread = threading.Thread(target=work_thread, daemon=True)
                    thread.start()
                    while thread.is_alive():
                        now = time.perf_counter()
                        run["elapsed"] = now - t0
                        fractions = {step: state.get(f"{index}:{step}", 0.0) for step in spec.steps}
                        run["recal"] = temps.recalibrated_remaining_s(
                            spec.steps, run["shares"], fractions,
                            _longest_started_s(spec.steps, longest, fractions, ends, t0, now))
                        detail = (f"{temps.format_duration(run['elapsed'])} écoulées, {remaining_text()}"
                                  + (f" ({_estimate_source(run, fake)})" if run["measured"] else ""))
                        title = f"Analyse de {prepared['nom']} avec {spec.label}"
                        if prefix:
                            title += f" ({index}/{len(runs)})"
                        yield {status_box: status(title, detail, _step_fraction(steps, state))}
                        thread.join(0.3)
                    calcul_s = time.perf_counter() - t0
                    run["elapsed"], run["done"], run["recal"] = calcul_s, True, None
                    if "error" in outcome:
                        raise gr.Error(f"L'analyse avec {spec.label} a échoué. Détail : {outcome['error']}")
                    engines.mark_warm(spec.key, run["device"])
                    resultat = outcome["result"]
                    detection = spectrogramme.detection_from_trace(resultat.trace)
                    item = result_item(run, prepared, resultat.annotation, resultat.durees_etapes, calcul_s,
                                       loading_s, engine.describe_dict(), resultat.infos.get("rttm_source"),
                                       detection=detection)
                    results.append(item)
                    try:
                        store.put(run["cle"], {
                            "moteur": spec.key, "factice": fake, "peripherique": run["device"],
                            "nombre_locuteurs": run["speaker_conf"], "code": code,
                            "pistes": annotation_tracks(item["annotation"]), "durees_etapes": item["durees_etapes"],
                            "calcul_s": calcul_s, "reglages": item["configuration"]["reglages"],
                            "rttm_source": item["rttm_source"],
                            "detection": spectrogramme.encode_energy(detection) if detection else None,
                        })
                    except OSError as error:   # le cache est un plan de repli : jamais bloquant
                        gr.Warning(f"Résultat non enregistré dans le cache : {error}")

            # DER, carte des erreurs, statistiques et exports : quelques secondes sur un long
            # enregistrement, jusqu'à des minutes sur une sortie très morcelée (B7) ; l'écran le dit.
            yield {status_box: status("Mise en forme des résultats" + (", calcul du DER et de la carte des erreurs"
                                                                       if reference_path else ""), fraction=0.99)}
            result = dict(results[0], peaks=sortie.peaks(waveform[0].numpy(),
                                                        n_points=max(4000, int(PEAKS_PER_S * duration_s))))
            if len(results) > 1:
                result["comparaison"] = results[1]
            result["spectrogramme"] = spectrogramme.result(prepared["wav"], waveform[0].numpy())
            result = _with_reference(result, reference_path)
            summary = ", ".join(
                f"{item['libelle']} : {_plural(len(sortie.speaker_labels(item['annotation'])), 'locuteur')} "
                + ("en cache" if item["cache"] else f"en {temps.format_duration(item['calcul_s'])}")
                for item in results)
            total_s = sum(item["calcul_s"] for item in results)
            n_speakers = len(sortie.speaker_labels(result["annotation"]))
            title = summary if prefix else (f"{_plural(n_speakers, 'locuteur')} en {temps.format_duration(total_s)}"
                                            if n_speakers else f"aucun locuteur détecté, en {temps.format_duration(total_s)}")
            if not prefix:          # en comparaison, le titre commence par le nom d'un moteur (« pyannote »)
                title = title[0].upper() + title[1:]
            detail = f"{prepared['nom']}, {temps.format_duration(duration_s)} d'audio"
            if not prefix:
                detail += f", {result['libelle']}, RTF {_num(total_s / duration_s, 4)}"
            done = _status_html(steps, {step: 1.0 for step in steps}, title, detail, 1.0, labels=labels,
                                badges=_cache_badges(results),
                                done_s=prepared["normalisation_s"] + total_s)
            yield {status_box: done, viewer: _viewer_value(result), stats: _stats_html(result),
                   interactions_view: _interactions_html(result),
                   times: _times_all(result), der: _der_all(result, reference_path),
                   exports: gr.update(value=_exports_html(result), visible=True), exports_empty: gr.update(visible=False),
                   image_export: _image_html(result),
                   comparison: _comparison_html(result), comparison_card: gr.update(visible=bool(result.get("comparaison"))),
                   result_state: result, prepared_state: prepared,
                   # Réglages repliés, timeline en pleine largeur (R-U1).
                   settings_col: gr.update(visible=False), band: gr.update(visible=True),
                   band_text: _band_html(prepared, results), cache_info: _cache_info_html(store),
                   estimate: estimate_html(prepared, key, compare, key2, mode, k, k_min, k_max, device_choice,
                                           use_cache)}
        except Exception as error:
            # Le panneau passe à l'état « échec » sur l'étape en cause, message visible dans la page ;
            # la notification de Gradio est conservée.
            failed = _failed_step(steps, state)
            message = error.message if isinstance(error, gr.Error) else f"{type(error).__name__}: {error}"
            label = labels.get(failed) or PRE_LABELS.get(failed) or STEP_LABELS.get(failed, failed)
            yield {status_box: _status_html(steps, state, f"Échec : {label}", fraction=_step_fraction(steps, state),
                                            labels=labels, failed=failed, error=str(message))}
            if isinstance(error, gr.Error):
                raise
            raise gr.Error(f"L'analyse a échoué. Détail : {message}") from error

    def speakers_changed(result, reference_path, evt: gr.EventData):
        """Tableau des locuteurs : noms saisis (noms en double refusés, le tableau revient aux
        noms en vigueur), fusion de deux locuteurs, ou annulation de la dernière fusion (R-U9).
        Une fusion s'applique à une copie de l'annotation du moteur : le résultat en cache
        n'est jamais modifié."""
        skipped = tuple(gr.skip() for _ in range(8))
        data = getattr(evt, "_data", None) or {}
        if result is None:
            return skipped
        if isinstance(data.get("names"), dict):
            labels = sortie.speaker_labels(result["annotation"])
            typed = {label: str(data["names"].get(label, "") or "").strip()[:60] for label in labels}
            try:
                sortie.resolve_names(labels, typed)
            except ValueError as error:
                gr.Warning(f"{error} : choisissez un nom différent pour chaque locuteur.")
                return (gr.skip(), _stats_html(result), *skipped[2:])
            result = dict(result, names={**result["names"], **typed})
        elif isinstance(data.get("merge"), dict) or data.get("undo"):
            fusions = list(result.get("fusions") or [])
            if data.get("undo"):
                if not fusions:
                    return skipped
                restored = fusions.pop()[0]
            else:
                pair = (str(data["merge"].get("source", "")), str(data["merge"].get("target", "")))
                fusions.append(pair)
                restored = None
            origin = result.get("annotation_origine", result["annotation"])
            try:
                merged = sortie.merge_speakers(origin, fusions)
            except ValueError as error:
                gr.Warning(str(error))
                return (gr.skip(), _stats_html(result), *skipped[2:])
            names = dict(result["names"])
            if restored is not None:
                try:
                    sortie.resolve_names(sortie.speaker_labels(merged), names)
                except ValueError:
                    gr.Warning(f"Le nom de {restored} est déjà pris : {restored} retrouve son identifiant.")
                    names.pop(restored, None)
            result = _with_reference(dict(result, annotation=merged, fusions=fusions, names=names), reference_path)
        else:
            return skipped
        return (_viewer_value(result), _stats_html(result), _interactions_html(result), _exports_html(result),
                _der_all(result, reference_path), _comparison_html(result), _image_html(result), result)

    with gr.Blocks(title="Who Spoke?") as app:
        result_state = gr.State(None)
        prepared_state = gr.State(None)
        header = gr.HTML(_header_html(fake, engines.warmup, demo, demo.default_engine, presentation),
                         js_on_load=None)
        details = gr.HTML(_details_html(demo), js_on_load=DETAILS_JS, elem_classes="ws-details-wrap")
        initial = demo.speakers[demo.default_engine]
        timer = gr.Timer(1.0, active=warm_up)
        with gr.Tabs():
            with gr.Tab("Analyse"):
                # Bandeau des réglages repliés après l'analyse (R-U1).
                with gr.Row(visible=False, equal_height=True, elem_classes="ws-band") as band:
                    band_text = gr.HTML("", js_on_load=None, elem_classes="ws-band-info")
                    new_analysis = gr.Button("Nouvelle analyse", variant="secondary", scale=0, min_width=170,
                                             elem_classes="ws-band-button")
                with gr.Row(equal_height=False):
                    with gr.Column(scale=4, min_width=300, elem_classes="ws-card") as settings_col:
                        gr.HTML(_title("Nouvelle analyse",
                                       "Tout format audio ou vidéo, normalisé en WAV 16 kHz mono."),
                                js_on_load=None)
                        audio = gr.File(label="Fichier audio", file_count="single", type="filepath", height=150)
                        engine = gr.Dropdown(choices, value=demo.default_engine, label="Moteur",
                                             info=engine_info(demo.default_engine))
                        compare = gr.Checkbox(value=False, label="Comparer avec un second moteur",
                                              info="Les deux moteurs tournent l'un après l'autre sur le même fichier.")
                        engine2 = gr.Dropdown(choices, value=_second_engine(specs, demo.default_engine),
                                              label="Second moteur",
                                              visible=False)
                        mode = gr.Radio(speaker_modes(demo.default_engine), value=MODE_LABELS[initial["mode"]],
                                        label="Nombre de locuteurs",
                                        info=mode_info(demo.default_engine, MODE_LABELS[initial["mode"]]))
                        k = gr.Number(value=initial.get("valeur", 2), precision=0, minimum=1, label="Nombre imposé",
                                      visible=initial["mode"] == "impose")
                        with gr.Row(visible=initial["mode"] == "fourchette") as range_row:
                            k_min = gr.Number(value=initial.get("min", 2), precision=0, minimum=1, label="Minimum")
                            k_max = gr.Number(value=initial.get("max", 6), precision=0, minimum=1, label="Maximum")
                        # Réglage secondaire : masqué en mode présentation (B8).
                        # Moteur par défaut en CPU seul (Nemotron 3) : périphérique imposé d'emblée.
                        cpu_only = specs[demo.default_engine].cpu_only
                        device = gr.Dropdown(list(DEVICES), value="cpu" if cpu_only else "auto", label="Périphérique",
                                             interactive=not cpu_only,
                                             info=(CPU_ONLY_INFO.get(demo.default_engine, CPU_ONLY_INFO[None])
                                                   if cpu_only else ENGINE_INFO_DEVICE),
                                             elem_classes="ws-secondary")
                        reference = gr.File(label="Référence RTTM (facultative, pour le DER)",
                                            file_types=[".rttm"], type="filepath", height=150,
                                            elem_classes="ws-reference")
                        estimate = gr.HTML(estimate_html(None, *[None] * 9), js_on_load=None)
                        run = gr.Button("Analyser", variant="primary", size="lg", elem_classes="ws-run")
                        with gr.Accordion("Cache des résultats (plan de repli)", open=False,
                                          elem_classes=["ws-cache", "ws-secondary"]):
                            use_cache = gr.Checkbox(
                                value=False, label="Réafficher un résultat déjà calculé",
                                info="Même audio normalisé, même moteur, mêmes réglages, même configuration "
                                     "effective et mêmes révisions des modèles : réaffichage immédiat, sans calcul.")
                            cache_info = gr.HTML(_cache_info_html(store), js_on_load=None)
                            clear_cache = gr.Button("Vider le cache", variant="secondary", size="sm")
                    with gr.Column(scale=8, min_width=360):
                        # Avant toute analyse, une seule carte explicative (V8) ; l'état et les
                        # résultats apparaissent au lancement.
                        with gr.Column(elem_classes="ws-card ws-howto") as howto_card:
                            gr.HTML(_title("Comment ça marche", "Trois étapes, réglages à gauche."),
                                    js_on_load=None)
                            gr.HTML(_howto_html(), js_on_load=None)
                        with gr.Column(visible=False) as results_col:
                            with gr.Column(elem_classes="ws-card"):
                                status_box = gr.HTML(
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
                                gr.HTML(_title("Locuteurs", "Statistiques, extraits et renommage ; en comparaison, du premier moteur."),
                                        js_on_load=None)
                                stats = gr.HTML(_stats_html(None), js_on_load=STATS_JS)
                            with gr.Column(elem_classes="ws-card"):
                                gr.HTML(_title("Interactions", "Qui prend la parole après qui, et en combien de temps ; "
                                               "sans transcription, du premier moteur."), js_on_load=None)
                                interactions_view = gr.HTML(_interactions_html(None), js_on_load=None)
                            with gr.Column(elem_classes="ws-card"):
                                gr.HTML(_title("Évaluation", "DER face à la référence déposée."), js_on_load=None)
                                der = gr.HTML(_der_html(None, None), js_on_load=None)
                            with gr.Row(equal_height=False, elem_classes="ws-pair"):
                                with gr.Column(elem_classes="ws-card"):
                                    gr.HTML(_title("Temps de traitement"), js_on_load=None)
                                    times = gr.HTML(_times_html(None), js_on_load=None)
                                with gr.Column(elem_classes="ws-card"):
                                    gr.HTML(_title("Exports", "RTTM, JSON avec fiche de reproductibilité, étiquettes "
                                                   "Audacity et image de la timeline ; noms et fusions compris."),
                                            js_on_load=None)
                                    exports = gr.HTML("", js_on_load=None, visible=False, elem_classes="ws-exports")
                                    image_export = gr.HTML("", js_on_load=IMAGE_JS)
                                    exports_empty = gr.HTML(_empty("Disponibles après l'analyse."), js_on_load=None)

            with gr.Tab("Pipeline"):
                with gr.Column(elem_classes="ws-card"):
                    gr.HTML(_title("Pipeline", "Consultation en lecture seule : réglages effectifs de "
                                   "l'expérience source de chaque moteur, expliqués par le catalogue."),
                            js_on_load=None)
                    pipeline_engine = gr.Dropdown(
                        [(spec.label, key) for key, spec in specs.items()],
                        value=demo.default_engine, label="Moteur", elem_classes="pl-engine")
                    pipeline_view = gr.HTML(
                        pipeline_page(demo.default_engine),
                        js_on_load=(STATIC_DIR / "pipeline.js").read_text(), elem_classes="pl-view")

            with gr.Tab("Avancement") as progress_tab:
                sections = progress_sections()
                with gr.Column(elem_classes="ws-card"):
                    gr.HTML(_title("Avancement", "Généré depuis le dépôt à chaque ouverture de l'onglet : "
                                   "en-têtes des notes.md, results, fiches de décision, planning."),
                            js_on_load=None)
                    progress_summary = gr.HTML(sections["resume"], js_on_load=None)
                    progress_learned = gr.HTML(sections["appris"], js_on_load=NOTES_JS)
                with gr.Column(elem_classes="ws-card"):
                    gr.HTML(_title("Erreurs des systèmes de référence",
                                   "DER test sans collar décomposé, par corpus : quatre systèmes de référence, "
                                   "puis toute expérience retenue ou de référence."), js_on_load=None)
                    progress_chart = gr.HTML(sections["graphique"], js_on_load=None)
                with gr.Column(elem_classes="ws-card"):
                    gr.HTML(_title("Expériences et analyses", "Dans l'ordre chronologique. DER sans collar, "
                                   "chevauchements comptés ; en dessous, avec collar de 0,25\u202fs."), js_on_load=None)
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
                    gr.HTML(_title("File d'attente de la piste A (D23)",
                                   "Expériences à venir, dans l'ordre de docs/planning.md."), js_on_load=None)
                    progress_queue = gr.HTML(sections["file"], js_on_load=None)

            with gr.Tab(glossaire.TAB_LABEL):
                with gr.Column(elem_classes="ws-card"):
                    gr.HTML(_title("Glossaire", "Généré depuis docs/glossaire.md. Les termes soulignés en "
                                   "pointillé dans les autres onglets renvoient ici."), js_on_load=None)
                    gr.HTML(glossaire.render(glossary, linker), js_on_load=None)

        engine.change(engine_changed, engine, [engine, mode, device, k, k_min, k_max, details])
        pipeline_engine.change(pipeline_page, pipeline_engine, pipeline_view)

        def refresh_progress():
            sections = progress_sections()
            return (sections["resume"], sections["appris"], sections["graphique"], sections["frise"],
                    sections["oracles"], sections["decisions"], sections["file"])

        def show_notes(evt: gr.EventData):
            item_id = (getattr(evt, "_data", None) or {}).get("notes")
            if not item_id:
                return gr.skip(), gr.skip()
            return avancement.notes_markdown(repo_root, item_id), gr.update(visible=True)

        progress_tab.select(refresh_progress, None, [progress_summary, progress_learned, progress_chart,
                                                     progress_timeline, progress_oracles, progress_decisions,
                                                     progress_queue])
        progress_timeline.click(show_notes, None, [notes_view, notes_card])
        progress_learned.click(show_notes, None, [notes_view, notes_card])
        mode.change(mode_changed, [mode, engine], [k, range_row, mode])

        # Durée annoncée : recalculée à chaque changement de fichier ou de réglage.
        settings_inputs = [engine, compare, engine2, mode, k, k_min, k_max, device, use_cache]
        estimate_inputs = [prepared_state, *settings_inputs]
        audio.change(audio_changed, [audio, *settings_inputs], [prepared_state, estimate])
        for component in settings_inputs:
            component.change(estimate_html, estimate_inputs, estimate, show_progress="hidden")

        def warmup_tick(*inputs):
            # Indicateur « moteurs prêts » et durée annoncée suivent le préchauffage ; la
            # minuterie s'arrête quand il est fini.
            status = engines.warmup
            return (_header_html(fake, status, demo, inputs[1], presentation), estimate_html(*inputs),
                    gr.Timer(active=status.enabled and not status.finished))

        timer.tick(warmup_tick, estimate_inputs, [header, estimate, timer], show_progress="hidden")

        def clear_cache_click(*inputs):
            removed = store.clear()
            gr.Info(f"Cache vidé : {removed} résultat{'s' if removed > 1 else ''} supprimé{'s' if removed > 1 else ''}.")
            return _cache_info_html(store), estimate_html(*inputs)

        clear_cache.click(clear_cache_click, estimate_inputs, [cache_info, estimate])
        def reopen_settings(*inputs):
            return gr.update(visible=True), gr.update(visible=False), estimate_html(*inputs)

        new_analysis.click(reopen_settings, estimate_inputs, [settings_col, band, estimate])
        run.click(
            analyse, [prepared_state, audio, engine, compare, engine2, mode, k, k_min, k_max, device, reference,
                      use_cache],
            [status_box, viewer, stats, interactions_view, times, der, exports, exports_empty, image_export,
             comparison, comparison_card, result_state, prepared_state, settings_col, band, band_text, cache_info,
             estimate, howto_card, results_col],
            concurrency_limit=1, show_progress="hidden",  # l'avancement est dans le panneau d'état
        )
        stats.input(speakers_changed, [result_state, reference],
                    [viewer, stats, interactions_view, exports, der, comparison, image_export, result_state])

        def reference_changed(path, result):
            if result is None:
                return _der_html(None, path), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()
            result = _with_reference(result, path)
            # Exports refaits : l'image de la timeline montre la référence et la carte des erreurs.
            return (_der_all(result, path), _viewer_value(result), _comparison_html(result), _exports_html(result),
                    _image_html(result), result)

        reference.change(reference_changed, [reference, result_state],
                         [der, viewer, comparison, exports, image_export, result_state])
        compare.change(lambda on: gr.update(visible=on), compare, engine2)
    return app


def page_head(presentation: bool = False) -> str:
    """En-tête de page : jetons du système visuel (hors réécriture du CSS par Gradio), renvois du
    glossaire, mode présentation (posé d'emblée si demandé), sélecteur de thème."""
    flag = "<script>window.WS_PRESENTATION = true;</script>" if presentation else ""
    return (f"{theme.head()}<script>{(STATIC_DIR / 'glossaire.js').read_text()}</script>{flag}"
            f"<script>{(STATIC_DIR / 'presentation.js').read_text()}</script>"
            f"<script>{(STATIC_DIR / 'theme.js').read_text()}</script>")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Application de démonstration Who Spoke? (D17).")
    parser.add_argument("--factice", action="store_true",
                        help="moteur factice : étapes simulées et RTTM des expériences, aucune inférence")
    parser.add_argument("--factice-max-s", type=float, default=20.0,
                        help="durée maximale simulée d'une analyse en mode factice (s)")
    parser.add_argument("--factice-rttm", type=Path, default=None, metavar="DOSSIER",
                        help="mode factice : sorties fabriquées, <nom du fichier déposé>.rttm, cherchées avant "
                             "celles de l'expérience source (cas limites de l'interface)")
    parser.add_argument("--port", type=int, default=7860, help="port local (défaut : 7860)")
    parser.add_argument("--depot", type=Path, default=REPO_ROOT,
                        help="racine du dépôt dont sont lus expériences, résultats et catalogue, en lecture "
                             "seule (défaut : ce dépôt ; en développement : ~/Dev/Who-Spoke)")
    parser.add_argument("--sans-prechauffage", action="store_true",
                        help="ne pas charger ni préchauffer les moteurs au démarrage (chargés au premier usage)")
    parser.add_argument("--vider-cache", action="store_true",
                        help="vider le cache des résultats (~/.cache/whospoke/resultats) avant le lancement")
    parser.add_argument("--presentation", action="store_true",
                        help="ouvrir en mode présentation : texte et commandes agrandis, contrastes renforcés, "
                             "réglages secondaires masqués (vidéoprojecteur, écran partagé)")
    parser.add_argument("--config-demo", type=Path, default=None, metavar="FICHIER",
                        help="configuration de démonstration à lire à la place de configs/demo.yaml du dépôt "
                             "(essai d'un fichier avant le gel, par exemple configs/demo.exemple.yaml)")
    args = parser.parse_args(argv)
    for stale in travail.remove_stale():
        print(f"Dossier temporaire d'un lancement interrompu supprimé : {stale}")
    if args.vider_cache:
        store = ResultCache()
        removed = store.clear()
        print(f"Cache des résultats vidé ({store.directory}) : {removed} résultat{'s' if removed > 1 else ''} "
              f"supprimé{'s' if removed > 1 else ''}.")
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    # Suppression à la fermeture : sortie normale, Ctrl+C ou SIGTERM.
    atexit.register(travail.cleanup, RUN_DIR)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    gr.set_static_paths([STATIC_DIR])
    depot = args.depot.expanduser().resolve()
    if not (depot / "experiments").is_dir():
        parser.error(f"--depot : {depot} ne contient pas de dossier experiments/")
    if args.factice_rttm is not None and not args.factice:
        parser.error("--factice-rttm ne s'emploie qu'avec --factice")
    try:
        demo = moteurs.demo_config(depot, args.config_demo.expanduser().resolve() if args.config_demo else None)
    except moteurs.DemoConfigError as error:
        parser.error(f"configuration de démonstration : {error}")
    print(f"Configuration de démonstration : {demo.source}"
          + ("" if demo.frozen else " (configs/demo.yaml absent, avant le gel)")
          + f" ; moteur par défaut : {demo.default_engine}"
          + (f" ; non retenus pour la démonstration : {', '.join(demo.excluded)}." if demo.excluded else "."))
    app = build_app(fake=args.factice, fake_max_s=args.factice_max_s, repo_root=depot,
                    warm_up=not args.sans_prechauffage,
                    fake_rttm=args.factice_rttm.expanduser().resolve() if args.factice_rttm else None,
                    demo=demo, presentation=args.presentation)
    app.launch(
        server_name="127.0.0.1", server_port=args.port, share=False,
        allowed_paths=[str(RUN_DIR)], theme=theme.build_theme(), css=theme.css(),
        head=page_head(args.presentation),
        # Pied de page de Gradio masqué (R-U5) ; zones de dépôt en français quelle que soit
        # la langue du navigateur.
        footer_links=[], i18n=gr.I18n(**theme.UPLOAD_TEXT), mcp_server=False, ssr_mode=False,
    )


if __name__ == "__main__":
    main()
