"""Exécution partagée entre deux expériences (D25, V2 et V3 ; décision du cockpit du 02/11).

Une même exécution de l'enveloppe à deux sorties donne deux expériences distinctes : chacune
a son dossier, son `config.yaml` et ses lignes au leaderboard. Le bloc `execution_partagee`,
identique dans les deux `config.yaml`, désigne l'expérience « porteuse », la seule qui
s'exécute, et la sortie évaluée par chacune :

    execution_partagee:
      porteuse: EXP-0023
      experiences: {EXP-0022: habituelle, EXP-0023: exclusive}

La sortie de chaque expérience doit être celle de son réglage `pipeline.parametres.sortie`.
À la fin de chaque exécution (complète, puis mesure CPU), la porteuse copie dans le
`rttm/` de chaque autre expérience la sortie qui la concerne (`rttm_<sortie>/`) et y écrit
le rappel `execution_partagee.json` : porteuse, dossier, sortie, empreintes SHA-256 des
`execution_*.json` de la porteuse et des deux `config.yaml`. Le script d'évaluation lit les
exécutions dans le dossier de la porteuse après contrôle de ce rappel, et ne reporte le
temps de calcul que pour la porteuse.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

from whospoke.experiment import REPO_ROOT

EXPERIMENTS_DIR = REPO_ROOT / "experiments"
REMINDER = "execution_partagee.json"


class SharedRunError(ValueError):
    """Bloc `execution_partagee` incohérent, ou rappel qui ne correspond plus."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def experiment_dir(exp_id: str, root: Path | None = None) -> Path:
    root = root or EXPERIMENTS_DIR
    matches = sorted(root.glob(f"{exp_id}_*"))
    if len(matches) != 1:
        raise SharedRunError(f"{exp_id} : {len(matches)} dossier(s) dans {root}")
    return matches[0]


def _sortie(config: dict) -> str:
    return ((config.get("pipeline") or {}).get("parametres") or {}).get("sortie") or "habituelle"


def check_block(config: dict, root: Path | None = None) -> dict[str, tuple[Path, str]]:
    """Contrôle du bloc ; renvoie {expérience : (dossier, sortie)} pour toutes les expériences."""
    block = config.get("execution_partagee")
    if not block:
        return {}
    exp_id, mapping = config["exp_id"], block.get("experiences") or {}
    if exp_id not in mapping or block.get("porteuse") not in mapping or len(mapping) < 2:
        raise SharedRunError(f"{exp_id} : bloc execution_partagee incomplet ({block})")
    members = {}
    for other, sortie in mapping.items():
        directory = experiment_dir(other, root)
        other_config = config if other == exp_id else _load(directory / "config.yaml")
        if other_config.get("execution_partagee") != block:
            raise SharedRunError(f"{other} : bloc execution_partagee différent de celui de {exp_id}")
        if _sortie(other_config) != sortie:
            raise SharedRunError(f"{other} : sortie {_sortie(other_config)!r} au lieu de {sortie!r}")
        members[other] = (directory, sortie)
    return members


def _load(path: Path) -> dict:
    import yaml

    return yaml.safe_load(path.read_text())


def check_partners_empty(config: dict, root: Path | None = None) -> None:
    """Avant l'exécution : les autres expériences n'ont encore ni rttm/ rempli ni exécution."""
    for other, (directory, _) in check_block(config, root).items():
        if other == config["exp_id"]:
            continue
        filled = (directory / "rttm").is_dir() and any((directory / "rttm").iterdir())
        if filled or list(directory.glob("execution_*.json")) or (directory / REMINDER).exists():
            raise SharedRunError(f"{other} : déjà exécutée ou déjà alimentée")


def write_reminders(config: dict, exp_dir: Path, copy_rttm: bool, root: Path | None = None) -> list[str]:
    """Après une exécution de la porteuse : copie des RTTM et rappel dans chaque autre dossier."""
    written = []
    executions = {p.name: sha256(p) for p in sorted(exp_dir.glob("execution_*.json"))}
    for other, (directory, sortie) in check_block(config, root).items():
        if other == config["exp_id"]:
            continue
        if copy_rttm:
            source = exp_dir / f"rttm_{sortie}"
            if not source.is_dir():
                raise SharedRunError(f"{source} absent : sortie {sortie!r} non produite")
            target = directory / "rttm"
            for path in sorted(source.rglob("*.rttm")):   # rttm_<sortie>/<corpus>/ pour D24
                destination = target / path.relative_to(source)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
        reminder = {
            "porteuse": config["exp_id"],
            "dossier": str(exp_dir.relative_to(REPO_ROOT)) if exp_dir.is_relative_to(REPO_ROOT) else str(exp_dir),
            "sortie": sortie,
            "rttm_source": f"rttm_{sortie}",
            "executions": executions,
            "config_sha256_porteuse": sha256(exp_dir / "config.yaml"),
            "config_sha256": sha256(directory / "config.yaml"),
            "date": datetime.now().astimezone().isoformat(timespec="seconds"),
            "temps": "rapporté par la porteuse seulement",
        }
        (directory / REMINDER).write_text(json.dumps(reminder, ensure_ascii=False, indent=2) + "\n")
        written.append(other)
    return written


def read_reminder(config: dict, exp_dir: Path, root: Path | None = None) -> tuple[Path, dict] | None:
    """Pour l'évaluation d'une expérience non porteuse : (dossier de la porteuse, rappel)
    après contrôle des empreintes et des RTTM ; None si l'expérience porte son exécution."""
    members = check_block(config, root)
    if not members or config["execution_partagee"]["porteuse"] == config["exp_id"]:
        return None
    path = exp_dir / REMINDER
    if not path.exists():
        raise SharedRunError(f"{path.name} absent : la porteuse n'a pas encore été exécutée")
    reminder = json.loads(path.read_text())
    porteuse_dir, _ = members[config["execution_partagee"]["porteuse"]]
    if reminder["config_sha256"] != sha256(exp_dir / "config.yaml"):
        raise SharedRunError("config.yaml modifié depuis l'exécution partagée")
    if reminder["config_sha256_porteuse"] != sha256(porteuse_dir / "config.yaml"):
        raise SharedRunError("config.yaml de la porteuse modifié depuis l'exécution partagée")
    for name, digest in reminder["executions"].items():
        if sha256(porteuse_dir / name) != digest:
            raise SharedRunError(f"{name} de la porteuse différent du rappel")
    source = porteuse_dir / reminder["rttm_source"]
    mine = sorted(str(p.relative_to(exp_dir / "rttm")) for p in (exp_dir / "rttm").rglob("*.rttm"))
    if mine != sorted(str(p.relative_to(source)) for p in source.rglob("*.rttm")):
        raise SharedRunError("rttm/ ne contient pas les mêmes fichiers que la sortie de la porteuse")
    for name in mine:
        if (exp_dir / "rttm" / name).read_bytes() != (source / name).read_bytes():
            raise SharedRunError(f"rttm/{name} différent de {reminder['rttm_source']}/{name}")
    return porteuse_dir, reminder
