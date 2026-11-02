"""Campagne de temps (chantier E3a, scripts/campagne_temps.py), avec le moteur factice.

Aucune inférence : le moteur factice de l'application simule le RTF demandé, sur des
audios de synthèse de quelques secondes. Les relevés d'alimentation et de charge sont
simulés.
"""

import csv
import importlib.util
import json

import numpy as np
import pytest
import yaml
from scipy.io import wavfile

from app import moteurs
from whospoke import charge
from whospoke.experiment import REPO_ROOT

spec_ = importlib.util.spec_from_file_location("campagne_temps", REPO_ROOT / "scripts" / "campagne_temps.py")
campagne = importlib.util.module_from_spec(spec_)
spec_.loader.exec_module(campagne)

SR = 16000
AC = "Now drawing from 'AC Power'\n -InternalBattery-0 100%; charged;"
BATTERY = "Now drawing from 'Battery Power'\n -InternalBattery-0 80%; discharging;"
SUBSET = [("summre", "summre__r1"), ("summre", "summre__r2"), ("ami", "ami__r3")]
DURATIONS = {"summre__r1": 20.0, "summre__r2": 12.0, "ami__r3": 16.0}


def fake_root(tmp_path, uris=tuple(DURATIONS)):
    """Expérience source factice (EXP-0099) avec un RTTM par réunion de synthèse."""
    directory = tmp_path / "experiments" / "EXP-0099_essai"
    (directory / "rttm").mkdir(parents=True)
    (directory / "config.yaml").write_text(yaml.safe_dump({"device": "cpu", "pipeline": {"parametres": {}}}))
    (directory / "execution_cpu.json").write_text(json.dumps({"balayage": {"parametre": "theta", "valeur_retenue": 1.0}}))
    for uri in uris:
        (directory / "rttm" / f"{uri}.rttm").write_text(
            f"SPEAKER {uri} 1 0.500 3.000 <NA> <NA> SPK_00 <NA> <NA>\n"
            f"SPEAKER {uri} 1 4.000 3.000 <NA> <NA> SPK_01 <NA> <NA>\n")
    return tmp_path / "experiments"


def audio(tmp_path):
    rng = np.random.default_rng(0)
    for uri, duration in DURATIONS.items():
        wavfile.write(tmp_path / f"{uri}.wav", SR, (3000 * rng.standard_normal(int(duration * SR))).astype(np.int16))
    return lambda corpus, uri: tmp_path / f"{uri}.wav"


SPEC = moteurs.EngineSpec("essai", "Essai", "baseline", "EXP-0099", moteurs.BASELINE_STEPS, True, False)


def monitor(source=AC, load=0.5):
    return charge.MachineMonitor(interval_s=0.05, power_reader=lambda: source, load_reader=lambda: (load, load, load))


def run(tmp_path, **kwargs):
    root = fake_root(tmp_path)
    factory = lambda spec, device: moteurs.FakeEngine(spec, root, ticks_per_step=1)  # noqa: E731
    info = {"source": "temps.txt (protocole §3.5)", "fichiers": [{"corpus": c, "uri": u} for c, u in SUBSET]}
    options = dict(wav_path=audio(tmp_path), monitor=monitor(), cores=6, factice_rtf=0.02, load_max=1.5,
                   rest={"date": "2026-11-12T08:00:00+01:00", "charge_1min": {"moyenne": 0.9, "min": 0.6, "max": 1.2}},
                   sleep=lambda s: None, out=lambda m: None) | kwargs
    return campagne.campaign([(SPEC, "cpu")], SUBSET, info, factory, **options)


def test_sous_ensemble_du_protocole(tmp_path):
    for corpus in ("summre", "ami"):
        (tmp_path / corpus).mkdir()
        (tmp_path / corpus / "temps.txt").write_text(f"{corpus}__00\n{corpus}__05\n")
    subset, info = campagne.select_subset(splits=tmp_path)
    assert [u for _, u in subset] == ["summre__00", "summre__05", "ami__00", "ami__05"]
    assert "temps.txt" in info["source"] and [f["uri"] for f in info["fichiers"]] == [u for _, u in subset]


def test_sous_ensemble_du_depot():
    subset, _ = campagne.select_subset()
    expected = [(c, u) for c in ("summre", "ami")
                for u in (REPO_ROOT / "data" / "splits" / c / "temps.txt").read_text().split()]
    assert subset == expected and len(subset) == 4


def test_conditions_de_depart():
    reads = iter([{"source": "batterie", "charge_1min": 0.4}, {"source": "secteur", "charge_1min": 5.0},
                  {"source": "secteur", "charge_1min": 1.0}])
    ok, readings = campagne.wait_for_conditions(lambda: next(reads), 1.5, 600, sleep=lambda s: None, out=lambda m: None)
    assert ok and len(readings) == 3
    ok, readings = campagne.wait_for_conditions(lambda: {"source": "batterie", "charge_1min": 0.2}, 1.5, 30,
                                                poll_s=15, sleep=lambda s: None, out=lambda m: None)
    assert not ok and len(readings) == 3


def test_mesure_au_repos():
    loads = iter([0.8, 1.2, 1.0, 0.6, 0.9, 1.1, 0.7])
    read = lambda: {"source": "secteur", "charge_1min": next(loads)}  # noqa: E731
    slept = []
    rest = campagne.measure_rest(30.0, 5.0, read=read, sleep=slept.append, cores=6, out=lambda m: None)
    assert len(rest["releves"]) == 7 and slept == [5.0] * 6
    assert rest["charge_1min"] == {"moyenne": 0.9, "min": 0.6, "max": 1.2}
    assert rest["alimentation_conforme"] is True and rest["coeurs_performance"] == 6


def test_charge_concurrente():
    readings = [{"charge_1min": 2.0}, {"charge_1min": 6.5}]
    assert charge.concurrent_load(readings, 6) is True
    assert charge.concurrent_load(readings[:1], 6) is False
    assert charge.concurrent_load([{"charge_1min": None}], 6) is None


def test_campagne_avec_le_moteur_factice(tmp_path):
    result = run(tmp_path)
    (measure,) = result["mesures"]
    assert [m["uri"] for m in measure["reunions"]] == [u for _, u in SUBSET]
    assert all(m["erreur"] is None and m["conforme"] for m in measure["reunions"])
    summary = measure["synthese"]
    assert 0.02 <= summary["rtf"] < 0.06
    assert set(summary["rtf_par_corpus"]) == {"summre", "ami"}
    assert summary["temps_30min_s"] == pytest.approx(summary["rtf"] * 1800, abs=0.1)
    assert summary["surcout_fixe_s"] >= 0 and summary["conforme"]
    assert measure["prechauffage"]["duree_s"] == pytest.approx(20.0)   # 60 s demandées, réunion de 20 s
    assert result["factice"] and result["conditions_depart"]["reunies"]
    moments = [r["moment"] for r in result["releves"]["releves"]]
    assert moments[0] == "debut" and moments[-1] == "fin" and moments.count("debut_reunion") == 3
    assert "FixedOverhead(" in result["interface"]["code"] and "essai/cpu" in result["interface"]["rtf"]

    campagne.write_outputs(tmp_path / "sortie", result)
    rows = list(csv.DictReader((tmp_path / "sortie" / "mesures.csv").open()))
    assert len(rows) == 3 and rows[0]["moteur"] == "essai"
    table = (tmp_path / "sortie" / "tableau.md").read_text()
    assert "MOTEUR FACTICE" in table and "| Essai | cpu |" in table and "FIXED_OVERHEAD" in table
    saved = json.loads((tmp_path / "sortie" / "campagne.json").read_text())
    assert saved["charge_au_repos"]["charge_1min"]["max"] == 1.2 and saved["conditions_depart"]["charge_max"] == 1.5
    assert "Seuil de charge au départ : 1.5 ; charge sur 1 min au repos mesurée le 2026-11-12T08:00" in table


def test_batterie_campagne_refusee_ou_non_conforme(tmp_path):
    with pytest.raises(RuntimeError, match="Conditions de départ"):
        run(tmp_path, monitor=monitor(BATTERY), wait_max_s=0)
    result = run(tmp_path / "b", monitor=monitor(BATTERY), wait_max_s=0, ignore_conditions=True)
    measure = result["mesures"][0]
    assert not result["conditions_depart"]["reunies"]
    assert all(m["alimentation_conforme"] is False and not m["conforme"] for m in measure["reunions"])
    assert not measure["synthese"]["conforme"]
    assert "Conditions de départ non réunies" in campagne.markdown(result)


def test_charge_concurrente_rend_la_reunion_non_conforme(tmp_path):
    result = run(tmp_path, monitor=monitor(load=8.0), load_max=10.0)
    assert all(m["charge_concurrente"] is True and not m["conforme"] for m in result["mesures"][0]["reunions"])


def test_erreur_sur_une_reunion_consignee(tmp_path):
    root = fake_root(tmp_path, uris=("summre__r1", "summre__r2"))   # pas de RTTM pour ami__r3
    factory = lambda spec, device: moteurs.FakeEngine(spec, root, ticks_per_step=1)  # noqa: E731
    result = campagne.campaign([(SPEC, "cpu")], SUBSET, {}, factory, wav_path=audio(tmp_path), monitor=monitor(),
                               cores=6, factice_rtf=0.02, sleep=lambda s: None, out=lambda m: None)
    measure = result["mesures"][0]
    assert measure["reunions"][2]["erreur"].startswith("FileNotFoundError")
    assert measure["synthese"]["n_reunions"] == 2 and measure["synthese"]["n_erreurs"] == 1
    assert not measure["synthese"]["conforme"]


def test_plan_des_moteurs(tmp_path):
    root = fake_root(tmp_path)
    pairs, skipped = campagne.engine_plan(["pyannote-community-1"], ["mps", "cpu"], root)
    assert pairs == [] and "EXP-0007" in skipped[0]
    pairs, _ = campagne.engine_plan(["baseline-mfcc", "pyannote-community-1"], ["mps", "cpu"])
    assert [(s.key, d) for s, d in pairs] == [("baseline-mfcc", "cpu"), ("pyannote-community-1", "mps"),
                                              ("pyannote-community-1", "cpu")]


def test_ligne_de_commande(capsys):
    assert campagne.main(["--plan", "--moteurs", "baseline-mfcc"]) == 0
    out = capsys.readouterr().out
    assert "temps.txt" in out and "summre__007a_ECRH" in out and "Baseline MFCC (cpu)" in out
    assert campagne.main(["--plan", "--moteurs", "inconnu"]) == 2
    assert campagne.main(["--moteurs", "baseline-mfcc"]) == 2          # sans --repos ni --charge-max
    assert "obligatoires" in capsys.readouterr().out
