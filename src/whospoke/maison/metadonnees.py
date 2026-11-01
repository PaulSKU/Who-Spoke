"""Métadonnées d'un enregistrement du corpus maison, sans aucun nom (`<Mxx>/metadonnees.yaml`).

Le fichier ne contient que des champs fermés : aucun texte libre, donc aucune place pour
un nom. Il est écrit par la candidate à partir de la fiche de session et des formulaires
signés, qui restent hors du dépôt.

    session: M01
    condition: salle          # salle | visio | bruit (protocole d'enregistrement §3)
    consentements:            # options cochées sur le formulaire, par code de participant
      S1: [1, 2, 3]
      S2: [1, 3]
      S3: [1, 2]

Il sert à la conversion (participants attendus), au rapport d'évaluation (condition
d'enregistrement) et à la commande `versionner` : les références d'un enregistrement ne
sont versionnées que si **tous** les participants ont coché l'option 3 (conventions
d'annotation, amendement du 01/11).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

FILENAME = "metadonnees.yaml"
CONDITIONS = {"salle": "salle réverbérante", "visio": "visio", "bruit": "bruit de fond"}
OPTIONS = (1, 2, 3)
REQUIRED_OPTION = 1            # option 1 : obligatoire pour participer (formulaire)
VERSIONING_OPTION = 3          # option 3 : annotations anonymes versionnées dans le dépôt
_CODE = re.compile(r"^S\d+$")
_KEYS = {"session", "condition", "consentements"}


class MetadataError(ValueError):
    """Fichier de métadonnées absent, incomplet ou hors du format attendu."""


@dataclass(frozen=True)
class Metadata:
    session: str
    condition: str
    consents: dict[str, tuple[int, ...]]

    @property
    def participants(self) -> list[str]:
        return sorted(self.consents, key=lambda code: (len(code), code))

    @property
    def condition_label(self) -> str:
        return CONDITIONS[self.condition]

    def versioning_allowed(self) -> bool:
        """Vrai si tous les participants ont coché l'option 3."""
        return all(VERSIONING_OPTION in options for options in self.consents.values())

    def refusals(self) -> list[str]:
        """Codes des participants sans l'option 3."""
        return [code for code in self.participants if VERSIONING_OPTION not in self.consents[code]]


def parse(data: object, session: str) -> Metadata:
    """Valide le contenu lu ; lève `MetadataError` avec un message à corriger."""
    if not isinstance(data, dict):
        raise MetadataError(f"{FILENAME} : un dictionnaire YAML est attendu")
    unknown = set(data) - _KEYS
    if unknown:
        raise MetadataError(f"{FILENAME} : champs non prévus {sorted(unknown)} (seuls {sorted(_KEYS)} ; aucun nom)")
    if data.get("session") != session:
        raise MetadataError(f"{FILENAME} : session {data.get('session')!r} au lieu de {session!r}")
    condition = data.get("condition")
    if condition not in CONDITIONS:
        raise MetadataError(f"{FILENAME} : condition {condition!r} ; attendu {', '.join(CONDITIONS)}")
    consents = data.get("consentements")
    if not isinstance(consents, dict) or not consents:
        raise MetadataError(f"{FILENAME} : « consentements » doit lister chaque participant (S1: [1, 2, 3]…)")
    parsed: dict[str, tuple[int, ...]] = {}
    for code, options in consents.items():
        if not isinstance(code, str) or not _CODE.match(code):
            raise MetadataError(f"{FILENAME} : {code!r} n'est pas un code de participant (S1, S2…)")
        if not isinstance(options, list) or any(option not in OPTIONS for option in options):
            raise MetadataError(f"{FILENAME} : {code} : liste d'options parmi {list(OPTIONS)} attendue")
        if REQUIRED_OPTION not in options:
            raise MetadataError(f"{FILENAME} : {code} n'a pas l'option 1, obligatoire pour être enregistré")
        parsed[code] = tuple(sorted(set(options)))
    return Metadata(session, condition, parsed)


def load(session_dir: Path, session: str) -> Metadata:
    path = session_dir / FILENAME
    if not path.is_file():
        raise MetadataError(f"{path} absent (modèle dans docs/corpus-maison/guide-annotation.md)")
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as error:
        raise MetadataError(f"{FILENAME} illisible : {error}") from error
    return parse(data, session)


def load_optional(session_dir: Path, session: str) -> Metadata | None:
    """Métadonnées si le fichier existe (erreur s'il est invalide), None sinon."""
    return load(session_dir, session) if (session_dir / FILENAME).is_file() else None
