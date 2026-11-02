"""Démonstration (audit R-D2, R-D3, R-U1, R-U5 ; D17, amendement 2 ; app/app.py), en mode
factice : aucun modèle chargé, cache dans un dossier temporaire."""

import shutil
import wave
from types import SimpleNamespace

import numpy as np
import pytest

from app import app as interface
from app import cache, moteurs, temps, theme

ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")


# --- Préchauffage et indicateur « moteurs prêts » (R-D2) ----------------------------


def test_signal_d_appel_a_blanc():
    waveform, sample_rate = interface.warmup_signal()
    assert sample_rate == 16000 and waveform.shape == (1, int(interface.WARMUP_S * 16000))
    assert waveform.dtype.is_floating_point and 0.01 < float(waveform.abs().max()) <= 1.0


def test_prechauffage_factice_rend_les_moteurs_chauds(monkeypatch):
    monkeypatch.setattr(interface, "FAKE_WARMUP_PAUSE_S", 0.0)
    engines = interface.EngineCache(fake=True, fake_max_s=1.0)
    spec = moteurs.SPECS["pyannote-community-1"]
    assert not engines.is_warm(spec.key, "cpu")
    engines.warm_up([(spec, "cpu")])
    status = engines.warmup
    assert status.enabled and status.finished and (status.done, status.total) == (1, 1) and not status.failures
    assert engines.is_warm(spec.key, "cpu") and not engines.is_warm(spec.key, "mps")
    assert engines.get(spec, "cpu")[1] is None          # déjà chargé : pas de nouveau chargement


def test_echec_du_prechauffage_consigne_sans_arreter_les_autres(monkeypatch):
    monkeypatch.setattr(interface, "FAKE_WARMUP_PAUSE_S", 0.0)
    engines = interface.EngineCache(fake=True, fake_max_s=1.0)
    broken = moteurs.EngineSpec("casse", "Moteur cassé", "baseline", "EXP-9999", ("analyse",), True, False)
    good = moteurs.SPECS["baseline-mfcc"]
    engines.warm_up([(broken, "cpu"), (good, "cpu")])
    assert list(engines.warmup.failures) == ["Moteur cassé"] and "EXP-9999" in engines.warmup.failures["Moteur cassé"]
    assert engines.warmup.finished and engines.is_warm(good.key, "cpu") and not engines.is_warm("casse", "cpu")


def test_indicateur_moteurs_prets():
    status = interface.WarmupStatus()
    assert "Préchauffage désactivé" in interface._engines_badge(status)
    status = interface.WarmupStatus(enabled=True, total=4, done=1, current="pyannote community-1")
    html = interface._engines_badge(status)
    assert "Préchauffage des moteurs (1/4) : pyannote community-1" in html and 'data-state="run"' in html
    status.finished, status.done = True, 4
    assert ">Moteurs prêts<" in interface._engines_badge(status)
    status.failures = {"Baseline <ECAPA>": "modèle absent"}
    html = interface._engines_badge(status)
    assert "sauf Baseline &lt;ECAPA&gt;" in html and 'data-state="warn"' in html
    header = interface._header_html(True, status)
    assert "Moteur factice" in header and "ws-engines" in header


# --- Temps annoncé et temps restant (D17, amendement 2) ------------------------------


def test_surcout_fixe_non_compte_pour_un_moteur_prechauffe():
    from app.moteurs import FixedOverhead

    run = {"rtf": 0.0512, "measured": SimpleNamespace(exp_id="EXP-0007"),
           "overhead": FixedOverhead(1.1, "2026-11-01"), "warm": True}
    assert interface._estimate_source(run, fake=False).endswith("moteur préchauffé : surcoût fixe non compté")
    run["warm"] = False
    assert interface._estimate_source(run, fake=False).endswith("surcoût fixe 1,1\u202fs mesuré le 01/11/2026")


@pytest.mark.parametrize("span, recalibrated, text", [
    (None, False, "temps restant inconnu (RTF non mesuré sur ce périphérique)"),
    ((0.0, 0.0), False, "estimation dépassée, calcul en cours"),
    ((0.0, 6.0), False, "reste au plus 6\u202fs"),
    ((20.0, 29.0), False, "reste entre 20\u202fs et 29\u202fs"),
    ((12.0, 12.0), True, "reste environ 12\u202fs, recalé sur la vitesse observée"),
])
def test_texte_du_temps_restant(span, recalibrated, text):
    assert interface._remaining_text(span, recalibrated) == text


def test_debut_de_l_etape_la_plus_longue():
    steps = ("segmentation", "detection", "empreintes", "sortie")
    ends = {"segmentation": 3.0, "detection": 4.0}
    # Commencée à la fin de l'étape précédente, même sans avancement encore rapporté.
    assert interface._longest_started_s(steps, "empreintes", {}, ends, t0=0.0, now=10.0) == 6.0
    assert interface._longest_started_s(steps, "empreintes", {}, {"segmentation": 3.0}, 0.0, 10.0) is None
    assert interface._longest_started_s(steps, "segmentation", {"segmentation": 0.2}, {}, 1.0, 5.0) == 4.0
    assert interface._longest_started_s(steps, None, {}, ends, 0.0, 10.0) is None


# --- Finitions (R-U5) ------------------------------------------------------------------


def test_zones_de_depot_en_francais_pour_toutes_les_langues_de_gradio():
    from pathlib import Path

    import gradio as gr

    assets = Path(gr.__file__).parent / "templates" / "frontend" / "assets"
    provided = {path.name.rsplit("-", 1)[0] for path in assets.glob("*.js")}
    assert set(theme.GRADIO_LOCALES) <= provided
    i18n = gr.I18n(**theme.UPLOAD_TEXT)
    for locale in theme.GRADIO_LOCALES:
        assert i18n.translations[locale]["upload_text.drop_file"] == "Déposez le fichier ici"


def test_bandeau_des_reglages_replies():
    prepared = {"nom": "<réunion>.wav", "duree_s": 300.0}
    results = [{"libelle": "pyannote community-1", "device": "mps",
                "configuration": {"nombre_locuteurs": {"mode": "fourchette", "min": 2, "max": 6}}},
               {"libelle": "Baseline ECAPA", "device": "cpu",
                "configuration": {"nombre_locuteurs": {"mode": "fourchette", "min": 2, "max": 6}}}]
    html = interface._band_html(prepared, results)
    assert "&lt;réunion&gt;.wav" in html and "5\u202fmin 00\u202fs" in html
    assert "pyannote community-1 puis Baseline ECAPA" in html and "entre 2 et 6 locuteurs" in html
    assert "mps, cpu" in html


# --- Analyse de bout en bout : annonce, cache, réglages repliés -------------------------


def _wav(path, seconds=8.0, sample_rate=16000):
    t = np.arange(int(seconds * sample_rate)) / sample_rate
    data = (3000 * np.sin(2 * np.pi * 220 * t) * (np.sin(2 * np.pi * 0.5 * t) > 0)).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(data.tobytes())
    return str(path)


def _fn(blocks, name):
    return next(f.fn for f in blocks.fns.values() if getattr(f.fn, "__name__", "") == name)


def _by_label(update: dict) -> dict:
    """Sorties d'un `yield` de l'analyse, par classe CSS ou libellé du composant."""
    named = {}
    for component, value in update.items():
        key = (getattr(component, "elem_classes", None) or [None])[0] or getattr(component, "label", None)
        named.setdefault(key, value)
    return named


@ffmpeg
def test_analyse_puis_reaffichage_depuis_le_cache(tmp_path, monkeypatch):
    (tmp_path / "run").mkdir()
    monkeypatch.setattr(interface, "RUN_DIR", tmp_path / "run")
    blocks = interface.build_app(fake=True, fake_max_s=0.2, cache_dir=tmp_path / "cache")
    analyse, estimate = _fn(blocks, "analyse"), _fn(blocks, "estimate_html")
    audio = _wav(tmp_path / "004c_PAPH.wav")       # nom reconnu par le moteur factice (EXP-0007)
    settings = ("pyannote-community-1", False, "baseline-ecapa", "Automatique", 2, 2, 6, "cpu")

    # Durée annoncée avant le lancement : fourchette, moteur froid (pas de préchauffage ici).
    prepared = list(_fn(blocks, "audio_changed")(audio, *settings, True))[-1][0]
    assert prepared["duree_s"] == pytest.approx(8.0) and len(prepared["empreinte"]) == 64
    announce = estimate(prepared, *settings, True)
    assert "Durée estimée du calcul : " in announce and "moteur froid" in announce

    first = list(analyse(prepared, audio, *settings, None, True))
    final = first[-1]
    result = next(v for k, v in final.items() if isinstance(v, dict) and "annotation" in v)
    assert result["cache"] is None and result["moteur"] == "factice (pyannote-community-1)"
    store = cache.ResultCache(tmp_path / "cache")
    assert store.stats()[0] == 1
    # Réglages repliés et bandeau affiché (R-U1) ; l'annonce dit désormais « en cache ».
    visibility = [v.get("visible") for v in final.values() if isinstance(v, dict) and "visible" in v]
    assert False in visibility and True in visibility
    assert "résultat en cache" in estimate(prepared, *settings, True)
    assert "moteur prêt" in estimate(prepared, *settings, False)     # chaud après l'analyse

    second = list(analyse(prepared, audio, *settings, None, True))
    again = next(v for k, v in second[-1].items() if isinstance(v, dict) and "annotation" in v)
    assert again["cache"] and again["annotation"] == result["annotation"]
    assert again["calcul_s"] == pytest.approx(result["calcul_s"])
    assert len(second) < len(first)                      # aucun pas de calcul simulé
    # Badge visible dans le panneau d'avancement, avec la date du calcul d'origine.
    statuses = [v for v in second[-1].values() if isinstance(v, str) and "st-root" in v]
    assert len(statuses) == 1 and "Résultat réaffiché depuis le cache, calculé le " in statuses[0]
    assert "ws-cache-badge" not in next(v for v in first[-1].values() if isinstance(v, str) and "st-root" in v)
    # Case décochée : nouveau calcul, et l'annonce signale le résultat présent en cache.
    assert "nouveau calcul (case « Réafficher un résultat déjà calculé » décochée)" in estimate(prepared, *settings, False)

    # Cache désactivé : nouveau calcul ; autre réglage : autre clé.
    third = list(analyse(prepared, audio, *settings, None, False))
    assert next(v for v in third[-1].values() if isinstance(v, dict) and "annotation" in v)["cache"] is None
    imposed = ("pyannote-community-1", False, "baseline-ecapa", "Imposé", 3, 2, 6, "cpu")
    assert "résultat en cache" not in estimate(prepared, *imposed, True)

    # Vider le cache.
    info, _ = _fn(blocks, "clear_cache_click")(prepared, *settings, True)
    assert "aucun résultat" in info and store.stats()[0] == 0


@ffmpeg
def test_meme_audio_sous_un_autre_nom_meme_empreinte(tmp_path, monkeypatch):
    (tmp_path / "run").mkdir()
    monkeypatch.setattr(interface, "RUN_DIR", tmp_path / "run")
    blocks = interface.build_app(fake=True, fake_max_s=0.2, cache_dir=tmp_path / "cache")
    changed = _fn(blocks, "audio_changed")
    settings = ("pyannote-community-1", False, "baseline-ecapa", "Automatique", 2, 2, 6, "cpu", True)
    a = _wav(tmp_path / "a.wav")
    (tmp_path / "copie").mkdir()
    b = shutil.copy(a, tmp_path / "copie" / "b.wav")
    prints = [list(changed(path, *settings))[-1][0]["empreinte"] for path in (a, b)]
    assert prints[0] == prints[1]


def test_construction_sans_prechauffage_ni_minuterie_active(tmp_path):
    blocks = interface.build_app(fake=True, cache_dir=tmp_path)
    import gradio as gr

    timers = [block for block in blocks.blocks.values() if isinstance(block, gr.Timer)]
    assert len(timers) == 1 and timers[0].active is False


def test_reafficher_depuis_le_cache_decoche_par_defaut(tmp_path):
    import gradio as gr

    blocks = interface.build_app(fake=True, cache_dir=tmp_path)
    boxes = [b for b in blocks.blocks.values() if isinstance(b, gr.Checkbox)
             and b.label == "Réafficher un résultat déjà calculé"]
    assert len(boxes) == 1 and boxes[0].value is False


def test_badges_du_cache():
    cached = {"libelle": "pyannote community-1", "cache": "2026-11-01T19:50:12"}
    fresh = {"libelle": "Baseline ECAPA", "cache": None}
    assert interface._cache_badges([cached]) == ["Résultat réaffiché depuis le cache, calculé le 01/11/2026 à 19:50"]
    assert interface._cache_badges([cached, fresh]) == [
        "pyannote community-1 : résultat réaffiché depuis le cache, calculé le 01/11/2026 à 19:50"]
    assert interface._cache_badges([fresh]) == []
    html = interface._status_html([], {}, "Fini", badges=["Résultat <réaffiché>"])
    assert 'class="ws-cache-badge"' in html and "&lt;réaffiché&gt;" in html


def test_cle_fondee_sur_configuration_effective_et_revisions():
    from whospoke import embeddings
    from whospoke.pipelines import pyannote_community1 as wrapper

    expected = {
        "pyannote-community-1": {wrapper.MODEL_ID: wrapper.MODEL_REVISION},
        "baseline-ecapa": {embeddings.ECAPA_SOURCE: embeddings.ECAPA_REVISION},
        "baseline-wespeaker": {embeddings.WESPEAKER_SOURCE: embeddings.WESPEAKER_REVISION},
        "baseline-mfcc": {},
    }
    for key, revisions in expected.items():
        spec = moteurs.SPECS[key]
        try:
            moteurs.experiment_dir(spec.source_exp)
        except moteurs.EngineUnavailable:
            continue
        assert moteurs.model_revisions(spec) == revisions
        assert moteurs.effective_configuration(spec)        # consignée par l'expérience source
