"""Surcoût fixe du premier appel de chaque moteur de l'application, et vérification du temps restant.

Le temps restant affiché par l'application est estimé par « surcoût fixe du moteur + RTF ×
durée de l'audio » (décision du cockpit du 01/11/2026, journal). Le RTF vient des
expériences (`app/temps.py`) : il exclut le chargement des modèles et un préchauffage, et
porte sur des réunions longues. Le surcoût fixe couvre l'écart du premier appel après
chargement, celui que fait l'application à la première analyse.

Usage :
    uv run python scripts/measure_overhead.py mesure          # 3 lancements par moteur
    uv run python scripts/measure_overhead.py verification    # annoncé / réel, deux fichiers

Mode `mesure` : pour chaque moteur et périphérique de `ENGINES`, `--lancements` processus
distincts (3 par défaut), lancés l'un après l'autre. Chacun charge le moteur comme
l'application (`app.moteurs.build_engine`), puis traite deux fois de suite l'extrait de
mesure, à l'horloge murale. Surcoût d'un lancement = durée du premier appel − RTF × durée
de l'extrait ; le surcoût retenu est la moyenne des lancements. Extrait de mesure : 60 s
de `summre__004c_PAPH` (partition dev) à partir de 600 s, distinct des deux fichiers de
vérification.

Mode `verification` : pour chaque moteur, un processus neuf traite une fois chaque fichier
de vérification (premier appel après chargement) ; l'annonce est calculée avec et sans
surcoût (`app.temps.announced_s`, `app.moteurs.FIXED_OVERHEAD`). Fichiers : extrait de
3 min de `summre__007a_ECRH` (0 à 180 s), converti en mp3 stéréo 44,1 kHz puis normalisé
par `whospoke.audio.normalize` comme un dépôt dans l'application, et la réunion
`summre__036c_EAPH` (26 min 48 s, partition dev). pyannote en CPU seul n'est vérifié que
sur l'extrait de 3 min (environ 25 min de calcul sur la réunion).

Option `--enfant MOTEUR PÉRIPHÉRIQUE WAV APPELS` : un lancement, dans le processus enfant ;
écrit une ligne JSON sur la sortie standard.

Les résultats (JSON) sont écrits dans `--sortie` (hors du dépôt par défaut : dossier
temporaire), avec la charge moyenne de la machine au début de chaque lancement. La machine
doit être sur secteur ; l'état d'alimentation est relevé.
"""

from __future__ import annotations

import whospoke  # noqa: F401  (D27 : télémétrie coupée avant tout import tiers)

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(__file__).resolve()
PROCESSED = REPO_ROOT / "data" / "processed" / "summre"
sys.path.insert(0, str(REPO_ROOT))   # paquet `app` (moteurs de l'application)

ENGINES = (
    ("baseline-mfcc", "cpu"),
    ("baseline-ecapa", "cpu"),
    ("baseline-wespeaker", "cpu"),
    ("pyannote-community-1", "mps"),
    ("pyannote-community-1", "cpu"),
    ("nemotron-3", "cpu"),            # à mesurer à la fusion (app/moteurs.py, OVERHEAD_TO_MEASURE)
)
MEASURE_CLIP = ("summre__004c_PAPH", 600.0, 60.0)       # uri, début (s), durée (s)
SHORT_CLIP = ("summre__007a_ECRH", 0.0, 180.0)
LONG_FILE = "summre__036c_EAPH"
LONG_SKIPPED = {("pyannote-community-1", "cpu")}


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", *args], check=True)


def make_clip(uri: str, start_s: float, duration_s: float, out: Path) -> Path:
    """Extrait WAV 16 kHz mono d'un fichier normalisé du corpus."""
    _ffmpeg("-ss", str(start_s), "-t", str(duration_s), "-i", str(PROCESSED / f"{uri}.wav"),
            "-c:a", "pcm_s16le", str(out))
    return out


def make_upload_like(uri: str, start_s: float, duration_s: float, folder: Path) -> Path:
    """Extrait converti en mp3 stéréo 44,1 kHz, puis normalisé comme un dépôt dans l'application."""
    from whospoke.audio import normalize

    mp3 = folder / f"{uri.split('__')[-1]}_{int(duration_s)}s.mp3"
    _ffmpeg("-ss", str(start_s), "-t", str(duration_s), "-i", str(PROCESSED / f"{uri}.wav"),
            "-ac", "2", "-ar", "44100", "-b:a", "192k", str(mp3))
    return normalize(mp3, folder / f"{mp3.stem}.wav")


def child(key: str, device: str, wav: str, calls: int) -> None:
    """Un lancement : chargement du moteur, puis `calls` appels sur `wav`, chronométrés."""
    from app import moteurs
    from whospoke.audio import load_waveform

    spec = moteurs.SPECS[key]
    t0 = time.perf_counter()
    engine = moteurs.build_engine(spec, device)
    loading_s = time.perf_counter() - t0
    waveform, sample_rate = load_waveform(Path(wav))
    durations = []
    for _ in range(calls):
        t0 = time.perf_counter()
        engine.run(waveform, sample_rate, uri=Path(wav).stem, num_speakers=None,
                   progress=lambda step, fraction: None)
        durations.append(time.perf_counter() - t0)
    print(json.dumps({"moteur": key, "peripherique": device, "chargement_s": loading_s,
                      "duree_audio_s": waveform.shape[1] / sample_rate, "appels_s": durations}))


def launch(key: str, device: str, wav: Path, calls: int) -> dict:
    """Un lancement dans un processus neuf ; charge moyenne et alimentation relevées avant."""
    from whospoke.power import power_reading

    load = os.getloadavg()
    power = power_reading("lancement")
    completed = subprocess.run([sys.executable, str(SCRIPT), "--enfant", key, device, str(wav), str(calls)],
                               cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    row = json.loads(completed.stdout.strip().splitlines()[-1])
    row.update(charge_moyenne=[round(x, 2) for x in load], alimentation=power["source"])
    return row


def rtf_for(key: str, device: str):
    from app import moteurs, temps

    spec = moteurs.SPECS[key]
    return temps.measured_rtf(spec.source_exp, device, moteurs.source_device(spec))


def measure(launches: int, folder: Path) -> dict:
    uri, start_s, duration_s = MEASURE_CLIP
    clip = make_clip(uri, start_s, duration_s, folder / f"{uri}_{int(start_s)}s_{int(duration_s)}s.wav")
    results = {}
    for key, device in ENGINES:
        measured = rtf_for(key, device)
        rows = [launch(key, device, clip, calls=2) for _ in range(launches)]
        for row in rows:
            row["surcout_s"] = row["appels_s"][0] - measured.rtf * row["duree_audio_s"]
            print(f"{key} ({device}) : premier appel {row['appels_s'][0]:.2f} s, second {row['appels_s'][1]:.2f} s, "
                  f"surcoût {row['surcout_s']:.2f} s, charge {row['charge_moyenne'][0]}", flush=True)
        mean = sum(row["surcout_s"] for row in rows) / len(rows)
        results[f"{key}@{device}"] = {"rtf": measured.rtf, "source_rtf": measured.source(),
                                      "surcout_moyen_s": mean, "lancements": rows}
        print(f"=> {key} ({device}) : surcoût moyen {mean:.2f} s (RTF {measured.rtf})", flush=True)
    return {"extrait": {"uri": uri, "debut_s": start_s, "duree_s": duration_s}, "moteurs": results}


def verify(folder: Path) -> dict:
    from app import moteurs, temps

    files = {"extrait_3min": make_upload_like(*SHORT_CLIP, folder), "reunion_26min48": PROCESSED / f"{LONG_FILE}.wav"}
    results = []
    for name, wav in files.items():
        for key, device in ENGINES:
            if name == "reunion_26min48" and (key, device) in LONG_SKIPPED:
                continue
            measured = rtf_for(key, device)
            overhead = moteurs.fixed_overhead(key, device)
            row = launch(key, device, wav, calls=1)
            real = row["appels_s"][0]
            before = temps.announced_s(measured.rtf, row["duree_audio_s"])
            after = temps.announced_s(measured.rtf, row["duree_audio_s"], overhead.seconds if overhead else 0.0)
            row.update(fichier=name, rtf=measured.rtf, surcout_s=overhead.seconds if overhead else None,
                       annonce_sans_surcout_s=before, annonce_s=after, reel_s=real,
                       ecart_sans_surcout=(before - real) / real, ecart=(after - real) / real)
            results.append(row)
            print(f"{name}, {key} ({device}) : annoncé {after:.1f} s (sans surcoût {before:.1f} s), réel {real:.1f} s, "
                  f"écart {100 * row['ecart']:+.0f} % (sans surcoût {100 * row['ecart_sans_surcout']:+.0f} %), "
                  f"charge {row['charge_moyenne'][0]}", flush=True)
    return {"fichiers": {name: str(path) for name, path in files.items()}, "resultats": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="Méthode et fichiers : voir l'en-tête du script.")
    parser.add_argument("mode", nargs="?", choices=("mesure", "verification"), help="mesure du surcoût ou vérification")
    parser.add_argument("--lancements", type=int, default=3, help="processus par moteur en mode mesure (3 par défaut)")
    parser.add_argument("--sortie", type=Path, default=None,
                        help="fichier JSON des résultats (par défaut : dossier temporaire, hors du dépôt)")
    parser.add_argument("--enfant", nargs=4, metavar=("MOTEUR", "PÉRIPHÉRIQUE", "WAV", "APPELS"),
                        help="un lancement, dans le processus enfant (usage interne, une ligne JSON en sortie)")
    args = parser.parse_args()
    if args.enfant:
        key, device, wav, calls = args.enfant
        child(key, device, wav, int(calls))
        return
    if args.mode is None:
        parser.error("mode requis : mesure ou verification")
    with tempfile.TemporaryDirectory(prefix="surcout-") as tmp:
        started = datetime.now().astimezone().isoformat(timespec="seconds")
        body = measure(args.lancements, Path(tmp)) if args.mode == "mesure" else verify(Path(tmp))
    output = args.sortie or Path(tempfile.gettempdir()) / f"whospoke-{args.mode}-surcout.json"
    output.write_text(json.dumps({"mode": args.mode, "debut": started, **body}, ensure_ascii=False, indent=2) + "\n")
    print(f"Résultats : {output}")


if __name__ == "__main__":
    main()
