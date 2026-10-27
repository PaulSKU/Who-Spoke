# Who Spoke?

Système de diarisation de locuteurs : à partir d'un enregistrement, déterminer qui parle et quand, en estimant lui-même le nombre de locuteurs. La cible d'évaluation est constituée d'enregistrements en français, de conditions et de nombres de locuteurs variés.

## Installation

Prérequis : [uv](https://docs.astral.sh/uv/) et ffmpeg accessibles dans le `PATH`.

```bash
uv sync
cp .env.example .env    # puis renseigner HF_TOKEN (jeton Hugging Face)
uv run python scripts/check_env.py
uv run pytest
```

Le périphérique de calcul est choisi automatiquement (CUDA, puis MPS, puis CPU) et peut être forcé.

## Documentation

| Document | Contenu |
|---|---|
| `docs/cadrage.md` | Décisions initiales D1 à D15 |
| `docs/methode.md` | Conventions, arborescence, formats |
| `docs/protocole-eval.md` | Protocole d'évaluation figé |
| `docs/corpus.md` | Fiche des corpus |
| `docs/journal.md` | Journal de bord |

## État d'avancement

- Dépôt initialisé : arborescence, environnement uv (Python 3.11), choix du périphérique.
- Métriques d'évaluation (DER et JER, conditions `collar_0` et `collar_0_25`) et tests obligatoires du protocole.
- Aucune pipeline de diarisation ni aucune donnée à ce stade.
