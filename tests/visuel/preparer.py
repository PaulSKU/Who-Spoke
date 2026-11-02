"""Réunion de synthèse pour les captures de référence (audit visuel du 02/11, chantier B10).

Aucune donnée de corpus : audio synthétique (ffmpeg, `tests.fabrique.tone`), sortie de
moteur et référence écrites ici, tirées d'un générateur à graine fixe : les captures sont
reproductibles d'un lancement à l'autre.

    uv run python -m tests.visuel.preparer DOSSIER

Le dossier reçoit `reunion_synthese.wav` (à déposer), `sorties/reunion_synthese.rttm`
(sortie du moteur factice, `--factice-rttm DOSSIER/sorties`) et `reunion_synthese_reference.rttm`
(référence à déposer).
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from tests import fabrique

NAME = "reunion_synthese"
DURATION_S = 90.0
SEED = 20261102


def turns(seed: int = SEED) -> list[tuple[float, float, str]]:
    """Tours de 4 locuteurs, de 0,4 à 6 s, avec quelques chevauchements brefs."""
    rng = random.Random(seed)
    rows, t, previous = [], 0.5, None
    while t < DURATION_S - 1.0:
        speaker = rng.choice([s for s in ("SPEAKER_00", "SPEAKER_01", "SPEAKER_02", "SPEAKER_03") if s != previous])
        length = round(rng.choice((0.4, 0.8, 1.5, 2.5, 4.0, 6.0)) * rng.uniform(0.8, 1.2), 3)
        end = min(round(t + length, 3), DURATION_S - 0.5)
        rows.append((round(t, 3), end, speaker))
        previous = speaker
        t = end + round(rng.choice((-0.4, 0.0, 0.2, 0.3, 0.8, 1.2)), 3)
    return rows


def reference(rows: list[tuple[float, float, str]], seed: int = SEED) -> list[tuple[float, float, str]]:
    """Référence : frontières décalées de quelques centièmes, locuteurs renommés, un tour
    attribué à un autre locuteur et un cinquième locuteur bref."""
    rng = random.Random(seed + 1)
    names = {"SPEAKER_00": "SPK_A", "SPEAKER_01": "SPK_B", "SPEAKER_02": "SPK_C", "SPEAKER_03": "SPK_D"}
    out = []
    for index, (start, end, speaker) in enumerate(rows):
        shift = round(rng.uniform(-0.15, 0.15), 3)
        label = names[speaker] if index % 9 != 4 else "SPK_A"
        out.append((max(0.0, round(start + shift, 3)), round(end + shift / 2, 3), label))
    out.append((40.0, 41.2, "SPK_E"))
    return sorted(out)


def build(directory: Path) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    audio = directory / f"{NAME}.wav"
    if not audio.is_file():
        fabrique.audio("wav_16k", audio, DURATION_S)
    rows = turns()
    output = fabrique.write_rttm(directory / "sorties" / f"{NAME}.rttm", NAME, rows)
    ref = fabrique.write_rttm(directory / f"{NAME}_reference.rttm", NAME, reference(rows))
    return {"audio": audio, "sortie": output, "reference": ref}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dossier", type=Path)
    paths = build(parser.parse_args().dossier)
    print("\n".join(f"{key} : {path}" for key, path in paths.items()))
