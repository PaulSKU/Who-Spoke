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


def format_value(name: str, value) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "oui" if value else "non"
    if isinstance(value, float):
        text = f"{value:.6g}".replace(".", ",")
        return text + (" s" if name.endswith("_s") else "")
    if isinstance(value, int):
        return str(value) + (" s" if name.endswith("_s") else " Hz" if name.endswith("_hz") else "")
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
        + (" (principale)" if i == 0 else f" (± {format_value('', metrics[name].collar / 2)} s)")
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
    return page


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
        f'<span class="av-confidence av-conf-{escape(c.confiance)}">{escape(CONFIDENCE.get(c.confiance, c.confiance))}</span>'
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


def _stage_html(stage: Stage, selected: bool) -> str:
    models = "".join(f'<li>{escape(row.value)} — {escape(row.revision or NO_REVISION)}</li>' for row in stage.models)
    errors = ", ".join(stage.errors) or "aucune erreur propre"
    if stage.parts:
        # Bloc d'un même réseau : réglages et constats de chaque étape, sous son nom.
        body = "".join(
            f'<section class="pl-part" aria-label="{escape(part.label)}"><h4 class="pl-part-title">{escape(part.label)}'
            f'<span class="sub">{escape(part.role)}</span></h4>'
            + (_table_html(part.rows) if part.rows else '<p class="ws-empty-note">Aucun réglage propre.</p>')
            + _constats_html(part.constats, part.label) + "</section>"
            for part in stage.parts)
    else:
        body = _table_html(stage.rows) + _constats_html(stage.constats)
    return (
        f'<section class="pl-sheet" data-stage="{stage.id}" aria-label="{escape(stage.label)}"'
        f'{"" if selected else " hidden"}>'
        f'<p class="pl-family">{escape(stage.family)}</p><h3>{escape(stage.label)}</h3>'
        f'<p class="pl-role">{escape(stage.role)}</p>'
        '<dl class="pl-facts">'
        + (f'<div><dt>Modèle</dt><dd><ul>{models}</ul></dd></div>' if models else "")
        + f'<div><dt>Erreurs produites</dt><dd>{escape(errors)}</dd></div>'
        f'<div><dt>Défini dans</dt><dd><code>{escape(stage.defined_in)}</code></dd></div></dl>'
        f'{body}</section>'
    )


def _button(stage: Stage, selected: bool, evaluation: bool = False) -> str:
    cls = "pl-step pl-eval" if evaluation else "pl-step"
    count = len(stage.all_constats)
    measured = f" · {count} constat{'s' if count > 1 else ''}" if count else ""
    return (f'<button type="button" class="{cls}" data-stage="{stage.id}" aria-pressed="{str(selected).lower()}">'
            f'<span class="pl-step-name">{escape(stage.label)}</span>'
            f'<span class="pl-step-family">{escape(stage.family)}{measured}</span></button>')


def render(page: Page) -> str:
    spec = page.spec
    if page.unavailable:
        return (f'<div class="pl-root"><p class="ws-empty-note">{escape(spec.label)} : configuration '
                f'effective indisponible ({escape(page.unavailable)}). Elle sera affichée dès que '
                f'{escape(spec.source_exp)} aura été exécutée.</p></div>')
    versions = ", ".join(f"{escape(k)} {escape(str(v))}" for k, v in page.versions.items() if k != "python")
    head = (f'<p class="pl-meta">Expérience source <strong>{escape(spec.source_exp)}</strong> · exécution '
            f'<code>{escape(page.device)}</code> du {escape(page.date[:10])} · commit <code>{escape(page.commit)}</code>'
            + (f" · {versions}" if versions else "") + f' · <code>{escape(page.execution)}</code></p>')
    issues = []
    if page.not_catalogued:
        issues.append("Dans la configuration, absents du catalogue : " + ", ".join(page.not_catalogued))
    if page.not_configured:
        issues.append(f"Au catalogue du moteur « {spec.pipeline} », absents de cette configuration : "
                      + ", ".join(page.not_configured))
    if page.wrong_step:
        issues.append("Étape différente : " + " ; ".join(page.wrong_step))
    if page.constat_issues:
        issues.append("docs/constats.yaml : " + " ; ".join(page.constat_issues))
    callout = ""
    if issues:
        callout = ('<div class="pl-issues" role="note"><p class="strong">Écarts entre la configuration et le '
                   'catalogue</p><ul>' + "".join(f"<li>{escape(i)}</li>" for i in issues) + "</ul></div>")
    first = page.stages[1].id if len(page.stages) > 1 else page.stages[0].id
    flow = '<span class="pl-arrow" aria-hidden="true">→</span>'.join(
        _button(stage, stage.id == first) for stage in page.stages)
    sheets = "".join(_stage_html(stage, stage.id == first) for stage in page.stages)
    sheets += _stage_html(page.evaluation, False)
    return (
        f'<div class="pl-root">{head}{callout}'
        f'<nav class="pl-flow" aria-label="Étapes du pipeline">{flow}'
        f'<span class="pl-sep" aria-hidden="true"></span>{_button(page.evaluation, False, evaluation=True)}</nav>'
        f'{sheets}<p class="ws-caption">Lecture seule : toute modification passe par une fiche de décision '
        f'et une expérience (D17).</p></div>'
    )
