"""Estimation du temps restant à partir du RTF mesuré (D17, app/temps.py)."""

import pytest

from app import temps

HEADER = "exp_id,date,slug,reference,variable_modifiee,corpus,partition,pipeline,mode_n_locuteurs,der_c0,manquee_c0,fausse_alarme_c0,confusion_c0,der_c025,jer_c0,mae_n_locuteurs,rtf,rtf_cpu,git_commit\n"


@pytest.fixture
def leaderboard(tmp_path):
    path = tmp_path / "leaderboard.csv"
    path.write_text(
        HEADER
        + "EXP-0001,d,s,,,ami,dev,p,estime,1,1,1,1,1,1,0,0.05,0.80,abc\n"
        + "EXP-0001,d,s,,,ami,test,p,estime,1,1,1,1,1,1,0,0.06,0.80,abc\n"
        + "EXP-0002,d,s,,,ami,dev,p,estime,1,1,1,1,1,1,0,0.10,,abc\n"
        + "EXP-0003,d,s,,,ami,dev,p,estime,1,1,1,1,1,1,0,0.02,0.03,abc\n"
        + "EXP-0003,d,s,,,ami,test,p,estime,1,1,1,1,1,1,0,0.02,0.05,abc\n"
        + "EXP-0003,d,s,,,ami,autre,p,estime,1,1,1,1,1,1,0,0.02,0.90,abc\n"
    )
    return path


def test_rtf_du_peripherique_de_l_experience(leaderboard):
    measured = temps.measured_rtf("EXP-0001", "mps", "mps", leaderboard)
    # Plusieurs lignes : la plus grande valeur, pour ne pas sous-estimer.
    assert measured.rtf == pytest.approx(0.06)
    assert measured.column == "rtf"
    assert "EXP-0001" in measured.source()


def test_rtf_cpu_seul(leaderboard):
    measured = temps.measured_rtf("EXP-0001", "cpu", "mps", leaderboard)
    assert measured.rtf == pytest.approx(0.80) and measured.column == "rtf_cpu"


def test_colonne_du_peripherique_choisi_pour_une_experience_en_cpu(leaderboard):
    # Amendement 1 de D17 : CPU choisi -> rtf_cpu, même si l'expérience a tourné en CPU ;
    # plus grande valeur entre dev et test seulement.
    measured = temps.measured_rtf("EXP-0003", "cpu", "cpu", leaderboard)
    assert measured.column == "rtf_cpu" and measured.rtf == pytest.approx(0.05)
    # rtf_cpu vide pour une expérience exécutée en CPU : repli sur rtf (même périphérique).
    assert temps.measured_rtf("EXP-0002", "cpu", "cpu", leaderboard).column == "rtf"


def test_rtf_non_mesure(leaderboard):
    assert temps.measured_rtf("EXP-0001", "cuda", "mps", leaderboard) is None
    assert temps.measured_rtf("EXP-0002", "cpu", "mps", leaderboard) is None
    assert temps.measured_rtf("EXP-0099", "mps", "mps", leaderboard) is None
    assert temps.measured_rtf("EXP-0001", "mps", "mps", leaderboard.with_name("absent.csv")) is None


def test_rtf_lu_dans_le_leaderboard_du_depot():
    measured = temps.measured_rtf("EXP-0007", "mps", "mps")
    assert measured is not None and 0.0 < measured.rtf < 1.0


def test_temps_restant():
    assert temps.remaining_s(0.05, 600.0, 10.0) == pytest.approx(20.0)
    assert temps.remaining_s(0.05, 600.0, 45.0) == 0.0
    assert temps.remaining_s(None, 600.0, 10.0) is None


@pytest.mark.parametrize("seconds, text", [
    (None, "—"), (4.4, "4 s"), (59.6, "1 min 00 s"), (125, "2 min 05 s"), (3720, "1 h 02 min"),
])
def test_format_des_durees(seconds, text):
    assert temps.format_duration(seconds) == text
