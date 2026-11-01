"""Détection fine par Silero VAD en post-traitement (D25, V2 et V3 ; chantier E5).

silero-vad n'est pas encore dans uv.lock : le modèle et la binarisation de Silero sont
simulés (énergie de la fenêtre, seuil simple). Aucun modèle n'est chargé.
"""

import importlib
import json
import math
import sys

import numpy as np
import pytest
import torch
from pyannote.core import Annotation, Segment, Timeline
from scipy.io import wavfile

from whospoke.evaluation.metrics import DiarizationEvaluator
from whospoke.experiment import REPO_ROOT
from whospoke.pipelines import silero
from whospoke.pipelines.base import ORIGINS, Engine, Resultat, Setting, load_catalogue

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import reglage_silero  # noqa: E402

SR = 16000


class FakeModel:
    """Probabilité de parole = énergie de la fenêtre (le vrai modèle est un réseau récurrent)."""

    def __init__(self):
        self.resets = 0
        self.calls = 0
        self.threads = set()

    def reset_states(self):
        self.resets += 1

    def __call__(self, chunk, sample_rate):
        assert chunk.shape == (silero.WINDOW,) and sample_rate == SR
        self.calls += 1
        self.threads.add(torch.get_num_threads())
        return torch.tensor(min(1.0, 10.0 * float(chunk.pow(2).mean().sqrt())))


def fake_binarize(speech_probs, sampling_rate, threshold, min_silence_duration_ms, speech_pad_ms,
                  min_speech_duration_ms, audio_length_samples, return_seconds, calls=None):
    """Binarisation simplifiée au format de get_speech_timestamps_from_probs (échantillons)."""
    if calls is not None:
        calls.append(dict(threshold=threshold, min_silence_duration_ms=min_silence_duration_ms,
                          speech_pad_ms=speech_pad_ms, min_speech_duration_ms=min_speech_duration_ms))
    assert sampling_rate == SR and return_seconds is False
    w = silero.WINDOW
    runs, start = [], None
    for i, p in enumerate([*speech_probs, 0.0]):
        if p >= threshold and start is None:
            start = i
        elif p < threshold and start is not None:
            runs.append([start * w, min(i * w, audio_length_samples)])
            start = None
    merged = []
    for run in runs:
        if merged and run[0] - merged[-1][1] < SR * min_silence_duration_ms / 1000:
            merged[-1][1] = run[1]
        else:
            merged.append(run)
    pad = int(SR * speech_pad_ms / 1000)
    return [{"start": max(0, s - pad), "end": min(audio_length_samples, e + pad)} for s, e in merged
            if e - s >= SR * min_speech_duration_ms / 1000]


def annotation(uri, turns):
    result = Annotation(uri=uri)
    for index, (start, end, label) in enumerate(turns):
        result[Segment(start, end), index] = label
    return result


def signal_with_speech(seconds, speech, seed=0):
    """Bruit fort dans les zones de parole, presque nul ailleurs."""
    rng = np.random.default_rng(seed)
    x = 0.001 * rng.standard_normal(int(seconds * SR))
    for start, end in speech:
        x[int(start * SR):int(end * SR)] = 0.3 * rng.standard_normal(int(end * SR) - int(start * SR))
    return x.astype(np.float32)


# --- Masque et intersection ---------------------------------------------------------


def test_reglages_transmis_a_silero():
    params = silero.MaskParams(seuil=0.6, silence_min_s=0.2, marge_s=0.03)
    # La marge est déduite : un silence rouvert dure au moins silence_min_s.
    assert params.silero_kwargs() == {"threshold": 0.6, "min_silence_duration_ms": 260, "speech_pad_ms": 30,
                                      "min_speech_duration_ms": 250}
    for bad in ({"seuil": 1.0}, {"seuil": 0.0}, {"marge_s": -0.1}, {"silence_min_s": -1}):
        with pytest.raises(ValueError):
            silero.MaskParams(**bad)


def test_masque_en_secondes():
    calls = []
    probs = np.array([0.9] * 10 + [0.1] * 20 + [0.9] * 10, dtype=np.float32)   # 32 ms par fenêtre
    mask = silero.speech_mask(probs, 40 * silero.WINDOW, silero.MaskParams(silence_min_s=0.2, marge_s=0.0),
                              lambda *a, **k: fake_binarize(*a, **k, calls=calls), uri="a")
    assert calls[0]["min_silence_duration_ms"] == 200
    assert [(round(s.start, 3), round(s.end, 3)) for s in mask] == [(0.0, 0.32), (0.96, 1.28)]
    assert mask.uri == "a"
    # Silence de 0,64 s plus court que silence_min_s : non rouvert.
    closed = silero.speech_mask(probs, 40 * silero.WINDOW, silero.MaskParams(silence_min_s=1.0, marge_s=0.0), fake_binarize)
    assert len(closed) == 1 and closed[0].end == pytest.approx(1.28)


def test_rouvre_une_pause_pontee_sans_creer_de_parole():
    hypothesis = annotation("a", [(0, 10, "A"), (8, 12, "B"), (20, 25, "A")])
    mask = Timeline([Segment(0, 4), Segment(5, 9), Segment(11, 30)])
    refined = silero.refine(hypothesis, mask)
    assert refined.uri == "a"
    assert [(s.start, s.end) for s in refined.label_timeline("A")] == [(0, 4), (5, 9), (20, 25)]
    # Chevauchement gardé là où le masque le permet.
    assert [(s.start, s.end) for s in refined.label_timeline("B")] == [(8, 9), (11, 12)]
    assert silero.removed_speech_s(hypothesis, refined) == pytest.approx(3.0)   # 4-5 et 9-11


def test_ne_cree_jamais_de_parole_ni_de_locuteur():
    rng = np.random.default_rng(1)
    for _ in range(50):
        turns = []
        for _ in range(rng.integers(1, 12)):
            start = float(rng.uniform(0, 60))
            turns.append((start, start + float(rng.uniform(0.1, 8)), f"S{rng.integers(0, 4)}"))
        hypothesis = annotation("x", turns)
        mask = Timeline([Segment(s, s + float(rng.uniform(0.05, 5))) for s in rng.uniform(0, 60, rng.integers(0, 15))]).support()
        refined = silero.refine(hypothesis, mask)
        assert set(refined.labels()) <= set(hypothesis.labels())
        for label in refined.labels():
            after, before = refined.label_timeline(label), hypothesis.label_timeline(label)
            assert after.support().duration() <= before.support().duration() + 1e-9
            assert after.crop(before, mode="intersection").duration() == pytest.approx(after.duration())
            assert after.crop(mask, mode="intersection").duration() == pytest.approx(after.duration())
        # Tout ce qui reste dans le masque est conservé.
        kept = hypothesis.crop(mask, mode="intersection")
        assert refined.get_timeline().support().duration() == pytest.approx(kept.get_timeline().support().duration())


def test_probabilites_comme_get_speech_timestamps():
    model = FakeModel()
    original = torch.get_num_threads()
    torch.set_num_threads(3)
    try:
        x = torch.from_numpy(signal_with_speech(1.0, [(0.5, 1.0)])).unsqueeze(0)
        steps = []
        probs = silero.speech_probabilities(model, x, progress=steps.append)
        assert torch.get_num_threads() == 3        # rétabli après le calcul
    finally:
        torch.set_num_threads(original)
    assert len(probs) == math.ceil(SR / silero.WINDOW) == model.calls and model.resets == 1
    assert model.threads == {1}
    assert probs.dtype == np.float32 and probs[:10].max() < 0.1 and probs[20:].min() > 0.9
    assert steps[-1] == 1.0


# --- Chargement de Silero -----------------------------------------------------------


def test_silero_absent(monkeypatch):
    monkeypatch.setitem(sys.modules, "silero_vad", None)
    with pytest.raises(silero.SileroMissing, match="uv add silero-vad==6.2.3"):
        silero.load_model()
    with pytest.raises(silero.SileroMissing, match="uv add"):
        silero.load_binarize()


def test_version_empreinte_et_fils_de_torch(tmp_path, monkeypatch):
    """Un faux paquet silero_vad qui, comme le vrai, impose un fil à l'import. Un dossier
    par version : réécrit sur place dans la même seconde et à taille égale, le module
    serait relu depuis son bytecode périmé."""
    real = {name: module for name, module in sys.modules.items() if name.startswith("silero_vad")}
    before = torch.get_num_threads()
    try:
        for version, error in (("5.1.2", "5.1.2 installé"), ("6.2.3", "empreinte")):
            package = tmp_path / version / "silero_vad"
            (package / "data").mkdir(parents=True)
            (package / "data" / "__init__.py").write_text("")
            (package / "data" / silero.MODEL_FILE).write_bytes(b"autres poids")
            (package / "__init__.py").write_text(
                f"import torch\ntorch.set_num_threads(1)\n__version__ = {version!r}\n"
                "def get_speech_timestamps_from_probs(*a, **k):\n    return []\n"
                "def load_silero_vad(onnx=False):\n    return 'modele'\n")
            monkeypatch.syspath_prepend(str(tmp_path / version))
            for name in [m for m in sys.modules if m.startswith("silero_vad")]:
                del sys.modules[name]
            importlib.invalidate_caches()
            with pytest.raises(silero.SileroMissing, match=error):
                silero.load_model()
            assert torch.get_num_threads() == before
        assert silero.load_binarize()([]) == []
    finally:
        # Le faux paquet ne doit pas rester importé pour les tests suivants.
        for name in [m for m in sys.modules if m.startswith("silero_vad")]:
            del sys.modules[name]
        sys.modules.update(real)
        importlib.invalidate_caches()


def test_cache_des_probabilites(tmp_path):
    path = silero.cache_path("summre", "summre__x", root=tmp_path)
    assert path.relative_to(tmp_path).parts[:4] == ("processed", "summre", "silero", silero.CACHE_TAG)
    probs = np.linspace(0, 1, 32, dtype=np.float32)
    silero.save_probabilities(path, probs, 32 * silero.WINDOW - 100)
    loaded, n = silero.load_probabilities(path)
    assert np.array_equal(loaded, probs) and n == 32 * silero.WINDOW - 100
    silero.save_probabilities(path, probs, 40 * silero.WINDOW)
    with pytest.raises(ValueError, match="probabilités pour"):
        silero.load_probabilities(path)


# --- Moteur composé -----------------------------------------------------------------


class FakeInner(Engine):
    name = "pyannote-community-1"

    def __init__(self, turns, trace=False):
        super().__init__(trace=trace)
        self.turns = turns
        self.device = torch.device("cpu")
        self.received = None

    def run(self, waveform, sample_rate=SR, uri=None, num_speakers=None, speech=None, progress=None):
        self.received = {"num_speakers": num_speakers, "speech": speech}
        if progress:
            progress("segmentation", 1.0)
        result = Resultat(annotation(uri, self.turns), {"segmentation": 0.5})
        result.autres_sorties = {"exclusive": annotation(uri, [(0, 3, "A"), (3, 6, "B")])}
        return result

    def describe(self):
        return {"detection": [Setting("segmentation.modele", "pyannote/segmentation", "modele")],
                "regroupement": [Setting("clustering.threshold", 0.6, "modele")]}


def test_moteur_compose():
    inner = FakeInner([(0.0, 6.0, "A"), (4.5, 6.0, "B")])
    engine = silero.SileroRefinement(inner, seuil=0.5, marge_s=0.0, model=FakeModel(), binarize=fake_binarize)
    assert engine.name == "pyannote-community-1-silero" == silero.pyannote_silero.name
    assert engine.device == inner.device and engine.speaker_mode == "estime"
    engine.trace = True
    assert inner.trace is True
    x = torch.from_numpy(signal_with_speech(6.0, [(0.0, 2.0), (3.0, 6.0)])).unsqueeze(0)
    steps = []
    result = engine.run(x, SR, uri="r", num_speakers=2, progress=lambda s, f: steps.append(s))
    assert inner.received == {"num_speakers": 2, "speech": None}
    assert steps[0] == "detection" and steps[-1] == "segmentation"   # Silero avant le moteur suivi
    a = result.annotation.label_timeline("A")
    assert len(a) == 2 and a[0].end == pytest.approx(2.0, abs=0.04) and a[1].start == pytest.approx(3.0, abs=0.04)
    assert result.annotation.label_timeline("B").duration() == pytest.approx(1.5, abs=0.04)
    # La sortie exclusive du moteur suivi reçoit le même masque (V3).
    assert result.autres_sorties["exclusive"].get_timeline().support().duration() == pytest.approx(5.0, abs=0.08)
    assert result.infos["silero"]["parole_retiree_s"] == pytest.approx(1.0, abs=2 * silero.FRAME_S)   # fenêtres de 32 ms
    assert set(result.durees_etapes) == {"segmentation", "detection_fine"}
    with pytest.raises(ValueError, match="oracle"):
        engine.run(x, SR, uri="r", speech=Timeline([Segment(0, 1)]))


def test_reglages_du_moteur_compose_au_catalogue():
    catalogue = load_catalogue()
    entries = catalogue["moteurs"]["pyannote-community-1-silero"]
    pyannote = catalogue["moteurs"]["pyannote-community-1"]
    assert {k: v for k, v in entries.items() if k in pyannote} == pyannote   # entrées reprises à l'identique
    engine = silero.SileroRefinement(FakeInner([]), silence_min_s=0.4, model=FakeModel(), binarize=fake_binarize)
    described = engine.describe()
    assert [s.name for s in described["regroupement"]] == ["clustering.threshold"]
    added = {s.name: s for s in described["detection"] if s.name.startswith("silero.")}
    assert set(added) == set(entries) - set(pyannote)
    for setting in added.values():
        assert entries[setting.name]["etape"] == "detection" and setting.origin in ORIGINS
    assert added["silero.silence_min_s"].origin == "experience" and added["silero.seuil"].origin == "defaut"
    assert added["silero.modele"].value.startswith("silero-vad==6.2.3@e1122837f415")


# --- Script de réglage --------------------------------------------------------------

REFERENCE = [(0.0, 4.0, "A"), (6.0, 10.0, "A"), (10.0, 14.0, "B")]
BRIDGED = [(0.0, 10.0, "spk0"), (10.0, 14.0, "spk1")]          # pause 4-6 pontée


def write_rttm(path, uri, turns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        annotation(uri, turns).write_rttm(handle)


@pytest.fixture
def depot(tmp_path):
    """Dépôt miniature : deux fichiers SUMM-RE dev, références, UEM, audio et deux sources."""
    uris = ["summre__d1", "summre__d2"]
    (tmp_path / "data/splits/summre/uem").mkdir(parents=True)
    (tmp_path / "data/splits/summre/dev.txt").write_text("\n".join(uris) + "\n")
    evaluator = {"v2": DiarizationEvaluator(), "v3": DiarizationEvaluator()}
    for index, uri in enumerate(uris):
        (tmp_path / f"data/splits/summre/uem/{uri}.uem").write_text(f"{uri} 1 0.000 14.000\n")
        write_rttm(tmp_path / f"data/processed/summre/rttm/{uri}.rttm", uri, REFERENCE)
        pcm = (signal_with_speech(14.0, [(0, 4), (6, 14)], seed=index) * 32767).astype(np.int16)
        wavfile.write(tmp_path / f"data/processed/summre/{uri}.wav", SR, pcm)
        write_rttm(tmp_path / f"experiments/EXP-A/rttm/{uri}.rttm", uri, BRIDGED)
        write_rttm(tmp_path / f"experiments/EXP-B/rttm/{uri}.rttm", uri, BRIDGED)
        reference = annotation(uri, REFERENCE)
        uem = Timeline([Segment(0, 14)], uri=uri)
        for name in evaluator:
            evaluator[name].add(reference, annotation(uri, BRIDGED), uem)
    # DER consignés par l'évaluateur officiel : le script doit les retrouver.
    for name, exp in (("v2", "EXP-A"), ("v3", "EXP-B")):
        report = evaluator[name].report()
        metriques = {c: {"der": round(report[c]["der"], 2)} for c in ("collar_0", "collar_0_25")}
        (tmp_path / f"experiments/{exp}/results_summre_dev.json").write_text(json.dumps({"metriques": metriques}))
    return tmp_path


def run_script(depot, *extra, model_loader=None):
    loader = model_loader or (lambda: (FakeModel(), fake_binarize))
    return reglage_silero.main(["--racine", str(depot), "--source-v2", "experiments/EXP-A",
                                "--source-v3", "experiments/EXP-B", "--seuils", "0.5,0.9",
                                "--silences", "0.2,3.0", "--marges", "0.0", *extra],
                               model_loader=loader, binarize=fake_binarize)


def test_reglage_de_bout_en_bout(depot, capsys):
    assert run_script(depot, "--probabilites") == 0
    cache = sorted((depot / "data/processed/summre/silero" / silero.CACHE_TAG).glob("*.npz"))
    assert [p.stem for p in cache] == ["summre__d1", "summre__d2"]

    def no_model():
        raise AssertionError("le cache aurait dû suffire")

    out = depot / "results" / "essai"
    assert run_script(depot, "--sortie", str(out), model_loader=no_model) == 0
    summary = json.loads((out / "reglage.json").read_text())
    assert summary["controle_sources"]["v2"]["conforme"] is True
    assert summary["silero"]["lus_en_cache"] == 2 and summary["silero"]["calcules"] == []
    assert len(summary["grille"]) == 4
    source = summary["sources_evaluees"]["v2"]["metriques"]["collar_0"]
    best = summary["v2_retenue"]
    # La pause pontée (2 s sur 12 s de parole) est rouverte : fausse alarme retirée.
    assert source["fausse_alarme"] == pytest.approx(100 * 2 / 12, abs=0.01)
    assert best["reglage"]["silence_min_s"] == 0.2
    assert best["metriques"]["collar_0"]["fausse_alarme"] < 2.0 < source["fausse_alarme"]
    assert best["parole_retiree_s"] == pytest.approx(4.0, abs=0.2)          # 2 s par fichier
    # Silence minimal de 3 s : la pause de 2 s reste pontée.
    unchanged = [r for r in summary["grille"] if r["reglage"]["silence_min_s"] == 3.0 and r["reglage"]["seuil"] == 0.5]
    assert unchanged[0]["metriques"]["collar_0"]["der"] == pytest.approx(source["der"], abs=0.5)
    assert summary["v3"]["reglage"] == best["reglage"]
    assert summary["choix"]["alerte"] is None
    rows = (out / "grille.csv").read_text().splitlines()
    assert len(rows) == 5 and rows[0].startswith("seuil,silence_min_s,marge_s,parole_retiree_s,der_c0")
    text = (out / "reglage.md").read_text()
    assert "**V2 retenue**" in text and "**V3** (réglage de V2)" in text and "| 0,5 | 0,2 | 0,0 |" in text
    assert run_script(depot, "--sortie", str(out)) == 1                       # sortie non vide : refus
    assert "n'est pas vide" in capsys.readouterr().out


def test_reglage_refuse_une_source_non_reproduite(depot, capsys):
    path = depot / "experiments/EXP-A/results_summre_dev.json"
    data = json.loads(path.read_text())
    data["metriques"]["collar_0"]["der"] += 1.0
    path.write_text(json.dumps(data))
    assert run_script(depot) == 1
    assert "NON REPRODUIT" in capsys.readouterr().out
    assert not (depot / "results").exists()


def test_reglage_sans_silero(depot, capsys):
    def missing():
        raise silero.SileroMissing(f"silero-vad absent de l'environnement ({silero.INSTALL_HINT})")

    assert reglage_silero.main(["--racine", str(depot), "--source-v2", "experiments/EXP-A",
                                "--source-v3", "aucune"], model_loader=missing) == 1
    assert "uv add silero-vad==6.2.3" in capsys.readouterr().out


# --- Silero réel (après `uv add silero-vad==6.2.3` ; ignorés tant qu'il est absent) ---


def test_binarisation_reelle_de_silero():
    """Sens des réglages avec la vraie fonction de Silero (sans modèle) : un silence n'est
    rouvert que s'il dure au moins silence_min_s, marge déduite, à une fenêtre près."""
    pytest.importorskip("silero_vad")
    binarize = silero.load_binarize()
    w = silero.FRAME_S
    probs = np.array([0.9] * 31 + [0.05] * 12 + [0.9] * 31 + [0.05] * 4 + [0.9] * 20, dtype=np.float32)
    n = len(probs) * silero.WINDOW

    def gaps(params):
        mask = silero.speech_mask(probs, n, params, binarize)
        return [mask[i + 1].start - mask[i].end for i in range(len(mask) - 1)]

    assert gaps(silero.MaskParams(0.5, 0.2, 0.0)) == [pytest.approx(12 * w)]       # 0,384 s rouvert, 0,128 s non
    assert gaps(silero.MaskParams(0.5, 0.2, 0.03)) == [pytest.approx(12 * w - 0.06)]
    assert gaps(silero.MaskParams(0.5, 0.5, 0.0)) == []


@pytest.mark.modele
def test_modele_reel_de_silero():
    """Version, empreinte et probabilités du vrai modèle sur un signal synthétique."""
    pytest.importorskip("silero_vad")
    before = torch.get_num_threads()
    model, _ = silero.load_model()
    assert torch.get_num_threads() == before
    x = torch.from_numpy(signal_with_speech(2.0, [])).unsqueeze(0)
    probs = silero.speech_probabilities(model, x)
    assert len(probs) == math.ceil(2 * SR / silero.WINDOW) and probs.max() < 0.5    # bruit très faible
