"""Contrôle de l'alimentation (D21 §3) : lecture de pmset, relevés et conformité, sur sorties simulées."""

import importlib.util
import time

from whospoke.experiment import REPO_ROOT
from whospoke.power import PowerMonitor, is_compliant, parse_pmset, power_reading

SECTEUR = """Now drawing from 'AC Power'
 -InternalBattery-0 (id=20643939)\t100%; charged; 0:00 remaining present: true
"""
BATTERIE = """Now drawing from 'Battery Power'
 -InternalBattery-0 (id=20643939)\t93%; discharging; 4:58 remaining present: true
"""

spec = importlib.util.spec_from_file_location("evaluate", REPO_ROOT / "scripts" / "evaluate.py")
evaluate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluate)


def test_lecture_secteur_batterie_illisible():
    assert parse_pmset(SECTEUR) == "secteur"
    assert parse_pmset(BATTERIE) == "batterie"
    assert parse_pmset("Now drawing from 'UPS Power'\n") == "UPS Power"
    assert parse_pmset("") is None
    assert parse_pmset(None) is None
    assert parse_pmset("pmset: commande inconnue") is None


def test_releve_consigne_la_premiere_ligne():
    reading = power_reading("debut", lambda: BATTERIE)
    assert reading["moment"] == "debut"
    assert reading["source"] == "batterie"
    assert reading["brut"] == "Now drawing from 'Battery Power'"
    illisible = power_reading("fin", lambda: None)
    assert illisible["source"] is None and illisible["brut"] is None


def releves(*sources):
    return [{"source": source} for source in sources]


def test_conformite():
    assert is_compliant(releves("secteur", "secteur", "secteur")) is True
    assert is_compliant(releves("secteur", "batterie", "secteur")) is False
    assert is_compliant(releves("UPS Power")) is False
    assert is_compliant(releves("secteur", None)) is None
    assert is_compliant(releves(None, "batterie")) is False  # un relevé hors secteur suffit
    assert is_compliant([]) is None
    assert is_compliant(None) is None


def test_releves_debut_periodiques_fin():
    sorties = iter([SECTEUR] * 3 + [BATTERIE] * 100)
    monitor = PowerMonitor(interval_s=0.02, reader=lambda: next(sorties))
    monitor.start()
    time.sleep(0.15)
    monitor.stop()
    block = monitor.block()
    moments = [r["moment"] for r in block["releves"]]
    assert moments[0] == "debut" and moments[-1] == "fin"
    assert moments.count("periodique") >= 2
    assert set(moments[1:-1]) == {"periodique"}
    assert block["commande"] == "pmset -g batt"
    assert block["conforme"] is False


def test_temps_conforme_dans_les_resultats():
    fichiers = [{"uri": "a", "duree_audio_s": 100.0, "calcul_s": 5.0}]
    base = {"device": "mps", "chargement_modeles_s": 1.0, "fichiers": fichiers}
    secteur = {**base, "alimentation": {"releves": releves("secteur", "secteur")}}
    batterie = {**base, "alimentation": {"releves": releves("secteur", "batterie")}}
    illisible = {**base, "alimentation": {"releves": releves(None, None)}}
    assert evaluate.timing_block(secteur, ["a"])["conforme"] is True
    assert evaluate.timing_block(batterie, ["a"])["conforme"] is False
    assert evaluate.timing_block(illisible, ["a"])["conforme"] is None
    assert evaluate.timing_block(base, ["a"])["conforme"] is None  # exécution antérieure à D21
