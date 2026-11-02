"""Tableaux et figures du rendu (chantier E7 ; scripts/rendu.py), sur un dépôt fabriqué
dans un dossier temporaire : results_*.json, per_file, leaderboard, constats, campagne."""

import csv
import importlib.util
import json
import sys
import xml.etree.ElementTree as ET

import pytest
import yaml

from app import avancement as av
from whospoke.evaluation.metrics import bootstrap_der_ci
from whospoke.experiment import REPO_ROOT

spec_ = importlib.util.spec_from_file_location("rendu", REPO_ROOT / "scripts" / "rendu.py")
rendu = importlib.util.module_from_spec(spec_)
sys.modules["rendu"] = rendu          # dataclasses du script
spec_.loader.exec_module(rendu)

KINDS = ("manquee", "fausse_alarme", "confusion")


def files(n, base=(10.0, 5.0, 3.0), step=1.0, reference=100.0, wrong_count=()):
    """n fichiers : durées d'erreur (s) qui croissent de `step` par fichier, 100 s de parole."""
    return {f"f{i:02d}": ([b + step * i for b in base], reference, 1 if i in wrong_count else 0) for i in range(n)}


def pooled(rows, scale=1.0):
    errors = sum(sum(e) * scale for e, _, _ in rows.values())
    total = sum(t for _, t, _ in rows.values())
    return 100.0 * errors / total


def experiment(root, exp_id, slug, corpus, rows, partition="test", reference=None, variable=None,
               pipeline="baseline", mode="estime", vad="energie", verdict="reference", commit="abc1234",
               representation=None, leaderboard=True):
    """Expérience fabriquée : per_file et results cohérents (collar 0,25 s = moitié des erreurs)."""
    directory = root / "experiments" / f"{exp_id}_{slug}"
    directory.mkdir(parents=True, exist_ok=True)
    if not (directory / "notes.md").exists():
        (directory / "notes.md").write_text(f'---\nid: {exp_id}\nquestion: "Q ?"\nverdict: {verdict}\n'
                                            f"decisions: []\n---\n# {exp_id}\n")
    if representation:
        (directory / "config.yaml").write_text(yaml.safe_dump({"pipeline": {"parametres": {
            "representation": representation}}}))
    fields = ["uri", "der_c0", "der_c025", "erreur_n_locuteurs"] + [
        f"{k}_{c}_s" for c in ("c0", "c025") for k in (*KINDS, "duree_reference")]
    with (directory / f"per_file_{corpus}_{partition}.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for uri, (errors, total, wrong) in rows.items():
            row = {"uri": uri, "erreur_n_locuteurs": wrong,
                   "der_c0": 100.0 * sum(errors) / total, "der_c025": 50.0 * sum(errors) / total}
            for collar, scale in (("c0", 1.0), ("c025", 0.5)):
                row |= {f"{k}_{collar}_s": e * scale for k, e in zip(KINDS, errors)}
                row[f"duree_reference_{collar}_s"] = total
            writer.writerow(row)
    total = sum(t for _, t, _ in rows.values())
    components = {k: round(100.0 * sum(e[i] for e, _, _ in rows.values()) / total, 2) for i, k in enumerate(KINDS)}
    der_c0, der_c025 = round(pooled(rows), 2), round(pooled(rows, 0.5), 2)
    (directory / f"results_{corpus}_{partition}.json").write_text(json.dumps({
        "exp_id": exp_id, "slug": slug, "date": f"2026-10-{20 + int(exp_id[-2:]) % 10}T12:00:00+01:00",
        "git_commit": commit, "reference": reference, "variable_modifiee": variable,
        "donnees": {"corpus": corpus, "partition": partition, "n_fichiers": len(rows)},
        "systeme": {"pipeline": pipeline, "mode_n_locuteurs": mode, "vad": vad},
        "metriques": {"collar_0": {"der": der_c0, **components}, "collar_0_25": {"der": der_c025},
                      "n_locuteurs": {"taux_exact": 100.0 * sum(1 for _, _, w in rows.values() if not w) / len(rows)}},
        "evaluation": {"git_commit": commit + "0" * 33}, "invalidee": None,
    }))
    if leaderboard:
        path = root / "results" / "leaderboard.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        new = not path.exists()
        with path.open("a", newline="") as handle:
            writer = csv.writer(handle)
            if new:
                writer.writerow(["exp_id", "corpus", "partition", "der_c0", "der_c025", "git_commit"])
            writer.writerow([exp_id, corpus, partition, der_c0, der_c025, commit])
    return directory


CONSTATS = {"version": 1, "date": "2026-11-02", "constats": [
    {"id": "C01", "etape": "detection", "moteurs": [], "texte": "Constat sur la baseline.",
     "sources": ["EXP-0009", "EXP-0012"], "confiance": "certain", "cle": True},
    {"id": "C02", "etape": "detection", "moteurs": [], "texte": "Constat sur un oracle.",
     "sources": ["EXP-0004"], "confiance": "probable", "cle": False},
    {"id": "C03", "etape": "evaluation", "moteurs": [], "texte": "Constat sans expérience du rendu.",
     "sources": ["A-0001"], "confiance": "certain", "cle": True},
]}


@pytest.fixture
def depot(tmp_path):
    root = tmp_path / "depot"
    summre = files(8, wrong_count={0, 1})
    experiment(root, "EXP-0007", "pyannote-c1-summre", "summre", summre, pipeline="pyannote-community-1",
               vad="integree", commit="568efbb")
    experiment(root, "EXP-0009", "baseline-mfcc-summre", "summre", files(8, base=(20.0, 3.0, 25.0)),
               commit="568efbb")
    experiment(root, "EXP-0012", "baseline-ecapa-summre", "summre", files(8, base=(20.0, 3.0, 8.0)),
               reference="EXP-0009", variable="representation", verdict="retenu", commit="3856355",
               representation="ecapa")
    experiment(root, "EXP-0016", "pyannote-c1-summre-exclusive", "summre", files(8, base=(15.0, 3.0, 3.0)),
               reference="EXP-0007", variable="sortie", pipeline="pyannote-community-1", vad="integree",
               verdict="en_cours", commit="12a67a6")
    experiment(root, "EXP-0002", "baseline-mfcc-ami-sdm", "ami", files(4, base=(30.0, 5.0, 27.0)), commit="540bb5e")
    experiment(root, "EXP-0004", "baseline-vad-oracle", "ami", files(4, base=(15.0, 0.0, 34.0)),
               reference="EXP-0002", variable="detection_oracle", vad="oracle", verdict="informatif",
               commit="3abe688")
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "constats.yaml").write_text(yaml.safe_dump(CONSTATS, allow_unicode=True))
    (root / "configs").mkdir()
    (root / "configs" / "summre_degrade.yaml").write_text(yaml.safe_dump({
        "conditions": {"rev04": {"reverberation": {"rt60_s": 0.4}}, "bru05": {"bruit": {"rsb_db": 5}},
                       "cod08": {"codec": {"debit_kbps": 8}},
                       "salle": {"reverberation": {"rt60_s": 0.6}, "bruit": {"rsb_db": 10}}},
        "ecoute": {"liste_zoom": "data/splits/summre/zoom_test.txt"}}, sort_keys=False))
    (root / "data" / "splits" / "summre").mkdir(parents=True)
    (root / "data" / "splits" / "summre" / "zoom_test.txt").write_text("f00\nf01\nf02\n")
    return root


def page(root, name):
    return rendu.build(root)[name]


# --- Tableau des systèmes -------------------------------------------------------------


def test_systemes_par_corpus_en_condition_reelle(depot):
    text = page(depot, "systemes.md")
    summre, ami = text.split("## AMI (SDM)")
    assert text.index("## SUMM-RE") < text.index("## AMI (SDM)")      # SUMM-RE d'abord (D3)
    assert "EXP-0004" not in ami.split("**Sources.**")[0]               # détection oracle : pas un système
    assert "EXP-0002 (baseline-mfcc-ami-sdm)" in ami
    line = next(li for li in summre.splitlines() if li.startswith("| pyannote community-1 | EXP-0007"))
    rows = files(8, wrong_count={0, 1})
    assert f"| {rendu.pct(round(pooled(rows), 2))} | {rendu.pct(round(pooled(rows, 0.5), 2))} |" in line
    assert "6/8 (75,0 %)" in line                                       # nombre de locuteurs exact
    assert "| Baseline ECAPA | EXP-0012" in summre and "| retenu |" in summre
    # Système décliné : la variable modifiée distingue la ligne.
    assert "| pyannote community-1 (sortie) | EXP-0016" in summre


def test_ecart_a_la_reference_par_bootstrap_apparie(depot):
    text = page(depot, "systemes.md")
    a, b = files(8, base=(15.0, 3.0, 3.0)), files(8, wrong_count={0, 1})
    ci = bootstrap_der_ci([sum(e) for e, _, _ in a.values()], [t for _, t, _ in a.values()],
                          [sum(e) for e, _, _ in b.values()], [t for _, t, _ in b.values()])
    expected = (f"{rendu.num(ci['estimation'], sign=True)} [{rendu.num(ci['borne_inf'], sign=True)} ; "
                f"{rendu.num(ci['borne_sup'], sign=True)}]")
    line = next(li for li in text.splitlines() if li.startswith("| EXP-0016 | EXP-0007 (sortie)"))
    assert expected in line
    assert "0 / 8 sur 8" in line                                        # moins bon sur chaque fichier
    # Amélioration : signe moins typographique.
    assert "| EXP-0012 | EXP-0009 (representation) | −" in text


def test_ecart_sans_intervalle_sous_cinq_fichiers():
    a, b = files(3, base=(5.0, 1.0, 1.0)), files(3)

    def per_file(rows):
        return {u: {f"{k}_{c}_s": e[i] for c in ("c0", "c025") for i, k in enumerate(KINDS)}
                | {"duree_reference_c0_s": t, "duree_reference_c025_s": t,
                   "der_c0": 100 * sum(e) / t, "der_c025": 100 * sum(e) / t} for u, (e, t, _) in rows.items()}

    gaps, _ = rendu.compare(per_file(a), per_file(b))
    assert gaps["c0"].low is None and gaps["c0"].n == 3
    assert gaps["c0"].estimate == pytest.approx(pooled(a) - pooled(b))
    assert "[" not in gaps["c0"].text()
    assert rendu.compare(per_file(a), per_file(files(4)))[1].startswith("fichiers différents")
    assert rendu.compare(None, per_file(b)) == (None, "per_file absent")


def test_reference_absente_signalee(depot):
    experiment(depot, "EXP-0020", "baseline-x-summre", "summre", files(8), reference="EXP-0099",
               variable="seuil", verdict="en_cours")
    line = next(li for li in page(depot, "systemes.md").splitlines() if li.startswith("| EXP-0020 |"))
    assert "référence absente" in line


# --- Oracles ------------------------------------------------------------------------


def test_oracles_serie_de_l_avancement(depot):
    text = page(depot, "oracles.md")
    rows = [li for li in text.splitlines() if li.startswith("| EXP-")]
    assert [r.split(" ")[1] for r in rows] == list(av.ORACLE_SERIES)
    oracle = next(r for r in rows if r.startswith("| EXP-0004"))
    assert "détection : oracle" in oracle and "detection_oracle" in oracle and "| EXP-0002 |" in oracle
    assert "[" not in oracle                                            # 4 fichiers : pas d'intervalle
    assert next(r for r in rows if r.startswith("| EXP-0003")).count("absente de ce dépôt") == 1


# --- Robustesse ---------------------------------------------------------------------


def test_robustesse_vide_avant_a3(depot):
    text = page(depot, "robustesse.md")
    assert "Aucun résultat d'A3 pour l'instant" in text
    assert "`rev04` (réverbération, RT60 visé 0,4 s)" in text
    assert "`salle` (réverbération, RT60 visé 0,6 s et bruit, RSB 10 dB)" in text


def test_robustesse_moteur_par_condition(depot):
    clean = files(8, wrong_count={0, 1})
    # A3 : une expérience par moteur, un jeu par condition, propre = test de la référence.
    for corpus, base in (("summre-cod08", (14.0, 5.0, 3.0)), ("summre-rev04", (20.0, 5.0, 6.0))):
        experiment(depot, "EXP-0030", "pyannote-c1-summre-degrade", corpus, files(8, base=base),
                   reference="EXP-0007", variable="condition", pipeline="pyannote-community-1", vad="integree",
                   verdict="en_cours", commit="ffff000")
    text = page(depot, "robustesse.md")
    main = text.split("## Sous-groupes")[0]
    rows = [li for li in main.splitlines() if li.startswith("| pyannote community-1 — EXP-0030")]
    assert [r.split(" | ")[1].split(" ")[0] for r in rows] == ["propre", "`rev04`", "`cod08`"]   # ordre de la config
    assert "propre (EXP-0007)" in rows[0]
    rev04 = files(8, base=(20.0, 5.0, 6.0))
    ci = bootstrap_der_ci([sum(e) for e, _, _ in rev04.values()], [t for _, t, _ in rev04.values()],
                          [sum(e) for e, _, _ in clean.values()], [t for _, t, _ in clean.values()])
    assert rendu.num(ci["estimation"], sign=True) + " [" in rows[1]
    assert "0 / 8 sur 8" in rows[1]
    # Sous-groupes : Zoom (3 réunions, pas d'intervalle) et autres (5, avec intervalle).
    groups = [li for li in text.split("## Sous-groupes")[1].splitlines() if li.startswith("| pyannote")]
    cells = groups[0].split(" | ")
    assert "[" not in cells[2] and cells[4] == "3"
    assert "[" in cells[5] and cells[7].rstrip(" |") == "5"
    assert "EXP-0030 (`ffff000`)" in text and "EXP-0007 (`568efbb`)" in text
    # Pas dans le tableau des systèmes : corpus dégradés exclus.
    assert "EXP-0030" not in page(depot, "systemes.md")


def test_robustesse_propre_de_l_experience_prioritaire(depot):
    experiment(depot, "EXP-0031", "baseline-ecapa-degrade", "summre-propre", files(8), reference="EXP-0012",
               variable="condition", representation="ecapa", verdict="en_cours")
    experiment(depot, "EXP-0031", "baseline-ecapa-degrade", "summre-bru05", files(8, base=(12.0, 6.0, 4.0)),
               reference="EXP-0012", variable="condition", representation="ecapa", verdict="en_cours")
    text = page(depot, "robustesse.md")
    assert "| Baseline ECAPA — EXP-0031 | propre (EXP-0031) |" in text
    assert "`bru05` (bruit, RSB 5 dB)" in text


# --- Temps ----------------------------------------------------------------------------


def campaign(root, name, date, factice=False, reached=True, conforme=True):
    directory = root / "results" / "campagne_temps" / name
    directory.mkdir(parents=True)
    summary = {"rtf": 0.0512, "rtf_min": 0.049, "rtf_max": 0.0533, "temps_30min_s": 92.2,
               "surcout_fixe_s": 1.84, "n_reunions": 3, "n_erreurs": 0, "conforme": conforme}
    (directory / "campagne.json").write_text(json.dumps({
        "date": date, "factice": factice, "git": {"commit": "0123456789ab", "clean": True},
        "conditions_depart": {"reunies": reached},
        "sous_ensemble": {"source": "data/splits/<corpus>/temps.txt",
                          "fichiers": [{"uri": "summre__a"}, {"uri": "ami__b"}]},
        "mesures": [{"moteur": "pyannote", "libelle": "pyannote community-1", "peripherique": "mps",
                     "chargement_s": 4.53, "synthese": summary},
                    {"moteur": "baseline", "libelle": "Baseline ECAPA", "peripherique": "cpu",
                     "chargement_s": 1.2, "synthese": summary | {"conforme": False}}]}))
    return directory


def test_temps_vide_avant_la_campagne(depot):
    campaign(depot, "2026-11-05_10h00", "2026-11-05T10:00:00+01:00", factice=True)
    text = page(depot, "temps.md")
    assert "Campagne du 12/11 pas encore faite" in text
    assert "1 campagne(s) ignorée(s)" in text


def test_temps_de_la_campagne_la_plus_recente(depot):
    campaign(depot, "2026-11-12_09h00", "2026-11-12T09:00:00+01:00", reached=False)
    campaign(depot, "2026-11-12_10h00", "2026-11-12T10:00:00+01:00")
    campaign(depot, "2026-11-12_14h00", "2026-11-12T14:00:00+01:00", factice=True)
    text = page(depot, "temps.md")
    assert "| pyannote community-1 | mps | 0,0512 | 0,0490 – 0,0533 | 1 min 32 s | 1,8 s | 4,5 s | 3 |" in text
    assert "| Baseline ECAPA | cpu | non conforme, non reporté (D21) |" in text
    assert "`results/campagne_temps/2026-11-12_10h00/campagne.json` du 2026-11-12T10:00" in text
    assert "commit `0123456`" in text and "summre__a, ami__b" in text
    assert "2 autre(s) campagne(s) ignorée(s)" in text


# --- Sources, constats, contrôles -------------------------------------------------------


def test_sources_et_constats_lies(depot):
    text = page(depot, "systemes.md")
    assert "EXP-0012 (`3856355`)" in text and "EXP-0009 (`568efbb`)" in text
    assert "- C01 (certain) : Constat sur la baseline. Sources : EXP-0009, EXP-0012." in text
    assert "C02" not in text and "C03" not in text
    assert "- C02 (probable)" in page(depot, "oracles.md")
    assert "version 1 du 2026-11-02" in text


def test_controle_du_leaderboard(depot):
    assert "concordent (6 lignes" in page(depot, "README.md")
    path = depot / "results" / "leaderboard.csv"
    lines = path.read_text().splitlines()
    lines[1] = lines[1].replace(lines[1].split(",")[3], "99.0", 1)
    path.write_text("\n".join(lines) + "\n")
    experiment(depot, "EXP-0021", "hors-leaderboard", "ami", files(4), leaderboard=False)
    readme = page(depot, "README.md")
    assert "der_c0 99.0 au leaderboard" in readme
    assert "EXP-0021 ami test : results_*.json absent du leaderboard" in readme


# --- Figures ----------------------------------------------------------------------------


def test_figures_autonomes_comme_l_onglet_avancement(depot):
    pages = rendu.build(depot)
    groups = av.reference_systems(av.read_items(depot))
    for name, narrow in (("figures/systemes_reference.svg", False), ("figures/systemes_reference_etroit.svg", True)):
        svg = pages[name]
        root = ET.fromstring(svg)                                       # XML bien formé
        assert root.get("width") == root.get("viewBox").split()[2] and root.get("width") != "100%"
        style = root.find("{http://www.w3.org/2000/svg}style").text
        assert "--av-err-manquee:#2a78d6" in style and "prefers-color-scheme: dark" in style
        assert ".av-chart .av-txt" in style and "--font:" in style
        # Mêmes barres que l'onglet : le corps du SVG est celui de app.graphique.
        body = rendu.graphique.svg(groups, narrow, "avn" if narrow else "avw")
        assert body.split("</desc>")[1] in svg
    assert "![DER test sans collar" in pages["README.md"]


def test_sans_resultat_ni_figure(tmp_path):
    pages = rendu.build(tmp_path)
    assert not any(name.startswith("figures/") for name in pages)
    assert "Aucun résultat de test." in pages["systemes.md"]
    assert "absent ou vide" in pages["README.md"]


# --- Écriture et vérification -------------------------------------------------------


def test_ecrit_puis_verifie(depot, capsys):
    output = depot / "docs" / "rendu"
    assert rendu.main(["--racine", str(depot)]) == 0
    assert sorted(p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()) == [
        "README.md", "figures/systemes_reference.svg", "figures/systemes_reference_etroit.svg",
        "oracles.md", "robustesse.md", "systemes.md", "temps.md"]
    assert rendu.build(depot) == rendu.build(depot)                      # déterministe
    assert rendu.main(["--racine", str(depot), "--verifier"]) == 0
    (output / "systemes.md").write_text("modifié à la main\n")
    (output / "ancien.md").write_text("plus produit\n")
    capsys.readouterr()
    assert rendu.main(["--racine", str(depot), "--verifier"]) == 1
    assert "pas à jour : ancien.md" in capsys.readouterr().out
    assert rendu.main(["--racine", str(depot)]) == 0
    assert not (output / "ancien.md").exists()
    assert rendu.main(["--racine", str(depot), "--verifier"]) == 0
    assert str(depot) not in "".join((output / n).read_text() for n in ("README.md", "temps.md", "systemes.md"))


def test_depot_reel_sans_erreur():
    pages = rendu.build(REPO_ROOT)
    assert {"README.md", "systemes.md", "oracles.md", "robustesse.md", "temps.md"} <= set(pages)
