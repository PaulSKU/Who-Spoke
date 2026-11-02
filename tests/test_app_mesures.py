"""Chantier B5 (audit R-U7, R-U8) : constats, encadré « Ce que nous avons appris »,
graphique des systèmes de référence, décisions repliées, synthèse, Pipeline relié aux
mesures. Dépôts fabriqués dans un dossier temporaire ; aucun modèle."""

import json
import re

import pytest

from app import avancement as av
from app import constats, graphique, moteurs, pipeline
from whospoke.experiment import REPO_ROOT

CONSTATS = """
version: 1
date: 2026-11-01
constats:
  - {id: C01, etape: detection, moteurs: [baseline-ecapa], texte: "La détection <b>par énergie</b> manque 21,9 points.",
     sources: [EXP-0012, EXP-0099], confiance: certain, cle: true}
  - {id: C02, etape: segmentation, moteurs: [pyannote-community-1], texte: "Segmentation neuronale décisive.",
     sources: [EXP-0001], confiance: probable, cle: true}
  - {id: C03, etape: detection, moteurs: [pyannote-community-1], texte: "Fausse alarme dans les pauses.",
     sources: [A-0001], confiance: certain, cle: false}
  - {id: C04, etape: evaluation, moteurs: [], texte: "Le collar stabilise le DER.", sources: [], confiance: incertain, cle: true}
  - {id: C05, etape: inexistante, moteurs: [], texte: "Étape mal nommée.", sources: [], confiance: certain, cle: false}
  - {id: C06, etape: regroupement, texte: "Sans confiance.", cle: true}
  - {id: C07, etape: regroupement, moteurs: [], texte: "Confiance inventée.", confiance: sure, cle: false}
"""


# --- Lecture de docs/constats.yaml ------------------------------------------------------


def test_lecture_des_constats(tmp_path):
    assert constats.read(tmp_path).present is False
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "constats.yaml").write_text(CONSTATS)
    data = constats.read(tmp_path)
    assert data.present and data.version == "1" and data.date == "2026-11-01"
    assert [c.id for c in data.items] == ["C01", "C02", "C03", "C04", "C05", "C07"]   # C06 incomplet
    assert any("C06" in p and "confiance" in p for p in data.problems)
    assert any("C07" in p and "sure" in p for p in data.problems)
    assert data.items[3].concerns("baseline-mfcc") and not data.items[0].concerns("baseline-mfcc")
    (tmp_path / "docs" / "constats.yaml").write_text("constats: [non fermé")
    assert constats.read(tmp_path).problems and constats.read(tmp_path).items == []


def test_constats_du_depot_principal_bien_formes():
    main = REPO_ROOT.parent / "Who-Spoke"
    if not (main / constats.RELATIVE).is_file():
        pytest.skip("docs/constats.yaml absent du dépôt principal")
    data = constats.read(main)
    assert data.problems == [] and data.items
    catalogue = pipeline.load_catalogue(main)
    assert {c.etape for c in data.items} <= set(catalogue["etapes"]) | {constats.EVALUATION}
    assert {m for c in data.items for m in c.moteurs} <= set(moteurs.SPECS)


# --- Onglet Avancement ------------------------------------------------------------------


HEADER = "---\nid: {id}\nquestion: \"{question}\"\nverdict: {verdict}\ndecisions: []\n---\n# {id}\n"


def experiment(root, exp_id, slug, corpus, der, components, verdict="informatif", representation=None,
               mode="estime", vad="energie", pipeline_name="baseline", invalidated=False, notes=True):
    directory = root / "experiments" / f"{exp_id}_{slug}"
    directory.mkdir(parents=True, exist_ok=True)
    params = f"\n    representation: {representation}" if representation else " {}"
    (directory / "config.yaml").write_text(f"pipeline:\n  nom: {pipeline_name}\n  parametres:{params}\ndevice: cpu\n")
    manquee, fausse_alarme, confusion = components
    (directory / f"results_{corpus}_test.json").write_text(json.dumps({
        "exp_id": exp_id, "date": f"2026-10-{20 + int(exp_id[-2:]):02d}", "reference": None,
        "variable_modifiee": None, "invalidee": invalidated or None,
        "donnees": {"corpus": corpus, "partition": "test"},
        "systeme": {"pipeline": pipeline_name, "mode_n_locuteurs": mode, "vad": vad},
        "metriques": {"collar_0": {"der": der, "manquee": manquee, "fausse_alarme": fausse_alarme,
                                   "confusion": confusion},
                      "collar_0_25": {"der": der - 3}},
    }))
    if notes:
        (directory / "notes.md").write_text(HEADER.format(id=exp_id, question="Q", verdict=verdict))


@pytest.fixture
def depot(tmp_path):
    root = tmp_path
    experiment(root, "EXP-0001", "pyannote-ami", "ami", 19.92, (8.0, 4.0, 7.92), "reference",
               pipeline_name="pyannote-community-1", vad="integree")
    experiment(root, "EXP-0002", "mfcc-ami", "ami", 64.38, (32.28, 4.99, 27.11), "reference")
    experiment(root, "EXP-0003", "mfcc-k-oracle", "ami", 63.42, (32.28, 4.99, 26.15), "informatif", mode="oracle")
    experiment(root, "EXP-0004", "mfcc-vad-oracle", "ami", 49.1, (10.0, 9.0, 30.1), "informatif", vad="oracle")
    experiment(root, "EXP-0009", "mfcc-summre", "summre", 49.36, (21.9, 3.0, 24.46), "reference")
    experiment(root, "EXP-0012", "ecapa-summre", "summre", 33.42, (21.9, 3.0, 8.52), "retenu", "ecapa")
    experiment(root, "EXP-0015", "wespeaker-summre", "summre", 35.86, (21.9, 3.0, 10.96), "ecarte", "wespeaker")
    experiment(root, "EXP-0016", "mfcc-summre-bis", "summre", 48.0, (20.0, 3.0, 25.0), "retenu")
    experiment(root, "EXP-0017", "ecapa-summre-invalide", "summre", 30.0, (10.0, 10.0, 10.0), "retenu", "ecapa",
               invalidated=True)
    docs = root / "docs"
    (docs / "decisions").mkdir(parents=True)
    (docs / "constats.yaml").write_text(CONSTATS)
    (docs / "synthese.md").write_text("# Synthèse vivante\n\nCe que nous savons.\n")
    (docs / "cadrage.md").write_text(
        "# Cadrage\n\n**Statut.** D1 à D2 actées le 27/10/2026. Restent ouverts : la seconde amélioration de D2.\n\n"
        "## 0. Décisions\n\n| ID | Décision |\n|---|---|\n| D1 | Métrique |\n| D2 | Améliorations |\n")
    (docs / "decisions" / "D16-entree.md").write_text("# D16 — Entrée audio\n\nStatut : actée\n")
    return root


def test_systemes_de_reference_du_graphique(depot):
    groups = dict(av.reference_systems(av.read_items(depot)))
    assert list(groups) == ["SUMM-RE", "AMI (SDM)"]                 # SUMM-RE (D3) en premier
    summre = [(b.label, b.exp_id) for b in groups["SUMM-RE"]]
    # Ordre fixe des systèmes, puis toute expérience retenue ou de référence ; jamais une
    # expérience invalidée ; WeSpeaker écarté mais système de référence : présent.
    assert summre == [("Baseline MFCC", "EXP-0009"), ("Baseline ECAPA", "EXP-0012"),
                      ("Baseline WeSpeaker", "EXP-0015"), ("Baseline MFCC", "EXP-0016")]
    assert groups["SUMM-RE"][-1].sub == "EXP-0016, retenu"
    # AMI : première expérience réaliste de chaque système ; les oracles n'y sont pas.
    assert [(b.label, b.exp_id) for b in groups["AMI (SDM)"]] == [("Baseline MFCC", "EXP-0002"),
                                                                  ("pyannote community-1", "EXP-0001")]
    mfcc = groups["AMI (SDM)"][0]
    assert mfcc.der == 64.38 and mfcc.values == {"manquee": 32.28, "fausse_alarme": 4.99, "confusion": 27.11}


def test_graphique_accessible_et_proportionnel(depot):
    groups = av.reference_systems(av.read_items(depot))
    svg = graphique.svg(groups, narrow=False, uid="t")
    assert 'role="img"' in svg and 'aria-labelledby="t-t t-d"' in svg
    assert "<title id=\"t-t\">DER test sans collar des systèmes de référence, par corpus</title>" in svg
    assert "Baseline MFCC 64,38\u202f% (parole manquée 32,28\u202f%, fausse alarme 4,99\u202f%, confusion 27,11\u202f%)" in svg
    # Motifs de la carte des erreurs en plus des couleurs : parole manquée pleine, fausse
    # alarme hachurée, confusion en contour (fond de surface, trait de la couleur).
    assert 'style="fill:var(--av-err-manquee)"' in svg
    assert 'id="t-fausse_alarme"' in svg and "rotate(45)" in svg
    assert "fill:url(#t-fausse_alarme);stroke:var(--av-err-fausse_alarme)" in svg
    assert "fill:var(--ws-surface);stroke:var(--av-err-confusion);stroke-width:1.5" in svg
    assert "t-confusion" not in svg and "t-manquee" not in svg
    assert "var(--av-err-manquee)" in svg and "#" not in re.sub(r'(id|href)="[^"]*"|url\(#[^)]*\)', "", svg)
    # Valeur du DER écrite au bout de chaque barre ; une info-bulle par segment.
    for _, bars in groups:
        for bar in bars:
            assert f">{graphique._pct(bar.der)}</text>" in svg
    assert svg.count('class="av-seg"') == sum(len(bars) * 3 for _, bars in groups)
    # Longueur totale d'une barre proportionnelle au DER : la barre la plus longue finit à
    # x0 + portée × DER / maximum (au demi-trait près pour un contour).
    paths = re.findall(r'class="av-seg" d="([^"]+)"', svg)
    xs = [float(x) for d in paths for x in re.findall(r"[MHQ ]([\d.]+),", d)]
    longest = max(bar.der for _, bars in groups for bar in bars)
    maximum = graphique._scale_max(groups)
    assert max(xs) == pytest.approx(214 + (760 - 214 - 66) * longest / maximum, abs=0.8)
    narrow = graphique.svg(groups, narrow=True, uid="n")
    assert 'viewBox="0 0 340 ' in narrow and 'viewBox="0 0 760 ' in svg
    figure = graphique.figure(groups)
    assert "av-chart-wide" in figure and "av-chart-narrow" in figure and "Valeurs du graphique" in figure
    assert "<td class=\"num strong\">64,38\u202f%</td>" in figure
    assert "Aucun résultat" in graphique.figure([])


def test_encadre_ce_que_nous_avons_appris(depot):
    html = av.render(depot)["appris"]
    assert "Ce que nous avons appris" in html
    # Constats clés seulement, texte échappé, confiance écrite.
    assert "par énergie" in html and "&lt;b&gt;" in html and "<b>par" not in html
    assert "Fausse alarme dans les pauses" not in html                  # cle: false
    assert "ws-conf-certain" in html and "ws-conf-probable" in html and "ws-conf-incertain" in html
    # Source présente : bouton qui affiche ses notes ; absente : signalée, sans bouton.
    assert 'class="ws-btn ws-btn-sm av-notes av-source" data-id="EXP-0012"' in html
    assert 'data-id="EXP-0099"' not in html and "Absente de ce dépôt" in html
    assert "docs/constats.yaml : à corriger" in html and "C06" in html
    assert 'data-id="synthese"' in html


def test_synthese_rendue_dans_la_page(depot):
    text = av.notes_markdown(depot, av.SYNTHESIS_ID)
    assert text.startswith("`docs/synthese.md`") and "Ce que nous savons." in text
    (depot / "docs" / "synthese.md").unlink()
    assert "absent" in av.notes_markdown(depot, av.SYNTHESIS_ID)
    assert 'data-id="synthese"' not in av.render(depot)["appris"]


def test_decisions_de_cadrage_repliees_et_chemin_masque(depot):
    sections = av.render(depot)
    decisions = sections["decisions"]
    before, _, folded = decisions.partition('<details class="av-framing ws-fold">')
    assert "D16" in before and "D1<" not in before                      # D16 et suivantes visibles
    assert "D1<" in folded and "D2<" in folded and "dont 1 avec un point ouvert" in folded
    assert str(depot) not in "".join(sections.values())


def test_sections_avec_constats_absents(tmp_path):
    sections = av.render(tmp_path)
    assert "docs/constats.yaml absent" in sections["appris"]
    assert "Aucun résultat" in sections["graphique"]


# --- Onglet Pipeline -----------------------------------------------------------------------


@pytest.fixture
def pipeline_depot(tmp_path):
    """Expériences et catalogue de ce dépôt, constats fabriqués."""
    (tmp_path / "experiments").symlink_to(REPO_ROOT / "experiments")
    (tmp_path / "src").symlink_to(REPO_ROOT / "src")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "constats.yaml").write_text(CONSTATS)
    return tmp_path


def test_constats_sous_les_etapes_du_moteur(pipeline_depot):
    page = pipeline.load_page(moteurs.SPECS["baseline-ecapa"], pipeline_depot)
    by_id = {stage.id: stage for stage in page.stages}
    assert [c.id for c in by_id["detection"].constats] == ["C01"]
    # C07 (confiance inconnue, signalée) reste affiché : tous les moteurs, étape Regroupement.
    assert [c.id for c in by_id["regroupement"].constats] == ["C07"]
    assert all(not stage.constats for stage in page.stages if stage.id not in ("detection", "regroupement"))
    assert [c.id for c in page.evaluation.constats] == ["C04"]            # tous les moteurs
    # Étape inconnue du catalogue et constats mal formés : signalés en tête, pour tout moteur.
    assert any("C05" in issue and "inexistante" in issue for issue in page.constat_issues)
    html = pipeline.render(page)
    assert "docs/constats.yaml : " in html and "étape « inexistante » absente du catalogue" in html
    assert "Constats mesurés" in html and "La détection &lt;b&gt;par énergie&lt;/b&gt;" in html
    assert "EXP-0012, EXP-0099" in html and '>1 constat</text>' in html     # nombre sur l'étape du schéma


def test_pyannote_segmentation_neuronale_en_un_bloc(pipeline_depot):
    page = pipeline.load_page(moteurs.SPECS["pyannote-community-1"], pipeline_depot)
    ids = [stage.id for stage in page.stages]
    assert "segmentation_neuronale" in ids and "detection" not in ids and "segmentation" not in ids
    block = page.stages[ids.index("segmentation_neuronale")]
    assert block.label == "Segmentation neuronale (détection et segmentation)"
    assert [part.id for part in block.parts] == ["detection", "segmentation"]
    # Réglages distincts par étape, constats rattachés à leur étape.
    assert all(part.rows for part in block.parts)
    assert [c.id for c in block.parts[0].constats] == ["C03"] and [c.id for c in block.parts[1].constats] == ["C02"]
    html = pipeline.render(page)
    assert html.count('class="pl-part"') == 2 and "2 constats" in html
    assert html.count('id="pl-tab-segmentation_neuronale"') == 1          # un onglet
    assert html.count('id="pl-sheet-segmentation_neuronale"') == 1        # une fiche
    # Parole manquée et fausse alarme naissent dans ce bloc : leurs segments le sélectionnent.
    assert html.count('class="pl-errseg') == 3
    assert 'class="pl-frame-label"' in html and "Un seul réseau" in html
    # Le bloc est la première étape affichée après la normalisation, comme la détection avant.
    assert ids[:2] == ["normalisation", "segmentation_neuronale"]


def test_regroupement_lu_dans_le_catalogue():
    catalogue = pipeline.load_catalogue(REPO_ROOT)
    groups = catalogue["regroupements"]["pyannote-community-1"]
    assert groups[0]["etapes"] == ["detection", "segmentation"] and groups[0]["role"]
    assert set(groups[0]["etapes"]) <= set(catalogue["etapes"])
    # Catalogue de --depot sans regroupements : celui de ce code est utilisé.
    assert pipeline._groups({"etapes": {}}, "pyannote-community-1") == groups
    assert pipeline._groups({"regroupements": {}}, "pyannote-community-1") == []
