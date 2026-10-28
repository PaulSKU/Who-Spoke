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

## 2026-10-27 — Interprétation de V5 (cockpit)

Objectif : interpréter les résultats de V5 et décider du mode d'entrée audio.
Réalisé : lecture du dépôt (commit 58f1b5d) et des résultats de V5 ; rédaction de la fiche D16.
Résultats (interprétation) :
- Temps de calcul : en MPS, RTF de 0,055, soit environ 18 fois plus rapide que le temps réel ; une réunion de 30 min se traite en moins de 2 min. En CPU seul, RTF de 0,87 : une réunion de 30 min prend environ 26 min. C'est utilisable hors ligne, mais limite pour une démonstration en direct sans GPU Apple. À signaler au tuteur, qui a demandé ce chiffre.
- DER sans collar de 25,2 % sur une seule réunion, contre 19,9 % publié pour community-1 sur les 16 réunions de test. Les deux chiffres ne sont pas comparables : la difficulté varie fortement d'une réunion à l'autre. C'est l'expérience EXP-0001, sur la partition de test complète, qui vérifiera la reproduction. Ces chiffres restent une borne optimiste, puisque AMI figure dans l'entraînement de pyannote.
- La parole manquée domine (16,4 points sur 25,2) : en champ lointain, il s'agit vraisemblablement de parole faible ou en chevauchement **[probable]**. La décomposition par zone de chevauchement (protocole §3.2, pas encore implémentée) permettra de le vérifier.
- Le collar de 0,25 s retire 7,5 points de DER : une part importante des erreurs se situe à moins de 250 ms des frontières.
- JER de 30,2 %, supérieur au DER : l'erreur semble concentrée sur au moins un locuteur, probablement un locuteur qui parle peu **[probable]**, à vérifier locuteur par locuteur.
- Métriques identiques en MPS et en CPU : le choix du périphérique ne change pas les résultats.
Décisions : D16 proposée (entrée audio en mémoire).
Problèmes : aucun bloquant.
Suite : après validation de D16, préparer EXP-0001 (pyannote community-1 sur AMI SDM, dev puis test), avec le script d'évaluation complet (protocole §3.2 et §3.4), `src/whospoke/audio.py` et `scripts/data/get_ami.py`.

## 2026-10-27 — Chaîne d'évaluation complète et EXP-0001 (Claude Code)

Objectif : implémenter D16, les métriques complètes du protocole, la préparation d'AMI, l'enveloppe community-1, les scripts d'exécution et d'évaluation, puis exécuter EXP-0001.
Réalisé :
- Commit `docs:` des documents du cockpit (D16 actée, méthode §4.2–4.4, protocole §3.5) ; en-tête du leaderboard avec `rtf_cpu`.
- `src/whospoke/audio.py` (D16) : `normalize` (ffmpeg en sous-processus, code de retour contrôlé, pas de fichier partiel) et `load_waveform` (contrôle de 16 kHz, du mono et du PCM 16 bits). Tests sur stéréo 44,1 kHz, m4a, fichier invalide. `scripts/v5_smoke_test.py` réécrit sur ce module.
- `src/whospoke/evaluation/metrics.py` : décomposition par zone avec et sans chevauchement (§3.2), nombre de locuteurs (§3.4, compté dans l'UEM), lignes par fichier, intervalle de confiance par bootstrap sur les fichiers (1 000 tirages, graine 0, différence appariée possible) et décompte des fichiers gagnants (§4). 35 tests au total.
- `scripts/data/get_ami.py` : 34 réunions (dev 18, 9,67 h ; test 16, 9,06 h), RTTM `only_words` et UEM du dépôt `pyannote/AMI-diarization-setup` au commit `67c2d539…` ; uri réécrit en `ami__<réunion>` ; manifeste, listes, UEM dans `data/splits/ami/uem/`. Sous-ensemble de mesure du temps : ES2004a et TS3003a (42,6 min).
- `src/whospoke/pipelines/pyannote_community1.py`, `scripts/run_experiment.py`, `scripts/evaluate.py`.
- EXP-0001 exécutée en MPS (dev et test), puis en CPU seul sur `temps.txt`, sous `caffeinate -i`, sur secteur.
Résultats : EXP-0001 (sans collar, chevauchements comptés)

| Jeu | DER | Manquée | Fausse alarme | Confusion | DER `collar_0_25` | JER | DER sans chev. | DER chev. | MAE K | K exact |
|---|---|---|---|---|---|---|---|---|---|---|
| dev | 18,64 % | 8,10 % | 4,86 % | 5,68 % | 11,15 % | 23,75 % | 13,55 % | 33,37 % | 0,11 | 88,89 % |
| test | 19,92 % | 11,16 % | 3,81 % | 4,94 % | 13,21 % | 27,07 % | 13,76 % | 36,59 % | 0,38 | 75,00 % |

- Temps : MPS, RTF 0,0500 (dev) et 0,0509 (test), chargement des modèles 6,05 s, soit environ 91 s pour 30 min. CPU seul (6 fils), sur 2 555 s d'audio : RTF 0,7978, soit environ 24 min pour 30 min.
- Valeur publiée pour community-1 sur AMI SDM test : 19,9 %. ES2004a : 25,23 %, identique à V5.
- Test, trois DER les plus élevés : TS3003a 26,10 % (K̂ = 2 pour K = 4), EN2002d 26,00 %, ES2004a 25,23 %, avec la parole manquée dominante dans les trois cas.
- Erreurs sur le nombre de locuteurs : dev IS1008b +1, ES2011a −1 ; test IS1009b +1, ES2004b +2, ES2004c +1, TS3003a −2.
Décisions : aucune.
Problèmes :
- Miroir AMI d'Édimbourg lent (environ 0,3 Mo/s par connexion), avec un 403 transitoire sous 8 connexions simultanées. Sept fichiers ont été tronqués sans erreur, par une connexion close prématurément. Le contrôle de cohérence UEM/signal les a détectés. Corrections : reprise par en-tête Range, nouvelles tentatives, contrôle de la taille annoncée. Les tailles des 34 fichiers ont été vérifiées contre le Content-Length du serveur.
- `arbre_propre = false` dans les deux `results_ami_*.json`. Pendant la mesure CPU et l'évaluation, des documents du cockpit étaient modifiés ou non suivis dans `docs/` : D17, glossaire, méthode, conventions d'annotation. L'exécution MPS a eu lieu sur un arbre propre. Le code est resté inchangé (commit d9f177a pour les deux exécutions et l'évaluation).
- En CPU seul : `UserWarning: std(): degrees of freedom is <= 0`, déjà observé en V5.
Suite : interprétation au cockpit (`notes.md`) ; décision sur le statut `arbre_propre` d'EXP-0001.

## 2026-10-28 — Interprétation d'EXP-0001 (cockpit)

Objectif : interpréter EXP-0001 et trancher les points soulevés par la session Claude Code.
Réalisé : lecture des résultats et des fichiers par réunion ; rédaction de `notes.md` d'EXP-0001 (observations et interprétation) ; fiche D18 proposée.
Résultats : EXP-0001 reproduit la valeur publiée (19,92 % contre 19,9 % sur le test AMI SDM, sans collar). Le chevauchement, qui représente 27 % de la parole de référence, concentre la moitié de l'erreur. Le nombre de locuteurs est faux dans 4 réunions de test sur 16. RTF de 0,05 en MPS et de 0,80 en CPU seul.
Décisions : D18 actée (arbre propre défini sur le code, la configuration et les données ; requalification d'EXP-0001 ; précisions du protocole).
Problèmes : `arbre_propre: false` sur EXP-0001, causé par l'écriture de documents du cockpit pendant la mesure CPU. Le défaut venait de la règle, pas du résultat. Le préchauffage de 60 s, demandé dans le prompt du cockpit, contredisait le protocole §3.5 : c'est le protocole qui est aligné (D18).
Suite : après validation de D18, faire appliquer D18 par Claude Code, puis spécifier la baseline (D19).
