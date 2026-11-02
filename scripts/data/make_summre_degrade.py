"""Génération de SUMM-RE test dégradé (D24) et du dossier d'écoute de contrôle.

Usage :
    uv run python scripts/data/make_summre_degrade.py --etat
    uv run python scripts/data/make_summre_degrade.py --telecharger-pistes
    uv run python scripts/data/make_summre_degrade.py
    uv run python scripts/data/make_summre_degrade.py --conditions bru15 cod08
    uv run python scripts/data/make_summre_degrade.py --ecoute-seulement

Configuration : `configs/summre_degrade.yaml` (graine, salle, bruits, conditions, écoute).
Son SHA-256 est consigné dans le manifeste et dans `generation.json`.

Sources :
- mélanges de SUMM-RE test (`data/processed/summre/`), pour le bruit et le codec ;
- pistes individuelles de micros-casques de SUMM-RE test, pour la réverbération (cas
  réaliste de D24 §1) : `data/raw/summre/pistes/test/` (flottant 32 bits, 16 kHz), obtenues
  par `--telecharger-pistes`, qui retélécharge les Parquet de test à la révision figée de
  D20 (SHA-256 contrôlé contre le dépôt et contre `data/raw/summre/etat.json`) par la
  fonction d'extraction de `get_summre.py`. Pour chaque réunion, le mélange des pistes
  (même chaîne que D20 §2) doit reproduire exactement le mélange existant, sinon la
  génération s'arrête. Option `--repli-melange` : une réponse impulsionnelle unique est
  appliquée au mélange (repli de D24 si les pistes manquent), et c'est consigné ;
- bruits DEMAND (Zenodo 1227121, version 16 kHz, canal 1), téléchargés au besoin dans
  `data/raw/demand/` (MD5 contrôlé contre Zenodo, SHA-256 consigné dans
  `data/manifests/demand.csv`).

Conditions (D24 §1) : réverbération simulée par pyroomacoustics (méthode des images, salle
parallélépipédique, absorption et ordre maximal par `inverse_sabine`, micro au centre de la
table, chaque locuteur à une position distincte ; RT60 mesuré sur chaque réponse en T20 et
en T60, consignés : la cible est atteinte en T20, le T60 la dépasse d'environ 30 à 45 %) ; bruit additif à un RSB calculé sur les
zones de parole de la référence (dans l'UEM), la puissance du bruit étant mesurée sur ces
mêmes zones ; codec Opus (libopus, ffmpeg, application voip), décodé et ramené à 16 kHz ;
`salle` combine réverbération et bruit. Les positions des locuteurs et l'affectation des
bruits sont tirées une fois par réunion (graine, identifiant de la réunion) : elles sont
les mêmes pour toutes les conditions qui les utilisent.

Niveaux : le mélange réverbéré est ramené à la valeur efficace du mélange propre sur les
zones de parole ; le délai de propagation directe de chaque locuteur est retranché de sa
réponse impulsionnelle (il reste le délai fixe du filtre de pyroomacoustics, consigné). Si
la crête d'un signal produit dépasse PEAK_MAX, tout le signal est atténué (gain consigné) :
aucun écrêtage. Sorties en PCM 16 bits, 16 kHz mono, dans
`data/processed/summre_degrade/<condition>/<uri>.wav` (non versionné) ; références et UEM
inchangés (ceux de SUMM-RE test).

Traçabilité : `data/manifests/summre_degrade.csv` (versionné) donne, par condition et par
réunion, le SHA-256 du WAV produit, la crête, le gain et l'affectation (positions,
environnement de bruit, décalage, RT60 mesuré, décalage du codec). Si le manifeste existe,
toute régénération est comparée à lui et une différence arrête le script.
`data/processed/summre_degrade/generation.json` consigne la date, le commit, l'état de
l'arbre, les versions et les options.

Écoute de contrôle (D24 §1) : trois extraits de `ecoute.duree_s` secondes, aux mêmes
instants pour toutes les conditions et pour `propre`, dans
`data/processed/summre_degrade/ecoute/` (non versionné), avec une page `index.html` de
lecture locale. Réunions tirées par la graine (une réunion Zoom, deux en présentiel) ;
fenêtre choisie, dans l'UEM, pour le plus grand nombre de locuteurs actifs, puis la plus
grande durée de parole. S'y ajoutent les premières `ecoute.duree_s` secondes de chaque bruit
DEMAND seul (canal utilisé, niveau d'origine), pour vérifier qu'aucun ne contient de parole
intelligible, quel que soit le bruit affecté aux trois extraits.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
import zlib
from datetime import datetime
from importlib.metadata import version as _version
from pathlib import Path

import whospoke  # noqa: F401  (D27 : télémétrie coupée avant tout import tiers)
import numpy as np
import yaml
from scipy.io import wavfile
from scipy.signal import oaconvolve

sys.path.insert(0, str(Path(__file__).resolve().parent))
import get_summre as summre  # noqa: E402  (extraction et mélange de D20)

from whospoke.experiment import (  # noqa: E402
    REPO_ROOT,
    dataset_uris,
    git_state,
    load_rttm,
    load_uem,
    processed_wav,
    reference_rttm,
    uem_path,
)

CONFIG = REPO_ROOT / "configs" / "summre_degrade.yaml"
TRACKS_DIR = summre.TRACKS_DIR / "test"
DEMAND_DIR = REPO_ROOT / "data" / "raw" / "demand"
DEMAND_RECORD = "1227121"
DEMAND_API = f"https://zenodo.org/api/records/{DEMAND_RECORD}"
DEMAND_LICENCE = "CC BY-SA 3.0 (DEMAND.pdf ; métadonnées Zenodo : CC BY 4.0)"
MANIFEST = REPO_ROOT / "data" / "manifests" / "summre_degrade.csv"
DEMAND_MANIFEST = REPO_ROOT / "data" / "manifests" / "demand.csv"
SAMPLE_RATE = summre.SAMPLE_RATE
PEAK_MAX = 0.99
EXPECTED_TEST = summre.PARTITIONS["test"]   # (réunions, pistes)
MIN_FREE_GB_PER_CONDITION = 1.6

MANIFEST_COLUMNS = ["condition", "uri", "sha256", "duree_s", "crete", "gain", "details", "config_sha256"]
DEMAND_COLUMNS = ["environnement", "fichier", "taille", "md5_zenodo", "sha256", "canal", "licence", "source"]


# --- Configuration et utilitaires -----------------------------------------------------


def load_config() -> tuple[dict, str]:
    raw = CONFIG.read_bytes()
    return yaml.safe_load(raw), hashlib.sha256(raw).hexdigest()


def file_sha256(path: Path) -> str:
    return summre.sha256(path)


def meeting_rng(seed: int, uri: str) -> np.random.Generator:
    """Générateur propre à une réunion : indépendant de l'ordre et des conditions demandées."""
    return np.random.default_rng([seed, zlib.crc32(uri.encode())])


def free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1e9


def read_pcm16(path: Path) -> np.ndarray:
    rate, data = wavfile.read(path)
    if rate != SAMPLE_RATE or data.dtype != np.int16 or data.ndim != 1:
        raise ValueError(f"{path} : WAV PCM 16 bits mono à {SAMPLE_RATE} Hz attendu")
    return data


def speech_mask(uri: str, n: int) -> np.ndarray:
    """Échantillons de parole de la référence dans l'UEM (base du RSB et des niveaux)."""
    reference = load_rttm(reference_rttm("summre", uri), uri)
    uem = load_uem(uem_path("summre", uri), uri)
    mask = np.zeros(n, dtype=bool)
    for segment in reference.get_timeline().support().crop(uem):
        mask[int(segment.start * SAMPLE_RATE): int(segment.end * SAMPLE_RATE)] = True
    return mask


def rms(signal: np.ndarray, mask: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(signal[mask], dtype=np.float64))))


def finalize(signal: np.ndarray) -> tuple[np.ndarray, float]:
    """PCM 16 bits sans écrêtage : atténuation globale si la crête dépasse PEAK_MAX."""
    peak = float(np.max(np.abs(signal)))
    gain = PEAK_MAX / peak if peak > PEAK_MAX else 1.0
    return summre.to_pcm16(signal * gain), gain


def write_wav(path: Path, data: np.ndarray) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    wavfile.write(tmp, SAMPLE_RATE, data)
    tmp.replace(path)
    return file_sha256(path)


# --- Pistes individuelles de SUMM-RE test ---------------------------------------------


def local_tracks() -> dict[str, list[dict]]:
    """Pistes présentes localement, par uri de réunion (triées par audio_id, comme D20)."""
    tracks: dict[str, list[dict]] = {}
    if not TRACKS_DIR.is_dir():
        return tracks
    for meta in sorted(TRACKS_DIR.glob("*.json")):
        info = json.loads(meta.read_text())
        if (TRACKS_DIR / f"{info['audio_id']}.wav").is_file():
            tracks.setdefault(summre.uri_of(info["meeting_id"]), []).append(info)
    for infos in tracks.values():
        infos.sort(key=lambda info: info["audio_id"])
    return tracks


def tracks_complete(tracks: dict[str, list[dict]], uris: list[str]) -> bool:
    n_tracks = sum(len(tracks.get(uri, [])) for uri in uris)
    return set(uris) <= set(tracks) and (len(uris), n_tracks) == EXPECTED_TEST


def download_tracks() -> None:
    """Retéléchargement des Parquet de test (D20, révision figée) et extraction des pistes."""
    state = summre.load_state()
    known_sha = {name: record["sha256"] for name, record in state["parquets"].items()}
    files = summre.remote_parquets("test")
    t0 = time.perf_counter()
    for name, size, lfs_sha in files:
        expected = state["parquets"].get(name, {}).get("pistes", [])
        if expected and all((TRACKS_DIR / f"{a}.wav").is_file() for a in expected):
            continue
        if free_gb(REPO_ROOT) < 5.0:
            sys.exit(f"[degrade] moins de 5 Go libres : téléchargement de {name} refusé")
        print(f"[degrade] {name} ({size / 1e6:.0f} Mo), {time.perf_counter() - t0:.0f} s écoulées",
              flush=True)
        record = summre.extract_parquet(name, lfs_sha, known_sha, "test")
        if expected and sorted(record["pistes"]) != sorted(expected):
            raise RuntimeError(f"{name} : pistes {record['pistes']} au lieu de {expected}")
    print(f"[degrade] pistes de test extraites en {time.perf_counter() - t0:.0f} s", flush=True)


def load_tracks(infos: list[dict]) -> list[np.ndarray]:
    signals = []
    for info in infos:
        rate, data = wavfile.read(TRACKS_DIR / f"{info['audio_id']}.wav")
        assert rate == SAMPLE_RATE and data.dtype == np.float32 and data.ndim == 1
        signals.append(data)
    return signals


# --- Bruits DEMAND --------------------------------------------------------------------


def demand_channel(env: str, channel: str) -> Path:
    return DEMAND_DIR / env / f"{channel}.wav"


def fetch_demand(envs: list[str], channel: str) -> None:
    """Télécharge au besoin la version 16 kHz de chaque environnement (MD5 contrôlé)."""
    missing = [env for env in envs if not demand_channel(env, channel).is_file()]
    if not missing:
        return
    with urllib.request.urlopen(DEMAND_API, timeout=60) as response:
        files = {f["key"]: f for f in json.load(response)["files"]}
    rows = {}
    if DEMAND_MANIFEST.exists():
        with DEMAND_MANIFEST.open() as handle:
            rows = {row["environnement"]: row for row in csv.DictReader(handle)}
    DEMAND_DIR.mkdir(parents=True, exist_ok=True)
    for env in missing:
        key = f"{env}_16k.zip"
        meta = files[key]
        archive = DEMAND_DIR / key
        print(f"[degrade] DEMAND {key} ({meta['size'] / 1e6:.0f} Mo)", flush=True)
        urllib.request.urlretrieve(f"{DEMAND_API}/files/{key}/content", archive)
        md5 = hashlib.md5(archive.read_bytes()).hexdigest()
        if f"md5:{md5}" != meta["checksum"]:
            raise RuntimeError(f"{key} : MD5 {md5} différent de Zenodo ({meta['checksum']})")
        digest = file_sha256(archive)
        if env in rows and rows[env]["sha256"] != digest:
            raise RuntimeError(f"{key} : SHA-256 {digest} différent du manifeste")
        with zipfile.ZipFile(archive) as bundle:
            names = [n for n in bundle.namelist() if n.endswith(f"/{channel}.wav")]
            if len(names) != 1:
                raise RuntimeError(f"{key} : canal {channel} introuvable ({names})")
            target = demand_channel(env, channel)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bundle.read(names[0]))
        rows[env] = {
            "environnement": env, "fichier": key, "taille": archive.stat().st_size,
            "md5_zenodo": md5, "sha256": digest, "canal": channel,
            "licence": DEMAND_LICENCE, "source": f"zenodo.org/records/{DEMAND_RECORD}",
        }
        archive.unlink()  # seul le canal utilisé est conservé
    with DEMAND_MANIFEST.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DEMAND_COLUMNS)
        writer.writeheader()
        writer.writerows(rows[env] for env in sorted(rows))


def load_noise(env: str, channel: str) -> np.ndarray:
    rate, data = wavfile.read(demand_channel(env, channel))
    if rate != SAMPLE_RATE or data.ndim != 1:
        raise ValueError(f"DEMAND {env}/{channel} : mono {SAMPLE_RATE} Hz attendu")
    scale = 32768.0 if data.dtype == np.int16 else 1.0
    return data.astype(np.float64) / scale


def looped(noise: np.ndarray, n: int, offset: int, fade: int) -> np.ndarray:
    """Bruit de longueur n à partir de `offset`, bouclé avec un fondu enchaîné à puissance constante."""
    ramp = np.linspace(0.0, 1.0, fade)
    fade_in, fade_out = np.sqrt(ramp), np.sqrt(1.0 - ramp)
    out = noise[offset:].copy()
    while len(out) < n:
        out[-fade:] = out[-fade:] * fade_out + noise[:fade] * fade_in
        out = np.concatenate([out, noise[fade:]])
    return out[:n]


def add_noise(signal: np.ndarray, noise: np.ndarray, mask: np.ndarray, snr_db: float) -> tuple[np.ndarray, float]:
    """Ajoute le bruit au RSB voulu, puissances mesurées sur les zones de parole."""
    p_signal = np.mean(np.square(signal[mask], dtype=np.float64))
    p_noise = np.mean(np.square(noise[mask], dtype=np.float64))
    gain = float(np.sqrt(p_signal / (p_noise * 10.0 ** (snr_db / 10.0))))
    return signal + gain * noise, gain


# --- Réverbération --------------------------------------------------------------------


def place_speakers(n: int, rng: np.random.Generator, room: dict) -> list[dict]:
    """Positions distinctes autour du micro (distance, azimut), dans la salle avec une marge."""
    dims = np.asarray(room["dimensions_m"], dtype=float)
    mic = np.asarray(room["micro_m"], dtype=float)
    d_min, d_max = room["distance_m"]
    margin, gap = room["marge_mur_m"], np.deg2rad(room["ecart_angulaire_min_deg"])
    for _ in range(10000):
        azimuths = rng.uniform(0.0, 2.0 * np.pi, n)
        distances = rng.uniform(d_min, d_max, n)
        xy = mic[:2] + np.stack([distances * np.cos(azimuths), distances * np.sin(azimuths)], axis=1)
        inside = np.all((xy >= margin) & (xy <= dims[:2] - margin))
        ordered = np.sort(azimuths)
        gaps = np.diff(np.concatenate([ordered, ordered[:1] + 2.0 * np.pi])) if n > 1 else [2 * np.pi]
        if inside and np.min(gaps) >= gap:
            # Distance au micro dans l'espace (bouche plus haute que la table).
            height = room["hauteur_bouche_m"] - mic[2]
            return [
                {"x": float(x), "y": float(y), "z": room["hauteur_bouche_m"],
                 "azimut_deg": float(np.rad2deg(a)), "distance_m": float(np.hypot(d, height))}
                for (x, y), a, d in zip(xy, azimuths, distances)
            ]
    raise RuntimeError(f"Placement de {n} locuteurs impossible avec ces contraintes")


def room_rirs(positions: list[dict], rt60: float, room: dict) -> tuple[list[np.ndarray], dict]:
    """Réponses impulsionnelles de chaque position vers le micro, délai direct retranché."""
    import pyroomacoustics as pra

    dims = list(room["dimensions_m"])
    absorption, max_order = pra.inverse_sabine(rt60, dims)
    shoebox = pra.ShoeBox(dims, fs=SAMPLE_RATE, materials=pra.Material(absorption), max_order=max_order)
    for p in positions:
        shoebox.add_source([p["x"], p["y"], p["z"]])
    shoebox.add_microphone(list(room["micro_m"]))
    shoebox.compute_rir()
    # T20 (décroissance de −5 à −25 dB extrapolée, mesure usuelle) et T60 sur toute la
    # décroissance ; la cible d'inverse_sabine est atteinte en T20, le T60 la dépasse.
    t20 = np.asarray(shoebox.measure_rt60(decay_db=20)).reshape(-1)
    t60 = np.asarray(shoebox.measure_rt60()).reshape(-1)
    c = pra.constants.get("c")
    rirs = []
    for k, p in enumerate(positions):
        rir = np.asarray(shoebox.rir[0][k], dtype=np.float64)
        rirs.append(rir[int(round(p["distance_m"] / c * SAMPLE_RATE)):])
    info = {
        "rt60_cible_s": rt60,
        "rt60_mesure_t20_s": [round(float(v), 3) for v in t20],
        "rt60_mesure_t60_s": [round(float(v), 3) for v in t60],
        "absorption": round(float(absorption), 4),
        "ordre_max": int(max_order),
        "delai_filtre_ms": round(1000.0 * (pra.constants.get("frac_delay_length") // 2) / SAMPLE_RATE, 2),
    }
    return rirs, info


def reverberant_mix(signals: list[np.ndarray], rirs: list[np.ndarray]) -> np.ndarray:
    """Chaque piste convoluée avec la réponse de son locuteur, puis mélange de D20 §2."""
    wet = [oaconvolve(s.astype(np.float64), r)[: len(s)] for s, r in zip(signals, rirs)]
    return summre.mix_tracks(wet).astype(np.float64)


# --- Codec ----------------------------------------------------------------------------


def opus_roundtrip(source: Path, kbps: int, n: int, workdir: Path) -> tuple[np.ndarray, float]:
    """Encodage Opus puis décodage à 16 kHz ; renvoie le signal et le décalage mesuré (ms)."""
    encoded, decoded = workdir / "codec.ogg", workdir / "codec.wav"
    base = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
    for command in (
        base + ["-i", str(source), "-ac", "1", "-c:a", "libopus", "-b:a", f"{kbps}k",
                "-application", "voip", str(encoded)],
        base + ["-i", str(encoded), "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_f32le", str(decoded)],
    ):
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(f"ffmpeg a échoué : {completed.stderr.strip()[-2000:]}")
    rate, data = wavfile.read(decoded)
    assert rate == SAMPLE_RATE and data.ndim == 1
    signal = np.zeros(n, dtype=np.float64)
    signal[: min(n, len(data))] = data[:n]
    return signal, len(data)


def codec_lag_ms(reference: np.ndarray, signal: np.ndarray) -> float:
    """Décalage du signal décodé par rapport au propre, sur les 120 premières secondes."""
    n = min(len(reference), 120 * SAMPLE_RATE)
    lag, _, _ = summre.estimate_lag(signal[:n], reference[:n], SAMPLE_RATE, 0.1)
    return 1000.0 * lag


# --- Génération -----------------------------------------------------------------------


def assignments(uri: str, n_sources: int, config: dict) -> dict:
    """Tirages d'une réunion, toujours dans le même ordre : positions, bruit, décalage."""
    rng = meeting_rng(config["graine"], uri)
    positions = place_speakers(n_sources, rng, config["salle"])
    envs = config["bruit"]["environnements"]
    env = envs[int(rng.integers(len(envs)))]
    offset_s = float(rng.uniform(0.0, config["bruit"]["decalage_max_s"]))
    return {"positions": positions, "bruit": env, "decalage_bruit_s": round(offset_s, 3)}


def generate(config: dict, config_sha: str, conditions: list[str], fallback: bool) -> tuple[list[dict], dict]:
    out_dir = REPO_ROOT / config["sortie"]
    uris = dataset_uris(config["source"]["liste"])
    tracks = {} if fallback else local_tracks()
    if not fallback and not tracks_complete(tracks, uris):
        sys.exit("[degrade] pistes individuelles de test absentes ou incomplètes : lancer "
                 "--telecharger-pistes, ou --repli-melange (D24 §1)")
    needed = MIN_FREE_GB_PER_CONDITION * len(conditions)
    if free_gb(REPO_ROOT) < needed:
        sys.exit(f"[degrade] {free_gb(REPO_ROOT):.1f} Go libres, {needed:.1f} Go nécessaires")
    channel = config["bruit"]["canal"]
    fetch_demand(config["bruit"]["environnements"], channel)
    noises = {env: load_noise(env, channel) for env in config["bruit"]["environnements"]}
    fade = int(config["bruit"]["fondu_s"] * SAMPLE_RATE)
    specs = config["conditions"]

    rows, records = [], {}
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        for index, uri in enumerate(uris, start=1):
            t0 = time.perf_counter()
            clean_pcm = read_pcm16(processed_wav("summre", uri))
            clean = clean_pcm.astype(np.float64) / 32767.0
            n = len(clean)
            mask = speech_mask(uri, n)
            level = rms(clean, mask)
            if fallback:
                signals, speakers = [clean.astype(np.float32)], ["melange"]
            else:
                infos = tracks[uri]
                signals = load_tracks(infos)
                remix = summre.to_pcm16(summre.mix_tracks(signals))
                if not np.array_equal(remix, clean_pcm):
                    sys.exit(f"[degrade] {uri} : le mélange des pistes ne reproduit pas le mélange existant")
                speakers = [info["speaker_id"] for info in infos]
            draw = assignments(uri, len(signals), config)
            records[uri] = {"locuteurs": speakers, **draw}
            noise = looped(noises[draw["bruit"]], n, int(draw["decalage_bruit_s"] * SAMPLE_RATE), fade)
            rir_cache: dict[float, tuple[np.ndarray, dict]] = {}

            for condition in conditions:
                spec = specs[condition]
                details: dict = {}
                signal = clean
                if "reverberation" in spec:
                    rt60 = float(spec["reverberation"]["rt60_s"])
                    if rt60 not in rir_cache:
                        rirs, info = room_rirs(draw["positions"], rt60, config["salle"])
                        wet = reverberant_mix(signals, rirs)
                        rir_cache[rt60] = (wet * (level / rms(wet, mask)), info)
                    signal, info = rir_cache[rt60]
                    details["reverberation"] = {
                        **info, "repli_melange": fallback,
                        "positions": {s: f"{p['distance_m']:.2f} m, {p['azimut_deg']:.0f}°"
                                      for s, p in zip(speakers, draw["positions"])},
                    }
                if "bruit" in spec:
                    signal, gain = add_noise(signal, noise, mask, float(spec["bruit"]["rsb_db"]))
                    details["bruit"] = {"environnement": draw["bruit"], "decalage_s": draw["decalage_bruit_s"],
                                        "rsb_db": spec["bruit"]["rsb_db"], "gain_bruit": round(gain, 6)}
                if "codec" in spec:
                    kbps = int(spec["codec"]["debit_kbps"])
                    signal, decoded_n = opus_roundtrip(processed_wav("summre", uri), kbps, n, workdir)
                    details["codec"] = {"debit_kbps": kbps, "echantillons_decodes": decoded_n,
                                        "decalage_ms": round(codec_lag_ms(clean, signal), 2)}
                pcm, gain = finalize(signal)
                path = out_dir / condition / f"{uri}.wav"
                digest = write_wav(path, pcm)
                rows.append({
                    "condition": condition, "uri": uri, "sha256": digest,
                    "duree_s": round(n / SAMPLE_RATE, 3), "crete": round(float(np.max(np.abs(pcm))) / 32767.0, 4),
                    "gain": round(gain, 6), "details": json.dumps(details, ensure_ascii=False, sort_keys=True),
                    "config_sha256": config_sha,
                })
            print(f"[degrade] [{index}/{len(uris)}] {uri} : {len(signals)} source(s), bruit {draw['bruit']}, "
                  f"{time.perf_counter() - t0:.1f} s", flush=True)
    return rows, records


def check_and_write_manifest(rows: list[dict], conditions: list[str]) -> list[str]:
    """Compare aux lignes déjà consignées (régénération) puis réécrit le manifeste."""
    existing: dict[tuple[str, str], dict] = {}
    if MANIFEST.exists():
        with MANIFEST.open() as handle:
            existing = {(r["condition"], r["uri"]): r for r in csv.DictReader(handle)}
    differences = [
        f"{r['condition']}/{r['uri']}" for r in rows
        if (r["condition"], r["uri"]) in existing and existing[(r["condition"], r["uri"])]["sha256"] != r["sha256"]
    ]
    if differences:
        sys.exit(f"[degrade] régénération différente du manifeste : {', '.join(differences[:10])}")
    for row in rows:
        existing[(row["condition"], row["uri"])] = row
    with MANIFEST.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerows(existing[key] for key in sorted(existing))
    return differences


# --- Écoute ---------------------------------------------------------------------------


def best_window(uri: str, duration_s: float) -> float:
    """Début (s) de la fenêtre de l'UEM au plus grand nombre de locuteurs, puis de parole."""
    reference = load_rttm(reference_rttm("summre", uri), uri)
    uem = load_uem(uem_path("summre", uri), uri).extent()
    from pyannote.core import Segment

    best, best_key = uem.start, (-1, -1.0)
    for start in np.arange(uem.start, uem.end - duration_s, 1.0):
        window = Segment(float(start), float(start) + duration_s)
        cropped = reference.crop(window)
        key = (len(cropped.labels()), cropped.get_timeline().support().duration())
        if key > best_key:
            best, best_key = float(start), key
    return round(best)


def listening(config: dict) -> Path:
    spec = config["ecoute"]
    out_dir = REPO_ROOT / config["sortie"]
    target = out_dir / "ecoute"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    uris = dataset_uris(config["source"]["liste"])
    zoom = set(dataset_uris(spec["liste_zoom"]))
    rng = np.random.default_rng(config["graine"])
    chosen = list(rng.choice(sorted(zoom & set(uris)), 1)) + list(
        rng.choice(sorted(set(uris) - zoom), spec["extraits"] - 1, replace=False))
    conditions = ["propre", *config["conditions"]]
    duration = float(spec["duree_s"])
    lines, extracts = [], []
    for k, uri in enumerate(chosen, start=1):
        start = best_window(uri, duration)
        stem = f"e{k}_{uri.removeprefix('summre__')}_{int(start)}s"
        files = {}
        for condition in conditions:
            source = processed_wav("summre", uri) if condition == "propre" else out_dir / condition / f"{uri}.wav"
            data = read_pcm16(source)
            excerpt = data[int(start * SAMPLE_RATE): int((start + duration) * SAMPLE_RATE)]
            name = f"{stem}__{condition}.wav"
            wavfile.write(target / name, SAMPLE_RATE, excerpt)
            files[condition] = name
        extracts.append((stem, uri, start, files))
        lines.append(f"- `{stem}` : {uri}, de {start:.0f} s à {start + duration:.0f} s"
                     f"{' (Zoom)' if uri in zoom else ''}")
    channel = config["bruit"]["canal"]
    noises = {}
    for env in config["bruit"]["environnements"]:
        rate, data = wavfile.read(demand_channel(env, channel))
        noises[env] = f"bruit_{env}.wav"
        wavfile.write(target / noises[env], rate, data[: int(duration * rate)])
    assigned = {uri: json.loads((out_dir / "generation.json").read_text())["affectations"][uri]["bruit"]
                for _, uri, _, _ in extracts} if (out_dir / "generation.json").exists() else {}
    lines = [line + (f" ; bruit {assigned[uri]}" if uri in assigned else "")
             for line, (_, uri, _, _) in zip(lines, extracts)]
    (target / "LISEZMOI.md").write_text(
        "# Écoute de contrôle de D24\n\nExtraits, identiques pour toutes les conditions :\n\n"
        + "\n".join(lines) + "\n\nBruits DEMAND seuls (canal " + channel + ", niveau d'origine) : "
        + ", ".join(f"`{name}`" for name in noises.values())
        + ".\n\nOuvrir `index.html` dans un navigateur (lecture locale).\n")
    cells = "".join(f"<th>{html.escape(c)}</th>" for c in conditions)
    body = "".join(
        f"<tr><td>{html.escape(stem)}</td>" + "".join(
            f'<td><audio controls preload="none" src="{html.escape(files[c])}"></audio></td>' for c in conditions)
        + "</tr>" for stem, _, _, files in extracts)
    (target / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Écoute D24</title>'
        "<style>body{font-family:sans-serif;margin:16px}td,th{padding:4px 8px;text-align:left}"
        "audio{width:180px}</style><h1>Écoute de contrôle de D24</h1>"
        f"<p>Trois extraits de {duration:.0f} s, aux mêmes instants pour chaque condition.</p>"
        f"<table><tr><th>Extrait</th>{cells}</tr>{body}</table>"
        "<h2>Bruits seuls</h2><p>Aucun ne doit contenir de parole intelligible (D24 §1).</p><table>"
        + "".join(f'<tr><td>{html.escape(env)}</td><td><audio controls preload="none" '
                  f'src="{html.escape(name)}"></audio></td></tr>' for env, name in noises.items())
        + "</table>")
    return target


# --- Point d'entrée -------------------------------------------------------------------


def print_state(config: dict) -> None:
    uris = dataset_uris(config["source"]["liste"])
    tracks = local_tracks()
    n_tracks = sum(len(tracks.get(uri, [])) for uri in uris)
    channel = config["bruit"]["canal"]
    print(f"[degrade] pistes de test locales : {len([u for u in uris if u in tracks])}/{EXPECTED_TEST[0]} "
          f"réunions, {n_tracks}/{EXPECTED_TEST[1]} pistes ({TRACKS_DIR.relative_to(REPO_ROOT)})")
    for env in config["bruit"]["environnements"]:
        print(f"[degrade] DEMAND {env}/{channel} : {'présent' if demand_channel(env, channel).is_file() else 'absent'}")
    print(f"[degrade] espace libre : {free_gb(REPO_ROOT):.1f} Go")
    try:
        print(f"[degrade] pyroomacoustics {_version('pyroomacoustics')}")
    except Exception:
        print("[degrade] pyroomacoustics absent")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Voir l'en-tête du script et docs/decisions/D24-robustesse.md.",
    )
    parser.add_argument("--etat", action="store_true",
                        help="indique la disponibilité locale des pistes de test et des bruits, puis s'arrête")
    parser.add_argument("--telecharger-pistes", action="store_true",
                        help="retélécharge les Parquet de SUMM-RE test (révision figée de D20) et extrait "
                             "les pistes individuelles dans data/raw/summre/pistes/test/, puis s'arrête")
    parser.add_argument("--repli-melange", action="store_true",
                        help="réverbération appliquée au mélange par une réponse unique (repli de D24), "
                             "sans pistes individuelles ; consigné dans le manifeste")
    parser.add_argument("--conditions", nargs="+", metavar="CODE",
                        help="conditions à générer (défaut : toutes celles de la configuration)")
    parser.add_argument("--ecoute-seulement", action="store_true",
                        help="refait seulement le dossier d'écoute à partir des fichiers générés")
    args = parser.parse_args()

    config, config_sha = load_config()
    if args.etat:
        print_state(config)
        return
    if args.telecharger_pistes:
        download_tracks()
        print_state(config)
        return
    if not args.ecoute_seulement:
        conditions = args.conditions or list(config["conditions"])
        unknown = set(conditions) - set(config["conditions"])
        if unknown:
            sys.exit(f"[degrade] conditions inconnues : {sorted(unknown)}")
        state = git_state()
        t0 = time.perf_counter()
        rows, records = generate(config, config_sha, conditions, args.repli_melange)
        check_and_write_manifest(rows, conditions)
        ffmpeg = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()[0]
        out_dir = REPO_ROOT / config["sortie"]
        (out_dir / "generation.json").write_text(json.dumps({
            "date": datetime.now().astimezone().isoformat(timespec="seconds"),
            "git_commit": state["commit"], "arbre_propre": state["clean"],
            "fichiers_non_commites": state["dirty"],
            "config": str(CONFIG.relative_to(REPO_ROOT)), "config_sha256": config_sha,
            "conditions": conditions, "repli_melange": args.repli_melange,
            "versions": {"pyroomacoustics": _version("pyroomacoustics"), "numpy": np.__version__,
                         "scipy": _version("scipy"), "ffmpeg": ffmpeg},
            "duree_s": round(time.perf_counter() - t0, 1),
            "affectations": records,
        }, ensure_ascii=False, indent=1) + "\n")
        print(f"[degrade] {len(rows)} fichiers en {time.perf_counter() - t0:.0f} s", flush=True)
    target = listening(config)
    print(f"[degrade] dossier d'écoute : {target.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
