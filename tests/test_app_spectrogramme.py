"""Vue spectrogramme et énergie de la baseline (D28 §2, chantier B9 ; app/spectrogramme.py),
en mode factice : aucun modèle chargé (la baseline MFCC n'en utilise pas)."""

import librosa
import numpy as np
import pytest
import torch

from app import app as interface
from app import cache, moteurs, spectrogramme
from tests.test_app_demonstration import _fn, _wav, ffmpeg
from whospoke.pipelines.baseline import Baseline, BaselineParams

SR = 16000


def _signal(seconds=6.0, seed=0):
    """Silence bruité, puis salves d'un son harmonique : de quoi détecter de la parole."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * SR)) / SR
    voiced = sum(np.sin(2 * np.pi * 150 * k * t) / k for k in range(1, 8))
    gate = (np.sin(2 * np.pi * 0.4 * t) > 0.2).astype(float)
    return (0.3 * voiced * gate + 3e-3 * rng.standard_normal(len(t))).astype(np.float32)


# --- Spectrogramme : celui de la baseline, quantifié, en pyramide -------------------------


def test_spectrogramme_dont_la_baseline_tire_ses_mfcc():
    y = _signal()
    mfcc, _ = Baseline().analyse(y)
    p = BaselineParams()
    again = librosa.feature.mfcc(S=librosa.power_to_db(spectrogramme.mel_power(y)), n_mfcc=p.n_mfcc).T
    assert again.shape == mfcc.shape
    np.testing.assert_allclose(again, mfcc, rtol=1e-4, atol=1e-3)


def test_quantification_et_plage():
    db = np.array([[-200.0, -spectrogramme.RANGE_DB, -30.0, 0.0, 5.0]])
    assert spectrogramme.quantize(db).tolist() == [[0, 0, 128, 255, 255]]
    db = spectrogramme.mel_db(_signal())
    assert db.max() == 0.0 and db.min() >= -spectrogramme.RANGE_DB
    silent = spectrogramme.mel_db(np.zeros(SR, np.float32))
    assert np.all(silent == -spectrogramme.RANGE_DB)


def test_pyramide_moyenne_par_paires():
    frames = np.random.default_rng(1).integers(0, 256, size=(1001, 40)).astype(np.uint8)
    levels = spectrogramme.pyramid(frames)
    assert [len(level) for level in levels] == [1001, 501, 251]
    assert len(levels[-1]) <= spectrogramme.MIN_LEVEL_FRAMES
    expected = (frames[0].astype(int) + frames[1] + 1) // 2
    assert levels[1][0].tolist() == expected.tolist()
    assert levels[1][-1].tolist() == frames[-1].tolist()      # trame isolée : moyenne avec elle-même
    assert spectrogramme.pyramid(frames[:10])[0] is not None and len(spectrogramme.pyramid(frames[:10])) == 1


def test_fichier_de_la_pyramide(tmp_path):
    wav = tmp_path / "essai.wav"
    y = _signal(seconds=20.0)
    described = spectrogramme.compute(wav, y)
    path = described["fichier"]
    assert path == tmp_path / ("essai" + spectrogramme.SUFFIX)
    data = np.fromfile(path, dtype=np.uint8)
    bands = described["bandes"]
    assert bands == BaselineParams().n_mels and described["pas_s"] == BaselineParams().hop_s
    sizes = [level["trames"] * bands for level in described["niveaux"]]
    assert data.size == sum(sizes)
    assert [level["decalage"] for level in described["niveaux"]] == list(np.cumsum([0] + sizes[:-1]))
    first = data[:sizes[0]].reshape(-1, bands)
    expected = spectrogramme.quantize(spectrogramme.mel_db(y)).T
    assert np.array_equal(first, expected)
    # Trame la plus énergique à 255 ; salve (0,2 à 1 s) bien plus énergique que le silence (1,4 à 2,4 s).
    assert first.max() == 255 and first[140:240].mean() + 50 < first[20:100].mean()


def test_calcul_en_tache_de_fond_une_seule_fois(tmp_path):
    wav = tmp_path / "fond.wav"
    y = _signal(seconds=3.0)
    job = spectrogramme.start(wav, y)
    assert spectrogramme.start(wav, y) is job
    assert spectrogramme.result(wav)["fichier"].is_file()
    assert spectrogramme.result(tmp_path / "jamais.wav") is None        # ni calcul ni signal
    assert spectrogramme.result(tmp_path / "tard.wav", y)["fichier"].is_file()


def test_graduations_sur_l_echelle_mel():
    ticks = spectrogramme.band_ticks()
    assert [tick["hz"] for tick in ticks] == list(spectrogramme.TICKS_HZ)
    ys = [tick["y"] for tick in ticks]
    assert all(0.0 <= y <= 1.0 for y in ys) and ys == sorted(ys, reverse=True)   # aigu en haut
    assert ticks[-1]["libelle"] == "8 kHz" and ticks[-1]["y"] < 0.02
    # Échelle mel : de 1 à 2 kHz, puis de 2 à 4 kHz, des écarts du même ordre (pas linéaire).
    gaps = np.diff([tick["y"] for tick in ticks if tick["hz"] >= 1000])
    assert np.ptp(gaps) < 0.6 * abs(gaps).mean()


# --- Palette : une teinte, pas de clarté réguliers en OKLab, une rampe par mode ----------


@pytest.mark.parametrize("mode, ends", [("clair", spectrogramme.RAMP_LIGHT), ("sombre", spectrogramme.RAMP_DARK)])
def test_rampe_perceptuellement_uniforme(mode, ends):
    colors = np.array(spectrogramme.palettes()[mode]) / 255.0
    assert len(colors) == 256
    assert colors[0].tolist() == pytest.approx((spectrogramme._hex_rgb(ends[0])).tolist(), abs=1 / 255)
    assert colors[-1].tolist() == pytest.approx((spectrogramme._hex_rgb(ends[1])).tolist(), abs=1 / 255)
    lab = spectrogramme.to_oklab(colors)
    lightness = lab[:, 0]
    steps = np.diff(lightness)
    direction = np.sign(lightness[-1] - lightness[0])
    assert np.all(steps * direction >= 0)                         # clarté monotone (égalités : arrondi à 8 bits)
    ideal = np.linspace(lightness[0], lightness[-1], len(lightness))
    assert np.abs(lightness - ideal).max() < 0.004                # pas réguliers en OKLab, à l'arrondi près
    assert np.hypot(lab[:, 1], lab[:, 2]).max() < 0.01            # neutre : la couleur reste aux locuteurs
    # Plus d'énergie = plus foncé en clair, plus clair en sombre.
    assert (direction < 0) == (mode == "clair")


def test_oklab_aller_retour():
    rgb = np.random.default_rng(2).random((50, 3))
    np.testing.assert_allclose(spectrogramme.from_oklab(spectrogramme.to_oklab(rgb)), rgb, atol=1e-6)


# --- Détection de parole de la baseline : trace du moteur, cache, trace factice ----------


def test_detection_tiree_de_la_trace_de_la_baseline(tmp_path):
    y = _signal()
    trace = Baseline(theta=1.0, trace=True).run(torch.from_numpy(y)[None], SR).trace
    detection = spectrogramme.detection_from_trace(trace)
    assert detection["seuil_db"] == pytest.approx(trace["seuil_db"]) and not detection["factice"]
    assert detection["pas_s"] == BaselineParams().hop_s
    assert len(detection["regions"]) == len(trace["regions_parole"]) > 0
    np.testing.assert_array_equal(detection["energie_db"], trace["energie_db"])
    described = spectrogramme.write_energy(detection, tmp_path / "e.bin")
    stored = np.fromfile(tmp_path / "e.bin", dtype=np.float32)
    np.testing.assert_array_equal(stored, trace["energie_db"])
    assert described["trames"] == len(stored) and described["min_db"] < described["seuil_db"] < described["max_db"]
    # Aller-retour du cache, au dixième de dB.
    back = spectrogramme.decode_energy(spectrogramme.encode_energy(detection))
    np.testing.assert_allclose(back["energie_db"], detection["energie_db"], atol=0.05)
    assert back["regions"] == detection["regions"] and back["seuil_db"] == detection["seuil_db"]
    # Détection oracle (aucun seuil) ou autre moteur : rien à afficher.
    assert spectrogramme.detection_from_trace(dict(trace, seuil_db=None)) is None
    assert spectrogramme.detection_from_trace(None) is None
    assert spectrogramme.decode_energy(None) is None


def test_trace_fabriquee_du_moteur_factice():
    y = _signal()
    trace = moteurs.fabricated_trace(y)
    assert trace["factice"] and trace["pas_trame_s"] == moteurs.FAKE_HOP_S
    assert len(trace["energie_db"]) == len(y) // int(moteurs.FAKE_HOP_S * SR)
    detection = spectrogramme.detection_from_trace(trace)
    assert detection["factice"] and detection["regions"]
    assert all(b > a for a, b in detection["regions"])
    assert moteurs.fabricated_trace(np.zeros(10, np.float32))["regions_parole"].shape == (0, 2)


def test_moteur_factice_ne_trace_que_pour_une_baseline(tmp_path):
    rttm = tmp_path / "essai.rttm"
    rttm.write_text("SPEAKER essai 1 0.000 2.000 <NA> <NA> A <NA> <NA>\n")
    waveform = torch.from_numpy(_signal())[None]
    for key, expected in (("baseline-ecapa", True), ("pyannote-community-1", False)):
        engine = moteurs.FakeEngine(moteurs.SPECS[key], simulated_s=0.0, fabricated=tmp_path)
        engine.trace = True
        assert (engine.run(waveform, SR, uri="essai").trace is not None) is expected
        engine.trace = False
        assert engine.run(waveform, SR, uri="essai").trace is None


# --- Visualiseur : valeur, gabarit, script --------------------------------------------------


def test_valeur_du_visualiseur_avec_spectrogramme_et_detection(tmp_path):
    from tests.test_app_appariement import full_result

    result = full_result(tmp_path)
    result["wav"] = tmp_path / "x.wav"
    result["spectrogramme"] = spectrogramme.compute(tmp_path / "x.wav", _signal(2.0))
    value = interface._viewer_value(result)
    spec = value["spectrogramme"]
    assert "fichier" not in spec and spec["url"].endswith("x" + spectrogramme.SUFFIX)
    assert spec["url"].startswith("/gradio_api/file=") and len(spec["palettes"]["clair"]) == 256
    assert value["detection"] is None
    # Détection du second moteur quand le premier n'en a pas.
    detection = spectrogramme.detection_from_trace(moteurs.fabricated_trace(_signal(2.0)))
    second = dict(result, libelle="Baseline ECAPA",
                  detection=spectrogramme.write_energy(detection, tmp_path / "x.ecapa.energie.bin"))
    value = interface._viewer_value(dict(result, comparaison=second))
    assert value["detection"]["moteur"] == "Baseline ECAPA" and value["detection"]["factice"]
    assert value["detection"]["url"].endswith("x.ecapa.energie.bin")
    assert interface._viewer_value(dict(result, spectrogramme=None))["spectrogramme"] is None


def test_gabarit_et_script_de_la_vue_spectrogramme():
    template = interface.VIEWER_TEMPLATE
    for name in ("wsp-view-wave", "wsp-view-spec", "wsp-energy-toggle", "wsp-spec-canvas", "wsp-spec-axis",
                 "wsp-spec-legend", "wsp-energy-canvas", "wsp-energy-tip", "wsp-energy-legend"):
        assert name in template
    script = (interface.STATIC_DIR / "visualiseur.js").read_text()
    # Image du serveur découpée à la partie visible, au niveau de la pyramide adapté au zoom.
    for marker in ("function drawSpectrogram", "spec.niveaux", "visibleWindow()", "scheduleLayers()",
                   "function drawEnergy", "e.seuil_db", "setLineDash", "MutationObserver"):
        assert marker in script
    assert "WaveSurfer.Spectrogram" not in script                  # greffon écarté (mesures de B9)
    assert not (interface.WAVESURFER_DIR / "spectrogram.min.js").exists()
    css = (interface.STATIC_DIR / "visualiseur.css").read_text()
    assert "--wsp-spec-h: 112px" in css and "--wsp-spec-h: 144px" in css


# --- De bout en bout, moteur factice ----------------------------------------------------------


@ffmpeg
def test_analyse_factice_avec_spectrogramme_et_trace(tmp_path, monkeypatch):
    (tmp_path / "run").mkdir()
    monkeypatch.setattr(interface, "RUN_DIR", tmp_path / "run")
    blocks = interface.build_app(fake=True, fake_max_s=0.2, cache_dir=tmp_path / "cache")
    analyse = _fn(blocks, "analyse")
    audio = _wav(tmp_path / "004c_PAPH.wav")       # nom reconnu par le moteur factice
    settings = ("pyannote-community-1", True, "baseline-ecapa", "Automatique", 2, 2, 6, "cpu")
    prepared = list(_fn(blocks, "audio_changed")(audio, *settings, True))[-1][0]

    def viewer(updates):
        return next(v for v in updates[-1].values() if isinstance(v, dict) and "spectrogramme" in v)

    value = viewer(list(analyse(prepared, audio, *settings, None, True)))
    spec = value["spectrogramme"]
    path = spec["url"].removeprefix("/gradio_api/file=")
    assert np.fromfile(path, dtype=np.uint8).size == sum(level["trames"] for level in spec["niveaux"]) * spec["bandes"]
    detection = value["detection"]
    assert detection["moteur"] == "Baseline ECAPA" and detection["factice"]
    energy = np.fromfile(detection["url"].removeprefix("/gradio_api/file="), dtype=np.float32)
    assert len(energy) == detection["trames"] == 800                  # 8 s par tranches de 10 ms
    # Réaffichage depuis le cache : la trace est rendue avec le résultat.
    entries = [cache.ResultCache(tmp_path / "cache").get(key) for key in
               [p.stem for p in (tmp_path / "cache").glob("*.json")]]
    assert any(entry and entry.get("detection") for entry in entries)
    again = viewer(list(analyse(prepared, audio, *settings, None, True)))
    assert again["detection"]["seuil_db"] == detection["seuil_db"]
    assert again["detection"]["regions"] == detection["regions"]
