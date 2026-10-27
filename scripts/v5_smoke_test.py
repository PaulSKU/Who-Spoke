"""Vérification V5 : pyannote community-1 de bout en bout sur AMI ES2004a (SDM, Array1-01).

Ce n'est pas une expérience EXP : rien n'est écrit dans experiments/ ni dans le
leaderboard. Le résultat est consigné à la main dans docs/journal.md.

Étapes :
1. téléchargement de l'audio (miroir AMI), de la référence RTTM (only_words) et de
   l'UEM depuis pyannote/AMI-diarization-setup, dans data/raw/ami/ ;
2. normalisation en WAV 16 kHz mono (whospoke.audio, D16), dans data/processed/ami/ ;
3. pour chaque périphérique (MPS puis CPU), un sous-processus distinct qui charge la
   pipeline, fait un préchauffage sur un extrait de 60 s, puis traite la réunion
   entière en lui passant un dict {"waveform", "sample_rate"} lu par
   whospoke.audio.load_waveform (sans torchcodec) ;
4. essai séparé avec un chemin de fichier passé directement à la pipeline (extrait de
   60 s), dont l'échec éventuel est consigné sans faire échouer le script.

Chaque mesure tourne dans son propre processus pour que la mémoire maximale
(`ru_maxrss`) soit propre au périphérique mesuré.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
import sys
import time
import traceback
import urllib.request
import warnings
from pathlib import Path

from whospoke.audio import load_waveform, normalize

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw" / "ami"
PROCESSED_DIR = REPO_ROOT / "data" / "processed" / "ami"

MEETING = "ES2004a"
URI = f"ami__{MEETING}"
PIPELINE_NAME = "pyannote/speaker-diarization-community-1"
SETUP_BASE = "https://raw.githubusercontent.com/pyannote/AMI-diarization-setup/main"
SOURCES = {
    f"{MEETING}.Array1-01.wav": (
        f"https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus/{MEETING}/audio/"
        f"{MEETING}.Array1-01.wav"
    ),
    f"{MEETING}.rttm": f"{SETUP_BASE}/only_words/rttms/test/{MEETING}.rttm",
    # Le dépôt ne fournit pas d'UEM propre à only_words : l'UEM est commun aux deux
    # variantes d'annotation (uems/test/).
    f"{MEETING}.uem": f"{SETUP_BASE}/uems/test/{MEETING}.uem",
}

WARMUP_SECONDS = 60.0

NORMALIZED_WAV = PROCESSED_DIR / f"{URI}.wav"
EXCERPT_WAV = PROCESSED_DIR / f"{URI}__extrait60s.wav"
RESULTS_JSON = PROCESSED_DIR / "v5_results.json"


# --- Préparation des données -------------------------------------------------------


def download() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        target = RAW_DIR / name
        if target.exists() and target.stat().st_size > 0:
            print(f"[données] déjà présent : {target.relative_to(REPO_ROOT)}")
            continue
        print(f"[données] téléchargement : {url}")
        tmp = target.with_suffix(target.suffix + ".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.rename(target)


def prepare() -> None:
    download()
    if not NORMALIZED_WAV.exists():
        print("[données] normalisation 16 kHz mono (ffmpeg)")
        normalize(RAW_DIR / f"{MEETING}.Array1-01.wav", NORMALIZED_WAV)
    if not EXCERPT_WAV.exists():
        normalize(NORMALIZED_WAV, EXCERPT_WAV, duration=WARMUP_SECONDS)


def load_reference():
    from pyannote.core import Annotation, Segment, Timeline

    reference = Annotation(uri=URI)
    for line in (RAW_DIR / f"{MEETING}.rttm").read_text().splitlines():
        fields = line.split()
        if not fields or fields[0] != "SPEAKER":
            continue
        start, duration, speaker = float(fields[3]), float(fields[4]), fields[7]
        reference[Segment(start, start + duration)] = speaker
    uem = Timeline(uri=URI)
    for line in (RAW_DIR / f"{MEETING}.uem").read_text().splitlines():
        fields = line.split()
        if fields:
            uem.add(Segment(float(fields[2]), float(fields[3])))
    return reference, uem


# --- Sous-processus de mesure ------------------------------------------------------


def peak_rss_mb() -> float:
    # ru_maxrss est en octets sur macOS, en kilo-octets sous Linux.
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / 2**20 if sys.platform == "darwin" else value / 2**10


def load_pipeline(device_name: str):
    import torch
    from dotenv import load_dotenv
    from pyannote.audio import Pipeline

    from whospoke.device import select_device

    load_dotenv(REPO_ROOT / ".env")
    token = os.environ.get("HF_TOKEN") or None
    if token is None:
        raise RuntimeError("HF_TOKEN absent ou vide dans .env (modèle à accès restreint)")
    device = select_device(device_name)
    if device.type == "cpu":
        # CPU seul : on s'assure qu'aucun repli MPS n'intervient.
        os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "0"
    pipeline = Pipeline.from_pretrained(PIPELINE_NAME, token=token)
    if pipeline is None:
        raise RuntimeError(f"Chargement de {PIPELINE_NAME} impossible (accès au modèle ?)")
    pipeline.to(device)
    return pipeline, device, torch


def annotation_of(output):
    """La pipeline 4.x renvoie un DiarizeOutput ; les versions antérieures une Annotation."""
    return getattr(output, "speaker_diarization", output)


def run_device(device_name: str) -> dict:
    from whospoke.evaluation.metrics import DiarizationEvaluator, round_rates

    caught: list[str] = []
    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter("always")

        t0 = time.perf_counter()
        pipeline, device, torch = load_pipeline(device_name)
        loading_s = time.perf_counter() - t0

        # Préchauffage (protocole §3.5) sur l'extrait de 60 s, non compté.
        t0 = time.perf_counter()
        waveform, sample_rate = load_waveform(EXCERPT_WAV)
        pipeline({"waveform": waveform, "sample_rate": sample_rate})
        warmup_s = time.perf_counter() - t0

        # Temps de calcul : lecture de l'audio normalisé + pipeline complète.
        t0 = time.perf_counter()
        waveform, sample_rate = load_waveform(NORMALIZED_WAV)
        output = pipeline({"waveform": waveform, "sample_rate": sample_rate})
        if device.type == "mps":
            torch.mps.synchronize()
        compute_s = time.perf_counter() - t0

        caught = [f"{w.category.__name__}: {w.message}" for w in records]

    audio_s = waveform.shape[1] / sample_rate
    hypothesis = annotation_of(output)
    hypothesis.uri = URI
    reference, uem = load_reference()

    evaluator = DiarizationEvaluator()
    per_condition = evaluator.add(reference, hypothesis, uem=uem)
    metrics = {
        name: round_rates({k: v for k, v in values.items() if not k.endswith("_s")})
        | {k: round(v, 2) for k, v in values.items() if k.endswith("_s")}
        for name, values in per_condition.items()
    }

    rttm_path = PROCESSED_DIR / f"v5_hyp_{device.type}.rttm"
    with rttm_path.open("w") as handle:
        hypothesis.write_rttm(handle)

    result = {
        "device": device.type,
        "torch_threads": torch.get_num_threads(),
        "duree_audio_s": round(audio_s, 2),
        "chargement_modeles_s": round(loading_s, 2),
        "prechauffage_s": round(warmup_s, 2),
        "calcul_s": round(compute_s, 2),
        "rtf": round(compute_s / audio_s, 4),
        "temps_30_min_s": round(compute_s / audio_s * 1800, 1),
        "memoire_max_processus_mo": round(peak_rss_mb(), 1),
        "n_locuteurs_estime": len(hypothesis.labels()),
        "n_locuteurs_reference": len(reference.crop(uem).labels()),
        "metriques": metrics,
        "avertissements": sorted(set(caught)),
    }
    if device.type == "mps":
        result["mps_memoire_pilote_max_mo"] = round(torch.mps.driver_allocated_memory() / 2**20, 1)
    return result


def run_file_path() -> dict:
    """Essai : chemin de fichier passé directement à la pipeline (décodage par pyannote)."""
    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter("always")
        pipeline, _, _ = load_pipeline("auto")
        try:
            output = pipeline(str(EXCERPT_WAV))
            outcome = {
                "fonctionne": True,
                "n_locuteurs_estime": len(annotation_of(output).labels()),
            }
        except Exception as error:  # noqa: BLE001 — on consigne l'erreur exacte
            outcome = {
                "fonctionne": False,
                "erreur": f"{type(error).__name__}: {error}",
                "trace": traceback.format_exc(),
            }
    outcome["avertissements"] = sorted({f"{w.category.__name__}: {w.message}" for w in records})
    return outcome


# --- Orchestration -----------------------------------------------------------------


def run_child(mode: str, timeout: float | None = None) -> dict:
    command = [sys.executable, __file__, "--child", mode]
    print(f"[v5] sous-processus : {mode}", flush=True)
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, cwd=REPO_ROOT
        )
    except subprocess.TimeoutExpired:
        return {"erreur": f"délai dépassé ({timeout} s)"}
    sys.stderr.write(completed.stderr)
    marker = "V5_RESULT="
    for line in completed.stdout.splitlines():
        if line.startswith(marker):
            return json.loads(line[len(marker):])
    return {
        "erreur": f"code de sortie {completed.returncode}",
        "stderr_fin": completed.stderr[-4000:],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--child", help=argparse.SUPPRESS)
    parser.add_argument(
        "--devices", default="mps,cpu", help="périphériques à mesurer, dans l'ordre (défaut : mps,cpu)"
    )
    args = parser.parse_args()

    if args.child:
        try:
            result = run_file_path() if args.child == "file_path" else run_device(args.child)
        except Exception as error:  # noqa: BLE001
            result = {"erreur": f"{type(error).__name__}: {error}", "trace": traceback.format_exc()}
        print("V5_RESULT=" + json.dumps(result, ensure_ascii=False), flush=True)
        return

    prepare()
    results = {"meeting": MEETING, "pipeline": PIPELINE_NAME, "devices": {}}
    for name in args.devices.split(","):
        results["devices"][name] = run_child(name)
        print(json.dumps(results["devices"][name], ensure_ascii=False, indent=2), flush=True)
    results["essai_chemin_fichier"] = run_child("file_path", timeout=1800)
    print(json.dumps(results["essai_chemin_fichier"], ensure_ascii=False, indent=2), flush=True)

    RESULTS_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"[v5] résultats : {RESULTS_JSON.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
