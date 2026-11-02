"""Graphique de l'onglet Avancement (audit R-U7) : DER test sans collar des systèmes de
référence, décomposé en parole manquée, fausse alarme et confusion, par corpus.

SVG généré côté serveur, sans bibliothèque ni ressource distante. Méthode du skill
dataviz : barres horizontales empilées (une seule échelle), 20 px d'épaisseur, 2 px de
surface entre segments, bout arrondi de 4 px côté données seulement, grille en filet ;
couleurs = trois premiers emplacements de la palette catégorielle de l'application,
validés en clair et en sombre (`validate_palette.js`, contraste ≥ 3:1 compris), doublés
des motifs de la carte des erreurs de l'Analyse (parole manquée pleine, fausse alarme
hachurée, confusion en contour : un même type d'erreur a la même apparence partout,
décision du cockpit du 01/11) ; légende toujours présente ; valeur du DER écrite au bout de chaque
barre ; titre et description pour les lecteurs d'écran, info-bulle par segment, et
tableau des valeurs. Les teintes sont des variables CSS (`--av-err-*` dans
`interface.css`) : le même SVG se lit en clair et en sombre.

Deux mises en page du même graphique : large (étiquettes à gauche) et étroite (étiquette
au-dessus de la barre, pour 375 px) ; la feuille de style montre l'une ou l'autre.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from html import escape

from app import formatage

KINDS = (("manquee", "Parole manquée"), ("fausse_alarme", "Fausse alarme"), ("confusion", "Confusion"))
# Motifs de la carte des erreurs (`visualiseur.css`) : plein, hachures, contour.
STYLES = {"manquee": "plein", "fausse_alarme": "hachures", "confusion": "contour"}
OUTLINE = 1.5     # épaisseur du contour (hachures et contour), comme la carte des erreurs

BAR = 20          # épaisseur d'une barre
GAP = 2           # surface entre deux segments
RADIUS = 4        # bout arrondi, côté données


@dataclass
class Bar:
    label: str            # système
    sub: str              # expérience source
    exp_id: str
    values: dict          # manquee, fausse_alarme, confusion (points de DER)
    der: float


def _num(value: float, digits: int = 2) -> str:
    return formatage.nombre(value, digits)


def _pct(value: float) -> str:
    return formatage.pourcentage(value, 2)


def _scale_max(groups: list[tuple[str, list[Bar]]]) -> int:
    top = max((bar.der for _, bars in groups for bar in bars), default=10.0)
    return max(10, int(math.ceil(top / 10.0)) * 10)


def _ticks(maximum: int) -> list[int]:
    step = 10 if maximum <= 50 else 20
    return list(range(0, maximum + 1, step))


def _paint(kind: str, uid: str) -> str:
    """Remplissage et trait d'un segment ou d'une pastille de légende, selon son motif."""
    color = f"var(--av-err-{kind})"
    style = STYLES[kind]
    if style == "plein":
        return f"fill:{color}"
    fill = f"url(#{uid}-{kind})" if style == "hachures" else "var(--ws-surface)"
    return f"fill:{fill};stroke:{color};stroke-width:{OUTLINE}"


def _shape(x: float, y: float, width: float, height: float, rounded: bool) -> str:
    """Chemin d'un rectangle, bout droit arrondi de 4 px si `rounded`."""
    r = min(RADIUS, width, height / 2) if rounded else 0
    if r <= 0:
        return f"M{x:.2f},{y:.2f} H{x + width:.2f} V{y + height:.2f} H{x:.2f} Z"
    right = x + width
    return (f"M{x:.2f},{y:.2f} H{right - r:.2f} Q{right:.2f},{y:.2f} {right:.2f},{y + r:.2f} "
            f"V{y + height - r:.2f} Q{right:.2f},{y + height:.2f} {right - r:.2f},{y + height:.2f} H{x:.2f} Z")


def _segment(x: float, y: float, width: float, kind: str, last: bool, uid: str, tip: str) -> str:
    """Un segment ; le dernier porte le bout arrondi de 4 px, les autres sont droits. Le
    contour est tracé à l'intérieur du segment (rectangle rentré d'un demi-trait)."""
    if width <= 0:
        return ""
    inset = OUTLINE / 2 if STYLES[kind] != "plein" else 0.0
    if width <= 2 * inset:
        inset = 0.0
    path = _shape(x + inset, y + inset, width - 2 * inset, BAR - 2 * inset, last and width > RADIUS)
    return f'<path class="av-seg" d="{path}" style="{_paint(kind, uid)}"><title>{escape(tip)}</title></path>'


def _bar(x0: float, y: float, span: float, maximum: int, bar: Bar, corpus: str, uid: str) -> str:
    present = [(kind, label) for kind, label in KINDS if (bar.values.get(kind) or 0) > 0]
    parts, x = [], x0
    for index, (kind, label) in enumerate(present):
        width = span * bar.values[kind] / maximum
        last = index == len(present) - 1
        drawn = width if last else max(0.0, width - GAP)
        tip = f"{bar.label} ({bar.exp_id}), {corpus} test : {label.lower()} {_pct(bar.values[kind])}"
        parts.append(_segment(x, y, drawn, kind, last, uid, tip))
        x += width
    return "".join(parts)


def _defs(uid: str) -> str:
    """Hachures de la fausse alarme : traits de 2 px tous les 5 px, inclinés comme ceux de
    la carte des erreurs, sur la surface."""
    patterns = []
    for kind, style in STYLES.items():
        if style != "hachures":
            continue
        patterns.append(
            f'<pattern id="{uid}-{kind}" width="5" height="5" patternUnits="userSpaceOnUse" '
            f'patternTransform="rotate(45)"><rect width="5" height="5" style="fill:var(--ws-surface)"/>'
            f'<rect width="2" height="5" style="fill:var(--av-err-{kind})"/></pattern>')
    return f"<defs>{''.join(patterns)}</defs>"


def _legend(x: float, y: float, vertical: bool, uid: str) -> tuple[str, float]:
    items, cx, cy = [], x, y
    for kind, label in KINDS:
        items.append(f'<rect x="{cx + 0.75:.2f}" y="{cy + 0.75}" width="12.5" height="12.5" rx="3" '
                     f'style="{_paint(kind, uid)}"/>'
                     f'<text class="av-txt" x="{cx + 20:.1f}" y="{cy + 11}">{escape(label)}</text>')
        if vertical:
            cy += 20
        else:
            cx += 30 + 7.2 * len(label)
    return "".join(items), (cy if vertical else cy + 20)


def svg(groups: list[tuple[str, list[Bar]]], narrow: bool, uid: str) -> str:
    """Un SVG accessible ; `groups` : [(corpus, barres)] dans l'ordre d'affichage."""
    maximum = _scale_max(groups)
    width = 340 if narrow else 760
    label_w = 0 if narrow else 214
    value_w = 66
    x0 = label_w
    span = width - label_w - value_w
    parts = [_defs(uid)]
    legend, y = _legend(0, 4, narrow, uid)
    parts.append(legend)
    y += 10
    top = y
    rows = []
    for corpus, bars in groups:
        rows.append(f'<text class="av-txt av-strong" x="0" y="{y + 14}">{escape(corpus)}, partition test</text>')
        y += 26
        for bar in bars:
            if narrow:
                rows.append(f'<text class="av-txt" x="0" y="{y + 12}">{escape(bar.label)}'
                            f'<tspan class="av-muted" dx="6">{escape(bar.sub)}</tspan></text>')
                y += 18
                label = ""
            else:
                label = (f'<text class="av-txt" x="0" y="{y + 9}">{escape(bar.label)}</text>'
                         f'<text class="av-muted av-small" x="0" y="{y + 22}">{escape(bar.sub)}</text>')
            end = x0 + span * bar.der / maximum
            rows.append(label + _bar(x0, y, span, maximum, bar, corpus, uid)
                        + f'<text class="av-txt av-strong" x="{end + 6:.1f}" y="{y + 14}">{_pct(bar.der)}</text>')
            y += BAR + (14 if narrow else 16)
        y += 6
    grid = "".join(
        f'<line class="av-grid" x1="{x0 + span * t / maximum:.1f}" y1="{top}" x2="{x0 + span * t / maximum:.1f}" '
        f'y2="{y}"/>' for t in _ticks(maximum))
    axis = "".join(
        f'<text class="av-muted av-small" x="{x0 + span * t / maximum:.1f}" y="{y + 14}" '
        f'text-anchor="{"start" if t == 0 else "middle"}">{t} %</text>' for t in _ticks(maximum))
    height = y + 22
    description = " ; ".join(
        f"{corpus} : " + ", ".join(
            f"{bar.label} {_pct(bar.der)} (parole manquée {_pct(bar.values.get('manquee') or 0)}, "
            f"fausse alarme {_pct(bar.values.get('fausse_alarme') or 0)}, "
            f"confusion {_pct(bar.values.get('confusion') or 0)})" for bar in bars)
        for corpus, bars in groups)
    return (
        f'<svg class="av-chart" viewBox="0 0 {width} {height}" width="100%" role="img" '
        f'aria-labelledby="{uid}-t {uid}-d" xmlns="http://www.w3.org/2000/svg">'
        f'<title id="{uid}-t">DER test sans collar des systèmes de référence, par corpus</title>'
        f'<desc id="{uid}-d">{escape(description)}.</desc>'
        f'{grid}{"".join(parts)}{"".join(rows)}{axis}</svg>'
    )


def table(groups: list[tuple[str, list[Bar]]]) -> str:
    """Tableau des valeurs du graphique (vue sans graphique)."""
    rows = []
    for corpus, bars in groups:
        for bar in bars:
            values = "".join(f'<td class="num">{_pct(bar.values.get(kind) or 0)}</td>' for kind, _ in KINDS)
            rows.append(f'<tr><td>{escape(corpus)}</td><td>{escape(bar.label)}<span class="sub">{escape(bar.sub)}'
                        f'</span></td><td class="num strong">{_pct(bar.der)}</td>{values}</tr>')
    return ('<div class="ws-table-wrap"><table class="ws-table av-table"><thead><tr><th scope="col">Corpus</th>'
            '<th scope="col">Système</th><th scope="col" class="num">DER</th>'
            + "".join(f'<th scope="col" class="num">{label}</th>' for _, label in KINDS)
            + f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def figure(groups: list[tuple[str, list[Bar]]]) -> str:
    """Graphique (deux mises en page) et tableau des valeurs repliable."""
    if not groups:
        return '<p class="ws-empty-note">Aucun résultat de test pour les systèmes de référence.</p>'
    return (f'<figure class="av-figure"><div class="av-chart-wide">{svg(groups, False, "avw")}</div>'
            f'<div class="av-chart-narrow">{svg(groups, True, "avn")}</div>'
            '<figcaption class="ws-caption">Partition test, sans collar, chevauchements comptés : la longueur '
            'totale de chaque barre est le DER. Survoler un segment donne sa valeur ; toutes les valeurs sont dans le tableau ci-dessous.</figcaption></figure>'
            f'<details class="av-values ws-fold"><summary>Valeurs du graphique (tableau)</summary>{table(groups)}</details>')
