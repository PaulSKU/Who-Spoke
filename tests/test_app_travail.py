"""Lancement de l'application : hors ligne et dossiers temporaires (D17, amendement 1)."""

import os
import subprocess
import sys

import pytest

from app import travail
from whospoke.experiment import REPO_ROOT


def test_hors_ligne_hors_mode_factice(tmp_path):
    environ: dict[str, str] = {}
    work = travail.configure_environment(environ, ["--port", "7861"], root=tmp_path)
    assert environ["HF_HUB_OFFLINE"] == "1"
    assert environ["PYANNOTE_METRICS_ENABLED"] == "false"
    assert environ["GRADIO_TEMP_DIR"] == str(work / "gradio")
    assert work == tmp_path / f"run-{os.getpid()}"


def test_mode_factice_sans_contrainte_sur_le_hub(tmp_path):
    environ: dict[str, str] = {}
    travail.configure_environment(environ, ["--factice"], root=tmp_path)
    assert "HF_HUB_OFFLINE" not in environ
    assert environ["PYANNOTE_METRICS_ENABLED"] == "false"     # télémétrie coupée dans tous les modes


@pytest.mark.parametrize("argv, offline", [([], "True"), (["--factice"], "False")])
def test_variable_posee_avant_l_import_du_hub(argv, offline):
    """Lancé comme `python -m app.app`, le module pose HF_HUB_OFFLINE avant d'importer
    huggingface_hub : la constante lue à l'import le reflète. Aucun modèle n'est chargé
    (`--help` arrête le programme avant le lancement du serveur)."""
    code = (
        "import os, runpy, sys\n"
        f"sys.argv = ['app.app', *{argv!r}, '--help']\n"
        "try:\n"
        "    runpy.run_module('app.app', run_name='__main__')\n"
        "except SystemExit:\n"
        "    pass\n"
        "from pyannote.audio.telemetry.metrics import is_metrics_enabled\n"
        "assert not is_metrics_enabled(), 'télémétrie de pyannote active'\n"
        "import huggingface_hub.constants as c\n"
        "print(c.HF_HUB_OFFLINE)\n"
    )
    environ = {key: value for key, value in os.environ.items()
               if key not in ("HF_HUB_OFFLINE", "PYANNOTE_METRICS_ENABLED")}
    completed = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, env=environ,
                               capture_output=True, text=True, timeout=120)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip().splitlines()[-1] == offline


def test_suppression_a_la_fermeture(tmp_path):
    work = travail.run_dir(tmp_path)
    (work / "gradio").mkdir(parents=True)
    (work / "gradio" / "audio.wav").write_bytes(b"0")
    travail.cleanup(work, root=tmp_path)
    assert not work.exists()
    # Jamais en dehors du dossier racine de l'application.
    other = tmp_path / "autre"
    other.mkdir()
    with pytest.raises(ValueError):
        travail.cleanup(other, root=tmp_path)
    assert other.exists()


def test_dossiers_de_lancements_interrompus(tmp_path):
    finished = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"],
                              capture_output=True, text=True, check=True)
    dead = tmp_path / f"run-{finished.stdout.strip()}"
    alive = travail.run_dir(tmp_path)
    unrelated = tmp_path / "notes"
    for path in (dead, alive, unrelated):
        path.mkdir()
    assert travail.remove_stale(tmp_path) == [dead]
    assert alive.exists() and unrelated.exists() and not dead.exists()
