"""Révisions figées des modèles (D18, amendement du 01/11), sans charger de modèle."""

import pytest

from whospoke import embeddings
from whospoke.pipelines import pyannote_community1 as wrapper


class Captured(Exception):
    pass


def test_pyannote_et_wespeaker_au_meme_instantane():
    assert wrapper.MODEL_REVISION == embeddings.WESPEAKER_REVISION
    assert embeddings.WESPEAKER_SOURCE == wrapper.MODEL_ID
    for revision in (wrapper.MODEL_REVISION, embeddings.ECAPA_REVISION):
        assert len(revision) == 40 and int(revision, 16) >= 0   # commit complet, jamais « main »


def test_pipeline_chargee_a_la_revision_figee(monkeypatch):
    from pyannote.audio import Pipeline

    calls = []

    def fake_from_pretrained(checkpoint, **kwargs):
        calls.append((checkpoint, kwargs))
        raise Captured

    monkeypatch.setattr(Pipeline, "from_pretrained", staticmethod(fake_from_pretrained))
    monkeypatch.setenv("HF_TOKEN", "hf_jeton_de_test")
    with pytest.raises(Captured):
        wrapper.PyannoteCommunity1(device="cpu")
    checkpoint, kwargs = calls[0]
    assert checkpoint == wrapper.MODEL_ID and kwargs["revision"] == wrapper.MODEL_REVISION


def test_revision_consignee_dans_la_valeur_du_modele():
    """Forme des sous-modèles transmise par pyannote quand une révision est donnée."""
    spec = {"checkpoint": wrapper.MODEL_ID, "subfolder": "segmentation", "revision": wrapper.MODEL_REVISION}
    assert wrapper._checkpoint(spec) == f"{wrapper.MODEL_ID}/segmentation@{wrapper.MODEL_REVISION}"
