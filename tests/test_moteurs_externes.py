"""Moteurs externes en sous-processus : Nemotron 3 Diarization et DiariZen (chantier E4).

Aucun modèle : l'exécutant est simulé par un script de la bibliothèque standard, lancé
par l'interpréteur des tests, qui parle le vrai protocole (`runners/protocole.py`).
"""

import ast
import re
import sys
import wave

import numpy as np
import pytest
import torch

from whospoke.experiment import REPO_ROOT
from whospoke.pipelines import diarizen, externe, nemotron3
from whospoke.pipelines.base import ORIGINS, load_catalogue

SR = 16000
FAKE_RUNNER = '''
import json, os, sys, wave
sys.path.insert(0, {runners!r})
import protocole
protocole.disable_telemetry()


def load(config):
    print("bavardage d'une bibliothèque sur la sortie standard")
    if config.get("echec"):
        raise RuntimeError("modèle absent du cache")
    keys = ("HF_HUB_OFFLINE", "HF_TOKEN", "PYANNOTE_METRICS_ENABLED", "OTEL_SDK_DISABLED", "WANDB_MODE",
            "ONE_LOGGER_EXPORTER_CONFIG_PATH", "HF_HUB_DISABLE_TELEMETRY")
    configuration = {{"locuteurs_max": 8, "trame_s": 0.01, "mode": "hors ligne (is_streaming=False)"}}
    if "empreintes" in config:
        configuration = {{"inference": {{"seg_duration": 16, "segmentation_step": 0.1, "apply_median_filtering": True}},
                         "regroupement": {{"method": "VBxClustering", "min_speakers": 1, "max_speakers": 20,
                                           "ahc_threshold": 0.6, "Fa": 0.07, "Fb": 0.8}}}}
    return config, {{"versions": {{"python": "3.x", "torch": "simulé"}}, "configuration": configuration,
                    "env": {{key: os.environ.get(key) for key in keys}}, "cwd": os.getcwd(), "recue": config}}


def handle(config, request):
    if request["uri"] == "plante":
        raise ValueError("fichier illisible")
    if request["uri"] == "meurt":
        os._exit(3)
    with wave.open(request["entree"]) as handle:
        duration = handle.getnframes() / handle.getframerate()
    protocole.write_rttm(request["sortie"], request["uri"],
                         [(0.0, duration / 2, "SPK_00"), (duration / 2, duration, "SPK_01")])
    return {{"durees": {{"detection": 0.01}}, "n_trames": int(duration * 100),
            "n_locuteurs_bornes": [request.get("min_speakers"), request.get("max_speakers")]}}


protocole.serve(load, handle)
'''


@pytest.fixture
def runner(tmp_path):
    path = tmp_path / "executant_simule.py"
    path.write_text(FAKE_RUNNER.format(runners=str(externe.RUNNERS_DIR)))
    return path


def signal(seconds=4.0):
    rng = np.random.default_rng(0)
    return torch.from_numpy((0.1 * rng.standard_normal(int(seconds * SR))).astype(np.float32)).unsqueeze(0)


def check_catalogue(engine):
    entries = load_catalogue()["moteurs"][engine.name]
    names = set()
    for step, settings in engine.describe().items():
        assert step in load_catalogue()["etapes"], step
        for setting in settings:
            assert setting.name in entries, setting.name
            assert entries[setting.name]["etape"] == step, setting.name
            assert setting.origin in ORIGINS
            names.add(setting.name)
    assert names == set(entries)


def test_nemotron_au_contrat(runner, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_secret")
    monkeypatch.setenv("ONE_LOGGER_EXPORTER_CONFIG_PATH", "/tmp/exportateurs.yaml")
    monkeypatch.setenv("PYANNOTE_METRICS_ENABLED", "true")
    engine = nemotron3.Nemotron3Diarization(python=sys.executable, runner=runner)
    try:
        ready = engine.ready
        assert ready["recue"] == {"modele": nemotron3.MODEL_ID, "revision": nemotron3.MODEL_REVISION,
                                  "peripherique": "cpu", "seuil": 0.5}
        # D27 : hors ligne, télémétrie coupée, sans jeton, dans un dossier temporaire vide.
        assert ready["env"] == {"HF_HUB_OFFLINE": "1", "HF_TOKEN": None, "PYANNOTE_METRICS_ENABLED": "false",
                                "OTEL_SDK_DISABLED": "true", "WANDB_MODE": "disabled",
                                "ONE_LOGGER_EXPORTER_CONFIG_PATH": None, "HF_HUB_DISABLE_TELEMETRY": "1"}
        assert ready["cwd"] == str(engine._process.workdir.resolve()) and "chargement_s" in ready
        steps = []
        result = engine.run(signal(4.0), SR, uri="ami__essai", progress=lambda s, f: steps.append((s, f)))
        assert result.annotation.uri == "ami__essai" and sorted(result.annotation.labels()) == ["SPK_00", "SPK_01"]
        assert result.annotation.get_timeline().duration() == pytest.approx(4.0, abs=0.01)
        assert result.durees_etapes["detection"] == 0.01 and "sous_processus" in result.durees_etapes
        assert steps == [("detection", 0.0), ("detection", 1.0)]
        # Le modèle reste chargé : un second fichier passe par le même processus.
        assert engine.run(signal(2.0), SR, uri="b").annotation.get_timeline().duration() == pytest.approx(2.0, abs=0.01)
        check_catalogue(engine)
        settings = {s.name: s for step in engine.describe().values() for s in step}
        assert settings["nemotron.modele"].value == f"{nemotron3.MODEL_ID}@{nemotron3.MODEL_REVISION[:12]}"
        assert settings["nemotron.seuil"].origin == "defaut"
    finally:
        engine.close()
    assert engine._process.process is None


def test_nemotron_refuse_nombre_impose_et_parole_oracle(runner):
    with pytest.raises(ValueError, match="estime seul"):
        nemotron3.Nemotron3Diarization(python=sys.executable, runner=runner, speaker_mode="oracle")
    with pytest.raises(ValueError, match="cpu ou mps"):
        nemotron3.Nemotron3Diarization(python=sys.executable, runner=runner, device="cuda")
    engine = nemotron3.Nemotron3Diarization(python=sys.executable, runner=runner, threshold=0.4)
    try:
        with pytest.raises(ValueError, match="nombre de locuteurs imposé"):
            engine.run(signal(), SR, uri="a", num_speakers=3)
        from pyannote.core import Segment, Timeline
        with pytest.raises(ValueError, match="oracle"):
            engine.run(signal(), SR, uri="a", speech=Timeline([Segment(0, 1)]))
        assert {s.name: s.origin for s in engine.describe()["detection"]}["nemotron.seuil"] == "experience"
    finally:
        engine.close()


def test_diarizen_nombre_de_locuteurs(runner):
    estimated = diarizen.DiariZen(python=sys.executable, runner=runner)
    bounded = diarizen.DiariZen(python=sys.executable, runner=runner, min_speakers=2, max_speakers=6)
    try:
        assert estimated.ready["recue"]["revision_empreintes"] == diarizen.EMBEDDING_REVISION
        assert estimated.speaker_mode == "estime" and bounded.speaker_mode == "borne"
        assert estimated.run(signal(), SR, uri="a").infos["n_locuteurs_bornes"] == [None, None]
        assert estimated.run(signal(), SR, uri="a", num_speakers=3).infos["n_locuteurs_bornes"] == [3, 3]
        assert bounded.run(signal(), SR, uri="a").infos["n_locuteurs_bornes"] == [2, 6]
        check_catalogue(estimated)
        settings = {s.name: s.value for step in bounded.describe().values() for s in step}
        assert settings["diarizen.n_locuteurs"] == "borne [2, 6]"
        assert settings["diarizen.regroupement"] == "VBxClustering"
        assert settings["diarizen.code"].endswith(diarizen.CODE_COMMIT[:12])
        assert "estimé (entre 1 et 20)" in {s.value for s in estimated.describe()["regroupement"]}
    finally:
        estimated.close()
        bounded.close()


def test_erreurs_de_l_executant(runner, tmp_path):
    with pytest.raises(externe.ExternalError, match="chargement : RuntimeError: modèle absent du cache"):
        externe.ExternalProcess([sys.executable, runner, '{"echec": true}'])
    process = externe.ExternalProcess([sys.executable, runner, "{}"])
    try:
        wav = externe.write_wav(process.workdir / "a.wav", np.zeros(SR, dtype=np.float32))
        with pytest.raises(externe.ExternalError, match="traitement : ValueError: fichier illisible"):
            process.request({"entree": str(wav), "sortie": str(tmp_path / "x.rttm"), "uri": "plante"})
        # L'exécutant survit à une erreur de traitement…
        assert process.request({"entree": str(wav), "sortie": str(tmp_path / "x.rttm"), "uri": "ok"})["ok"]
        # … mais pas à sa propre mort, signalée avec son code de sortie.
        with pytest.raises(externe.ExternalError, match="code 3"):
            process.request({"entree": str(wav), "sortie": str(tmp_path / "x.rttm"), "uri": "meurt"})
        with pytest.raises(externe.ExternalError, match="déjà arrêté"):
            process.request({"uri": "ok"})
    finally:
        workdir = process.workdir
        process.close()
    assert not workdir.exists()


def test_environnement_absent(tmp_path):
    with pytest.raises(externe.EnvironmentMissing, match="scripts/envs/nemotron.sh"):
        externe.env_python("nemotron", root=tmp_path)


def test_wav_sans_perte(tmp_path):
    pcm = np.array([-32768, -1, 0, 1, 12345, 32767], dtype=np.int16)
    path = externe.write_wav(tmp_path / "a.wav", pcm.astype(np.float32) / 32768.0)
    with wave.open(str(path)) as handle:
        assert (handle.getframerate(), handle.getnchannels(), handle.getsampwidth()) == (SR, 1, 2)
        assert np.array_equal(np.frombuffer(handle.readframes(6), dtype="<i2"), pcm)


@pytest.mark.parametrize("name", ["protocole.py", "executant_nemotron3.py", "executant_diarizen.py"])
def test_executants_sans_import_tiers_au_chargement(name):
    """Les exécutants tournent sous Python 3.10 à 3.12 sans le paquet whospoke : au niveau du
    module, bibliothèque standard et `protocole` seulement ; les bibliothèques lourdes sont
    importées dans `load`."""
    tree = ast.parse((externe.RUNNERS_DIR / name).read_text(), feature_version=(3, 10))
    for node in tree.body:
        if isinstance(node, ast.Import | ast.ImportFrom):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module]
            for module in modules:
                assert module.split(".")[0] in sys.stdlib_module_names | {"protocole", "__future__"}, (name, module)


def test_revisions_des_scripts_d_installation():
    nemotron_sh = (REPO_ROOT / "scripts" / "envs" / "nemotron.sh").read_text()
    diarizen_sh = (REPO_ROOT / "scripts" / "envs" / "diarizen.sh").read_text()
    assert re.search(rf"^REVISION={nemotron3.MODEL_REVISION}\b", nemotron_sh, re.M)
    assert re.search(rf"^CODE_COMMIT={diarizen.CODE_COMMIT}\b", diarizen_sh, re.M)
    assert re.search(rf"^MODEL_REVISION={diarizen.MODEL_REVISION}\b", diarizen_sh, re.M)
    assert re.search(rf"^EMBEDDING_REVISION={diarizen.EMBEDDING_REVISION}\b", diarizen_sh, re.M)
    pinned = (REPO_ROOT / "scripts" / "envs" / "nemotron.txt").read_text()
    assert re.search(r"^transformers==5\.(1[89]|[2-9]\d)\.", pinned, re.M)   # nemotron3_diarization depuis 5.18


def test_executants_ne_masquent_pas_les_paquets_des_moteurs():
    """Le dossier d'un exécutant est en tête de sys.path : un fichier `diarizen.py` y masquerait
    le paquet `diarizen` (erreur trouvée au premier lancement réel, 01/11)."""
    names = {path.stem for path in externe.RUNNERS_DIR.glob("*.py")}
    assert names == {"protocole", "executant_nemotron3", "executant_diarizen"}
