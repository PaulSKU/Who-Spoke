"""Cache des résultats (audit R-D3, chantier C5 ; app/cache.py), sans modèle ni réseau."""

import json

import numpy as np
import pytest
from pyannote.core import Annotation, Segment

from app import cache
from whospoke.experiment import REPO_ROOT

SETTINGS = {"peripherique": "cpu", "nombre_locuteurs": {"mode": "automatique"}, "parametres": {"theta": 0.5}}


def test_empreinte_des_echantillons():
    samples = np.linspace(-1, 1, 16000, dtype=np.float32)
    assert cache.audio_fingerprint(samples) == cache.audio_fingerprint(samples.copy())
    changed = samples.copy()
    changed[100] += 1e-3
    assert cache.audio_fingerprint(changed) != cache.audio_fingerprint(samples)


CONFIGURATION = {"regroupement": [{"nom": "theta", "valeur": 0.5, "origine": "experience"}]}
REVISIONS = {"pyannote/speaker-diarization-community-1": "3533c8cf8e369892e6b79ff1bf80f7b0286a54ee"}


def test_cle_sensible_a_chaque_composante():
    base = dict(fingerprint="a" * 64, engine="pyannote-community-1", fake=False, settings=SETTINGS,
                configuration=CONFIGURATION, revisions=REVISIONS)
    key = cache.result_key(**base)
    assert len(key) == 64 and key == cache.result_key(**base)
    # Ordre des clés des réglages sans effet ; toute composante changée donne une autre clé.
    assert cache.result_key(**dict(base, settings=dict(reversed(list(SETTINGS.items()))))) == key
    variants = [dict(base, fingerprint="b" * 64), dict(base, engine="baseline-ecapa"), dict(base, fake=True),
                dict(base, settings=dict(SETTINGS, peripherique="mps")),
                dict(base, settings=dict(SETTINGS, parametres={"theta": 0.6})),
                dict(base, settings=dict(SETTINGS, nombre_locuteurs={"mode": "impose", "valeur": 3})),
                dict(base, configuration={"regroupement": [{"nom": "theta", "valeur": 0.6}]}),
                dict(base, revisions={"pyannote/speaker-diarization-community-1": "0" * 40}), dict(base, revisions={})]
    assert len({cache.result_key(**v) for v in variants} | {key}) == len(variants) + 1


def test_le_commit_n_entre_pas_dans_la_cle():
    """Décision du cockpit du 01/11 : un commit de documents n'invalide pas le cache."""
    import inspect

    assert "code" not in inspect.signature(cache.result_key).parameters


def test_pistes_avec_chevauchement_restituees_a_l_identique():
    annotation = Annotation(uri="essai")
    annotation[Segment(0.0, 4.0), "a"] = "SPK_00"
    annotation[Segment(3.0, 5.5), "b"] = "SPK_01"
    annotation[Segment(3.5, 4.5), "c"] = "SPK_00"      # même locuteur, autre piste
    annotation[Segment(6.0, 7.0), 3] = "SPK_01"        # piste numérotée, comme load_rttm
    tracks = cache.annotation_tracks(annotation)
    restored = cache.annotation_from_tracks(json.loads(json.dumps(tracks)), "essai")
    assert restored == annotation and restored.uri == "essai"
    assert cache.annotation_tracks(restored) == tracks


def test_enregistrer_lire_vider(tmp_path):
    store = cache.ResultCache(tmp_path / "resultats")
    assert store.stats() == (0, 0) and store.get("0" * 64) is None and store.clear() == 0
    key = cache.result_key("a" * 64, "baseline-mfcc", True, SETTINGS, CONFIGURATION, {})
    path = store.put(key, {"pistes": [[0.0, 1.0, "0", "S0"]], "calcul_s": 1.5})
    assert path.parent == tmp_path / "resultats" and path.name == f"{key}.json"
    entry = store.get(key)
    assert entry["calcul_s"] == 1.5 and entry["version"] == cache.FORMAT_VERSION and entry["date"]
    (tmp_path / "resultats" / "autre.txt").write_text("à garder")
    count, size = store.stats()
    assert count == 1 and size > 0
    assert store.clear() == 1 and store.get(key) is None
    assert (tmp_path / "resultats" / "autre.txt").is_file()   # seuls les résultats sont supprimés


def test_entree_illisible_ou_d_un_autre_format_ignoree(tmp_path):
    store = cache.ResultCache(tmp_path)
    key = "c" * 64
    (tmp_path / f"{key}.json").write_text("{pas du json")
    assert store.get(key) is None
    (tmp_path / f"{key}.json").write_text(json.dumps({"version": 999}))
    assert store.get(key) is None


def test_cle_invalide_refusee(tmp_path):
    store = cache.ResultCache(tmp_path)
    for key in ("../x", "A" * 64, "a" * 63):
        with pytest.raises(ValueError):
            store.put(key, {})
        assert store.get(key) is None
    assert list(tmp_path.iterdir()) == []


def test_dossier_par_defaut_hors_du_depot(monkeypatch, tmp_path):
    monkeypatch.delenv("WHOSPOKE_CACHE_DIR", raising=False)
    default = cache.default_dir()
    assert default.parts[-3:] == (".cache", "whospoke", "resultats")
    assert not default.is_relative_to(REPO_ROOT)
    monkeypatch.setenv("WHOSPOKE_CACHE_DIR", str(tmp_path))
    assert cache.default_dir() == tmp_path / "resultats"


def test_version_du_code(tmp_path):
    version = cache.code_version(REPO_ROOT)
    assert version == "inconnu" or len(version.removesuffix("+modifie")) == 40
    assert cache.code_version(tmp_path) == "inconnu"   # hors dépôt git
