"""Requalification de l'arbre propre d'une expérience évaluée (D18, scripts/evaluate.py)."""

import importlib.util
import json
import subprocess

import pytest

from whospoke.experiment import REPO_ROOT

spec = importlib.util.spec_from_file_location("evaluate", REPO_ROOT / "scripts" / "evaluate.py")
evaluate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluate)


def write_experiment(tmp_path, cpu_dirty, commit_mps="abc", commit_cpu="abc", sha_cpu="0e36"):
    (tmp_path / "execution_mps.json").write_text(json.dumps(
        {"git_commit": commit_mps, "arbre_propre": True, "fichiers_non_commites": [], "config_sha256": "0e36"}
    ))
    (tmp_path / "execution_cpu.json").write_text(json.dumps(
        {"git_commit": commit_cpu, "arbre_propre": False, "fichiers_non_commites": cpu_dirty,
         "config_sha256": sha_cpu}
    ))
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


def git_repo(tmp_path, second_change):
    """Dépôt à deux commits ; le second modifie `second_change`. Renvoie (dépôt, commits)."""
    repo = tmp_path / "depot"
    (repo / "src").mkdir(parents=True)
    (repo / "experiments").mkdir()

    def git(*args):
        return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True,
                              text=True).stdout.strip()

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "test")
    (repo / "src" / "code.py").write_text("x = 1\n")
    (repo / "experiments" / "resultat.txt").write_text("a\n")
    git("add", ".")
    git("commit", "-q", "-m", "premier")
    first = git("rev-parse", "HEAD")
    target = repo / second_change
    target.write_text(target.read_text() + "modifié\n")
    git("commit", "-q", "-am", "second")
    return repo, [first, git("rev-parse", "HEAD")]


def experiment_dir(tmp_path):
    exp = tmp_path / "exp"
    exp.mkdir()
    return exp


def test_requalification_commits_differents_sans_diff_controle(tmp_path):
    repo, (first, second) = git_repo(tmp_path, "experiments/resultat.txt")
    exp = experiment_dir(tmp_path)
    path, before = write_experiment(exp, ["docs/journal.md"], commit_mps=first, commit_cpu=second)
    evaluate.requalify(exp, repo=repo)
    after = json.loads(path.read_text())
    assert after["arbre_propre"] is True
    block = after["requalification"]
    assert block["nouvelle_valeur"] is True
    assert sorted(block["commits"]) == sorted([first, second])
    assert block["diff_chemins_controles"] == "vide"
    assert {k: v for k, v in after.items() if k not in ("arbre_propre", "requalification")} == {
        k: v for k, v in before.items() if k != "arbre_propre"
    }


def test_requalification_refusee_si_diff_sous_src(tmp_path):
    repo, (first, second) = git_repo(tmp_path, "src/code.py")
    exp = experiment_dir(tmp_path)
    path, before = write_experiment(exp, [], commit_mps=first, commit_cpu=second)
    with pytest.raises(SystemExit, match="git diff"):
        evaluate.requalify(exp, repo=repo)
    assert json.loads(path.read_text()) == before  # rien n'est écrit


def test_requalification_refusee_si_config_differente(tmp_path):
    repo, (first, second) = git_repo(tmp_path, "experiments/resultat.txt")
    exp = experiment_dir(tmp_path)
    path, before = write_experiment(exp, [], commit_mps=first, commit_cpu=second, sha_cpu="ffff")
    with pytest.raises(SystemExit, match="config_sha256"):
        evaluate.requalify(exp, repo=repo)
    assert json.loads(path.read_text()) == before


def test_requalification_refusee_si_execution_sale(tmp_path):
    repo, (first, second) = git_repo(tmp_path, "experiments/resultat.txt")
    exp = experiment_dir(tmp_path)
    path, before = write_experiment(exp, ["src/whospoke/audio.py"], commit_mps=first, commit_cpu=second)
    with pytest.raises(SystemExit, match="non propre"):
        evaluate.requalify(exp, repo=repo)
    assert json.loads(path.read_text()) == before
