"""Chantier B7 : robustesse de l'interface face à des fichiers inconnus (démonstration du
16/11). Fichiers fabriqués par `tests/fabrique.py`, sans donnée personnelle ; moteur factice
avec sorties fabriquées (`--factice-rttm`). Un message d'erreur dit toujours quoi faire."""

import html
import json
import re
import shutil
from pathlib import Path
from types import SimpleNamespace

import gradio as gr
import pytest
from pyannote.core import Annotation, Segment

from app import app as interface
from app import image, interactions, moteurs, sortie, temps
from tests import fabrique

ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")
SETTINGS = ("pyannote-community-1", False, "baseline-ecapa", "Automatique", 2, 2, 6, "cpu")
ACTION = re.compile(r"Déposez|déposez|Vérifiez|Récupérez|Convertissez|exportez|Installez|corrigez|Corrigez|"
                    r"Gardez|coupez|relancez")


def annotation(rows, uri="essai"):
    result = Annotation(uri=uri)
    for index, (start, end, label) in enumerate(rows):
        result[Segment(start, end), index] = label
    return result


def handlers(tmp_path, monkeypatch, outputs: Path | None = None):
    (tmp_path / "run").mkdir(exist_ok=True)
    monkeypatch.setattr(interface, "RUN_DIR", tmp_path / "run")
    blocks = interface.build_app(fake=True, fake_max_s=0.05, cache_dir=tmp_path / "cache",
                                 fake_rttm=outputs or tmp_path / "sorties")
    return {getattr(f.fn, "__name__", ""): f.fn for f in blocks.fns.values()}


def prepare(fns, path):
    """Dépôt d'un fichier : (préparé, durée annoncée), ou gr.Error."""
    return list(fns["audio_changed"](str(path), *SETTINGS, False))[-1]


def analyse(fns, path, reference=None):
    final = list(fns["analyse"](None, str(path), *SETTINGS, reference, False))[-1]
    result = next(v for v in final.values() if isinstance(v, dict) and "annotation" in v)
    texts = [html.unescape(v) for v in final.values() if isinstance(v, str)]
    return result, texts


# --- Fichiers audio ----------------------------------------------------------------------

READABLE = [case for case in fabrique.CASES_AUDIO
            if case[1] not in ("corrompu", "texte_renomme", "mp4_sans_son")]


@ffmpeg
@pytest.mark.parametrize("name,kind,seconds", READABLE, ids=[case[0] for case in READABLE])
def test_formats_lisibles_normalises(tmp_path, monkeypatch, name, kind, seconds):
    """Vidéo, stéréo, 44,1 et 48 kHz, m4a, ogg, 3 s, silence : WAV 16 kHz mono, bonne durée."""
    fns = handlers(tmp_path, monkeypatch)
    path = fabrique.audio(kind, tmp_path / "audio" / name, seconds)
    prepared, announce = prepare(fns, path)
    assert prepared["duree_s"] == pytest.approx(seconds, abs=0.1)
    assert prepared["silencieux"] is (kind == "silence")
    assert "Durée estimée" in announce
    assert ("semble silencieux" in announce) is (kind == "silence")


@ffmpeg
@pytest.mark.parametrize("name,kind,cause", [
    ("enregistrement coupé.m4a", "corrompu", "est incomplet"),
    ("compte-rendu.wav", "texte_renomme", "n'est pas un fichier audio ou vidéo lisible"),
    ("video sans son.mp4", "mp4_sans_son", "ne contient pas de piste son"),
])
def test_fichiers_illisibles_message_qui_dit_quoi_faire(tmp_path, monkeypatch, name, kind, cause):
    fns = handlers(tmp_path, monkeypatch)
    path = fabrique.audio(kind, tmp_path / "audio" / name, 20.0)
    with pytest.raises(gr.Error) as caught:
        prepare(fns, path)
    message = caught.value.message
    assert f"« {name} »" in message and cause in message and ACTION.search(message)
    assert str(tmp_path) not in message and "@ 0x" not in message      # ni chemin local ni adresse
    # Analyse lancée quand même : le panneau passe à l'échec, avec le même message.
    with pytest.raises(gr.Error):
        list(fns["analyse"](None, str(path), *SETTINGS, None, False))


def test_message_audio_sans_ffmpeg_ni_cause_connue():
    assert "brew install ffmpeg" in interface._audio_error("a.wav", RuntimeError("Exécutable ffmpeg introuvable : 'x'"))
    other = interface._audio_error("a.wav", RuntimeError("ffmpeg a échoué sur /tmp/a.wav (code 1) : bizarre"))
    assert "Convertissez-le en WAV ou en MP3" in other and "bizarre" in other and "/tmp" not in other


# --- Sorties de moteur fabriquées ---------------------------------------------------------

@pytest.fixture
def made(tmp_path, monkeypatch):
    """Audio de 60 s et sorties fabriquées de chaque cas ; renvoie (handlers, chemin de l'audio)."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg absent")
    audio = fabrique.audio("wav_16k", tmp_path / "base.wav", 60.0)

    def run(case, rows=None, reference=None):
        rows = fabrique.outputs(60.0)[case] if rows is None else rows
        fabrique.write_rttm(tmp_path / "sorties" / f"{case}.rttm", case, rows)
        path = tmp_path / "audio" / f"{case}.wav"
        path.parent.mkdir(exist_ok=True)
        shutil.copy(audio, path)
        return analyse(fns, path, reference)

    fns = handlers(tmp_path, monkeypatch)
    run.fns = fns
    return run


def test_zero_locuteur(made):
    result, texts = made("zero locuteur")
    assert not len(result["annotation"])
    status = next(t for t in texts if "st-root" in t)
    assert "Aucun locuteur détecté, en" in status and "locuteur(s)" not in status
    assert any("Aucun locuteur détecté : le moteur n'a trouvé aucune parole" in t and "Vérifiez" in t for t in texts)
    assert any("pas d'interaction à décrire" in t for t in texts)
    exports = interface._exports(result)
    assert Path(exports[2]).read_text() == "" and "<svg" in Path(exports[3]).read_text()
    assert interface._viewer_value(result)["groupes"][0]["locuteurs"] == []
    assert "'Aucun locuteur', 'Aucun locuteur détecté'" in (interface.STATIC_DIR / "visualiseur.js").read_text()


def test_un_locuteur(made):
    result, texts = made("un locuteur")
    assert any("1 locuteur en" in t for t in texts)
    html = interface._interactions_html(result)
    assert "ws-matrix" not in html and "—" in html                    # ni matrice ni latence
    assert 'class="ws-merge"' not in interface._stats_html(result)    # personne avec qui fusionner


@pytest.mark.parametrize("case,count", [("six locuteurs", 6), ("neuf locuteurs", 9), ("douze locuteurs", 12)])
def test_six_neuf_douze_locuteurs(made, case, count):
    result, texts = made(case)
    assert any(f"{count} locuteurs en" in t for t in texts)
    speakers = interface._viewer_value(result)["groupes"][0]["locuteurs"]
    assert len(speakers) == count
    # Huit couleurs, puis gris : l'identité est portée par le nom de chaque piste.
    assert len({s["couleur"] for s in speakers}) == min(count, 8) + (1 if count > 8 else 0)
    matrix = interface._interactions_html(result)
    assert matrix.count('<th scope="row"') == count
    assert ('class="ws-mx-num"' in matrix) is (count > interface.MATRIX_NAMED_MAX)


def test_au_dela_de_neuf_locuteurs_isolement_par_le_nom():
    script = (interface.STATIC_DIR / "visualiseur.js").read_text()
    assert "toggleIsolation(spk.id)" in script and "cliquer sur leur nom" in script
    assert "ou cliquer sur son nom" in interface.VIEWER_TEMPLATE


def test_chevauchement_massif(made):
    result, texts = made("chevauchement massif")
    stats = interface._stats_html(result)
    assert stats.count("disabled") == 4                               # aucun extrait sans chevauchement
    html = interface._interactions_html(result)
    assert "Aucun passage de parole" in html and "0 passages" not in html


def test_tours_de_50_ms(made):
    result, _ = made("tours de 50 ms")
    assert len(result["annotation"]) == 1200
    html = interface._interactions_html(result)
    assert "0,05 s" in html and "0,1 s" not in html                  # durée moyenne et plus long tour
    assert temps.format_duration(0.05) == "0,05 s" and temps.format_duration(0.0) == "0 s"
    assert temps.format_duration(4.2) == "4 s"
    script = (interface.STATIC_DIR / "visualiseur.js").read_text()
    assert "function fmtSpan" in script and "span.length" in script


# --- Noms ---------------------------------------------------------------------------------

LONG = "Konstantin Oberhauser-Wettstein, direction financière et juridique du groupe"


def test_noms_longs_speciaux_et_doublons(made):
    result, _ = made("six locuteurs")
    changed = made.fns["speakers_changed"]
    names = {"SPEAKER_00": LONG, "SPEAKER_01": "<script>alert(1)</script>", "SPEAKER_02": "Seán O'Brien",
             "SPEAKER_03": "王秀英", "SPEAKER_04": "نور الهدى", "SPEAKER_05": '🦊 Fox & "Co"'}
    outputs = changed(result, None, SimpleNamespace(_data={"names": names}))
    renamed = outputs[-1]
    assert renamed["names"]["SPEAKER_00"] == LONG[:60]                # 60 caractères au plus
    for html in outputs[1:3]:
        assert "<script>alert" not in html and "&lt;script&gt;" in html
    assert "<script>alert" not in outputs[6] and "&amp;lt;script&amp;gt;" in outputs[6]   # SVG dans un attribut
    svg = interface._timeline_svg(renamed)
    assert "<script>" not in svg and "…" in svg                      # nom coupé dans l'image
    files = {Path(p).suffix: Path(p) for p in interface._exports(renamed)}
    rttm = files[".rttm"].read_text()
    assert "<script>alert(1)</script>" in rttm and "Seán_O'Brien" in rttm and "王秀英" in rttm
    data = json.loads(files[".json"].read_text())
    assert data["etiquettes_audacity"]["S1"]["nom"] == LONG[:60]
    codes = {line.split("\t")[2] for line in files[".txt"].read_text().splitlines()}
    assert codes == {"S1", "S2", "S3", "S4", "S5", "S6"}             # codes seulement, jamais les noms
    # Doublons à la casse, aux espaces et à « _ » près : refusés, avec la raison.
    with pytest.warns(UserWarning, match="« Alice Martin » et « alice_martin ».*égaux aux espaces"):
        refused = changed(renamed, None, SimpleNamespace(_data={"names": {"SPEAKER_00": "Alice Martin",
                                                                         "SPEAKER_01": "alice_martin"}}))
    assert refused[-1].get("__type__") == "update"
    with pytest.raises(ValueError, match="Nom en double : « Alice »"):
        sortie.resolve_names(["A", "B"], {"A": "Alice", "B": "Alice"})


# --- Références ---------------------------------------------------------------------------

@pytest.mark.parametrize("case,expected", [
    ("colonnes manquantes", r"ligne 1 : 5 champs au lieu de 10.*Corrigez cette ligne"),
    ("nombre illisible", r"ligne 1 : début « zéro » ou durée « 1,5 » illisible.*corrigez"),
    ("duree negative", r"ligne 1 : début 4.0 s, durée -1.0 s.*doivent être positifs"),
    ("vide", r"est vide\. Déposez le fichier RTTM"),
    ("pas un rttm", r"ressemble à des étiquettes Audacity.*Convertissez"),
    ("binaire", r"n'est pas un fichier texte.*déposez le fichier \.rttm"),
    ("plusieurs fichiers", r"décrit 2 enregistrements.*Gardez seulement"),
])
def test_references_mal_formees(tmp_path, case, expected):
    paths = fabrique.references(tmp_path, "six locuteurs", 60.0)
    with pytest.raises(ValueError, match=expected):
        sortie.read_reference(paths[case])
    html = interface._der_html(None, str(paths[case]))                # contrôlée dès le dépôt
    assert "Référence inutilisable" in html and 'role="alert"' in html


def test_reference_d_un_autre_fichier_plus_longue_plus_courte(made, tmp_path):
    paths = fabrique.references(tmp_path / "refs", "six locuteurs", 60.0)
    expected = {"autre fichier": "décrit l'enregistrement « summre__004c_PAPH »",
                "plus longue": "va jusqu'à 1:59, l'audio s'arrête à 1:00",
                "plus courte": "s'arrête à 0:29 sur 1:00 d'audio"}
    for case, text in expected.items():
        result, texts = made("six locuteurs", reference=str(paths[case]))
        der = next(t for t in texts if "ws-scope" in t)
        plain = re.sub(r"<[^>]+>", "", der).replace(" ", " ")
        assert text in plain and "À vérifier" in plain and ACTION.search(plain.split("À vérifier")[1]), case
    # La bonne référence ne déclenche aucun avertissement ; le nom court du corpus est reconnu.
    good = fabrique.write_rttm(tmp_path / "bonne.rttm", "six locuteurs", fabrique.outputs(60.0)["six locuteurs"])
    reference = sortie.read_reference(good)
    assert sortie.reference_warnings(reference, reference, "six locuteurs", 60.0) == []
    assert sortie._same_recording("summre__007a_ECRH", "007a_ECRH")


# --- Moteur factice et longs enregistrements ---------------------------------------------

def test_moteur_factice_sorties_fabriquees_et_message(tmp_path):
    spec = moteurs.SPECS["pyannote-community-1"]
    fabrique.write_rttm(tmp_path / "réunion du 16.rttm", "réunion du 16", [(0.0, 2.0, "A")])
    engine = moteurs.FakeEngine(spec, simulated_s=0.0, fabricated=tmp_path)
    import torch
    out = engine.run(torch.zeros(1, 16000 * 3), uri="réunion du 16")
    assert out.annotation.labels() == ["A"] and out.annotation.uri == "réunion du 16"
    with pytest.raises(FileNotFoundError, match="aucune sortie pour « inconnu ».*--factice-rttm"):
        engine.run(torch.zeros(1, 16000), uri="inconnu")


def test_quatre_vingt_dix_minutes_de_tours(tmp_path):
    """90 min de tours (sans audio) : calculs, visualiseur, image et étiquettes sans erreur."""
    duration = 5400.0
    hyp = annotation(fabrique.turns_round_robin(4, duration, 3.0, 0.4))
    ref = annotation(fabrique.turns_round_robin(4, duration, 2.9, 0.5))
    errors = interface._errors_for(ref, {"annotation": hyp, "duree_s": duration})
    assert errors["zones"]
    report = interactions.report(hyp)
    assert report["n_passages"] == len(hyp) - 1
    result = {"annotation": hyp, "names": {}, "duree_s": duration, "libelle": "pyannote", "reference": ref,
              "erreurs": errors, "wav": tmp_path / "x.wav", "peaks": [], "uri": "long"}
    svg = interface._timeline_svg(result)
    assert svg.count("<rect") > len(hyp) and image.tick_step(duration) == 600
    assert len(sortie.to_audacity(hyp).splitlines()) == len(hyp)


@pytest.mark.lent
@ffmpeg
@pytest.mark.parametrize("name,kind,seconds", fabrique.LONG_AUDIO)
def test_trente_et_quatre_vingt_dix_minutes(tmp_path, monkeypatch, name, kind, seconds):
    fns = handlers(tmp_path, monkeypatch)
    path = fabrique.audio(kind, tmp_path / "audio" / name, seconds)
    stem = Path(name).stem
    fabrique.write_rttm(tmp_path / "sorties" / f"{stem}.rttm", stem, fabrique.turns_round_robin(4, seconds, 3.0, 0.4))
    result, texts = analyse(fns, path)
    assert result["duree_s"] == pytest.approx(seconds, abs=0.5) and len(result["peaks"]) == int(10 * seconds)
    assert any("4 locuteurs en" in t for t in texts)
