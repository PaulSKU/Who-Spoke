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

Au 29 octobre 2026 (troisième jour).

| Chantier | État |
|---|---|
| Cadrage, méthode, protocole d'évaluation | Fait (D1 à D20) |
| Chaîne d'évaluation (DER, JER, chevauchement, nombre de locuteurs, bootstrap) | Faite, testée |
| Corpus AMI, micro de salle (dev et test) | Préparé |
| pyannote community-1 | Intégré ; résultat publié reproduit sur AMI (EXP-0001) |
| Baseline classique (énergie, MFCC, regroupement) | Faite (EXP-0002) |
| Diagnostics oracles (détection, nombre de locuteurs) | Faits (EXP-0003 à EXP-0006) |
| Empreintes neuronales (D8) | À faire |
| NeMo | À faire (essai borné) |
| SUMM-RE (validation en français) | Préparé (dev 36, test 37 réunions) ; pyannote, oracle et baseline évalués (EXP-0007 à EXP-0009) |
| Corpus maison (3 réunions en français) | Documents prêts ; enregistrements à faire |
| Interface de démonstration et page Pipeline (D17) | Spécifiée ; à construire |

Résultats sur les partitions de test, chevauchements comptés :

| Expérience | Corpus | DER sans collar | DER collar 0,25 s | JER | Nombre de locuteurs exact | Temps pour 30 min d'audio |
|---|---|---|---|---|---|---|
| EXP-0001 — pyannote community-1 | AMI, micro de salle (16 réunions) | 19,9 % | 13,2 % | 27,1 % | 12/16 | ≈ 1 min 30 s (MPS) ; ≈ 24 min (CPU) |
| EXP-0002 — baseline MFCC | AMI, micro de salle | 64,4 % | 61,2 % | 70,6 % | 0/16 | ≈ 3 s (CPU) |
| EXP-0007 — pyannote community-1 | SUMM-RE, français (37 réunions) | 26,3 % | 14,8 % | 28,7 % | 31/37 | ≈ 1 min 30 s (MPS) ; ≈ 23 min (CPU) |
| EXP-0009 — baseline MFCC | SUMM-RE, français | 49,4 % | 42,7 % | 61,2 % | 17/37 | ≈ 2 s (CPU) |

Les chiffres sur AMI sont optimistes pour pyannote, qui a vu ce corpus à l'entraînement (`docs/corpus.md` §9). SUMM-RE est en français, mais il est enregistré en micros-casques, pas en micro de salle. Les expériences et leur interprétation sont dans `experiments/` et `results/leaderboard.csv`.
