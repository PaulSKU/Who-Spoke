# CLAUDE.md — consignes permanentes pour Claude Code

## Projet

« Who Spoke? » : système de diarisation de locuteurs (qui parle, et quand), réalisé en trois semaines dans le cadre d'une piscine d'entrée en laboratoire. L'évaluation finale porte sur des enregistrements **en français**, inconnus, de conditions et de nombres de locuteurs variés, remis en direct. Le système doit **estimer lui-même le nombre de locuteurs**. Le rendu est évalué autant sur la qualité de l'outil que sur la rigueur et la traçabilité de la démarche.

## Documents à lire

| Quand | Quoi |
|---|---|
| Au début de chaque session | `docs/methode.md` (conventions, formats, boucle de travail) |
| Avant toute tâche liée à une décision | La fiche citée dans le prompt (`docs/cadrage.md` pour D1 à D15, `docs/decisions/` au-delà) |
| Avant tout code d'évaluation ou toute expérience | `docs/protocole-eval.md` |
| Avant tout téléchargement ou traitement de données | `docs/corpus.md` |

En cas de contradiction entre un prompt et ces documents, il faut le signaler et demander, sans trancher seul.

## Règles impératives

1. **Langue.** Documentation, commentaires, messages de commit et journal en français. Identifiants de code en anglais.
2. **Données.** Ne jamais ajouter à git d'audio, de `.env`, de jeton, de cache de modèle ni de nom réel de participant. Vérifier `git status` avant chaque commit.
3. **Expériences.** Respecter strictement le format de `docs/methode.md` §4.2 et §4.3. Ne jamais modifier une expérience déjà exécutée. Toute correction donne une nouvelle expérience `EXP-NNNN` (numéro suivant).
4. **Arbre propre.** Commiter le code avant de lancer une expérience. Le script d'évaluation consigne `arbre_propre`.
5. **Ablation.** Une seule variable modifiée par rapport à l'expérience de référence indiquée dans `config.yaml`.
6. **Partitions.** Ne jamais utiliser une partition `test` pour régler un paramètre.
7. **Leaderboard.** `results/leaderboard.csv` n'est alimenté que par le script d'évaluation.
8. **Dépendances.** Toute nouvelle dépendance passe par `uv add`. Signaler dans le compte rendu chaque dépendance ajoutée et sa raison.
9. **Décisions.** Ne prendre aucune décision de conception non couverte par une fiche. Proposer les options dans le compte rendu.
10. **Tests.** `uv run pytest` doit réussir avant tout commit de code. Les tests du protocole d'évaluation (`docs/protocole-eval.md` §6) ne sont jamais désactivés.

## Environnement

| Élément | Valeur |
|---|---|
| Machine principale | MacBook Pro M2 Pro (macOS, Apple Silicon) |
| Gestionnaire | uv ; Python 3.11 ; versions figées dans `uv.lock` |
| Périphérique de calcul | Choix automatique CUDA, puis MPS, puis CPU, forçable par option (`--device`) |
| Audio | Toute entrée normalisée en WAV 16 kHz mono via ffmpeg avant traitement |
| Secrets | `HF_TOKEN` lu depuis `.env` (modèle dans `.env.example`) |
| NeMo | Environnement séparé, jamais dans l'environnement uv principal |

## Commandes usuelles

```bash
uv sync                      # installer l'environnement
uv run pytest                # tests
uv run python scripts/...    # points d'entrée
```

## Fin de session

1. Commiter selon les conventions de `docs/methode.md` §6, en commençant par un commit `docs:` distinct pour les documents modifiés dans `docs/` depuis la session précédente sans avoir été commités.
2. Ajouter une entrée factuelle à `docs/journal.md` (format §4.5) : ce qui a été fait, les expériences produites, les problèmes rencontrés. L'interprétation des résultats est laissée au cockpit.
3. Terminer par un compte rendu court : fichiers créés ou modifiés, expériences et métriques principales, points nécessitant une décision.
4. Pousser sur `origin main`.
