"""Constats mesurés (`docs/constats.yaml`, tenu par le cockpit ; audit R-U7 et R-U8).

Source unique de l'encadré « Ce que nous avons appris » (onglet Avancement, constats
`cle: true`) et des constats affichés sous chaque étape (onglet Pipeline). Lecture seule,
sous la racine `--depot`. Un fichier absent donne une liste vide ; un fichier illisible ou
un constat mal formé est signalé, jamais ignoré en silence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

RELATIVE = Path("docs") / "constats.yaml"
CONFIDENCES = ("certain", "probable", "incertain")
EVALUATION = "evaluation"     # étape hors catalogue : la mesure


@dataclass
class Constat:
    id: str
    etape: str
    moteurs: list[str]
    texte: str
    sources: list[str]
    confiance: str
    cle: bool

    def concerns(self, engine_key: str) -> bool:
        """Vrai si le constat vaut pour ce moteur (liste vide : tous les moteurs)."""
        return not self.moteurs or engine_key in self.moteurs


@dataclass
class Constats:
    items: list[Constat] = field(default_factory=list)
    version: str = ""
    date: str = ""
    problems: list[str] = field(default_factory=list)
    present: bool = False


def read(root: Path) -> Constats:
    path = root / RELATIVE
    result = Constats()
    if not path.is_file():
        return result
    result.present = True
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as error:
        result.problems.append(f"{RELATIVE} illisible ({type(error).__name__})")
        return result
    result.version, result.date = str(data.get("version", "")), str(data.get("date", ""))
    for index, raw in enumerate(data.get("constats") or [], start=1):
        if not isinstance(raw, dict):
            result.problems.append(f"constat n° {index} : entrée invalide")
            continue
        ident = str(raw.get("id") or f"n° {index}")
        missing = [name for name in ("id", "etape", "texte", "confiance") if not raw.get(name)]
        if missing:
            result.problems.append(f"constat {ident} : champ(s) manquant(s) {', '.join(missing)}")
            continue
        confidence = str(raw["confiance"])
        if confidence not in CONFIDENCES:
            result.problems.append(f"constat {ident} : confiance inconnue « {confidence} »")
        result.items.append(Constat(
            id=ident, etape=str(raw["etape"]), moteurs=[str(m) for m in raw.get("moteurs") or []],
            texte=str(raw["texte"]), sources=[str(s) for s in raw.get("sources") or []],
            confiance=confidence, cle=bool(raw.get("cle")),
        ))
    return result
