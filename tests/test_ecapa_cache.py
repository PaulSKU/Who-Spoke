"""Emplacement des fichiers d'ECAPA (D17, amendement 1), sans modèle ni réseau.

Les fichiers sont lus en place dans le cache Hugging Face : jamais de `pretrained_models/`
dans le dossier de lancement.
"""

import pytest

from whospoke import embeddings


class Captured(Exception):
    pass


def test_options_de_chargement():
    from speechbrain.utils.fetching import LocalStrategy

    options = embeddings.ecapa_load_options()
    assert options["source"] == embeddings.ECAPA_SOURCE
    assert options["savedir"] is None
    assert options["local_strategy"] == LocalStrategy.NO_LINK
    assert options["fetch_config"].revision == embeddings.ECAPA_REVISION


def test_le_chargement_utilise_ces_options(tmp_path, monkeypatch):
    from speechbrain.inference.speaker import EncoderClassifier

    calls = []

    def fake_from_hparams(**kwargs):
        calls.append(kwargs)
        raise Captured

    monkeypatch.setattr(EncoderClassifier, "from_hparams", staticmethod(fake_from_hparams))
    monkeypatch.chdir(tmp_path)
    with pytest.raises(Captured):
        embeddings.SpeakerEmbedder("ecapa", device="cpu")
    assert calls[0]["savedir"] is None and calls[0]["run_opts"] == {"device": "cpu"}
    assert calls[0]["fetch_config"].revision == embeddings.ECAPA_REVISION


def test_lecture_en_place_sans_dossier_dans_le_repertoire_courant(tmp_path, monkeypatch):
    """Avec ces options, speechbrain renvoie le fichier là où il est (ici une source
    locale, à la place du cache) et ne crée rien dans le dossier courant."""
    from speechbrain.utils.fetching import fetch

    source = tmp_path / "cache"
    source.mkdir()
    (source / "hyperparams.yaml").write_text("modules: {}\n")
    launch = tmp_path / "lancement"
    launch.mkdir()
    monkeypatch.chdir(launch)
    options = embeddings.ecapa_load_options()
    path = fetch("hyperparams.yaml", source=str(source), savedir=options["savedir"],
                 local_strategy=options["local_strategy"])
    assert path.resolve() == (source / "hyperparams.yaml").resolve()
    assert list(launch.iterdir()) == []
