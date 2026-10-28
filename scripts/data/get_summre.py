"""Préparation de SUMM-RE, partitions dev et test (D20).

Source : dépôt Hugging Face linagora/SUMM-RE, figé à la révision REVISION (D20 §1).
Une ligne Parquet = une piste de micro-casque d'un participant, avec ses segments et
ses mots alignés.

Étapes :
1. pour chaque fichier Parquet de data/dev/ et data/test/ : téléchargement dans
   data/raw/summre/, contrôle du SHA-256 contre celui du dépôt (LFS) et, s'il existe,
   contre le manifeste ; extraction de chaque piste, rééchantillonnée à 16 kHz mono par
   ffmpeg en flottant 32 bits (piste intermédiaire), et de ses mots ; puis suppression du
   Parquet, une fois toutes ses pistes extraites et son SHA-256 consigné dans
   data/raw/summre/etat.json (reprise possible après interruption) ;
2. par réunion, une fois toutes les pistes de la partition extraites : mélange
   (pistes complétées par des zéros jusqu'à la plus longue, additionnées et divisées par
   leur nombre, sans écrêtage ; D20 §2) écrit en PCM 16 bits dans
   data/processed/summre/summre__<meeting_id>.wav ; référence construite à partir des
   mots (D20 §3) dans data/processed/summre/rttm/ ; UEM dans data/splits/summre/uem/ ;
   contrôle de synchronisation ; suppression des pistes intermédiaires ;
3. contrôles et statistiques de D20 §4, manifeste data/manifests/summre.csv, listes
   data/splits/summre/{dev,test,temps,zoom_dev,zoom_test}.txt ;
4. contrôle croisé avec le dérivé ggfox00000/dia-summre-test (RTTM seuls, téléchargés
   dans data/raw/ puis supprimés) : DER sans collar entre nos références du test
   (référence) et les siennes (hypothèse), dans nos UEM. Ce dérivé ne sert jamais à noter.

Synchronisation (D20 §2) : chaque piste est corrélée au mélange des autres pistes de la
réunion (le mélange complet contient la piste elle-même, ce qui placerait toujours le
pic à un décalage nul) ; le pic est cherché à ±1 s, sur les signaux ramenés à 8 kHz. La
mesure repose sur la diaphonie (la voix des autres captée par chaque micro-casque) : elle
n'est retenue que si le pic est saillant (rapport du pic à l'écart-type de la corrélation
sur ±1 s d'au moins SYNC_MIN_SALIENCE). Sans diaphonie, notamment pour les pistes Zoom
séparées, le décalage est déclaré non mesurable. Un décalage mesurable supérieur à 50 ms
est signalé. Décalage, coefficient et saillance sont consignés par piste dans le manifeste.

Un nouveau lancement après une préparation complète ne retélécharge rien : il recalcule
les statistiques à partir des sorties et du manifeste, puis refait le contrôle croisé.

Usage : uv run python scripts/data/get_summre.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.io import wavfile

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw" / "summre"
TRACKS_DIR = RAW_DIR / "pistes"
STATE = RAW_DIR / "etat.json"
DERIVED_DIR = REPO_ROOT / "data" / "raw" / "dia-summre-test"
PROCESSED_DIR = REPO_ROOT / "data" / "processed" / "summre"
RTTM_DIR = PROCESSED_DIR / "rttm"
SPLITS_DIR = REPO_ROOT / "data" / "splits" / "summre"
UEM_DIR = SPLITS_DIR / "uem"
MANIFEST = REPO_ROOT / "data" / "manifests" / "summre.csv"

CORPUS = "summre"
REPO_ID = "linagora/SUMM-RE"
REVISION = "47cb4ec3437ef5497b6092b8c6d1e0b5b1d86dc0"
LICENCE = "CC BY-SA 4.0"
DERIVED_REPO_ID = "ggfox00000/dia-summre-test"
DERIVED_REVISION = "d6f8f2f2e59486d20652719164b362280b6a1123"

# Nombre de réunions et de pistes attendues (fiche du dépôt, D20 §4).
PARTITIONS = {"dev": (36, 130), "test": (37, 124)}
SAMPLE_RATE = 16000
MERGE_GAP_S = 0.2          # fusion des écarts de 200 ms ou moins (conventions-annotation.md §2)
UEM_MARGIN_S = 1.0         # premier mot − 1 s, dernier mot + 1 s (D20 §3)
SYNC_RATE = 8000           # fréquence de calcul de la corrélation croisée
SYNC_SEARCH_S = 1.0        # décalages explorés : ±1 s
SYNC_MAX_LAG_S = 0.05      # seuil de signalement (D20 §2)
# Saillance minimale du pic pour qu'un décalage soit tenu pour mesuré : le maximum de
# |corrélation| de deux bruits indépendants sur 16 001 décalages est d'environ 4,5 écarts-types.
SYNC_MIN_SALIENCE = 10.0

# Sous-ensemble de mesure du temps en CPU seul (protocole §3.5), dans la partition de test :
# deux réunions totalisant 30 à 45 min (D20 §5). Règle : une réunion en présentiel et une
# réunion Zoom, pour ne pas mesurer le temps sur une seule condition d'enregistrement ;
# la première paire, dans l'ordre des identifiants, dont le total tombe dans la fourchette.
TIMING_TOTAL_RANGE_S = (30 * 60.0, 45 * 60.0)

# Jetons de convention SPPAS sans contenu lexical : pause courte, bruit, rire. Ils sont
# gardés dans la référence (D20 §3 : les mots alignés), mais leur part est mesurée.
NON_LEXICAL_TOKENS = ("+", "*", "@")


def uri_of(meeting: str) -> str:
    return f"{CORPUS}__{meeting}"


def is_zoom(meeting: str) -> bool:
    """Code de lieu Z (Zoom) : dernière lettre du suffixe de `meeting_id` (ex. 020b_EBDZ)."""
    return meeting.split("_")[-1].endswith("Z")


# --- Référence (D20 §3) -------------------------------------------------------------------


def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def word_intervals(segments: list[dict], skip: tuple[str, ...] = ()) -> tuple[list[tuple[float, float]], int]:
    """Intervalles des mots d'une piste, et nombre de mots sans horodatage.

    Un mot sans début ou sans fin prend les bornes de son segment. Les mots dont le texte
    figure dans `skip` sont ignorés (mesure de la part des jetons non lexicaux).
    """
    intervals, missing = [], 0
    for segment in segments or []:
        for word in segment.get("words") or []:
            if word.get("word") in skip:
                continue
            start, end = word.get("start"), word.get("end")
            if _missing(start) or _missing(end):
                missing += 1
                start, end = segment["start"], segment["end"]
            if end > start:
                intervals.append((float(start), float(end)))
    return intervals, missing


def merge_intervals(intervals: list[tuple[float, float]], gap: float = MERGE_GAP_S) -> list[tuple[float, float]]:
    """Union d'intervalles, en fusionnant ceux séparés de `gap` secondes ou moins."""
    merged: list[list[float]] = []
    for start, end in sorted(intervals):
        if merged and start - merged[-1][1] <= gap + 1e-9:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def build_reference(
    tracks: list[dict], skip: tuple[str, ...] = ()
) -> tuple[dict[str, list[tuple[float, float]]], int]:
    """Référence d'une réunion : intervalles fusionnés par locuteur, et mots sans horodatage.

    `tracks` : une entrée par piste, avec `speaker_id` et `segments`. Un participant sans
    aucun mot n'apparaît pas dans la référence (il n'est pas compté comme locuteur).
    Le chevauchement découle des intervalles de locuteurs différents qui se recouvrent.
    """
    by_speaker: dict[str, list[tuple[float, float]]] = defaultdict(list)
    missing = 0
    for track in tracks:
        intervals, n_missing = word_intervals(track["segments"], skip)
        by_speaker[track["speaker_id"]] += intervals
        missing += n_missing
    reference = {
        speaker: merge_intervals(intervals)
        for speaker, intervals in sorted(by_speaker.items())
        if intervals
    }
    return reference, missing


def rttm_text(uri: str, reference: dict[str, list[tuple[float, float]]]) -> str:
    rows = sorted(
        (start, end, speaker) for speaker, intervals in reference.items() for start, end in intervals
    )
    return "".join(
        f"SPEAKER {uri} 1 {start:.3f} {end - start:.3f} <NA> <NA> {speaker} <NA> <NA>\n"
        for start, end, speaker in rows
    )


def uem_bounds(reference: dict[str, list[tuple[float, float]]], duration: float) -> tuple[float, float]:
    """Du premier mot moins 1 s au dernier mot plus 1 s, borné au signal (D20 §3)."""
    first = min(start for intervals in reference.values() for start, _ in intervals)
    last = max(end for intervals in reference.values() for _, end in intervals)
    return max(0.0, first - UEM_MARGIN_S), min(duration, last + UEM_MARGIN_S)


def speech_overlap(reference: dict[str, list[tuple[float, float]]], uem: tuple[float, float]) -> dict:
    """Parole (≥ 1 locuteur), chevauchement (≥ 2) et temps par locuteur, dans l'UEM."""
    low, high = uem
    events = []
    per_speaker = {}
    for speaker, intervals in reference.items():
        total = 0.0
        for start, end in intervals:
            start, end = max(start, low), min(end, high)
            if end > start:
                events += [(start, 1), (end, -1)]
                total += end - start
        per_speaker[speaker] = total
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
    return {"parole_s": speech, "chevauchement_s": overlap, "par_locuteur_s": per_speaker}


# --- Signal (D20 §2) ----------------------------------------------------------------------


def mix_tracks(tracks: list[np.ndarray]) -> np.ndarray:
    """Pistes complétées par des zéros jusqu'à la plus longue, additionnées, divisées par leur nombre."""
    length = max(len(track) for track in tracks)
    mix = np.zeros(length, dtype=np.float64)
    for track in tracks:
        mix[: len(track)] += track
    return (mix / len(tracks)).astype(np.float32)


def to_pcm16(signal: np.ndarray) -> np.ndarray:
    """Conversion en PCM 16 bits ; refuse tout dépassement de [-1, 1] (pas d'écrêtage)."""
    peak = float(np.max(np.abs(signal))) if len(signal) else 0.0
    if peak > 1.0:
        raise ValueError(f"crête {peak:.4f} > 1 : la conversion écrêterait le signal")
    return np.round(signal.astype(np.float64) * 32767.0).astype(np.int16)


def estimate_lag(
    track: np.ndarray, others: np.ndarray, sample_rate: int, search_s: float
) -> tuple[float, float, float]:
    """Décalage (s) de `track` par rapport à `others`, coefficient et saillance du pic.

    Un décalage positif signifie que `track` est en retard. Corrélation par FFT, pic
    cherché dans ±`search_s`, normalisée par les normes des deux signaux. La saillance est
    le rapport de |pic| à l'écart-type de la corrélation sur la plage explorée.
    """
    n = min(len(track), len(others))
    a = track[:n].astype(np.float64) - track[:n].mean()
    b = others[:n].astype(np.float64) - others[:n].mean()
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0.0:
        return 0.0, 0.0, 0.0
    size = 1 << (2 * n - 1).bit_length()
    corr = np.fft.irfft(np.fft.rfft(a, size) * np.conj(np.fft.rfft(b, size)), size)
    max_lag = int(search_s * sample_rate)
    lags = np.concatenate([np.arange(0, max_lag + 1), np.arange(-max_lag, 0)])
    values = np.concatenate([corr[: max_lag + 1], corr[size - max_lag:]])
    best = int(np.argmax(np.abs(values)))
    salience = float(abs(values[best]) / np.std(values)) if np.std(values) > 0 else 0.0
    return lags[best] / sample_rate, float(values[best] / norm), salience


def resample_to_float(src: Path, dst: Path) -> None:
    """Rééchantillonnage à 16 kHz mono par ffmpeg, en flottant 32 bits (piste intermédiaire)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".part.wav")
    command = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
        "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_f32le", str(tmp),
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0 or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg a échoué sur {src} : {completed.stderr.strip()[-2000:]}")
    tmp.replace(dst)


def source_rate(path: Path) -> int:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", wavfile.WavFileWarning)  # blocs annexes du WAV source
        rate, _ = wavfile.read(path, mmap=True)
    return int(rate)


# --- Téléchargement et extraction (D20 §1) ------------------------------------------------


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {"revision": REVISION, "parquets": {}}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_name(STATE.name + ".part")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1))
    tmp.replace(STATE)


def remote_parquets(partition: str) -> list[tuple[str, int, str]]:
    """(chemin, taille, SHA-256 LFS) des Parquet d'une partition à la révision figée."""
    from huggingface_hub import HfApi

    info = HfApi().dataset_info(REPO_ID, revision=REVISION, files_metadata=True)
    if info.sha != REVISION:
        sys.exit(f"[summre] révision {info.sha} au lieu de {REVISION}")
    files = [
        (s.rfilename, s.size, s.lfs.sha256 if s.lfs else None)
        for s in info.siblings
        if s.rfilename.startswith(f"data/{partition}/") and s.rfilename.endswith(".parquet")
    ]
    return sorted(files)


def extract_parquet(name: str, expected_sha: str | None, known_sha: dict[str, str], partition: str) -> dict:
    """Télécharge un Parquet, extrait ses pistes et ses mots, puis supprime le brut."""
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download

    path = Path(hf_hub_download(
        REPO_ID, name, repo_type="dataset", revision=REVISION, local_dir=RAW_DIR,
    ))
    digest = sha256(path)
    if expected_sha and digest != expected_sha:
        raise RuntimeError(f"{name} : SHA-256 {digest} différent de celui du dépôt ({expected_sha})")
    if name in known_sha and known_sha[name] != digest:
        raise RuntimeError(f"{name} : SHA-256 {digest} différent du manifeste ({known_sha[name]})")

    out_dir = TRACKS_DIR / partition
    out_dir.mkdir(parents=True, exist_ok=True)
    tracks = []
    parquet = pq.ParquetFile(path)
    columns = ["meeting_id", "speaker_id", "audio_id", "audio", "segments"]
    for batch in parquet.iter_batches(batch_size=1, columns=columns):
        row = batch.to_pylist()[0]
        audio_id = row["audio_id"]
        tmp = out_dir / f"{audio_id}.source.wav"
        tmp.write_bytes(row["audio"]["bytes"])
        rate = source_rate(tmp)
        resample_to_float(tmp, out_dir / f"{audio_id}.wav")
        tmp.unlink()
        segments = [
            {"start": s["start"], "end": s["end"], "words": s["words"]} for s in row["segments"] or []
        ]
        (out_dir / f"{audio_id}.json").write_text(json.dumps({
            "meeting_id": row["meeting_id"], "speaker_id": row["speaker_id"], "audio_id": audio_id,
            "parquet": name, "frequence_source": rate, "segments": segments,
        }, ensure_ascii=False))
        tracks.append(audio_id)
        print(f"[summre] {name} : piste {audio_id} ({rate} Hz)", flush=True)
    record = {"sha256": digest, "taille": path.stat().st_size, "pistes": tracks, "partition": partition}
    path.unlink()  # le brut n'est supprimé qu'après extraction complète (D20 §1)
    return record


# --- Préparation d'une réunion ------------------------------------------------------------


def prepare_meeting(meeting: str, partition: str, track_ids: list[str]) -> dict:
    out_dir = TRACKS_DIR / partition
    infos = [json.loads((out_dir / f"{audio_id}.json").read_text()) for audio_id in track_ids]
    signals = []
    for audio_id in track_ids:
        rate, data = wavfile.read(out_dir / f"{audio_id}.wav")
        assert rate == SAMPLE_RATE and data.dtype == np.float32 and data.ndim == 1
        signals.append(data)
    mix = mix_tracks(signals)
    uri = uri_of(meeting)
    wav = PROCESSED_DIR / f"{uri}.wav"
    wav.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(wav.with_name(wav.name + ".part"), SAMPLE_RATE, to_pcm16(mix))
    wav.with_name(wav.name + ".part").replace(wav)
    duration = len(mix) / SAMPLE_RATE

    reference, missing = build_reference(infos)
    if not reference:
        raise RuntimeError(f"{uri} : aucun mot horodaté")
    RTTM_DIR.mkdir(parents=True, exist_ok=True)
    (RTTM_DIR / f"{uri}.rttm").write_text(rttm_text(uri, reference))
    uem = uem_bounds(reference, duration)
    UEM_DIR.mkdir(parents=True, exist_ok=True)
    (UEM_DIR / f"{uri}.uem").write_text(f"{uri} 1 {uem[0]:.3f} {uem[1]:.3f}\n")

    # Synchronisation : chaque piste contre le mélange des autres, à 8 kHz.
    from scipy.signal import resample_poly

    lags = {}
    if len(signals) > 1:
        padded = [np.pad(s, (0, len(mix) - len(s))).astype(np.float64) for s in signals]
        total = np.sum(padded, axis=0)
        for info, track in zip(infos, padded):
            others = total - track
            lags[info["speaker_id"]] = estimate_lag(
                resample_poly(track, 1, SAMPLE_RATE // SYNC_RATE),
                resample_poly(others, 1, SAMPLE_RATE // SYNC_RATE),
                SYNC_RATE, SYNC_SEARCH_S,
            )

    lexical, _ = build_reference(infos, skip=NON_LEXICAL_TOKENS)
    n_tokens = Counter(
        word.get("word") for info in infos for s in info["segments"] for word in s.get("words") or []
    )
    return {
        "uri": uri,
        "partition": partition,
        "zoom": is_zoom(meeting),
        "parquets": ";".join(sorted({info["parquet"] for info in infos})),
        "revision": REVISION,
        "licence": LICENCE,
        "duree_s": round(duration, 3),
        "n_pistes": len(infos),
        "n_locuteurs": len(reference),
        "locuteurs": ";".join(reference),
        "participants_sans_parole": ";".join(
            sorted(info["speaker_id"] for info in infos if info["speaker_id"] not in reference)
        ),
        "frequences_source": ";".join(str(f) for f in sorted({info["frequence_source"] for info in infos})),
        "mots_sans_horodatage": missing,
        "n_mots": sum(n_tokens.values()),
        "n_jetons_non_lexicaux": sum(n_tokens[t] for t in NON_LEXICAL_TOKENS),
        "parole_sans_jetons_non_lexicaux_s": round(speech_overlap(lexical, uem)["parole_s"], 3),
        "crete_melange": round(float(np.max(np.abs(mix))), 4),
        "decalages": format_lags(lags),
    }


def format_lags(lags: dict[str, tuple[float, float, float]]) -> str:
    """`locuteur:décalage_ms/coefficient/saillance`, séparés par des points-virgules."""
    return ";".join(f"{spk}:{1000 * lag:.1f}/{coef:.4f}/{sal:.1f}" for spk, (lag, coef, sal) in lags.items())


def parse_lags(text: str) -> dict[str, tuple[float, float, float]]:
    lags = {}
    for item in filter(None, text.split(";")):
        speaker, values = item.split(":")
        lag_ms, coef, sal = (float(v) for v in values.split("/"))
        lags[speaker] = (lag_ms / 1000, coef, sal)
    return lags


def sync_summary(text: str) -> tuple[float | None, list[str]]:
    """Plus grand décalage mesurable (s, None si aucun) et pistes non mesurables."""
    lags = parse_lags(text)
    measured = [lag for lag, _, sal in lags.values() if sal >= SYNC_MIN_SALIENCE]
    unmeasured = [spk for spk, (_, _, sal) in lags.items() if sal < SYNC_MIN_SALIENCE]
    return (max(measured, key=abs) if measured else None), unmeasured


# --- Lecture des sorties et statistiques --------------------------------------------------


def read_rttm(uri: str) -> dict[str, list[tuple[float, float]]]:
    reference: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for line in (RTTM_DIR / f"{uri}.rttm").read_text().splitlines():
        fields = line.split()
        start, length = float(fields[3]), float(fields[4])
        reference[fields[7]].append((start, start + length))
    return dict(reference)


def read_uem(uri: str) -> tuple[float, float]:
    fields = (UEM_DIR / f"{uri}.uem").read_text().split()
    return float(fields[2]), float(fields[3])


def check_meeting(row: dict) -> dict:
    """Contrôles de cohérence d'une réunion préparée ; ajoute parole et chevauchement."""
    uri = row["uri"]
    rate, data = wavfile.read(PROCESSED_DIR / f"{uri}.wav", mmap=True)
    duration = len(data) / rate
    reference, uem = read_rttm(uri), read_uem(uri)
    problems = []
    if rate != SAMPLE_RATE or data.dtype != np.int16 or data.ndim != 1:
        problems.append("signal non normalisé")
    if not 0.0 <= uem[0] < uem[1] <= duration + 1e-3:
        problems.append(f"UEM {uem} hors du signal ({duration:.3f} s)")
    for speaker, intervals in reference.items():
        if any(start < uem[0] - 1e-3 or end > uem[1] + 1e-3 for start, end in intervals):
            problems.append(f"segment de {speaker} hors UEM")
    n_speakers = len(reference)
    if not 2 <= n_speakers <= 4:
        problems.append(f"{n_speakers} locuteurs (2 à 4 attendus)")
    if problems:
        raise RuntimeError(f"{uri} : " + " ; ".join(problems))
    stats = speech_overlap(reference, uem)
    return row | {
        "uem_s": round(uem[1] - uem[0], 3),
        "parole_s": round(stats["parole_s"], 3),
        "chevauchement_s": round(stats["chevauchement_s"], 3),
        "par_locuteur_s": stats["par_locuteur_s"],
    }


def summarize(rows: list[dict], label: str) -> None:
    if not rows:
        return
    duration = sum(r["duree_s"] for r in rows)
    uem = sum(r["uem_s"] for r in rows)
    speech = sum(r["parole_s"] for r in rows)
    overlap = sum(r["chevauchement_s"] for r in rows)
    speaker_times = [t for r in rows for t in r["par_locuteur_s"].values()]
    speakers = {s for r in rows for s in r["par_locuteur_s"]}
    distribution = Counter(r["n_locuteurs"] for r in rows)
    print(
        f"[summre] {label} : {len(rows)} réunions, {sum(int(r['n_pistes']) for r in rows)} pistes, "
        f"{len(speakers)} locuteurs distincts ; locuteurs par réunion "
        f"{dict(sorted(distribution.items()))} ; signal {duration / 3600:.2f} h, UEM {uem / 3600:.2f} h, "
        f"parole {speech / 3600:.2f} h, chevauchement {overlap / 3600:.2f} h "
        f"({100 * overlap / speech:.1f} % de la parole) ; temps de parole par locuteur et par réunion : "
        f"médiane {np.median(speaker_times) / 60:.1f} min, min {min(speaker_times) / 60:.1f}, "
        f"max {max(speaker_times) / 60:.1f}"
    )


# --- Contrôle croisé (D20 §4) -------------------------------------------------------------


def cross_check(test_rows: list[dict]) -> list[tuple[str, float]]:
    """DER sans collar entre nos références du test et celles du dérivé, réunion par réunion."""
    from huggingface_hub import HfApi, hf_hub_download
    from pyannote.core import Annotation, Segment, Timeline
    from pyannote.metrics.diarization import DiarizationErrorRate

    info = HfApi().dataset_info(DERIVED_REPO_ID, revision=DERIVED_REVISION)
    names = sorted(s.rfilename for s in info.siblings if s.rfilename.endswith(".rttm"))
    for name in names:
        hf_hub_download(DERIVED_REPO_ID, name, repo_type="dataset", revision=DERIVED_REVISION,
                        local_dir=DERIVED_DIR)
    variants = {name.split("/")[0] for name in names}
    for variant in sorted(variants - {"summre-A"}):
        for name in names:
            if name.startswith("summre-A/"):
                other = DERIVED_DIR / name.replace("summre-A/", f"{variant}/", 1)
                if (DERIVED_DIR / name).read_bytes() != other.read_bytes():
                    print(f"[summre] contrôle croisé : {name} diffère dans {variant}")

    results = []
    for row in test_rows:
        uri = row["uri"]
        meeting = uri.removeprefix(f"{CORPUS}__")
        path = DERIVED_DIR / "summre-A" / "rttm" / f"{meeting}.rttm"
        if not path.exists():
            print(f"[summre] contrôle croisé : {meeting} absent du dérivé")
            continue
        reference, hypothesis = Annotation(uri=uri), Annotation(uri=uri)
        for speaker, intervals in read_rttm(uri).items():
            for start, end in intervals:
                reference[Segment(start, end)] = speaker
        for line in path.read_text().splitlines():
            fields = line.split()
            if not fields or fields[0] != "SPEAKER":
                continue
            start, length = float(fields[3]), float(fields[4])
            hypothesis[Segment(start, start + length)] = fields[7]
        low, high = read_uem(uri)
        metric = DiarizationErrorRate(collar=0.0, skip_overlap=False)
        der = metric(reference, hypothesis, uem=Timeline([Segment(low, high)]))
        results.append((uri, 100 * der))
    shutil.rmtree(DERIVED_DIR)  # le dérivé ne sert qu'à ce contrôle (D20 §4)
    return results


# --- Programme principal ------------------------------------------------------------------


def read_manifest() -> list[dict]:
    if not MANIFEST.exists():
        return []
    with MANIFEST.open() as handle:
        return list(csv.DictReader(handle))


MANIFEST_COLUMNS = [
    "uri", "partition", "zoom", "parquets", "sha256", "revision", "licence", "duree_s", "n_pistes",
    "n_locuteurs", "locuteurs", "participants_sans_parole", "frequences_source", "mots_sans_horodatage",
    "n_mots", "n_jetons_non_lexicaux", "parole_sans_jetons_non_lexicaux_s", "crete_melange",
    "decalages",
]


def prepare_partition(partition: str, state: dict, known_sha: dict[str, str]) -> list[dict]:
    expected_meetings, expected_tracks = PARTITIONS[partition]
    files = remote_parquets(partition)
    for name, size, lfs_sha in files:
        if name in state["parquets"]:
            continue
        print(f"[summre] {name} ({size / 1e6:.0f} Mo)", flush=True)
        state["parquets"][name] = extract_parquet(name, lfs_sha, known_sha, partition)
        save_state(state)

    tracks: dict[str, list[str]] = defaultdict(list)
    out_dir = TRACKS_DIR / partition
    for name, _, _ in files:
        for audio_id in state["parquets"][name]["pistes"]:
            meeting = json.loads((out_dir / f"{audio_id}.json").read_text())["meeting_id"]
            tracks[meeting].append(audio_id)
    n_tracks = sum(len(ids) for ids in tracks.values())
    if (len(tracks), n_tracks) != (expected_meetings, expected_tracks):
        sys.exit(f"[summre] {partition} : {len(tracks)} réunions et {n_tracks} pistes, "
                 f"{expected_meetings} et {expected_tracks} attendues")

    rows = []
    for meeting in sorted(tracks):
        row = prepare_meeting(meeting, partition, sorted(tracks[meeting]))
        row["sha256"] = ";".join(
            state["parquets"][name]["sha256"] for name in row["parquets"].split(";")
        )
        rows.append(row)
        print(f"[summre] {row['uri']} : {row['n_pistes']} pistes, {row['n_locuteurs']} locuteurs, "
              f"{row['duree_s']:.0f} s, décalages {row['decalages']}", flush=True)
    shutil.rmtree(out_dir)  # pistes intermédiaires
    return rows


def partition_done(partition: str, manifest: list[dict]) -> bool:
    rows = [r for r in manifest if r["partition"] == partition]
    return len(rows) == PARTITIONS[partition][0] and all(
        (PROCESSED_DIR / f"{r['uri']}.wav").exists() and (RTTM_DIR / f"{r['uri']}.rttm").exists()
        and (UEM_DIR / f"{r['uri']}.uem").exists()
        for r in rows
    )


def choose_timing(test_rows: list[dict]) -> list[str]:
    low, high = TIMING_TOTAL_RANGE_S
    presential = [r for r in test_rows if not r["zoom"]]
    zoom = [r for r in test_rows if r["zoom"]]
    for first in presential:
        for second in zoom:
            if low <= first["duree_s"] + second["duree_s"] <= high:
                return [first["uri"], second["uri"]]
    sys.exit("[summre] aucune paire présentiel + Zoom de 30 à 45 min dans test")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Voir l'en-tête du script et docs/decisions/D20-preparation-summ-re.md.",
    )
    parser.parse_args()

    manifest = read_manifest()
    known_sha = {}
    for row in manifest:
        known_sha.update(zip(row["parquets"].split(";"), row["sha256"].split(";")))
    state = load_state()
    if state.get("revision") != REVISION:
        sys.exit(f"[summre] {STATE} porte sur une autre révision ({state.get('revision')})")

    rows = []
    for partition in PARTITIONS:
        if partition_done(partition, manifest):
            print(f"[summre] {partition} déjà préparée : statistiques recalculées depuis les sorties")
            rows += [dict(r, zoom=r["zoom"] == "True", duree_s=float(r["duree_s"]),
                          n_locuteurs=int(r["n_locuteurs"]))
                     for r in manifest if r["partition"] == partition]
        else:
            rows += prepare_partition(partition, state, known_sha)

    rows = [check_meeting(row) for row in rows]

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    SPLITS_DIR.mkdir(parents=True, exist_ok=True)
    for partition in PARTITIONS:
        part = [r for r in rows if r["partition"] == partition]
        (SPLITS_DIR / f"{partition}.txt").write_text("\n".join(r["uri"] for r in part) + "\n")
        (SPLITS_DIR / f"zoom_{partition}.txt").write_text(
            "".join(f"{r['uri']}\n" for r in part if r["zoom"])
        )
    test_rows = [r for r in rows if r["partition"] == "test"]
    timing = choose_timing(test_rows)
    (SPLITS_DIR / "temps.txt").write_text("\n".join(timing) + "\n")

    # Statistiques (D20 §4).
    for partition in PARTITIONS:
        part = [r for r in rows if r["partition"] == partition]
        summarize(part, partition)
        summarize([r for r in part if r["zoom"]], f"{partition} Zoom")
    summarize([r for r in rows if r["zoom"]], "dev + test Zoom")
    speakers = {p: {s for r in rows if r["partition"] == p for s in r["par_locuteur_s"]} for p in PARTITIONS}
    common = sorted(speakers["dev"] & speakers["test"])
    print(f"[summre] locuteurs communs à dev et test : {len(common)} ({', '.join(common)})")
    sync = {r["uri"]: sync_summary(r["decalages"]) for r in rows}
    desync = [uri for uri, (lag, _) in sync.items() if lag is not None and abs(lag) > SYNC_MAX_LAG_S]
    n_unmeasured = sum(len(unmeasured) for _, unmeasured in sync.values())
    fully_unmeasured = [uri for uri, (lag, _) in sync.items() if lag is None]
    print(f"[summre] synchronisation : {len(desync)} réunions avec un décalage mesurable "
          f"> {1000 * SYNC_MAX_LAG_S:.0f} ms ; {n_unmeasured} pistes non mesurables (saillance "
          f"< {SYNC_MIN_SALIENCE:g}) ; {len(fully_unmeasured)} réunions sans aucune piste mesurable")
    for uri in desync:
        print(f"  {uri} : {next(r['decalages'] for r in rows if r['uri'] == uri)}")
    for uri in fully_unmeasured:
        print(f"  non mesurable : {uri} (Zoom : {is_zoom(uri.removeprefix(CORPUS + '__'))})")
    measured = [abs(lag) for lag, _ in sync.values() if lag is not None]
    if measured:
        print(f"[summre] plus grand décalage mesurable par réunion : médiane "
              f"{1000 * np.median(measured):.1f} ms, max {1000 * max(measured):.1f} ms")
    missing = {r["uri"]: int(r["mots_sans_horodatage"]) for r in rows if int(r["mots_sans_horodatage"])}
    detail = ", ".join(f"{uri}={n}" for uri, n in missing.items())
    print(f"[summre] mots sans horodatage : {sum(missing.values())} ({detail})")
    for partition in PARTITIONS:
        part = [r for r in rows if r["partition"] == partition]
        speech = sum(r["parole_s"] for r in part)
        lexical = sum(float(r["parole_sans_jetons_non_lexicaux_s"]) for r in part)
        print(f"[summre] {partition} : jetons non lexicaux {sum(int(r['n_jetons_non_lexicaux']) for r in part)} "
              f"sur {sum(int(r['n_mots']) for r in part)} ; parole sans eux {lexical / 3600:.3f} h "
              f"contre {speech / 3600:.3f} h ({100 * (speech - lexical) / speech:.2f} %)")
    print(f"[summre] temps.txt : {', '.join(timing)} "
          f"({sum(r['duree_s'] for r in rows if r['uri'] in timing) / 60:.1f} min)")
    print(f"[summre] crête maximale d'un mélange : {max(float(r['crete_melange']) for r in rows):.4f}")

    ders = cross_check(test_rows)
    print("[summre] contrôle croisé (DER sans collar, nos références contre le dérivé) :")
    for uri, der in ders:
        print(f"  {uri} {der:.2f} %")
    if ders:
        values = [d for _, d in ders]
        print(f"[summre] contrôle croisé : {len(ders)} réunions, min {min(values):.2f} %, "
              f"médiane {np.median(values):.2f} %, max {max(values):.2f} %")


if __name__ == "__main__":
    main()
