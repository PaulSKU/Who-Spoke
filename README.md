# Who Spoke?

Système de diarisation de locuteurs : à partir d'un enregistrement, déterminer qui parle et quand, en estimant lui-même le nombre de locuteurs. La cible d'évaluation est constituée d'enregistrements en français, de conditions et de nombres de locuteurs variés.

## Installation

Pas-à-pas complet, durées mesurées, problèmes connus (ffmpeg sur macOS 14, dossier `envs/`) et vérification automatique d'une installation : [`docs/installation.md`](docs/installation.md).

Prérequis : [uv](https://docs.astral.sh/uv/) et l'exécutable `ffmpeg` accessibles dans le `PATH`. Seul l'exécutable est requis, et non les bibliothèques partagées de ffmpeg : l'audio est normalisé par ffmpeg en sous-processus, puis passé aux pipelines en mémoire (décision D16).

```bash
uv sync
cp .env.example .env    # puis renseigner HF_TOKEN (jeton Hugging Face)
uv run python scripts/check_env.py
uv run python scripts/prefetch_models.py   # une fois, avec accès réseau : modèles aux révisions figées
uv run pytest
```

Le modèle pyannote est à accès restreint : accepter ses conditions sur le Hub Hugging Face avant le préchargement. Le script télécharge les modèles dans le cache Hugging Face, puis vérifie qu'ils se chargent hors ligne. Ensuite, aucun accès réseau n'est nécessaire.

La suite par défaut exclut les tests lents. Le test de reproduction d'EXP-0001 (RTTM d'ES2004a identique à l'octet près, environ 1 min en MPS, `HF_TOKEN` et audio AMI requis) se lance à part, avant toute modification de l'enveloppe pyannote (D19, amendement 5) :

```bash
uv run pytest -m lent
```

Le périphérique de calcul est choisi automatiquement (CUDA, puis MPS, puis CPU) et peut être forcé.

## Lancer l'interface

```bash
uv run python -m app.app             # moteurs réels
uv run python -m app.app --factice   # moteur factice, sans calcul (démonstration de l'interface seule)
```

Puis ouvrir http://127.0.0.1:7860 dans un navigateur. Le serveur est local : aucun lien public, aucune connexion vers l'extérieur. Les modèles sont lus dans le cache local, et la télémétrie des bibliothèques est coupée (D27). Il faut avoir lancé `scripts/prefetch_models.py` une fois auparavant. Options : `--port` pour changer de port ; `--depot` pour lire les expériences d'un autre dossier du dépôt.

| Onglet | Rôle |
|---|---|
| Analyse | Dépôt d'un fichier audio de tout format ; choix du moteur (pyannote community-1, baseline MFCC, ECAPA ou WeSpeaker), du nombre de locuteurs (automatique, imposé ou fourchette) et du périphérique ; avancement avec temps restant ; forme d'onde et timeline des locuteurs, écoute d'un segment au clic, zoom ; statistiques et renommage des locuteurs ; exports RTTM et JSON. Avec une référence RTTM : DER décomposé et carte des erreurs. Option de comparaison de deux moteurs sur le même fichier |
| Pipeline | Étapes et réglages effectifs de chaque moteur, en lecture seule, générés depuis les expériences et le catalogue |
| Avancement | Expériences, verdicts, décomposition de l'erreur par les oracles, décisions et file d'attente, générés depuis le dépôt |
| Glossaire | Vocabulaire du projet, lié depuis les autres onglets |

Pour une réunion de 30 min, l'analyse prend environ 1 min 30 s avec pyannote en MPS, et moins d'une minute avec les baselines en CPU. Détails techniques, vérifications hors ligne et limites connues : `app/README.md`.

## Commande en ligne

La même analyse que l'onglet « Analyse », sans l'interface, hors ligne et avec les mêmes moteurs :

```bash
uv run whospoke diarize reunion.m4a                                   # pyannote, nombre de locuteurs estimé, RTTM sur la sortie standard
uv run whospoke diarize reunion.m4a --moteur baseline-ecapa --locuteurs 4 --sortie json -o reunion.json
uv run whospoke diarize reunion.m4a --locuteurs 2-6                   # fourchette (pyannote seulement)
```

Options : `--moteur` (`pyannote-community-1`, `baseline-mfcc`, `baseline-ecapa`, `baseline-wespeaker`), `--locuteurs` (`auto`, `N` ou `MIN-MAX`), `--peripherique`, `--sortie` (`rttm` ou `json`), `-o`. La commande lit la configuration des moteurs dans `experiments/` : elle s'utilise depuis un clone du dépôt.

## Documentation

| Document | Contenu |
|---|---|
| `docs/cadrage.md` | Décisions initiales D1 à D15, contraintes de la cible |
| `docs/decisions/` | Décisions suivantes (D16 et au-delà) |
| `docs/planning.md` | Planning du sprint et file d'attente des expériences |
| `docs/methode.md` | Conventions, arborescence, formats |
| `docs/protocole-eval.md` | Protocole d'évaluation figé |
| `docs/corpus.md` | Fiche des corpus |
| `docs/corpus-maison/` | Consentement, protocole d'enregistrement et conventions d'annotation du corpus maison |
| `docs/glossaire.md` | Concepts et vocabulaire, dans l'ordre de lecture |
| `docs/recherche/` | Recherche documentaire (corpus, veille sur les modèles) |
| `docs/maquettes/` | Maquettes de l'interface |
| `app/README.md` | Application de démonstration : fonctionnement, vérifications, limites |
| [`docs/installation.md`](docs/installation.md) | Installation pas à pas, durées mesurées, problèmes connus, vérification sur machine vierge |
| [`docs/licences.md`](docs/licences.md) | Licences des modèles, des fichiers de tiers, des dépendances et des corpus |
| `docs/corpus-maison/guide-annotation.md` | Pas-à-pas de la chaîne du corpus maison (synchronisation, pré-annotation, annotation, contrôle) |
| `experiments/`, `analyses/` | Expériences et analyses a posteriori, avec leur interprétation (`notes.md`) |
| `docs/journal.md` | Journal de bord |
| `results/leaderboard.csv` | Une ligne par expérience et par jeu évalué |

## État d'avancement

Au 1er novembre 2026.

| Chantier | État |
|---|---|
| Cadrage, méthode, protocole d'évaluation | Fait (D1 à D27 ; D24 et D25 réservées) |
| Chaîne d'évaluation (DER, JER, chevauchement, nombre de locuteurs, bootstrap) | Faite, testée |
| Corpus AMI, micro de salle (dev et test) | Préparé |
| pyannote community-1 | Intégré ; résultat publié reproduit sur AMI (EXP-0001) ; modèle figé à une révision (D18) |
| Baseline classique (énergie, MFCC, regroupement) | Faite (EXP-0002, EXP-0009) |
| Diagnostics oracles (détection, nombre de locuteurs) | Faits (EXP-0003 à EXP-0006) |
| Empreintes neuronales (D8, D22) | Faites (EXP-0010 à EXP-0015) : ECAPA retenue pour la baseline ; la parole manquée par la détection d'énergie devient l'erreur principale |
| Analyses a posteriori | A-0001 : sensibilité de la référence de SUMM-RE à la convention de découpage |
| Moteurs supplémentaires (D23) | File d'attente : NeMo Sortformer v2 (prochain), Nemotron 3 Diarization, puis comparaisons cloud |
| SUMM-RE (validation en français) | Préparé (dev 36, test 37 réunions) ; pyannote, oracle et baselines MFCC, ECAPA et WeSpeaker évalués (EXP-0007 à EXP-0009, EXP-0012, EXP-0015) |
| Corpus maison (3 réunions en français) | Documents prêts ; enregistrements prévus les 4 et 5 novembre |
| Interface de démonstration (D17, D26) | Faite et fusionnée : onglets Analyse, Pipeline, Avancement et Glossaire ; essai avec les vrais moteurs et fonctionnement hors ligne vérifiés (D27) |

Résultats sur les partitions de test, chevauchements comptés :

| Expérience | Corpus | DER sans collar | DER collar 0,25 s | JER | Nombre de locuteurs exact | Temps pour 30 min d'audio |
|---|---|---|---|---|---|---|
| EXP-0001 — pyannote community-1 | AMI, micro de salle (16 réunions) | 19,9 % | 13,2 % | 27,1 % | 12/16 | ≈ 1 min 30 s (MPS) ; ≈ 24 min (CPU) |
| EXP-0002 — baseline MFCC | AMI, micro de salle | 64,4 % | 61,2 % | 70,6 % | 0/16 | ≈ 3 s (CPU) |
| EXP-0007 — pyannote community-1 | SUMM-RE, français (37 réunions) | 26,3 % | 14,8 % | 28,7 % | 31/37 | ≈ 1 min 30 s (MPS) ; ≈ 23 min (CPU) |
| EXP-0009 — baseline MFCC | SUMM-RE, français | 49,4 % | 42,7 % | 61,2 % | 17/37 | ≈ 2 s (CPU) |
| EXP-0010 — baseline ECAPA | AMI, micro de salle | 45,9 % | 40,9 % | 51,2 % | 7/16 | ≈ 26 s (CPU) |
| EXP-0013 — baseline WeSpeaker | AMI, micro de salle | 49,2 % | 44,0 % | 51,0 % | 0/16 | ≈ 36 s (CPU) |
| EXP-0012 — baseline ECAPA | SUMM-RE, français | 33,4 % | 24,4 % | 39,2 % | 28/37 | non exploitable (batterie) |
| EXP-0015 — baseline WeSpeaker | SUMM-RE, français | 35,9 % | 26,7 % | 44,3 % | 23/37 | ≈ 39 s (CPU) |

Les chiffres sur AMI sont optimistes pour pyannote, qui a vu ce corpus à l'entraînement (`docs/corpus.md` §9). SUMM-RE est en français, mais il est enregistré en micros-casques, pas en micro de salle. Sur SUMM-RE, le DER sans collar dépend fortement de la convention de découpage de la référence (jusqu'à 8 points pour pyannote), alors que le DER avec collar n'en dépend presque pas (analyse A-0001) : les deux sont toujours rapportés. WeSpeaker est le modèle d'empreintes de pyannote : l'écart entre EXP-0013 et EXP-0001 (29 points sur AMI, dont 21 de parole manquée) mesure ce que pyannote doit à sa segmentation neuronale et à son regroupement, et non à ses empreintes. Les expériences et leur interprétation sont dans `experiments/` et `results/leaderboard.csv`.

## Licence

Code et documentation sous licence MIT (`LICENSE`). Les modèles, fichiers de tiers et corpus gardent leur licence : voir [`docs/licences.md`](docs/licences.md). L'intégration continue (`.github/workflows/tests.yml`) lance la suite rapide à chaque envoi, sous Linux, avec torch en CPU, sans modèle ni jeton.
