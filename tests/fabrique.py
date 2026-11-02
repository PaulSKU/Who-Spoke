"""Fichiers de test fabriqués pour les cas limites de l'interface (chantier B7).

Aucune donnée personnelle : l'audio est synthétique (sinusoïdes hachées, bruit, silence,
généré par ffmpeg) et les sorties de moteur sont des RTTM écrits ici. Utilisé par
`tests/test_app_cas_limites.py`, et en ligne de commande pour la vérification dans le
navigateur :

    uv run python -m tests.fabrique DOSSIER          # cas courts
    uv run python -m tests.fabrique DOSSIER --longs  # plus 30 et 90 min

Le dossier reçoit `audio/` (fichiers à déposer), `sorties/` (RTTM fabriqués, à passer à
l'application par `--factice-rttm`) et `references/` (RTTM de référence à déposer).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

FFMPEG = "ffmpeg"


def _run(*args: str) -> None:
    subprocess.run([FFMPEG, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *args],
                   check=True, capture_output=True)


def _encoder(*names: str) -> str | None:
    """Premier encodeur disponible parmi `names` (ffmpeg varie d'une installation à l'autre)."""
    listing = subprocess.run([FFMPEG, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    return next((name for name in names if f" {name} " in listing), None)


def tone(seconds: float, rate: int = 16000, channels: int = 1) -> list[str]:
    """Source ffmpeg : sinusoïde hachée (une « voix » qui s'arrête toutes les secondes)."""
    layout = "stereo" if channels == 2 else "mono"
    return ["-f", "lavfi", "-i",
            f"sine=frequency=220:sample_rate={rate}:duration={seconds},"
            f"volume='if(lt(mod(t,2),1.2),0.5,0)':eval=frame,aformat=channel_layouts={layout}"]


def audio(kind: str, path: Path, seconds: float = 20.0) -> Path:
    """Fabrique un fichier audio ou vidéo du type `kind` (voir CASES_AUDIO)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if kind == "wav_16k":
        _run(*tone(seconds), "-c:a", "pcm_s16le", str(path))
    elif kind == "stereo_44k":
        _run(*tone(seconds, 44100, 2), "-c:a", "pcm_s16le", str(path))
    elif kind == "stereo_48k":
        _run(*tone(seconds, 48000, 2), "-c:a", "pcm_s24le", str(path))
    elif kind in ("mp4", "mov"):
        _run("-f", "lavfi", "-i", f"color=c=gray:s=320x240:r=10:d={seconds}", *tone(seconds, 48000, 2),
             "-shortest", "-c:v", "mpeg4", "-c:a", "aac", str(path))
    elif kind == "mp4_sans_son":
        _run("-f", "lavfi", "-i", f"color=c=gray:s=320x240:r=10:d={seconds}", "-c:v", "mpeg4", str(path))
    elif kind == "m4a":
        _run(*tone(seconds, 44100, 2), "-c:a", "aac", str(path))
    elif kind == "ogg":
        codec = _encoder("libvorbis", "libopus")
        _run(*tone(seconds, 48000, 2), "-c:a", codec, str(path))
    elif kind == "corrompu":
        # Enregistrement interrompu : m4a coupé en deux, l'index (moov) final manque.
        whole = path.with_name(path.stem + ".complet.m4a")
        audio("m4a", whole, seconds)
        data = whole.read_bytes()
        path.write_bytes(data[: len(data) // 2])
        whole.unlink()
    elif kind == "texte_renomme":
        path.write_text("Compte rendu de la réunion du 16 novembre\n\n- point 1\n- point 2\n" * 40,
                        encoding="utf-8")
    elif kind == "silence":
        _run("-f", "lavfi", "-i", f"anullsrc=r=16000:cl=mono:d={seconds}", "-c:a", "pcm_s16le", str(path))
    else:
        raise ValueError(f"type d'audio inconnu : {kind}")
    return path


# Cas d'audio : nom du fichier déposé, type, durée (s).
CASES_AUDIO = [
    ("video.mp4", "mp4", 20.0),
    ("video.mov", "mov", 20.0),
    ("video sans son.mp4", "mp4_sans_son", 20.0),
    ("stereo 44k.wav", "stereo_44k", 20.0),
    ("stereo 48k.wav", "stereo_48k", 20.0),
    ("dictaphone.m4a", "m4a", 20.0),
    ("message.ogg", "ogg", 20.0),
    ("enregistrement coupé.m4a", "corrompu", 20.0),
    ("compte-rendu.wav", "texte_renomme", 0.0),
    ("trois secondes.wav", "wav_16k", 3.0),
    ("silence.wav", "silence", 20.0),
]
LONG_AUDIO = [("trente minutes.m4a", "m4a", 1800.0), ("quatre-vingt-dix minutes.m4a", "m4a", 5400.0)]


# --- Sorties de moteur fabriquées (RTTM) -----------------------------------------------

def rttm_line(uri: str, start: float, end: float, label: str) -> str:
    """Ligne RTTM ; un champ RTTM ne contient pas d'espace (comme `sortie.rttm_name`)."""
    uri = "_".join(uri.split())
    return f"SPEAKER {uri} 1 {start:.3f} {end - start:.3f} <NA> <NA> {label} <NA> <NA>\n"


def turns_round_robin(n_speakers: int, duration: float, turn: float, gap: float = 0.2) -> list[tuple]:
    """Tours successifs de `turn` s, chaque locuteur à son tour, séparés de `gap` s."""
    rows, t, index = [], 0.0, 0
    while t + turn <= duration:
        rows.append((t, t + turn, f"SPEAKER_{index % n_speakers:02d}"))
        t += turn + gap
        index += 1
    return rows


def overlap_everyone(n_speakers: int, duration: float) -> list[tuple]:
    """Chevauchement massif : tout le monde parle tout le temps, avec de courtes pauses."""
    return [(start, min(start + 4.5, duration), f"SPEAKER_{k:02d}")
            for k in range(n_speakers) for start in range(0, int(duration), 5)]


def outputs(duration: float) -> dict[str, list[tuple]]:
    """Sorties fabriquées par cas, pour un audio de `duration` s."""
    return {
        "un locuteur": [(1.0, duration - 1.0, "SPEAKER_00")],
        "zero locuteur": [],
        "six locuteurs": turns_round_robin(6, duration, 1.0),
        "neuf locuteurs": turns_round_robin(9, duration, 0.8),
        "douze locuteurs": turns_round_robin(12, duration, 0.6, 0.1),
        "chevauchement massif": overlap_everyone(4, duration),
        "tours de 50 ms": turns_round_robin(3, duration, 0.05, 0.0),
    }


def write_rttm(path: Path, uri: str, rows: list[tuple]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(rttm_line(uri, start, end, label) for start, end, label in rows))
    return path


# --- Références -------------------------------------------------------------------------

def references(directory: Path, uri: str, duration: float) -> dict[str, Path]:
    """Références déposables : mal formées, d'un autre fichier, plus longue, plus courte."""
    directory.mkdir(parents=True, exist_ok=True)
    good = turns_round_robin(2, duration, 1.5)
    uri = "_".join(uri.split())
    files = {
        "colonnes manquantes": "SPEAKER {u} 1 0.0 1.5\n".format(u=uri),
        "nombre illisible": "SPEAKER {u} 1 zéro 1,5 <NA> <NA> A <NA> <NA>\n".format(u=uri),
        "duree negative": "SPEAKER {u} 1 4.0 -1.0 <NA> <NA> A <NA> <NA>\n".format(u=uri),
        "vide": "",
        "pas un rttm": "début\tfin\ttexte\n0.0\t1.5\tS1\n",
        "binaire": None,
        "plusieurs fichiers": rttm_line(uri, 0, 1, "A") + rttm_line(uri + "_bis", 1, 2, "B"),
    }
    paths = {}
    for name, text in files.items():
        path = directory / f"{name}.rttm"
        if text is None:
            path.write_bytes(bytes(range(256)) * 8)
        else:
            path.write_text(text, encoding="utf-8")
        paths[name] = path
    paths["autre fichier"] = write_rttm(directory / "autre fichier.rttm", "summre__004c_PAPH",
                                        turns_round_robin(3, duration, 2.0))
    paths["plus longue"] = write_rttm(directory / "plus longue.rttm", uri,
                                      good + turns_round_robin(2, duration * 2, 1.5)[len(good):])
    paths["plus courte"] = write_rttm(directory / "plus courte.rttm", uri,
                                      [row for row in good if row[1] <= duration / 2])
    return paths


def build(directory: Path, long: bool = False) -> None:
    """Tous les fichiers des cas, pour la vérification dans le navigateur."""
    if directory.exists():
        shutil.rmtree(directory)
    for name, kind, seconds in CASES_AUDIO + (LONG_AUDIO if long else []):
        audio(kind, directory / "audio" / name, seconds)
        stem = Path(name).stem
        rows = [] if kind == "silence" else turns_round_robin(2, max(seconds, 1.0), 1.5)
        write_rttm(directory / "sorties" / f"{stem}.rttm", stem, rows)
    for case, rows in outputs(60.0).items():
        audio("wav_16k", directory / "audio" / f"{case}.wav", 60.0)
        write_rttm(directory / "sorties" / f"{case}.rttm", case, rows)
    references(directory / "references", "six locuteurs", 60.0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dossier", type=Path)
    parser.add_argument("--longs", action="store_true", help="ajouter les audios de 30 et 90 min")
    args = parser.parse_args()
    build(args.dossier, args.longs)
    print(f"Fichiers fabriqués dans {args.dossier}")
