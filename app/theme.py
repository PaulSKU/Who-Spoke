"""Thème de l'application (D17 ; système visuel de l'audit visuel du 02/11, §3 et §4).

Une seule source de valeurs : les jetons de `app/static/jetons.css` (`--ws-*`, redéfinis
sous `.dark` et en mode présentation). Chaque variable du thème Gradio, et sa variante
`_dark` quand Gradio en a une, renvoie à un jeton : aucune ne retombe sur la valeur claire
en mode sombre (Gradio 6.31 reprend la valeur claire d'une `_dark` non définie). Les jetons
sont injectés dans <head> sans réécriture (`head`), le reste du CSS passe par `css`.

La couleur est réservée aux locuteurs (palette de app/app.py). Polices système uniquement
(aucun fichier de police chargé), chiffres tabulaires pour les mesures.
"""

from __future__ import annotations

from pathlib import Path

import gradio as gr

STATIC_DIR = Path(__file__).resolve().with_name("static")
CSS_PATH = STATIC_DIR / "interface.css"
TOKENS_PATH = STATIC_DIR / "jetons.css"

SANS = ["system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Helvetica Neue", "Arial", "sans-serif"]
MONO = ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"]

INK, SLATE, LINE, CONTROL_LINE = "var(--ws-ink)", "var(--ws-slate)", "var(--ws-line)", "var(--ws-control-line)"
CANVAS, SURFACE, TRACK, ON_INK = "var(--ws-canvas)", "var(--ws-surface)", "var(--ws-track)", "var(--ws-on-ink)"
NONE = "none"

# Variables du thème ayant une variante `_dark` dans Gradio 6.31 : même jeton dans les deux
# modes, le jeton changeant de valeur sous .dark. Liste complète (contrôlée par un test).
WITH_DARK: dict[str, str] = {
    "accordion_text_color": INK,
    "background_fill_primary": SURFACE,
    "background_fill_secondary": CANVAS,
    "block_background_fill": SURFACE,
    "block_border_color": LINE,
    "block_border_width": "0px",
    "block_info_text_color": SLATE,
    "block_label_background_fill": SURFACE,
    "block_label_border_color": LINE,
    "block_label_border_width": "0px",
    "block_label_text_color": INK,
    "block_shadow": NONE,                 # l'ombre est celle des cartes (.ws-card), pas des blocs
    "block_title_background_fill": "transparent",
    "block_title_border_color": LINE,
    "block_title_border_width": "0px",
    "block_title_text_color": INK,
    "body_background_fill": CANVAS,
    "body_text_color": INK,
    "body_text_color_subdued": SLATE,
    "border_color_accent": INK,
    "border_color_accent_subdued": LINE,
    "border_color_primary": LINE,
    "button_border_width": "1px",
    "button_cancel_background_fill": SURFACE,
    "button_cancel_background_fill_hover": CANVAS,
    "button_cancel_border_color": LINE,
    "button_cancel_border_color_hover": SLATE,
    "button_cancel_shadow": NONE,
    "button_cancel_shadow_active": NONE,
    "button_cancel_shadow_hover": NONE,
    "button_cancel_text_color": INK,
    "button_cancel_text_color_hover": INK,
    "button_primary_background_fill": INK,
    "button_primary_background_fill_hover": INK,
    "button_primary_border_color": INK,
    "button_primary_border_color_hover": INK,
    "button_primary_shadow": NONE,
    "button_primary_shadow_active": NONE,
    "button_primary_shadow_hover": NONE,
    "button_primary_text_color": ON_INK,
    "button_primary_text_color_hover": ON_INK,
    "button_secondary_background_fill": SURFACE,
    "button_secondary_background_fill_hover": CANVAS,
    "button_secondary_border_color": LINE,
    "button_secondary_border_color_hover": SLATE,
    "button_secondary_shadow": NONE,
    "button_secondary_shadow_active": NONE,
    "button_secondary_shadow_hover": NONE,
    "button_secondary_text_color": INK,
    "button_secondary_text_color_hover": INK,
    "checkbox_background_color": SURFACE,
    "checkbox_background_color_focus": SURFACE,
    "checkbox_background_color_hover": SURFACE,
    "checkbox_background_color_selected": INK,
    "checkbox_border_color": CONTROL_LINE,       # rond ou case non cochés : ≥ 3:1 (V1)
    "checkbox_border_color_focus": INK,
    "checkbox_border_color_hover": INK,
    "checkbox_border_color_selected": INK,
    "checkbox_border_width": "1.5px",
    "checkbox_label_background_fill": SURFACE,
    "checkbox_label_background_fill_hover": CANVAS,
    "checkbox_label_background_fill_selected": CANVAS,
    "checkbox_label_border_color": LINE,
    "checkbox_label_border_color_hover": SLATE,
    "checkbox_label_border_color_selected": INK,
    "checkbox_label_border_width": "1px",
    "checkbox_label_shadow": NONE,               # le liseré rogné du choix coché (V1)
    "checkbox_label_shadow_active": NONE,
    "checkbox_label_shadow_hover": NONE,
    "checkbox_label_text_color": INK,
    "checkbox_label_text_color_selected": INK,
    "code_background_fill": CANVAS,
    "color_accent_soft": LINE,
    "error_background_fill": CANVAS,
    "error_border_color": INK,
    "error_border_width": "1px",
    "error_icon_color": INK,
    "error_text_color": INK,
    "input_background_fill": SURFACE,
    "input_background_fill_focus": SURFACE,
    "input_background_fill_hover": SURFACE,
    "input_border_color": LINE,
    "input_border_color_focus": INK,
    "input_border_color_hover": SLATE,
    "input_border_width": "1px",
    "input_placeholder_color": SLATE,
    "input_shadow": NONE,
    "input_shadow_focus": NONE,
    "link_text_color": INK,
    "link_text_color_active": INK,
    "link_text_color_hover": INK,
    "link_text_color_visited": INK,
    "loader_color": INK,
    "panel_background_fill": SURFACE,
    "panel_border_color": LINE,
    "panel_border_width": "0px",
    "shadow_spread": "0px",
    "slider_color": INK,
    "stat_background_fill": TRACK,
    "table_border_color": LINE,
    "table_even_background_fill": SURFACE,
    "table_odd_background_fill": SURFACE,
    "table_row_focus": CANVAS,
    "table_text_color": INK,
}

# Variables sans variante sombre : jetons aussi, ou valeurs sans couleur.
WITHOUT_DARK: dict[str, str] = {
    "color_accent": INK,
    # Point du bouton radio coché : Gradio le dessine en SVG blanc, sans variante sombre ;
    # il prend ici la couleur du fond dans les deux modes (audit visuel, §3).
    "radio_circle": "radial-gradient(circle, var(--background-fill-primary) 0 3px, transparent 3.5px)",
    "block_radius": "var(--ws-radius-card)",
    "block_label_radius": "var(--ws-radius-control)",
    "block_label_shadow": NONE,
    "block_label_text_weight": "500",
    "block_label_text_size": "0.875rem",
    "block_title_text_weight": "500",
    "block_padding": "0px",
    "input_radius": "var(--ws-radius-control)",
    "checkbox_border_radius": "var(--ws-radius-mark)",
    "checkbox_label_padding": "var(--ws-space-2) var(--ws-space-3)",
    "button_large_radius": "var(--ws-radius-control)",
    "button_medium_radius": "var(--ws-radius-control)",
    "button_small_radius": "var(--ws-radius-control)",
    "layout_gap": "var(--ws-space-4)",
    "form_gap_width": "0px",
    "shadow_drop": NONE,
    "shadow_drop_lg": NONE,
    "shadow_inset": NONE,
}


def build_theme() -> gr.themes.Base:
    theme = gr.themes.Base(
        primary_hue=gr.themes.colors.neutral,
        secondary_hue=gr.themes.colors.neutral,
        neutral_hue=gr.themes.colors.stone,
        font=SANS,
        font_mono=MONO,
        # Grille de 4 et 8 px (audit visuel, §4).
        spacing_size=gr.themes.Size(xxs="2px", xs="4px", sm="4px", md="8px", lg="8px", xl="12px", xxl="16px"),
        radius_size=gr.themes.Size(xxs="var(--ws-radius-mark)", xs="var(--ws-radius-mark)",
                                   sm="var(--ws-radius-control)", md="var(--ws-radius-control)",
                                   lg="var(--ws-radius-control)", xl="var(--ws-radius-card)",
                                   xxl="var(--ws-radius-card)"),
        text_size=gr.themes.sizes.text_md,
    )
    values = dict(WITHOUT_DARK)
    for name, value in WITH_DARK.items():
        values[name] = value
        values[f"{name}_dark"] = value
    return theme.set(**values)


def css() -> str:
    return CSS_PATH.read_text()


def head() -> str:
    """Jetons, placés dans <head> sans passer par la réécriture du CSS de Gradio."""
    return f"<style>{TOKENS_PATH.read_text()}</style>"


# Zones de dépôt en français quelle que soit la langue du navigateur (audit R-U5) : Gradio
# choisit ses textes selon la langue du navigateur ; les clés de ses zones de dépôt sont
# redéfinies pour toutes les langues qu'il fournit (Gradio 6.3).
GRADIO_LOCALES = ("ca", "de", "en", "es", "et", "eu", "fa", "fr", "he", "id", "ja", "ko", "lt", "nb",
                  "pt-BR", "pt", "ro", "ru", "sv", "ta", "th", "tr", "uk", "ur", "uz", "zh-CN", "zh-TW")
_UPLOAD_FR = {
    "upload_text.drop_file": "Déposez le fichier ici",
    "upload_text.click_to_upload": "cliquez pour le choisir",
    "common.or": "ou",
}
UPLOAD_TEXT = {locale: dict(_UPLOAD_FR) for locale in GRADIO_LOCALES}
