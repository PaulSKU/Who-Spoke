"""scripts/prefetch_models.py (D17, amendement 1), sans réseau ni modèle : téléchargement
et chargements simulés."""

import importlib.util
import subprocess
import sys

import pytest

from whospoke.embeddings import ECAPA_REVISION, ECAPA_SOURCE, WESPEAKER_REVISION
from whospoke.experiment import REPO_ROOT

spec = importlib.util.spec_from_file_location("prefetch_models", REPO_ROOT / "scripts" / "prefetch_models.py")
prefetch = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = prefetch  # nécessaire aux dataclasses du script
spec.loader.exec_module(prefetch)

TOKEN = "hf_jeton_de_test"


def test_depots_de_tous_les_moteurs():
    repos = {(repo.repo_id, repo.revision) for repo in prefetch.REPOS}
    # WeSpeaker n'est pas un dépôt à part : c'est community-1 à la révision figée.
    assert repos == {
        ("pyannote/speaker-diarization-community-1", "main"),
        ("pyannote/speaker-diarization-community-1", WESPEAKER_REVISION),
        (ECAPA_SOURCE, ECAPA_REVISION),
    }


def test_telechargement_simule_avec_le_jeton(capsys):
    calls = []

    def fake_download(**kwargs):
        calls.append(kwargs)
        return f"/cache/{kwargs['repo_id']}"

    assert prefetch.download(token=TOKEN, downloader=fake_download) == []
    assert [call["revision"] for call in calls] == [repo.revision for repo in prefetch.REPOS]
    assert all(call["token"] == TOKEN for call in calls)
    assert TOKEN not in capsys.readouterr().out


def test_echec_de_telechargement_signale(capsys):
    def failing(**kwargs):
        if kwargs["repo_id"] == ECAPA_SOURCE:
            raise ConnectionError("réseau indisponible")
        return "/cache"

    failures = prefetch.download(token=TOKEN, downloader=failing)
    assert len(failures) == 1 and ECAPA_SOURCE in failures[0] and "réseau indisponible" in failures[0]
    assert TOKEN not in capsys.readouterr().out


def test_jeton_absent(monkeypatch, tmp_path):
    import whospoke.pipelines.pyannote_community1 as wrapper

    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(wrapper, "REPO_ROOT", tmp_path)  # .env absent
    with pytest.raises(RuntimeError, match="HF_TOKEN"):
        prefetch.read_token()


def test_verification_lancee_hors_ligne_depuis_un_dossier_vide():
    seen = {}

    def runner(command, cwd, env):
        seen.update(command=command, cwd=cwd, env=env)
        return subprocess.CompletedProcess(command, 0)

    assert prefetch.run_offline_check(runner=runner) is True
    assert seen["env"]["HF_HUB_OFFLINE"] == "1"
    assert seen["command"][-1] == "--verification-hors-ligne"
    assert seen["cwd"] != str(REPO_ROOT)


def test_fichier_ecrit_dans_le_dossier_de_lancement_detecte(capsys):
    from pathlib import Path

    def runner(command, cwd, env):
        (Path(cwd) / "pretrained_models").mkdir()
        return subprocess.CompletedProcess(command, 0)

    assert prefetch.run_offline_check(runner=runner) is False
    assert "pretrained_models" in capsys.readouterr().out


@pytest.mark.parametrize("offline, expected", [("1", "True"), (None, "refus")])
def test_verification_enfant_avec_chargements_simules(offline, expected):
    """Processus enfant réel, chargements simulés : un modèle en cache, un absent."""
    code = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('p', {str(REPO_ROOT / 'scripts' / 'prefetch_models.py')!r})\n"
        "p = importlib.util.module_from_spec(spec); sys.modules['p'] = p; spec.loader.exec_module(p)\n"
        "from huggingface_hub.errors import LocalEntryNotFoundError\n"
        "def absent():\n"
        "    raise LocalEntryNotFoundError('absent du cache')\n"
        "try:\n"
        "    failures = p.verify_offline({'en cache': lambda: object(), 'absent': absent})\n"
        "except RuntimeError:\n"
        "    print('refus'); sys.exit(0)\n"
        "print(len(failures) == 1 and 'absent' in failures[0])\n"
    )
    import os

    env = {key: value for key, value in os.environ.items() if key != "HF_HUB_OFFLINE"}
    if offline:
        env["HF_HUB_OFFLINE"] = offline
    completed = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True,
                               timeout=120)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip().splitlines()[-1] == expected
