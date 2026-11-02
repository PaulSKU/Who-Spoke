"""Fonctions et exécution de scripts/analyses/a0003_cas_echec.py (D28 §1), sur données fabriquées.

Aucune donnée réelle : références et hypothèses tirées au hasard (graine fixe), audio de bruit
synthétique, per_file calculés par l'évaluateur du protocole.
"""

import csv
import importlib.util
import json
import sys

import numpy as np
import pytest
import yaml
from pyannote.core import Annotation, Segment, Timeline
from scipy.io import wavfile

from app import sortie
from whospoke.evaluation.metrics import DiarizationEvaluator
from whospoke.experiment import REPO_ROOT

spec = importlib.util.spec_from_file_location("a0003", REPO_ROOT / "scripts" / "analyses" / "a0003_cas_echec.py")
a0003 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a0003)

RATE = 16000
DURATION = 60.0
UEM = (0.5, 59.5)


def annotation(uri, turns):
    out = Annotation(uri=uri)
    for k, (start, end, label) in enumerate(turns):
        out[Segment(start, end), k] = label
    return out


def write_rttm(path, ann):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"SPEAKER {ann.uri} 1 {s.start:.3f} {s.duration:.3f} <NA> <NA> {label} <NA> <NA>\n"
                            for s, _, label in ann.itertracks(yield_label=True)))


def random_reference(uri, rng, n_speakers):
    turns, t = [], 1.0
    while t < DURATION - 3:
        length = float(rng.choice([0.3, 0.4, 0.8, 1.5, 3.0, 5.0]))
        label = f"S{int(rng.integers(n_speakers))}"
        turns.append((round(t, 2), round(min(t + length, DURATION - 1), 2), label))
        t += length + float(rng.choice([-0.4, 0.0, 0.2, 0.6, 1.5]))   # négatif : chevauchement
    return annotation(uri, turns)


def degraded(ref, rng, drop=None, merge=None, jitter=0.2):
    turns = []
    for s, _, label in ref.itertracks(yield_label=True):
        if label == drop:
            continue
        label = merge.get(label, label) if merge else label
        a, b = s.start + rng.uniform(-jitter, jitter), s.end + rng.uniform(-jitter, jitter)
        if b - a > 0.05:
            turns.append((max(a, 0.0), b, f"H{label}"))
    turns.append((DURATION - 0.9, DURATION - 0.6, "Hbruit"))   # hors UEM : sans effet
    return annotation(ref.uri, turns)


@pytest.fixture
def depot(tmp_path, monkeypatch):
    """Dépôt fabriqué : corpus public `fab` (dev 4, test 3 fichiers), corpus `maison` (2),
    deux systèmes, références, UEM, audio et per_file."""
    rng = np.random.default_rng(0)
    data, splits, experiments = tmp_path / "data", tmp_path / "splits", tmp_path / "depot" / "experiments"
    monkeypatch.setattr(a0003, "SPLITS_DIR", splits)
    systems = {"EXP-9001_sys-a": {}, "EXP-9002_sys-b": {}}
    layout = {("fab", "dev"): ["fab__d1", "fab__d2", "fab__d3", "fab__d4"], ("fab", "test"): ["fab__t1", "fab__t2", "fab__t3"],
              ("maison", "eval"): ["maison__M01", "maison__M02"]}
    for (corpus, partition), uris in layout.items():
        (splits / corpus).mkdir(parents=True, exist_ok=True)
        (splits / corpus / f"{partition}.txt").write_text("\n".join(uris) + "\n")
        uem_dir = (data / "processed" / "maison" / "uem") if corpus == "maison" else (splits / corpus / "uem")
        uem_dir.mkdir(parents=True, exist_ok=True)
        for k, uri in enumerate(uris):
            (uem_dir / f"{uri}.uem").write_text(f"{uri} 1 {UEM[0]:.3f} {UEM[1]:.3f}\n")
            ref = random_reference(uri, rng, 2 + k % 3)
            write_rttm(data / "processed" / corpus / "rttm" / f"{uri}.rttm", ref)
            noise = (rng.normal(0, 0.05, int(DURATION * RATE)) * 32767).astype(np.int16)
            wavfile.write(data / "processed" / corpus / f"{uri}.wav", RATE, noise)
            labels = sorted(ref.labels())
            hyps = {"EXP-9001_sys-a": degraded(ref, rng, jitter=0.15),
                    "EXP-9002_sys-b": degraded(ref, rng, drop=labels[-1] if k % 2 else None,
                                               merge={labels[0]: labels[1]} if len(labels) > 2 else None, jitter=0.4)}
            for name, hyp in hyps.items():
                write_rttm(experiments / name / "rttm" / f"{uri}.rttm", hyp)
                uem = Timeline([Segment(*UEM)])
                systems[name].setdefault((corpus, partition), []).append((ref, hyp, uem))
    for name, by_set in systems.items():
        for (corpus, partition), triples in by_set.items():
            evaluator = DiarizationEvaluator()
            for ref, hyp, uem in triples:
                evaluator.add(ref, hyp, uem=uem)
            rows = evaluator.per_file()
            with (experiments / name / f"per_file_{corpus}_{partition}.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
    config = yaml.safe_load((REPO_ROOT / "analyses" / "A-0003_cas-echec" / "config.yaml").read_text())
    config["systemes"] = [
        {"nom": "sys-a", "sources": [{"exp_id": "EXP-9001", "corpus": "fab", "partitions": ["dev", "test"]},
                                     {"exp_id": "EXP-9001", "corpus": "maison", "partitions": ["eval"]}]},
        {"nom": "sys-b", "sources": [{"exp_id": "EXP-9002", "corpus": "fab", "partitions": ["dev", "test"]}]},
    ]
    config["classement"]["n_pires"] = 2
    config["descripteurs"]["type_reunion"] = {"fab": [str(splits / "fab" / "test.txt")]}
    config["extraits"].update({"corpus": ["fab"], "n_min": 3, "n_max": 6, "max_par_systeme": 4, "max_par_corpus": 6})
    return {"config": config, "data": data, "experiments": experiments, "out": tmp_path / "sortie",
            "ecoute": tmp_path / "a0003" / "ecoute"}


def read(path):
    with path.open() as handle:
        return list(csv.DictReader(handle))


def run(depot):
    return a0003.run(depot["config"], depot["out"], depot["data"], depot["ecoute"], depot["experiments"])


# --- Catégories : même définition que la carte de l'application ---------------------------


def test_zone_suit_les_constats_de_la_carte():
    # A parle de 0 à 10 s, B de 10,3 à 20 s (pause de 0,3 s), C dit « oui » de 30 à 30,4 s.
    ref = annotation("u", [(0.0, 10.0, "A"), (10.3, 20.0, "B"), (30.0, 30.4, "C"), (40.0, 50.0, "A")])
    hyp = annotation("u", [(0.0, 10.3, "x"), (10.3, 20.0, "y"), (40.0, 50.0, "x")])
    errors = a0003.file_errors(ref, hyp, Timeline([Segment(0.0, 60.0)]))
    zones = {(z["type"], z["debut"]): z for z in a0003.categorized_zones(errors)}
    assert zones[("fausse_alarme", 10.0)]["categories"] == {"pause", "frontiere"}
    assert zones[("manquee", 30.0)]["categories"] == {"tour_court", "frontiere", "non_apparie"}
    # Mêmes constats que ceux de la carte (`_Context.describe`), zone par zone.
    for zone in errors["zones"]:
        context = zone["contexte"]
        found = zones[(zone["type"], zone["debut"])]["categories"]
        assert ("chevauchement" in found) == (context["chevauchement_s"] > 0)
        assert ("tour_court" in found) == bool(context["tour_court"])
        assert ("pause" in found) == bool(context["pause"])
        assert ("frontiere" in found) == (context["frontiere_s"] is not None)


def test_seuils_lus_dans_l_application():
    ref = annotation("u", [(0.0, 10.0, "A"), (20.0, 20.0 + sortie.SHORT_TURN_S + 0.01, "B")])
    hyp = annotation("u", [(0.0, 10.0, "x")])
    zones = a0003.categorized_zones(a0003.file_errors(ref, hyp, Timeline([Segment(0.0, 30.0)])))
    assert "tour_court" not in zones[0]["categories"]


def test_uem_officiel_comme_le_protocole():
    ref = annotation("u", [(0.0, 5.0, "A"), (6.0, 20.0, "B")])
    hyp = annotation("u", [(0.0, 3.0, "x"), (6.0, 25.0, "y")])
    uem = Timeline([Segment(2.0, 22.0)])
    errors = a0003.file_errors(ref, hyp, uem)
    row = DiarizationEvaluator().add(ref, hyp, uem=uem)["collar_0"]
    for kind in a0003.ERROR_TYPES:
        assert errors["totaux"][kind] == pytest.approx(row[f"{kind}_s"], abs=1e-6)
    counts = a0003.tally(a0003.categorized_zones(errors))
    assert counts["tous"]["erreur_s"] == pytest.approx(sum(row[f"{k}_s"] for k in a0003.ERROR_TYPES), abs=1e-3)


def test_decompte_seules_et_aucune():
    zones = [{"type": "manquee", "debut": 0.0, "fin": 2.0, "categories": {"chevauchement"}},
             {"type": "manquee", "debut": 3.0, "fin": 4.0, "categories": {"chevauchement", "pause"}},
             {"type": "confusion", "debut": 5.0, "fin": 5.5, "categories": set()}]
    counts = a0003.tally(zones)
    assert counts["tous"]["erreur_s"] == pytest.approx(3.5)
    assert counts["tous"]["chevauchement_s"] == pytest.approx(3.0)
    assert counts["tous"]["chevauchement_seule_s"] == pytest.approx(2.0)
    assert counts["tous"]["aucune_s"] == pytest.approx(0.5)
    assert counts["confusion"]["erreur_s"] == pytest.approx(0.5) and counts["fausse_alarme"]["n_zones"] == 0
    row = a0003.tally_row(counts["tous"], with_share=True)
    assert row["chevauchement_pct"] == pytest.approx(85.71) and row["duree_mediane_zone_s"] == 1.0


# --- Descripteurs et corrélations --------------------------------------------------------


def test_descripteurs():
    ref = annotation("u", [(0.0, 4.0, "A"), (3.0, 3.5, "B"), (6.0, 6.8, "A"), (8.0, 12.0, "C"), (30.0, 31.0, "B")])
    out = a0003.descriptors(ref, Timeline([Segment(0.0, 20.0)]), short_turn_s=1.0)
    # Hors UEM, le dernier tour ne compte pas. Parole : 4 + 0,8 + 4 = 8,8 s ; chevauchement 0,5 s.
    assert out["n_locuteurs"] == 3 and out["n_tours"] == 4
    assert out["part_parole"] == pytest.approx(8.8 / 20.0)
    assert out["part_chevauchement"] == pytest.approx(round(0.5 / 8.8, 4))
    assert out["part_tours_courts"] == pytest.approx(0.5)
    assert out["duree_moyenne_tour_s"] == pytest.approx((4 + 0.5 + 0.8 + 4) / 4, abs=1e-3)


def test_spearman_descriptif():
    assert a0003.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert a0003.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0
    assert a0003.spearman([1, 1, 1, 1], [1, 2, 3, 4]) is None
    assert a0003.spearman([1, None, 3], [1, 2, 3]) is None   # moins de 3 paires


# --- Extraits ----------------------------------------------------------------------------


def test_fenetres_et_dominance():
    zones = [{"type": "manquee", "debut": 10.0, "fin": 14.0, "categories": {"chevauchement"}},
             {"type": "confusion", "debut": 40.0, "fin": 41.0, "categories": {"pause", "frontiere"}}]
    starts, scores = a0003.window_scores(zones, 0.0, 60.0, 15.0, 0.5)
    assert starts[-1] == pytest.approx(45.0)
    assert scores["tous"].max() == pytest.approx(4.0, abs=0.06)
    assert scores["chevauchement"][starts == 5.0][0] == pytest.approx(4.0, abs=0.06)
    candidate = {"systeme": "s", "exp_id": "E", "corpus": "c", "partition": "dev", "uri": "u", "der_c0": 50.0,
                 "uem_debut": 0.0, "uem_fin": 60.0, "zones": zones}
    chosen = a0003.select_excerpts([candidate], {"duree_s": 15, "pas_s": 0.5, "n_min": 1, "n_max": 3,
                                                 "max_par_systeme": 3, "max_par_corpus": 3})
    # Un fichier au plus une fois : la première catégorie trouvée le prend.
    assert len(chosen) == 1 and chosen[0]["categorie"] == "chevauchement"
    assert chosen[0]["debut"] <= 10.0 and chosen[0]["fin"] >= 14.0 and chosen[0]["fin"] - chosen[0]["debut"] == 15.0


def test_maison_refuse_dans_les_extraits_publics(depot):
    depot["config"]["extraits"]["corpus"] = ["fab", "maison"]
    with pytest.raises(SystemExit):
        run(depot)


# --- Exécution complète ------------------------------------------------------------------


def test_execution_complete(depot):
    details = run(depot)
    out = depot["out"]
    ranking = read(out / "classement.csv")
    assert len(ranking) == 7 + 2 + 7
    for system, corpus, n in (("sys-a", "fab", 7), ("sys-b", "fab", 7), ("sys-a", "maison", 2)):
        rows = [r for r in ranking if r["systeme"] == system and r["corpus"] == corpus]
        assert [int(r["rang"]) for r in rows] == list(range(1, n + 1))
        ders = [float(r["der_c0"]) for r in rows]
        assert ders == sorted(ders, reverse=True)
        assert sum(r["pire"] == "True" for r in rows) == min(2, n)
    # Contrôle : la carte de l'application redonne les composantes du per_file.
    assert max(details["controle_totaux_ecart_max_s"].values()) <= a0003.TOTALS_TOLERANCE_S
    categories = read(out / "categories.csv")
    per_file = {}
    for name in ("per_file_fab_dev.csv", "per_file_fab_test.csv"):
        per_file.update({r["uri"]: r for r in read(depot["experiments"] / "EXP-9002_sys-b" / name)})
    total = sum(float(r[f"{k}_c0_s"]) for r in per_file.values() for k in a0003.ERROR_TYPES)
    row = next(r for r in categories if r["systeme"] == "sys-b" and r["type_erreur"] == "tous")
    assert float(row["erreur_s"]) == pytest.approx(total, abs=0.05)
    for category in a0003.CATEGORIES:
        assert float(row[f"{category}_seule_s"]) <= float(row[f"{category}_s"]) <= float(row["erreur_s"]) + 1e-6
    # Descripteurs : un par corpus × fichier ; type de réunion d'après la liste déclarée.
    descriptors = {(r["corpus"], r["uri"]): r for r in read(out / "descripteurs.csv")}
    assert len(descriptors) == 9
    assert descriptors[("fab", "fab__t1")]["type_reunion"] == "zoom"
    assert descriptors[("fab", "fab__d1")]["type_reunion"] == "autre"
    assert descriptors[("maison", "maison__M01")]["type_reunion"] == ""
    correlations = read(out / "correlations.csv")
    assert {r["descripteur"] for r in correlations if r["corpus"] == "maison"} == (
        set(depot["config"]["correlations"]["descripteurs"]) - {"zoom"})
    assert all(r["rho_spearman"] == "" or -1.0 <= float(r["rho_spearman"]) <= 1.0 for r in correlations)


def test_extraits_publics_et_locaux(depot):
    details = run(depot)
    excerpts = read(depot["out"] / "extraits.csv")
    spec = depot["config"]["extraits"]
    assert spec["n_min"] <= len(excerpts) <= spec["n_max"] and details["extraits"]["public"] == len(excerpts)
    assert {r["corpus"] for r in excerpts} == {"fab"}                       # jamais le corpus maison
    assert len({r["uri"] for r in excerpts}) == len(excerpts)
    assert all(sum(r["systeme"] == s for r in excerpts) <= spec["max_par_systeme"] for s in ("sys-a", "sys-b"))
    assert [r["motif"] for r in excerpts] == sorted((r["motif"] for r in excerpts), key=lambda m: m != "categorie")
    listen = depot["ecoute"]
    for r in excerpts:
        rate, data = wavfile.read(listen / r["fichier_audio"])
        assert rate == RATE and len(data) == pytest.approx((float(r["fin"]) - float(r["debut"])) * RATE, abs=2)
        assert float(r["fin"]) - float(r["debut"]) == pytest.approx(15.0)
        assert UEM[0] <= float(r["debut"]) and float(r["fin"]) <= UEM[1]
    page = (listen / "index.html").read_text()
    assert page.count("<audio") == len(excerpts) and "grille_remplie.csv" in page
    assert "maison" not in page
    grid = read(listen / "grille.csv")
    assert [g["extrait"] for g in grid] == [r["extrait"] for r in excerpts]
    assert all(g[c] == "" for g in grid for c in a0003.CAUSES)
    # Corpus maison : dossier local à part, avec sa propre liste ; rien dans le dossier de l'analyse.
    local = depot["ecoute"].parent / "ecoute_maison"
    local_rows = read(local / "extraits.csv")
    assert local_rows and {r["corpus"] for r in local_rows} == {"maison"}
    assert details["extraits"]["local"] == len(local_rows)
    assert not any("maison" in path.name for path in depot["out"].iterdir())


def test_main_essai_et_immutabilite(depot, monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(depot["config"], allow_unicode=True))
    args = ["a0003", "--config", str(config_path), "--donnees", str(depot["data"]),
            "--experiences", str(depot["experiments"]), "--sortie", str(depot["out"])]
    monkeypatch.setattr(sys, "argv", args)
    a0003.main()
    execution = json.loads((depot["out"] / "execution.json").read_text())
    assert execution["essai"] is True and execution["analyse_id"] == "A-0003"
    assert set(execution["seuils_carte"]) == {"tour_court_s", "pause_courte_s", "frontiere_s", "contigu_s"}
    assert (depot["out"] / "ecoute" / "index.html").exists()
    with pytest.raises(SystemExit):                       # exécutée : immuable
        a0003.main()
    monkeypatch.setattr(sys, "argv", ["a0003", "--config", str(config_path),
                                      "--sortie", str(REPO_ROOT / "analyses" / "essai")])
    with pytest.raises(SystemExit):                       # un essai ne s'écrit pas dans analyses/
        a0003.main()


def test_script_lancable_hors_de_pytest():
    import subprocess

    result = subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "analyses" / "a0003_cas_echec.py"), "--help"],
                            cwd=REPO_ROOT / "scripts", capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
