"""Nemotron 3 Diarization dans l'application (D23, A4 ; D29 : intégré quel que soit le moteur de
démonstration) : moteur, nombre de locuteurs estimé seulement, comparaison avec pyannote,
onglet Pipeline d'un système de bout en bout. Moteur factice, aucun modèle chargé ; le vrai
moteur est vérifié à la fusion."""

import re

import numpy as np
import pytest
import torch

from app import app as interface
from app import moteurs, pipeline
from whospoke.audio import SAMPLE_RATE
from whospoke.experiment import REPO_ROOT

KEY = "nemotron-3"
SPEC = moteurs.SPECS[KEY]
CSS = (interface.STATIC_DIR / "interface.css").read_text()


def page_of(key):
    page = pipeline.load_page(moteurs.SPECS[key], REPO_ROOT)
    if page.unavailable:
        pytest.skip(page.unavailable)
    return page


# --- Moteur ------------------------------------------------------------------------------


def test_moteur_repris_d_exp_0027_en_cpu_nombre_estime_seulement():
    assert (SPEC.label, SPEC.pipeline, SPEC.source_exp) == ("Nemotron 3 Diarization", "nemotron3-diarization", "EXP-0027")
    assert SPEC.cpu_only and SPEC.auto_only and SPEC.max_speakers == 8 and not SPEC.supports_range
    assert SPEC.steps == ("detection",) and SPEC.step_label("detection", "x") == "Réseau de bout en bout"
    assert moteurs.model_revisions(SPEC) == {"nvidia/Nemotron-3-Diarization": "f667ed73aee57d40cc39428eb768b4fd87a0a29e"}


def test_construit_par_l_enveloppe_existante_en_cpu(monkeypatch):
    from whospoke.pipelines import nemotron3

    built = {}

    class Stub:
        def __init__(self, **kwargs):
            built.update(kwargs)

    monkeypatch.setattr(nemotron3, "Nemotron3Diarization", Stub)
    assert isinstance(moteurs.build_engine(SPEC, "mps"), Stub)
    assert built == {"device": "cpu", "speaker_mode": "estime"}       # MPS ignoré : exception Metal


def test_rtf_mesure_et_surcout_mesure_a_la_fusion():
    from app import temps

    measured = temps.measured_rtf("EXP-0027", "cpu", "cpu")
    assert measured is not None and measured.exp_id == "EXP-0027" and 0.005 < measured.rtf < 0.03
    overhead = moteurs.fixed_overhead(KEY, "cpu")                      # mesuré le 03/11 (D29, condition 4)
    assert overhead is not None and overhead.measured_on == "2026-11-03" and (KEY, "cpu") not in moteurs.OVERHEAD_TO_MEASURE
    script = (REPO_ROOT / "scripts" / "measure_overhead.py").read_text()
    assert '("nemotron-3", "cpu"),' in script


def test_moteur_factice_relit_les_rttm_d_exp_0027():
    engine = moteurs.FakeEngine(SPEC, simulated_s=0.0, ticks_per_step=1)
    steps = []
    result = engine.run(torch.zeros(1, 30 * SAMPLE_RATE, dtype=torch.float32), SAMPLE_RATE, uri="007a_ECRH",
                        progress=lambda step, fraction: steps.append(step))
    assert "EXP-0027_nemotron3-summre/rttm/summre__007a_ECRH.rttm" in result.infos["rttm_source"]
    assert steps == ["detection"] and len(result.annotation.labels()) >= 1


def test_impose_ou_fourchette_dit_que_le_moteur_estime_seul():
    for mode in ("Imposé", "Fourchette"):
        note = interface._auto_only_note(SPEC, mode)
        assert note == (f"Nemotron 3 Diarization estime seul le nombre de locuteurs (8 au plus) : « {mode} » "
                        "ne s'applique pas à lui, il analyse en automatique.")
    assert interface._auto_only_note(SPEC, "Automatique") is None
    assert interface._auto_only_note(moteurs.SPECS["pyannote-community-1"], "Imposé") is None


def test_comparaison_par_defaut_nemotron_contre_pyannote():
    assert interface._second_engine(moteurs.SPECS, "pyannote-community-1") == KEY
    assert interface._second_engine(moteurs.SPECS, KEY) == "pyannote-community-1"
    assert interface.CPU_ONLY_INFO[KEY].startswith("CPU seul pour ce moteur (en MPS, exception Metal")


def test_durees_avec_les_libelles_du_moteur():
    html = interface._times_html({
        "moteur_cle": KEY, "normalisation_s": 0.1, "chargement_s": None, "durees_etapes": {"analyse": 0.5,
        "detection": 13.4, "sous_processus": 14.0}, "calcul_s": 14.0, "duree_s": 1200.0, "device": "cpu",
        "rtf_mesure": None, "factice": False, "configuration": {"nombre_locuteurs": {"mode": "automatique"}}})
    assert "<td>Réseau de bout en bout</td>" in html and "Sous-processus (total, échanges compris)" in html


def test_cache_couvre_l_environnement_separe():
    from app import cache

    assert "scripts/envs" in cache.ENGINE_CODE


# --- Onglet Pipeline : système de bout en bout --------------------------------------------


def test_une_seule_etape_de_bout_en_bout_sans_empreintes_ni_regroupement():
    page = page_of(KEY)
    assert [stage.id for stage in page.stages] == ["normalisation", "reseau_bout_en_bout", "sortie"]
    network = page.stages[1]
    assert network.end_to_end and not network.parts and network.number == "2"
    assert {row.name for row in network.rows} == {"nemotron.modele", "nemotron.seuil", "nemotron.trame_s",
                                                   "nemotron.locuteurs_max", "nemotron.n_locuteurs"}
    html = pipeline.render(page)
    tabs = re.findall(r'role="tab" id="pl-tab-([a-z_]+)"', html)
    assert tabs == ["normalisation", "reseau_bout_en_bout", "sortie", "evaluation"]
    assert "De l&#x27;audio aux tours de parole" in html or "De l'audio aux tours de parole" in html
    assert not page.not_catalogued and not page.not_configured and not page.wrong_step


def test_formes_des_donnees_lues_dans_la_configuration():
    page = page_of(KEY)
    assert page.stages[1].shape == "8 sorties de locuteur, trames de 0,01 s"
    assert page.stages[2].shape == "tours de parole (RTTM)" and not page.shape_gaps


def test_naissance_des_erreurs_dans_le_meme_reseau():
    html = pipeline.render(page_of(KEY))
    assert html.count('data-stage="reseau_bout_en_bout"') >= 3
    assert "système de bout en bout, les trois composantes naissent dans le même réseau" in html


def test_mise_en_regard_des_cascades_de_pyannote_et_de_la_baseline():
    page = page_of(KEY)
    assert [label for label, _ in page.cascades] == ["pyannote community-1", "Baseline ECAPA"]
    html = pipeline.render(page)
    figure = html[html.index('<figure class="pl-cascades">'):html.index("</figure>")]
    assert 'class="pl-cas-chip pl-cas-e2e"' in figure and figure.count("pl-cas-e2e") == 1
    assert "Empreintes vocales" in figure and "Représentation" in figure
    # Une cascade n'est pas mise en regard d'elle-même.
    assert not page_of("pyannote-community-1").cascades and "pl-cascades" not in pipeline.render(page_of("pyannote-community-1"))


def test_constats_c18_et_c19_sous_le_reseau_et_les_constats_generaux_ecartes():
    page = page_of(KEY)
    ids = {c.id for c in page.stages[1].constats}
    if not {"C18", "C19"} <= {c.id for c in pipeline.constats_file.read(REPO_ROOT).items}:
        pytest.skip("C18 et C19 absents de docs/constats.yaml")
    assert {"C18", "C19"} <= ids
    # C15 (« moteurs: [] », étape de représentation) porte sur une étape que ce système n'a pas.
    assert "C15" not in ids and not page.constat_issues


def test_moteur_inconnu_d_un_constat_signale(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "constats.yaml").write_text(
        "version: 1\ndate: 2026-11-03\nconstats:\n"
        "  - {id: C90, etape: segmentation, moteurs: [nemotron3], texte: t, sources: [EXP-0027], confiance: certain, cle: true}\n")
    for name in ("experiments", "src"):
        (tmp_path / name).symlink_to(REPO_ROOT / name)
    page = pipeline.load_page(SPEC, tmp_path)
    assert any("constat C90 : moteur « nemotron3 » inconnu de l'application" in issue for issue in page.constat_issues)


# --- Retouche de B14 ------------------------------------------------------------------------


def test_bordure_des_listes_deroulantes_alignee_sur_les_champs():
    assert '.wrap:has(input[role="combobox"]) { border-color: var(--ws-control-line) !important; }' in CSS
