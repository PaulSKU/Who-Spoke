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

## 2026-10-27 — Vérification V5 : pyannote community-1 de bout en bout (Claude Code)

Objectif : vérifier que `pyannote/speaker-diarization-community-1` tourne de bout en bout sur la machine locale, en MPS puis en CPU seul (`protocole-eval.md` §3.5), sans fixer le nombre de locuteurs. Ce n'est pas une expérience EXP : rien dans `experiments/` ni dans le leaderboard.
Réalisé :
- Commits `docs:` des documents du cockpit (cadrage v0.3, protocole v1.1, puis fiche corpus, `methode.md`, `corpus-maison/`, `recherche/`).
- `scripts/v5_smoke_test.py` : téléchargement de AMI ES2004a en SDM (`Array1-01`), de la référence `only_words/rttms/test/ES2004a.rttm` et de l'UEM commun `uems/test/ES2004a.uem` (il n'existe pas d'UEM propre à `only_words`, voir `corpus.md` §3) ; normalisation ffmpeg 16 kHz mono ; lecture du WAV par `scipy.io.wavfile` (sans torchcodec) et passage d'un dict `{"waveform", "sample_rate"}` à la pipeline. Chaque mesure tourne dans un sous-processus distinct (mémoire maximale `ru_maxrss` propre à chaque périphérique), avec un préchauffage non compté sur un extrait de 60 s. Exécution sous `caffeinate -i`, sur le commit `63b703a`.
- Réunion : 1049,35 s (17 min 29 s) ; UEM 0 à 1049,35 s ; parole de référence 923,43 s.

Résultats (aucune expérience EXP) :

| Périphérique | Chargement des modèles | Calcul | RTF | 30 min d'audio | Mémoire max. du processus |
|---|---|---|---|---|---|
| MPS | 20,10 s | 57,22 s | 0,0545 | 98 s | 879 Mo (pilote MPS : 3 508 Mo) |
| CPU (6 fils) | 6,51 s | 916,60 s | 0,8735 | 1 572 s | 2 392 Mo |

Locuteurs estimés : 4 sur MPS comme sur CPU, contre 4 dans la référence.

| Condition | DER | Manquée | Fausse alarme | Confusion | JER |
|---|---|---|---|---|---|
| `collar_0` | 25,23 % | 16,41 % | 4,50 % | 4,32 % | 30,17 % |
| `collar_0_25` | 17,68 % | 12,20 % | 3,05 % | 2,44 % | 21,74 % |

Les métriques sont identiques au centième près entre MPS et CPU. En `collar_0_25`, la parole de référence évaluée tombe à 663,72 s, parce que le collar exclut des zones de la référence.

Essai avec le chemin de fichier passé directement à la pipeline : échec. `RuntimeError: Could not load libtorchcodec`. Pour FFmpeg 9 : `Library not loaded: @rpath/libavutil.61.dylib`, cherchée dans `/opt/homebrew/opt/ffmpeg/lib/` et dans le dossier du Python uv. Le ffmpeg 9.0.2 installé via conda-forge n'expose pas ses bibliothèques partagées à torchcodec. L'erreur survient au décodage (`pyannote/audio/core/io.py`), pas au chargement de la pipeline. Le passage par un dict en mémoire fonctionne.
Décisions : aucune.
Problèmes :
- `HF_TOKEN` vide au premier lancement ; renseigné par l'utilisatrice.
- Avertissement en CPU seul : `UserWarning: std(): degrees of freedom is <= 0` (ReduceOps.cpp). Aucun avertissement capturé en MPS.
- Aucune erreur liée à l'écart torch 2.14.1 / torchaudio 2.11.0.
Suite : interprétation au cockpit ; choix du mode d'entrée audio de la chaîne (dict en mémoire, ou réparation de torchcodec).
