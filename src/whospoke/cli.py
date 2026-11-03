"""Commande en ligne `whospoke` (audit du 01/11, R-R2 ; chantier E1).

    uv run whospoke diarize reunion.m4a
    uv run whospoke diarize reunion.m4a --moteur baseline-ecapa --locuteurs 4 --sortie json -o reunion.json
    uv run whospoke diarize reunion.m4a --locuteurs 2-6          # fourchette (pyannote seulement)

Elle reprend les moteurs de l'application (`app/moteurs.py`) : mêmes expériences sources,
même θ retenu, mêmes périphériques imposés (CPU seul pour les baselines), même
normalisation de l'audio (D15, D16) et mêmes exports RTTM et JSON (`app/sortie.py`). Le
résultat est écrit sur la sortie standard, ou dans le fichier donné par `-o` ; les
messages d'avancement vont sur la sortie d'erreur.

Hors ligne (D27) : `HF_HUB_OFFLINE=1` est posée avant tout import de huggingface_hub, qui
la lit une fois pour toutes ; les modèles sont lus dans le cache local rempli par
`scripts/prefetch_models.py`, et la télémétrie est coupée par l'import de `whospoke`.
Ce module n'importe donc que la bibliothèque standard à son chargement.

La configuration des moteurs est lue dans `experiments/` et le paquet `app/` du dépôt :
la commande s'utilise depuis un clone du dépôt, comme l'interface.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from collections.abc import MutableMapping, Sequence
from pathlib import Path

from whospoke.telemetry import disable_telemetry

ENGINES = ("pyannote-community-1", "baseline-mfcc", "baseline-ecapa", "baseline-wespeaker", "nemotron-3")
DEFAULT_ENGINE = "pyannote-community-1"   # moteur proposé par défaut dans l'interface
DEVICES = ("auto", "cpu", "mps", "cuda")
FORMATS = ("rttm", "json")

_RANGE = re.compile(r"^(\d+)-(\d+)$")


class CliError(RuntimeError):
    """Erreur d'utilisation ou d'exécution, affichée sans trace (code de sortie 1)."""


def configure_environment(environ: MutableMapping[str, str]) -> None:
    """Fonctionnement hors ligne et télémétrie coupée, avant tout import tiers (D27)."""
    disable_telemetry(environ)
    environ["HF_HUB_OFFLINE"] = "1"


def parse_speakers(text: str) -> tuple[int | None, dict]:
    """`auto`, `N` ou `MIN-MAX` -> (nombre imposé, configuration consignée).

    La configuration a la forme de celle de l'interface (`nombre_locuteurs` du JSON).
    """
    text = text.strip().lower()
    if text in ("auto", "automatique"):
        return None, {"mode": "automatique"}
    if text.isdigit():
        value = int(text)
        if value < 1:
            raise CliError("--locuteurs : le nombre imposé doit valoir au moins 1")
        return value, {"mode": "impose", "valeur": value}
    match = _RANGE.match(text)
    if match:
        low, high = int(match.group(1)), int(match.group(2))
        if low < 1 or low > high:
            raise CliError("--locuteurs : fourchette MIN-MAX avec 1 ≤ MIN ≤ MAX attendue")
        return None, {"mode": "fourchette", "min": low, "max": high}
    raise CliError(f"--locuteurs : {text!r} non reconnu (attendu : auto, un nombre, ou MIN-MAX)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="whospoke", description="Who Spoke? — diarisation de locuteurs, en ligne de commande.")
    commands = parser.add_subparsers(dest="commande", required=True)
    diarize = commands.add_parser(
        "diarize", help="diarise un fichier audio avec un moteur de l'application",
        description="Diarise un fichier audio (tout format lu par ffmpeg) avec un moteur de l'application, "
                    "hors ligne. Le résultat va sur la sortie standard, ou dans le fichier donné par -o.")
    diarize.add_argument("audio", type=Path, help="fichier audio à analyser")
    diarize.add_argument("--moteur", choices=ENGINES, default=DEFAULT_ENGINE,
                         help=f"moteur (défaut : {DEFAULT_ENGINE})")
    diarize.add_argument("--locuteurs", default="auto",
                         help="nombre de locuteurs : auto (estimé, défaut), N (imposé) ou MIN-MAX "
                              "(fourchette, pyannote seulement)")
    diarize.add_argument("--peripherique", choices=DEVICES, default="auto",
                         help="périphérique de calcul (défaut : auto ; les baselines tournent toujours en CPU)")
    diarize.add_argument("--sortie", choices=FORMATS, default="rttm", help="format du résultat (défaut : rttm)")
    diarize.add_argument("-o", "--fichier", type=Path, default=None,
                         help="fichier de sortie (défaut : sortie standard)")
    return parser


def _say(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _engines_module():
    """`app.moteurs` et `app.sortie`, en ajoutant la racine du dépôt au chemin si besoin.

    Le paquet `app` n'est pas installé : le script `whospoke` le trouve à côté de `src/`.
    """
    from whospoke.experiment import REPO_ROOT

    try:
        from app import moteurs, sortie
    except ModuleNotFoundError:
        sys.path.insert(0, str(REPO_ROOT))
        from app import moteurs, sortie
    return moteurs, sortie


def diarize(args: argparse.Namespace) -> str:
    """Analyse complète ; renvoie le texte du résultat (RTTM ou JSON)."""
    num_speakers, speaker_conf = parse_speakers(args.locuteurs)
    moteurs, sortie = _engines_module()

    from whospoke.audio import AudioError, load_waveform, normalize
    from whospoke.device import select_device

    spec = moteurs.SPECS[args.moteur]
    if spec.auto_only and speaker_conf["mode"] != "automatique":
        raise CliError(f"{spec.label} estime seul le nombre de locuteurs ({spec.max_speakers} au plus) : "
                       "--locuteurs auto.")
    if speaker_conf["mode"] == "fourchette" and not spec.supports_range:
        raise CliError(f"{spec.label} ne prend pas en charge une fourchette : imposez un nombre.")
    try:
        moteurs.engine_params(spec)
    except moteurs.EngineUnavailable as error:
        raise CliError(f"{spec.label} est indisponible : {error}") from error
    try:
        device = "cpu" if spec.cpu_only else select_device(args.peripherique).type
    except (RuntimeError, ValueError) as error:
        raise CliError(f"{error}. Choisissez auto ou cpu.") from error

    uri = args.audio.stem
    with tempfile.TemporaryDirectory(prefix="whospoke-") as work:
        _say(f"Normalisation de {args.audio.name} (WAV 16 kHz mono)…")
        try:
            wav = normalize(args.audio, Path(work) / f"{sortie.rttm_name(uri)}.wav")
            waveform, sample_rate = load_waveform(wav)
        except AudioError as error:
            raise CliError(f"Ce fichier n'a pas pu être lu comme de l'audio. Détail : {error}") from error
    duration_s = waveform.shape[1] / sample_rate

    _say(f"Chargement de {spec.label} ({device})…")
    try:
        engine = moteurs.build_engine(spec, device)
    except Exception as error:
        message = moteurs.missing_model_message(error, spec)
        if message is not None:
            raise CliError(message) from error
        raise
    if spec.supports_range:
        engine.min_speakers = speaker_conf.get("min")
        engine.max_speakers = speaker_conf.get("max")

    seen: set[str] = set()

    def progress(step: str, fraction: float) -> None:
        if step not in seen:
            seen.add(step)
            _say(f"  étape : {step}")

    _say(f"Analyse de {duration_s:.1f} s d'audio…")
    start = time.perf_counter()
    resultat = engine.run(waveform, sample_rate, uri=uri, num_speakers=num_speakers, progress=progress)
    compute_s = time.perf_counter() - start
    n_speakers = len(sortie.speaker_labels(resultat.annotation))
    _say(f"Terminé en {compute_s:.1f} s : {n_speakers} locuteur(s).")

    if args.sortie == "rttm":
        return sortie.to_rttm(resultat.annotation, uri)
    configuration = {
        "experience_source": spec.source_exp, "peripherique": device,
        "nombre_locuteurs": speaker_conf, "moteur_factice": False,
        "reglages": engine.describe_dict(),
    }
    data = sortie.to_json(resultat.annotation, uri, duration_s, spec.key, configuration, compute_s)
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def main(argv: Sequence[str] | None = None, environ: MutableMapping[str, str] = os.environ) -> int:
    configure_environment(environ)
    args = build_parser().parse_args(argv)
    try:
        if not args.audio.is_file():
            raise CliError(f"Fichier introuvable : {args.audio}")
        text = diarize(args)
    except CliError as error:
        _say(f"whospoke : {error}")
        return 1
    if args.fichier is None:
        sys.stdout.write(text)
    else:
        args.fichier.parent.mkdir(parents=True, exist_ok=True)
        args.fichier.write_text(text)
        _say(f"Résultat écrit dans {args.fichier}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
