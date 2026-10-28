"""Contrôles de scripts/evaluate.py : empreinte de config.yaml, bloc temps_cpu."""

import hashlib
import importlib.util
import json

import pytest

from whospoke.experiment import REPO_ROOT

spec = importlib.util.spec_from_file_location("evaluate", REPO_ROOT / "scripts" / "evaluate.py")
evaluate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluate)


def write_runs(tmp_path, config_text, recorded):
    (tmp_path / "config.yaml").write_text(config_text)
    runs = {}
    for device, digest in recorded.items():
        run = {"config_sha256": digest}
        (tmp_path / f"execution_{device}.json").write_text(json.dumps(run))
        runs[f"execution_{device}.json"] = run
    return runs


def test_empreinte_conforme_acceptee(tmp_path):
    text = "exp_id: EXP-X\n"
    digest = hashlib.sha256(text.encode()).hexdigest()
    runs = write_runs(tmp_path, text, {"mps": digest, "cpu": digest})
    evaluate.check_config(tmp_path, runs)


def test_config_modifiee_refusee(tmp_path):
    digest = hashlib.sha256(b"exp_id: EXP-X\n").hexdigest()
    runs = write_runs(tmp_path, "exp_id: EXP-X\ndevice: cpu\n", {"mps": digest})
    with pytest.raises(SystemExit, match="execution_mps.json"):
        evaluate.check_config(tmp_path, runs)


def test_empreinte_absente_refusee(tmp_path):
    (tmp_path / "config.yaml").write_text("exp_id: EXP-X\n")
    with pytest.raises(SystemExit, match="None"):
        evaluate.check_config(tmp_path, {"execution_cpu.json": {}})


def test_exp_0001_conforme():
    exp_dir = REPO_ROOT / "experiments" / "EXP-0001_pyannote-c1-ami-sdm"
    runs = {p.name: json.loads(p.read_text()) for p in exp_dir.glob("execution_*.json")}
    evaluate.check_config(exp_dir, runs)


def test_temps_cpu_tire_de_l_execution_principale():
    run = {"mode": "complet", "fichiers": [
        {"uri": "ami__ES2004a", "duree_audio_s": 100.0, "calcul_s": 2.0},
        {"uri": "ami__TS3003a", "duree_audio_s": 300.0, "calcul_s": 4.0},
        {"uri": "ami__IS1009a", "duree_audio_s": 1000.0, "calcul_s": 50.0},
    ]}
    block = evaluate.cpu_block(run, "data/splits/ami/temps.txt")
    assert block == {"sous_ensemble": "data/splits/ami/temps.txt", "duree_audio_s": 400.0,
                     "calcul_s": 6.0, "rtf": 0.015}
