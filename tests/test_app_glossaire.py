"""Glossaire intégré (D26, chantier I3 ; app/glossaire.py) : lecture de docs/glossaire.md,
onglet, renvois automatiques. Glossaire fabriqué dans un dossier temporaire."""

import re

import pytest

from app import glossaire as g
from whospoke.experiment import REPO_ROOT

TEXT = """# Glossaire

Introduction avec `code` et **gras**.

## La chaîne en une phrase

Six étapes : détecter la parole, regrouper.

---

### Collar
Définition : zone de tolérance autour des frontières, exclue du calcul du DER.
Source : protocole.

### DER (*Diarization Error Rate*)
Définition : rapport des erreurs ; dépend du collar.
Rôle dans la chaîne : métrique principale.

### Détection d'activité vocale (VAD, *voice activity detection*)
Définition : parole ou non.

### Empreinte vocale (*speaker embedding*)
Définition : un vecteur par voix.

### Hybride (système)
Définition : réseau local et regroupement global.

### Parole
Définition : terme court, pour tester la priorité au plus long.

### Parole manquée (*missed detection*)
Définition : parole de la référence non couverte.

### Regroupement (*clustering*)
Définition : rassembler les empreintes.

## Conditions

Une partie avec son texte.

### Oracle
Définition : vérité terrain à la place d'une étape.
"""


@pytest.fixture
def glossary(tmp_path):
    path = tmp_path / "glossaire.md"
    path.write_text(TEXT)
    return g.read_glossary(path)


@pytest.fixture
def linker(glossary):
    return g.Linker(glossary)


def anchors(html):
    return re.findall(r'data-term="([^"]+)"', html)


def test_lecture_des_termes_et_variantes(glossary):
    terms = {t.name: t for t in glossary.terms}
    assert list(terms) == ["Collar", "DER", "Détection d'activité vocale", "Empreinte vocale", "Hybride",
                           "Parole", "Parole manquée", "Regroupement", "Oracle"]
    assert terms["DER"].english == ["Diarization Error Rate"]
    assert terms["Détection d'activité vocale"].aliases == ["VAD"]
    # « (système) », en minuscules, est un qualificatif et non une variante.
    assert terms["Hybride"].variants == ["Hybride"]
    assert terms["DER"].definition == "rapport des erreurs ; dépend du collar."
    assert terms["DER"].anchor == "gl-der"
    assert terms["Détection d'activité vocale"].anchor == "gl-detection-d-activite-vocale"


def test_parties_introduction_et_separateur(glossary):
    assert glossary.intro.startswith("Introduction")
    assert glossary.sections == [("La chaîne en une phrase", "Six étapes : détecter la parole, regrouper."),
                                 ("Conditions", "Une partie avec son texte.")]
    parts = {t.name: t.part for t in glossary.terms}
    assert parts["Collar"] == "" and parts["Oracle"] == "Conditions"   # « --- » clôt la partie


def test_sous_chaines_et_identifiants(linker):
    html = linker.link("<p>DER sans collar</p>")
    assert anchors(html) == ["gl-der", "gl-collar"]
    for text in ("der_c0", "clustering.threshold", "VBxClustering", "RTFM", "pré-DER", "DERnier", "collar=0.5"):
        assert anchors(linker.link(f"<p>{text}</p>")) == [], text


def test_sigles_sensibles_a_la_casse_mots_non(linker):
    assert anchors(linker.link("<p>der et Der</p>")) == []
    assert anchors(linker.link("<p>Le DER</p>")) == ["gl-der"]
    assert anchors(linker.link("<p>REGROUPEMENT puis oracle</p>")) == ["gl-regroupement", "gl-oracle"]
    assert anchors(linker.link("<p>la VAD</p>")) == ["gl-detection-d-activite-vocale"]


def test_pluriels_apostrophes_et_plus_long_d_abord(linker):
    assert anchors(linker.link("<p>Empreintes vocales</p>")) == ["gl-empreinte-vocale"]
    assert anchors(linker.link("<p>détection d’activité vocale</p>")) == ["gl-detection-d-activite-vocale"]
    # « Parole manquée » l'emporte sur « Parole » ; « parole » seule renvoie à « Parole ».
    assert anchors(linker.link("<p>Parole manquée</p>")) == ["gl-parole-manquee"]
    assert anchors(linker.link("<td>parole</td>")) == ["gl-parole"]


def test_premiere_occurrence_par_bloc(linker):
    html = linker.link("<table><tr><th>DER</th><td>DER et DER</td></tr></table><p>DER <span>DER</span></p>")
    assert anchors(html) == ["gl-der", "gl-der", "gl-der"]    # th, td, p : une fois chacun
    nested = linker.link("<div><p>collar</p>collar</div>")
    assert anchors(nested) == ["gl-collar", "gl-collar"]       # le p est un bloc dans le div


def test_jamais_dans_code_bouton_lien_ni_attribut(linker):
    html = linker.link('<p title="DER"><code>DER</code> <button>DER</button> <a href="#">DER</a> '
                       '<span data-x="collar">texte</span></p>')
    assert anchors(html) == []
    assert 'title="DER"' in html and 'data-x="collar"' in html


def test_html_preserve(linker):
    source = '<p class="x">&lt;b&gt; DER &amp; 3 &lt; 4<br>suite</p><img src="a.png" alt="DER">'
    html = linker.link(source)
    assert '&lt;b&gt;' in html and '&amp;' in html and '3 &lt; 4' in html
    assert '<br>' in html and 'alt="DER"' in html
    assert re.sub(r"<a [^>]*>(.*?)</a>", r"\1", html) == source


def test_onglet_une_ancre_par_terme_sans_lien_vers_soi(glossary, linker):
    html = g.render(glossary, linker)
    ids = re.findall(r'<article class="gl-term" id="([^"]+)"', html)
    assert len(ids) == len(glossary.terms) == len(set(ids))
    der = html[html.index('id="gl-der"'):html.index('id="gl-detection')]
    assert "gl-collar" in der                        # la définition du DER renvoie au collar
    assert 'data-term="gl-der"' not in der           # mais jamais à elle-même
    assert html.count('class="gl-index"') == len(glossary.terms)
    assert "<code>code</code>" in html and "<strong>gras</strong>" in html


def test_glossaire_absent(tmp_path):
    glossary = g.read_glossary(tmp_path / "absent.md")
    assert glossary.terms == [] and "introuvable" in g.render(glossary)
    assert g.Linker(glossary).link("<p>DER</p>") == "<p>DER</p>"


def test_glossaire_du_depot():
    glossary = g.read_glossary(REPO_ROOT / g.GLOSSARY_RELATIVE)
    assert len(glossary.terms) >= 20
    assert len({t.anchor for t in glossary.terms}) == len(glossary.terms)
    assert all(t.definition for t in glossary.terms)


def test_renvois_dans_les_onglets():
    """Analyse (tableau du DER), Pipeline et Avancement passent par le glossaire du dépôt."""
    from app import app as interface

    linker = g.Linker(g.read_glossary(REPO_ROOT / g.GLOSSARY_RELATIVE))
    title, status, stats, times, der = interface._linked(linker)
    assert "gl-link" in status(["segmentation"], {}, "En cours")
    assert "gl-link" in title("Décomposition de l'erreur par les oracles")
    interface.build_app(fake=True)


# --- Formes courtes (D26, amendement du 01/11) -----------------------------------------

SHORT = """# Glossaire

### Confusion de locuteur (*speaker confusion*)
Formes courtes : confusion.
Définition : parole attribuée au mauvais locuteur.

### Détection d'activité vocale (VAD, *voice activity detection*)
Formes courtes : détection de parole, détection d'activité vocale.
Définition : parole ou non.

### Empreinte vocale (*speaker embedding*)
Formes courtes : empreinte, embedding
Définition : un vecteur par voix.

### Effet de bord
Formes courtes : confusion.
Définition : entrée fabriquée qui revendique une forme déjà prise.
"""


@pytest.fixture
def short_glossary(tmp_path):
    path = tmp_path / "glossaire.md"
    path.write_text(SHORT)
    return g.read_glossary(path)


def test_ligne_formes_courtes_lue_et_non_affichee_comme_champ(short_glossary):
    terms = {t.name: t for t in short_glossary.terms}
    assert terms["Confusion de locuteur"].short_forms == ["confusion"]
    assert terms["Détection d'activité vocale"].short_forms == ["détection de parole", "détection d'activité vocale"]
    assert terms["Empreinte vocale"].short_forms == ["empreinte", "embedding"]       # point final facultatif
    assert all(key != "Formes courtes" for t in short_glossary.terms for key, _ in t.fields)
    assert terms["Confusion de locuteur"].definition == "parole attribuée au mauvais locuteur."
    html = g.render(short_glossary)
    assert '<p class="gl-short">Formes courtes : confusion</p>' in html


def test_formes_courtes_renvoient_a_l_entree_mot_entier(short_glossary):
    linker = g.Linker(short_glossary)
    assert anchors(linker.link("<th>Confusion</th>")) == ["gl-confusion-de-locuteur"]
    assert anchors(linker.link("<li>Détection de parole</li>")) == ["gl-detection-d-activite-vocale"]
    assert anchors(linker.link("<p>deux empreintes, des embeddings</p>")) == ["gl-empreinte-vocale"]
    for text in ("confusion_c0", "confusion.ratio", "embeddingDim", "nb_confusion"):
        assert anchors(linker.link(f"<p>{text}</p>")) == [], text
    # Le terme complet reste prioritaire sur sa forme courte.
    html = linker.link("<p>Confusion de locuteur</p>")
    assert re.findall(r">([^<]+)</a>", html) == ["Confusion de locuteur"]


def test_forme_revendiquee_par_deux_entrees_signalee(short_glossary):
    linker = g.Linker(short_glossary)
    assert linker.conflicts == ["« confusion » : Confusion de locuteur et Effet de bord"]
    assert anchors(linker.link("<p>confusion</p>")) == ["gl-confusion-de-locuteur"]   # la première l'emporte


def test_formes_courtes_du_depot():
    """Glossaire de la branche (sans formes courtes) et, s'il est présent, celui du dépôt
    principal : aucune forme revendiquée deux fois, chacune renvoie à sa propre entrée."""
    paths = [REPO_ROOT / g.GLOSSARY_RELATIVE]
    main = REPO_ROOT.parent / "Who-Spoke" / g.GLOSSARY_RELATIVE
    if main.is_file():
        paths.append(main)
    for path in paths:
        glossary = g.read_glossary(path)
        linker = g.Linker(glossary)
        assert linker.conflicts == [], path
        for term in glossary.terms:
            for form in term.short_forms:
                assert anchors(linker.link(f"<p>{form}</p>"))[:1] == [term.anchor], (path, form)
