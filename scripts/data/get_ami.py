"""Préparation d'AMI, micro distant (SDM, Array1-01), partitions dev et test.

Partition et références : dépôt pyannote/AMI-diarization-setup, figé au commit
SETUP_COMMIT (docs/corpus.md §3). Signal : miroir AMI d'Édimbourg.

Étapes :
1. téléchargement, dans data/raw/ami/, du signal Array1-01 de chaque réunion des
   listes dev (18) et test (16), de son RTTM `only_words` et de son UEM (commun aux deux
   variantes d'annotation) ;
2. vérification de la somme SHA-256 du signal brut contre le manifeste s'il existe déjà ;
3. normalisation (whospoke.audio, D15/D16) vers data/processed/ami/ami__<réunion>.wav ;
4. réécriture du champ uri en ami__<réunion> : RTTM dans data/processed/ami/rttm/,
   UEM dans data/splits/ami/uem/ (versionnés, protocole §2) ;
5. contrôles de cohérence RTTM / UEM / audio ;
6. écriture de data/manifests/ami.csv et de data/splits/ami/{dev,test,temps}.txt.

Usage : uv run python scripts/data/get_ami.py [--jobs 4]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from whospoke.audio import SAMPLE_RATE, load_waveform, normalize

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw" / "ami"
PROCESSED_DIR = REPO_ROOT / "data" / "processed" / "ami"
RTTM_DIR = PROCESSED_DIR / "rttm"
SPLITS_DIR = REPO_ROOT / "data" / "splits" / "ami"
UEM_DIR = SPLITS_DIR / "uem"
MANIFEST = REPO_ROOT / "data" / "manifests" / "ami.csv"

CORPUS = "ami"
SETUP_COMMIT = "67c2d539286e89f68952d5dcf83912bd9f01dfae"
SETUP_BASE = f"https://raw.githubusercontent.com/pyannote/AMI-diarization-setup/{SETUP_COMMIT}"
AUDIO_BASE = "https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus"
LICENCE = "CC BY 4.0"
PARTITIONS = {"dev": 18, "test": 16}

# Sous-ensemble de mesure du temps en CPU seul (protocole §3.5), dans la partition de test.
# ES2004a (17,5 min) : réunion de la vérification V5, pour la continuité des mesures.
# TS3003a (25,1 min) : autre site d'enregistrement (TNO) et autre salle, pour ne pas
# mesurer le temps sur une seule acoustique ; c'est, parmi les réunions de test d'un autre
# site, la plus longue qui garde le total dans la fourchette (42,6 min), afin d'avoir le
# plus d'audio possible pour stabiliser la mesure.
TIMING_MEETINGS = ("ES2004a", "TS3003a")
TIMING_TOTAL_RANGE_S = (30 * 60.0, 45 * 60.0)

# Tolérance sur les fins d'UEM et de RTTM au-delà de la fin du signal.
END_TOLERANCE_S = 1.0


def uri_of(meeting: str) -> str:
    return f"{CORPUS}__{meeting}"


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read().decode("utf-8")


def download(url: str, target: Path, attempts: int = 5) -> None:
    """Téléchargement avec reprises : les erreurs HTTP ou réseau transitoires (le miroir
    d'Édimbourg renvoie parfois 403 sous charge) sont retentées après une attente croissante."""
    for attempt in range(1, attempts + 1):
        try:
            return _download_once(url, target)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            if attempt == attempts:
                raise
            wait = 30 * attempt
            print(f"[ami] échec ({error}) sur {url}, nouvel essai dans {wait} s", flush=True)
            time.sleep(wait)


def _download_once(url: str, target: Path) -> None:
    """Téléchargement en continu vers un fichier .part, renommé à la fin.

    Un .part laissé par une interruption est repris à partir de sa taille (en-tête Range).
    """
    if target.exists() and target.stat().st_size > 0:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".part")
    offset = tmp.stat().st_size if tmp.exists() else 0
    request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
    print(f"[ami] téléchargement : {url}" + (f" (reprise à {offset} octets)" if offset else ""), flush=True)
    with urllib.request.urlopen(request, timeout=120) as response:
        if offset and response.status != 206:
            offset = 0  # le serveur ignore Range : on repart de zéro
        length = response.headers.get("Content-Length")
        expected = offset + int(length) if length is not None else None
        with tmp.open("ab" if offset else "wb") as handle:
            shutil.copyfileobj(response, handle, length=1 << 20)
    # Une connexion close prématurément ne lève pas d'erreur : on contrôle la taille.
    size = tmp.stat().st_size
    if expected is not None and size != expected:
        raise ConnectionError(f"{url} : {size} octets reçus sur {expected}")
    tmp.rename(target)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sources(meeting: str, partition: str) -> dict[str, str]:
    return {
        "audio": f"{AUDIO_BASE}/{meeting}/audio/{meeting}.Array1-01.wav",
        "rttm": f"{SETUP_BASE}/only_words/rttms/{partition}/{meeting}.rttm",
        # Pas d'UEM propre à only_words : l'UEM est commun aux deux variantes.
        "uem": f"{SETUP_BASE}/uems/{partition}/{meeting}.uem",
    }


def raw_paths(meeting: str) -> dict[str, Path]:
    return {
        "audio": RAW_DIR / f"{meeting}.Array1-01.wav",
        "rttm": RAW_DIR / f"{meeting}.rttm",
        "uem": RAW_DIR / f"{meeting}.uem",
    }


def rewrite_uri(text: str, meeting: str, field: int) -> tuple[str, int]:
    """Remplace le champ uri (index `field`) ; vérifie qu'il valait bien `meeting`."""
    lines, count = [], 0
    for line in text.splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[field] != meeting:
            raise ValueError(f"{meeting} : uri inattendu {fields[field]!r} dans « {line} »")
        fields[field] = uri_of(meeting)
        lines.append(" ".join(fields))
        count += 1
    return "\n".join(lines) + "\n", count


def prepare_meeting(meeting: str, partition: str, known_sha: dict[str, str]) -> dict:
    urls, raw = sources(meeting, partition), raw_paths(meeting)
    for kind in ("audio", "rttm", "uem"):
        download(urls[kind], raw[kind])

    uri = uri_of(meeting)
    digest = sha256(raw["audio"])
    if uri in known_sha and known_sha[uri] != digest:
        raise RuntimeError(f"{uri} : SHA-256 différent du manifeste ({digest} ≠ {known_sha[uri]})")

    wav = PROCESSED_DIR / f"{uri}.wav"
    if not wav.exists():
        normalize(raw["audio"], wav)

    rttm_text, n_segments = rewrite_uri(raw["rttm"].read_text(), meeting, field=1)
    uem_text, n_uem = rewrite_uri(raw["uem"].read_text(), meeting, field=0)
    RTTM_DIR.mkdir(parents=True, exist_ok=True)
    UEM_DIR.mkdir(parents=True, exist_ok=True)
    (RTTM_DIR / f"{uri}.rttm").write_text(rttm_text)
    (UEM_DIR / f"{uri}.uem").write_text(uem_text)

    return {
        "uri": uri,
        "partition": partition,
        "url_source": urls["audio"],
        "url_reference": urls["rttm"],
        "licence": LICENCE,
        "sha256": digest,
        "n_segments": n_segments,
        "n_uem": n_uem,
    }


def check_meeting(row: dict) -> dict:
    """Contrôles de cohérence ; ajoute durée audio, étendue UEM, parole et locuteurs."""
    uri = row["uri"]
    waveform, sample_rate = load_waveform(PROCESSED_DIR / f"{uri}.wav")
    duration = waveform.shape[1] / sample_rate
    assert sample_rate == SAMPLE_RATE

    uem = []
    for line in (UEM_DIR / f"{uri}.uem").read_text().splitlines():
        fields = line.split()
        uem.append((float(fields[2]), float(fields[3])))
    problems = []
    for start, end in uem:
        if not 0.0 <= start < end:
            problems.append(f"UEM invalide {start}–{end}")
        if end > duration + END_TOLERANCE_S:
            problems.append(f"UEM au-delà du signal ({end:.2f} > {duration:.2f} s)")

    speakers, speech, last_end = set(), 0.0, 0.0
    for line in (RTTM_DIR / f"{uri}.rttm").read_text().splitlines():
        fields = line.split()
        if fields[0] != "SPEAKER" or fields[1] != uri:
            problems.append(f"ligne RTTM inattendue : {line}")
            continue
        start, length = float(fields[3]), float(fields[4])
        if length <= 0.0:
            problems.append(f"segment de durée nulle ou négative : {line}")
        speakers.add(fields[7])
        speech += length
        last_end = max(last_end, start + length)
    if last_end > duration + END_TOLERANCE_S:
        problems.append(f"RTTM au-delà du signal ({last_end:.2f} > {duration:.2f} s)")
    if uem and last_end > max(end for _, end in uem) + END_TOLERANCE_S:
        problems.append(f"RTTM au-delà de l'UEM ({last_end:.2f} s)")
    if problems:
        raise RuntimeError(f"{uri} : " + " ; ".join(problems))

    return row | {
        "duree_s": round(duration, 3),
        "uem_s": round(sum(end - start for start, end in uem), 3),
        "parole_cumulee_s": round(speech, 2),
        "n_locuteurs": len(speakers),
    }


def read_known_sha() -> dict[str, str]:
    if not MANIFEST.exists():
        return {}
    with MANIFEST.open() as handle:
        return {row["uri"]: row["sha256"] for row in csv.DictReader(handle)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jobs", type=int, default=4, help="téléchargements simultanés")
    args = parser.parse_args()

    meetings: list[tuple[str, str]] = []
    for partition, expected in PARTITIONS.items():
        listed = fetch_text(f"{SETUP_BASE}/lists/{partition}.meetings.txt").split()
        if len(listed) != expected:
            sys.exit(f"[ami] {partition} : {len(listed)} réunions listées, {expected} attendues")
        meetings += [(meeting, partition) for meeting in listed]

    known_sha = read_known_sha()
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        rows = list(pool.map(lambda mp: prepare_meeting(*mp, known_sha), meetings))
    rows = [check_meeting(row) for row in rows]

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    columns = ["uri", "partition", "url_source", "url_reference", "licence", "duree_s", "sha256"]
    with MANIFEST.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    SPLITS_DIR.mkdir(parents=True, exist_ok=True)
    by_uri = {row["uri"]: row for row in rows}
    for partition in PARTITIONS:
        uris = [row["uri"] for row in rows if row["partition"] == partition]
        (SPLITS_DIR / f"{partition}.txt").write_text("\n".join(uris) + "\n")

    timing = [uri_of(meeting) for meeting in TIMING_MEETINGS]
    if any(by_uri[uri]["partition"] != "test" for uri in timing):
        sys.exit("[ami] le sous-ensemble de mesure du temps doit appartenir à test")
    timing_total = sum(by_uri[uri]["duree_s"] for uri in timing)
    low, high = TIMING_TOTAL_RANGE_S
    if not low <= timing_total <= high:
        sys.exit(f"[ami] temps.txt : {timing_total / 60:.1f} min hors de la fourchette 30–45 min")
    (SPLITS_DIR / "temps.txt").write_text("\n".join(timing) + "\n")

    print("\n[ami] réunion, partition, durée (s), UEM (s), parole cumulée (s), locuteurs")
    for row in rows:
        print(
            f"  {row['uri']:<16} {row['partition']:<5} {row['duree_s']:>9.1f} "
            f"{row['uem_s']:>9.1f} {row['parole_cumulee_s']:>9.1f} {row['n_locuteurs']:>3}"
        )
    for partition in PARTITIONS:
        part = [row for row in rows if row["partition"] == partition]
        print(
            f"[ami] {partition} : {len(part)} réunions, "
            f"{sum(row['duree_s'] for row in part) / 3600:.2f} h de signal, "
            f"{sum(row['uem_s'] for row in part) / 3600:.2f} h d'UEM"
        )
    print(f"[ami] temps.txt : {', '.join(timing)} ({timing_total / 60:.1f} min)")


if __name__ == "__main__":
    main()
