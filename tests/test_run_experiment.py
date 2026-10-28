"""Fonctions de scripts/run_experiment.py : valeurs de balayage, oracles (D19)."""

import importlib.util

import pytest

from whospoke.experiment import REPO_ROOT, reference_rttm

spec = importlib.util.spec_from_file_location("run_experiment", REPO_ROOT / "scripts" / "run_experiment.py")
run_experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_experiment)


def test_valeurs_de_balayage():
    values = run_experiment.sweep_values({"debut": 0.10, "fin": 1.50, "pas": 0.05})
    assert len(values) == 29
    assert values[0] == 0.1 and values[-1] == 1.5 and values[1] == 0.15


def test_sans_oracle_rien_n_est_impose():
    assert run_experiment.oracle_inputs({}, "ami", "ami__ES2004a") == (None, None)


@pytest.mark.skipif(not reference_rttm("ami", "ami__ES2004a").exists(), reason="références AMI absentes")
def test_oracles_lus_dans_la_reference():
    config = {"mode_n_locuteurs": "oracle", "detection_oracle": True}
    num_speakers, speech = run_experiment.oracle_inputs(config, "ami", "ami__ES2004a")
    assert num_speakers == 4
    assert speech.duration() > 0
    # Les régions sont disjointes (support) et dans l'UEM.
    _, uem = run_experiment.reference_in_uem("ami", "ami__ES2004a")
    assert speech.crop(uem.extent()).duration() == pytest.approx(speech.duration())
