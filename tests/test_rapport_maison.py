"""Rapport d'évaluation du corpus maison (chantier E3b, scripts/rapport_maison.py).

Données synthétiques uniquement : références écrites à la main, audio de bruit ou réunion
de synthèse ; moteurs simulés (sortie connue) et baseline MFCC, sans modèle neuronal.
"""

import csv
import importlib.util
import json
import os

import numpy as np
import pytest
from pyannote.core import Annotation, Segment
from scipy.io import wavfile

from app import moteurs
from whospoke import charge
from whospoke.experiment import REPO_ROOT, load_rttm
from whospoke.pipelines.base import Engine, Resultat


def load_script(name, relative):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rapport = load_script("rapport_maison", "scripts/rapport_maison.py")
SR = 16000
TURNS = [("M01_S1", 1.0, 4.0), ("M01_S2", 4.5, 8.0), ("M01_S1", 8.5, 10.0)]
CONDITIONS = {"M01": "salle", "M02": "visio"}


def write_recording(processed, raw, session, condition=None, uem=True, signal=None):
    uri = f"maison__{session}"
    (processed / "rttm").mkdir(parents=True, exist_ok=True)
    (processed / "uem").mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(len(session))
    signal = signal if signal is not None else 0.05 * rng.standard_normal(12 * SR)
    wavfile.write(processed / f"{uri}.wav", SR, np.round(signal * 32767).astype(np.int16))
    (processed / "rttm" / f"{uri}.rttm").write_text("".join(
        f"SPEAKER {uri} 1 {a:.3f} {b - a:.3f} <NA> <NA> {code.replace('M01', session)} <NA> <NA>\n"
        for code, a, b in TURNS))
    if uem:
        (processed / "uem" / f"{uri}.uem").write_text(f"{uri} 1 0.500 11.000\n")
    if condition:
        (raw / session).mkdir(parents=True, exist_ok=True)
        (raw / session / "metadonnees.yaml").write_text(
            f"session: {session}\ncondition: {condition}\nconsentements:\n  S1: [1]\n  S2: [1, 3]\n")


class Stub(Engine):
    """Renvoie la référence, éventuellement privée de son dernier tour (parole manquée)."""

    name = "stub"

    def __init__(self, drop_last: bool) -> None:
        super().__init__()
        self.drop_last = drop_last

    def run(self, waveform, sample_rate=SR, uri=None, num_speakers=None, speech=None, progress=None):
        annotation = Annotation(uri=uri)
        turns = TURNS[:-1] if self.drop_last else TURNS
        for index, (code, a, b) in enumerate(turns):
            annotation[Segment(a, b), index] = "A" if code.endswith("S1") else "B"
        return Resultat(annotation=annotation)

    def describe(self):
        return {}


PERFECT = moteurs.EngineSpec("parfait", "Parfait", "baseline", "EXP-0098", moteurs.BASELINE_STEPS, True, False)
MISSING = moteurs.EngineSpec("manque", "Manque", "baseline", "EXP-0097", moteurs.BASELINE_STEPS, True, False)
PAIRS = [(PERFECT, "cpu", {"theta": 1.0}), (MISSING, "cpu", {"theta": 1.0})]


class Factory:
    def __init__(self):
        self.calls = []

    def __call__(self, spec, device):
        self.calls.append(spec.key)
        return Stub(drop_last=spec.key == "manque")


def quiet_monitor():
    return charge.MachineMonitor(interval_s=60, power_reader=lambda: "Now drawing from 'AC Power'",
                                 load_reader=lambda: (0.5, 0.5, 0.5))


def build(tmp_path, n=3, pairs=PAIRS, factory=None, recompute=False):
    processed, raw = tmp_path / "processed", tmp_path / "raw"
    for i in range(1, n + 1):
        session = f"M{i:02d}"
        if not (processed / "rttm" / f"maison__{session}.rttm").exists():
            write_recording(processed, raw, session, CONDITIONS.get(session))
    recs, incomplete = rapport.recordings(processed, raw)
    factory = factory or Factory()
    report = rapport.build_report(recs, incomplete, pairs, [], factory, tmp_path / "sortie", "essai synthétique",
                                  recompute, monitor=quiet_monitor(), out=lambda m: None)
    return report, factory


def test_metriques_par_fichier_et_mention(tmp_path):
    report, _ = build(tmp_path)
    perfect, missing = report["resultats"]
    assert [r["session"] for r in perfect["par_fichier"]] == ["M01", "M02", "M03"]
    assert [r["condition"] for r in perfect["par_fichier"]] == ["salle réverbérante", "visio", "non renseignée"]
    assert all(r["der_c0"] == pytest.approx(0.0) and r["der_c025"] == pytest.approx(0.0) for r in perfect["par_fichier"])
    row = missing["par_fichier"][0]
    # Dernier tour (1,5 s) manqué sur 8 s de parole de référence dans l'UEM.
    assert row["manquee_c0"] == pytest.approx(100 * 1.5 / 8.0)
    assert row["der_c0"] == pytest.approx(row["manquee_c0"])
    assert row["n_locuteurs_reference"] == 2 and row["n_locuteurs_hypothese"] == 2
    assert row["duree_uem_s"] == pytest.approx(10.5)
    assert {"jer_c0", "jer_c025", "der_chevauchement", "der_sans_chevauchement", "erreur_n_locuteurs"} <= set(row)
    assert perfect["bootstrap"] == {"collar_0": None, "collar_0_25": None}
    assert report["mention"].startswith("Test qualitatif") and report["controle_reseau_d27"] == "essai synthétique"

    out = tmp_path / "sortie"
    text = (out / "rapport.md").read_text()
    assert "**Test qualitatif : corpus maison de 3 enregistrement(s)" in text
    assert "Pas d'intervalle de confiance : moins de 5 fichiers." in text
    assert "| M02 | visio |" in text
    assert len(list(csv.DictReader((out / "par_fichier.csv").open()))) == 6
    assert json.loads((out / "rapport.json").read_text())["bootstrap_min_fichiers"] == 5


def test_bootstrap_a_partir_de_cinq_fichiers(tmp_path):
    report, _ = build(tmp_path, n=5)
    ci = report["resultats"][1]["bootstrap"]["collar_0"]
    assert ci is not None and ci["borne_inf"] <= ci["estimation"] <= ci["borne_sup"]
    assert "Intervalle de confiance à 95 %" in (tmp_path / "sortie" / "rapport.md").read_text()


def test_hypotheses_en_cache_et_nouvelle_reference(tmp_path):
    _, factory = build(tmp_path, n=2)
    assert factory.calls == ["parfait", "manque"]
    hyp = tmp_path / "sortie" / "hypotheses" / "manque" / "maison__M01.rttm"
    assert len(load_rttm(hyp, "maison__M01").labels()) == 2
    _, again = build(tmp_path, n=2)
    assert again.calls == []                          # rien de nouveau : aucun moteur chargé
    _, third = build(tmp_path, n=3)                   # nouvelle référence : seulement M03
    assert third.calls == ["parfait", "manque"]
    info = json.loads((tmp_path / "sortie" / "hypotheses" / "parfait" / "maison__M03.json").read_text())
    assert info["experience_source"] == "EXP-0098" and info["peripherique"] == "cpu"
    changed = [(PERFECT, "cpu", {"theta": 2.0}), PAIRS[1]]
    _, fourth = build(tmp_path, n=3, pairs=changed)   # réglage changé : recalcul de ce moteur seulement
    assert fourth.calls == ["parfait"]
    _, fifth = build(tmp_path, n=3, recompute=True)
    assert fifth.calls == ["parfait", "manque"]


def test_reference_incomplete_ecartee(tmp_path):
    processed, raw = tmp_path / "processed", tmp_path / "raw"
    write_recording(processed, raw, "M01", "salle")
    write_recording(processed, raw, "M02", uem=False)
    recs, incomplete = rapport.recordings(processed, raw)
    assert [r["uri"] for r in recs] == ["maison__M01"]
    assert incomplete == ["maison__M02 : uem absent(s)"]


def test_baseline_mfcc_sur_une_reunion_de_synthese(tmp_path):
    test_maison = load_script("test_maison_donnees", "tests/test_maison.py")
    table, _, _ = test_maison.meeting()
    processed, raw = tmp_path / "processed", tmp_path / "raw"
    write_recording(processed, raw, "M01", "bruit", signal=0.9 * table / np.abs(table).max())
    uri = "maison__M01"
    truth = [(f"M01_{c}", a, b) for c, a, b in test_maison.TURNS]
    (processed / "rttm" / f"{uri}.rttm").write_text("".join(
        f"SPEAKER {uri} 1 {a:.3f} {b - a:.3f} <NA> <NA> {code} <NA> <NA>\n" for code, a, b in truth))
    (processed / "uem" / f"{uri}.uem").write_text(f"{uri} 1 3.000 36.000\n")
    recs, _ = rapport.recordings(processed, raw)
    pairs, skipped = rapport.available_engines(["baseline-mfcc"], "cpu")
    assert skipped == [] and pairs[0][0].key == "baseline-mfcc" and "theta" in pairs[0][2]
    report = rapport.build_report(recs, [], pairs, [], moteurs.build_engine, tmp_path / "sortie", "essai",
                                  monitor=quiet_monitor(), out=lambda m: None)
    row = report["resultats"][0]["par_fichier"][0]
    assert row["condition"] == "bruit de fond" and row["n_locuteurs_reference"] == 3
    assert 0.0 <= row["der_c0"] <= 100.0 and row["n_locuteurs_hypothese"] >= 1


def test_controle_reseau_obligatoire(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(os, "environ", dict(os.environ))   # main() pose HF_HUB_OFFLINE
    write_recording(tmp_path / "processed", tmp_path / "raw", "M01", "salle")
    args = ["--references", str(tmp_path / "processed"), "--sessions", str(tmp_path / "raw"),
            "--moteurs", "baseline-mfcc", "--peripherique", "cpu"]
    assert rapport.main(args + ["--plan"]) == 0
    assert "maison__M01" in capsys.readouterr().out
    assert rapport.main(args) == 2
    assert "--controle-reseau obligatoire" in capsys.readouterr().out
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert not (tmp_path / "processed" / "rapport").exists()
