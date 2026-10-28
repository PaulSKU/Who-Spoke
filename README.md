# Who Spoke?

Système de diarisation de locuteurs : à partir d'un enregistrement, déterminer qui parle et quand, en estimant lui-même le nombre de locuteurs. La cible d'évaluation est constituée d'enregistrements en français, de conditions et de nombres de locuteurs variés.

## Installation

Prérequis : [uv](https://docs.astral.sh/uv/) et l'exécutable `ffmpeg` accessibles dans le `PATH`. Seul l'exécutable est requis, et non les bibliothèques partagées de ffmpeg : l'audio est normalisé par ffmpeg en sous-processus, puis passé aux pipelines en mémoire (décision D16).

```bash
uv sync
cp .env.example .env    # puis renseigner HF_TOKEN (jeton Hugging Face)
uv run python scripts/check_env.py
uv run pytest
```

La suite par défaut exclut les tests lents. Le test de reproduction d'EXP-0001 (RTTM d'ES2004a identique à l'octet près, environ 1 min en MPS, `HF_TOKEN` et audio AMI requis) se lance à part, avant toute modification de l'enveloppe pyannote (D19, amendement 5) :

```bash
uv run pytest -m lent
```

Le périphérique de calcul est choisi automatiquement (CUDA, puis MPS, puis CPU) et peut être forcé.

## Documentation

| Document | Contenu |
|---|---|
| `docs/cadrage.md` | Décisions initiales D1 à D15, contraintes de la cible |
| `docs/decisions/` | Décisions suivantes (D16 et au-delà) |
| `docs/methode.md` | Conventions, arborescence, formats |
| `docs/protocole-eval.md` | Protocole d'évaluation figé |
| `docs/corpus.md` | Fiche des corpus |
| `docs/corpus-maison/` | Consentement, protocole d'enregistrement et conventions d'annotation du corpus maison |
| `docs/glossaire.md` | Concepts et vocabulaire, dans l'ordre de lecture |
| `docs/recherche/` | Recherche documentaire sur les corpus |
| `docs/journal.md` | Journal de bord |
| `results/leaderboard.csv` | Une ligne par expérience et par jeu évalué |

## État d'avancement

Au 28 octobre 2026 (fin du deuxième jour).

| Chantier | État |
|---|---|
| Cadrage, méthode, protocole d'évaluation | Fait (D1 à D19) |
| Chaîne d'évaluation (DER, JER, chevauchement, nombre de locuteurs, bootstrap) | Faite, testée |
| Corpus AMI, micro de salle (dev et test) | Préparé |
| pyannote community-1 | Intégré ; résultat publié reproduit sur AMI (EXP-0001) |
| Baseline classique (énergie, MFCC, regroupement) | Faite (EXP-0002) |
| Diagnostics oracles (détection, nombre de locuteurs) | Faits (EXP-0003 à EXP-0006) |
| Empreintes neuronales (D8) | À faire |
| NeMo | À faire (essai borné) |
| SUMM-RE (validation en français) | À préparer |
| Corpus maison (3 réunions en français) | Documents prêts ; enregistrements à faire |
| Interface de démonstration et page Pipeline (D17) | Spécifiée ; à construire |

Résultats sur le test AMI en micro de salle (16 réunions), sans collar, chevauchements comptés :

| Expérience | DER | JER | Nombre de locuteurs exact | Temps pour 30 min d'audio |
|---|---|---|---|---|
| EXP-0001 — pyannote community-1 | 19,9 % | 27,1 % | 12/16 | ≈ 1 min 30 s (MPS) ; ≈ 24 min (CPU) |
| EXP-0002 — baseline MFCC | 64,4 % | 70,6 % | 0/16 | ≈ 3 s (CPU) |

Ces chiffres sont optimistes pour pyannote, qui a vu AMI à l'entraînement (`docs/corpus.md` §9). Ils ne disent encore rien des réunions en français. Les expériences et leur interprétation sont dans `experiments/` et `results/leaderboard.csv`.
