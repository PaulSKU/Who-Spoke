# Vérification de l'installation — 02/11/2026 00:56

Script : `scripts/verifier_installation.sh` (R-R4, chantier E6). Verdict : **vérification partielle réussie (sans modèles)** ; durée totale : 3 min 03 s.

| | |
|---|---|
| Dépôt cloné | `https://github.com/PaulSKU/Who-Spoke.git`, branche `outils`, commit `d253503a9122` |
| Options | modèles : non (--sans-modeles) ; téléchargement : non ; .env fourni : non ; moteurs externes : non ; cache de uv : celui de la machine |
| Système | macOS 14.1.2, arm64 |
| uv | uv 0.11.28 (ebf0f43d7 2026-07-07 aarch64-apple-darwin) |
| git | git version 2.39.2 (Apple Git-143) |
| ffmpeg | ffmpeg version 9.0.2 (~/.local/bin/ffmpeg) |
| Homebrew | Homebrew 7.0.11 |
| Environnement `.venv` du clone | 1.3G ; espace libre au départ : 38Gi |

| Étape | Statut | Durée | Dernière ligne du journal |
|---|---|---|---|
| prerequis | ok | 0 min 00 s | uv, git et ffmpeg présents |
| clone | ok | 0 min 01 s | — |
| uv_sync | ok | 0 min 01 s | Installed 143 packages in 1.00s |
| check_env | ok | 0 min 07 s | HF_TOKEN : absent |
| tests | ok | 2 min 36 s | 363 passed, 10 skipped, 4 deselected in 153.51s (0:02:33) |
| prefetch_models | non lancé | 0 min 00 s | --sans-modeles : ni téléchargement ni vérification |
| application | ok | 0 min 16 s | arrêt propre (SIGTERM, code 0) en 1 s ; prête en 7 s, option --sans-prechauffage absente de cette version : lancée sans |
| cli | ok | 0 min 01 s | usage: whospoke diarize [-h] |
| env_nemotron | non lancé | 0 min 00 s | option --moteurs-externes non demandée |
| env_diarizen | non lancé | 0 min 00 s | option --moteurs-externes non demandée |

Durées à l'horloge murale, à la seconde. Journaux de chaque étape dans `journaux/`.
Le cache de uv de la machine était utilisé : sur une machine vierge, `uv sync` télécharge en plus Python 3.11 et les paquets (torch compris).
