"""Vérification de l'environnement : macOS, Python, torch, MPS, ffmpeg, HF_TOKEN.

La valeur de HF_TOKEN n'est jamais affichée, seulement sa présence.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent


def ffmpeg_status() -> str:
    path = shutil.which("ffmpeg")
    if path is None:
        return "absent"
    try:
        first_line = subprocess.run(
            [path, "-version"], capture_output=True, text=True, check=True
        ).stdout.splitlines()[0]
    except (OSError, subprocess.CalledProcessError, IndexError):
        return f"présent ({path}), version illisible"
    return f"présent ({path}) — {first_line}"


def main() -> None:
    load_dotenv(REPO_ROOT / ".env")

    mac_version = platform.mac_ver()[0] or "non macOS"
    print(f"macOS            : {mac_version} ({platform.machine()})")
    print(f"Python           : {sys.version.split()[0]} ({sys.executable})")

    try:
        import torch

        print(f"torch            : {torch.__version__}")
        print(f"MPS disponible   : {torch.backends.mps.is_available()}")
        print(f"CUDA disponible  : {torch.cuda.is_available()}")
    except ImportError:
        print("torch            : absent")

    from whospoke.device import select_device

    print(f"Périphérique auto: {select_device()}")
    print(f"ffmpeg           : {ffmpeg_status()}")
    print(f"HF_TOKEN         : {'présent' if os.environ.get('HF_TOKEN') else 'absent'}")


if __name__ == "__main__":
    main()
