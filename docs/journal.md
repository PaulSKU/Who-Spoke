# Journal de bord

Entrées datées, ajoutées en fin de fichier, au format de `docs/methode.md` §4.5 :

```markdown
## AAAA-MM-JJ — <titre de la session> (<cockpit | Claude Code | manuel>)

Objectif : …
Réalisé : …
Résultats : EXP-…
Décisions : D…
Problèmes : …
Suite : …
```

## 2026-10-27 — Initialisation du dépôt (Claude Code)

Objectif : initialiser le dépôt selon `docs/methode.md` §2, sans code de diarisation ni données.
Réalisé :
- Vérifications V1–V3 (données fournies par l'utilisatrice, complétées par la session) : macOS 14.1.2 (arm64), 16 Go de RAM ; 25 Gio libres (95 %) au relevé initial, 21 Gio libres (96 %) au relevé de la session ; uv 0.11.28. Homebrew inutilisable sur macOS 14 pour ffmpeg (compilation depuis les sources) ; ffmpeg installé via conda-forge dans un environnement conda dédié et exposé dans `~/.local/bin`. ffmpeg était introuvable au début de la session et présent à la fin (version 9.0.2).
- Commit `docs:` initial de `CLAUDE.md` et `docs/`.
- Arborescence de `methode.md` §2, `.gitignore`, projet uv (Python 3.11, paquet `whospoke`), `.env.example`, en-tête de `results/leaderboard.csv`, `data/README.md`, squelettes de `journal.md`, `corpus.md`, `glossaire.md`, `README.md`.
- `src/whospoke/device.py` (CUDA > MPS > CPU, forçable) et 7 tests.
- `src/whospoke/evaluation/metrics.py` (DER décomposé et JER, conditions `collar_0` et `collar_0_25`, agrégation en rapport des sommes) et les six tests de `protocole-eval.md` §6.
- `scripts/check_env.py`.
- `uv run pytest` : 13 tests réussis. Test collar : décalage de 0,2 s, DER > 0 avec `collar=0.3`, DER = 0 avec `collar=0.4` et `collar=0.5` ; `collar` est donc bien une largeur totale (moitié de chaque côté).
- `check_env` : Python 3.11.15, torch 2.14.1, MPS disponible, périphérique automatique `mps`, ffmpeg présent, HF_TOKEN absent (pas de `.env`).
Résultats : aucune expérience.
Décisions : aucune.
Problèmes : ffmpeg absent du système au départ (voir ci-dessus). torchaudio résolu en 2.11.0 avec torch 2.14.1.
Suite : créer `.env` avec HF_TOKEN ; V5 (pyannote de bout en bout, RTF CPU et MPS).
