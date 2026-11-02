"""Exécution partagée entre deux expériences (D25, V2 et V3 ; whospoke.partage, evaluate.py)."""

import hashlib
import importlib.util
import json
import sys

import numpy as np
import pytest
from scipy.io import wavfile

from whospoke import partage
from whospoke.experiment import REPO_ROOT

spec = importlib.util.spec_from_file_location("evaluate", REPO_ROOT / "scripts" / "evaluate.py")
evaluate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluate)

URI = "synth__a"
COMMIT = "1234567890abcdef1234567890abcdef12345678"
BLOCK = "execution_partagee:\n  porteuse: EXP-B\n  experiences: {EXP-A: habituelle, EXP-B: exclusive}\n"


def config_text(exp_id, sortie, liste, block=BLOCK):
    return (
        f"exp_id: {exp_id}\nslug: s\nreference: null\nvariable_modifiee: null\n"
        f"pipeline: {{nom: pyannote-community-1, vad: integree, parametres: {{sortie: {sortie}}}}}\n"
        f"device: mps\njeux:\n  - {{corpus: synth, partition: dev, liste: {liste}}}\n{block}"
    )


@pytest.fixture
def depot(tmp_path):
    """Porteuse EXP-B (sortie exclusive) exécutée ; EXP-A (habituelle) sans exécution propre."""
    root = tmp_path / "experiments"
    liste = tmp_path / "liste.txt"
    liste.write_text(f"{URI}\n")
    a, b = root / "EXP-A_v2", root / "EXP-B_v3"
    for directory in (a, b):
        directory.mkdir(parents=True)
    (a / "config.yaml").write_text(config_text("EXP-A", "habituelle", liste))
    (b / "config.yaml").write_text(config_text("EXP-B", "exclusive", liste))
    for name, speaker in (("rttm", "x"), ("rttm_habituelle", "h")):
        (b / name).mkdir()
        (b / name / f"{URI}.rttm").write_text(f"SPEAKER {URI} 1 1.000 7.000 <NA> <NA> {speaker} <NA> <NA>\n")
    run = {
        "mode": "complet", "date_fin": "2026-11-02T12:00:00+01:00", "git_commit": COMMIT,
        "fichiers_non_commites": [], "config_sha256": hashlib.sha256((b / "config.yaml").read_bytes()).hexdigest(),
        "device": "mps", "mode_n_locuteurs": "estime", "chargement_modeles_s": 0.0,
        "fichiers": [{"uri": URI, "duree_audio_s": 10.0, "calcul_s": 0.5, "rtf": 0.05}],
    }
    (b / "execution_mps.json").write_text(json.dumps(run))
    return root, a, b


def load(path):
    import yaml

    return yaml.safe_load(path.read_text())


def test_bloc_controle(depot):
    root, a, b = depot
    members = partage.check_block(load(a / "config.yaml"), root)
    assert members == {"EXP-A": (a, "habituelle"), "EXP-B": (b, "exclusive")}
    partage.check_partners_empty(load(b / "config.yaml"), root)
    # Sortie incohérente avec le bloc.
    bad = load(a / "config.yaml")
    bad["pipeline"]["parametres"]["sortie"] = "exclusive"
    with pytest.raises(partage.SharedRunError, match="sortie"):
        partage.check_block(bad, root)
    assert partage.check_block({"exp_id": "EXP-C"}, root) == {}


def test_rappel_et_relecture(depot):
    root, a, b = depot
    config_b = load(b / "config.yaml")
    assert partage.write_reminders(config_b, b, copy_rttm=True, root=root) == ["EXP-A"]
    assert (a / "rttm" / f"{URI}.rttm").read_text() == (b / "rttm_habituelle" / f"{URI}.rttm").read_text()
    reminder = json.loads((a / partage.REMINDER).read_text())
    assert reminder["porteuse"] == "EXP-B" and reminder["sortie"] == "habituelle"
    assert set(reminder["executions"]) == {"execution_mps.json"}
    porteuse, read = partage.read_reminder(load(a / "config.yaml"), a, root)
    assert porteuse == b and read == reminder
    assert partage.read_reminder(config_b, b, root) is None  # la porteuse porte son exécution
    with pytest.raises(partage.SharedRunError, match="déjà"):
        partage.check_partners_empty(config_b, root)


def test_rappel_refuse_les_modifications(depot):
    root, a, b = depot
    partage.write_reminders(load(b / "config.yaml"), b, copy_rttm=True, root=root)
    (a / "rttm" / f"{URI}.rttm").write_text(f"SPEAKER {URI} 1 1.000 2.000 <NA> <NA> h <NA> <NA>\n")
    with pytest.raises(partage.SharedRunError, match="différent"):
        partage.read_reminder(load(a / "config.yaml"), a, root)
    partage.write_reminders(load(b / "config.yaml"), b, copy_rttm=True, root=root)
    (b / "execution_mps.json").write_text("{}")
    with pytest.raises(partage.SharedRunError, match="execution_mps.json"):
        partage.read_reminder(load(a / "config.yaml"), a, root)


def test_evaluation_de_l_experience_non_porteuse(depot, tmp_path, monkeypatch):
    root, a, b = depot
    partage.write_reminders(load(b / "config.yaml"), b, copy_rttm=True, root=root)
    data = tmp_path / "data"
    (data / "rttm").mkdir(parents=True)
    wavfile.write(data / f"{URI}.wav", 16000, np.zeros(16000 * 10, dtype=np.int16))
    (data / f"{URI}.uem").write_text(f"{URI} 1 0.000 10.000\n")
    (data / "rttm" / f"{URI}.rttm").write_text(f"SPEAKER {URI} 1 1.000 3.000 <NA> <NA> A <NA> <NA>\n")
    monkeypatch.setattr(partage, "EXPERIMENTS_DIR", root)
    monkeypatch.setattr(evaluate, "processed_wav", lambda corpus, uri: data / f"{uri}.wav")
    monkeypatch.setattr(evaluate, "reference_rttm", lambda corpus, uri: data / "rttm" / f"{uri}.rttm")
    monkeypatch.setattr(evaluate, "uem_path", lambda corpus, uri: data / f"{uri}.uem")
    monkeypatch.setattr(evaluate, "git_state", lambda: {"commit": COMMIT, "clean": True, "dirty": []})
    leaderboard = tmp_path / "leaderboard.csv"
    for exp in (a, b):
        monkeypatch.setattr(sys, "argv", ["evaluate.py", "--exp", str(exp), "--leaderboard", str(leaderboard)])
        evaluate.main()
    ra = json.loads((a / "results_synth_dev.json").read_text())
    rb = json.loads((b / "results_synth_dev.json").read_text())
    assert ra["temps"] is None and ra["temps_cpu"] is None
    assert rb["temps"]["rtf"] == 0.05
    assert ra["execution_partagee"] == {"porteuse": "EXP-B", "experiences": {"EXP-A": "habituelle", "EXP-B": "exclusive"},
                                        "temps_rapporte": False}
    assert rb["execution_partagee"]["temps_rapporte"] is True
    assert ra["arbre_propre"] is True and ra["git_commit"] == COMMIT[:7]
    rows = leaderboard.read_text().splitlines()
    assert rows[1].split(",")[0] == "EXP-A" and rows[1].split(",")[-3:-1] == ["", ""]
    assert ",".join(rows[2].split(",")[-3:-2]) == "0.05"


def test_copie_des_sorties_par_corpus(depot):
    """D24 : sorties rangées par corpus (rttm_<sortie>/<corpus>/), copiées avec leur arborescence."""
    root, a, b = depot
    nested = b / "rttm_habituelle" / "summre-rev04"
    nested.mkdir()
    (nested / f"{URI}.rttm").write_text(f"SPEAKER {URI} 1 2.000 1.000 <NA> <NA> h <NA> <NA>\n")
    partage.write_reminders(load(b / "config.yaml"), b, copy_rttm=True, root=root)
    assert (a / "rttm" / "summre-rev04" / f"{URI}.rttm").read_text() == (nested / f"{URI}.rttm").read_text()
    assert partage.read_reminder(load(a / "config.yaml"), a, root)[0] == b
