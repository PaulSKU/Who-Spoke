"""Lecture des RTTM et UEM, listes de partition et état git (whospoke.experiment)."""

import pytest
from pyannote.core import Segment

from whospoke.experiment import (
    REPO_ROOT,
    dataset_uris,
    git_state,
    is_controlled,
    load_rttm,
    load_uem,
    tree_is_clean,
)


def test_load_rttm_et_uem(tmp_path):
    rttm = tmp_path / "a.rttm"
    rttm.write_text(
        "SPEAKER ami__X 1 0.50 2.00 <NA> <NA> S1 <NA> <NA>\n"
        "SPEAKER ami__X 1 1.50 1.00 <NA> <NA> S2 <NA> <NA>\n"
    )
    annotation = load_rttm(rttm, "ami__X")
    assert sorted(annotation.labels()) == ["S1", "S2"]
    assert annotation.label_duration("S1") == pytest.approx(2.0)
    assert annotation.get_overlap().duration() == pytest.approx(1.0)

    uem = tmp_path / "a.uem"
    uem.write_text("ami__X 1 0.000 10.000\n")
    assert list(load_uem(uem, "ami__X")) == [Segment(0.0, 10.0)]


def test_uri_incoherent_refuse(tmp_path):
    rttm = tmp_path / "a.rttm"
    rttm.write_text("SPEAKER X 1 0.5 2.0 <NA> <NA> S1 <NA> <NA>\n")
    with pytest.raises(ValueError, match="uri"):
        load_rttm(rttm, "ami__X")
    uem = tmp_path / "a.uem"
    uem.write_text("X 1 0 10\n")
    with pytest.raises(ValueError, match="uri"):
        load_uem(uem, "ami__X")


def test_liste_sans_doublon(tmp_path):
    liste = tmp_path / "dev.txt"
    liste.write_text("a\nb\n\n")
    assert dataset_uris(liste) == ["a", "b"]
    liste.write_text("a\na\n")
    with pytest.raises(ValueError, match="double"):
        dataset_uris(liste)


# --- Règle de l'arbre propre (D18) -------------------------------------------------


def test_fichier_sale_sous_docs_arbre_propre():
    assert tree_is_clean(["docs/glossaire.md", "docs/decisions/D17-interface.md"])
    assert tree_is_clean(["README.md", "results/leaderboard.csv", "experiments/EXP-0001_x/notes.md"])
    assert tree_is_clean([])


def test_fichier_sale_sous_src_arbre_sale():
    assert not tree_is_clean(["docs/glossaire.md", "src/whospoke/audio.py"])


def test_uv_lock_arbre_sale():
    assert not tree_is_clean(["uv.lock"])
    assert not tree_is_clean(["pyproject.toml"])


@pytest.mark.parametrize(
    "path",
    ["src/a.py", "scripts/run_experiment.py", "configs/x.yaml", "tests/test_x.py",
     "data/splits/ami/dev.txt", "data/manifests/ami.csv", "uv.lock", "pyproject.toml"],
)
def test_chemins_controles(path):
    assert is_controlled(path)


@pytest.mark.parametrize(
    "path",
    ["docs/methode.md", "README.md", "results/leaderboard.csv", "experiments/EXP-0001_x/notes.md",
     "data/README.md", "srcx/a.py", "docs/src/a.md"],
)
def test_chemins_non_controles(path):
    assert not is_controlled(path)


def test_git_state_liste_tous_les_fichiers_non_commites():
    """Un fichier non suivi sous experiments/ est listé mais ne salit pas l'arbre."""
    exp_dir = REPO_ROOT / "experiments" / "EXP-9999_test-git-state"
    exp_dir.mkdir(parents=True)
    try:
        (exp_dir / "run.log").write_text("essai\n")
        state = git_state()
        assert "experiments/EXP-9999_test-git-state/run.log" in state["dirty"]
        assert state["clean"] == tree_is_clean(state["dirty"])
        assert len(state["commit"]) == 40
    finally:
        (exp_dir / "run.log").unlink()
        exp_dir.rmdir()
