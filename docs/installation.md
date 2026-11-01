# Installation

Version du 2 novembre 2026 (audit du 01/11, R-R4 ; chantier E6). Le test sur machine vierge est prévu le jeudi 12/11 (planning v2.0). Ce document dit ce qu'il faut avant de commencer, l'ordre des étapes, les durées mesurées et les problèmes connus. Le script `scripts/verifier_installation.sh` refait tout le parcours depuis un clone neuf et chronomètre chaque étape.

## 1. Prérequis

| Élément | Détail |
|---|---|
| Machine | macOS sur Apple Silicon. Vérifié sur macOS 14.1.2 (M2 Pro, 16 Go). Le calcul passe par MPS, sinon par le CPU |
| Outils de développement d'Apple | `xcode-select --install` : fournit `git` |
| uv | Gestionnaire de l'environnement Python ; vérifié avec uv 0.11.28. Installation : https://docs.astral.sh/uv/ (installateur officiel ou Homebrew). uv télécharge lui-même Python 3.11 |
| ffmpeg | L'exécutable seul, dans le `PATH` (normalisation de l'audio en sous-processus, D16) ; les bibliothèques partagées ne sont pas requises. Sur macOS 14, voir §4 |
| Compte Hugging Face | Nécessaire pour `pyannote/speaker-diarization-community-1`, **modèle à accès restreint** : 1. créer un compte sur https://huggingface.co ; 2. connecté à ce compte, accepter les conditions sur https://huggingface.co/pyannote/speaker-diarization-community-1 ; 3. créer un jeton en lecture (Settings > Access Tokens). Le jeton ne sert qu'au préchargement ; ensuite tout fonctionne hors ligne |
| Accès au dépôt | Dépôt GitHub public : `git clone` sans identifiants |
| Espace disque | Environnement `.venv` : 1,3 Go. Modèles : 34 Mo (community-1) et 89 Mo (ECAPA). En option, environnements séparés (`envs/`, §4) : 0,7 Go pour Nemotron 3 et 1,0 Go pour DiariZen, sans leurs poids |
| Réseau | Pour le clone, `uv sync` et le préchargement des modèles seulement. Ensuite, l'application et la commande en ligne tournent hors ligne (D27) |

## 2. Étapes

```bash
git clone https://github.com/PaulSKU/Who-Spoke.git
cd Who-Spoke
uv sync --locked
cp .env.example .env    # puis écrire le jeton : HF_TOKEN=<jeton>
uv run python scripts/check_env.py
uv run python scripts/prefetch_models.py   # réseau et jeton ; télécharge puis vérifie hors ligne
uv run pytest
uv run python -m app.app                   # http://127.0.0.1:7860
uv run whospoke diarize --help
```

- `uv sync --locked` refuse de continuer si `uv.lock` ne correspond plus à `pyproject.toml` : l'environnement est exactement celui des expériences.
- `check_env.py` affiche la version de macOS, de Python et de torch, MPS, ffmpeg, et la présence du jeton (jamais sa valeur).
- `prefetch_models.py` place les modèles dans le cache Hugging Face, aux révisions figées, puis vérifie qu'ils se chargent hors ligne. `--verifier` fait la vérification seule.
- En option, environnements séparés des moteurs externes (D23, chantier E4) : `sh scripts/envs/nemotron.sh --modeles` et `sh scripts/envs/diarizen.sh --modeles`, depuis la racine du dépôt (`docs/recherche/e4-moteurs-externes.md`).

## 3. Vérification automatique

```bash
nice -n 19 bash scripts/verifier_installation.sh --sans-modeles
```

Le script travaille dans un dossier temporaire, effacé à la fin, sauf avec `--garder`. Il enchaîne :

1. le clone depuis GitHub (`--depot`, `--branche` ; par défaut `main`) ;
2. `uv sync --locked`, puis `check_env.py` ;
3. la suite rapide ;
4. le préchargement des modèles ;
5. le démarrage de l'application, avec `--sans-prechauffage` si la version clonée a cette option, jusqu'à la première réponse HTTP, puis son arrêt par SIGTERM ;
6. `whospoke diarize --help`.

| Option | Effet |
|---|---|
| (aucune) | Les modèles doivent déjà être en cache : `prefetch_models.py --verifier`. Sinon, arrêt, avec la marche à suivre pour le jeton et les conditions de community-1 |
| `--sans-modeles` | Ni préchargement ni test chargeant un modèle ; Hub hors ligne ; aucune inférence |
| `--env FICHIER --telecharger` | Copie le `.env` dans le clone (sans l'afficher), puis lance le préchargement réel |
| `--moteurs-externes` | Recrée en plus `envs/nemotron` et `envs/diarizen`, sans les poids |
| `--cache-uv-vierge` | Cache de uv neuf, dans le dossier temporaire : mesure le téléchargement réel de `uv sync` |
| `--port`, `--sortie`, `--garder` | Port de l'application (7870), dossier du rapport, dossier de travail gardé |

Le rapport est écrit dans `results/installation/<date>_<heure>/` :

- `rapport.md` : système, versions, puis statut, durée et dernière ligne utile de chaque étape ;
- `etapes.tsv` ;
- `journaux/` : un journal par étape, avec le dossier personnel remplacé par `~`.

Pour le 12/11 :

```bash
bash scripts/verifier_installation.sh --cache-uv-vierge --env <chemin du .env> --telecharger --moteurs-externes
```

## 4. Durées mesurées

Mesure du 02/11/2026 (`results/installation/2026-11-02_00h56/`) :

- MacBook Pro M2 Pro, macOS 14.1.2 ;
- branche `outils` (commit `d253503`), avant fusion ;
- `--sans-modeles`, sous `nice -n 19`, pendant que la piste A calculait.

| Étape | Durée |
|---|---|
| Clone | 1 s |
| `uv sync --locked` (143 paquets, cache de uv de la machine) | 1 s |
| `check_env.py` | 7 s |
| Suite rapide (363 réussis, 10 sautés) | 2 min 36 s |
| Application : prête (première réponse HTTP) | 7 s ; arrêt propre en 1 s |
| `whospoke diarize --help` | 1 s |
| **Total** | **3 min 03 s** |

Ces durées sont des minimums :

- **`uv sync`** a puisé dans le cache de uv. Sur une machine vierge, il télécharge Python 3.11 et environ 1,3 Go installés. Non mesuré : à mesurer le 12/11 avec `--cache-uv-vierge`.
- **Préchargement des modèles** (environ 120 Mo) : non mesuré, faute de jeton dans le clone. À mesurer le 12/11.
- **Environnements séparés** : 5 min 30 s pour Nemotron 3 et 2 min 55 s pour DiariZen (chantier E4, cache de uv déjà rempli), sans les poids.

## 5. Problèmes connus

- **Homebrew et ffmpeg sur macOS 14.** Homebrew ne fournit plus de binaire précompilé de ffmpeg pour macOS 14 : `brew install ffmpeg` le compile depuis les sources, ce qui l'a rendu inutilisable au démarrage du projet (journal du 27/10). Solution retenue sur la machine du projet : ffmpeg de conda-forge dans un environnement conda dédié, exposé dans `~/.local/bin` par des liens symboliques (ffmpeg 9.0.2). Commandes équivalentes, non rejouées :

  ```bash
  conda create -n ffmpeg -c conda-forge ffmpeg
  mkdir -p ~/.local/bin
  ln -s "$(conda info --base)/envs/ffmpeg/bin/ffmpeg" ~/.local/bin/ffmpeg
  ln -s "$(conda info --base)/envs/ffmpeg/bin/ffprobe" ~/.local/bin/ffprobe
  ```

  `~/.local/bin` doit être dans le `PATH`, et `check_env.py` doit afficher « ffmpeg : présent ». Seul l'exécutable sert : passer un chemin de fichier directement à pyannote échouerait (`Could not load libtorchcodec`), ce que le projet évite en passant l'audio en mémoire (D16).
- **Dossier `envs/`.** Il contient les environnements séparés de Nemotron 3 et de DiariZen. Il est ignoré par git (`/envs/` dans `.gitignore`), donc absent d'un clone : on le recrée par `scripts/envs/*.sh`, lancés depuis la racine du dépôt. Il contient aussi le code cloné de DiariZen et ses tests : le `conftest.py` racine les exclut de `pytest`. Le motif doit rester ancré (`/envs/`), sinon il masque aussi `scripts/envs/`. Taille sur la machine du projet : 0,7 Go (Nemotron 3), 1,0 Go (DiariZen), plus 1,4 Go et 26 Mo pour les essais NeMo et NeMo-Speech.cpp, qu'on peut supprimer.
- **Accès restreint.** Sans conditions acceptées ou sans jeton, `prefetch_models.py` échoue au téléchargement de community-1 et affiche le message du Hub. Le jeton est lu dans `.env`, jamais affiché ni versionné.
- **`--sans-prechauffage`.** L'option de l'application vient de la branche `ui`. Avant sa fusion, le script de vérification lance l'application sans elle et le note dans le rapport.
- **Test lié au dépôt de développement.** `tests/test_app_avancement.py::test_depot_principal_complet_si_present` lit `~/Dev/Who-Spoke` s'il existe. Sur la machine du projet, il échoue tant que les expériences en cours n'ont pas leur en-tête. Sur une machine vierge, il est sauté.
- **Port occupé.** L'application écoute sur 7860 ; en cas de conflit, `--port`.
