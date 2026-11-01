"""Image de la timeline (audit R-U11, chantier B6) : SVG autonome, généré côté serveur.

Mêmes groupes que la timeline de l'onglet Analyse (`app._viewer_value`) : premier moteur
en couleurs, second moteur en gris, référence aux couleurs de l'appariement, et la carte
des erreurs de chaque moteur avec ses motifs (parole manquée pleine, fausse alarme
hachurée, confusion en contour). Toute la durée du fichier sur une seule échelle.

Fichier destiné à être ouvert ailleurs (rapport, diaporama) : couleurs fixes du mode clair
sur fond blanc, police système, sans ressource distante ; titre et description pour les
lecteurs d'écran. Le PNG est tiré de ce SVG par le navigateur (canevas), sans dépendance.
"""

from __future__ import annotations

from html import escape

WIDTH = 1200
LABEL_W = 220        # colonne des noms
MARGIN = 16
LANE = 18            # hauteur d'une piste
LANE_GAP = 6
GROUP_GAP = 18
INK, SLATE, LINE, SURFACE = "#18191d", "#5f616a", "#e2e2df", "#ffffff"
ERROR_ROWS = (("manquee", "Parole manquée"), ("fausse_alarme", "Fausse alarme"), ("confusion", "Confusion"))
NICE_STEPS = (1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600)


def clock(seconds: float) -> str:
    """« 0:05 », « 12:30 », « 1:02:03 »."""
    seconds = int(round(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def tick_step(duration_s: float, target: int = 10) -> int:
    """Pas des graduations : le plus petit pas « rond » donnant au plus `target` intervalles."""
    return next((step for step in NICE_STEPS if duration_s / step <= target), NICE_STEPS[-1])


def _fit(text: str, width: float, char_w: float = 6.6) -> str:
    """Texte coupé (avec « … ») pour tenir dans `width` pixels, à la louche."""
    limit = max(4, int(width / char_w))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def timeline_svg(groups: list[dict], duration_s: float, title: str) -> str:
    """SVG de la timeline ; `groups` au format de `_viewer_value(result)["groupes"]`."""
    span = WIDTH - LABEL_W - 2 * MARGIN
    x0 = MARGIN + LABEL_W
    duration = max(duration_s, 1e-6)

    def x(t: float) -> float:
        return x0 + span * min(max(t, 0.0), duration) / duration

    rows, y = [], 48
    summary = []
    for group in groups:
        rows.append(f'<text x="{MARGIN}" y="{y + 12}" class="h">{escape(_fit(group["titre"], WIDTH))}</text>')
        y += 22
        speakers = group["locuteurs"]
        lane_of = {speaker["id"]: index for index, speaker in enumerate(speakers)}
        top = y
        for speaker in speakers:
            rows.append(f'<text x="{MARGIN}" y="{y + 13}" class="t">{escape(_fit(speaker["nom"], LABEL_W - 12))}</text>'
                        f'<rect x="{x0}" y="{y}" width="{span}" height="{LANE}" fill="#f0f0ed"/>')
            y += LANE + LANE_GAP
        for segment in group["segments"]:
            index = lane_of.get(segment["locuteur"])
            if index is None:
                continue
            left, right = x(segment["debut"]), x(segment["fin"])
            rows.append(f'<rect x="{left:.2f}" y="{top + index * (LANE + LANE_GAP)}" '
                        f'width="{max(right - left, 0.5):.2f}" height="{LANE}" '
                        f'fill="{speakers[index]["couleur"]}"/>')
        summary.append(f"{group['titre']} : " + ", ".join(speaker["nom"] for speaker in speakers))
        errors = group.get("erreurs")
        if errors:
            rows.append(f'<text x="{MARGIN}" y="{y + 12}" class="s">Erreurs sans collar</text>')
            y += 20
            for kind, label in ERROR_ROWS:
                rows.append(f'<text x="{MARGIN}" y="{y + 13}" class="t">{label}</text>'
                            f'<rect x="{x0}" y="{y}" width="{span}" height="{LANE}" fill="#f0f0ed"/>')
                for zone in errors["zones"]:
                    if zone["type"] != kind:
                        continue
                    left, right = x(zone["debut"]), x(zone["fin"])
                    rows.append(_error_mark(kind, left, y, max(right - left, 0.5)))
                y += LANE + LANE_GAP
        y += GROUP_GAP
    step = tick_step(duration)
    ticks = list(range(0, int(duration) + 1, step))
    axis = "".join(
        f'<line x1="{x(t):.2f}" y1="40" x2="{x(t):.2f}" y2="{y - GROUP_GAP + 4}" stroke="{LINE}"/>'
        f'<text x="{x(t):.2f}" y="{y}" class="a" text-anchor="{"start" if t == 0 else "middle"}">{clock(t)}</text>'
        for t in ticks)
    height = y + 16
    description = (f"Timeline de {clock(duration_s)} : " + " ; ".join(summary)
                   + ". Une piste par locuteur, un rectangle par segment de parole.")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" aria-labelledby="titre desc">'
        f'<title id="titre">{escape(title)}</title><desc id="desc">{escape(description)}</desc>'
        '<style>text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,'
        f'sans-serif;font-size:12px;fill:{INK}}}.h{{font-size:13px;font-weight:600}}.s,.a{{fill:{SLATE};'
        'font-size:11px}</style>'
        f'<defs><pattern id="hachures" width="5" height="5" patternUnits="userSpaceOnUse" '
        f'patternTransform="rotate(45)"><rect width="2" height="5" fill="{INK}"/></pattern></defs>'
        f'<rect width="{WIDTH}" height="{height}" fill="{SURFACE}"/>'
        f'<text x="{MARGIN}" y="24" class="h">{escape(_fit(title, WIDTH))}</text>'
        f'{axis}{"".join(rows)}</svg>'
    )


def _error_mark(kind: str, x: float, y: float, width: float) -> str:
    """Zone d'erreur au motif de la carte des erreurs (encre)."""
    if kind == "manquee":
        return f'<rect x="{x:.2f}" y="{y}" width="{width:.2f}" height="{LANE}" fill="{INK}"/>'
    fill = "url(#hachures)" if kind == "fausse_alarme" else SURFACE
    inset = 0.75 if width > 1.5 else 0.0
    return (f'<rect x="{x + inset:.2f}" y="{y + inset}" width="{width - 2 * inset:.2f}" height="{LANE - 2 * inset}" '
            f'fill="{fill}" stroke="{INK}" stroke-width="1.5"/>')
