"""Requalification de l'arbre propre d'une expérience évaluée (D18, scripts/evaluate.py)."""

import importlib.util
import json

import pytest

from whospoke.experiment import REPO_ROOT

spec = importlib.util.spec_from_file_location("evaluate", REPO_ROOT / "scripts" / "evaluate.py")
evaluate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluate)


def write_experiment(tmp_path, cpu_dirty, commit_cpu="abc"):
    (tmp_path / "execution_mps.json").write_text(
        json.dumps({"git_commit": "abc", "arbre_propre": True, "fichiers_non_commites": []})
    )
    (tmp_path / "execution_cpu.json").write_text(
        json.dumps({"git_commit": commit_cpu, "arbre_propre": False, "fichiers_non_commites": cpu_dirty})
    )
    results = {
        "exp_id": "EXP-X",
        "arbre_propre": False,
        "metriques": {"collar_0": {"der": 19.92}},
        "invalidee": None,
    }
    path = tmp_path / "results_ami_test.json"
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    return path, results


def test_requalification_docs_seuls(tmp_path):
    path, before = write_experiment(tmp_path, ["docs/glossaire.md", "docs/decisions/D17-interface.md"])
    evaluate.requalify(tmp_path)
    after = json.loads(path.read_text())
    assert after["arbre_propre"] is True
    block = after["requalification"]
    assert block["regle"] == "D18"
    assert block["ancienne_valeur"] is False and block["nouvelle_valeur"] is True
    assert block["date"]
    # Seules arbre_propre et requalification changent ; requalification suit arbre_propre.
    assert {k: v for k, v in after.items() if k not in ("arbre_propre", "requalification")} == {
        k: v for k, v in before.items() if k != "arbre_propre"
    }
    keys = list(after)
    assert keys[keys.index("arbre_propre") + 1] == "requalification"
    with pytest.raises(SystemExit):
        evaluate.requalify(tmp_path)  # une seule requalification


def test_requalification_code_sale_reste_false(tmp_path):
    path, _ = write_experiment(tmp_path, ["src/whospoke/audio.py"])
    evaluate.requalify(tmp_path)
    assert json.loads(path.read_text())["arbre_propre"] is False


def test_requalification_commits_differents(tmp_path):
    path, _ = write_experiment(tmp_path, [], commit_cpu="def")
    evaluate.requalify(tmp_path)
    assert json.loads(path.read_text())["arbre_propre"] is False
