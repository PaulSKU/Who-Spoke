"""Fonctions de scripts/data/make_summre_degrade.py (D24), sur signaux synthétiques."""

import importlib.util

import numpy as np
import pytest

from whospoke.experiment import REPO_ROOT

spec = importlib.util.spec_from_file_location(
    "make_summre_degrade", REPO_ROOT / "scripts" / "data" / "make_summre_degrade.py")
degrade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(degrade)

CONFIG, CONFIG_SHA = degrade.load_config()


def test_configuration_de_d24():
    assert set(CONFIG["conditions"]) == {"rev04", "rev08", "bru15", "bru05", "cod16", "cod08", "salle"}
    assert CONFIG["conditions"]["salle"] == {"reverberation": {"rt60_s": 0.6}, "bruit": {"rsb_db": 10}}
    assert "OMEETING" not in CONFIG["bruit"]["environnements"]  # discussion enregistrée
    assert len(CONFIG_SHA) == 64


def test_tirages_deterministes_et_independants_de_l_ordre():
    a = degrade.assignments("summre__007a_ECRH", 4, CONFIG)
    b = degrade.assignments("summre__007a_ECRH", 4, CONFIG)
    c = degrade.assignments("summre__008a_EARH", 4, CONFIG)
    assert a == b
    assert a != c


def test_positions_dans_la_salle_et_distinctes():
    room = CONFIG["salle"]
    for seed in range(20):
        positions = degrade.place_speakers(4, np.random.default_rng(seed), room)
        azimuths = sorted(p["azimut_deg"] for p in positions)
        gaps = np.diff(azimuths + [azimuths[0] + 360.0])
        assert min(gaps) >= room["ecart_angulaire_min_deg"] - 1e-9
        for p in positions:
            assert room["marge_mur_m"] <= p["x"] <= room["dimensions_m"][0] - room["marge_mur_m"]
            assert room["marge_mur_m"] <= p["y"] <= room["dimensions_m"][1] - room["marge_mur_m"]
            horizontal = np.hypot(p["x"] - room["micro_m"][0], p["y"] - room["micro_m"][1])
            assert room["distance_m"][0] <= horizontal <= room["distance_m"][1]


def test_bruit_boucle_sans_saut():
    noise = np.sin(np.arange(1000) / 7.0)
    out = degrade.looped(noise, 3500, offset=300, fade=50)
    assert len(out) == 3500
    np.testing.assert_array_equal(out[:650], noise[300:950])
    assert np.max(np.abs(np.diff(out))) < 0.5  # fondu enchaîné : aucune discontinuité


def test_rsb_sur_les_zones_de_parole():
    rng = np.random.default_rng(0)
    signal = np.zeros(16000)
    signal[4000:12000] = 0.3 * rng.standard_normal(8000)
    mask = signal != 0
    noise = 0.05 * rng.standard_normal(16000)
    for snr in (15.0, 5.0):
        noisy, gain = degrade.add_noise(signal, noise, mask, snr)
        added = noisy - signal
        measured = 10 * np.log10(np.mean(signal[mask] ** 2) / np.mean(added[mask] ** 2))
        assert measured == pytest.approx(snr, abs=1e-9)


def test_aucun_ecretage():
    pcm, gain = degrade.finalize(np.array([0.0, 1.8, -0.9]))
    assert gain == pytest.approx(degrade.PEAK_MAX / 1.8)
    assert np.max(np.abs(pcm)) <= 32767
    pcm, gain = degrade.finalize(np.array([0.0, 0.5]))
    assert gain == 1.0


@pytest.mark.modele
def test_reponses_impulsionnelles_et_rt60():
    """Réponses de pyroomacoustics : délai direct retranché, RT60 T20 proche de la cible."""
    room = CONFIG["salle"]
    positions = degrade.place_speakers(2, np.random.default_rng(0), room)
    rirs, info = degrade.room_rirs(positions, 0.6, room)
    assert len(rirs) == 2
    assert all(int(np.argmax(np.abs(r))) < 2 * 81 for r in rirs)  # pic direct dans le filtre fractionnaire
    assert all(abs(t - 0.6) < 0.15 for t in info["rt60_mesure_t20_s"])
    assert all(t > t20 for t, t20 in zip(info["rt60_mesure_t60_s"], info["rt60_mesure_t20_s"]))
