"""Chantier B8 : zoom maximal relevé, mode présentation, configuration de démonstration
(D17, amendement 1 : configs/demo.yaml au gel). Moteur factice, aucun modèle chargé."""

import shutil

import pytest

from app import app as interface
from app import moteurs, reproductibilite
from app.app import STATIC_DIR
from whospoke.experiment import REPO_ROOT

EXAMPLE = REPO_ROOT / "configs" / "demo.exemple.yaml"


def _repo_with(tmp_path, text: str | None):
    """Dépôt minimal : les expériences du vrai dépôt, et configs/demo.yaml si `text`."""
    (tmp_path / "experiments").symlink_to(REPO_ROOT / "experiments")
    if text is not None:
        (tmp_path / "configs").mkdir()
        (tmp_path / "configs" / "demo.yaml").write_text(text, encoding="utf-8")
    return tmp_path


def _component(blocks, label):
    return next(block for block in blocks.blocks.values() if getattr(block, "label", None) == label)


def _fn(blocks, name):
    return next(fn.fn for fn in blocks.fns.values() if getattr(fn.fn, "__name__", "") == name)


# --- Zoom maximal (1) -----------------------------------------------------------------


def test_zoom_maximal_150_px_par_seconde_et_segments_hors_vue_masques():
    script = (STATIC_DIR / "visualiseur.js").read_text()
    assert "const MAX_PX_PER_S = 150;" in script
    # Mesuré sur 30 min (app/README.md) : sans masquage, la lecture suivie tombait à 20 images/s.
    assert "function cullBars(scroll)" in script and "cullBars(scroll);" in script
    assert script.count("element._bars.push(bar);") == 2      # segments et zones d'erreur


# --- Configuration de démonstration (3) ----------------------------------------------


def test_sans_configs_demo_yaml_la_correspondance_du_code_s_applique(tmp_path):
    demo = moteurs.demo_config(_repo_with(tmp_path, None))
    assert demo.source == "app/moteurs.py" and not demo.frozen and demo.sha256 is None
    assert demo.specs == moteurs.SPECS and demo.default_engine == moteurs.DEFAULT_ENGINE
    assert all(conf == {"mode": "automatique"} for conf in demo.speakers.values())
    assert demo.trace() == {"fichier": "app/moteurs.py", "gel": None, "sha256": None}


def test_exemple_lu_comme_le_sera_configs_demo_yaml(tmp_path):
    demo = moteurs.demo_config(_repo_with(tmp_path, EXAMPLE.read_text()))
    assert demo.source == "configs/demo.yaml" and demo.frozen and demo.frozen_on == "2026-11-10"
    assert demo.default_engine == "pyannote-community-1" and len(demo.sha256) == 64
    assert {key: spec.source_exp for key, spec in demo.specs.items()} == {
        "baseline-mfcc": "EXP-0009", "baseline-ecapa": "EXP-0012", "baseline-wespeaker": "EXP-0015",
        "pyannote-community-1": "EXP-0007"}
    assert demo.speakers["pyannote-community-1"] == {"mode": "fourchette", "min": 2, "max": 6}
    assert demo.speakers["baseline-mfcc"] == {"mode": "automatique"}
    # Au gel, seul demo.yaml sera écrit : l'exemple ne doit pas être pris pour lui.
    assert moteurs.demo_config(REPO_ROOT, EXAMPLE).source == "configs/demo.exemple.yaml"


def test_l_experience_source_de_la_configuration_remplace_celle_du_code(tmp_path):
    text = EXAMPLE.read_text().replace("experience_source: EXP-0012", "experience_source: EXP-0004")
    text = text.replace("moteur_par_defaut: pyannote-community-1", "moteur_par_defaut: baseline-ecapa")
    demo = moteurs.demo_config(_repo_with(tmp_path, text))
    assert demo.specs["baseline-ecapa"].source_exp == "EXP-0004" and demo.default_engine == "baseline-ecapa"
    assert moteurs.SPECS["baseline-ecapa"].source_exp == "EXP-0012"     # le code n'est pas modifié
    # Une expérience source absente rend le moteur indisponible, comme avant le gel.
    reasons = interface._availability(True, tmp_path / "experiments", {
        "baseline-ecapa": moteurs.dataclasses.replace(demo.specs["baseline-ecapa"], source_exp="EXP-9998")})
    assert reasons == {"baseline-ecapa": "EXP-9998 n'existe pas encore"}


@pytest.mark.parametrize("old, new, message", [
    ("baseline-mfcc:\n", "baseline-mfcc-v2:\n", "moteur inconnu « baseline-mfcc-v2 »"),
    ("  baseline-wespeaker:\n    experience_source: EXP-0015\n", "",
     "baseline-wespeaker absent de « moteurs »"),
    ("experience_source: EXP-0009", "experience_source: 9", "attend un identifiant EXP-NNNN"),
    ("experience_source: EXP-0009", "experience_source: EXP-0009\n    nombre_locuteurs: {mode: fourchette, min: 2, max: 6}",
     "Baseline MFCC ne prend pas en charge une fourchette"),
    ("min: 2, max: 6", "min: 7, max: 6", "« min » (7) dépasse « max » (6)"),
    ("min: 2, max: 6", "min: deux, max: 6", "« min » doit être un entier"),
    ("{mode: fourchette, min: 2, max: 6}", "{mode: libre}", "« mode » vaut automatique, impose ou fourchette"),
    ("moteur_par_defaut: pyannote-community-1", "moteur_par_defaut: nemo", "« moteur_par_defaut » (nemo)"),
    ("moteurs:\n", "engines:\n", "la clé « moteurs » manque"),
    ("gel: 2026-11-10", "gel: [2026-11-10", "n'est pas un YAML lisible"),
])
def test_configuration_incoherente_refusee_avec_ce_qu_il_faut_corriger(tmp_path, old, new, message):
    text = EXAMPLE.read_text()
    assert old in text
    with pytest.raises(moteurs.DemoConfigError, match=message.replace("(", r"\(").replace(")", r"\)")):
        moteurs.demo_config(_repo_with(tmp_path, text.replace(old, new, 1)))


def test_nombre_impose_par_defaut(tmp_path):
    text = EXAMPLE.read_text().replace("{mode: fourchette, min: 2, max: 6}", "{mode: impose, valeur: 4}")
    assert moteurs.demo_config(_repo_with(tmp_path, text)).speakers["pyannote-community-1"] == {
        "mode": "impose", "valeur": 4}


def test_fichier_passe_en_option_introuvable(tmp_path):
    with pytest.raises(moteurs.DemoConfigError, match="--config-demo"):
        moteurs.demo_config(REPO_ROOT, tmp_path / "absent.yaml")


def test_en_tete_affiche_configuration_et_moteur_en_vigueur(tmp_path):
    frozen = moteurs.demo_config(_repo_with(tmp_path, EXAMPLE.read_text()))
    header = interface._header_html(True, None, frozen, "pyannote-community-1")
    assert "Configuration : <code>configs/demo.yaml</code>, gel du 10/11/2026" in header
    assert "pyannote community-1</span> (EXP-0007), entre 2 et 6 locuteurs par défaut" in header
    header = interface._header_html(True, None, frozen, "baseline-ecapa")
    assert "Baseline ECAPA</span> (EXP-0012)</span></p>" in header
    before = moteurs.demo_config(tmp_path / "vide")
    assert "correspondance de <code>app/moteurs.py</code>, avant le gel" in interface._header_html(False, None, before)


def test_application_ouverte_selon_la_configuration(tmp_path):
    repo = _repo_with(tmp_path, EXAMPLE.read_text())
    for name in ("results", "docs", "catalogue"):
        if (REPO_ROOT / name).exists():
            (repo / name).symlink_to(REPO_ROOT / name)
    demo = moteurs.demo_config(repo)
    blocks = interface.build_app(fake=True, repo_root=repo, cache_dir=tmp_path / "cache", demo=demo)
    assert _component(blocks, "Nombre de locuteurs").value == "Fourchette"
    assert (_component(blocks, "Minimum").value, _component(blocks, "Maximum").value) == (2, 6)
    assert _component(blocks, "Nombre imposé").visible is False
    # Changer de moteur : le nombre de locuteurs suit la configuration de ce moteur, et l'en-tête aussi.
    engine_changed = _fn(blocks, "engine_changed")
    info, mode, device, k, k_min, k_max, header = engine_changed("baseline-mfcc")
    assert mode["value"] == "Automatique" and mode["choices"] == ["Automatique", "Imposé"]
    assert "value" not in k and "value" not in k_min and "value" not in k_max     # inchangés
    assert "Baseline MFCC</span> (EXP-0009)" in header
    _, mode, _, _, k_min, k_max, header = engine_changed("pyannote-community-1")
    assert mode["value"] == "Fourchette" and (k_min["value"], k_max["value"]) == (2, 6)
    assert "entre 2 et 6 locuteurs par défaut" in header


def test_fiche_de_reproductibilite_consigne_la_configuration():
    trace = {"configuration_demo": {"fichier": "configs/demo.yaml", "gel": "2026-11-10", "sha256": "a" * 64}}
    result = {"tracabilite": trace, "calcul_s": 1.0, "moteur_cle": "pyannote-community-1", "factice": True,
              "configuration": {"experience_source": "EXP-0007", "reglages": {}, "nombre_locuteurs": {"mode": "automatique"}},
              "device": "cpu", "duree_s": 10.0, "normalisation_s": 0.1, "chargement_s": None, "durees_etapes": {}}
    assert reproductibilite.sheet(result)["configuration_demo"] == trace["configuration_demo"]


# --- Mode présentation (2) ------------------------------------------------------------


def test_bouton_du_mode_presentation_dans_l_en_tete():
    assert 'class="ws-present" aria-pressed="false"' in interface._header_html(False)
    assert 'class="ws-present" aria-pressed="true"' in interface._header_html(False, presentation=True)


def test_option_presentation_pose_le_mode_des_le_chargement():
    on, off = interface.page_head(True), interface.page_head(False)
    assert "window.WS_PRESENTATION = true;" in on and "WS_PRESENTATION = true" not in off
    script = (STATIC_DIR / "presentation.js").read_text()
    assert script in on and script in off and (STATIC_DIR / "glossaire.js").read_text() in off
    assert "classList.toggle('ws-presentation')" in script and "aria-pressed" in script
    assert "ws-presentation" in (STATIC_DIR / "visualiseur.js").read_text()     # zoom recalculé


def test_mode_presentation_agrandit_renforce_et_masque():
    css = (STATIC_DIR / "interface.css").read_text()
    block = css[css.index("html.ws-presentation {"):]
    assert "font-size: 125%;" in block and "--text-md: 18px;" in block
    assert "html.ws-presentation, html.ws-presentation .dark {" in css     # tailles redéclarées en sombre
    assert "html.ws-presentation .dark {" in css
    assert "html.ws-presentation .ws-secondary { display: none !important; }" in css
    viewer = (STATIC_DIR / "visualiseur.css").read_text()
    assert "html.ws-presentation & {" in viewer and ".wsp-hint { display: none; }" in viewer


def test_reglages_secondaires_marques(tmp_path):
    blocks = interface.build_app(fake=True, cache_dir=tmp_path / "cache")
    assert "ws-secondary" in _component(blocks, "Périphérique").elem_classes
    accordion = _component(blocks, "Cache des résultats (plan de repli)")
    assert "ws-secondary" in accordion.elem_classes and "ws-cache" in accordion.elem_classes


@pytest.mark.skipif(shutil.which("node") is None, reason="node absent")
def test_scripts_syntaxe(tmp_path):
    import subprocess

    wrapped = tmp_path / "visualiseur.js"
    wrapped.write_text("function f(element, props, watch) {\n" + (STATIC_DIR / "visualiseur.js").read_text() + "\n}\n")
    for path in (wrapped, STATIC_DIR / "presentation.js"):
        subprocess.run(["node", "--check", str(path)], check=True)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")
def test_comparaison_avec_fourchette_le_second_moteur_estime_le_nombre(tmp_path, monkeypatch):
    # La fourchette de 2 à 6 par défaut de pyannote ne doit pas empêcher la comparaison avec
    # une baseline (second moteur par défaut) : celle-ci tourne en nombre automatique.
    from tests import fabrique

    (tmp_path / "run").mkdir()
    monkeypatch.setattr(interface, "RUN_DIR", tmp_path / "run")
    infos = []
    monkeypatch.setattr(interface.gr, "Info", lambda message, *args, **kwargs: infos.append(message))
    path = fabrique.audio("wav_16k", tmp_path / "essai.wav", 12.0)
    fabrique.write_rttm(tmp_path / "sorties" / "essai.rttm", "essai", fabrique.turns_round_robin(3, 12.0, 1.5))
    blocks = interface.build_app(fake=True, fake_max_s=0.05, cache_dir=tmp_path / "cache",
                                 fake_rttm=tmp_path / "sorties", demo=moteurs.demo_config(REPO_ROOT, EXAMPLE))
    analyse = _fn(blocks, "analyse")
    settings = ("pyannote-community-1", True, "baseline-ecapa", "Fourchette", 2, 2, 6, "cpu")
    final = list(analyse(None, str(path), *settings, None, False))[-1]
    result = next(v for v in final.values() if isinstance(v, dict) and "annotation" in v)
    assert result["configuration"]["nombre_locuteurs"] == {"mode": "fourchette", "min": 2, "max": 6}
    assert infos == ["Fourchette appliquée à pyannote community-1 seulement : Baseline ECAPA estime lui-même "
                     "le nombre de locuteurs."]
    assert result["tracabilite"]["configuration_demo"]["fichier"] == "configs/demo.exemple.yaml"


def test_bandeau_donne_le_reglage_de_chaque_moteur_quand_ils_different():
    prepared = {"nom": "essai.wav", "duree_s": 12.0}
    results = [{"libelle": "pyannote community-1", "device": "cpu",
                "configuration": {"nombre_locuteurs": {"mode": "fourchette", "min": 2, "max": 6}}},
               {"libelle": "Baseline ECAPA", "device": "cpu",
                "configuration": {"nombre_locuteurs": {"mode": "automatique"}}}]
    band = interface._band_html(prepared, results)
    assert ("pyannote community-1 : entre 2 et 6 locuteurs ; Baseline ECAPA : nombre de locuteurs "
            "automatique") in band
    results[1]["configuration"]["nombre_locuteurs"] = {"mode": "fourchette", "min": 2, "max": 6}
    assert "<span>entre 2 et 6 locuteurs</span>" in interface._band_html(prepared, results)
