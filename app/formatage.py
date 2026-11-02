"""Nombres affichés en français (audit visuel du 02/11, §4) : une seule source pour les
tableaux, les textes, les SVG et l'image de la timeline.

Virgule décimale ; espace fine insécable (U+202F) entre les groupes de milliers et devant
les unités et le signe % ; signe moins typographique (U+2212) ; unités en français (s, min,
h, Ko, Mo, Go). Les chiffres sont alignés par `font-variant-numeric: tabular-nums` (CSS).
Jamais pour les fichiers lus par une machine (RTTM, JSON, étiquettes Audacity).
"""

from __future__ import annotations

import math

NNBSP = " "     # espace fine insécable
MINUS = "−"     # signe moins
DASH = "—"           # valeur inconnue


def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def nombre(value: float | None, decimals: int = 0, sign: bool = False) -> str:
    """« 1 234,5 » ; `sign` : « +0,80 » ou « −0,80 » ; « — » pour une valeur inconnue."""
    if _missing(value):
        return DASH
    text = f"{abs(value):,.{decimals}f}".replace(",", NNBSP).replace(".", ",")
    negative = value < 0 and any(c not in "0, " for c in text)   # « −0,00 » s'écrit « 0,00 »
    prefix = MINUS if negative else ("+" if sign else "")
    return prefix + text


def unite(value: float | None, unit: str, decimals: int = 0, sign: bool = False) -> str:
    """« 2,98 s », « 7,2 Ko » : nombre, espace fine insécable, unité."""
    return DASH if _missing(value) else f"{nombre(value, decimals, sign)}{NNBSP}{unit}"


def pourcentage(value: float | None, decimals: int = 1, sign: bool = False) -> str:
    """« 26,59 % » (la valeur est déjà en pour cent)."""
    return unite(value, "%", decimals, sign)


def duree(seconds: float | None) -> str:
    """« 0,05 s », « 4 s », « 2 min 05 s », « 1 h 02 min » ; « — » pour une valeur inconnue."""
    if _missing(seconds):
        return DASH
    if 0 < seconds < 0.995:   # sous la seconde : au centième (tour de 50 ms, analyse factice)
        return unite(seconds, "s", 2)
    seconds = max(0, int(round(seconds)))
    if seconds < 60:
        return f"{seconds}{NNBSP}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}{NNBSP}min {seconds:02d}{NNBSP}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}{NNBSP}h {minutes:02d}{NNBSP}min"


def taille(octets: int | None) -> str:
    """« 512 o », « 7,2 Ko », « 3,4 Mo », « 1,2 Go » (puissances de 1 000, unités SI)."""
    if _missing(octets):
        return DASH
    for unit, scale in (("Go", 1e9), ("Mo", 1e6), ("Ko", 1e3)):
        if octets >= scale:
            return unite(octets / scale, unit, 1)
    return unite(octets, "o")


def general(value: float) -> str:
    """Valeur d'un réglage, à six chiffres significatifs au plus (« 0,7045 », « 1e-05 »)."""
    return f"{value:.6g}".replace(".", ",").replace("-", MINUS)
