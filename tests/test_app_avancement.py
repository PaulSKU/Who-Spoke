"""Onglet « Avancement » (D26, chantier I2 ; app/avancement.py), sur un dépôt fabriqué
dans un dossier temporaire : en-têtes de notes.md, results, fiches et planning."""

import json

import pytest

from app import avancement as av

HEADER = """---
id: {id}
question: "{question}"
verdict: {verdict}
decisions: [{decisions}]
---
# {id}

Corps des notes.
"""


def results(directory, corpus, partition, der_c0, der_c025, reference=None, variable=None,
            date="2026-10-28T12:00:00+01:00", invalidated=None, components=(10.0, 5.0, 3.0)):
    manquee, fa, confusion = components
    (directory / f"results_{corpus}_{partition}.json").write_text(json.dumps({
        "exp_id": directory.name[:8], "date": date, "reference": reference, "variable_modifiee": variable,
        "donnees": {"corpus": corpus, "partition": partition},
        "systeme": {"pipeline": "baseline", "mode_n_locuteurs": "estime"},
        "metriques": {"collar_0": {"der": der_c0, "manquee": manquee, "fausse_alarme": fa, "confusion": confusion},
                      "collar_0_25": {"der": der_c025}},
        "invalidee": invalidated,
    }))


@pytest.fixture
def depot(tmp_path):
    root = tmp_path / "depot"
    exp = root / "experiments"
    # Référence, en-tête complet.
    d = exp / "EXP-0002_baseline-mfcc"
    d.mkdir(parents=True)
    (d / "notes.md").write_text(HEADER.format(id="EXP-0002", question="Que vaut une chaîne classique ?",
                                              verdict="reference", decisions="D7, D19"))
    results(d, "ami", "dev", 64.95, 61.5)
    results(d, "ami", "test", 64.38, 61.21)
    # Oracle, sans en-tête.
    d = exp / "EXP-0003_baseline-k-oracle"
    d.mkdir()
    (d / "notes.md").write_text("# EXP-0003\n\nNotes sans en-tête.\n")
    results(d, "ami", "test", 63.42, 60.41, reference="EXP-0002", variable="mode_n_locuteurs",
            date="2026-10-28T14:00:00+01:00", components=(32.28, 4.99, 26.15))
    # En-tête cassé, résultats invalidés.
    d = exp / "EXP-0004_essai"
    d.mkdir()
    (d / "notes.md").write_text("---\nid: EXP-0004\nquestion: [non fermé\n---\n# EXP-0004\n")
    results(d, "ami", "test", 49.09, 45.1, date="2026-10-29T10:00:00+01:00", invalidated={"motif": "x"})
    # En-tête dont l'id et le verdict sont faux.
    d = exp / "EXP-0005_mal-renseignee"
    d.mkdir()
    (d / "notes.md").write_text(HEADER.format(id="EXP-0099", question="<b>Q</b>", verdict="peut-etre",
                                              decisions="D9"))
    # Configurée, pas encore exécutée, sans notes.
    (exp / "EXP-0006_a-venir").mkdir()
    # Analyse avec en-tête, date dans execution.json.
    a = root / "analyses" / "A-0001_sensibilite"
    a.mkdir(parents=True)
    (a / "notes.md").write_text(HEADER.format(id="A-0001", question="Sensibilité de la référence ?",
                                              verdict="informatif", decisions="D21"))
    (a / "execution.json").write_text(json.dumps({"date": "2026-10-28T13:00:00+01:00"}))
    # Décisions.
    docs = root / "docs"
    (docs / "decisions").mkdir(parents=True)
    (docs / "cadrage.md").write_text(
        "# Cadrage\n\n**Statut.** Décisions D1 à D3 actées le 27/10/2026. Restent ouverts : le choix "
        "de la seconde amélioration de D2, et D3 (S3).\n\n## 0. Vue d'ensemble\n\n"
        "| ID | Décision | Recommandation |\n|---|---|---|\n| D1 | Protocole | x |\n"
        "| D2 | Ablation | x |\n| D3 | Licence **libre** | x |\n\n## 1. Décisions\n")
    (docs / "decisions" / "D16-entree.md").write_text("# D16 — Entrée audio\n\nStatut : actée\n")
    (docs / "decisions" / "D17-interface.md").write_text(
        "# D17 — Interface\n\nStatut : actée (périmètre, branche `interface`)\n\n## Amendement 1 — prototype\n\nStatut : proposée\n")
    (docs / "planning.md").write_text(
        "# Planning\n\n## File d'attente des expériences (D23)\n\nTexte.\n\n"
        "| Rang | Expérience ou chantier | Condition |\n|---|---|---|\n"
        "| 0 | EXP-0004 à EXP-0007, baseline | En cours |\n| 1 | Robustesse | Fiche D24 |\n"
        "| 2 | Interface | Fiche D17 |\n\n## Calendrier\n")
    return root


def test_en_tete_complet(depot):
    header = av.read_header(depot / "experiments" / "EXP-0002_baseline-mfcc" / "notes.md", "EXP-0002")
    assert header.status == "ok" and header.problems == []
    assert header.question == "Que vaut une chaîne classique ?"
    assert header.verdict == "reference" and header.decisions == ["D7", "D19"]


def test_en_tete_manquant_illisible_ou_incoherent_sans_planter(depot):
    exp = depot / "experiments"
    assert av.read_header(exp / "EXP-0003_baseline-k-oracle" / "notes.md", "EXP-0003").status == "manquant"
    assert av.read_header(exp / "EXP-0004_essai" / "notes.md", "EXP-0004").status == "illisible"
    assert av.read_header(exp / "EXP-0006_a-venir" / "notes.md", "EXP-0006").status == "manquant"
    wrong = av.read_header(exp / "EXP-0005_mal-renseignee" / "notes.md", "EXP-0005")
    assert wrong.status == "ok"
    assert any("EXP-0099" in p for p in wrong.problems) and any("verdict inconnu" in p for p in wrong.problems)


def test_frise_dans_l_ordre_avec_der_test_en_premier(depot):
    items = av.read_items(depot)
    # Ordre chronologique ; EXP-0006, sans date, en dernier.
    assert [i.id for i in items] == ["EXP-0002", "A-0001", "EXP-0003", "EXP-0004", "EXP-0005", "EXP-0006"]
    exp2 = items[0]
    assert [r.partition for r in exp2.results] == ["test", "dev"]
    assert exp2.result("test").der_c0 == 64.38 and exp2.result("test").der_c025 == 61.21
    html = av.render(depot)["frise"]
    assert html.index("64,38 %") < html.index("64,95 %")          # test avant dev
    assert "collar 0,25 s : 61,21 %" in html
    assert html.count(av.MISSING_HEADER) >= 2                       # EXP-0003 et EXP-0006
    assert "en-tête illisible" in html and "invalidée" in html
    assert "référence" in html and "informatif" in html and "analyse a posteriori" in html
    assert "&lt;b&gt;Q&lt;/b&gt;" in html and "<b>Q</b>" not in html
    assert 'data-id="EXP-0002"' in html and 'data-id="EXP-0006"' not in html   # pas de notes.md


def test_decomposition_par_les_oracles(depot):
    html = av.render(depot)["oracles"]
    assert "EXP-0003" in html and "mode_n_locuteurs" in html
    assert "-0,96 pt" in html                                       # 63,42 − 64,38
    assert "26,15 %" in html                                        # confusion
    assert "absente de ce dépôt" in html                            # EXP-0010, EXP-0011


def test_decisions_et_statuts(depot):
    decisions = {d.number: d for d in av.read_decisions(depot)}
    assert sorted(decisions) == [1, 2, 3, 16, 17]
    assert decisions[1].status == "actée le 27/10/2026"
    assert "ouvert : le choix de la seconde amélioration de D2" in decisions[2].status
    assert decisions[3].title == "Licence libre" and decisions[3].status.endswith("ouvert : D3 (S3)")
    assert decisions[17].status == "actée (périmètre, branche `interface`)"
    assert decisions[17].amendments == [("Amendement 1 — prototype", "proposée")]
    html = av.render(depot)["decisions"]
    assert "branche <code>interface</code>" in html and "proposée" in html


def test_file_d_attente_et_etat_constate(depot):
    queue = av.read_queue(depot, av.read_items(depot))
    assert [q.rank for q in queue] == ["0", "1", "2"]
    # EXP-0004 a des résultats ; EXP-0005 et EXP-0006 existent sans résultats ; EXP-0007 n'existe pas.
    assert queue[0].state == "1/4 avec résultats, 3/4 créées"
    assert queue[1].state == "fiche D24 absente" and queue[2].state == "fiche D17 présente"


def test_notes_affichees_sans_en_tete(depot):
    text = av.notes_markdown(depot, "EXP-0002")
    assert "Corps des notes." in text and "verdict:" not in text
    assert "Pas de notes.md" in av.notes_markdown(depot, "EXP-0006")
    assert "invalide" in av.notes_markdown(depot, "../etc")


def test_depot_vide_ou_incomplet(tmp_path):
    sections = av.render(tmp_path)
    assert set(sections) == {"resume", "frise", "oracles", "decisions", "file"}
    assert "introuvable" in sections["file"]


def test_lecture_seule(depot):
    before = sorted((str(p), p.stat().st_mtime_ns) for p in depot.rglob("*"))
    av.render(depot)
    av.notes_markdown(depot, "EXP-0002")
    assert sorted((str(p), p.stat().st_mtime_ns) for p in depot.rglob("*")) == before


def test_resume_accorde(depot):
    resume = av.render(depot)["resume"]
    assert "5 expériences, 1 analyse, 5 décisions" in resume


def test_depot_principal_complet_si_present():
    """Avec les en-têtes et les statuts ajoutés au dépôt principal (D26, amendement du
    01/11), plus aucun « en-tête manquant » ni « statut non indiqué »."""
    from whospoke.experiment import REPO_ROOT

    main = REPO_ROOT.parent / "Who-Spoke"
    if not (main / "experiments").is_dir():
        pytest.skip("dépôt principal absent")
    items = av.read_items(main)
    if not any(i.header.status == "ok" for i in items):
        pytest.skip("en-têtes pas encore ajoutés dans ce dépôt")
    assert [i.id for i in items if i.header.status != "ok" or i.header.problems] == []
    assert [(d.number, t) for d in av.read_decisions(main) for t, s in d.amendments if s == "statut non indiqué"] == []
