"""Contrôle de l'alimentation (D21 §3) et de la charge (D21, amendement du 01/11) : lecture de
pmset, relevés, conformité et charge concurrente, sur sorties simulées."""

import importlib.util
import time

from whospoke import charge
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

spec = importlib.util.spec_from_file_location("run_experiment", REPO_ROOT / "scripts" / "run_experiment.py")
run_experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_experiment)


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


# --- Charge de la machine (D21, amendement du 01/11) ----------------------------------


def test_bloc_d_execution_avec_la_charge():
    """Relevés de whospoke.charge aux mêmes instants que l'alimentation ; bloc consigné."""
    loads = iter([(3.0, 3.0, 3.0)] * 3 + [(8.5, 4.0, 3.0)] * 100)
    monitor = charge.MachineMonitor(interval_s=0.02, power_reader=lambda: SECTEUR,
                                    load_reader=lambda: next(loads))
    monitor.start()
    time.sleep(0.15)
    monitor.stop()
    block = run_experiment.machine_block(list(monitor.readings), 6, monitor.interval_s)
    assert block["commande"] == "pmset -g batt"
    assert block["coeurs_performance"] == 6
    assert all({"source", "charge_1min", "charge_5min", "charge_15min"} <= set(r) for r in block["releves"])
    moments = [r["moment"] for r in block["releves"]]
    assert moments[0] == "debut" and moments[-1] == "fin"
    assert block["conforme"] is True
    assert block["charge_concurrente"] is True
    calme = [{"source": "secteur", "charge_1min": 2.0}, {"source": "secteur", "charge_1min": 6.0}]
    assert run_experiment.machine_block(calme, 6, 60.0)["charge_concurrente"] is False  # égal : pas de dépassement


def test_charge_concurrente_dans_les_resultats():
    fichiers = [{"uri": "a", "duree_audio_s": 100.0, "calcul_s": 5.0}]
    base = {"device": "mps", "chargement_modeles_s": 1.0, "fichiers": fichiers}
    releves_charge = [{"source": "secteur", "charge_1min": 2.0}, {"source": "secteur", "charge_1min": 9.0}]
    chargee = {**base, "alimentation": {"releves": releves_charge, "coeurs_performance": 6}}
    calme = {**base, "alimentation": {"releves": releves_charge[:1], "coeurs_performance": 6}}
    illisible = {**base, "alimentation": {"releves": [{"source": "secteur", "charge_1min": None}],
                                          "coeurs_performance": 6}}
    ancienne = {**base, "alimentation": {"releves": releves("secteur", "secteur")}}  # avant l'amendement
    assert evaluate.timing_block(chargee, ["a"])["charge_concurrente"] is True
    assert evaluate.timing_block(calme, ["a"])["charge_concurrente"] is False
    assert evaluate.timing_block(illisible, ["a"])["charge_concurrente"] is None
    assert evaluate.timing_block(ancienne, ["a"])["charge_concurrente"] is None
    assert evaluate.timing_block(base, ["a"])["charge_concurrente"] is None
    cpu = {**chargee, "mode": "mesure_cpu", "sous_ensemble": "x", "duree_audio_s": 100.0,
           "calcul_s": 5.0, "rtf": 0.05}
    assert evaluate.cpu_block(cpu)["charge_concurrente"] is True
    assert evaluate.cpu_block({**calme, "mode": "complet"}, None)["charge_concurrente"] is False
