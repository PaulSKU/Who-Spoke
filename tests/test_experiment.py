"""Lecture des RTTM et UEM, listes de partition et état git (whospoke.experiment)."""

import pytest
from pyannote.core import Segment

from whospoke.experiment import REPO_ROOT, dataset_uris, git_state, load_rttm, load_uem


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


def test_git_state_exclut_le_dossier_d_experience():
    exp_dir = REPO_ROOT / "experiments" / "EXP-9999_test-git-state"
    exp_dir.mkdir(parents=True)
    try:
        (exp_dir / "run.log").write_text("essai\n")
        before = git_state()
        assert "experiments/EXP-9999_test-git-state/run.log" in before["dirty"]
        after = git_state(exclude=exp_dir)
        assert "experiments/EXP-9999_test-git-state/run.log" not in after["dirty"]
        assert len(after["commit"]) == 40
    finally:
        (exp_dir / "run.log").unlink()
        exp_dir.rmdir()
