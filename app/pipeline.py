"""Onglet « Pipeline » : consultation en lecture seule de la configuration des moteurs (D17, D26).

La page est générée, jamais rédigée à la main :

- les réglages et leurs valeurs viennent de `configuration_effective`, consignée dans
  `execution_<périphérique>.json` de l'expérience source du moteur (`app/moteurs.py`) ;
- leur libellé, leur effet, les composantes du DER concernées et la décision qui les
  fixe viennent de `src/whospoke/pipelines/catalogue.yaml` ;
- l'étape Normalisation, commune à tous les moteurs, lit ses valeurs dans le code
  (`whospoke.audio.describe_normalisation`) et ses textes dans la section `communs` du
  catalogue (D26, amendement du 01/11) ; l'étape Évaluation lit ses valeurs dans
  `whospoke.evaluation.metrics` et dans le config.yaml de l'expérience source.

Tout est lu depuis une racine de dépôt configurable (`--depot` de app/app.py), sans
jamais y écrire, ni charger de modèle. Les réglages présents dans la configuration mais
absents du catalogue, ou l'inverse, sont signalés en tête de page.

Révisions des modèles (D18, amendement du 01/11) : lues dans la valeur d'un réglage
`*.modele` au format `dépôt@commit (architecture)`, ou dans un réglage `*.revision` ;
sinon, la page affiche « révision non consignée ».

Pipeline relié aux mesures (audit R-U8) : sous chaque étape, les constats de
`docs/constats.yaml` dont l'`etape` est celle-ci et dont les `moteurs` comprennent le
moteur affiché (liste vide : tous) ; « evaluation » va sous l'étape Évaluation. Un constat
dont l'étape n'existe pas au catalogue est signalé en tête de page. Les étapes qu'un même
réseau réalise sont présentées dans un seul bloc, réglages distingués par étape, selon la
section `regroupements` du catalogue (pyannote : détection et segmentation) ; à défaut dans
le catalogue de `--depot`, celle du catalogue de ce code est utilisée.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

import yaml

from app import formatage
from app import constats as constats_file
from app import moteurs
from whospoke import audio
from whospoke.evaluation.metrics import CONDITIONS, DiarizationEvaluator

CATALOGUE_RELATIVE = Path("src") / "whospoke" / "pipelines" / "catalogue.yaml"
NO_REVISION = "révision non consignée"
_REVISION = re.compile(r"@([0-9a-f]{7,40})\b")

ORIGIN_LABELS = {
    "experience": "Expérience",
    "defaut": "Défaut du moteur",
    "modele": "Modèle pré-entraîné",
    "code": "Imposé par le code",
}
# Famille d'erreurs de chaque étape (glossaire : la chaîne en une phrase).
FAMILIES = {
    "analyse": "Préparation", "normalisation_cepstrale": "Préparation",
    "detection": "Détection", "segmentation": "Détection",
    "representation": "Attribution", "empreintes": "Attribution",
    "regroupement": "Attribution", "attribution": "Attribution",
    "sortie": "Résultat",
}
SOURCE_FILES = {
    "baseline": "src/whospoke/pipelines/baseline.py",
    "pyannote-community-1": "src/whospoke/pipelines/pyannote_community1.py",
}
NON_ERRORS = {"temps", "aucun effet sur le DER"}


@dataclass
class Row:
    name: str
    label: str
    value: str
    origin: str
    decision: str | None
    effect: str | None
    components: list[str]
    revision: str | None = None   # réglages de modèle seulement
    catalogued: bool = True


@dataclass
class Stage:
    id: str
    label: str
    family: str
    role: str
    defined_in: str
    rows: list[Row]
    note: str = ""
    constats: list = field(default_factory=list)    # constats_file.Constat de cette étape
    parts: list["Stage"] = field(default_factory=list)   # étapes d'un même réseau, regroupées
    shape: str = ""          # forme des données en sortie (flèche du schéma, catalogue `formes`)
    number: str = ""         # numéro dans le pipeline (« 2–3 » pour un bloc de deux étapes)

    @property
    def step_ids(self) -> list[str]:
        return [part.id for part in self.parts] if self.parts else [self.id]

    @property
    def all_constats(self) -> list:
        return [c for part in self.parts for c in part.constats] if self.parts else self.constats

    @property
    def errors(self) -> list[str]:
        seen: list[str] = []
        for row in self.rows + [row for part in self.parts for row in part.rows]:
            seen += [c for c in row.components if c not in NON_ERRORS and c not in seen]
        return seen

    @property
    def models(self) -> list[Row]:
        return [row for row in self.rows + [r for part in self.parts for r in part.rows] if row.revision is not None]


@dataclass
class Page:
    spec: moteurs.EngineSpec
    unavailable: str | None = None
    execution: str = ""
    device: str = ""
    date: str = ""
    commit: str = ""
    versions: dict = field(default_factory=dict)
    stages: list[Stage] = field(default_factory=list)
    evaluation: Stage | None = None
    not_catalogued: list[str] = field(default_factory=list)      # dans la configuration, pas au catalogue
    not_configured: list[str] = field(default_factory=list)      # au catalogue, pas dans la configuration
    wrong_step: list[str] = field(default_factory=list)          # étape différente
    constat_issues: list[str] = field(default_factory=list)      # constats à étape inconnue, fichier mal formé
    shape_gaps: list[str] = field(default_factory=list)          # formes des données incomplètes
    errors: dict | None = None    # DER test sans collar de l'expérience source et ses composantes


def format_value(name: str, value) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "oui" if value else "non"
    if isinstance(value, float):
        text = formatage.general(value)
        return text + (f"{formatage.NNBSP}s" if name.endswith("_s") else "")
    if isinstance(value, int):
        unit = "s" if name.endswith("_s") else "Hz" if name.endswith("_hz") else None
        return formatage.unite(value, unit) if unit else str(value)
    return str(value)


def revision_of(setting: dict, settings: list[dict]) -> str:
    """Révision d'un réglage de modèle : `@commit` dans sa valeur, ou réglage `*.revision`."""
    match = _REVISION.search(str(setting["valeur"]))
    if match:
        return match.group(1)
    prefix = setting["nom"].rsplit(".", 1)[0]
    for other in settings:
        if other["nom"] == f"{prefix}.revision" and other["valeur"]:
            return str(other["valeur"])
    return NO_REVISION


def load_catalogue(root: Path) -> dict:
    path = root / CATALOGUE_RELATIVE
    if not path.is_file():
        raise FileNotFoundError(f"Catalogue introuvable : {path}")
    return yaml.safe_load(path.read_text())


def execution_file(spec: moteurs.EngineSpec, root: Path) -> Path:
    """execution_<périphérique>.json de l'exécution principale de l'expérience source."""
    return moteurs.execution_path(spec, root / "experiments")


def _common_normalisation(catalogue: dict, page: Page) -> Stage:
    """Étape Normalisation : valeurs lues dans `whospoke.audio`, textes dans le catalogue
    (`communs`) ; rien d'écrit ici (D26, amendement du 01/11)."""
    entries = catalogue.get("communs") or {}
    step = (catalogue.get("etapes") or {}).get("normalisation", {})
    settings = audio.describe_normalisation()
    rows = []
    for setting in settings:
        entry = entries.get(setting["nom"])
        if entry is None:
            page.not_catalogued.append(f"{setting['nom']} (normalisation)")
        elif entry["etape"] != "normalisation":
            page.wrong_step.append(f"{setting['nom']} : étape « normalisation » dans le code, "
                                   f"« {entry['etape']} » au catalogue")
        rows.append(_row(setting, settings, entry))
    described = {setting["nom"] for setting in settings}
    page.not_configured += sorted(f"{name} (communs)" for name, entry in entries.items()
                                  if entry.get("etape") == "normalisation" and name not in described)
    return Stage("normalisation", step.get("libelle", "Normalisation"), "Préparation", step.get("role", ""),
                 f"src/{audio.__name__.replace('.', '/')}.py (ffmpeg en sous-processus)", rows)


def _row(setting: dict, settings: list[dict], entry: dict | None) -> Row:
    name = setting["nom"]
    return Row(
        name=name,
        label=(entry or {}).get("libelle", name),
        value=format_value(name, setting["valeur"]),
        origin=setting.get("origine", ""),
        decision=(entry or {}).get("decision"),
        effect=(entry or {}).get("effet"),
        components=list((entry or {}).get("composantes", [])),
        revision=revision_of(setting, settings) if name.endswith(".modele") else None,
        catalogued=entry is not None,
    )


def _evaluation(config: dict) -> Stage:
    evaluator = DiarizationEvaluator()
    metrics = evaluator._der
    collars = " et ".join(
        f"{format_value('', metrics[name].collar)}"
        + (" (principale)" if i == 0 else f" (± {format_value('', metrics[name].collar / 2)}{formatage.NNBSP}s)")
        for i, name in enumerate(CONDITIONS)
    )
    skip = all(metric.skip_overlap for metric in metrics.values())
    references = (config.get("evaluation") or {}).get("references") or "data/processed/<corpus>/rttm"
    rows = [
        Row("collar", "collar (pyannote.metrics)", collars, "code", "D1",
            "Zone de tolérance autour des frontières de la référence (largeur totale).", ["mesure seulement"]),
        Row("skip_overlap", "skip_overlap", "oui" if skip else "non : chevauchements comptés", "code", "D1",
            "Les zones où plusieurs personnes parlent restent dans le calcul.", ["mesure seulement"]),
        Row("uem", "Zone évaluée (UEM)", "UEM du corpus, sinon fichier entier", "code", "protocole §2",
            "Intervalles sur lesquels porte l'évaluation.", ["mesure seulement"]),
        Row("references", "Références", str(references), "experience", "protocole §2",
            "Annotations de référence de l'expérience source.", ["mesure seulement"]),
        Row("agregation", "Agrégation", "rapport des sommes", "code", "protocole §4",
            "Les durées d'erreur sont sommées sur les fichiers avant le rapport.", ["mesure seulement"]),
    ]
    return Stage("evaluation", "Évaluation", "Mesure (hors pipeline)",
                 "N'agit pas sur ce que l'outil produit, seulement sur la façon de le noter : changer ces "
                 "réglages change le score, pas le système.", "src/whospoke/evaluation/metrics.py, "
                 "docs/protocole-eval.md", rows)


def load_page(spec: moteurs.EngineSpec, root: Path) -> Page:
    """Page d'un moteur, lue depuis la racine de dépôt `root` (lecture seule)."""
    page = Page(spec)
    try:
        path = execution_file(spec, root)
    except moteurs.EngineUnavailable as error:
        page.unavailable = str(error)
        return page
    execution = json.loads(path.read_text())
    effective = execution.get("configuration_effective")
    if not effective:
        page.unavailable = f"{path.name} ne contient pas de configuration_effective"
        return page
    catalogue = load_catalogue(root)
    entries = catalogue["moteurs"].get(spec.pipeline, {})
    steps = catalogue["etapes"]
    config = moteurs.source_config(spec, root / "experiments")

    page.execution = str(path.relative_to(root))
    page.device = execution.get("device", "")
    page.date = execution.get("date_fin", "")
    page.commit = (execution.get("git_commit") or "")[:7]
    page.versions = execution.get("versions") or {}
    page.stages.append(_common_normalisation(catalogue, page))
    configured = set()
    for step, settings in effective.items():
        if step not in steps:
            page.wrong_step.append(f"étape « {step} » absente du catalogue")
        rows = []
        for setting in settings:
            name = setting["nom"]
            configured.add(name)
            entry = entries.get(name)
            if entry is None:
                page.not_catalogued.append(f"{name} ({step})")
            elif entry["etape"] != step:
                page.wrong_step.append(f"{name} : étape « {step} » dans la configuration, « {entry['etape']} » au catalogue")
            if name.endswith(".revision"):
                continue  # affiché avec son modèle
            rows.append(_row(setting, settings, entry))
        page.stages.append(Stage(
            id=step, label=steps.get(step, {}).get("libelle", step), family=FAMILIES.get(step, "Autre"),
            role=steps.get(step, {}).get("role", ""), defined_in=SOURCE_FILES.get(spec.pipeline, ""), rows=rows,
        ))
    page.not_configured += sorted(set(entries) - configured)
    page.evaluation = _evaluation(config)
    _attach_constats(page, root, set(steps))
    page.stages = _grouped(page.stages, _groups(catalogue, spec.pipeline))
    values = {setting["nom"]: setting["valeur"] for setting in audio.describe_normalisation()}
    values.update({setting["nom"]: setting["valeur"] for settings in effective.values() for setting in settings})
    _shapes(page, _section(catalogue, "formes"), values)
    _number(page)
    page.errors = source_errors(spec, root)
    return page


def _section(catalogue: dict, name: str) -> dict:
    """Section du catalogue de `--depot`, à défaut celle du catalogue de ce code."""
    section = catalogue.get(name)
    if section is None:
        from whospoke.pipelines.base import load_catalogue as own_catalogue

        section = own_catalogue().get(name) or {}
    return section


_PLACEHOLDER = re.compile(r"\{([^{}]+)\}")


def _shapes(page: Page, formes: dict, values: dict) -> None:
    """Forme des données en sortie de chaque étape (bloc : sa dernière étape), lue dans le
    catalogue et remplie avec les réglages en vigueur ; un réglage absent laisse l'étiquette
    générique et l'écart est signalé, comme les autres écarts de la page."""
    templates = {**(formes.get("communs") or {}), **(formes.get(page.spec.pipeline) or {})}
    for stage in page.stages:
        key = stage.parts[-1].id if stage.parts else stage.id
        entry = templates.get(key)
        if not entry:
            page.shape_gaps.append(f"forme des données après « {stage.label} » absente du catalogue")
            continue
        missing = [name for name in _PLACEHOLDER.findall(entry["modele"]) if values.get(name) is None]
        if missing:
            stage.shape = entry.get("generique", "")
            page.shape_gaps.append(f"forme des données après « {stage.label} » : "
                                   f"{', '.join(missing)} absent de la configuration effective")
        else:
            stage.shape = _PLACEHOLDER.sub(lambda m: format_value(m.group(1), values[m.group(1)]), entry["modele"])


def _number(page: Page) -> None:
    n = 0
    for stage in page.stages:
        if stage.parts:
            first = n + 1
            for part in stage.parts:
                n += 1
                part.number = str(n)
            stage.number = f"{first}–{n}"
        else:
            n += 1
            stage.number = str(n)


def source_errors(spec: moteurs.EngineSpec, root: Path) -> dict | None:
    """DER test sans collar de l'expérience source (premier corpus évalué en test) et ses
    trois composantes, en points de DER ; None si elle n'a pas de résultat de test."""
    try:
        directory = moteurs.experiment_dir(spec.source_exp, root / "experiments")
    except moteurs.EngineUnavailable:
        return None
    for path in sorted(directory.glob("results_*_test.json")):
        try:
            data = json.loads(path.read_text())
            c0 = data["metriques"]["collar_0"]
            parts = {key: float(c0[key]) for key in ("manquee", "fausse_alarme", "confusion")}
            return {"exp": spec.source_exp, "corpus": data["donnees"]["corpus"], "der": float(c0["der"]),
                    "composantes": parts}
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None


def _groups(catalogue: dict, pipeline_name: str) -> list[dict]:
    """Regroupements d'étapes du moteur : catalogue de `--depot`, à défaut celui de ce code."""
    groups = catalogue.get("regroupements")
    if groups is None:
        from whospoke.pipelines.base import load_catalogue as own_catalogue

        groups = own_catalogue().get("regroupements") or {}
    return list(groups.get(pipeline_name) or [])


def _grouped(stages: list[Stage], groups: list[dict]) -> list[Stage]:
    """Étapes d'un même réseau réunies dans un bloc, à la place de la première d'entre elles ;
    chacune garde ses réglages et ses constats."""
    for group in groups:
        members = [stage for stage in stages if stage.id in group.get("etapes", [])]
        if len(members) < 2:
            continue
        order = {step: i for i, step in enumerate(group["etapes"])}
        members.sort(key=lambda stage: order[stage.id])
        block = Stage(id=group["id"], label=group.get("libelle", group["id"]), family=members[0].family,
                      role=group.get("role", ""), defined_in=members[0].defined_in, rows=[], parts=members)
        position = min(stages.index(stage) for stage in members)
        stages = [stage for stage in stages if stage not in members]
        stages.insert(position, block)
    return stages


def _attach_constats(page: Page, root: Path, known_steps: set[str]) -> None:
    data = constats_file.read(root)
    page.constat_issues += data.problems
    by_step = {stage.id: stage for stage in page.stages}
    by_step[constats_file.EVALUATION] = page.evaluation
    for constat in data.items:
        if constat.etape not in known_steps and constat.etape != constats_file.EVALUATION:
            page.constat_issues.append(f"constat {constat.id} : étape « {constat.etape} » absente du catalogue")
            continue
        stage = by_step.get(constat.etape)
        if stage is not None and constat.concerns(page.spec.key):
            stage.constats.append(constat)


# --- Rendu -------------------------------------------------------------------------


def _row_html(row: Row) -> str:
    origin = ORIGIN_LABELS.get(row.origin, row.origin or "—")
    decision = f'<span class="sub">{escape(row.decision)}</span>' if row.decision else ""
    chips = "".join(f'<span class="pl-chip">{escape(c)}</span>' for c in row.components) or "—"
    effect = escape(row.effect) if row.effect else '<em>absent du catalogue</em>'
    revision = ""
    if row.revision is not None:
        cls = "pl-rev pl-rev-missing" if row.revision == NO_REVISION else "pl-rev"
        text = row.revision if row.revision == NO_REVISION else f"révision {row.revision[:7]}"
        revision = f'<span class="{cls}" title="{escape(row.revision)}">{escape(text)}</span>'
    flag = "" if row.catalogued else ' class="pl-uncatalogued"'
    name = "" if row.label == row.name else f'<span class="sub"><code>{escape(row.name)}</code></span>'
    return (f'<tr{flag}><td><span class="strong">{escape(row.label)}</span>{name}</td>'
            f'<td>{escape(row.value)}{revision}</td><td>{escape(origin)}{decision}</td>'
            f'<td>{effect}</td><td>{chips}</td></tr>')


CONFIDENCE = {"certain": "certain", "probable": "probable", "incertain": "incertain"}


def _constats_html(constats: list, label: str | None = None) -> str:
    if not constats:
        return ""
    items = "".join(
        f'<li><p>{escape(c.texte)}</p><p class="pl-constat-meta">'
        f'<span class="ws-conf ws-conf-{escape(c.confiance)}">{escape(CONFIDENCE.get(c.confiance, c.confiance))}</span>'
        f'<span class="sub">{escape(c.id)} · sources : {escape(", ".join(c.sources) or "—")}</span></p></li>'
        for c in constats)
    title = "Constats mesurés" + (f" : {label}" if label else "")
    return (f'<div class="pl-constats"><p class="pl-constats-title">{escape(title)}</p>'
            f'<ul class="pl-constats-list">{items}</ul></div>')


def _table_html(rows: list[Row]) -> str:
    return ('<div class="ws-table-wrap"><table class="ws-table pl-table"><thead><tr>'
            '<th scope="col">Réglage</th><th scope="col">Valeur en vigueur</th><th scope="col">Origine</th>'
            '<th scope="col">Ce que ça fait</th><th scope="col">Joue sur</th></tr></thead>'
            f'<tbody>{"".join(_row_html(row) for row in rows)}</tbody></table></div>')


def _model_short(row: Row) -> str:
    """« WeSpeakerResNet34 » ou « spkrec-ecapa-voxceleb » : architecture entre parenthèses,
    sinon dernier élément du nom du dépôt."""
    match = re.search(r"\(([^()]+)\)", row.value)
    if match:
        return match.group(1)
    return row.value.split("@")[0].rstrip("/").rsplit("/", 1)[-1]


def _subtitle(stage: Stage) -> tuple[str, str]:
    """(modèle, révision abrégée) d'une étape, ou (famille, "") sans modèle."""
    models = stage.models
    if not models:
        return stage.family, ""
    row = models[0]
    revision = "" if row.revision in (None, NO_REVISION) else row.revision[:7]
    return _model_short(row), revision


def _stage_html(stage: Stage, selected: bool) -> str:
    models = "".join(f'<li>{escape(row.value)} — {escape(row.revision or NO_REVISION)}</li>' for row in stage.models)
    errors = ", ".join(stage.errors) or "aucune erreur propre"
    if stage.parts:
        # Bloc d'un même réseau : réglages et constats de chaque étape, sous son nom.
        body = "".join(
            f'<section class="pl-part" aria-label="{escape(part.label)}"><h4 class="pl-part-title">'
            f'{escape(part.number)}. {escape(part.label)}<span class="sub">{escape(part.role)}</span></h4>'
            + (_table_html(part.rows) if part.rows else '<p class="ws-empty-note">Aucun réglage propre.</p>')
            + _constats_html(part.constats, part.label) + "</section>"
            for part in stage.parts)
    else:
        body = _table_html(stage.rows) + _constats_html(stage.constats)
    step = f"Étape {stage.number} · " if stage.number else ""
    return (
        f'<section class="pl-sheet" id="pl-sheet-{stage.id}" role="tabpanel" aria-labelledby="pl-tab-{stage.id}" '
        f'tabindex="0" data-stage="{stage.id}"{"" if selected else " hidden"}>'
        f'<p class="pl-family">{escape(step + stage.family)}</p><h3>{escape(stage.label)}</h3>'
        f'<p class="pl-role">{escape(stage.role)}</p>'
        '<dl class="pl-facts">'
        + (f'<div><dt>Modèle</dt><dd><ul>{models}</ul></dd></div>' if models else "")
        + f'<div><dt>Erreurs produites</dt><dd>{escape(errors)}</dd></div>'
        + (f'<div><dt>Forme des données en sortie</dt><dd>{escape(stage.shape)}</dd></div>' if stage.shape else "")
        + f'<div><dt>Défini dans</dt><dd><code>{escape(stage.defined_in)}</code></dd></div></dl>'
        f'{body}</section>'
    )


# --- Schéma de gauche à droite (audit visuel du 02/11, §6 ; B12) ------------------------
# SVG en unités propres, mis à l'échelle de la carte : sans retour à la ligne dès 840 px,
# lisible à 1280 × 720. Les étapes sont des onglets (role="tab") d'une liste d'onglets ;
# leur fiche s'affiche sous le schéma. Le texte est coupé ici, avec les tailles du mode
# présentation (les plus grandes), pour tenir dans les deux modes.

VIEW_W = 1180
GAP = 18          # flèche entre deux étapes
INNER = 10        # entre deux étapes d'un même réseau
SEP = 36          # avant l'Évaluation, détachée derrière un filet pointillé
FRAME = 6         # marge du cadre « un seul réseau »
TOP = 28          # place de l'intitulé du cadre
NODE_H = 168
SHAPE_DY = 20     # première ligne de la forme des données, sous les étapes
# Tailles du mode présentation (interface.css), les plus grandes : le texte coupé pour elles
# tient aussi en taille normale.
FONT = {"title": 12.5, "sub": 12, "badge": 11.5, "shape": 12}
# Composantes du DER dans le badge d'une étape, en mots courts ; les autres effets (frontières,
# nombre de locuteurs) restent dans la fiche de l'étape.
BADGE = {"parole manquée": "manquée", "fausse alarme": "fausse alarme", "confusion": "confusion"}
CORPORA = {"summre": "SUMM-RE", "ami": "AMI"}


def _wrap(text: str, width: float, size: float, bold: bool = False, lines: int = 3) -> list[str]:
    """Lignes de `text` tenant dans `width` unités (largeur moyenne d'un caractère : 0,52 em,
    mesurée sur les polices système ; 0,55 em en gras) ; la dernière finit par « … » si le
    texte dépasse `lines` lignes. Un mot plus long qu'une ligne reste entier."""
    per_char = size * (0.55 if bold else 0.52)
    limit = max(4, int(width / per_char))
    out, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) <= limit or not current:
            current = candidate
        else:
            out.append(current)
            current = word
    if current:
        out.append(current)
    if len(out) > lines:
        out = out[:lines]
        out[-1] = out[-1][: max(1, limit - 1)].rstrip() + "…"
    return out


def _text(lines: list[str], x: float, y: float, step: float, cls: str, anchor: str = "start") -> str:
    spans = "".join(f'<tspan x="{x:.1f}" dy="{0 if i == 0 else step}">{escape(line)}</tspan>'
                    for i, line in enumerate(lines))
    return f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}">{spans}</text>'


# Aperçus de 24 px, schématiques et statiques : la page ne dispose pas des données d'un
# fichier. Couleurs des locuteurs pour la segmentation et le regroupement seulement.
_WAVE = (0.2, 0.7, 0.4, 0.95, 0.3, 0.6, 0.15, 0.8, 0.5, 0.25, 0.9, 0.35, 0.65, 0.2, 0.75, 0.45)
_DOTS = ((0.1, 0.3), (0.18, 0.7), (0.27, 0.45), (0.35, 0.2), (0.44, 0.8), (0.52, 0.5), (0.6, 0.25),
         (0.68, 0.65), (0.76, 0.4), (0.85, 0.75), (0.92, 0.3))


def _preview(step: str, x: float, y: float, w: float) -> str:
    h = 24
    if step == "normalisation":
        points = " ".join(f"{x + w * i / (len(_WAVE) - 1):.1f},{y + h / 2 + (h / 2 - 2) * v * (-1) ** i:.1f}"
                          for i, v in enumerate(_WAVE))
        return f'<polyline class="pl-pv-line" points="{points}"/>'
    if step in ("analyse", "normalisation_cepstrale"):
        bars, n = [], 18
        for i in range(n):
            v = _WAVE[i % len(_WAVE)]
            bh = max(3, (h - 2) * v)
            top = y + (h - bh) / 2 if step == "normalisation_cepstrale" else y + h - bh
            bars.append(f'<rect class="pl-pv-ink" x="{x + w * i / n:.1f}" y="{top:.1f}" width="{w / n * 0.6:.1f}" height="{bh:.1f}"/>')
        return "".join(bars)
    if step == "detection":
        spans = ((0.0, 0.22), (0.3, 0.55), (0.62, 0.78), (0.85, 1.0))
        return "".join(f'<rect class="pl-pv-ink" x="{x + w * a:.1f}" y="{y + 8}" width="{w * (b - a):.1f}" height="8" rx="2"/>'
                       for a, b in spans)
    if step == "segmentation":
        rows = (((0.0, 0.3), (0.62, 0.8)), ((0.25, 0.55),), ((0.5, 0.7), (0.85, 1.0)))
        return "".join(f'<rect class="pl-spk-{k + 1}" x="{x + w * a:.1f}" y="{y + 1 + 8 * k}" width="{w * (b - a):.1f}" height="6" rx="2"/>'
                       for k, row in enumerate(rows) for a, b in row)
    if step in ("empreintes", "representation"):
        return "".join(f'<circle class="pl-pv-ink" cx="{x + w * a:.1f}" cy="{y + 3 + (h - 6) * b:.1f}" r="2.4"/>'
                       for a, b in _DOTS)
    if step == "regroupement":
        return "".join(f'<circle class="pl-spk-{1 + min(2, int(a * 3))}" cx="{x + w * a:.1f}" cy="{y + 3 + (h - 6) * b:.1f}" r="2.8"/>'
                       for a, b in _DOTS)
    if step in ("attribution", "sortie"):
        spans = ((0.0, 0.18), (0.22, 0.5), (0.55, 0.7), (0.74, 1.0))
        return "".join(f'<rect class="pl-pv-soft" x="{x + w * a:.1f}" y="{y + 4 + 6 * (i % 3)}" width="{w * (b - a):.1f}" height="4" rx="2"/>'
                       for i, (a, b) in enumerate(spans))
    if step == "evaluation":
        return (f'<rect class="pl-pv-ink" x="{x:.1f}" y="{y + 4}" width="{w * 0.7:.1f}" height="5" rx="2"/>'
                f'<rect class="pl-pv-dash" x="{x + w * 0.1:.1f}" y="{y + 14}" width="{w * 0.75:.1f}" height="5" rx="2"/>')
    return ""


def _box(stage: Stage, x: float, y: float, w: float, evaluation: bool = False) -> str:
    """Une étape : numéro, titre, modèle et révision abrégée, aperçu, badge d'erreurs en texte."""
    pad = 8
    inner = w - 2 * pad
    model, revision = _subtitle(stage)
    title = _wrap(stage.label, inner, FONT["title"], bold=True, lines=3)
    sub = _wrap(model, inner, FONT["sub"], lines=2)
    errors = " · ".join(BADGE[e] for e in stage.errors if e in BADGE) if not evaluation else "mesure seulement"
    badge = _wrap(errors or "aucune erreur du DER", inner, FONT["badge"], lines=2)
    parts = [f'<rect class="pl-box{" pl-box-eval" if evaluation else ""}" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" '
             f'height="{NODE_H}" rx="8"/>']
    count = len(stage.all_constats)
    if count:
        parts.append(f'<text class="pl-n-meta" x="{x + w - pad:.1f}" y="{y + 22}" text-anchor="end">'
                     f'{count} constat{"s" if count > 1 else ""}</text>')
    if stage.number:
        parts.append(f'<circle class="pl-num" cx="{x + pad + 9:.1f}" cy="{y + 18}" r="9"/>'
                     f'<text class="pl-num-text" x="{x + pad + 9:.1f}" y="{y + 21.5}" text-anchor="middle">'
                     f'{escape(stage.number)}</text>')
    parts.append(_text(title, x + pad, y + 46, 15, "pl-n-title"))
    sub_y = y + 46 + 15 * len(title) + 2
    parts.append(_text(sub, x + pad, sub_y, 13, "pl-n-sub"))
    if revision:
        parts.append(f'<text class="pl-n-rev" x="{x + pad:.1f}" y="{sub_y + 13 * len(sub):.1f}">{escape(revision)}</text>')
    parts.append(_preview("evaluation" if evaluation else stage.id, x + pad, y + NODE_H - 64, inner))
    parts.append(_text(badge, x + pad, y + NODE_H - 24, 12, "pl-n-badge"))
    return "".join(parts)


def _diagram(page: Page, selected: str) -> str:
    stages = page.stages
    units = sum(len(stage.parts) or 1 for stage in stages) + 1
    inner_gaps = sum(len(stage.parts) - 1 for stage in stages if stage.parts)
    frames = sum(1 for stage in stages if stage.parts)
    unit = (VIEW_W - GAP * (len(stages) - 1) - SEP - INNER * inner_gaps - 2 * FRAME * frames) / units
    y = TOP
    nodes, arrows, shapes = [], [], []
    x = 0.0

    def tab(stage: Stage, content: str, label: str) -> str:
        chosen = stage.id == selected
        return (f'<g class="pl-node" role="tab" id="pl-tab-{stage.id}" data-stage="{stage.id}" '
                f'aria-selected="{str(chosen).lower()}" aria-controls="pl-sheet-{stage.id}" '
                f'tabindex="{0 if chosen else -1}" aria-label="{escape(label, quote=True)}">{content}</g>')

    def arrow(x1: float, x2: float, shape: str, dashed: bool = False) -> None:
        mid = y + NODE_H / 2
        cls = "pl-arrow pl-arrow-dash" if dashed else "pl-arrow"
        arrows.append(f'<line class="{cls}" x1="{x1 + 2:.1f}" y1="{mid}" x2="{x2 - 6:.1f}" y2="{mid}"/>'
                      f'<path class="pl-arrow-head" d="M{x2 - 7:.1f} {mid - 4} L{x2 - 1:.1f} {mid} L{x2 - 7:.1f} {mid + 4} Z"/>')
        if shape:
            width = unit + GAP - 8
            lines = _wrap(shape, width, FONT["shape"], lines=3)
            shapes.append(_text(lines, (x1 + x2) / 2, y + NODE_H + SHAPE_DY, 13, "pl-n-shape", "middle"))

    for index, stage in enumerate(stages):
        model, revision = _subtitle(stage)
        count = len(stage.all_constats)
        label = f"Étape {stage.number} : {stage.label}" + (f", {model}" if stage.models else "") + (
            f" ; erreurs : {', '.join(stage.errors)}" if stage.errors else "") + (
            f" ; {count} constat{'s' if count > 1 else ''} mesuré{'s' if count > 1 else ''}" if count else "")
        if stage.parts:
            start = x
            x += FRAME
            content = []
            for k, part in enumerate(stage.parts):
                content.append(_box(part, x, y, unit))
                x += unit + (INNER if k < len(stage.parts) - 1 else 0)
            x += FRAME
            frame = (f'<rect class="pl-frame" x="{start:.1f}" y="{y - 22}" width="{x - start:.1f}" '
                     f'height="{NODE_H + 22 + FRAME}" rx="12"/>'
                     f'<text class="pl-frame-label" x="{start + 10:.1f}" y="{y - 7}">Un seul réseau : '
                     f'{escape(model)}</text>')
            nodes.append(tab(stage, frame + "".join(content), label + " ; un seul réseau"))
            right = x
        else:
            nodes.append(tab(stage, _box(stage, x, y, unit), label))
            x += unit
            right = x
        if index < len(stages) - 1:
            arrow(right, right + GAP, stage.shape)
            x += GAP
    # Évaluation, détachée derrière un filet pointillé : la sortie y est mesurée, rien n'en revient.
    sep_x = x + SEP / 2
    arrow(x, x + SEP, stages[-1].shape, dashed=True)
    x += SEP
    evaluation = page.evaluation
    nodes.append(tab(evaluation, _box(evaluation, x, y, unit, evaluation=True),
                     "Évaluation, mesure seulement : hors du pipeline"))
    separator = (f'<line class="pl-sep-line" x1="{sep_x:.1f}" y1="{y - 22}" x2="{sep_x:.1f}" '
                 f'y2="{y + NODE_H + 6}"/>')
    height = y + NODE_H + SHAPE_DY + 13 * 3 + 6
    return (f'<div class="pl-diagram-wrap" role="tablist" aria-label="Étapes du pipeline" aria-orientation="horizontal">'
            f'<svg class="pl-diagram" role="none" viewBox="0 0 {VIEW_W} {height}">{separator}{"".join(arrows)}{"".join(shapes)}{"".join(nodes)}</svg></div>')


# Étapes où naît chaque composante du DER : la première est sélectionnée, la seconde mise en
# évidence. La confusion naît surtout des empreintes (passer des MFCC à ECAPA la divise par
# trois, constat C05), puis du regroupement (retour du cockpit sur B12).
ERROR_PARTS = (("manquee", "Parole manquée", ("detection",)), ("fausse_alarme", "Fausse alarme", ("detection",)),
               ("confusion", "Confusion", ("empreintes", "representation", "regroupement")))


def _stage_of(page: Page, step: str) -> Stage | None:
    return next((stage for stage in page.stages if step in stage.step_ids), None)


def _targets(page: Page, steps: tuple[str, ...]) -> list[tuple[Stage, Stage]]:
    """(onglet, étape affichée) de chaque étape présente, dans l'ordre ; dans un bloc, l'étape
    elle-même est nommée, l'onglet restant celui du bloc."""
    found = []
    for step in steps:
        stage = _stage_of(page, step)
        if stage is not None and all(stage is not tab for tab, _ in found):
            part = next((x for x in stage.parts if x.id == step), stage)
            found.append((stage, part))
    return found


def _errors_bar(page: Page) -> str:
    """Naissance des erreurs : DER test sans collar de l'expérience source, empilé ; chaque
    segment sélectionne l'étape où l'erreur naît (et met en évidence la seconde)."""
    data = page.errors
    if not data:
        return (f'<p class="ws-empty-note pl-errors">{escape(page.spec.source_exp)} n\'a pas encore de résultat de '
                'test : barre de la naissance des erreurs indisponible.</p>')
    corpus = CORPORA.get(data["corpus"], data["corpus"])
    segments, legend = [], []
    for key, label, steps in ERROR_PARTS:
        value = data["composantes"][key]
        targets = _targets(page, steps)
        names = [shown.label for _, shown in targets]
        target = " et ".join([names[0], *[name[:1].lower() + name[1:] for name in names[1:]]]) if names else steps[0]
        numbers = " et ".join(shown.number for _, shown in targets)
        text = f"{label} : {formatage.unite(value, 'points', 2)}, naît à « {target} »" + (
            f" (étape{'s' if len(targets) > 1 else ''} {numbers})" if targets else "")
        if targets:
            tab = targets[0][0]
            attrs = f' data-stage="{tab.id}" aria-controls="pl-sheet-{tab.id}"'
            if len(targets) > 1:
                attrs += f' data-also="{targets[1][0].id}"'
        else:
            attrs = " disabled"
        segments.append(f'<button type="button" class="pl-errseg pl-err-{key}" style="flex-grow: {value:.4f}"{attrs} '
                        f'aria-label="{escape(text, quote=True)}" title="{escape(text, quote=True)}"></button>')
        legend.append(f'<li><span class="pl-errkey pl-err-{key}" aria-hidden="true"></span>'
                      f'<span>{escape(label)} {escape(formatage.pourcentage(value, 2))}</span>'
                      f'<span class="sub">→ {escape(target)}</span></li>')
    return (
        '<section class="pl-errors" aria-label="Naissance des erreurs">'
        f'<p class="pl-errors-head"><span class="strong">Naissance des erreurs</span> '
        f'<span class="sub">DER test sans collar de {escape(data["exp"])} ({escape(corpus)}) : '
        f'{escape(formatage.pourcentage(data["der"], 2))}</span></p>'
        f'<div class="pl-errbar" role="group" aria-label="Composantes du DER ; un clic sélectionne l\'étape">'
        f'{"".join(segments)}</div><ul class="pl-errlegend">{"".join(legend)}</ul>'
        '<p class="ws-caption">Attribution simplifiée : la parole manquée et la fausse alarme naissent surtout à '
        'la détection de la parole, la confusion aux empreintes et au regroupement (passer des MFCC à ECAPA '
        'divise la confusion par trois, constat C05) ; une erreur peut avoir plusieurs causes en amont.</p></section>'
    )


def _kv(rows: list[Row]) -> str:
    if not rows:
        return '<p class="ws-empty-note">Aucun réglage propre.</p>'
    return ('<dl class="pl-kv">' + "".join(f'<div><dt>{escape(row.label)}</dt><dd>{escape(row.value)}</dd></div>'
                                           for row in rows) + "</dl>")


def _stepper(page: Page) -> str:
    """Petit écran : liste numérotée verticale, une étape dépliée à la fois, réglages en
    liste « clé : valeur » ; la forme des données entre deux étapes."""
    items = []
    for stage in [*page.stages, page.evaluation]:
        evaluation = stage is page.evaluation
        model, revision = _subtitle(stage)
        sub = "mesure seulement" if evaluation else (" · ".join(stage.errors) or "aucune erreur propre")
        if stage.parts:
            body = "".join(f'<h4 class="pl-part-title">{escape(part.number)}. {escape(part.label)}</h4>{_kv(part.rows)}'
                           for part in stage.parts)
        else:
            body = _kv(stage.rows)
        model_line = (f'<p class="pl-st-model">{escape(model)}'
                      + (f' <span class="pl-rev">révision {escape(revision)}</span>' if revision else "") + "</p>"
                      if stage.models else "")
        items.append(
            f'<li class="pl-st{" pl-st-eval" if evaluation else ""}">'
            f'<button type="button" class="pl-st-toggle" aria-expanded="false" aria-controls="pl-st-{stage.id}">'
            f'<span class="pl-st-num" aria-hidden="true">{escape(stage.number or "·")}</span>'
            f'<span class="pl-st-text"><span class="pl-st-title">{escape(stage.label)}</span>'
            f'<span class="pl-st-sub">{escape(sub)}</span></span></button>'
            f'<div class="pl-st-panel" id="pl-st-{stage.id}" hidden><p class="pl-role">{escape(stage.role)}</p>'
            f'{model_line}{body}</div>'
            + (f'<p class="pl-st-shape"><span aria-hidden="true">↓</span> {escape(stage.shape)}</p>'
               if stage.shape and not evaluation else "")
            + "</li>")
    return f'<ol class="pl-stepper" aria-label="Étapes du pipeline">{"".join(items)}</ol>'


def render(page: Page) -> str:
    spec = page.spec
    if page.unavailable:
        return (f'<div class="pl-root"><p class="ws-empty-note">{escape(spec.label)} : configuration '
                f'effective indisponible ({escape(page.unavailable)}). Elle sera affichée dès que '
                f'{escape(spec.source_exp)} aura été exécutée.</p></div>')
    versions = ", ".join(f"{escape(k)} {escape(str(v))}" for k, v in page.versions.items() if k != "python")
    head = (f'<p class="pl-meta">Expérience source <strong>{escape(spec.source_exp)}</strong> · exécution '
            f'<code>{escape(page.device)}</code> du {escape(formatage.date(page.date))} · commit <code>{escape(page.commit)}</code>'
            + (f" · {versions}" if versions else "") + f' · <code>{escape(page.execution)}</code></p>')
    issues = []
    if page.not_catalogued:
        issues.append("Dans la configuration, absents du catalogue : " + ", ".join(page.not_catalogued))
    if page.not_configured:
        issues.append(f"Au catalogue du moteur « {spec.pipeline} », absents de cette configuration : "
                      + ", ".join(page.not_configured))
    if page.wrong_step:
        issues.append("Étape différente : " + " ; ".join(page.wrong_step))
    if page.shape_gaps:
        issues.append("Formes des données : " + " ; ".join(page.shape_gaps))
    if page.constat_issues:
        issues.append("docs/constats.yaml : " + " ; ".join(page.constat_issues))
    callout = ""
    if issues:
        callout = ('<div class="pl-issues" role="note"><p class="strong">Écarts entre la configuration et le '
                   'catalogue</p><ul>' + "".join(f"<li>{escape(i)}</li>" for i in issues) + "</ul></div>")
    first = page.stages[1].id if len(page.stages) > 1 else page.stages[0].id
    sheets = "".join(_stage_html(stage, stage.id == first) for stage in page.stages)
    sheets += _stage_html(page.evaluation, False)
    return (
        f'<div class="pl-root">{head}{callout}{_diagram(page, first)}{_errors_bar(page)}'
        f'<div class="pl-sheets">{sheets}</div>{_stepper(page)}'
        f'<p class="ws-caption">Lecture seule : toute modification passe par une fiche de décision '
        f'et une expérience (D17).</p></div>'
    )
