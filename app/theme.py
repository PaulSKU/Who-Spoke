"""Thème de l'application (D17) : sobre, monochrome, hors ligne.

La couleur est réservée aux locuteurs (palette de app/app.py) : l'interface elle-même
n'emploie que cinq teintes neutres, en clair et en sombre. Polices système uniquement
(aucun fichier de police chargé, ni local ni distant), chiffres tabulaires pour les mesures.
"""

from __future__ import annotations

from pathlib import Path

import gradio as gr

CSS_PATH = Path(__file__).resolve().with_name("static") / "interface.css"

# Teintes nommées (clair, sombre).
INK = ("#18191d", "#ecece9")        # texte principal, bouton principal, focus
SLATE = ("#5f616a", "#a3a49e")      # texte secondaire (contraste ≥ 4,5:1 sur SURFACE et CANVAS)
LINE = ("#e2e2df", "#2d2e33")       # filets, bordures
CANVAS = ("#f4f4f2", "#121315")     # fond de page
SURFACE = ("#ffffff", "#1b1c1f")    # cartes, champs

SANS = ["system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Helvetica Neue", "Arial", "sans-serif"]
MONO = ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"]

# Ombres en couches (sm : contrôles ; md : cartes), anneau de 1 px en guise de bordure.
SHADOW_SM = ("0 1px 2px -1px rgba(0,0,0,0.08), 0 0 0 1px rgba(25,28,33,0.08)",
             "0 1px 2px -1px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.07)")


def build_theme() -> gr.themes.Base:
    theme = gr.themes.Base(
        primary_hue=gr.themes.colors.neutral,
        secondary_hue=gr.themes.colors.neutral,
        neutral_hue=gr.themes.colors.stone,
        font=SANS,
        font_mono=MONO,
        radius_size=gr.themes.sizes.radius_md,
        text_size=gr.themes.sizes.text_md,
    )
    light, dark = 0, 1
    values: dict[str, str] = {}

    def both(name: str, pair: tuple[str, str]) -> None:
        # Certaines variables n'ont pas de variante sombre : interface.css les redéfinit sous .dark.
        values[name] = pair[light]
        if hasattr(theme, f"{name}_dark"):
            values[f"{name}_dark"] = pair[dark]

    both("body_background_fill", CANVAS)
    both("body_text_color", INK)
    both("body_text_color_subdued", SLATE)
    both("block_info_text_color", SLATE)
    both("block_label_text_color", INK)
    both("block_title_text_color", INK)
    both("border_color_primary", LINE)
    both("border_color_accent", INK)
    both("color_accent", INK)
    both("color_accent_soft", LINE)
    both("block_background_fill", SURFACE)
    both("panel_background_fill", SURFACE)
    both("input_background_fill", SURFACE)
    both("input_border_color", LINE)
    both("input_border_color_focus", INK)
    both("input_border_color_hover", SLATE)
    both("checkbox_border_color", LINE)
    both("checkbox_background_color_selected", INK)
    both("checkbox_border_color_selected", INK)
    both("checkbox_label_background_fill", SURFACE)
    both("checkbox_label_background_fill_hover", CANVAS)
    both("checkbox_label_background_fill_selected", CANVAS)
    both("checkbox_label_border_color", LINE)
    both("checkbox_label_border_color_selected", INK)
    both("checkbox_label_text_color", INK)
    both("checkbox_label_text_color_selected", INK)
    both("button_primary_background_fill", INK)
    both("button_primary_background_fill_hover", INK)
    both("button_primary_border_color", INK)
    both("button_primary_border_color_hover", INK)
    both("button_primary_text_color", (SURFACE[0], CANVAS[1]))
    both("button_primary_text_color_hover", (SURFACE[0], CANVAS[1]))
    both("button_secondary_background_fill", SURFACE)
    both("button_secondary_background_fill_hover", CANVAS)
    both("button_secondary_border_color", LINE)
    both("button_secondary_text_color", INK)
    both("table_border_color", LINE)
    both("table_even_background_fill", SURFACE)
    both("table_odd_background_fill", SURFACE)
    both("table_text_color", INK)
    both("block_label_background_fill", SURFACE)
    both("input_shadow", SHADOW_SM)
    values.update(
        block_border_width="0px",
        block_shadow="none",
        block_shadow_dark="none",
        block_label_border_width="0px",
        block_label_shadow="none",
        block_label_text_weight="500",
        block_label_text_size="0.875rem",
        block_title_text_weight="500",
        block_padding="0px",
        input_border_width="1px",
        input_radius="8px",
        block_radius="12px",
        button_large_radius="10px",
        button_medium_radius="8px",
        button_small_radius="8px",
        button_primary_shadow="none",
        button_primary_shadow_hover="none",
        button_secondary_shadow="none",
        checkbox_label_shadow="none",
        checkbox_label_border_width="1px",
        layout_gap="16px",
        form_gap_width="0px",
        shadow_drop="none",
        shadow_spread="0px",
    )
    return theme.set(**values)


def css() -> str:
    return CSS_PATH.read_text()
