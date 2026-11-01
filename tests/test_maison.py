"""Chaîne du corpus maison (chantier E2), sur signaux de synthèse uniquement.

Une « réunion » de 40 s : trois voix (harmoniques modulées en amplitude), un claquement
au début et à la fin. Le signal de table les mélange ; chaque piste d'aide entend sa
voix à 0 dB et les autres à −10 dB, avec son propre gain, son propre bruit et sa propre
réponse au claquement, puis passe sur l'horloge de son téléphone (décalage et dérive
connus). Aucun audio réel, aucun modèle.
"""

import importlib.util
import json
import shutil

import numpy as np
import pytest
from scipy.io import wavfile

from whospoke.experiment import REPO_ROOT
from whospoke.maison import preannotation as pre
from whospoke.maison import reference as ref
from whospoke.maison import synchro

SR = 16000
DURATION = 40.0
CLAPS = (2.0, 37.0)
TURNS = [("S1", 4.0, 7.0), ("S2", 7.5, 10.0), ("S3", 10.3, 13.0), ("S1", 13.5, 15.0), ("S2", 16.0, 20.0),
         ("S3", 20.5, 23.0), ("S1", 24.0, 27.0), ("S2", 28.0, 30.0), ("S3", 31.0, 34.0)]
F0 = {"S1": 110.0, "S2": 180.0, "S3": 240.0}
# Horloge de chaque téléphone : temps_aide = décalage + rapport × temps_table.
CLOCKS = {"S1": (3.2, 1 + 250e-6), "S2": (-1.1, 1 - 400e-6), "S3": (0.45, 1.0)}
GAINS = {"S1": 1.0, "S2": 0.4, "S3": 2.0}
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")


def load_script(name, relative):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


maison = load_script("maison", "scripts/data/maison.py")


def voice(f0, n, rng):
    t = np.arange(n) / SR
    wobble = 1 + 0.02 * np.sin(2 * np.pi * 0.7 * t + rng.uniform(0, 6))
    phase = 2 * np.pi * f0 * np.cumsum(wobble) / SR
    signal = sum(np.sin(k * phase + rng.uniform(0, 6)) / k for k in range(1, 12))
    return signal * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * t + rng.uniform(0, 6)))


def bursts(seed=99):
    """Un même claquement (source) par instant, entendu par tous les appareils."""
    rng = np.random.default_rng(seed)
    n = int(0.03 * SR)
    return [rng.standard_normal(n) * np.exp(-np.arange(n) / (0.004 * SR)) for _ in CLAPS]


def heard(burst, rng):
    """Le claquement à travers la réponse propre à un appareil : trajet direct, puis réflexions."""
    m = int(0.01 * SR)
    response = 0.5 * rng.standard_normal(m) * np.exp(-np.arange(m) / (0.002 * SR))
    response[0] = 4.0
    return np.convolve(burst, response)[:len(burst)] / 4.0


def sources(turns=TURNS, seed=0):
    """Voix de chaque locuteur sur l'axe de temps de la table (s'ignorent hors de leurs tours)."""
    rng = np.random.default_rng(seed)
    n = int(DURATION * SR)
    voices = {code: np.zeros(n) for code in F0}
    for code, start, end in turns:
        a, b = int(start * SR), int(end * SR)
        voices[code][a:b] += 0.25 * voice(F0[code], b - a, rng)
    return voices


def add_claps(signal, rng, level):
    for instant, burst in zip(CLAPS, bursts()):
        sound = heard(burst, rng)
        a = int(instant * SR)
        signal[a:a + len(sound)] += level * sound
    return signal


def meeting(turns=TURNS, seed=0):
    """(table, {code: piste d'aide sur l'axe de la table}, {code: piste sur l'horloge du téléphone})."""
    voices = sources(turns, seed)
    rng = np.random.default_rng(seed + 1)
    n = len(voices["S1"])
    table = sum(0.5 * v for v in voices.values()) + 0.002 * rng.standard_normal(n)
    table = add_claps(table, rng, 0.8)
    on_table_axis, on_phone = {}, {}
    for code in F0:
        track = sum(v if other == code else 10 ** (-10 / 20) * v for other, v in voices.items())
        track = add_claps(track + 0.002 * rng.standard_normal(n), rng, 0.8)
        track = GAINS[code] * track / 2.5
        on_table_axis[code] = track
        offset, ratio = CLOCKS[code]
        length = int((offset + ratio * DURATION) * SR) if offset < 0 else int((DURATION + offset) * SR)
        phone_times = np.arange(length) / SR
        table_times = (phone_times - offset) / ratio
        on_phone[code] = np.interp(table_times * SR, np.arange(n), track, left=0.0, right=0.0)
    return table, on_table_axis, on_phone


def truth_labels(turns=TURNS):
    return {code: [(a, b) for c, a, b in turns if c == code] for code in F0}


def frame_agreement(found, expected, start, end, guard=0.06, step=0.01):
    """Part des instants (hors ±`guard` autour d'une frontière) où le locuteur trouvé est le bon."""
    def who(speakers, t):
        names = [code for code, intervals in speakers.items() if any(a <= t < b for a, b in intervals)]
        return names[0] if names else None

    edges = [x for intervals in expected.values() for interval in intervals for x in interval]
    times = [t for t in np.arange(start, end, step) if all(abs(t - e) > guard for e in edges)]
    return np.mean([who(found, t) == who(expected, t) for t in times])


# --- Fusion, étiquettes, UEM, RTTM ------------------------------------------------------


def test_fusion_a_200_ms():
    assert ref.merge_intervals([(0.0, 1.0), (1.2, 2.0)]) == [(0.0, 2.0)]
    assert ref.merge_intervals([(0.0, 1.0), (1.201, 2.0)]) == [(0.0, 1.0), (1.201, 2.0)]
    assert ref.merge_intervals([(1.0, 3.0), (0.0, 1.5), (2.0, 2.5)]) == [(0.0, 3.0)]


def test_meme_fusion_que_summre():
    get_summre = load_script("get_summre", "scripts/data/get_summre.py")
    rng = np.random.default_rng(3)
    for _ in range(50):
        starts = np.round(rng.uniform(0, 30, 20), 3)
        intervals = [(float(s), float(s + d)) for s, d in zip(starts, np.round(rng.uniform(0.05, 1.5, 20), 3))]
        assert ref.merge_intervals(intervals) == get_summre.merge_intervals(intervals)


def test_lecture_des_etiquettes_audacity(tmp_path):
    path = tmp_path / "M01_S2.txt"
    path.write_text("1.500000\t2.250000\tS2\n\\\t100.0\t2000.0\n3,5\t4,0\t\n\n5.0\t6.0\tà vérifier : S1 ou S2\n")
    assert ref.read_labels(path) == [(1.5, 2.25, "S2"), (3.5, 4.0, ""), (5.0, 6.0, "à vérifier : S1 ou S2")]
    path.write_text("2.0\t1.0\tS1\n")
    with pytest.raises(ref.LabelError, match="ligne 1"):
        ref.read_labels(path)


def test_ecriture_relue(tmp_path):
    labels = [(0.25, 1.0, "S1"), (2.0, 3.123456, "S3")]
    ref.write_labels(tmp_path / "S1.txt", labels)
    assert ref.read_labels(tmp_path / "S1.txt") == labels


def test_lecture_d_une_annotation(tmp_path):
    (tmp_path / "M01_S1.txt").write_text("1.0\t2.0\t\n3.0\t4.0\tS1\n")
    (tmp_path / "M01.txt").write_text("5.0\t6.0\tS2\n7.0\t8.0\tM01_S3\n0.0\t1.5\texclusion\n9.0\t9.0\tS2\n")
    (tmp_path / "a_verifier.txt").write_text("2.0\t2.5\tà vérifier : S1 ou S2\n")
    annotation = ref.read_annotation(tmp_path, "M01")
    assert annotation.speakers == {"M01_S1": [(1.0, 2.0), (3.0, 4.0)], "M01_S2": [(5.0, 6.0)],
                                   "M01_S3": [(7.0, 8.0)]}
    assert annotation.exclusions == [(0.0, 1.5)]
    assert len(annotation.warnings) == 2          # zone à vérifier, étiquette ponctuelle


@pytest.mark.parametrize("text, message", [("Paul", "inconnu"), ("M02_S1", "autre session")])
def test_texte_refuse(tmp_path, text, message):
    (tmp_path / "M01.txt").write_text(f"1.0\t2.0\t{text}\n")
    with pytest.raises(ref.LabelError, match=message):
        ref.read_annotation(tmp_path, "M01")


def test_uem_claquements_et_exclusions():
    assert ref.uem_intervals(2.0, 37.0) == [(3.0, 36.0)]
    assert ref.uem_intervals(2.0, 37.0, [(2.5, 5.0), (20.0, 21.0)]) == [(5.0, 20.0), (21.0, 36.0)]


def test_reference_rttm_et_uem(tmp_path):
    annotation = ref.Annotation(speakers={"M01_S1": [(2.0, 4.0), (4.15, 5.0), (30.0, 40.0)],
                                          "M01_S2": [(10.0, 11.0)]})
    reference = ref.build_reference(annotation, ref.uem_intervals(2.0, 37.0))
    assert reference.speakers == {"M01_S1": [(3.0, 5.0), (30.0, 36.0)], "M01_S2": [(10.0, 11.0)]}
    assert len(reference.cropped) == 1 and "M01_S1" in reference.cropped[0]
    text = ref.rttm_text("maison__M01", reference.speakers)
    assert text.splitlines()[0] == "SPEAKER maison__M01 1 3.000 2.000 <NA> <NA> M01_S1 <NA> <NA>"
    (tmp_path / "r.rttm").write_text(text)
    (tmp_path / "r.uem").write_text(ref.uem_text("maison__M01", reference.uem))
    from whospoke.experiment import load_rttm, load_uem

    assert load_rttm(tmp_path / "r.rttm", "maison__M01").get_timeline().duration() == pytest.approx(9.0)
    assert load_uem(tmp_path / "r.uem", "maison__M01").duration() == pytest.approx(33.0)


def test_controles():
    uem = [(3.0, 36.0)]
    reference = ref.Reference({"M01_S1": [(3.0, 35.0)], "M01_S2": [(10.0, 12.0)]}, uem, [])
    report = ref.check_reference(reference, ["M01_S1", "M01_S2", "M01_S3"])
    assert report["bloquants"] == ["M01_S3 : aucun segment"]
    assert report["statistiques"]["chevauchement_s"] == pytest.approx(2.0)
    assert report["statistiques"]["parole_s"] == pytest.approx(32.0)
    assert any("pauses à découper" in w for w in report["avertissements"])
    outside = ref.Reference({"M01_S1": [(1.0, 2.0)]}, uem, [])
    assert "hors de l'UEM" in ref.check_reference(outside, ["M01_S1"])["bloquants"][0]


def test_accord():
    first = {"M01_S1": [(0.0, 10.0)], "M01_S2": [(10.0, 20.0)]}
    assert ref.agreement(first, first, [(0.0, 20.0)])["collar_0"]["der"] == pytest.approx(0.0)
    # Libellés différents (appariement optimal) et une seconde manquée sur 20 : 5 %.
    second = {"X": [(1.0, 10.0)], "Y": [(10.0, 20.0)]}
    assert ref.agreement(first, second, [(0.0, 20.0)])["collar_0"]["der"] == pytest.approx(5.0)


# --- Synchronisation ----------------------------------------------------------------------


def test_correlation_normalisee():
    rng = np.random.default_rng(0)
    region = rng.standard_normal(2000)
    template = region[700:900].copy()
    corr = synchro.normalized_xcorr(template, region)
    assert int(np.argmax(corr)) == 700 and corr[700] == pytest.approx(1.0)
    assert corr[300] == pytest.approx(np.corrcoef(template, region[300:500])[0, 1])


def test_claquements_de_la_table():
    table, _, _ = meeting()
    start, end = synchro.find_table_claps(table)
    assert start == pytest.approx(CLAPS[0], abs=0.006) and end == pytest.approx(CLAPS[1], abs=0.006)


def test_decalage_et_derive_retrouves():
    table, _, phones = meeting()
    filtered = synchro.highpass(table, synchro.SyncParams().passe_haut_hz)
    for code, (offset, ratio) in CLOCKS.items():
        sync = synchro.sync_track(code, filtered, phones[code], *CLAPS)
        assert sync.aide_debut_s == pytest.approx(offset + ratio * CLAPS[0], abs=0.001), code
        assert sync.aide_fin_s == pytest.approx(offset + ratio * CLAPS[1], abs=0.001), code
        assert (sync.rapport - 1) * 1e6 == pytest.approx((ratio - 1) * 1e6, abs=50), code
        assert sync.alertes == [], code


def test_piste_alignee_sur_la_table():
    table, on_table_axis, phones = meeting()
    filtered = synchro.highpass(table, synchro.SyncParams().passe_haut_hz)
    sync = synchro.sync_track("S1", filtered, phones["S1"], *CLAPS)
    aligned = synchro.align(phones["S1"], sync, CLAPS[0], len(table))
    part = slice(int(5 * SR), int(35 * SR))
    assert np.corrcoef(aligned[part], on_table_axis["S1"][part])[0, 1] > 0.99


def test_claquement_absent_signale():
    rng = np.random.default_rng(5)
    table, _, _ = meeting()
    filtered = synchro.highpass(table, synchro.SyncParams().passe_haut_hz)
    noise = 0.01 * rng.standard_normal(len(table))
    sync = synchro.sync_track("S1", filtered, noise, *CLAPS)
    assert any("douteux" in alert for alert in sync.alertes)


# --- Pré-annotation -----------------------------------------------------------------------


def test_piste_la_plus_forte_designe_le_locuteur():
    _, on_table_axis, _ = meeting()
    start, end = CLAPS[0] + 1, CLAPS[1] - 1
    result = pre.preannotate(on_table_axis, start, end)
    assert set(result.segments) == {"S1", "S2", "S3"}
    assert frame_agreement(result.segments, truth_labels(), start, end) > 0.98
    assert result.a_verifier == []


def test_chevauchement_a_verifier():
    turns = TURNS + [("S2", 25.0, 26.5)]           # S2 parle pendant S1, au même niveau
    _, on_table_axis, _ = meeting(turns)
    result = pre.preannotate(on_table_axis, CLAPS[0] + 1, CLAPS[1] - 1)
    zones = [(a, b, text) for a, b, text in result.a_verifier if a < 26.5 and b > 25.0]
    assert zones and zones[0][2] == "à vérifier : S1 ou S2"


def test_seuil_d_activite():
    _, on_table_axis, _ = meeting()
    strict = pre.preannotate(on_table_axis, 3.0, 36.0, pre.PreannotationParams(seuil_activite_db=200.0))
    assert all(not intervals for intervals in strict.segments.values())


# --- Chaîne complète sur fichiers ---------------------------------------------------------


def write_session(root, session="M01", aids=("S1", "S2", "S3")):
    table, _, phones = meeting()
    directory = root / session
    directory.mkdir(parents=True)
    for name, signal in [("table", table)] + [(code, phones[code]) for code in aids]:
        pcm = np.round(0.9 * signal / np.abs(signal).max() * 32767).astype(np.int16)
        wavfile.write(directory / f"{name}.wav", SR, pcm)
    return directory


METADATA = "session: M01\ncondition: salle\nconsentements:\n  S1: [1, 2, 3]\n  S2: [1, 2]\n  S3: [1, 2, 3]\n"


@needs_ffmpeg
def test_chaine_complete(tmp_path):
    directory = write_session(tmp_path)
    processed = tmp_path / "processed" / "maison"
    (directory / "metadonnees.yaml").write_text(METADATA)
    sync = maison.synchronize(directory, "M01")
    for track in sync["pistes"]:
        offset, ratio = CLOCKS[track["piste"]]
        assert track["claquement_debut_dans_la_piste_s"] == pytest.approx(offset + ratio * CLAPS[0], abs=0.002)
        assert track["alertes"] == []
    assert json.loads((directory / "synchro.json").read_text())["claquements_table_s"]["debut"] == \
        pytest.approx(CLAPS[0], abs=0.006)

    maison.preannotate(directory, "M01")
    labels = sorted(p.name for p in (directory / "preannotation").glob("*.txt"))
    assert labels == ["S1.txt", "S2.txt", "S3.txt", "a_verifier.txt"]

    # « Correction » : les étiquettes pré-annotées, exportées dans annotation/, plus l'annonce exclue.
    annotation = directory / "annotation"
    annotation.mkdir()
    for code in ("S1", "S2", "S3"):
        shutil.copy(directory / "preannotation" / f"{code}.txt", annotation / f"M01_{code}.txt")
    (annotation / "M01_exclusions.txt").write_text("3.0\t3.8\texclusion\n")
    report = maison.convert(directory, "M01", processed=processed)
    assert report["valide"] and report["statistiques"]["n_locuteurs"] == 3 and report["condition"] == "salle"
    paths = maison.reference_paths("M01", processed)
    assert paths["wav"].is_file() and not (directory / "reference").exists()
    rttm = maison.read_rttm(paths["rttm"])
    uem = maison.read_uem(paths["uem"])
    assert uem == [(3.8, 36.0)]
    truth = {f"M01_{code}": intervals for code, intervals in truth_labels().items()}
    assert ref.agreement(truth, rttm, uem)["collar_0"]["der"] < 3.0

    window = maison.draw_window(directory, "M01", seed=7, processed=processed)["fenetre_s"]
    assert window[1] - window[0] == pytest.approx(120.0) or window == [3.8, 36.0]
    control = directory / "controle"
    ref.write_labels(control / "M01.txt",
                     [(a, b, code) for code, intervals in truth_labels().items() for a, b in intervals])
    accord = maison.control_agreement(directory, "M01", processed=processed)
    assert accord["der_collar_0"] < 3.0
    assert any("au moins 24 h" in alert for alert in accord["alertes"])
    assert "Session terminée." in maison.status(directory, "M01", processed)

    # S2 n'a pas coché l'option 3 : rien n'est versionné.
    versioned = tmp_path / "splits" / "maison"
    with pytest.raises(maison.SessionError, match="option 3 non cochée par S2"):
        maison.version(directory, "M01", processed, versioned)
    assert not versioned.exists()
    (directory / "metadonnees.yaml").write_text(METADATA.replace("S2: [1, 2]", "S2: [1, 2, 3]"))
    copies = maison.version(directory, "M01", processed, versioned)
    assert copies["rttm"] == versioned / "rttm" / "maison__M01.rttm"
    assert copies["rttm"].read_text() == paths["rttm"].read_text()
    assert copies["uem"].read_text() == paths["uem"].read_text()


@needs_ffmpeg
def test_locuteur_sans_segment_bloque_la_conversion(tmp_path):
    directory = write_session(tmp_path)
    processed = tmp_path / "processed" / "maison"
    maison.synchronize(directory, "M01")
    maison.preannotate(directory, "M01")
    annotation = directory / "annotation"
    annotation.mkdir()
    for code in ("S1", "S2"):                       # S3 oublié à l'export
        shutil.copy(directory / "preannotation" / f"{code}.txt", annotation / f"M01_{code}.txt")
    with pytest.raises(maison.SessionError, match="bloquants"):
        maison.convert(directory, "M01", processed=processed)
    assert not maison.reference_paths("M01", processed)["rttm"].exists()
    assert json.loads((directory / "conversion.json").read_text())["bloquants"] == ["M01_S3 : aucun segment"]


@needs_ffmpeg
def test_pistes_deja_alignees_et_etat(tmp_path):
    directory = write_session(tmp_path, aids=())
    processed = tmp_path / "processed"
    assert "Étape suivante : metadonnees.yaml" in maison.status(directory, "M01", processed)
    (directory / "metadonnees.yaml").write_text("session: M01\ncondition: visio\nconsentements:\n  S1: [1]\n")
    assert "Étape suivante : synchroniser" in maison.status(directory, "M01", processed)
    sync = maison.synchronize(directory, "M01", already_aligned=True)
    assert sync["pistes"] == []
    with pytest.raises(maison.SessionError, match="à partir de zéro"):
        maison.preannotate(directory, "M01")
    assert "Étape suivante : corriger dans Audacity" in maison.status(directory, "M01", processed)


def test_chemins_des_references():
    """Les références du corpus maison sont là où l'évaluation les lit (data/processed/maison/)."""
    from whospoke.experiment import processed_wav, reference_rttm, uem_path

    paths = maison.reference_paths("M01")
    assert paths == {"wav": processed_wav("maison", "maison__M01"),
                     "rttm": reference_rttm("maison", "maison__M01"),
                     "uem": uem_path("maison", "maison__M01")}
    assert uem_path("maison", "maison__M01") == REPO_ROOT / "data" / "processed" / "maison" / "uem" / "maison__M01.uem"
    assert uem_path("summre", "summre__x") == REPO_ROOT / "data" / "splits" / "summre" / "uem" / "summre__x.uem"


def test_exclusion_retiree_de_l_uem_et_de_la_reference():
    annotation = ref.Annotation(speakers={"M01_S1": [(3.0, 6.0), (10.0, 12.0)]}, exclusions=[(3.0, 5.0)])
    uem = ref.uem_intervals(2.0, 37.0, annotation.exclusions)
    reference = ref.build_reference(annotation, uem)
    assert uem == [(5.0, 36.0)]
    assert reference.speakers == {"M01_S1": [(5.0, 6.0), (10.0, 12.0)]}


@pytest.mark.parametrize("text, message", [
    ("session: M01\ncondition: salle\nconsentements:\n  S1: [1, 3]\nnom: Paul\n", "champs non prévus"),
    ("session: M02\ncondition: salle\nconsentements:\n  S1: [1]\n", "session"),
    ("session: M01\ncondition: cave\nconsentements:\n  S1: [1]\n", "condition"),
    ("session: M01\ncondition: salle\nconsentements:\n  Paul: [1]\n", "code de participant"),
    ("session: M01\ncondition: salle\nconsentements:\n  S1: [2, 3]\n", "option 1"),
    ("session: M01\ncondition: salle\nconsentements:\n  S1: [1, 4]\n", "liste d'options"),
])
def test_metadonnees_refusees(tmp_path, text, message):
    from whospoke.maison import metadonnees as meta

    (tmp_path / "metadonnees.yaml").write_text(text)
    with pytest.raises(meta.MetadataError, match=message):
        meta.load(tmp_path, "M01")


def test_metadonnees_et_option_3(tmp_path):
    from whospoke.maison import metadonnees as meta

    (tmp_path / "metadonnees.yaml").write_text(METADATA)
    data = meta.load(tmp_path, "M01")
    assert data.participants == ["S1", "S2", "S3"] and data.condition_label == "salle réverbérante"
    assert not data.versioning_allowed() and data.refusals() == ["S2"]
    assert meta.load_optional(tmp_path / "absent", "M01") is None


def test_session_mal_nommee(tmp_path, capsys):
    assert maison.main(["--racine", str(tmp_path), "etat", "m1"]) == 2
