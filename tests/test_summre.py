"""Préparation de SUMM-RE (D20, scripts/data/get_summre.py), sur des données synthétiques."""

import importlib.util

import numpy as np
import pytest

from whospoke.experiment import REPO_ROOT

spec = importlib.util.spec_from_file_location("get_summre", REPO_ROOT / "scripts" / "data" / "get_summre.py")
get_summre = importlib.util.module_from_spec(spec)
spec.loader.exec_module(get_summre)


def words(*spans):
    return [{"word": f"w{i}", "start": start, "end": end} for i, (start, end) in enumerate(spans)]


def track(speaker, segments):
    return {"speaker_id": speaker, "segments": segments}


# --- Référence à partir des mots ----------------------------------------------------------


def test_fusion_des_ecarts_de_200_ms_ou_moins():
    segment = {"start": 0.0, "end": 3.0, "words": words((0.0, 0.5), (0.7, 1.0), (1.21, 1.5), (2.0, 3.0))}
    reference, missing = get_summre.build_reference([track("001", [segment])])
    # 0,2 s exactement : fusionné ; 0,21 s et 0,5 s : non fusionnés.
    assert reference == {"001": [(0.0, 1.0), (1.21, 1.5), (2.0, 3.0)]}
    assert missing == 0


def test_pause_interne_au_segment_conservee():
    # Le segment couvre 0–5 s, mais la référence suit les mots (D20 §3).
    segment = {"start": 0.0, "end": 5.0, "words": words((0.0, 1.0), (4.0, 5.0))}
    reference, _ = get_summre.build_reference([track("001", [segment])])
    assert reference["001"] == [(0.0, 1.0), (4.0, 5.0)]


def test_mot_sans_horodatage_prend_les_bornes_du_segment():
    segment = {"start": 10.0, "end": 12.0, "words": [
        {"word": "a", "start": 10.0, "end": 10.4},
        {"word": "b", "start": None, "end": None},
        {"word": "c", "start": float("nan"), "end": 11.0},
    ]}
    reference, missing = get_summre.build_reference([track("001", [segment])])
    assert missing == 2
    assert reference["001"] == [(10.0, 12.0)]


def test_chevauchement_entre_locuteurs():
    a = track("001", [{"start": 0.0, "end": 4.0, "words": words((0.0, 4.0))}])
    b = track("002", [{"start": 3.0, "end": 6.0, "words": words((3.0, 6.0))}])
    reference, _ = get_summre.build_reference([a, b])
    stats = get_summre.speech_overlap(reference, (0.0, 10.0))
    assert stats["parole_s"] == pytest.approx(6.0)
    assert stats["chevauchement_s"] == pytest.approx(1.0)
    assert stats["par_locuteur_s"] == {"001": pytest.approx(4.0), "002": pytest.approx(3.0)}
    text = get_summre.rttm_text("summre__x", reference)
    assert text.splitlines() == [
        "SPEAKER summre__x 1 0.000 4.000 <NA> <NA> 001 <NA> <NA>",
        "SPEAKER summre__x 1 3.000 3.000 <NA> <NA> 002 <NA> <NA>",
    ]


def test_participant_sans_parole_exclu_du_decompte():
    parlants = [track(s, [{"start": 1.0, "end": 2.0, "words": words((1.0, 2.0))}]) for s in ("001", "002", "003")]
    muet = track("004", [])
    muet_vide = track("005", [{"start": 0.0, "end": 1.0, "words": []}])
    reference, _ = get_summre.build_reference(parlants + [muet, muet_vide])
    assert sorted(reference) == ["001", "002", "003"]


@pytest.mark.parametrize("token", ["+", "*", "@", "@@", "*+", "+ +"])
def test_jeton_non_lexical(token):
    assert get_summre.is_non_lexical(token)


@pytest.mark.parametrize("token", ["oui", "@bonjour", "oui@", "", None, "-"])
def test_jeton_lexical(token):
    # Un rire mêlé à du texte reste de la parole (amendement du 28/10 de D20).
    assert not get_summre.is_non_lexical(token)


def test_jetons_non_lexicaux_retires_de_la_reference():
    segment = {"start": 0.0, "end": 4.0, "words": [
        {"word": "oui", "start": 0.0, "end": 0.5},
        {"word": "@", "start": 1.0, "end": 2.0},
        {"word": "+", "start": 2.0, "end": 2.1},
        {"word": "ah@", "start": 3.0, "end": 4.0},
    ]}
    lexical, _ = get_summre.build_reference([track("001", [segment])])
    complete, _ = get_summre.build_reference([track("001", [segment])], keep_non_lexical=True)
    assert lexical["001"] == [(0.0, 0.5), (3.0, 4.0)]
    assert complete["001"] == [(0.0, 0.5), (1.0, 2.1), (3.0, 4.0)]


def test_locuteur_sans_jeton_lexical_non_compte():
    a = track("001", [{"start": 0.0, "end": 1.0, "words": words((0.0, 1.0))}])
    b = track("002", [{"start": 2.0, "end": 3.0, "words": [{"word": "*", "start": 2.0, "end": 3.0}]}])
    reference, _ = get_summre.build_reference([a, b])
    assert list(reference) == ["001"]


def test_inventaire_des_jetons_retires():
    tracks = [
        track("001", [{"start": 0.0, "end": 3.0, "words": [
            {"word": "+", "start": 0.0, "end": 0.1}, {"word": "@", "start": 0.1, "end": 0.5},
            {"word": "+", "start": 1.0, "end": 1.1}, {"word": "@oui", "start": 2.0, "end": 3.0},
        ]}]),
        track("002", [{"start": 0.0, "end": 1.0, "words": [{"word": "@@", "start": 0.0, "end": 1.0}]}]),
    ]
    inventory = get_summre.non_lexical_inventory(tracks)
    assert inventory == {"+": 2, "@": 1, "@@": 1}
    text = get_summre.format_inventory(inventory)
    assert text == "+:2;@:1;@@:1"
    assert get_summre.parse_inventory(text) == inventory


def test_reference_et_uem_ecrites_sans_jetons(tmp_path, monkeypatch):
    monkeypatch.setattr(get_summre, "RTTM_DIR", tmp_path / "rttm")
    monkeypatch.setattr(get_summre, "UEM_DIR", tmp_path / "uem")
    # Un bruit ouvre l'enregistrement : l'UEM part du premier mot lexical.
    infos = [
        track("001", [{"start": 2.0, "end": 9.0, "words": [
            {"word": "*", "start": 2.0, "end": 3.0},
            {"word": "bon", "start": 5.0, "end": 6.0},
            {"word": "@", "start": 8.0, "end": 9.0},
        ]}]),
        track("002", [{"start": 6.0, "end": 7.0, "words": [{"word": "oui", "start": 6.0, "end": 7.0}]}]),
    ]
    fields = get_summre.write_reference("summre__x", infos, duration=20.0)
    assert (tmp_path / "uem" / "summre__x.uem").read_text() == "summre__x 1 4.000 8.000\n"
    assert (tmp_path / "rttm" / "summre__x.rttm").read_text() == (
        "SPEAKER summre__x 1 5.000 1.000 <NA> <NA> 001 <NA> <NA>\n"
        "SPEAKER summre__x 1 6.000 1.000 <NA> <NA> 002 <NA> <NA>\n"
    )
    assert fields["n_locuteurs"] == 2
    assert fields["n_mots"] == 4
    assert fields["n_jetons_non_lexicaux"] == 2
    assert fields["jetons_retires"] == "*:1;@:1"
    # Avec les jetons, dans l'UEM [4, 8] : 5–7 de parole lexicale, 8 exclu (borne de l'UEM).
    assert fields["parole_avec_jetons_non_lexicaux_s"] == pytest.approx(2.0)


def test_uem_premier_et_dernier_mot_bornes_au_signal():
    reference = {"001": [(0.4, 2.0)], "002": [(5.0, 9.5)]}
    assert get_summre.uem_bounds(reference, 10.0) == (0.0, 10.0)
    assert get_summre.uem_bounds({"001": [(3.0, 4.0)]}, 10.0) == (2.0, 5.0)


# --- Mélange ------------------------------------------------------------------------------


def test_melange_longueurs_differentes():
    a = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)
    b = np.array([1.0, -1.0], dtype=np.float32)
    mix = get_summre.mix_tracks([a, b])
    assert len(mix) == 4
    np.testing.assert_allclose(mix, [0.75, -0.25, 0.25, 0.25])


def test_melange_sans_ecretage():
    # Pistes à pleine échelle et en phase : la somme dépasse 1, la moyenne non.
    tracks = [np.ones(100, dtype=np.float32) * 0.99 for _ in range(4)]
    mix = get_summre.mix_tracks(tracks)
    assert float(np.max(np.abs(mix))) <= 1.0
    pcm = get_summre.to_pcm16(mix)
    assert pcm.dtype == np.int16 and int(pcm.max()) == round(0.99 * 32767)


def test_conversion_refuse_un_depassement():
    with pytest.raises(ValueError):
        get_summre.to_pcm16(np.array([0.0, 1.2], dtype=np.float32))


# --- Synchronisation ----------------------------------------------------------------------


@pytest.mark.parametrize("delay", [0, 40, -400])
def test_decalage_estime(delay):
    rng = np.random.default_rng(0)
    rate = 8000
    source = rng.standard_normal(rate * 4)
    shifted = np.roll(source, delay)
    lag, coefficient, salience = get_summre.estimate_lag(shifted, source, rate, 1.0)
    assert lag == pytest.approx(delay / rate)
    assert coefficient > 0.9
    assert salience >= get_summre.SYNC_MIN_SALIENCE


def test_decalage_non_mesurable_sans_diaphonie():
    rng = np.random.default_rng(1)
    rate = 8000
    lag, coefficient, salience = get_summre.estimate_lag(
        rng.standard_normal(rate * 20), rng.standard_normal(rate * 20), rate, 1.0
    )
    assert abs(coefficient) < 0.05
    assert salience < get_summre.SYNC_MIN_SALIENCE
    text = get_summre.format_lags({"001": (lag, coefficient, salience), "002": (0.012, 0.3, 40.0)})
    worst, unmeasured = get_summre.sync_summary(text)
    assert worst == pytest.approx(0.012)
    assert unmeasured == ["001"]


def test_code_de_lieu_zoom():
    assert get_summre.is_zoom("020b_EBDZ")
    assert not get_summre.is_zoom("007a_ECRH")
