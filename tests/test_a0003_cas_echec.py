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


# --- Catégories : définition unique d'app/sortie.py -------------------------------------


def protocol_row(ref, hyp, uem):
    """Durées d'erreur du per_file du protocole, sans et avec collar."""
    result = DiarizationEvaluator().add(ref, hyp, uem=uem)
    return {f"{kind}_{suffix}_s": result[condition][f"{kind}_s"] for condition, suffix in
            (("collar_0", "c0"), ("collar_0_25", "c025")) for kind in a0003.ERROR_TYPES}


# A et B appariés ; C (« oui » de 0,4 s) et D jamais trouvés ; z trouvé en trop ; B dit par x.
REF = [(0.0, 10.0, "A"), (10.3, 20.0, "B"), (25.0, 28.0, "D"), (30.0, 30.4, "C"), (40.0, 50.0, "A"), (56.0, 58.0, "B")]
HYP = [(0.0, 10.3, "x"), (10.3, 20.0, "y"), (40.0, 48.0, "x"), (52.0, 55.0, "z"), (56.0, 58.0, "x")]


def test_categories_lues_dans_l_application():
    assert a0003.CATEGORIES == tuple(sortie.ERROR_CATEGORIES)
    assert a0003.CATEGORIES[0] == a0003.BOUNDARY and "trouve_en_trop" in a0003.CATEGORIES
    ref, hyp, uem = annotation("u", REF), annotation("u", HYP), Timeline([Segment(0.0, 60.0)])
    errors = a0003.file_errors(ref, hyp, uem)
    counts = a0003.tally(errors, protocol_row(ref, hyp, uem))
    for kind in a0003.ERROR_TYPES:                      # les secondes de la carte, sans recalcul
        assert counts[kind]["categories"] == errors["categories"][kind]
    assert counts["fausse_alarme"]["categories"]["trouve_en_trop"] == pytest.approx(3.0)
    assert counts["manquee"]["categories"]["reference_non_appariee"] == pytest.approx(2.5)   # 3 s − 2 × 0,25
    assert counts["confusion"]["categories"]["autre"] == pytest.approx(1.5)
    assert counts["manquee"]["categories"]["tour_court"] == 0.0     # 0,4 s : tout dans la tolérance


def test_frontiere_egale_l_erreur_pardonnee_par_le_collar():
    ref, hyp, uem = annotation("u", REF), annotation("u", HYP), Timeline([Segment(0.0, 60.0)])
    row = protocol_row(ref, hyp, uem)
    counts = a0003.tally(a0003.file_errors(ref, hyp, uem), row)
    for kind in a0003.ERROR_TYPES:
        line = a0003.tally_row(counts[kind], with_share=False)
        assert line["pardonne_collar_s"] == pytest.approx(row[f"{kind}_c0_s"] - row[f"{kind}_c025_s"], abs=1e-3)
        assert line["ecart_frontiere_collar_s"] == pytest.approx(0.0, abs=1e-3)
        assert line["erreur_s"] == pytest.approx(row[f"{kind}_c0_s"], abs=1e-3)


def test_parts_sur_toute_l_erreur_et_hors_frontiere():
    ref, hyp, uem = annotation("u", REF), annotation("u", HYP), Timeline([Segment(0.0, 60.0)])
    errors = a0003.file_errors(ref, hyp, uem)
    merged = a0003.merge_tallies([a0003.tally(errors, protocol_row(ref, hyp, uem))] * 2)
    line = a0003.tally_row(merged["tous"], with_share=True)
    assert sum(line[f"{c}_pct"] for c in a0003.CATEGORIES) == pytest.approx(100.0, abs=0.05)
    others = [c for c in a0003.CATEGORIES if c != a0003.BOUNDARY]
    assert sum(line[f"{c}_hors_frontiere_pct"] for c in others) == pytest.approx(100.0, abs=0.05)
    assert line["hors_frontiere_s"] == pytest.approx(line["erreur_s"] - line["frontiere_s"], abs=1e-3)
    assert line["erreur_s"] == pytest.approx(2 * sum(sum(v.values()) for v in errors["categories"].values()), abs=1e-3)
    assert line["n_zones"] == 2 * len(errors["zones"])


def test_uem_officiel_comme_le_protocole():
    ref = annotation("u", [(0.0, 5.0, "A"), (6.0, 20.0, "B")])
    hyp = annotation("u", [(0.0, 3.0, "x"), (6.0, 25.0, "y")])
    uem = Timeline([Segment(2.0, 22.0)])
    errors = a0003.file_errors(ref, hyp, uem)
    row = protocol_row(ref, hyp, uem)
    for kind in a0003.ERROR_TYPES:
        assert errors["totaux"][kind] == pytest.approx(row[f"{kind}_c0_s"], abs=1e-6)
    line = a0003.tally_row(a0003.tally(errors, row)["tous"], with_share=False)
    assert line["erreur_s"] == pytest.approx(sum(row[f"{k}_c0_s"] for k in a0003.ERROR_TYPES), abs=1e-3)
    assert line["ecart_frontiere_collar_s"] == pytest.approx(0.0, abs=1e-3)


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
    zones = [{"type": "manquee", "debut": 10.0, "fin": 14.0, "categorie": "chevauchement", "tolerance_s": 0.5},
             {"type": "confusion", "debut": 40.0, "fin": 41.0, "categorie": "pause", "tolerance_s": 0.0},
             {"type": "fausse_alarme", "debut": 50.0, "fin": 50.2, "categorie": "frontiere", "tolerance_s": 0.2}]
    starts, scores = a0003.window_scores(zones, 0.0, 60.0, 15.0, 0.5)
    assert starts[-1] == pytest.approx(45.0)
    assert scores["tous"][starts == 5.0][0] == pytest.approx(4.0, abs=0.06)
    assert scores["chevauchement"][starts == 5.0][0] == pytest.approx(3.5, abs=0.06)   # 4 s − 0,5 s de tolérance
    assert scores["frontiere"][starts == 5.0][0] == pytest.approx(0.5, abs=0.06)
    assert scores["frontiere"][starts == 45.0][0] == pytest.approx(0.2, abs=0.06)
    candidate = {"systeme": "s", "exp_id": "E", "corpus": "c", "partition": "dev", "uri": "u", "der_c0": 50.0,
                 "uem_debut": 0.0, "uem_fin": 60.0, "zones": zones}
    spec = {"duree_s": 15, "pas_s": 0.5, "n_min": 1, "n_max": 3, "max_par_systeme": 3, "max_par_corpus": 3,
            "categories_exclues": ["frontiere"]}
    chosen = a0003.select_excerpts([candidate], spec)
    # Un fichier au plus une fois : la première catégorie retenue trouvée le prend.
    assert len(chosen) == 1 and chosen[0]["categorie"] == "chevauchement"
    assert chosen[0]["debut"] <= 10.0 and chosen[0]["fin"] >= 14.0 and chosen[0]["fin"] - chosen[0]["debut"] == 15.0
    zones[0]["categorie"], zones[0]["tolerance_s"] = "frontiere", 4.0
    chosen = a0003.select_excerpts([candidate], spec)
    assert chosen[0]["categorie"] == "pause"                     # « frontiere » exclue des extraits


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
    assert sum(float(row[f"{c}_pct"]) for c in a0003.CATEGORIES) == pytest.approx(100.0, abs=0.05)
    pardonne = sum(float(r[f"{k}_c0_s"]) - float(r[f"{k}_c025_s"]) for r in per_file.values() for k in a0003.ERROR_TYPES)
    assert float(row["pardonne_collar_s"]) == pytest.approx(pardonne, abs=0.05)
    control = details["controle_frontiere_collar_s"]["sys-b/fab"]
    assert control["ecart_frontiere_collar_s"] == pytest.approx(control["frontiere_s"] - control["pardonne_collar_s"], abs=1e-3)
    assert details["categories"] == sortie.ERROR_CATEGORIES
    by_file = [r for r in read(out / "categories_par_fichier.csv") if r["systeme"] == "sys-b" and r["type_erreur"] == "tous"]
    assert len(by_file) == 7 and sum(float(r["erreur_s"]) for r in by_file) == pytest.approx(float(row["erreur_s"]), abs=0.05)
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
    assert page.count("<audio") == len(excerpts) and a0003.GRID in page and "--importer-grille" in page
    assert "maison" not in page
    assert all(r["categorie"] not in depot["config"]["extraits"]["categories_exclues"] for r in excerpts)
    grid = read(listen / a0003.GRID)
    assert [g["extrait"] for g in grid] == [r["extrait"] for r in excerpts] == [f"x{k}" for k in range(1, len(grid) + 1)]
    assert list(excerpts[0])[0] == "extrait"
    assert all(g[c] == "" for g in grid for c in a0003.CAUSES)
    # Corpus maison : dossier local à part, avec sa propre liste ; rien dans le dossier de l'analyse.
    local = depot["ecoute"].parent / "ecoute_maison"
    local_rows = read(local / "extraits.csv")
    assert (local / a0003.GRID).exists() and "jamais versionnée" in (local / "index.html").read_text()
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


def test_grille_versee_apres_controle(depot, tmp_path):
    run(depot)
    out = depot["out"]
    (out / "execution.json").write_text("{}")
    filled = tmp_path / "remplie.csv"
    rows = read(depot["ecoute"] / a0003.GRID)
    rows[0]["rires"], rows[0]["remarques"] = "x", "deux voix, « mm », rires"
    a0003.write_csv(filled, rows, a0003.GRID_FIELDS)
    target = a0003.import_grid(filled, out)
    assert target == out / a0003.GRID and read(target)[0]["rires"] == "x"
    with pytest.raises(SystemExit):                       # jamais remplacée
        a0003.import_grid(filled, out)


@pytest.mark.parametrize("defaut", ["extrait_manquant", "audio_different", "cause_mal_cochee", "colonnes", "non_executee"])
def test_grille_refusee(depot, tmp_path, defaut):
    run(depot)
    out = depot["out"]
    if defaut != "non_executee":
        (out / "execution.json").write_text("{}")
    rows = read(depot["ecoute"] / a0003.GRID)
    fields = list(a0003.GRID_FIELDS)
    if defaut == "extrait_manquant":
        rows = rows[1:]
    elif defaut == "audio_different":
        rows[0]["fichier_audio"] = "autre.wav"
    elif defaut == "cause_mal_cochee":
        rows[0]["bruit"] = "oui"
    elif defaut == "colonnes":
        fields = fields[:-1]
        rows = [{k: r[k] for k in fields} for r in rows]
    filled = tmp_path / "remplie.csv"
    a0003.write_csv(filled, rows, fields)
    with pytest.raises(SystemExit):
        a0003.import_grid(filled, out)
    assert not (out / a0003.GRID).exists()
