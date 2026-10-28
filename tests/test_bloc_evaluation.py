"""Bloc `evaluation` des results_*.json : commit et arbre du script d'évaluation (D18)."""

import hashlib
import importlib.util
import json
import sys

import numpy as np
from scipy.io import wavfile

from whospoke.experiment import REPO_ROOT

spec = importlib.util.spec_from_file_location("evaluate", REPO_ROOT / "scripts" / "evaluate.py")
evaluate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluate)

URI = "synth__a"
COMMIT = "1234567890abcdef1234567890abcdef12345678"


def write_experiment(tmp_path):
    """Expérience synthétique d'un fichier, exécutée en CPU sur COMMIT, arbre propre."""
    exp = tmp_path / "EXP-X_synth"
    (exp / "rttm").mkdir(parents=True)
    data = tmp_path / "data"
    (data / "rttm").mkdir(parents=True)
    wavfile.write(data / f"{URI}.wav", 16000, np.zeros(16000 * 10, dtype=np.int16))
    (data / f"{URI}.uem").write_text(f"{URI} 1 0.000 10.000\n")
    (data / "rttm" / f"{URI}.rttm").write_text(
        f"SPEAKER {URI} 1 1.000 3.000 <NA> <NA> A <NA> <NA>\n"
        f"SPEAKER {URI} 1 5.000 3.000 <NA> <NA> B <NA> <NA>\n"
    )
    (exp / "rttm" / f"{URI}.rttm").write_text(
        f"SPEAKER {URI} 1 1.000 7.000 <NA> <NA> s0 <NA> <NA>\n"
    )
    liste = tmp_path / "liste.txt"
    liste.write_text(f"{URI}\n")
    config = (
        "exp_id: EXP-X\nslug: synth\nreference: null\nvariable_modifiee: null\n"
        "pipeline: {nom: baseline, vad: energie}\ndevice: cpu\n"
        f"jeux:\n  - {{corpus: synth, partition: dev, liste: {liste}}}\n"
    )
    (exp / "config.yaml").write_text(config)
    run = {
        "mode": "complet", "date_fin": "2026-10-28T12:00:00+01:00", "git_commit": COMMIT,
        "fichiers_non_commites": [], "config_sha256": hashlib.sha256(config.encode()).hexdigest(),
        "device": "cpu", "mode_n_locuteurs": "estime", "chargement_modeles_s": 0.0,
        "fichiers": [{"uri": URI, "duree_audio_s": 10.0, "calcul_s": 0.1, "rtf": 0.01}],
    }
    (exp / "execution_cpu.json").write_text(json.dumps(run))
    return exp, data


def run_evaluation(tmp_path, monkeypatch, state):
    exp, data = write_experiment(tmp_path)
    monkeypatch.setattr(evaluate, "processed_wav", lambda corpus, uri: data / f"{uri}.wav")
    monkeypatch.setattr(evaluate, "reference_rttm", lambda corpus, uri: data / "rttm" / f"{uri}.rttm")
    monkeypatch.setattr(evaluate, "uem_path", lambda corpus, uri: data / f"{uri}.uem")
    monkeypatch.setattr(evaluate, "git_state", lambda: state)
    monkeypatch.setattr(sys, "argv", [
        "evaluate.py", "--exp", str(exp), "--leaderboard", str(tmp_path / "leaderboard.csv"),
    ])
    evaluate.main()
    return json.loads((exp / "results_synth_dev.json").read_text())


def test_bloc_evaluation_arbre_propre(tmp_path, monkeypatch):
    state = {"commit": COMMIT, "clean": True, "dirty": ["docs/journal.md"]}
    results = run_evaluation(tmp_path, monkeypatch, state)
    block = results["evaluation"]
    assert block["git_commit"] == COMMIT
    assert block["arbre_propre"] is True
    assert block["fichiers_non_commites"] == ["docs/journal.md"]
    assert block["date"]
    assert results["arbre_propre"] is True
    keys = list(results)
    assert keys.index("evaluation") == keys.index("invalidee") - 1


def test_bloc_evaluation_arbre_sale(tmp_path, monkeypatch):
    # Évaluation sur un autre commit, avec du code non commité : consigné tel quel.
    state = {"commit": "f" * 40, "clean": False, "dirty": ["scripts/evaluate.py"]}
    results = run_evaluation(tmp_path, monkeypatch, state)
    assert results["evaluation"] == {
        "date": results["evaluation"]["date"],
        "git_commit": "f" * 40,
        "arbre_propre": False,
        "fichiers_non_commites": ["scripts/evaluate.py"],
    }
    assert results["arbre_propre"] is False
    assert results["git_commit"] == COMMIT[:7]  # commit de l'exécution, inchangé

