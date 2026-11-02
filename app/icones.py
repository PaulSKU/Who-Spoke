"""Icônes SVG des boutons-icônes (audit visuel du 02/11, §4 ; V4).

Dessinées sur une grille de 16 × 16, en `currentColor` : elles prennent la couleur du texte
du bouton, en clair comme en sombre. Décoratives (`aria-hidden`) : le bouton porte son nom
accessible (`aria-label`). Le triangle de lecture est centré sur son centre de gravité, et
non sur sa boîte englobante : il est donc décalé d'environ 1 px vers la droite, ce qui le
fait paraître centré dans le bouton.
"""

from __future__ import annotations

PATHS = {
    # Triangle (5,5 ; 3,2), (5,5 ; 12,8), (12,9 ; 8) : centre de gravité en x = 7,97, au
    # centre de la grille ; boîte englobante centrée en x = 9,2 (1,2 px à droite).
    "lecture": "M5.5 3.2 12.9 8 5.5 12.8Z",
    "pause": "M4.25 3h2.5v10h-2.5zM9.25 3h2.5v10h-2.5z",
    "moins": "M3 7.25h10v1.5H3z",
    "plus": "M7.25 3h1.5v4.25H13v1.5H8.75V13h-1.5V8.75H3v-1.5h4.25z",
    # Loupe : options de zoom et d'affichage repliées sur petit écran (V5).
    "loupe": "M7 2.5a4.5 4.5 0 0 1 3.6 7.2l2.85 2.85-1.06 1.06-2.85-2.85A4.5 4.5 0 1 1 7 2.5zm0 1.5a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
    "fermer": "M4.53 3.47 8 6.94l3.47-3.47 1.06 1.06L9.06 8l3.47 3.47-1.06 1.06L8 9.06l-3.47 3.47-1.06-1.06L6.94 8 3.47 4.53z",
}


def icon(name: str) -> str:
    """Icône `name` de PATHS, en SVG en ligne, sans nom accessible propre."""
    return (f'<svg class="ws-icon ws-icon-{name}" viewBox="0 0 16 16" aria-hidden="true" focusable="false">'
            f'<path d="{PATHS[name]}" fill="currentColor"/></svg>')
