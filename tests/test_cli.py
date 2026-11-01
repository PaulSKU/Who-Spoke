"""Commande en ligne `whospoke diarize` (chantier E1, src/whospoke/cli.py).

Aucun modèle neuronal n'est chargé : seule la baseline MFCC tourne, sur un signal de
synthèse de quelques secondes.
"""

import json
import os
import shutil
import subprocess
import sys
import tomllib

import numpy as np
import pytest
from scipy.io import wavfile

from whospoke import cli
from whospoke.experiment import REPO_ROOT
from whospoke.telemetry import TELEMETRY_OFF

SR = 16000
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")


def two_voices(path):
    """Deux « voix » (sinusoïdes modulées de 140 et 220 Hz) en alternance, 2 s chacune."""
    rng = np.random.default_rng(0)
    t = np.arange(2 * SR) / SR
    parts = []
    for freq in (140, 220, 140, 220):
        parts.append(0.3 * np.sin(2 * np.pi * freq * t) * (1 + 0.5 * np.sin(2 * np.pi * 4 * t))
                     + 0.01 * rng.standard_normal(len(t)))
        parts.append(0.005 * rng.standard_normal(SR // 2))
    wavfile.write(path, SR, (np.concatenate(parts) * 32767).astype(np.int16))
    return path


@pytest.mark.parametrize("text, expected", [
    ("auto", (None, {"mode": "automatique"})),
    ("3", (3, {"mode": "impose", "valeur": 3})),
    ("2-6", (None, {"mode": "fourchette", "min": 2, "max": 6})),
])
def test_nombre_de_locuteurs(text, expected):
    assert cli.parse_speakers(text) == expected


@pytest.mark.parametrize("text", ["0", "6-2", "0-3", "deux", "2-"])
def test_nombre_de_locuteurs_refuse(text):
    with pytest.raises(cli.CliError):
        cli.parse_speakers(text)


def test_hors_ligne_et_telemetrie_coupee():
    environ = {"HF_HUB_OFFLINE": "0", "PYANNOTE_METRICS_ENABLED": "true"}
    cli.configure_environment(environ)
    assert environ == {**TELEMETRY_OFF, "HF_HUB_OFFLINE": "1"}


def test_commande_declaree():
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    assert pyproject["project"]["scripts"] == {"whospoke": "whospoke.cli:main"}


def test_moteurs_de_l_application():
    from app import moteurs

    assert set(cli.ENGINES) == set(moteurs.SPECS)
    assert cli.DEFAULT_ENGINE in moteurs.SPECS


def test_variable_posee_avant_l_import_du_hub():
    """`main` pose HF_HUB_OFFLINE avant tout import de huggingface_hub (D27) ; `--help`
    arrête le programme avant toute analyse."""
    code = (
        "from whospoke import cli\n"
        "try:\n"
        "    cli.main(['diarize', '--help'])\n"
        "except SystemExit:\n"
        "    pass\n"
        "import huggingface_hub.constants as c\n"
        "print(c.HF_HUB_OFFLINE)\n"
    )
    environ = {key: value for key, value in os.environ.items() if key != "HF_HUB_OFFLINE"}
    completed = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, env=environ,
                               capture_output=True, text=True, timeout=120)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip().splitlines()[-1] == "True"


@needs_ffmpeg
def test_rttm_sur_la_sortie_standard(tmp_path, capsys):
    audio = two_voices(tmp_path / "essai.wav")
    code = cli.main(["diarize", str(audio), "--moteur", "baseline-mfcc", "--locuteurs", "2"], environ={})
    assert code == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines and all(line.startswith("SPEAKER essai 1 ") for line in lines)
    assert len({line.split()[7] for line in lines}) == 2


@needs_ffmpeg
def test_json_dans_un_fichier(tmp_path, capsys):
    audio = two_voices(tmp_path / "essai.wav")
    out = tmp_path / "sorties" / "essai.json"
    code = cli.main(["diarize", str(audio), "--moteur", "baseline-mfcc", "--locuteurs", "2",
                     "--sortie", "json", "-o", str(out)], environ={})
    assert code == 0
    assert capsys.readouterr().out == ""
    data = json.loads(out.read_text())
    assert data["uri"] == "essai" and data["moteur"] == "baseline-mfcc"
    assert data["duree_s"] == pytest.approx(10.0)
    assert data["configuration"]["experience_source"] == "EXP-0009"
    assert data["configuration"]["peripherique"] == "cpu"
    assert data["configuration"]["nombre_locuteurs"] == {"mode": "impose", "valeur": 2}
    assert len(data["locuteurs"]) == 2 and data["segments"]


def test_fourchette_refusee_pour_la_baseline(tmp_path, capsys):
    audio = two_voices(tmp_path / "essai.wav")
    code = cli.main(["diarize", str(audio), "--moteur", "baseline-mfcc", "--locuteurs", "2-4"], environ={})
    assert code == 1
    assert "fourchette" in capsys.readouterr().err


def test_fichier_absent(tmp_path, capsys):
    assert cli.main(["diarize", str(tmp_path / "absent.wav")], environ={}) == 1
    assert "introuvable" in capsys.readouterr().err


def test_moteur_inconnu(tmp_path):
    with pytest.raises(SystemExit) as error:
        cli.main(["diarize", str(tmp_path / "a.wav"), "--moteur", "inconnu"], environ={})
    assert error.value.code == 2
