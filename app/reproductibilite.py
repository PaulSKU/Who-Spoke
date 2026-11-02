"""Fiche de reproductibilité d'une analyse, dans l'export JSON (audit R-D5, chantier B6).

Ce qu'il faut pour refaire l'analyse et retrouver le même résultat : versions des
logiciels, commit du code et empreinte du code des moteurs, révisions figées des modèles
et réglages effectifs (D18), périphérique et machine, durées de chaque étape. Ni audio, ni
nom de fichier, ni chemin local : l'audio n'est désigné que par l'empreinte de ses
échantillons normalisés (celle de la clé du cache).
"""

from __future__ import annotations

import functools
import os
import platform
import subprocess
from importlib import metadata

PACKAGES = ("whospoke", "torch", "torchaudio", "pyannote.audio", "pyannote.core", "pyannote.metrics",
            "speechbrain", "numpy", "scipy", "scikit-learn", "librosa", "gradio")


def package_versions(packages: tuple[str, ...] = PACKAGES) -> dict[str, str]:
    """Version installée de chaque paquet (« absent » s'il ne l'est pas), sans l'importer."""
    versions = {"python": platform.python_version()}
    for name in packages:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "absent"
    return versions


@functools.lru_cache(maxsize=1)
def ffmpeg_version() -> str:
    """Première ligne de `ffmpeg -version` (normalisation de l'audio, D15), ou « absent »."""
    try:
        output = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, check=True,
                                timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return "absent"
    return output.splitlines()[0].strip() if output else "absent"


def machine(device: str) -> dict:
    """Système, architecture, processeur et périphérique de calcul effectif."""
    info = {"systeme": platform.platform(), "architecture": platform.machine(),
            "processeur": platform.processor() or platform.machine(), "coeurs": os.cpu_count(),
            "peripherique": device}
    if device == "cuda":
        try:
            import torch

            info["carte_graphique"] = torch.cuda.get_device_name(0)
        except Exception:   # pilote absent ou carte indisponible : la fiche reste utilisable
            info["carte_graphique"] = "inconnue"
    return info


def sheet(result: dict) -> dict:
    """Fiche d'un résultat : `result["tracabilite"]` (consigné à l'analyse) complété des
    versions, de la machine, des durées et des fusions de locuteurs en vigueur."""
    trace = result.get("tracabilite", {})
    calcul_s = result["calcul_s"]
    return {
        "date_analyse": trace.get("date_analyse"),
        "reaffiche_depuis_le_cache": bool(result.get("cache")),
        "date_calcul": result.get("cache") or trace.get("date_analyse"),
        "commit": trace.get("commit"),
        "empreinte_code_moteurs": trace.get("empreinte_code_moteurs"),
        "empreinte_audio": trace.get("empreinte_audio"),
        "moteur": result["moteur_cle"],
        "moteur_factice": result["factice"],
        "experience_source": result["configuration"]["experience_source"],
        "revisions_modeles": trace.get("revisions_modeles", {}),
        "configuration_effective": trace.get("configuration_effective", {}),
        "reglages": result["configuration"]["reglages"],
        "nombre_locuteurs": result["configuration"]["nombre_locuteurs"],
        "versions": dict(package_versions(), ffmpeg=ffmpeg_version()),
        "machine": machine(result["device"]),
        "durees_s": {
            "audio": round(result["duree_s"], 3),
            "normalisation": round(result["normalisation_s"], 3),
            "chargement_modele": None if result["chargement_s"] is None else round(result["chargement_s"], 3),
            "etapes": {step: round(seconds, 3) for step, seconds in result["durees_etapes"].items()},
            "calcul": round(calcul_s, 3),
            "rtf": round(calcul_s / result["duree_s"], 5) if result["duree_s"] else None,
        },
        "fusions": [{"source": source, "cible": target} for source, target in result.get("fusions", [])],
    }
