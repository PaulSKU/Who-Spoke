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

## 2026-10-28 — Application de D18 (Claude Code)

Objectif : appliquer D18 (arbre propre sur les chemins contrôlés, requalification d'EXP-0001, précisions du protocole).
Réalisé :
- Commit `docs:` des documents du cockpit : D17, D18, glossaire réordonné, méthode §4.6, journal du 28/10, `notes.md` d'EXP-0001, réalignement des tableaux des conventions d'annotation.
- Documentation : `methode.md` §4.2 (`execution_<device>.json`, troisième exception à l'immuabilité), §6 (chemins contrôlés), §7 (SHA-256 du fichier brut, options documentées) ; `protocole-eval.md` révision 1.2, §3.2, §3.4 et §3.5.
- `src/whospoke/experiment.py` : `is_controlled`, `tree_is_clean` ; `git_state` liste tous les fichiers non commités, sans exclusion, et calcule `clean` sur les seuls chemins contrôlés.
- `scripts/evaluate.py` : option `--requalifier` ; `arbre_propre` recalculé selon D18 à partir des `fichiers_non_commites` consignés par les exécutions, avec en plus le même commit pour toutes les exécutions ; option `--leaderboard` documentée. Options `--config` (`run_experiment.py`) et `--child` (`v5_smoke_test.py`) documentées dans `--help`.
- Tests : règle de l'arbre propre, requalification, et intégration de l'enveloppe community-1 sur un signal synthétique de 12 s, ignorée sans `HF_TOKEN`.
Résultats : EXP-0001 requalifiée, `arbre_propre` passe de false à true dans `results_ami_dev.json` et `results_ami_test.json`. Le diff ne touche que les clés `arbre_propre` et `requalification`. Leaderboard inchangé. `uv run pytest` : 59 tests réussis, dont les 3 d'intégration exécutés ; 3 ignorés lorsque `HF_TOKEN` est vide.
Décisions : aucune.
Problèmes : aucun bloquant. Le bloc `requalification` comporte un champ `sources` (liste des `execution_*.json` utilisés) en plus des quatre champs de D18.
Suite : spécification de la baseline (D19) au cockpit.

## 2026-10-28 — Contrat des moteurs, baseline et EXP-0002 (Claude Code)

Objectif : appliquer D19 (contrat commun, enveloppe pyannote au contrat, baseline, oracles, trace, balayage, catalogue), puis exécuter EXP-0002.
Réalisé :
- Commit `docs:` de D19.
- `scripts/evaluate.py` : refus d'évaluer si le `config_sha256` d'un `execution_*.json` diffère de l'empreinte de `config.yaml`. Quand `device` vaut `cpu`, `temps_cpu` est tiré de l'exécution principale, restreinte aux fichiers de `mesure_cpu.liste`.
- `src/whospoke/pipelines/base.py` : `Engine`, `Resultat`, `Setting`, `run(waveform, sample_rate, uri, num_speakers, speech, progress)`, `describe()`.
- Enveloppe pyannote au contrat : nombre de locuteurs par fichier à l'appel, `NotImplementedError` sur `speech`, progression par le hook de pyannote, `describe()` lu sur la pipeline chargée (sans le jeton). Le mode estimé redonne à l'identique le RTTM d'EXP-0001 sur ES2004a, en MPS (test).
- `src/whospoke/pipelines/baseline.py` : étapes et valeurs de D19 §2, trace (§3), `prepare`/`finish` pour le balayage de θ. 14 tests sur signaux synthétiques.
- `src/whospoke/pipelines/catalogue.yaml` : 23 réglages pyannote, 23 réglages baseline ; test de couverture de `describe()`.
- `scripts/run_experiment.py` : clés `mode_n_locuteurs`, `detection_oracle` et `balayage`, option `--trace`. `methode.md` §4.2 : format du balayage et de la trace. `.gitignore` : `experiments/*/trace/`.
- EXP-0002 exécutée en CPU avec `--trace`, sur le commit 540bb5e (arbre propre), puis évaluée.
Résultats : EXP-0002 (sans collar, chevauchements comptés), θ retenu = 0,95 (DER dev minimal ; 6,06 locuteurs en moyenne contre 4).

| Jeu | DER | Manquée | Fausse alarme | Confusion | DER `collar_0_25` | JER | DER sans chev. | DER chev. | MAE K | K exact |
|---|---|---|---|---|---|---|---|---|---|---|
| dev | 64,95 % | 30,20 % | 4,64 % | 30,11 % | 61,50 % | 70,53 % | 62,52 % | 70,54 % | 2,06 | 11,11 % |
| test | 64,38 % | 32,28 % | 4,99 % | 27,11 % | 61,21 % | 70,55 % | 61,70 % | 70,06 % | 2,00 | 0,00 % |

- Temps en CPU : RTF 0,0014 (dev) et 0,0015 (test) ; sur `temps.txt`, RTF 0,0011, soit environ 3 s pour 30 min. Balayage : 54 s de préparation des 18 fichiers, 937 s au total, l'évaluation des 29 valeurs dominant.
- Par rapport à EXP-0001 sur les mêmes fichiers : la baseline fait moins bien sur 18/18 fichiers de dev et 16/16 de test. Différence de DER (baseline − pyannote), bootstrap apparié (1 000 tirages, graine 0) : +46,31 points [40,95 ; 51,48] sur dev, +44,46 points [40,73 ; 48,70] sur test.
- Test, trois DER les plus élevés : TS3003a 79,77 % (K̂ = 8), TS3003d 79,07 % (K̂ = 8), IS1009a 75,70 % (K̂ = 8), pour K = 4.
Décisions : aucune. Deux lectures de D19 sont à confirmer (voir Problèmes).
Problèmes :
- Fenêtres de la baseline : à la lettre, la dernière fenêtre d'une région dépasse sur le silence, voire sur la région suivante. Sur signal synthétique, ces fenêtres de bord forment des groupes à part. Choix appliqué, à confirmer : les fenêtres sont bornées à leur région et gardées si 50 % de leur durée nominale y tombe ; les statistiques ne portent que sur les trames de parole.
- `n_mels` n'est pas fixé par D19 : 40 retenu, le défaut de librosa (128) laissant des filtres vides avec une FFT de 400 points. Il figure au catalogue comme « non couvert par D19 (à acter) ».
- Le silence minimal (0,2 s) comble déjà toute pause de moins de 0,2 s, si bien que la fusion des tours séparés de 200 ms ou moins ne joue que sur les pauses d'exactement 20 trames.
- Écarts entre la maquette de la page Pipeline et les valeurs lues : `embedding_exclude_overlap` vaut `True` (et non « Non ») ; `segmentation_batch_size` et `embedding_batch_size` valent 32 (et non 1).
- `device: cpu` produit `execution_cpu.json`, le même nom qu'une mesure `--mesure-cpu`. Les deux ne peuvent donc pas coexister ; d'où `temps_cpu` tiré de l'exécution principale.
Suite : interprétation au cockpit (`notes.md` d'EXP-0002) ; EXP-0003 à EXP-0005 de D19 §4.

## 2026-10-28 — Interprétation d'EXP-0002 et amendements de D19 (cockpit)

Objectif : interpréter la baseline et trancher les lectures de D19 soumises par Claude Code.
Réalisé : `notes.md` d'EXP-0002 rédigées ; D19 amendée (5 points) ; valeurs effectives de pyannote reportées dans la maquette de la page Pipeline.
Résultats : baseline à 64,4 % de DER sur le test AMI SDM, contre 19,9 % pour pyannote. Elle ne gagne que 9,4 points sur un système à un seul locuteur. La confusion plafonne à 27–30 points quel que soit θ, et la parole manquée est de 30 points. RTF de 0,0015 en CPU.
Décisions : D19 amendée (n_mels = 40 ; fenêtres bornées à leur région ; temps CPU de l'exécution principale ; fusion de 200 ms conservée ; test de reproduction marqué lent).
Problèmes : la maquette de la page Pipeline donnait trois valeurs fausses (embedding_exclude_overlap, tailles de lot), écrites d'après les défauts du code et non la configuration de community-1. C'est la raison d'être de la règle « la page lit la pipeline chargée » (D17).
Suite : session B, oracles EXP-0003 à EXP-0005.

## 2026-10-28 — Oracles EXP-0003 à EXP-0006 (Claude Code)

Objectif : appliquer l'amendement 5 de D19, puis exécuter les oracles de D19 §4 sur AMI SDM dev et test, une variable modifiée à la fois.
Réalisé :
- Commit `docs:` des documents du cockpit (amendements de D19, journal, `notes.md` d'EXP-0002).
- Marqueur pytest `lent` déclaré dans `pyproject.toml` et exclu par défaut (`addopts = "-m 'not lent'"`) ; le test de reproduction d'EXP-0001 le porte. `uv run pytest -m lent` est documenté dans le README. Suite par défaut : 87 tests ; test lent : réussi (RTTM d'ES2004a identique).
- Configurations d'EXP-0003 à EXP-0006 commitées une par une avant exécution. `notes.md` créées avec les deux sections vides.
- Baselines (EXP-0003, EXP-0004, EXP-0006) en CPU avec `--trace`, sur 3abe688, arbre propre. EXP-0004 et EXP-0006 : θ = 0,95 fixé (valeur d'EXP-0002, sans balayage). EXP-0003 et EXP-0006 gardent θ = 0,95 dans la configuration, sans effet puisque la coupe se fait au nombre imposé.
- EXP-0005 (pyannote, nombre oracle) en MPS sur 3abe688, puis mesure CPU sur `temps.txt`.
- Catalogue : `n_mels` rattaché à l'amendement 1 de D19.
Résultats (sans collar, chevauchements comptés ; RTF : périphérique de l'expérience, puis CPU sur `temps.txt`) :

| Exp. | Jeu | DER | Manquée | FA | Confusion | DER sans chev. | DER chev. | JER | MAE K | K exact | RTF | RTF CPU |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EXP-0003 | dev | 64,06 % | 30,19 | 4,64 | 29,23 | 62,00 % | 68,66 % | 72,40 % | 0,00 | 100 % | 0,0011 | 0,0008 |
| EXP-0003 | test | 63,42 % | 32,28 | 4,99 | 26,15 | 61,02 % | 68,47 % | 72,78 % | 0,00 | 100 % | 0,0012 | 0,0008 |
| EXP-0004 | dev | 54,23 % | 13,51 | 0,17 | 40,55 | 48,64 % | 68,80 % | 65,52 % | 2,00 | 11,11 % | 0,0015 | 0,0010 |
| EXP-0004 | test | 49,09 % | 14,59 | 0,14 | 34,35 | 42,25 % | 66,31 % | 63,68 % | 2,00 | 12,50 % | 0,0014 | 0,0010 |
| EXP-0005 | dev | 18,71 % | 8,10 | 4,86 | 5,75 | 13,58 % | 33,53 % | 23,60 % | 0,00 | 100 % | 0,053 | 0,9126 |
| EXP-0005 | test | 20,40 % | 11,16 | 3,81 | 5,42 | 14,60 % | 35,99 % | 26,91 % | 0,00 | 100 % | 0,057 | 0,9126 |
| EXP-0006 | dev | 51,72 % | 13,51 | 0,18 | 38,04 | 46,19 % | 66,69 % | 66,04 % | 0,00 | 100 % | 0,0014 | 0,0009 |
| EXP-0006 | test | 48,92 % | 14,59 | 0,14 | 34,19 | 42,57 % | 65,02 % | 66,81 % | 0,00 | 100 % | 0,0013 | 0,0009 |

Écart de DER sans collar à la référence, bootstrap apparié (1 000 tirages, graine 0), et fichiers améliorés :

| Exp. | Référence | dev | test |
|---|---|---|---|
| EXP-0003 | EXP-0002 | −0,89 [−2,33 ; +0,87] ; 13/18 (3 moins bons, 2 égaux) | −0,96 [−2,44 ; +0,78] ; 12/16 (2 moins bons, 2 égaux) |
| EXP-0004 | EXP-0002 | −10,71 [−14,42 ; −7,70] ; 18/18 | −15,29 [−17,79 ; −13,07] ; 16/16 |
| EXP-0006 | EXP-0004 | −2,51 [−3,76 ; −1,37] ; 14/18 (2 moins bons, 2 égaux) | −0,16 [−2,80 ; +2,22] ; 10/16 (4 moins bons, 2 égaux) |
| EXP-0005 | EXP-0001 | +0,07 [−0,16 ; +0,39] ; 1/18 (1 moins bon, 16 égaux) | +0,48 [−0,61 ; +2,50] ; 3/16 (1 moins bon, 12 égaux) |

- EXP-0005 ne modifie que les fichiers où EXP-0001 se trompait sur K. Test : IS1009b 16,37 → 13,21 %, ES2004b 16,02 → 15,24 %, ES2004c 14,21 → 13,70 %, TS3003a 26,10 → 49,36 % (K̂ = 2 dans EXP-0001, K = 4 imposé). Dev : IS1008b 14,11 → 12,90 %, ES2011a 29,00 → 33,11 %.
Décisions : aucune.
Problèmes :
- EXP-0005 a `arbre_propre: false`. L'exécution MPS a eu lieu sur 3abe688 et la mesure CPU sur e4701ba, parce que les résultats d'EXP-0003, 0004 et 0006 ont été commités entre les deux. Aucun chemin contrôlé de D18 ne diffère entre ces commits (seuls `experiments/` et `results/leaderboard.csv`). L'expérience n'a pas été modifiée. `--requalifier` ne couvre pas ce cas (il ne relit que les fichiers non commités).
- EXP-0006 ne figure pas au tableau de D19 §4 ; il a été ajouté par le prompt de la session.
Suite : interprétation au cockpit (`notes.md` d'EXP-0003 à EXP-0006) ; décision sur le statut d'EXP-0005.

## 2026-10-28 — Requalification d'EXP-0005 (Claude Code)

Objectif : appliquer l'amendement du 28/10 de D18 (exécutions d'une même expérience sur des commits différents).
Réalisé :
- Commit `docs:` de l'amendement de D18.
- `scripts/evaluate.py --requalifier` : si les `execution_*.json` portent sur des commits différents, trois conditions sont vérifiées (chaque exécution propre, `git diff --name-only` vide entre les commits sur les chemins contrôlés de D18, même `config_sha256`). Si l'une manque, refus sans rien écrire. Sinon, `arbre_propre` passe à true et le bloc `requalification` consigne en plus `commits` et `"diff_chemins_controles": "vide"`. Le cas d'un commit unique est inchangé.
- Tests (dépôt git temporaire à deux commits) : sans diff contrôlé → requalifiée ; diff sous `src/` → refus ; `config_sha256` différent → refus ; exécution sale → refus. Suite : 90 tests réussis (1 test lent exclu).
- EXP-0005 requalifiée : `arbre_propre` false → true dans `results_ami_dev.json` et `results_ami_test.json`, commits 3abe688 et e4701ba. Diff vérifié clé par clé : seules `arbre_propre` et `requalification` changent ; leaderboard inchangé.
Résultats : aucune nouvelle expérience ; métriques d'EXP-0005 inchangées.
Décisions : aucune.
Problèmes : aucun. Le commit de l'évaluation (e4701ba) n'est pas contrôlé séparément ; il coïncide ici avec celui de la mesure CPU.
Suite : interprétation au cockpit des oracles EXP-0003 à EXP-0006.

## 2026-10-28 — Interprétation des oracles EXP-0003 à EXP-0006 (cockpit)

Objectif : répartir l'erreur entre les étapes.
Réalisé : `notes.md` d'EXP-0003 à EXP-0006 rédigées.
Résultats :
- Baseline : la détection par énergie coûte 11 à 15 points (EXP-0004) ; le nombre de locuteurs oracle ne fait rien gagner (EXP-0003, EXP-0006) ; avec détection et nombre de locuteurs parfaits, il reste 14,6 points de chevauchement (plancher structurel) et 34 points de confusion dus à la représentation MFCC (EXP-0006, test).
- pyannote : le nombre de locuteurs oracle ne fait rien gagner en moyenne (+0,48 point sur le test, non significatif). Il améliore les trois surestimations, mais double le DER de TS3003a.
Décisions : aucune. Remise en question de l'amélioration n° 1 de D9, à trancher avec la candidate.
Problèmes : aucun.
Suite : décider des améliorations (D9) ; empreintes neuronales (D8) sur la référence EXP-0006 ; préparation de SUMM-RE.

## 2026-10-28 — Bloc evaluation, préparation de SUMM-RE (Claude Code)

Objectif : clore le point en suspens de D18 ; préparer SUMM-RE dev et test selon D20.
Réalisé :
- Commit `docs:` des documents du cockpit (README, cadrage, methode §5, journal, D20, notes d'EXP-0003 à EXP-0006).
- `scripts/evaluate.py` : chaque `results_*.json` reçoit un bloc `evaluation` (date, commit de l'évaluation, `arbre_propre` selon les chemins contrôlés de D18, `fichiers_non_commites`), placé avant `invalidee`. Résultats existants non modifiés. Test d'évaluation synthétique (arbre propre, arbre sale).
- Dépendance ajoutée : `pyarrow` 26.0.0 (lecture des Parquet).
- `scripts/data/get_summre.py` : révision `47cb4ec3` de `linagora/SUMM-RE` ; 57 Parquet (25,8 Go) traités un par un, SHA-256 contrôlé contre le dépôt et consigné, brut supprimé après extraction ; mélange moyen à 16 kHz ; référence à partir des mots (fusion à 200 ms) ; UEM ; listes dev, test, temps, zoom_dev, zoom_test ; contrôles de D20 §4 ; contrôle croisé avec `ggfox00000/dia-summre-test` (RTTM seuls). Relance vérifiée : rien n'est retéléchargé, le manifeste est identique. 15 tests sur données synthétiques ; suite : 107 tests réussis (1 test lent exclu).
- `docs/corpus.md` §2 et `data/README.md` mis à jour avec les valeurs mesurées.
Résultats : aucune expérience. Dev : 36 réunions, 130 pistes, 81 locuteurs, 11,89 h, chevauchement 14,5 % de la parole. Test : 37 réunions, 124 pistes, 91 locuteurs, 12,17 h, 17,2 %. Zoom : 5 réunions en dev (9,6 %), 3 en test (6,5 %). 18 locuteurs communs à dev et test. 0 mot sans horodatage. Aucun décalage mesurable supérieur à 50 ms (maximum 26,9 ms). Contrôle croisé : DER entre références de 0,00 % à 0,49 %. `temps.txt` : 007a_ECRH et 012c_EBPZ (39,5 min). Disque occupé à la fin : 2,6 Go dans `data/processed/summre/`.
Décisions : aucune.
Problèmes :
- Les pistes d'une même réunion peuvent être réparties sur deux Parquet : les mélanges sont faits après extraction de toute la partition, à partir de pistes intermédiaires en flottant 32 bits.
- La synchronisation mesurée contre le mélange complet serait toujours nulle (la piste y est incluse) : chaque piste est corrélée au mélange des autres. Sans diaphonie (8 réunions Zoom, et 101c_EDPH, codée H), le décalage n'est pas mesurable ; un critère de saillance du pic (≥ 10) l'établit.
- Les jetons SPPAS `+`, `*` et `@` sont des « mots » horodatés ; ils sont gardés (lecture littérale de D20 §3), pour 2,73 % de la parole en dev et 1,11 % en test.
- Aucune piste muette : les réunions à 3 participants n'ont que 3 pistes.
Suite : arbitrer au cockpit les jetons non lexicaux, la règle de saillance et le choix de `temps.txt` ; EXP-0007 à EXP-0009 (D20 §6).

## 2026-10-29 — Amendement 1 de D20, EXP-0007 à EXP-0009 sur SUMM-RE (Claude Code)

Objectif : appliquer l'amendement du 28/10 de D20 (jetons non lexicaux) ; exécuter les premières expériences sur SUMM-RE (D20 §6).
Réalisé :
- Commit `docs:` de l'amendement de D20 et du bloc `evaluation` de methode §4.3.
- `scripts/data/get_summre.py` : tout jeton composé uniquement de `+`, `*` ou `@` est retiré avant la construction des intervalles ; inventaire par réunion dans le manifeste (`jetons_retires`, `parole_avec_jetons_non_lexicaux_s`, qui remplace `parole_sans_jetons_non_lexicaux_s`). Option `--references` : les pistes et les mots ayant été supprimés après la préparation, les colonnes `meeting_id`, `speaker_id`, `audio_id` et `segments` des Parquet sont relues à distance (lectures partielles par `HfFileSystem`, à la révision figée, sans l'audio), après contrôle du SHA-256 LFS de chaque Parquet contre le manifeste. 8 tests synthétiques ajoutés ; suite : 122 tests réussis (1 test lent exclu).
- Références, UEM (9 modifiées) et manifeste regénérés ; contrôle croisé refait ; `docs/corpus.md` §2 et `data/README.md` mis à jour.
- EXP-0007 (pyannote community-1, MPS, puis CPU sur `temps.txt`), EXP-0008 (nombre de locuteurs oracle, MPS), EXP-0009 (baseline, balayage de θ sur dev, CPU, `--trace`) : configurations commitées avant exécution, toutes les exécutions sur le commit 568efbb, `arbre_propre` vrai pour les trois.
Résultats :
- Jetons retirés : dev `+` 2 285, `@` 1 089, `*` 404 ; test `@` 1 091, `*` 598, aucun `+` ; aucune forme composée. Parole : 9,33 h (dev) et 9,91 h (test), soit −2,73 % et −1,11 % ; chevauchement 12,6 % et 15,7 % de la parole (14,5 % et 17,2 % avant). Aucun locuteur perdu.
- Contrôle croisé avec `ggfox00000/dia-summre-test` : DER sans collar de 0,32 % à 9,82 % (102a_EBRH), médiane 1,90 %. Le dérivé garde les jetons : le DER entre nos références avant et après retrait reproduit ce contrôle à 0,49 point près.
- EXP-0007 : DER sans collar 26,00 % (dev) et 26,30 % (test) ; collar 0,25 s 10,76 % et 14,82 % ; JER 29,28 % et 28,73 % ; nombre de locuteurs exact 91,7 % et 83,8 % ; RTF MPS 0,051, RTF CPU 0,783 sur `temps.txt`.
- EXP-0008 : DER sans collar 26,50 % (dev) et 25,58 % (test) ; écart à EXP-0007 +0,49 [+0,00 ; +1,18] en dev (0 fichier amélioré, 3 dégradés) et −0,72 [−3,22 ; +0,89] en test (3 améliorés, 3 dégradés), bootstrap apparié, 1 000 tirages, graine 0.
- EXP-0009 : θ retenu 1,00 (0,95 sur AMI, EXP-0002) ; DER sans collar 46,54 % (dev) et 49,36 % (test) ; RTF CPU 0,0009.
Décisions : aucune.
Problèmes :
- Machine sur batterie au début de la session : les exécutions ont attendu le secteur (démarrage à 12:58). Le Mac a été débranché de 15:14 à 16:25 : environ la moitié d'EXP-0008 (essentiellement le test, RTF MPS 0,057 contre 0,052 en dev) a tourné sur batterie, contrairement au protocole §3.5. Les métriques de diarisation n'en dépendent pas ; EXP-0008 n'a pas de mesure CPU (diagnostic). EXP-0009 a attendu le secteur.
- Le balayage d'EXP-0009 a pris 786 s (préparation comprise), hors RTF.
Suite : interprétation au cockpit (`notes.md` d'EXP-0007 à EXP-0009, analyse des échecs §7, sous-ensemble Zoom).

## 2026-10-29 — Interprétation d'EXP-0007 à EXP-0009, SUMM-RE (cockpit)

Objectif : interpréter les premiers résultats en français.
Réalisé : notes.md d'EXP-0007 à EXP-0009 ; README mis à jour.
Résultats : pyannote atteint 26 % de DER sans collar sur SUMM-RE et 14,8 % avec collar (test). La fausse alarme domine (11 à 14 points), et les trois quarts disparaissent avec le collar : il s'agit probablement d'un effet de la convention de référence (fusion à 200 ms). Le nombre de locuteurs oracle ne fait rien gagner en moyenne (EXP-0008), comme sur AMI. La baseline atteint 49 % sur le test (θ = 1,00). Les réunions Zoom sont les plus faciles pour pyannote (17 %).
Décisions : aucune ; trois propositions soumises à la candidate (analyse de sensibilité de la référence, capture de l'alimentation dans les exécutions, suite de D9).
Problèmes : EXP-0008 en partie sur batterie ; son RTF n'est pas exploité.
Suite : analyse de sensibilité de la référence ; empreintes neuronales (D8) ; écoute de 080b_EBDH et 008a_EARH.

## 2026-10-31 — D21 : alimentation, variantes de référence, A-0001 (Claude Code)

Objectif : appliquer D21 (contrôle de l'alimentation, analyses a posteriori) et exécuter A-0001.
Réalisé :
- Commit `docs:` de D21, de methode §2 et §4.7, du README, du journal et des notes d'EXP-0007 à EXP-0009.
- `src/whospoke/power.py` et `scripts/run_experiment.py` : relevés de `pmset -g batt` au début, toutes les 60 s (fil d'arrière-plan) et à la fin, bloc `alimentation` de `execution_<device>.json`. `scripts/evaluate.py` : champ `conforme` dans `temps` et dans `temps_cpu` (true, false, null ; null sans relevés). Protocole §3.5 (révision 1.3) et methode §4.2-§4.3 mis à jour. Résultats existants non modifiés. 5 tests (secteur, batterie, illisible, relevés périodiques, champ des résultats).
- `scripts/data/get_summre.py --variante ECART_MS JETONS` : variantes de la référence à partir des mots relus à distance, dans `data/processed/summre/rttm_variantes/` (non versionné), UEM officiel réutilisé. 6 tests synthétiques. Les 8 variantes ont été générées ; `ecart200ms_jetons-retires` est identique octet pour octet à la référence officielle sur les 73 réunions (contrôle du script et `cmp`). Aucune variante ne change le nombre de locuteurs d'une réunion.
- `scripts/analyses/a0001_sensibilite_reference.py` et `analyses/A-0001_sensibilite-reference/` (configuration commitée avant exécution, commit 8586831, arbre propre). 8 tests de la répartition sur des cas construits à la main ; suite : 140 tests réussis. Durée de l'analyse : 16 min 44 s.
Résultats : A-0001 (`resultats.csv`, `repartition_erreurs.csv`). La variante officielle reproduit exactement les métriques d'EXP-0007 et d'EXP-0009.
- EXP-0007, DER sans collar de 200 ms à 1 000 ms, jetons retirés : dev 26,00 → 18,35 % (fausse alarme 14,24 → 5,10), test 26,30 → 21,13 % (11,28 → 5,03). Avec collar : dev 10,76 → 11,36 %, test 14,82 → 14,72 %.
- EXP-0009, mêmes variantes : dev 46,54 → 49,00 %, test 49,36 → 51,43 % (parole manquée en hausse).
- Répartition, référence officielle : fausse alarme de pyannote en pauses intra-locuteur ≤ 1 s 43,7 % (dev) et 34,2 % (test), pauses inter-locuteurs ≤ 1 s 16,0 % et 18,9 %, ailleurs 40,3 % et 46,8 % (dont environ 1 200 s pendant la parole de référence). Baseline : 31,2 / 21,0 / 47,8 % (dev), 19,7 / 24,1 / 56,3 % (test). Parole manquée sur des tours de moins de 0,5 s : 9,8 % et 7,6 % (pyannote), 7,2 % et 5,9 % (baseline).
Décisions : aucune.
Problèmes : la parole manquée en chevauchement partiel (0 < K̂ < K) n'est pas attribuable à un tour précis ; elle est répartie à parts égales entre les tours actifs (convention consignée dans config.yaml et l'en-tête du script). La catégorie (c) est détaillée en silences longs, bords et fausse alarme pendant la parole, en plus des trois catégories de D21.
Suite : observations et interprétation d'A-0001 au cockpit (`notes.md`) ; la règle d'interprétation de D21 §2 s'applique.

## 2026-10-31 — Interprétation d'A-0001 (cockpit)

Objectif : trancher l'hypothèse sur la fausse alarme de pyannote sur SUMM-RE.
Réalisé : notes.md d'A-0001 ; limite ajoutée à corpus.md §2 ; README mis à jour.
Résultats : pyannote recouvre 84 % des pauses de 1 s au plus d'un même locuteur. Les pauses courtes expliquent un peu plus de la moitié de sa fausse alarme, le faux chevauchement environ un quart (1 200 s par partition). Le DER sans collar varie de 5 à 8 points selon la règle de fusion, le DER avec collar de moins de 0,6 point. Le classement des systèmes est inchangé. Les partitions dev et test ont probablement des conventions de pause différentes.
Décisions : convention de référence inchangée (200 ms), conformément à D21 §2 ; écarts de la session acceptés (conforme dans temps_cpu, détail de la catégorie (c), répartition à parts égales de la parole manquée en chevauchement partiel).
Problèmes : aucun.
Suite : empreintes neuronales (D8, fiche D22).

## 2026-11-01 — Veille sur les modèles récents et file d'attente des moteurs (cockpit)

Objectif : consigner la veille sur Nemotron 3.5 Transcribe, Voxtral Mini Transcribe 3 et Nemotron 3 Diarization, et organiser leur test.
Réalisé : `docs/recherche/veille-2026-11-01-modeles-recents.md` ; fiche D23 (actée) ; planning en version 1.1 (file d'attente, coupes révisées).
Résultats : la diarisation de Nemotron 3.5 est exploitable sans sa transcription (champ `diarization`), mais le modèle entier doit tourner sur un GPU de 80 Go. Voxtral Mini Transcribe 3 a des poids fermés (API). Nemotron 3 Diarization (100 M de paramètres, 8 locuteurs, poids ouverts) est le seul des trois utilisable en local.
Décisions : D23 — tous les moteurs sont testés, l'un après l'autre, selon une file d'attente ; les moteurs cloud ou sur GPU loué sont des comparaisons, jamais le moteur de démonstration ; le corpus maison n'est jamais envoyé hors de la machine.
Problèmes : les publications sur X ne sont pas lisibles automatiquement ; les informations sur Voxtral viennent d'une source secondaire, à confirmer.
Suite : interprétation d'EXP-0013 à EXP-0015 ; prompt du rang 1 (NeMo Sortformer v2). Rangs 6 et 7 en attente d'une décision de la candidate (clé d'API et coût ; location d'un GPU).

## 2026-11-01 — D17 : onglet « Analyse » de l'application, branche `interface` (Claude Code)

Objectif : premier prototype de l'onglet « Analyse » (D17), développé sur la branche `interface` avec un moteur factice, sans inférence réelle pendant le lot d'expériences en cours sur `main`.
Réalisé :
- `uv add gradio` : Gradio 6.31.0 (figé par uv.lock) ; dépendances transitives dont fastapi, uvicorn, pydantic, httpx.
- `app/sortie.py` (statistiques par locuteur, renommage, exports RTTM et JSON, enveloppe de la forme d'onde, DER décomposé face à une référence déposée, deux collars) ; `app/temps.py` (RTF mesuré lu dans le leaderboard, temps restant) ; `app/moteurs.py` (quatre moteurs repris d'une expérience source : EXP-0009, EXP-0012, EXP-0013, EXP-0007 ; moteur factice au contrat de base.py) ; `app/app.py` (onglet « Analyse ») ; `app/static/` (wavesurfer.js 7.12.12 embarqué, visualiseur) ; `app/README.md`.
- 32 tests (`tests/test_app_*.py`) ; racine du dépôt ajoutée au `pythonpath` de pytest.
- Parcours complet en mode factice sur un extrait de 3 min de SUMM-RE 007a_ECRH converti en mp3 stéréo 44,1 kHz (hors dépôt) : normalisation, progression, timeline, écoute au clic, renommage, exports, DER face à la référence (RTTM d'EXP-0007 : 12,81 % sans collar sur l'extrait).
- Contrôle hors ligne (app/README.md) : toutes les requêtes du navigateur vont vers 127.0.0.1, polices comprises ; côté serveur, aucune connexion hors 127.0.0.1.
Résultats : aucune expérience.
Décisions : aucune ; points soumis à la candidate dans le compte rendu (expériences sources des moteurs, fourchette pour la baseline, RTF retenu, noms dans le RTTM exporté).
Problèmes : la suite complète de tests n'a pas été lancée, car `test_embeddings_baseline.py` et `test_catalogue.py` exécutent ECAPA et WeSpeaker ; suite lancée sans ces deux fichiers ni `test_pipeline_pyannote.py` (162 réussis, 1 ignoré). Baseline WeSpeaker indisponible tant qu'EXP-0013 n'est pas exécutée (θ inconnu, aucun RTTM). Chargement des modèles réels et mode réel non testés.
Suite : après le lot, suite de tests complète et essai en mode réel (dont `HF_HUB_OFFLINE=1`) ; fusion de `interface` dans `main` ; page Pipeline.

## 2026-11-01 — Refonte visuelle de l'onglet « Analyse », branche `interface` (Claude Code)

Objectif : rendre l'interface propre, professionnelle et moderne, en s'inspirant des skills d'interface proposés par la candidate.
Réalisé :
- Lecture en ligne de frontend-design, better-interface, beautiful-shadows, emil-design-eng, apple-design, interaction-design, accessibility, unslop et stageshow, sans les installer (`npx skills add` non lancé). Stageshow (maquettes produit en React) est hors sujet ici.
- `app/theme.py` : thème Gradio monochrome, cinq teintes neutres nommées en clair et en sombre, polices système ; `app/static/interface.css` : cartes à ombres en couches, tableaux, panneau d'avancement, focus visible, retour d'appui, `prefers-reduced-motion`, affichage étroit.
- `app/app.py` : en-tête, une carte par section (réglages, avancement, timeline, locuteurs, évaluation, temps, exports), tableaux HTML à la place des tableaux Markdown et du tableau de statistiques, noms saisis échappés, états vides explicites, renommage et exports masqués avant résultat, indicateurs de chargement de Gradio masqués, messages d'erreur qui disent quoi faire.
- Visualiseur : pistes sur fond doux, zones de clic de 24 px, libellés accessibles, graduations adaptées à la largeur ; zones colorées de la forme d'onde dessinées une seule fois (elles l'étaient deux fois).
- Vérifié en mode factice, en clair, en sombre et à 375 px de large. Contrôle hors ligne refait (app/README.md) : 88 requêtes vers 127.0.0.1, une icône en `data:`, aucune police chargée ; côté serveur, aucune connexion hors 127.0.0.1.
Résultats : aucune expérience.
Décisions : aucune.
Problèmes : suite de tests toujours lancée sans les trois fichiers qui chargent des modèles (163 réussis, 1 ignoré). Les couleurs de la forme d'onde suivent le thème actif à la création du lecteur, pas un changement de thème ultérieur.
Suite : inchangée (suite complète et mode réel après le lot, fusion, page Pipeline).

## 2026-11-01 — Prototype de l'onglet Analyse : arbitrages (cockpit)

Objectif : trancher les points ouverts du rapport de la session interface.
Réalisé : amendement 1 de D17 (proposé).
Résultats : onglet Analyse fonctionnel avec le moteur factice ; contrôle réseau limité à 127.0.0.1 ; 162 tests réussis hors tests qui chargent des modèles.
Décisions : voir l'amendement 1 de D17, en attente de validation par la candidate.
Problèmes : vrais moteurs non essayés ; accès éventuel à Hugging Face au chargement des modèles.
Suite : fusion après le lot WeSpeaker, suite de tests complète, essai avec les vrais moteurs, puis rang 1 de D23.

## 2026-11-01 — Amendement 1 de D17 sur la branche `interface` (Claude Code)

Objectif : appliquer l'amendement 1 de D17 (lu dans `~/Dev/Who-Spoke`, statut « proposée » dans la fiche) sans fusionner et sans charger de modèle neuronal pendant le lot EXP-0013 à EXP-0015.
Réalisé :
- `app/moteurs.py` : WeSpeaker reprend EXP-0015 (indisponible tant qu'elle n'existe pas dans la branche) ; message explicite quand un modèle manque du cache local (`LocalEntryNotFoundError` ou `OfflineModeIsEnabled` dans la chaîne des causes). `app/temps.py` : RTF lu dans la colonne du périphérique choisi (`rtf_cpu` en CPU, `rtf` sur le périphérique de l'expérience, repli sur `rtf` pour une expérience exécutée en CPU sans `rtf_cpu`), plus grande valeur entre dev et test.
- `app/travail.py` (nouveau) : au lancement par `python -m app.app`, hors mode factice, `HF_HUB_OFFLINE=1` avant tout import de huggingface_hub, pyannote ou speechbrain ; dossier `run-<pid>` par lancement, `GRADIO_TEMP_DIR` compris, supprimé à la fermeture (atexit, Ctrl+C, SIGTERM) ; dossiers des lancements tués supprimés au lancement suivant.
- DER : mention « Durée entière du fichier, sans UEM : non comparable aux résultats sur corpus. » au-dessus du tableau des deux conditions de collar.
- Zoom de la timeline : zoom natif de wavesurfer (rendu paresseux, contrairement à un élargissement du conteneur qui aurait dessiné plus de 200 Mo de canevas pour 30 min), pistes, axe et tête de lecture synchronisés sur son défilement ; curseur, boutons, Ctrl + molette ; zoom et position conservés au renommage ; commandes par délégation d'événements, le gabarit étant redessiné par Gradio.
- 12 tests nouveaux ou modifiés, sans modèle : source WeSpeaker, règle du RTF, message de cache, variable posée avant l'import du Hub (sous-processus, `--help`), suppression des dossiers, lancements interrompus, mention du DER, présence du zoom. Suite sans les trois fichiers qui chargent des modèles : 174 réussis, 1 ignoré.
- Vérifié dans le navigateur (mode factice) : zoom ×5,8 avec défilement synchronisé (canevas des pistes 3 327 px, forme d'onde 3 328 px), suivi de la lecture, renommage avec zoom conservé, « Tout afficher ». Dossier de lancement supprimé après SIGTERM et après Ctrl+C (code 0). Mode réel : démarrage et requête de la page sans connexion hors 127.0.0.1, sans analyse.
- Nettoyage des dossiers `analyse-*` laissés par les essais précédents dans le dossier temporaire.
Résultats : aucune expérience.
Décisions : aucune ; amendement 1 de D17 appliqué tel que rédigé.
Problèmes : SIGINT est ignoré par un processus lancé en arrière-plan depuis un shell non interactif (artefact de test, pas de l'application) ; vérifié dans les conditions d'un terminal. Le message de cache manquant n'a pas pu être vérifié sur un vrai chargement.
Suite : après le lot, suite de tests complète et essai réel des quatre moteurs (liste dans `app/README.md`, « Reste à vérifier avec les vrais moteurs ») ; `configs/demo.yaml` au gel.

## 2026-11-01 — Pages supplémentaires de l'interface (cockpit)

Objectif : planifier les pages Pipeline et Avancement, et les fonctionnalités retenues par la candidate.
Réalisé : fiche D26 (actée) ; maquette de la page Pipeline versionnée dans `docs/maquettes/`.
Décisions : D26 — onglets Pipeline, Avancement et Glossaire ; carte des erreurs et comparaison de deux moteurs dans l'onglet Analyse ; en-tête YAML dans chaque `notes.md` ; ni enregistrement au micro, ni modification de réglage depuis l'interface. Les numéros D24 et D25 restent réservés à la robustesse et au faux chevauchement (D23).
Suite : chantiers I1 à I5 dans la branche `interface`, puis vérification V après le lot WeSpeaker ; en-têtes des `notes.md` existants à l'interprétation du lot.

## 2026-11-01 — Amendement 1 de D17, lignes ajoutées : préchargement, ECAPA, palette (Claude Code)

Objectif : appliquer les deux lignes ajoutées à l'amendement 1 de D17 (préchargement des modèles, emplacement des fichiers d'ECAPA) et vérifier la palette des locuteurs, sur la branche `interface`, sans charger de modèle pendant le lot EXP-0014/0015.
Réalisé :
- Vérification que WeSpeaker est inclus dans community-1 : dans le cache, `models--pyannote--speaker-diarization-community-1/snapshots/3533c8c…/` contient `embedding/pytorch_model.bin`, et son `config.yaml` y renvoie (`embedding: $model/embedding`) ; `refs/main` pointe sur la même révision que celle figée pour la baseline WeSpeaker. Lecture de fichiers seulement, aucun modèle chargé.
- `scripts/prefetch_models.py` : télécharge community-1 (`main` et révision figée de WeSpeaker) et ECAPA (révision figée) avec `HF_TOKEN` lu dans `.env` (jamais affiché), puis vérifie les trois chargements dans un processus enfant avec `HF_HUB_OFFLINE=1` et un dossier courant vide, en contrôlant que rien n'y est écrit. 8 tests sans réseau (téléchargements et chargements simulés, dont un processus enfant réel). Non exécuté pour de vrai. Le message « modèle absent du cache » et `app/README.md` renvoient au script.
- `src/whospoke/embeddings.py`, chargement d'ECAPA seulement : `ecapa_load_options()` impose `savedir=None` et `LocalStrategy.NO_LINK`, donc une lecture en place dans le cache Hugging Face (`HF_HUB_CACHE`, `$HF_HOME/hub`). C'était déjà le comportement de speechbrain 1.1.2 sans `savedir` (aucun `pretrained_models/` dans `~/Dev/Who-Spoke`) ; il est rendu explicite, indépendant du dossier courant et de la version. Mêmes fichiers lus, calculs inchangés. 3 tests sans modèle.
- Palette des locuteurs : validateur de la skill dataviz (OKLab ΔE × 100, simulation de Machado 2009) sur le fond des pistes, plus une planche visuelle simulée. Paires adjacentes : réussi en clair (CVD 9,1 ; normal 19,6) et en sombre (8,4 ; 19,3). Toutes paires, deutéranopie : pire 4,5 en clair (1↔7), 1,6 en sombre (3↔5) ; vision normale : 7,1 (2↔8) dans les deux modes. La couleur seule ne sépare toutes les paires que jusqu'à 3 locuteurs ; au-delà, l'identité repose sur la piste nommée, le tableau et le survol, sauf pour les teintes de la forme d'onde. Au-delà de 8 locuteurs, un gris unique. Consigné dans `app/README.md`.
- Suite de tests sans les trois fichiers qui chargent des modèles : 185 réussis, 1 ignoré.
Résultats : aucune expérience.
Décisions : aucune. Proposition : ne pas compter sur les teintes de la forme d'onde pour identifier un locuteur (les retirer, ou y ajouter le nom au survol).
Problèmes : aucun.
Suite : après le lot, `uv run python scripts/prefetch_models.py`, puis la liste « Reste à vérifier avec les vrais moteurs » de `app/README.md`.

## 2026-11-01 — Retour du chantier I0 (cockpit)

Objectif : interpréter le rapport sur le préchargement, ECAPA et la palette.
Réalisé : amendement de D18 (révisions des modèles) ; paragraphe « Couleurs » dans D26.
Résultats : préchargement et lecture d'ECAPA dans le cache faits et testés sans réseau. La palette ne distingue par la seule couleur que 3 locuteurs en deutéranopie. Le moteur pyannote charge community-1 sans révision figée, et la révision n'est pas consignée dans les expériences.
Décisions : forme d'onde neutre (D26) ; tout modèle figé à un commit et consigné dans `configuration_effective` (D18, amendement du 01/11).
Suite : figer pyannote au chantier V, après le lot ; neutralisation de la forme d'onde en début d'I1.

## 2026-11-01 — D26 : forme d'onde neutre et onglet Pipeline (chantier I1), branche `interface` (Claude Code)

Objectif : appliquer le paragraphe « Couleurs » de D26, puis le chantier I1 (onglet Pipeline), sur la branche `interface`, sans fusion ni modèle chargé. D26, D17 et son amendement 1 lus dans `~/Dev/Who-Spoke`, en lecture seule.
Réalisé :
- Couleurs (D26) : forme d'onde neutre ; le segment cliqué y est marqué par une bande d'encre et entouré sur sa piste (`aria-pressed`). Vérifié dans le navigateur : aucune bande avant sélection, une seule après. Test : un seul `addRegion`, sans couleur de locuteur.
- `app/pipeline.py` et `app/static/pipeline.js` : onglet Pipeline en lecture seule, généré depuis `configuration_effective` de l'exécution principale de l'expérience source (EXP-0009, EXP-0012, EXP-0015, EXP-0007) et depuis `catalogue.yaml` ; sélecteur de moteur, enchaînement des étapes, fiche par étape (rôle, modèle et révision, erreurs produites, fichier de définition, tableau réglage, valeur, origine, effet, composantes du DER), étape Évaluation séparée (collars et `skip_overlap` lus sur les métriques instanciées, références lues dans config.yaml), étape Normalisation commune (fréquence lue dans `whospoke.audio`). Contenu repris de la maquette du 27/10, sans son style ni ses polices distantes.
- Révisions : lues dans la valeur `dépôt@commit` d'un réglage `*.modele` ou dans un réglage `*.revision`, sinon « révision non consignée ». Constat : ECAPA affiche `0f99f2d` ; les trois modèles de pyannote (segmentation, empreintes, PLDA) sont « révision non consignée ».
- Écarts entre configuration et catalogue, sur le dépôt principal : aucun pour EXP-0007 et EXP-0012 ; pour EXP-0009 (MFCC), cinq entrées du catalogue absentes de la configuration (`empreintes.dimension`, `empreintes.duree_min_s`, `empreintes.modele`, `empreintes.peripherique`, `normalisation`), propres aux variantes neuronales. Aucun réglage hors catalogue, aucune étape différente. WeSpeaker : page indisponible, EXP-0015 n'étant pas exécutée.
- Option `--depot` de l'application : expériences, `results/leaderboard.csv` et catalogue lus sous une autre racine, pour l'onglet Pipeline comme pour l'onglet Analyse (moteurs disponibles, θ, RTF, RTTM du moteur factice). Lancement de développement : `--factice --depot ~/Dev/Who-Spoke`. Aucune écriture dans le dépôt principal (vérifié par `git status` et par un test d'instantané).
- 11 tests sans modèle (10 pour l'onglet Pipeline, dont trois sur les expériences réelles de la branche ; 1 pour la forme d'onde neutre). Suite sans les trois fichiers qui chargent des modèles : 196 réussis, 1 ignoré.
- Contrôle hors ligne : 86 requêtes du navigateur, toutes vers 127.0.0.1 ; côté serveur, aucune connexion hors 127.0.0.1.
Résultats : aucune expérience.
Décisions : aucune. Points soumis : les textes et trois valeurs de l'étape Normalisation (canaux, format, entrée en mémoire) sont dans `app/pipeline.py`, faute de constantes exposées par `whospoke.audio` et d'entrée au catalogue ; les déplacer dans le catalogue au gel ?
Problèmes : pendant la vérification, le zoom de la timeline s'est trouvé au maximum après une interaction dans la page ; l'alignement des pistes est resté exact (10 800 px des deux côtés).
Suite : I2 (onglet Avancement), après les en-têtes YAML des `notes.md`.

## 2026-11-01 — D26 : onglet Avancement (chantier I2), branche `interface` (Claude Code)

Objectif : chantier I2 de D26, onglet Avancement généré depuis le dépôt, mêmes règles qu'I1 (branche `interface`, racine de dépôt configurable en lecture seule, aucun modèle).
Réalisé :
- `app/avancement.py` : frise des expériences et analyses (ordre chronologique ; question, verdict et décisions lus dans l'en-tête YAML de `notes.md`, D26 §2 ; corpus et DER des `results_*.json`, partition test puis dev, collar 0 puis 0,25 s ; résultats invalidés marqués) ; décomposition de l'erreur par les oracles (EXP-0002 à EXP-0006, EXP-0010, EXP-0011 : DER test, parole manquée, fausse alarme, confusion, écart avec la référence) ; décisions (D1 à D15 depuis le tableau et la phrase « Statut » de `cadrage.md`, points ouverts compris ; D16 et suivantes depuis la ligne `Statut :` des fiches et de leurs amendements) ; file d'attente de D23 depuis `planning.md`, complétée d'un état constaté (expériences citées créées ou avec résultats, fiches citées présentes ou absentes).
- Onglet dans `app/app.py`, régénéré à chaque ouverture ; un bouton « notes.md » par ligne affiche les notes, sans leur en-tête, dans la page.
- En-têtes absents (« en-tête manquant »), mal formés (« en-tête illisible »), `id` incohérent ou verdict hors liste : affichés sans erreur. 9 tests sur un dépôt fabriqué dans un dossier temporaire (en-têtes complets, absents, cassés, incohérents ; décisions ; file ; lecture seule). Suite sans les trois fichiers qui chargent des modèles : 205 réussis, 1 ignoré.
- Vérifié dans le navigateur avec `--depot ~/Dev/Who-Spoke` : 15 expériences, 1 analyse, 24 décisions ; les 16 `notes.md` sont « en-tête manquant » ; file : rang 0 « 2/3 avec résultats, 3/3 créées », rangs 4 et 5 « fiche D24 absente », « fiche D25 absente ». Toutes les requêtes du navigateur vers 127.0.0.1 ; aucune connexion serveur hors 127.0.0.1.
Résultats : aucune expérience.
Décisions : aucune.
Problèmes : les amendements sans ligne `Statut :` propre (D18 du 28/10, D19, D20, D22) s'affichent « statut non indiqué ». `docs/planning.md` n'est pas encore versionné dans le dépôt principal : l'onglet le lit tel qu'il est sur disque.
Suite : en-têtes des `notes.md` par le cockpit ; chantier I3 (glossaire intégré).

## 2026-11-01 — D26 : glossaire intégré (chantier I3), branche `interface` (Claude Code)

Objectif : chantier I3 de D26 (onglet Glossaire, renvois des termes depuis les autres onglets), mêmes règles qu'I1 et I2.
Réalisé :
- `app/glossaire.py` : lecture de `docs/glossaire.md` (termes `###`, champs, parties `##`, introduction ; une ligne `---` clôt la partie en cours) ; onglet Glossaire avec index, une ancre par terme et renvois entre définitions (jamais vers soi-même).
- Renvois automatiques dans les onglets Analyse (titres, avancement, tableaux des locuteurs, des temps et du DER), Pipeline et Avancement : première occurrence par bloc (paragraphe, cellule, élément de liste, titre) ; jamais dans du code, un bouton, un lien ni un attribut. Variantes tirées des titres du glossaire (terme français, termes anglais en italique, éléments entre parenthèses contenant une majuscule ; un qualificatif comme « (système) » écarté). Mot entier seulement, y compris face aux identifiants et expressions (`der_c0`, `clustering.threshold`, `VBxClustering`, `collar=0.5`) ; pluriel accepté ; variante la plus longue d'abord ; sigles sensibles à la casse. `app/static/glossaire.js` : un clic ouvre l'onglet Glossaire sur la définition, mise en évidence.
- 12 tests sur un glossaire fabriqué (lecture, variantes, sous-chaînes, casse, pluriels, priorité au plus long, blocs, zones exclues, HTML préservé, ancres) et sur le glossaire du dépôt. Suite sans les trois fichiers qui chargent des modèles : 217 réussis, 1 ignoré.
- Vérifié dans le navigateur avec `--depot ~/Dev/Who-Spoke` : 23 termes ; 22 renvois dans l'onglet Analyse après une analyse avec référence, 33 dans Pipeline, 40 dans Avancement, aucun dans du code ou un bouton ; saut vers « Fausse alarme » depuis le tableau du DER. Corrigé pendant la vérification : marge intérieure que Gradio impose aux liens. Toutes les requêtes vers 127.0.0.1.
Résultats : aucune expérience.
Décisions : aucune.
Problèmes : les formes abrégées ne sont pas reconnues (« Confusion » seul, en-tête du tableau du DER, ne renvoie pas à « Confusion de locuteur » ; « Détection de parole » pas à « Détection d'activité vocale ») ; les libellés des composants Gradio et la timeline n'ont pas de renvois.
Suite : chantier I4 (carte des erreurs).

## 2026-11-01 — D26 : carte des erreurs (chantier I4), branche `interface` (Claude Code)

Objectif : chantier I4 de D26, piste des erreurs sous la timeline quand une référence est déposée, mêmes règles (moteur factice, aucun modèle).
Réalisé :
- Examen de pyannote.metrics : `IdentificationErrorAnalysis.difference` donne le statut de chaque segment (correct, confusion, parole manquée, fausse alarme) mais compare les étiquettes telles quelles ; l'appariement vient de `DiarizationErrorRate.optimal_mapping` (hongrois). `sortie.error_map` reprend les étapes de `DiarizationErrorRate.compute_components` dans le même ordre (UEM, étiquettes renommées, appariement), puis `difference` sur l'hypothèse appariée ; durées cumulées segment par segment comme le DER. Aucun appariement recodé.
- Égalité stricte (`==`) des trois durées et de la parole de référence avec les composantes du DER sans collar : cas construit avec chevauchement, hypothèse parfaite, 25 paires d'annotations aléatoires ; parts affichées égales aux cellules du tableau du DER. Sur l'extrait de 3 min (EXP-0007 face à la référence SUMM-RE) : 5,557 s de parole manquée, 10,163 s de fausse alarme, 3,779 s de confusion, égales au bit près.
- Visualiseur : trois rangées nommées (encre pleine, hachures, contour) dans le canevas des pistes, donc soumises au zoom ; zones écoutables au clic et repérées sur la forme d'onde ; infobulle avec locuteur de référence et locuteur attribué ; ligne de totaux. Carte calculée à l'analyse ou au dépôt ultérieur de la référence. Corrigé pendant la vérification : la zone d'erreur sélectionnée n'était pas repérée sur la forme d'onde.
- Vérifié dans le navigateur : 123 zones (36 manquées, 70 fausses alarmes, 17 confusions) ; parts 3,65 %, 6,67 %, 2,48 % identiques au tableau ; zoom × 5,8 avec pistes et erreurs alignées sur la forme d'onde (3 327 et 3 328 px). Toutes les requêtes vers 127.0.0.1.
- Suite sans les trois fichiers qui chargent des modèles : 221 réussis, 1 ignoré.
Résultats : aucune expérience.
Décisions : aucune.
Problèmes : la carte est sans collar seulement ; les identifiants de référence de SUMM-RE sont des numéros (« 023 »), affichés tels quels.
Suite : chantier I5 (comparaison de deux moteurs).

## 2026-11-01 — D26 : comparaison de deux moteurs (chantier I5), branche `interface` (Claude Code)

Objectif : chantier I5 de D26, option « comparer avec un second moteur » de l'onglet Analyse, mêmes règles (moteur factice, aucun modèle).
Réalisé :
- `temps.cumulative_remaining_s` : temps restant de moteurs exécutés l'un après l'autre (reste du moteur en cours, estimation complète des suivants, inconnu si un RTF manque). 1 test.
- `app/app.py` : analyse en une ou deux passes sur le même fichier normalisé, avancement commun (étapes préfixées par le moteur) ; nombre de locuteurs et périphérique communs, fourchette refusée si l'un des moteurs ne la prend pas en charge. Résultat principal (statistiques, renommage) et second résultat ; référence et cartes des erreurs des deux moteurs calculées à l'analyse ou au dépôt ultérieur de la référence. Carte « Comparaison » : locuteurs, DER dans les deux conditions de collar, temps de calcul, RTF. Temps de traitement et DER par moteur. Exports des deux résultats, suffixés par moteur.
- Visualiseur : groupes superposés dans le même canevas (premier moteur en couleurs ; second moteur et référence en gris neutre ; cartes des erreurs des deux moteurs), alignés et zoomés ensemble, avec une légende par groupe ; clés de sélection propres à chaque groupe. La référence est aussi affichée en analyse simple.
- 5 tests de la comparaison sur des résultats fabriqués (groupes, couleurs, cartes égales aux composantes du DER de chaque moteur, tableau, exports, avancement, temps et DER par moteur). Suite sans les trois fichiers qui chargent des modèles : 227 réussis, 1 ignoré.
- Vérifié dans le navigateur (pyannote community-1 puis baseline ECAPA, extrait de 3 min, avec référence) : temps restant « pour les deux moteurs » pendant le premier ; 23 libellés et 23 pistes alignés ; tableau 12,81 % / 4,62 % (pyannote) et 16,71 % / 8,38 % (ECAPA) ; zoom × 5,8 commun ; segment du second moteur sélectionné et repéré sur la forme d'onde ; 4 fichiers d'export. Mode simple inchangé. Corrigé pendant la vérification : légendes de groupe tronquées. Toutes les requêtes vers 127.0.0.1.
Résultats : aucune expérience.
Décisions : aucune ; choix soumis au cockpit : second moteur et référence en gris neutre, référence affichée aussi en analyse simple, statistiques et renommage limités au premier moteur.
Problèmes : aucun.
Suite : vérification V (fusion dans `main`, suite complète, préchargement réel, essai avec les vrais moteurs).

## 2026-11-01 — Bilan de la branche interface, chantiers I1 à I5 (cockpit)

Objectif : trancher les points ouverts du récapitulatif de la branche `interface`.
Réalisé : en-têtes YAML ajoutés aux 16 `notes.md` (15 expériences, A-0001) ; méthode §4.2 mise à jour ; lignes « Statut » ajoutées aux amendements de D18, D19, D20 et D22 ; « Formes courtes » ajoutées à 7 entrées du glossaire ; amendement de D26.
Décisions : voir l'amendement du 01/11 de D26.
Suite : petit chantier I6 dans `interface` (formes courtes, mention « sans collar ») ; chantier V à la fin d'EXP-0015.

## 2026-11-01 — D26, amendement du 01/11 : chantier I6, branche `interface` (Claude Code)

Objectif : appliquer l'amendement du 01/11 de D26 (lu dans `~/Dev/Who-Spoke`, en lecture seule), sans fusion ni modèle.
Réalisé :
- Glossaire : ligne facultative « Formes courtes : a, b, c. » lue sous le titre d'une entrée (point final facultatif), non affichée comme champ mais sous le titre ; chaque forme renvoie à l'entrée avec les mêmes règles (mot entier, pluriel, plus long d'abord) ; une forme revendiquée par deux entrées renvoie à la première et est signalée (`Linker.conflicts`). Glossaire du dépôt principal : 7 entrées portent des formes courtes, aucun conflit ; « Confusion » (en-tête du tableau du DER) renvoie désormais à « Confusion de locuteur », « Détection de parole » à « Détection d'activité vocale ».
- Carte des erreurs : légende « Erreurs sans collar » (« Erreurs sans collar, <moteur> » en comparaison) et ligne des totaux qui le répète.
- Onglet Avancement contrôlé sur le dépôt principal avec les vrais en-têtes et statuts : 16 en-têtes lus sans problème (id, verdict, décisions), 0 « en-tête manquant » ou « illisible », 0 « statut non indiqué » (7 amendements, tous « actée »), 0 verdict inconnu. Restent affichés, à juste titre : « fiche D24 absente » et « fiche D25 absente » (file D23, rangs 4 et 5), DER « — » pour EXP-0015 (non exécutée). Corrigé : accord du résumé (« 1 analyse »).
- 8 tests (formes courtes, conflits, mention sans collar, résumé, dépôt principal). Suite sans les trois fichiers qui chargent des modèles : 233 réussis, 1 ignoré. Toutes les requêtes du navigateur vers 127.0.0.1.
Résultats : aucune expérience.
Décisions : aucune.
Problèmes : deux tests lisent le dépôt principal voisin (`../Who-Spoke`) s'il existe et sont ignorés sinon.
Suite : vérification V ; déplacement de l'étape Normalisation dans `catalogue.yaml` au chantier V (amendement du 01/11 de D26).

## 2026-11-01 — Empreintes neuronales dans la baseline, EXP-0010 à EXP-0015 (Claude Code, session commencée le 31/10)

Objectif : appliquer D22 (représentation `ecapa` et `wespeaker` dans la baseline) et exécuter EXP-0010 à EXP-0015.
Réalisé : vérifications de corpus.md §9 (ECAPA : VoxCeleb 1 et 2, Apache-2.0, dimension 192, 16 kHz ; empreintes de community-1 : données d'entraînement non documentées, architecture WeSpeakerResNet34 de dimension 256 lue dans le checkpoint) ; `uv add speechbrain` (1.1.2, versions de torch, torchaudio, numpy et pyannote inchangées, test lent d'EXP-0001 réussi) ; `src/whospoke/embeddings.py` (modèles figés à un commit, lots de 8 sans complément, longueur minimale mesurée au chargement : 640 échantillons pour ECAPA, 1 680 pour WeSpeaker) ; baseline à représentation configurable, describe() et catalogue mis à jour ; fenêtres trop courtes consignées dans run.log et `execution_cpu.json` ; tests sur signaux synthétiques (149 réussis) ; RTTM d'EXP-0002, EXP-0006 et EXP-0009 reproduits à l'octet près sur deux fichiers chacune avec la représentation MFCC.
Résultats : EXP-0010 à EXP-0015, en CPU. θ retenu : 1,00 (EXP-0010), 1,00 (EXP-0012), 0,95 (EXP-0013), 1,00 (EXP-0015), aucun au bord de la plage ; 0,95 imposé pour EXP-0011 et EXP-0014. DER sans collar sur test : AMI réaliste 64,4 (MFCC), 45,9 (ECAPA), 49,2 (WeSpeaker), 19,9 (pyannote) ; AMI oracles 48,9, 25,4, 27,6 ; SUMM-RE réaliste 49,4, 33,4, 35,9, 26,3. Écarts à la référence MFCC sur test (IC à 95 %, bootstrap) : EXP-0010 −18,5 [−23,7 ; −13,8], 15/16 fichiers améliorés ; EXP-0011 −23,5 [−28,8 ; −18,6], 16/16 ; EXP-0012 −16,0 [−19,5 ; −12,5], 36/37 ; EXP-0013 −15,2 [−20,1 ; −10,5], 14/16 ; EXP-0014 −21,3 [−25,9 ; −16,9], 15/16 ; EXP-0015 −13,5 [−17,7 ; −9,8], 32/37. Aucune fenêtre trop courte.
Décisions : amendement de D22 (normalisation par fichier, calcul en CPU), rédigé par le cockpit après signalement.
Problèmes : NaN intermittents des deux modèles en MPS (torch 2.14.1), d'où le CPU ; en CPU, ECAPA est 30 fois plus lent par fenêtre en lots de 16 qu'en lots de 8. Passage sur batterie pendant EXP-0012 (10 relevés sur 52) : temps non conforme, métriques non affectées ; le lot s'est arrêté avant EXP-0013, relancé le 01/11 sur secteur.
Suite : interprétation d'EXP-0010 à EXP-0015 au cockpit (`notes.md`, en-têtes YAML d'EXP-0015 à compléter).

## 2026-11-01 — Interprétation des empreintes neuronales, EXP-0010 à EXP-0015 (cockpit)

Objectif : interpréter les six expériences de D22.
Réalisé : observations et interprétation dans les six `notes.md`, verdicts des en-têtes YAML, README mis à jour.
Résultats : ECAPA et WeSpeaker réduisent fortement la confusion de la baseline (AMI test 27,1 → 8,6 et 11,9 points ; SUMM-RE test 24,4 → 8,5 et 10,9), avec des écarts significatifs à MFCC dans toutes les conditions. La parole manquée par la détection d'énergie devient l'erreur principale (70 % sur AMI, deux tiers sur SUMM-RE). WeSpeaker n'est jamais meilleur qu'ECAPA ; l'écart n'est pas significatif sous oracles. À empreinte identique, pyannote devance la baseline de 29,3 points sur AMI (72 % dus à la détection) et de 9,6 points sur SUMM-RE.
Décisions : verdicts — EXP-0010 et 0012 retenues (ECAPA, représentation de la baseline), EXP-0013 et 0015 écartées, EXP-0011 et 0014 informatives. Aucune nouvelle fiche.
Problèmes : temps d'EXP-0012 non conforme (batterie), non exploité.
Suite : chantier V (fusion de l'interface, révision figée de pyannote), puis rang 1 de D23 (NeMo Sortformer v2).

## 2026-11-01 — Chantier V de D26 : fusion de l'interface, révision figée, essai avec les vrais moteurs (Claude Code)

Objectif : chantier V de D26 après la fin du lot WeSpeaker, sans expérience en cours.
Réalisé :
- Commit `docs:` des documents du cockpit restés non commités (interprétation d'EXP-0010 à EXP-0015, en-têtes, journal) ; le reste avait déjà été commité par la session des expériences. `README.md` (état d'avancement, modifié par le cockpit) laissé non commité : hors de la liste demandée.
- Révisions (D18, amendement du 01/11) : un seul instantané de community-1 dans le cache, `3533c8cf8e369892e6b79ff1bf80f7b0286a54ee` (`refs/main` y pointe, créé le 27/10) ; ECAPA : `0f99f2d…`, seul instantané. pyannote figé à `3533c8c` (`MODEL_REVISION`, transmis par pyannote à la segmentation, aux empreintes et à la PLDA) ; `configuration_effective` consigne désormais `…@commit` pour chaque modèle des trois moteurs neuronaux ; `prefetch_models.py` ne télécharge plus `main`. Test lent de reproduction d'EXP-0001 réussi avant et après (RTTM identique à l'octet près). 3 tests.
- Fusion de `interface` dans `main` ; conflit sur `docs/journal.md` résolu en gardant les 33 entrées : ordre interne de chaque côté préservé, entrées du cockpit placées après le rapport auquel elles répondent (place de la « Veille » non déterminable, mise en tête du 01/11). `uv sync` ; `uv run pytest` complet : 255 réussis, puis 258.
- Étape Normalisation de la page Pipeline : valeurs lues dans `whospoke.audio` (constantes `CHANNELS`, `CODEC`, `SAMPLE_DTYPE` désormais utilisées par `normalize` et `load_waveform`, comportement inchangé ; `describe_normalisation()`), textes dans la section `communs` du catalogue ; plus rien d'écrit à la main dans `app/pipeline.py` pour cette étape. 3 tests.
- `scripts/prefetch_models.py` exécuté : réussi (téléchargement aux révisions figées, chargement hors ligne des trois modèles depuis un dossier vide).
- Essai réel sous relevé réseau (détail dans `app/README.md`) : télémétrie de pyannote.audio vers `otel.pyannote.ai` découverte à la première séance et coupée (`PYANNOTE_METRICS_ENABLED=false`) ; ensuite aucune connexion hors `127.0.0.1`. Temps restant : sous-estimé de 20 à 30 % sur 3 min (préchauffage et coût fixe exclus du RTF des expériences), de 16 % sur 27 min (pyannote : 82 s annoncées, 95 s réelles). Fourchette 4–6 de pyannote : 4 locuteurs au lieu de 3. Nombre imposé 4 de la baseline MFCC : 4 au lieu de 2. Modèle absent du cache (ECAPA, puis community-1, retirés temporairement puis restaurés) : message attendu dans les deux cas. Zoom maximal sur 26 min 48 s avec référence : 96 465 px, 3 181 segments, 66 ms pour zoomer, défilement à 11,4 ms par image en médiane (95e centile 16,7 ms), tas JavaScript stable vers 28 Mo.
Résultats : aucune expérience.
Décisions : aucune.
Problèmes : la télémétrie de pyannote.audio est active par défaut et n'est pas coupée par `scripts/run_experiment.py` : les exécutions de pyannote (et des empreintes WeSpeaker, chargées par pyannote.audio) ont probablement envoyé ces métadonnées **[probable]**, non vérifiable après coup. Après une erreur, le panneau d'avancement reste sur l'étape en cours.
Suite : décider de couper la télémétrie aussi dans les expériences ; rang 1 de D23 (NeMo Sortformer v2).

## 2026-11-01 — Retour du chantier V et télémétrie (cockpit)

Objectif : interpréter le rapport du chantier V.
Réalisé : fiche D27 (télémétrie) ; note D27 dans les `notes.md` des sept expériences qui ont chargé pyannote ; révision de community-1 consignée dans les notes d'EXP-0001 (vérifiée) et d'EXP-0007 (déduite).
Résultats : interface fusionnée et fonctionnelle avec les vrais moteurs ; pyannote figé à 3533c8c, EXP-0001 reproduite à l'octet ; télémétrie de pyannote découverte par le relevé réseau ; temps restant sous-estimé de 16 à 30 %.
Décisions : D27 — télémétrie coupée au niveau du paquet, contrôle réseau avant le corpus maison et à chaque nouveau moteur ; temps restant = surcoût fixe mesuré par moteur + RTF × durée.
Suite : correctifs (D27, temps restant, panneau après erreur), puis rang 1 de D23 (NeMo Sortformer v2).

## 2026-11-01 — Audit du projet (cockpit)

Objectif : recenser ce qui peut améliorer le projet, à toutes ses couches, à la demande de la candidate.
Réalisé : `docs/audit/audit-2026-11-01.md`. Méthode : lecture du dépôt (commit b747bd6), interface lancée en mode factice dans un environnement Linux en CPU avec captures des quatre onglets, trois recherches web (méthodes de diarisation, UI/UX et skills, annonces de juin à novembre 2026), fiches de community-1, Nemotron 3 Diarization et DiariZen revérifiées.
Résultats : sortie exclusive de pyannote disponible et non mesurée ; Nemotron 3 Diarization entraîné sur AMI train/dev et VoxConverse dev/test ; DiariZen annoncé à 13,9 % sur AMI-SDM (poids CC BY-NC, installation documentée en CUDA) ; dépôt public sans licence ; défauts d'interface relevés sur les captures.
Décisions : aucune. Le réordonnancement de D23 (R-M1) et le choix de la licence (R-R1) attendent la candidate.
Suite : transformer les recommandations retenues en chantiers.

## 2026-11-01 — D27, temps restant avec surcoût fixe, panneau après erreur (Claude Code)

Objectif : correctifs demandés par le cockpit après le chantier V : D27, estimation du temps restant, état du panneau d'avancement après une erreur.
Réalisé :
- Commits `docs:` des documents du cockpit : D27, notes D27 des sept expériences, journal et README (`b3f7d57`), README mis à jour pendant la session (`9cb3de9`), audit du 01/11 (`c8de216`).
- D27 (`d60280a`) : `whospoke.telemetry`, appelé par `whospoke/__init__.py` avant tout import tiers, impose `PYANNOTE_METRICS_ENABLED=false`, `HF_HUB_DISABLE_TELEMETRY=1`, `GRADIO_ANALYTICS_ENABLED=False` et `OTEL_SDK_DISABLED=true`. Inventaire des paquets installés : en plus des trois variables de la fiche, la télémétrie native de FastAPI (sous Gradio, OpenTelemetry, exportée seulement si un point d'arrivée OTLP est configuré), coupée par `OTEL_SDK_DISABLED` ; rien dans speechbrain, torch, torchaudio, lightning, optuna ni librosa. Tout point d'entrée importe `whospoke` avant tout autre module tiers (`app/__init__.py` l'importe). `tests/test_telemetry.py` (18 tests) : environnement hostile, effet réel sur huggingface_hub, pyannote.audio, Gradio et le SDK OpenTelemetry, ordre des imports de chaque script ; contre-épreuve sans `import whospoke` : télémétrie active. Liste dans `docs/methode.md` §7.1.
- Exécution de contrôle D27, non référencée (hors `experiments/`, sans évaluation ni leaderboard) : configuration d'EXP-0007 restreinte à deux réunions de dev (`summre__017a_EBRZ`, `summre__043a_EDRH`, 28 min 56 s), `scripts/run_experiment.py` sur le commit `d60280a` (arbre propre), MPS, sur secteur, sous hook d'audit Python (`socket.connect`, `getaddrinfo`, `sendto`, `bind`, `http.client`, `urllib.Request`) et relevé `lsof` toutes les 0,5 s. **Aucune connexion** : un seul événement, `socket.bind` sur `::1` port 0 (test de disponibilité d'IPv6 d'urllib3 à l'import, local) ; `lsof` vide. RTTM identiques à l'octet à ceux d'EXP-0007.
- Panneau après erreur (`7a7b1b1`) : toute erreur après le début de l'analyse marque l'étape en cause « échec » (celle en cours, à défaut la première non commencée), le titre la nomme, le message est dans le panneau (`role="alert"`) ; la notification est conservée. Vérifié dans le navigateur en mode factice (échec au calcul et à la normalisation). 1 test.
- Temps restant (`b0c7d52`, `b747bd6`) : estimation = surcoût fixe + RTF × durée ; `FIXED_OVERHEAD` daté par (moteur, périphérique) à côté de `SPECS` dans `app/moteurs.py` ; le panneau cite le RTF et le surcoût avec sa date. `scripts/measure_overhead.py` : mesure (3 processus neufs, premier appel après chargement sur 60 s de `summre__004c_PAPH`, dev) et vérification. 3 tests.
- `uv run pytest` complet : 279 réussis (1 lent exclu).
Résultats : surcoûts fixes mesurés le 01/11 : MFCC 1,5 s, ECAPA 1,3 s, WeSpeaker 1,6 s (CPU) ; pyannote 1,1 s (MPS), 6,6 s (CPU, 2,7 à 9,8 s). Écart annoncé/réel, premier appel après chargement : extrait de 3 min, pyannote MPS −22 % → −13 %, ECAPA −38 % → −11 %, WeSpeaker −56 % → −36 %, MFCC −93 % → −24 %, pyannote CPU −10 % → −6 % ; réunion de 26 min 48 s, pyannote MPS −19 % → −18 % (83 s annoncées, 102 s réelles), ECAPA −5 %, WeSpeaker −10 %, MFCC −18 %. Détail dans `app/README.md`.
Décisions : aucune.
Problèmes : l'annonce reste trop courte dans tous les cas. Sur la réunion, l'écart de pyannote vient du RTF (0,0632 obtenu contre 0,0512 dans EXP-0007), pas d'un coût fixe ; l'exécution de contrôle donne aussi 0,059 avec le même code et les mêmes versions. Machine chargée pendant toutes les mesures (charge moyenne 2,7 à 9,3 : application Claude, indexation de macOS), sans contrôle possible. Le surcoût est compté à chaque analyse, même moteur déjà chaud : l'annonce est alors plus longue d'environ le surcoût. Le README du cockpit indique encore « fusion et essai avec les vrais moteurs à faire » pour l'interface.
Suite : décider comment absorber l'écart proportionnel (remesure du RTF, marge), puis rang 1 de D23.

## 2026-11-01 — Feuille de route après l'audit (cockpit)

Objectif : organiser la mise en œuvre de toutes les recommandations de l'audit, retenues par la candidate.
Réalisé : planning en version 2.0 (cinq pistes, file A1 à A9, chantiers B1 à B6 et E1 et E2, calendrier jusqu'au 16/11) ; fiches D24 (robustesse) et D25 (fausse alarme de pyannote) ; amendement du 01/11 de D23 (file réordonnée).
Décisions : D24, D25, amendement de D23 ; licence MIT par défaut (audit R-R1), modifiable par la candidate ; pas de conversation orchestratrice supplémentaire, mais des prompts en lot et la lecture directe du dépôt par le cockpit.
Suite : lancer A1 (piste A), B1 (worktree `ui`) et E1 (worktree `outils`).

## 2026-11-01 — Retour des correctifs D27 et du temps restant (cockpit)

Objectif : trancher les points ouverts du rapport.
Réalisé : amendement 2 de D17.
Résultats : télémétrie coupée au niveau du paquet (4 variables, dont OTEL_SDK_DISABLED), contrôle réseau sans connexion sortante ; temps restant encore sous-estimé, car le RTF varie avec la charge de la machine.
Décisions : annonce en fourchette, recalage sur la vitesse observée, surcoût fixe seulement si le moteur est froid (amendement 2 de D17, appliqué au chantier B2). Le README était déjà à jour : la remarque du rapport date d'avant sa mise à jour.

## 2026-11-01 — Retour du chantier B1-B2 et charge de la machine (cockpit)

Objectif : trancher les choix de la session interface ; traiter l'effet du travail en parallèle sur les temps.
Réalisé : amendement du 01/11 de D21 (charge de la machine, campagne de temps dédiée).
Décisions :
- case « Réafficher un résultat déjà calculé » décochée par défaut, et badge visible quand un résultat vient du cache ;
- clé du cache fondée sur la configuration effective et les révisions des modèles, plutôt que sur le commit (un commit de documents ne doit pas l'invalider) ;
- autres choix validés : préchauffage de tous les moteurs disponibles, seuils du recalage, option `--sans-prechauffage`, modification du test du dépôt principal ;
- temps des expériences menées pendant le travail en parallèle non comparables ; temps de référence mesurés par une campagne dédiée après le gel.

## 2026-11-01 — Retour des chantiers E1 et E2 (cockpit)

Objectif : trancher les quatre points de la session outils.
Réalisé : amendement du 01/11 de `docs/corpus-maison/conventions-annotation.md`.
Décisions : code du locuteur dans le texte des labels ; label `exclusion` pour les annonces, retiré de l'UEM ; ré-annotation de contrôle sans pré-annotation ; références dans `data/processed/maison/`, versionnées seulement avec l'accord de tous les participants (option 3 du consentement, règle déjà prévue par le README du corpus maison). L'intégration continue (torch en CPU sans toucher à uv.lock) et la commande `whospoke diarize` sont validées.
Suite : correctifs d'E2 et chantier E3 (script de la campagne de temps, rapport d'évaluation par fichier du corpus maison).

## 2026-11-01 — Retour du chantier B3 (cockpit)

Objectif : valider les choix de la session interface.
Décisions :
- choix validés : un déplacement manuel coupe le suivi de la lecture ; ← revient au début du tour en cours s'il a commencé depuis plus de 0,3 s ; isoler un locuteur estompe les autres pistes sans changer ce qui est lu ;
- clé du cache complétée par une empreinte du code des moteurs (`src/whospoke/` et `app/moteurs.py`), pour qu'un changement de code qui modifie les résultats invalide le cache sans qu'un commit de documents le fasse.
Suite : chantier B4.

## 2026-11-01 — Retour des correctifs d'E2 et du chantier E3 (cockpit)

Objectif : trancher les trois points de la session outils.
Décisions :
- sous-ensemble de la campagne de temps : celui du protocole §3.5 (`data/splits/<corpus>/temps.txt`), et non un tirage par graine. La demande du cockpit contredisait le protocole ; l'option de tirage est retirée pour qu'il n'existe qu'une seule définition ;
- seuil de charge au démarrage : réglage du script, fixé le jour de la campagne à partir d'une mesure de la charge au repos (5 min, toutes applications fermées, `--mesurer-repos`), consignée dans la sortie de la campagne ;
- le document de synthèse publie, pour chaque enregistrement du corpus maison : son code (M01…), sa condition, le nombre de locuteurs de la référence et de l'hypothèse, sa durée arrondie à la minute et les métriques dans les deux conditions de collar. Ni horaires de parole, ni contenu, ni nom. Les sorties détaillées restent dans `data/processed/maison/rapport/` ;
- garde-fous ajoutés par la session validés (sorties non versionnées, contrôle réseau obligatoire avant une exécution réelle).
Suite : fusion d'`outils` dans `main` au prochain arrêt de la piste A, avant l'application du relevé de charge de D21 (module `whospoke.charge`) ; chantier E4 (préparation de Nemotron 3 Diarization et de DiariZen).

## 2026-11-01 — Retour du chantier B4 ; constats et synthèse (cockpit)

Objectif : valider les choix de B4 ; créer les sources du chantier B5.
Réalisé : `docs/constats.yaml` (10 constats rattachés aux étapes du catalogue, avec sources et confiance) ; `docs/synthese.md` (synthèse vivante, R-M3).
Décisions : choix de B4 validés (frontière de tour à 0,25 s, contiguïté à 0,05 s, pauses entre deux passages de parole seulement, couleurs de la référence calées sur le premier moteur en comparaison).
Suite : chantier B5.

## 2026-11-01 — Retours des chantiers B5 et E4 ; premier regard sur EXP-0016 (cockpit)

Objectif : valider les choix des sessions interface et outils ; préparer la fusion.
Décisions :
- B5 : repérage automatique des systèmes de référence et ordre SUMM-RE puis AMI validés. Le graphique reprend pour chaque type d'erreur le motif de la carte des erreurs (parole manquée pleine, fausse alarme hachurée, confusion en contour), pour qu'un même type d'erreur ait la même apparence partout ; le vert est foncé jusqu'à passer le contrôle de contraste en mode clair. Section `regroupements` du catalogue acceptée (invalidation du cache comprise).
- E4 : voie transformers pour Nemotron 3 et fork de DiariZen validés ; NeMo-Speech.cpp gardé en repli. L'enregistrement des deux moteurs dans `run_experiment.py` revient à la piste A, après la fusion.
- Premier regard sur EXP-0016, avant le rapport de la piste A : la sortie exclusive dégrade SUMM-RE test (DER sans collar 26,30 → 30,40 % ; fausse alarme −3,0, parole manquée +8,4, confusion −1,3). Le chevauchement réel perdu pèse plus que le faux chevauchement retiré. Si le bootstrap le confirme, V1 de D25 est écartée, et la bascule exclusive de l'interface (R-U12) est abandonnée.
Suite : fusion d'`outils` et d'`ui` dans `main` à l'arrêt de la piste A (avant A3) ; chantiers B6 et E5.

## 2026-11-02 — Retours des chantiers E5 et B6 (cockpit)

Objectif : trancher les questions des sessions outils et interface.
Décisions :
- Réglage de V2 sur dev : le point retenu minimise le DER sans collar sur SUMM-RE dev, parmi les points dont le DER avec collar sur dev ne dépasse pas celui d'EXP-0007 (10,76 %). C'est une contrainte, et pas seulement une alerte, en cohérence avec la règle 2 de D25. Si le minimum tombe au bord de la grille, la grille est élargie une fois.
- V2 et V3 en une seule exécution : admis. Une exécution de l'enveloppe à deux sorties donne deux expériences distinctes, V2 (sortie habituelle + Silero) et V3 (sortie exclusive + Silero). Chacune a son dossier, son config.yaml et son entrée au leaderboard, et leurs config.yaml mentionnent l'exécution partagée. Le temps de calcul n'est rapporté qu'une fois.
- B6 : définitions des indicateurs validées (tour sans comblement, passage de parole au sens du *floor transfer offset* de Heldner et Edlund 2010, tours inclus non comptés, latence signée et médiane) ; fusion absorbant le locuteur de la ligne, avec annulation de la dernière seulement ; codes Audacity dans l'ordre de première prise de parole ; une image par analyse.
Suite : chantiers B7 (cas limites de l'interface) et E6 (vérification d'une installation vierge).

## 2026-11-01 — Outils : licence, commande en ligne, intégration continue, chaîne du corpus maison (Claude Code)

Objectif : chantiers E1 et E2 du planning v2.0 (audit du 01/11, §7), dans le worktree `~/Dev/Who-Spoke-outils` (branche `outils`, créée depuis `main` à `2d458af`), sans charger de modèle, sans fusion ni nouvelle dépendance.
Réalisé :
- E1, licence (`6059d69`) : `LICENSE` MIT au nom de l'auteur de `pyproject.toml` (Pollos-ECE) ; `docs/licences.md` : community-1 CC-BY-4.0 et ECAPA Apache-2.0, vérifiées sur le Hub aux révisions figées (`3533c8c`, `0f99f2d`) ; wavesurfer 7.12.12 BSD-3-Clause (fichier joint) ; dépendances principales (métadonnées des paquets installés) ; corpus ; DiariZen CC BY-NC d'après l'audit, à revérifier avant intégration. Lien depuis le README ; `license = "MIT"` dans `pyproject.toml`.
- E1, commande en ligne (`9f6af41`) : `whospoke diarize <audio> --moteur … --locuteurs auto|N|MIN-MAX --peripherique … --sortie rttm|json [-o fichier]`, déclarée dans `[project.scripts]`. Elle reprend `app/moteurs.py` (expériences sources, θ, CPU imposé aux baselines) et `app/sortie.py` (exports identiques à l'interface). Hors ligne : `HF_HUB_OFFLINE=1` posée avant tout import du Hub, télémétrie coupée (D27) ; ajoutée aux points d'entrée contrôlés par `tests/test_telemetry.py`. Elle s'utilise depuis un clone : le paquet `app` n'est pas installé, la commande ajoute la racine du dépôt au chemin. 17 tests (baseline MFCC sur signal de synthèse). Essai manuel hors du dépôt : RTTM correct, erreur claire pour une fourchette demandée à une baseline.
- E1, intégration continue (`8d6b70f`) : `.github/workflows/tests.yml`, Ubuntu, uv 0.11.28, ffmpeg. Choix : sous Linux, `uv.lock` résout torch depuis PyPI en version CUDA (environ 3 Go de paquets nvidia-* et triton). Ajouter l'index CPU de PyTorch dans `pyproject.toml` réécrirait le verrou pour toutes les plateformes et créerait un conflit avec la piste A. La CI exporte donc les versions exactes du verrou, retire nvidia-* et triton, puis installe avec `uv pip install --torch-backend cpu` (torch 2.14.1+cpu, torchaudio et torchcodec +cpu, mêmes versions). `uv.lock` est inchangé, sa résolution macOS aussi ; `uv lock --check` vérifie qu'il est à jour. Suite rapide : `-m "not lent and not modele"`, `HF_HUB_OFFLINE=1`, aucun secret. Nouveau marqueur `modele` sur les deux tests qui chargent ECAPA (`test_ecapa`, `test_catalogue_baseline`). Résolution Linux contrôlée au préalable avec `uv pip compile --python-platform x86_64-manylinux_2_28`.
- E2 (`be3ef20`) : paquet `whospoke.maison` et point d'entrée `scripts/data/maison.py` (`etat`, `synchroniser`, `preannoter`, `convertir`, `tirer-controle`, `accord`), session par session dans `data/raw/maison/<Mxx>/`, sans réseau ni modèle. Synchronisation : claquements de la table (attaque la plus franche en passe-haut 1 kHz, première et dernière minute, imposables à la main), gabarit de 0,6 s retrouvé dans chaque piste d'aide par corrélation croisée normalisée ; décalage, dérive (ppm), corrélations et alertes dans `synchro.json` ; pistes recalées sur la table pour l'écoute dans Audacity ; option `--deja-alignees` pour les pistes séparées de visio. Pré-annotation : énergie par trame de 10 ms ramenée au plancher de bruit de chaque piste (10e percentile), lissage de 0,1 s ; parole si la piste la plus forte dépasse de 10 dB son plancher, locuteur = cette piste ; zone « à vérifier » si la deuxième piste est à moins de 3 dB ; fusion à 0,2 s ; export en labels Audacity. Conversion : le texte de chaque label porte le code du locuteur, et `exclusion` retire une zone de l'UEM ; fusion des pauses de 200 ms ou moins (même règle que SUMM-RE, vérifiée par un test croisé avec `get_summre.merge_intervals`) ; UEM du claquement + 1 s au claquement − 1 s, moins les exclusions ; RTTM `maison__Mxx`, locuteurs `Mxx_Sn`. Contrôles bloquants (locuteur sans segment, segment hors UEM : RTTM non écrit) et avertissements de plausibilité ; accord sur 2 min tirées au hasard (graine consignée), DER `collar_0` par `DiarizationEvaluator`, alerte si moins de 24 h entre les deux annotations. 23 tests sur signaux de synthèse (trois voix, claquement commun entendu par des réponses d'appareil différentes, décalages de −1,1 à +3,2 s, dérives de −400 à +250 ppm).
- E2, documentation (`f8b39b7`) : `docs/corpus-maison/guide-annotation.md`, pas-à-pas pour la candidate ; README (commande en ligne, licence, liens), index de `docs/corpus-maison/`.
Résultats : CI GitHub Actions verte au premier passage (run 41339091426 : torch 2.14.1+cpu, 286 tests réussis, 9 sautés, 3 désélectionnés, 1 min 46 s). Localement, suite rapide en conditions de CI (cache Hugging Face vide, hors ligne, sans jeton) : 309 réussis, 1 échec hors périmètre (ci-dessous). Sur signaux de synthèse : claquements retrouvés à moins de 0,01 ms près, dérives exactes, corrélations de 0,81 à 0,91 ; pré-annotation à 2,6 % de DER `collar_0` face à la vérité, uniquement aux frontières. Aucune expérience.
Décisions : aucune. Dépendances ajoutées : aucune ; `uv.lock` inchangé.
Problèmes : `tests/test_app_avancement.py::test_depot_principal_complet_si_present` échoue localement : il lit le dépôt principal voisin, où `experiments/EXP-0016_pyannote-c1-summre-exclusive/` (piste A, en cours) n'a pas encore d'en-tête. Il est sauté en CI. Les deux tests `modele` n'ont pas été lancés (consigne : aucun modèle chargé) : la règle 10 de CLAUDE.md (`uv run pytest` complet) n'est donc vérifiée que sur la suite sans eux, dont le code n'a pas changé. Audacity n'est pas installé sur la machine : ses menus et le comportement de l'export des labels (un fichier pour toutes les pistes, ou une piste à la fois) sont marqués [probable] dans le guide ; la conversion accepte les deux cas. Seuils de synchronisation et de pré-annotation choisis a priori, validés sur synthèse seulement. La branche `outils` contient le commit `2d458af` de `main`, qui n'était pas encore sur `origin/main`.
Suite : points à trancher par le cockpit : (1) emplacement des références pour A9 : `uem_path()` lit `data/splits/maison/uem/` (versionné), alors que `corpus-maison/README.md` place RTTM et UEM dans `data/processed/maison/` ; la chaîne les laisse dans `<Mxx>/reference/` ; reste à décider de l'installation, de `data/splits/maison/test.txt` et du versionnement selon le consentement. (2) Les conventions mettent les annonces « hors UEM », mais la règle « claquement + 1 s » ne les exclut pas : la chaîne demande un label `exclusion`. (3) Ré-annotation de contrôle : le guide autorise l'écoute des pistes d'aide alignées, mais pas la pré-annotation. (4) Le texte du label porte le code du locuteur, au lieu du seul nom de piste prévu par les conventions §3. Première session réelle : contrôler à l'oreille la synchronisation et ajuster au besoin les seuils de pré-annotation (consignés par session). Fusion de la branche `outils` (planning : mardi 3/11, entre deux expériences).

## 2026-11-01 — Outils : correctifs d'E2, campagne de temps (E3a), rapport du corpus maison (E3b) (Claude Code)

Objectif : appliquer l'amendement du 01/11 des conventions d'annotation à la chaîne E2, puis le chantier E3 (D21, amendement du 01/11 ; A9), dans le worktree `outils`, sans modèle chargé, sans fusion ni dépendance.
Réalisé :
- Correctifs d'E2 (`d7f0c35`) : `convertir` écrit le signal de test normalisé, le RTTM et l'UEM dans `data/processed/maison/` (`maison__Mxx.wav`, `rttm/`, `uem/`) et son rapport dans `<Mxx>/conversion.json` ; `uem_path()` lit `data/processed/maison/uem/` pour le corpus maison (inchangé pour les autres). Fichier `<Mxx>/metadonnees.yaml` (session, condition `salle|visio|bruit`, options cochées par code) : champs fermés uniquement, tout autre champ refusé, option 1 exigée ; il donne les participants attendus à la conversion et la condition au rapport. Commande `versionner Mxx` : copie RTTM et UEM dans `data/splits/maison/{rttm,uem}/` seulement si tous les participants ont l'option 3 et figurent dans le fichier ; sinon elle s'arrête en nommant les codes ; rien n'est ajouté à git. Les labels `exclusion` sont retirés de l'UEM et de la référence (déjà le cas, test explicite ajouté). Consigne de la fenêtre de contrôle et guide mis à jour (version 1.1 : métadonnées, emplacements, étape 6 « versionner »). 9 tests de plus (32 au total).
- E3a (`7d4eaf3`) : `scripts/campagne_temps.py` et `whospoke.charge` (charge moyenne par `os.getloadavg()`, équivalent de `sysctl vm.loadavg` ; cœurs de performance par `sysctl hw.perflevel0.physicalcpu`, 6 sur cette machine ; relevés d'alimentation et de charge en fil d'arrière-plan). Sous-ensemble : 3 réunions de SUMM-RE test et 3 d'AMI test, tirées avec la graine 20261112 et consignées (`summre__025b_EBDH`, `summre__045a_EARH`, `summre__072b_EEDH`, `ami__EN2002d`, `ami__ES2004c`, `ami__IS1009c`) ; option `--sous-ensemble temps` pour `temps.txt`. Départ seulement sur secteur et avec une charge sur 1 min ≤ max(1, cœurs de performance / 4), après au plus 10 min d'attente ; relevés toutes les 30 s et au début et à la fin de chaque réunion ; une réunion est conforme si elle est sur secteur et sans charge concurrente (règle 1 de l'amendement). Pour chaque moteur et périphérique : chargement mesuré, préchauffage de 60 s non compté (protocole §3.5), réunions l'une après l'autre ; RTF en rapport des sommes, par corpus, minimum et maximum, temps pour 30 min, surcoût fixe ; valeurs pour l'interface (`FIXED_OVERHEAD`, RTF par moteur et périphérique) ; `campagne.json`, `mesures.csv`, `tableau.md` dans `results/campagne_temps/<date>/`. `--plan` affiche le plan sans rien lancer. 10 tests, avec le moteur factice uniquement ; aucune exécution réelle.
- E3b (`65a5701`) : `scripts/rapport_maison.py`. Chaque référence complète de `data/processed/maison/` est évaluée par tous les moteurs disponibles de l'application : métriques du protocole par fichier dans les deux conditions de collar (DER, composantes, JER, DER par zone), nombre de locuteurs, condition d'enregistrement ; mention « test qualitatif » en tête ; valeurs globales indicatives ; bootstrap seulement à partir de 5 fichiers. Hypothèses en cache par signature (moteur, expérience source, paramètres, périphérique) : une nouvelle référence ne fait tourner que le nouveau fichier. Sorties dans `data/processed/maison/rapport/` (non versionné). `--controle-reseau` est obligatoire (D27 : contrôle réseau avant toute exécution sur le corpus maison) et consigné. 6 tests sur données synthétiques (moteurs simulés à sortie connue, baseline MFCC sur une réunion de synthèse).
Résultats : suite rapide en conditions de CI (cache Hugging Face vide, hors ligne), lancée une fois à la fin : 336 réussis, 9 sautés, 3 désélectionnés, 1 échec hors périmètre (ci-dessous). Aucune expérience.
Décisions : aucune. Dépendances ajoutées : aucune ; `uv.lock` inchangé.
Problèmes : `test_depot_principal_complet_si_present` échoue toujours localement : il lit le dépôt principal, où EXP-0016 à EXP-0019 (piste A, non commitées) n'ont pas encore d'en-tête ; il est sauté en CI. Le protocole §3.5 fixe déjà un sous-ensemble de mesure du temps (`data/splits/<corpus>/temps.txt`, deux fichiers par corpus, « fixé une fois pour toutes »), alors que le prompt et l'amendement de D21 demandent 3 + 3 réunions tirées par graine : le tirage est le défaut, `--sous-ensemble temps` reste disponible. Le seuil de charge de départ (cœurs de performance / 4, soit 1,5) est un choix a priori, sans mesure de la charge au repos de la machine (7,1 pendant cette session, avec la piste A). Le relevé de charge de `run_experiment.py` (règle 1 de l'amendement) n'est pas fait ici : `whospoke.charge` peut le servir. La branche `outils` part de `2d458af`, alors que `main` est à `12a67a6` (enveloppe pyannote à deux sorties) : la campagne et le rapport prendront la sortie choisie par `app/moteurs.py` au moment de la fusion.
Suite : points à trancher par le cockpit : (1) sous-ensemble de la campagne : tirage 3 + 3 ou `temps.txt` (protocole §3.5) ; (2) seuil de charge au départ, à fixer après une mesure de la machine au repos ; (3) ce que le rendu publie du rapport du corpus maison. Fusion de `outils` (planning : mardi 3/11) ; contrôle réseau D27 avant le premier `rapport_maison.py` réel ; campagne le 12/11, après le gel.

## 2026-11-01 — Outils : campagne sur temps.txt, E4 (préparation de Nemotron 3 et de DiariZen) (Claude Code)

Objectif : appliquer les décisions du cockpit sur la campagne de temps, puis préparer Nemotron 3 Diarization (A4) et DiariZen (A5), installation seulement, sans inférence, dans le worktree `outils`, sans fusion ni dépendance.
Réalisé :
- Campagne de temps (`e26d2f0`) : sous-ensemble du protocole §3.5 seulement (`data/splits/<corpus>/temps.txt`, 2 + 2 réunions), option de tirage retirée ; `--mesurer-repos` relève la charge toutes les 5 s pendant 5 min et l'écrit dans `results/campagne_temps/repos_<date>.json` ; `--charge-max` (seuil) et `--repos` sont obligatoires pour une campagne réelle et consignés dans sa sortie. 11 tests.
- E4, Nemotron 3 Diarization (révision `f667ed73aee5`, OpenMDW-1.1, non restreint). Trois voies explorées dans l'ordre demandé, toutes installables sur macOS : transformers (intégration native depuis 5.18, installé en 5.22.1, Python 3.12, torch 2.15.0, import correct en CPU) ; NeMo 3.0.0 (`SortformerEncLabelModel` importé en CPU, environnement d'essai `envs/nemotron-nemo/`) ; NeMo-Speech.cpp 0.3.0 (binaire officiel macOS Metal, SHA-256 contrôlé, `--version` et `diarize --help` répondent ; poids publiés seulement en `q8_0`). Voie retenue : transformers, avec les poids fp32. MPS probable d'après le code (PyTorch pur), non vérifié.
- E4, DiariZen Large s80 v2 (modèle `027b3e221b9d`, CC BY-NC 4.0 ; code `844f5555b0a9`, MIT ; empreintes WeSpeaker `837717ddb9ff`, CC-BY-4.0). Installation CUDA adaptée à macOS : uv, Python 3.10, torch 2.1.1 de PyPI, `onnxruntime` au lieu d'`onnxruntime-gpu`, sans outils de développement, contraintes du dépôt respectées ; import de `DiariZenPipeline` correct en CPU. Le code choisit CUDA, sinon le CPU : MPS seulement en forçant `pipeline.to("mps")`, non vérifié.
- Temps passé, à l'horloge murale, compté dans les essais bornés de D23 : Nemotron 3, 5 min 30 s (borne 2 h) ; DiariZen, 2 min 55 s (borne 4 h) ; plus 7 min 40 s de travail commun (scripts, enveloppes, catalogue, tests), puis la documentation. Le cache de uv explique ces durées. Installations sous `nice -n 19`, la piste A calculant.
- Environnements séparés `envs/<moteur>/` (ignorés par git), recréés par `scripts/envs/nemotron.sh` et `scripts/envs/diarizen.sh` aux versions figées (`scripts/envs/*.txt`), recréation vérifiée de zéro dans un dossier temporaire ; option `--modeles` pour télécharger les poids aux révisions figées, non lancée. `pyproject.toml` et `uv.lock` inchangés.
- Enveloppes au contrat D19 (`63d51da`) : `whospoke.pipelines.externe` (exécutant persistant en sous-processus, lancé une fois à la construction pour que le chargement ne soit pas compté ; une ligne JSON par message ; WAV PCM 16 bits sans perte ; RTTM relu ; erreurs remontées avec la sortie d'erreur), `nemotron3.py` (nombre de locuteurs estimé seulement, 8 au plus ; nombre imposé et parole oracle refusés), `diarizen.py` (estimé, borné ou imposé par `min_speakers` et `max_speakers`) ; `describe()` avec révisions et configuration effective ; entrées du catalogue. Coupure D27 pour l'exécutant : `TELEMETRY_OFF`, `HF_HUB_OFFLINE=1`, wandb désactivé, sans `HF_TOKEN` ni `ONE_LOGGER_EXPORTER_CONFIG_PATH`, dans un dossier temporaire vide. 11 tests avec un exécutant simulé, qui parle le vrai protocole. Les deux exécutants réels démarrent dans leur environnement et s'arrêtent proprement au chargement des poids, absents du cache.
- Documentation (`59b8e75`) : `docs/corpus.md` §9 (données d'entraînement des deux moteurs), `docs/licences.md`, `docs/methode.md` §7.1 et inventaire de `whospoke/telemetry.py`, fiche `docs/recherche/e4-moteurs-externes.md` (voies explorées, versions, risques, marche à suivre pour le premier fichier). `conftest.py` racine : la suite ignore les tests des dépôts clonés dans `envs/`.
Résultats : suite rapide en conditions de CI, à la fin : 348 réussis, 9 sautés, 3 désélectionnés, 1 échec hors périmètre (`test_depot_principal_complet_si_present`, EXP-0016 à EXP-0019 en cours sur `main`). Elle a tourné deux fois : la première s'est arrêtée à la collecte des tests des dépôts clonés dans `envs/`, d'où le `conftest.py`. Aucune expérience, aucune inférence.
Décisions : aucune. Dépendances ajoutées à l'environnement principal : aucune.
Problèmes : premier lancement réel de l'exécutant de DiariZen arrêté parce que le fichier `diarizen.py` masquait le paquet `diarizen` ; corrigé (`executant_*.py`, test de garde). Le motif `envs/` de `.gitignore` ignorait aussi `scripts/envs/` ; ancré en `/envs/`. Risque non vérifiable sans les poids : le fork de pyannote 3.1.1 de DiariZen avec huggingface_hub 2.4.0 et lightning 2.6.6. Les fiches de Nemotron 3 et de DiariZen ne documentent que Linux et les GPU NVIDIA. `scripts/run_experiment.py` ne connaît pas encore les deux moteurs (`PIPELINES`) : laissé à la piste A, le fichier étant modifié sur `main`.
Suite : piste A, premier fichier de chaque moteur selon la fiche E4 §6 (poids par `--modeles`, contrôle réseau D27, inscription dans `PIPELINES`) ; décider de la voie de secours de Nemotron (NeMo-Speech.cpp en Metal, poids `q8_0`) si la vitesse en CPU ou en MPS ne suffit pas ; fusion d'`outils`.

## 2026-11-01 — Outils : E5, détection fine par Silero VAD (D25, V2 et V3) (Claude Code)

Objectif : préparer les variantes V2 et V3 de D25 (masque de parole de Silero VAD appliqué à la sortie de pyannote), sans ajouter Silero à `uv.lock`, sans charger de modèle ni lancer d'inférence, dans le worktree `outils`.
Réalisé :
- `envs/` vérifié ignoré par git (`git check-ignore` : règle `/envs/` de `.gitignore` ; aucun fichier suivi sous `envs/`).
- Silero VAD vérifié (D27, D18), roue PyPI lue sans exécution : silero-vad 6.2.3, licence MIT, poids `silero_vad.jit` inclus dans le paquet (SHA-256 `e1122837f415…`), ni Hub ni jeton ; dépendances `packaging` et torch seulement (l'option `audio` impose torchaudio < 2.10 : à ne pas installer). Aucune télémétrie ni appel réseau en usage (seul `Validator`, jamais appelé, télécharge). Effet de bord trouvé : `import silero_vad` impose `torch.set_num_threads(1)` à tout le processus ; neutralisé.
- `whospoke.pipelines.silero` (`0d475a5`) : probabilités de Silero par fenêtre de 32 ms, binarisation par la fonction de Silero elle-même (`get_speech_timestamps_from_probs`), intersection avec la sortie du moteur (ne crée jamais de parole ni de locuteur ; test aléatoire). Moteur composé `SileroRefinement` (`<moteur>-silero`, même masque appliqué aux `autres_sorties` de l'enveloppe à deux sorties de `main`) et fabrique `pyannote_silero` pour `PIPELINES`. Réglages au catalogue sous `pyannote-community-1-silero` (entrées de pyannote reprises par ancre YAML) : `silero.seuil`, `silero.silence_min_s` (silence rouvert minimal, marge déduite), `silero.marge_s`, plus le modèle, la durée minimale de parole et le périphérique.
- `scripts/reglage_silero.py` : grille 3 × 3 × 3 sur SUMM-RE dev à partir des RTTM d'EXP-0007 (V2) et d'EXP-0016 (V3, réglage de V2 repris), sans relancer pyannote ; probabilités de Silero en cache (`data/processed/summre/silero/6.2.3-e1122837f415/`) ; arrêt si les RTTM sources ne redonnent pas leurs DER consignés. Contrôle fait sur les vraies données, en lecture seule : EXP-0007 dev 26,00 / 10,76 % et EXP-0016 dev 29,18 / 12,97 % reproduits ; 11 s par point de grille.
- 15 tests (`tests/test_silero.py`), dont 2 qui ne s'activent qu'avec silero-vad installé (vraie binarisation ; vrai modèle, marqueur `modele`).
- Documentation (`5f588fa`) : `docs/recherche/e5-silero.md` (vérifications, conception, pas-à-pas pour la piste A), `docs/licences.md`, `docs/corpus.md` §9, `docs/methode.md` §7.1, inventaire de `whospoke/telemetry.py`.
Résultats : suite complète une fois, à la fin : 364 réussis, 11 sautés, 1 désélectionné, 1 échec hors périmètre (`test_depot_principal_complet_si_present`, comme au lot précédent). Aucune expérience, aucune inférence.
Décisions : aucune. Proposition au cockpit : point retenu sur dev = DER sans collar minimal, avec alerte si le DER avec collar se dégrade (D25 ne fixe que les conditions sur test).
Problèmes : l'exécution, dans l'environnement principal, de la fonction de binarisation tirée de la roue téléchargée a été refusée (code externe pas encore admis comme dépendance). Le sens des réglages est vérifié par lecture du code 6.2.3 et par un masque simulé ; le test sur la vraie fonction le confirmera après le `uv add`. Première CI en échec sur un test (faux paquet Silero réécrit sur place, relu depuis son bytecode sous Linux) ; corrigé par un dossier par version.
Suite : piste A, à la fusion : `uv add silero-vad==6.2.3`, tests, `--probabilites` sous relevé réseau, réglage, inscription de `pyannote_silero` dans `PIPELINES`, expériences V2 et V3 (fiche E5 §4). Au cockpit : dire si une seule exécution à deux sorties peut porter V2 et V3.

## 2026-11-02 — Outils : décisions du cockpit sur E5, E6 (vérification d'une installation) (Claude Code)

Objectif : appliquer les deux décisions du cockpit du 02/11 sur E5 ; préparer le test d'installation sur machine vierge du 12/11 (R-R4), sans charger de modèle ni fusionner.
Réalisé :
- E5, règle de choix (`73e95d1`) : `scripts/reglage_silero.py` retient le DER sans collar minimal sur SUMM-RE dev parmi les points dont le DER avec collar, comparé au centième, ne dépasse pas celui de la source V2 (EXP-0007 : 10,76 %, lu dans ses résultats). Sans point admissible, rien n'est retenu et V3 n'est pas évaluée. Point au bord de la grille : l'axe est prolongé d'un pas symétrique du pas voisin (seuil borné à [0,05 ; 0,95], durées positives ou nulles), une seule fois ; un point encore au bord est signalé. 3 tests ajoutés ou modifiés (contrainte, absence de point admissible, élargissement).
- E5, exécution partagée (`b97d58f`) : fiche E5 §4 mise à jour (une exécution, deux expériences V2 et V3, temps rapporté une fois). `scripts/evaluate.py` exige `execution_<périphérique>.json` dans chaque dossier d'expérience : l'adaptation revient à la piste A sur `main`, rien n'est codé ici.
- E6 (`2f37e4b`) : `scripts/verifier_installation.sh`. Dans un dossier temporaire : clone depuis GitHub, `uv sync --locked`, `check_env.py`, suite rapide, préchargement (`--verifier` si les modèles sont en cache ; sinon arrêt avec la marche à suivre pour le jeton et les conditions de community-1, ou téléchargement avec `--env` et `--telecharger`), application démarrée (`--sans-prechauffage` si la version clonée l'a) jusqu'à la première réponse HTTP puis arrêtée par SIGTERM, `whospoke diarize --help` ; en option, `scripts/envs/*.sh` (`--moteurs-externes`) et cache de uv vierge (`--cache-uv-vierge`). Étapes chronométrées ; rapport, `etapes.tsv` et journaux dans `results/installation/<date>_<heure>/`, dossier personnel remplacé par `~`.
- Exécution avec `--sans-modeles` sur la branche `outils` (commit `d253503`), sous `nice -n 19` : vérification partielle réussie en 3 min 03 s (clone 1 s, `uv sync` 1 s avec le cache de uv de la machine, `check_env` 7 s, suite rapide 2 min 36 s avec 363 réussis, application prête en 7 s et arrêtée proprement en 1 s, CLI 1 s) ; `.venv` de 1,3 Go. Le script a tourné deux fois : la première exécution, réussie elle aussi, a montré des commentaires peu parlants dans le rapport et l'absence de la taille de l'environnement. Après correction, seul le second rapport est gardé (`results/installation/2026-11-02_00h56/`).
- `docs/installation.md` (`e0a5073`) : prérequis (macOS, outils d'Apple, uv, ffmpeg, compte Hugging Face et conditions de community-1, espace disque), étapes, vérification automatique, durées mesurées, problèmes connus (Homebrew et ffmpeg sur macOS 14, dossier `envs/`, accès restreint, `--sans-prechauffage` pas encore fusionnée, test lié au dépôt de développement, port) ; lien depuis le README.
Résultats : suite complète une fois, à la fin : 366 réussis, 11 sautés, 1 désélectionné, 1 échec hors périmètre (`test_depot_principal_complet_si_present`). Aucune expérience, aucune inférence, aucun modèle chargé.
Décisions : aucune.
Problèmes : `--sans-prechauffage` n'existe que sur la branche `ui` ; avant la fusion, le script lance l'application sans cette option et le note. Non mesurés : `uv sync` avec un cache vierge, préchargement réel (pas de jeton dans le clone). Ces mesures sont prévues le 12/11. Le rapport précédent donnait à tort `2ee1e07` comme dernier commit poussé ; c'était `d253503`.
Suite : le 12/11, sur machine vierge et après fusion : `bash scripts/verifier_installation.sh --cache-uv-vierge --env <.env> --telecharger --moteurs-externes`, puis reporter les durées dans `docs/installation.md` §4.

## 2026-11-01 — Interface : finitions (B1) et démonstration (B2), amendement 2 de D17 (Claude Code)

Objectif : chantiers B1 (C2) et B2 (C5) du planning v2.0, et amendement 2 de D17, dans le worktree `~/Dev/Who-Spoke-ui` (branche `ui`, créée depuis `main` en `2d458af`), moteur factice seulement, sans modèle chargé, sans fusion ni dépendance ajoutée.
Réalisé :
- B1, finitions R-U5 : zones de dépôt en français quelle que soit la langue du navigateur (`gr.I18n` sur les clés `upload_text.drop_file`, `upload_text.click_to_upload`, `common.or`, pour les 27 langues de Gradio 6.3) ; pied de page de Gradio masqué (`footer_links=[]`) ; zone de la référence à 150 px, plus rognée ; rangées d'intitulé de la timeline opaques au-dessus de la tête de lecture ; dernière graduation alignée à droite près du bord (« 5:00 » entier) ; étapes de l'avancement lues en colonne (`columns`).
- B1, R-U1 : après une analyse réussie, colonne des réglages masquée et bandeau pleine largeur (fichier, durée, moteurs, nombre de locuteurs, périphérique) avec « Nouvelle analyse », qui rouvre les réglages ; timeline et résultats en pleine largeur.
- B1, onglet Avancement : tableau « File d'attente de la piste A » (Rang, Contenu, Calcul estimé, Prérequis) ; « État constaté » réduit aux fiches citées présentes ou absentes.
- B2, R-D2 : préchauffage des moteurs disponibles au lancement (fil dédié, appel à blanc sur 20 s de signal synthétique), indicateur « Préchauffage des moteurs (k/n)… » puis « Moteurs prêts » ou « Moteurs prêts, sauf X » dans l'en-tête ; option `--sans-prechauffage`. Durée annoncée sous « Analyser » dès le dépôt (fichier normalisé à ce moment, normalisation réutilisée par l'analyse).
- Amendement 2 de D17 : fourchette surcoût + RTF × durée à surcoût + 1,3 × RTF × durée ; surcoût fixe compté seulement pour un moteur froid (ni chargé ni préchauffé) ; recalage sur la vitesse observée depuis le début de l'étape la plus longue de l'expérience source (parts lues dans `etapes_s` de `execution_<périphérique>.json`).
- B2, R-D3 : cache des résultats (`app/cache.py`) indexé par l'empreinte SHA-256 des échantillons de l'audio normalisé, le moteur, les réglages (périphérique, nombre de locuteurs, paramètres effectifs, θ compris) et le commit (« +modifie » si l'arbre n'est pas propre), rangé dans `~/.cache/whospoke/resultats/`, sans audio ni nom de fichier ; case « Réafficher un résultat déjà calculé », bouton « Vider le cache », option `--vider-cache`.
- Défauts trouvés à 375 px et corrigés : la règle mobile de `.gradio-container` ne s'appliquait pas (Gradio préfixe les sélecteurs d'un `@media`), la barre d'onglets et les tableaux élargissaient la page (487 puis 655 px de large). Gouttières et onglets par `clamp()`, tableaux et timeline à largeur intrinsèque nulle.
- Vérifié dans le navigateur, mode factice : clair et sombre à 1280 px, 375 px en clair et en sombre (largeur de page 375 px avant et après l'analyse) ; annonce, recalage (« reste environ 4 s, recalé sur la vitesse observée »), comparaison de deux moteurs dont l'un en cache, réaffichage depuis le cache, indicateur de préchauffage, onglet Avancement.
- Tests : `tests/test_app_cache.py` (8), `tests/test_app_demonstration.py` (16, dont une analyse factice de bout en bout : annonce, calcul, mise en cache, réaffichage identique, cache désactivé, autre réglage, vidage), `tests/test_app_temps.py` étendu (fourchette, parts, recalage), test de la file d'attente réécrit. `uv run pytest` : 302 réussis, 9 ignorés, 1 lent exclu.
Résultats : aucune expérience.
Décisions : aucune. Choix de la session, à valider : case « Réafficher un résultat déjà calculé » cochée par défaut ; préchauffage de tous les moteurs disponibles sur le périphérique de « auto » ; recalage seulement après 1 s et 2 % de l'étape la plus longue ; « État constaté » de la file réduit aux fiches.
Problèmes : le préchauffage réel n'a pas été exécuté (aucun modèle chargé) : appel à blanc des vrais moteurs sur signal synthétique à vérifier à la fusion, en particulier la baseline (une erreur est consignée et affichée sans bloquer). Les baselines ne rapportent leur avancement qu'en fin d'étape : pas de recalage avant la fin de la représentation. Tout commit invalide le cache. `test_depot_principal_complet_si_present` échouait sur l'état vivant du dépôt principal (EXP-0016 à EXP-0019 de la piste A, sans notes.md) : le test ne compte plus les expériences sans notes.md, pas encore interprétées (D26 §2). Sous ~380 px, Gradio range deux onglets dans son menu « … ».
Suite : fusion après B2 (planning), avec vérification du préchauffage réel et de l'annonce sur les vrais moteurs ; B3.

## 2026-11-01 — Interface : cache selon le retour du cockpit, vue d'ensemble et raccourcis (B3) (Claude Code)

Objectif : appliquer les décisions du cockpit sur le cache (retour du chantier B1-B2) et réaliser B3 (chantier C3), dans le worktree `ui`, moteur factice, sans modèle, fusion ni dépendance ajoutée.
Réalisé :
- Cache : case « Réafficher un résultat déjà calculé » décochée par défaut ; badge « Résultat réaffiché depuis le cache, calculé le … » dans le panneau d'avancement (préfixé par le moteur en comparaison) ; clé = empreinte de l'audio normalisé, moteur, réglages, configuration effective de l'expérience source (`moteurs.effective_configuration`) et révisions figées des modèles (`moteurs.model_revisions`), sans le commit, qui reste consigné dans l'entrée ; format d'entrée 2. Case décochée, l'annonce signale le résultat présent en cache et le nouveau calcul. `pipeline.execution_file` délègue à `moteurs.execution_path`.
- B3, vue d'ensemble (R-U2) : greffon Minimap de wavesurfer 7.12.12 embarqué (`app/static/wavesurfer-7.12.12/minimap.min.js`), tiré de l'archive npm, intégrité sha512 vérifiée contre le registre, licence BSD-3-Clause du paquet, aucune URL ; fenêtre visible rendue déplaçable (souris, doigt, ← → quand elle a le focus) ; clic ailleurs : lecture et vue amenées à cet instant.
- B3, lecture suivie et raccourcis (R-U3) : la vue suit la lecture ; bouton « Suivre la lecture », coupé quand on déplace la vue à la main ; Espace, ← → (tours du premier moteur ou du locuteur isolé), 1 à 9 (isoler un locuteur, autres pistes estompées), 0, ? (aide, aussi par un bouton ; Échap la ferme) ; inactifs dans un champ de saisie, dans le tableau de renommage, avec un modificateur ou hors de l'onglet Analyse ; pastille « parle : X » pendant la lecture.
- Vérifié dans le navigateur, mode factice : clair et sombre à 1280 px, clair et sombre à 375 px (largeur de page 375 px) ; glisser de la fenêtre (vue 1:38–3:00, lecture inchangée, suivi coupé), tours suivants, isolement, pastille, aide, raccourcis ignorés avec le focus dans un champ, badge du cache après relance du serveur. Deux défauts trouvés et corrigés pendant la vérification : la miniature captait le glisser destiné à la fenêtre (couches au-dessus de celle-ci), et la ligne du zoom débordait à 375 px.
- Tests : clé du cache (composantes, commit absent), badge, case décochée, révisions et configuration effective des moteurs, greffon embarqué (empreinte, licence), gabarit et script du visualiseur ; tests ciblés pendant le travail, suite complète une fois à la fin : 308 réussis, 9 ignorés, 1 lent exclu.
Résultats : aucune expérience.
Décisions : aucune. Choix de la session, à valider : déplacer la vue à la main coupe le suivi de la lecture ; ← revient au début du tour en cours s'il a commencé depuis plus de 0,3 s ; l'isolement estompe les autres pistes sans changer la lecture ; badge placé dans le panneau d'avancement, qui reste visible après « Nouvelle analyse ».
Problèmes : le simulateur de clavier du navigateur intégré n'émet pas « ? » (touche à `key` vide) : vérifié par évènement synthétique et par le bouton. Un changement de code qui modifierait les résultats sans changer la configuration effective ni les révisions n'invalide plus le cache. Couleurs de la vue d'ensemble fixées au rendu, comme la forme d'onde (limite déjà acceptée, D26).
Suite : fusion après B2 selon le planning (préchauffage réel à vérifier) ; B4.

## 2026-11-01 — Interface : empreinte du code des moteurs, appariement et explication des erreurs (B4) (Claude Code)

Objectif : compléter la clé du cache selon le retour du cockpit sur B3, puis réaliser B4 (chantier C4 de l'audit, R-U4 et R-U6), dans le worktree `ui`, moteur factice, sans modèle, fusion ni dépendance ajoutée.
Réalisé :
- Cache : empreinte du code des moteurs dans la clé (`cache.engine_code_fingerprint` : chemins et contenu des fichiers de `src/whospoke/` et de `app/moteurs.py`, caches Python exclus) ; format d'entrée 3. Test : documents, interface et `__pycache__` sans effet ; fichier du paquet modifié, ajouté ou supprimé, et `app/moteurs.py`, avec effet.
- Appariement visible : pistes de la référence aux couleurs du locuteur du premier moteur apparié, étiquette « 021 ↔ SPEAKER_03 », « (non apparié) » en gris sinon ; appariement optimal du DER calculé une fois avec la carte des erreurs (`sortie._Matching`, `error_map` refactorisée autour). Tableau d'appariement sous le DER : temps commun (cooccurrence de pyannote.core), couverture et pureté par locuteur (`DiarizationCoverage` et `DiarizationPurity` de pyannote.metrics restreintes à un locuteur, sans recodage).
- « Expliquer cette erreur » : carte ouverte par un clic sur une zone de la carte des erreurs (type, durée, locuteurs avec leur appariement, constats sur la référence : chevauchement, tour de moins de 0,5 s, pause de moins de 1 s, frontière de tour à moins de 0,25 s), formulée en constats, jamais en cause.
- Extrait typique : bouton ▶ par locuteur (plus long tour hors chevauchement, 10 s au plus), lu dans la timeline.
- Renommage dans le tableau des locuteurs (un champ par ligne, Entrée ou sortie du champ) ; grille Gradio supprimée ; noms échappés, valeur du champ comprise.
- Vérifié dans le navigateur en mode factice avec l'audio de `summre__007a_ECRH` et sa référence (copiés dans le dossier temporaire du lancement, supprimé à la fermeture) : clair à 1280 px, sombre et clair à 375 px. Défaut corrigé pendant la vérification : intervalle d'une zone courte affiché « 1:30 – 1:30 », désormais au dixième de seconde.
- Tests : `tests/test_app_appariement.py` (9 : appariement identique à celui du DER, tableau cohérent avec la pureté et la couverture globales de pyannote.metrics, couleurs de la référence, contextes, constats sans cause, extrait typique, renommage et échappement, refus des doublons), test de l'empreinte du code, tests de la comparaison mis à jour (référence désormais colorée). Tests ciblés pendant le travail, suite complète une fois à la fin : 319 réussis, 9 ignorés, 1 lent exclu.
Résultats : aucune expérience. Sur 007a_ECRH avec les segments d'EXP-0007 : DER sans collar 19,15 %, appariement 021 ↔ SPEAKER_03, 022 ↔ SPEAKER_00, 023 ↔ SPEAKER_01, 024 ↔ SPEAKER_02, couvertures de 83,3 à 93,2 %, puretés de 81,0 à 92,2 % (affichage, pas une mesure au sens du protocole : sans UEM).
Décisions : aucune. Choix de la session, à valider : seuil de proximité d'une frontière de tour fixé à 0,25 s (valeur du collar) ; pause « contiguë » à 0,05 s près ; pauses comptées seulement entre deux plages de parole (ni avant la première, ni après la dernière) ; appariement et couleurs de la référence d'après le premier moteur en comparaison ; tableau d'appariement par moteur dans l'Évaluation.
Problèmes : aucun bloquant. À 375 px, le tableau des locuteurs défile dans son cadre (champ du nom et ▶ visibles, colonnes suivantes à faire défiler).
Suite : fusion après B4 selon le planning (préchauffage réel à vérifier) ; B5.

## 2026-11-01 — Interface : Avancement raconté et Pipeline relié aux mesures (B5) (Claude Code)

Objectif : chantier B5 (C6 de l'audit, R-U7 et R-U8) dans le worktree `ui`, moteur factice, sans modèle, fusion ni dépendance ajoutée, à partir de `docs/constats.yaml` et `docs/synthese.md` du cockpit (lus via `--depot`).
Réalisé :
- `app/constats.py` : lecture et contrôle de `docs/constats.yaml` (champs manquants, confiance inconnue, fichier illisible signalés).
- Avancement : encadré « Ce que nous avons appris » (constats `cle: true`, confiance, bouton par source qui affiche ses notes) ; bouton qui rend `docs/synthese.md` dans la page ; graphique SVG en barres empilées du DER test sans collar des systèmes de référence par corpus (`app/graphique.py`, `avancement.reference_systems` : MFCC, ECAPA, WeSpeaker, pyannote par leur première expérience réaliste, puis tout verdict « retenu » ou « référence ») ; D1 à D15 repliées, D16 et suivantes visibles ; chemin local du dépôt masqué.
- Graphique selon le skill dataviz : palette (trois premiers emplacements de la palette de l'application) validée par `validate_palette.js` en clair (#ffffff) et en sombre (#1b1c1f), tous contrôles réussis, avertissement de contraste du vert en clair compensé par les valeurs écrites et le tableau ; motifs (plein, hachures à 45° et 135°), légende, `title` et `desc`, info-bulles, tableau repliable, deux mises en page (large et étroite).
- Pipeline : constats sous chaque étape selon `etape` et `moteurs`, « evaluation » sous l'étape Évaluation, nombre de constats sur le bouton de l'étape ; constats à étape inconnue ou mal formés signalés en tête de page ; pour pyannote, bloc « Segmentation neuronale (détection et segmentation) » avec les réglages et constats de chaque étape, déclaré dans une nouvelle section `regroupements` en fin de `src/whospoke/pipelines/catalogue.yaml` (repli sur le catalogue de ce code si celui de `--depot` ne l'a pas).
- Vérifié dans le navigateur, mode factice, `--depot ~/Dev/Who-Spoke` : clair et sombre à 1280 px, clair et sombre à 375 px (largeur de page 375 px). Défaut antérieur corrigé au passage : à 375 px, le chemin « Défini dans » de la page Pipeline débordait de sa carte.
- Tests : `tests/test_app_mesures.py` (14 : lecture des constats, constats du dépôt principal bien formés, choix des systèmes du graphique, graphique accessible, encadré, synthèse, décisions repliées et chemin masqué, constats par étape et par moteur, bloc de pyannote, regroupement lu dans le catalogue) ; test des sections de l'Avancement mis à jour. Tests ciblés pendant le travail, suite complète une fois à la fin : 330 réussis, 9 ignorés, 1 lent exclu.
Résultats : aucune expérience.
Décisions : aucune. Choix de la session, à valider : systèmes de référence identifiés automatiquement (pipeline et représentation, première expérience réaliste par corpus) ; SUMM-RE avant AMI ; couleurs catégorielles pour les trois types d'erreur dans ce graphique, alors que la carte des erreurs de l'Analyse reste à l'encre ; regroupement déclaré dans le catalogue, donc dans `src/` (chemin contrôlé, D18 : l'empreinte du code des moteurs change, et le cache des résultats avec elle).
Problèmes : `docs/constats.yaml` et `docs/synthese.md` ne sont pas encore commités dans le dépôt principal : sur la branche `ui` seule (sans `--depot`), l'encadré indique leur absence. À vérifier à la fusion : conflit possible sur la fin de `catalogue.yaml` si `main` y ajoute aussi une section.
Suite : B6 ; fusion selon le planning.

## 2026-11-01 — Interface : retouches de B5, fusion de locuteurs, interactions, exports et fiche de reproductibilité (B6) (Claude Code)

Objectif : retouches du graphique de B5 demandées par le cockpit, puis chantier B6 (P2 de l'audit : R-U9, R-U10, R-U11, R-D5 ; R-U12 abandonné) dans le worktree `ui`, moteur factice, sans modèle, fusion ni dépendance ajoutée.
Réalisé :
- Retouches de B5 : le graphique de l'Avancement reprend les motifs de la carte des erreurs (parole manquée pleine, fausse alarme hachurée, confusion en contour) ; vert pris un pas plus foncé (#199e70), `validate_palette.js` sans avertissement en clair et en sombre.
- Fusion de deux locuteurs depuis le tableau (« Fusionner avec… »), en chaîne, annulable (dernière fusion), sur une copie de l'annotation : le résultat du moteur et le cache ne changent jamais. Statistiques, interactions, timeline, comparaison, exports, DER, appariement et carte des erreurs recalculés ; « DER avant → après » dans l'Évaluation. La couleur d'un locuteur suit le locuteur, pas son rang.
- Indicateurs d'interaction sans transcription (`app/interactions.py`) : plus long monologue, tours, durée moyenne d'un tour, plus long tour, latence médiane de réponse par locuteur, matrice « qui suit qui » (tableau N × N accessible, effectifs écrits).
- Exports : étiquettes Audacity (une ligne par tour, code `S1`… dans le texte, format lu par `whospoke.maison.reference.read_labels` de la branche `outils`), image SVG de la timeline (`app/image.py`) et PNG tiré du SVG par le navigateur, sans dépendance.
- Fiche de reproductibilité dans le JSON (`app/reproductibilite.py`) : versions, commit, empreintes du code et de l'audio, révisions des modèles, configuration effective, réglages, machine et périphérique, durées, fusions.
- Vérifié dans le navigateur, mode factice, `summre__007a_ECRH` et sa référence : clair et sombre à 1280 px et à 375 px. Défauts corrigés pendant la vérification : liste « Fusionner avec… » qui gardait le choix précédent après redessin ; fusion en 10 s sur 20 min d'audio (DER calculé trois fois), ramenée à 3,3 s puis 2,2 s ; à 375 px, « Temps de traitement » et « Exports » côte à côte (défaut antérieur, rendu visible par les noms des nouveaux exports), désormais empilés.
- Tests : `tests/test_app_fusion.py` (11 : fusion sur copie et en chaîne, fusion et annulation depuis le tableau avec cache intact, DER avant → après et DER d'avant gardé, nom déjà pris à l'annulation, liste échappée, tours et passages, indicateurs, matrice accessible, étiquettes Audacity, image, fiche, traçabilité d'une analyse factice et d'un réaffichage) ; tests du graphique, du renommage et des exports mis à jour. Tests ciblés pendant le travail, suite complète une fois à la fin : 341 réussis, 9 ignorés, 1 lent exclu.
Résultats : aucune expérience. Sur 007a_ECRH (segments d'EXP-0007) : fusion de SPEAKER_03 dans SPEAKER_01, DER sans collar 19,15 % → 31,12 % ; 287 passages de parole, latence médiane 0,00 s pour chaque locuteur (85 passages exactement jointifs dans la sortie de pyannote) ; affichage, pas une mesure au sens du protocole.
Décisions : aucune. Choix de la session, à valider : définitions des indicateurs (tour = intervention, sans comblement des pauses ; passage de parole au sens du « floor transfer offset », tours inclus exclus ; latence signée, médiane) ; locuteur absorbé = celui de la ligne, l'autre garde nom et couleur ; annulation de la dernière fusion seulement ; codes Audacity `S1`… dans l'ordre de première prise de parole, correspondance dans le JSON ; une seule image par analyse (comparaison comprise), en couleurs du mode clair ; PNG produit par le navigateur, absent de la liste des exports.
Problèmes : aucun bloquant. Le moteur factice affiche dans « Temps de traitement » le chemin local du RTTM qu'il relit (antérieur, mode factice seulement, hors exports).
Suite : fusion d'`ui` dans `main` à l'arrêt de la piste A, selon le planning.

## 2026-11-02 — Interface : robustesse face à des fichiers inconnus (B7) (Claude Code)

Objectif : chantier B7 (cas limites de l'interface, pour la démonstration du 16/11) dans le worktree `ui`, moteur factice, sans modèle, fusion ni dépendance ajoutée ; démarche du skill break-ui (emilkowalski/skills, lu sans être installé).
Réalisé :
- `tests/fabrique.py` : fichiers de test sans donnée personnelle (audio synthétique par ffmpeg : vidéo mp4 et mov, vidéo muette, stéréo 44,1 et 48 kHz, m4a, ogg, m4a coupé, texte renommé en .wav, 3 s, silence, 30 et 90 min ; sorties fabriquées : 0, 1, 6, 9 et 12 locuteurs, chevauchement massif, tours de 50 ms ; références mal formées, d'un autre fichier, plus longue, plus courte). Option `--factice-rttm` : le moteur factice relit une sortie fabriquée au nom du fichier déposé.
- Messages qui disent quoi faire : fichier audio illisible (cause d'après ffmpeg, conseil, détail technique sans chemin), fichier inconnu du moteur factice, référence contrôlée ligne à ligne dès le dépôt (colonnes, nombres, durée négative refusée, fichier vide ou binaire, étiquettes Audacity reconnues, plusieurs enregistrements) ; titres des notifications en français.
- Avertissements « À vérifier » : fichier silencieux (avant le lancement), référence d'un autre enregistrement, plus longue ou plus courte que l'audio (le DER est calculé quand même).
- Aucun locuteur : état, tableaux et timeline le disent. Pluriels (« 1 locuteur », « aucun passage ») et durées sous la seconde au centième (tours de 50 ms).
- 10 locuteurs et plus : isolement par clic sur le nom d'une piste ; matrice numérotée au-delà de 4 locuteurs ou de noms longs, noms des lignes figés. Noms longs coupés par « … » dans la timeline (la colonne des noms ne s'élargit plus). Doublons de noms à la casse, aux blancs et à « _ » près, refusés avec la raison. Étape d'état pendant la mise en forme des résultats.
- Vérifié dans le navigateur (clair et sombre à 1280 px, sombre à 375 px) avec les fichiers fabriqués : erreurs audio, silence, 3 s, 12 locuteurs aux noms longs et spéciaux, tours de 50 ms, 90 min au zoom maximal, références mal assorties.
- Tests : `tests/test_app_cas_limites.py` (31, plus 2 lents pour 30 et 90 min, lancés une fois : réussis) ; tests de la lecture des références et du message du moteur factice mis à jour. Tests ciblés pendant le travail, suite complète une fois à la fin : 372 réussis, 9 ignorés, 3 lents exclus.
Résultats : aucune expérience. 90 min en mode factice : préparation 8 s, analyse et rendus 7 s, fusion 10 s, 1,1 Go ; dans le navigateur, résultat 13 s après le dépôt, zoom maximal en 0,45 s.
Décisions : aucune. Choix de la session, à valider : silence sous −80 dB ; seuils des avertissements de référence (1 s de parole au-delà de l'audio ; 10 s et 5 % de la parole trouvée après la fin de la référence) ; DER toujours calculé sur toute la durée, même avec une référence plus courte (l'avertissement conseille de couper l'audio, plutôt que de restreindre l'évaluation) ; nom de la référence comparé au nom du fichier (simple avertissement) ; matrice numérotée au-delà de 4 locuteurs ou de 14 caractères ; doublons de noms à la casse près.
Problèmes : sortie très morcelée lente (`Timeline.co_iter` de pyannote.core, à peu près quadratique en densité de segments) : 36 000 tours de 50 ms en 30 min demanderaient plusieurs minutes de mise en forme ; hors de portée des moteurs actuels. Comportement des moteurs réels sur ces fichiers à vérifier à la fusion. Au zoom maximal (60 px/s), un tour de 50 ms fait 3 px.
Suite : fusion d'`ui` dans `main` à l'arrêt de la piste A, selon le planning.

## 2026-11-02 — Piste A : A1, A2, fusions, D21, moteurs externes, essai de l'application, préparation d'A3 (Claude Code)

Objectif : rangs A1 et A2 du planning v2.0, puis, avant A3, fusion d'`outils` et d'`ui`, silero-vad, amendement du 01/11 de D21, enregistrement de Nemotron 3 et de DiariZen, essai de l'application avec les vrais moteurs ; enfin préparation d'A3 (D24) jusqu'à l'écoute de la candidate.
Réalisé :
- Commits `docs:` des documents du cockpit (planning v2.0, D23 à D25, D21, synthèse, constats, journal), en trois fois au fil de la session.
- Enveloppe pyannote à deux sorties (`12a67a6`) : réglage `sortie` (`habituelle` ou `exclusive`) qui désigne la sortie évaluée ; l'autre est écrite dans `rttm_<nom>/` (`Resultat.autres_sorties`). Relevé par fichier du nombre de groupes de VBx avant les bornes et du recours au KMeans (`n_locuteurs_vbx`, `kmeans`, `n_locuteurs_kmeans` dans `execution_*.json` et run.log), par enveloppes transparentes de `cluster_vbx` et `KMeans` pendant l'appel. Test lent EXP-0001 réussi avant et après.
- EXP-0016 à EXP-0019 exécutées (MPS puis CPU), évaluées, commitées ; `notes.md` avec en-tête (verdict `en_cours`) et observations factuelles, l'interprétation étant laissée au cockpit.
- Fusion d'`outils` (`f2c22a8`) puis d'`ui` (`03429e5`) : conflits de `docs/journal.md` résolus en gardant toutes les entrées (58) ; `catalogue.yaml` fusionné sans conflit (moteurs d'E4 et E5, section `regroupements`). `uv sync`, suite complète, lents et `modele` compris : 484 réussis, 2 ignorés (silero-vad absent).
- `uv add silero-vad==6.2.3` (`02edec3`) : roue `7b7f5436cfcb…` et poids `e1122837f415…`, ceux vérifiés par E5 ; aucun autre paquet modifié ; `tests/test_silero.py` 17 réussis.
- Amendement du 01/11 de D21 (`88e3ebb`, test corrigé dans `12946df`) : `run_experiment.py` relève alimentation et charge aux mêmes instants par `whospoke.charge.MachineMonitor` (60 s) ; le bloc `alimentation` consigne `coeurs_performance` et `charge_concurrente` ; `evaluate.py` reporte `charge_concurrente` dans `temps` et `temps_cpu` (null sans relevé de charge). Les expériences antérieures ne sont pas requalifiées.
- `PIPELINES` (`858e635`) : `nemotron3-diarization` et `diarizen` (enveloppes d'E4) ; type de périphérique lu aussi pour les moteurs externes. Les environnements `envs/` et les poids ne sont pas créés dans ce dépôt (`scripts/envs/*.sh --modeles`, A4 et A5).
- Essai de l'application, moteurs réels (port 7870, le 7860 étant pris par une application en mode factice lancée la veille, PID 72900, laissée en place), sous hook d'audit Python et relevé `lsof` toutes les 0,5 s : préchauffage des 4 moteurs (« Moteurs prêts ») ; extrait de 3 min de 007a_ECRH (mp3 stéréo 44,1 kHz) et sa référence coupée : durée annoncée 9 à 12 s, réelle 10 s ; DER sans collar 11,63 % (manquée 3,68, FA 4,56, confusion 3,39), avec collar 4,24 % ; appariement 021 → SPEAKER_00, 022 → SPEAKER_02, 023 → SPEAKER_01, 024 non apparié (3 locuteurs trouvés pour 4) ; cache : réaffichage en 1 s avec le badge et le même DER. Réseau : seulement `127.0.0.1:7870` (et le `bind` local de `::1`) ; `lsof` vide hors local.
- A3, préparation (`12e63be`, `4e88c85`, `61a6a9f`) : `scripts/data/make_summre_degrade.py`, `configs/summre_degrade.yaml`, 7 tests. Pistes individuelles de SUMM-RE test absentes localement : retéléchargées (28 Parquet, 12,72 Go, révision et SHA-256 du 28/10) en 10 min 19 s, 124 pistes, 8,8 Go dans `data/raw/summre/pistes/test/`. Dépendance ajoutée : pyroomacoustics 0.10.1 (MIT ; tire Cython 3.3.1), pour simuler les réponses impulsionnelles ; aucune télémétrie, aucun événement réseau en usage (inventaire de `telemetry.py` complété). MUSAN écarté (archive unique de 11,09 Go) ; DEMAND retenu (CC BY-SA 3.0 d'après sa documentation, CC BY 4.0 d'après les métadonnées Zenodo), 4 environnements (OOFFICE, PCAFETER, DLIVING, DWASHING ; OMEETING exclu), canal 1, MD5 contrôlé ; `docs/corpus.md` §7.1 mis à jour avant le téléchargement. Génération : 259 fichiers en 1 053 s (`data/processed/summre_degrade/<condition>/`, 1,3 Go par condition), manifeste `data/manifests/summre_degrade.csv`. Dossier d'écoute : 3 extraits de 20 s par condition et `propre` (093c_EBPZ, Zoom ; 053b_EDDH ; 060a_EDRH), plus 20 s de chaque bruit seul, avec `index.html`.
Résultats :
- EXP-0016 (SUMM-RE, sortie exclusive) : DER sans collar 29,18 % (dev), 30,40 % (test). Sortie habituelle identique à l'octet aux 73 RTTM d'EXP-0007. Écart à EXP-0007 (bootstrap apparié, 1 000 tirages, graine 0) : test +4,10 [+3,24 ; +5,03] sans collar, +2,97 [+2,21 ; +3,81] avec collar, 36 fichiers sur 37 dégradés ; dev +3,18 [+2,45 ; +3,92]. Test : parole manquée 15,55 contre 7,15, FA 8,30 contre 11,28, confusion 6,55 contre 7,87.
- EXP-0017 (AMI, sortie exclusive) : 23,09 % (dev), 24,48 % (test). Sortie habituelle identique à l'octet aux 34 RTTM d'EXP-0001. Écart à EXP-0001 : test +4,56 [+2,79 ; +6,32] sans collar, +3,55 [+1,87 ; +5,27] avec collar, 16 fichiers sur 16 dégradés ; dev +4,45 [+3,72 ; +5,00].
- EXP-0018 (SUMM-RE, bornes 2 à 6) : 26,00 % (dev), 25,82 % (test). VBx dans les bornes pour 72 fichiers sur 73 ; un KMeans : test 080b_EBDH (VBx 1, KMeans 2, référence 3), DER 66,01 → 51,25 %. Les 72 autres RTTM sont identiques à ceux d'EXP-0007. Écart : test −0,48 [−1,48 ; 0,00], dev 0,00.
- EXP-0019 (AMI, bornes 2 à 6) : 18,64 % (dev), 19,92 % (test). VBx dans les bornes pour les 34 fichiers (de 2 à 6), aucun KMeans ; RTTM identiques à l'octet à ceux d'EXP-0001.
- RT60 des réponses simulées : en T20, médianes 0,40 s (rev04, cible 0,4), 0,90 s (rev08, cible 0,8), 0,66 s (salle, cible 0,6) ; en T60 sur toute la décroissance, 0,53, 1,18 et 0,86 s. Décalage du codec mesuré : de −0,19 à +0,06 ms. Fichiers atténués pour éviter l'écrêtage (gain consigné) : 8 (rev04), 4 (rev08), 6 (salle), 4 (bru05), 1 (bru15), 2 (cod16), 2 (cod08). Déterminisme : cod08 et salle régénérés, SHA-256 identiques au manifeste.
Décisions : aucune.
Problèmes :
- EXP-0016 à EXP-0019 ont tourné pendant le travail des sessions B (interface) et E (outils), sans relevé de charge (antérieures à l'amendement de D21, non requalifiées). Charge sur 1 min relevée à 9,05 pour 6 cœurs de performance pendant EXP-0016. RTF MPS de pyannote : 0,059 à 0,066 (EXP-0016), contre 0,051 dans EXP-0007.
- EXP-0016 : 17 s sur batterie (21:12:09 à 21:12:26 d'après `pmset -g log`), un relevé hors secteur : `temps.conforme` false pour l'exécution MPS ; la mesure CPU est conforme ; métriques non affectées.
- Deux commits de code (`88e3ebb`, `12e63be`) ont été faits avec un test en échec (`test_controle_config`, bloc `temps_cpu` comparé en entier) : la suite complète n'avait pas été lancée après le premier, et le second a été commité par une commande enchaînée malgré l'échec. Corrigé par `12946df` ; suite complète, lents compris, 498 réussis.
- Le commit de fusion d'`outils` (`f2c22a8`) n'a pas le préfixe `chore:`.
- `test_depot_principal_complet_si_present` échouait après la fusion, faute de `notes.md` pour EXP-0016 à 0019 : en-têtes ajoutés (`16e5015`).
- `generation.json` (non versionné) décrit la dernière exécution du générateur, la régénération de contrôle (cod08 et salle) ; la génération complète (1 053 s) n'y figure plus, mais le manifeste versionné porte toutes les empreintes.
- Les bruits seuls du dossier d'écoute sont à leur niveau d'origine, faible (−37 à −56 dBFS) : monter le volume.
- Espace disque : 19 Go libres (pistes de test 8,8 Go, conditions 9,1 Go).
Suite : écoute de contrôle par la candidate (`data/processed/summre_degrade/ecoute/index.html`), puis expériences d'A3 (pyannote, configuration d'EXP-0007, et baseline ECAPA, configuration d'EXP-0012) ; le script d'exécution devra lire les WAV de `data/processed/summre_degrade/<condition>/` avec les références et UEM de SUMM-RE (corpus `summre-<condition>`), ce qui reste à faire.

## 2026-11-02 — Outils : tableaux et figures du rendu (E7) (Claude Code)

Objectif : chantier E7 dans le worktree `outils`, resynchronisé avec `main` (avance rapide sur `2c769ea`), sans modèle chargé, fusion ni dépendance ajoutée : générer depuis le leaderboard, les results_*.json et `docs/constats.yaml` les tableaux et figures du rendu dans `docs/rendu/` (versionné).
Réalisé :
- `scripts/rendu.py` : lit, en lecture seule, les expériences par le code de l'onglet Avancement (`app.avancement.read_items`), les per_file, `docs/constats.yaml` (`app.constats.read`), `configs/summre_degrade.yaml` et `results/campagne_temps/*/campagne.json`. Écrit dans `docs/rendu/` : `README.md` (index et contrôles), `systemes.md`, `oracles.md`, `robustesse.md`, `temps.md` et deux figures SVG. `--verifier` : code 1 si le dossier n'est plus à jour ; `--racine`, `--sortie`, `--campagne`. Sortie déterministe, sans date de génération ni chemin local.
- Systèmes : par corpus, partition test, condition réaliste (ni nombre de locuteurs ni détection oracle) ; DER dans les deux conditions de collar, composantes sans collar, nombre de locuteurs exact (réunions, d'après les per_file) ; écart à la référence déclarée de chaque expérience (`reference` de results.json), bootstrap apparié sur les fichiers (`bootstrap_der_ci`, 1 000 tirages, graine 0), dans les deux conditions de collar, avec le nombre de fichiers où l'expérience fait mieux ou moins bien.
- Oracles : série `ORACLE_SERIES` de l'onglet Avancement, mêmes colonnes, écart à la référence avec IC.
- Robustesse (D24) : expériences ayant des `results_summre-<condition>_test.json` ; une ligne par moteur et condition, dans l'ordre de la configuration ; écart au propre avec IC (propre : le jeu `summre-propre` ou `summre` de l'expérience, sinon le test de SUMM-RE de sa référence déclarée) ; sous-groupes réunions Zoom (liste `ecoute.liste_zoom` de la configuration) et autres. Pas d'intervalle sous 5 réunions (seuil de `scripts/rapport_maison.py`) : c'est le cas du groupe Zoom (3 réunions). Vide tant qu'A3 n'a pas de résultat.
- Temps : campagne la plus récente non factice et aux conditions de départ réunies ; ligne non conforme affichée « non reportée » (D21). Vide tant que la campagne du 12/11 n'a pas eu lieu.
- Figures : `app.graphique.svg` sur les barres de `app.avancement.reference_systems`, en mises en page large et étroite, rendues autonomes : règles `.av-chart` et teintes de `app/static/interface.css` recopiées à la génération, en clair et en sombre (`prefers-color-scheme`), taille explicite. Rendu vérifié par aperçu Quick Look.
- Chaque tableau indique ses sources : expériences avec le commit d'exécution (et d'évaluation s'il diffère), fichiers lus, constats liés (ceux dont une source est une expérience du tableau). Contrôle de concordance du leaderboard et des results_*.json, dans les deux sens, à 0,005 point près.
- `tests/test_rendu.py` : 16 tests sur un dépôt fabriqué (systèmes, écart et IC comparés à un appel direct de `bootstrap_der_ci`, absence d'IC sous 5 fichiers, référence absente, oracles, robustesse vide puis remplie avec sous-groupes, propre de l'expérience prioritaire, campagnes factice, hors conditions et réelle, sources et constats, contrôle du leaderboard, figures bien formées et identiques au corps de l'onglet, écriture puis `--verifier`, dépôt réel sans erreur).
- `docs/rendu/` généré sur ce dépôt ; lien depuis le README.
Résultats : aucune expérience. Leaderboard et results concordent (38 lignes). Écarts recalculés identiques à ceux des notes : EXP-0016 contre EXP-0007, test, +4,10 [+3,24 ; +5,03] sans collar ; EXP-0018, −0,48 [−1,48 ; +0,00]. Tests ciblés pendant le travail ; suite complète une fois à la fin : 500 réussis, 12 ignorés, 3 désélectionnés, aucun échec.
Décisions : écart des systèmes mesuré à la référence déclarée de chaque expérience, et non à un système de référence fixe par corpus (choix de la session, validé le 02/11). Choix de la session, à valider : pas d'intervalle sous 5 réunions dans les sous-groupes ; libellé d'un système décliné complété par sa variable modifiée.
Problèmes :
- `docs/rendu/` reflète les documents commités sur `main` : `docs/constats.yaml` version du 01/11 (C01 à C10) et verdicts `en_cours` d'EXP-0016 à 0019. Les mises à jour du cockpit non commitées dans `~/Dev/Who-Spoke` (C11, C12, verdicts) y entreront à la régénération qui suivra leur commit.
- Depuis que silero-vad est dans `uv.lock`, la suite par défaut lance `test_modele_reel_de_silero` (marqué `modele`, non exclu par défaut), qui charge sur CPU le modèle de Silero livré dans le paquet (2 Mo, sans réseau).
- La comparaison des moteurs entre eux à condition égale (D24 §3) n'est pas dans le tableau de robustesse, qui donne moteur × condition.
Suite : régénérer `docs/rendu/` après chaque expérience évaluée (`uv run python scripts/rendu.py`) et après la campagne du 12/11.

## 2026-11-02 — Outils : retours du cockpit sur E7 (Claude Code)

Objectif : appliquer le retour du cockpit sur E7 (journal de `main`, entrée « Retour du chantier E7 »), sans modèle chargé, fusion ni dépendance ajoutée.
Réalisé :
- `systemes.md` : l'écart à la référence déclarée reste la première comparaison ; seconde comparaison ajoutée, l'écart à pyannote community-1 du même corpus (EXP-0007 sur SUMM-RE, EXP-0001 sur AMI, choisi comme dans le graphique de l'Avancement : première expérience pyannote en condition réaliste avec un résultat de test non invalidé), avec IC du bootstrap apparié dans les deux conditions de collar et fichiers où l'expérience fait mieux ou moins bien. Les en-têtes nomment la référence de chaque colonne ; la légende précise que la seconde n'est pas une comparaison à une seule variable. Toutes les expériences du tableau ont désormais une ligne d'écarts, y compris celles sans référence déclarée (baselines MFCC).
- `robustesse.md` : section « Comparaison à pyannote community-1, à condition égale (D24 §3) » : chaque autre moteur d'A3 contre pyannote, condition par condition, propre compris, bootstrap apparié. L'expérience pyannote d'A3 est celle dont le propre est EXP-0007 ; une variante (sortie exclusive) est comparée comme un autre moteur.
- `test_modele_reel_de_silero` : déjà marqué `modele` depuis `0d475a5` (E5), comme les tests d'ECAPA ; vérifié que `-m "not modele"` l'exclut. Aucun changement.
- `tests/test_rendu.py` : 3 tests ajoutés (écart à pyannote du même corpus, comparaison à pyannote par condition avec choix de l'expérience pyannote, A3 sans pyannote) ; 19 au total.
Résultats : aucune expérience. SUMM-RE test, écart à EXP-0007 sans collar : baseline MFCC +23,06 [+19,05 ; +26,92], ECAPA +7,12 [+3,72 ; +9,77], WeSpeaker +9,56 [+6,02 ; +12,44]. Tests ciblés pendant le travail ; suite complète une fois à la fin : 503 réussis, 12 ignorés, 3 désélectionnés.
Décisions : aucune (application du retour du cockpit).
Problèmes : `main` a avancé (`61cd335` : conditions de D24, exécution partagée, A-0002) sans être refusionné dans `outils` ; le nommage `summre-<condition>` et les per_file lus ici sont ceux de `main`. A-0002 donne un IC pour le groupe Zoom, `docs/rendu/` n'en donne pas sous 5 réunions (décision du cockpit) : les deux sources diffèrent sur ce point.
Suite : régénérer `docs/rendu/` après la fusion dans `main` et après chaque expérience d'A3.

## 2026-11-02 — Interprétation d'A1 et A2 ; retours de B7 et E6 (cockpit)

Objectif : interpréter EXP-0016 à 0019 et trancher les questions des pistes A, B et E.
Réalisé : interprétations et verdicts d'EXP-0016 à 0019 ; constats C11 et C12 ; synthèse mise à jour ; méthode §4.2 (dossiers `rttm_<sortie>/`).
Résultats : sortie exclusive écartée (+4,1 points sur SUMM-RE, +4,6 sur AMI, significatif) ; bornes de 2 à 6 sans effet significatif, une seule réunion concernée.
Décisions :
- V1 de D25 écartée ; R-U12 abandonné. Bornes de 2 à 6 retenues comme garde-fou de la configuration de démonstration, sans gain revendiqué.
- D24 : bruits DEMAND (sans OMEETING) validés ; les réunions Zoom simulées dans une salle sont gardées, mais les résultats d'A3 seront aussi donnés à part pour les réunions Zoom et les autres, parce qu'une réunion Zoom réverbérée dans une seule salle est moins plausible ; RT60 rapporté en T20, avec le T60 mesuré en annexe.
- Script d'exécution : lecture des conditions dégradées avec les références et l'UEM de SUMM-RE test ; `evaluate.py` accepte une exécution partagée (V2 et V3), avec un fichier d'exécution rappelé dans chaque dossier.
- Processus : ne jamais enchaîner un commit après les tests autrement que par `&&` ; règle à ajouter à CLAUDE.md.
- B7 : seuils validés (silence −80 dB, avertissements de référence, matrice numérotée, doublons sans tenir compte de la casse) ; zoom maximal relevé à 150 px/s si la fluidité tient sur 30 min.
Suite : écoute de contrôle de D24 par la candidate, puis A3 ; chantiers B8 et E7.

## 2026-11-02 — README à jour (cockpit)

Réalisé : état d'avancement au 02/11 (D24, D25, bornes, moteurs externes, corpus maison, outillage), description des onglets et options de l'application après B1 à B7, documents ajoutés au tableau de documentation, note sur les temps de référence (D21).

## 2026-11-02 — Retour du chantier E7 (cockpit)

Décisions :
- tableau des systèmes : deux colonnes d'écart, toutes deux avec IC. La première, principale, donne l'écart à la référence déclarée (protocole, une seule variable). La seconde donne l'écart à pyannote community-1 (EXP-0001 ou EXP-0007, selon le corpus), parce que la question du rendu est aussi : « quel système face au moteur de démonstration ? ». Les en-têtes nomment explicitement la référence de chaque colonne ;
- robustesse : ajouter la comparaison des moteurs entre eux à condition égale (D24 §3), par rapport à pyannote ;
- pas d'IC sous 5 réunions (groupe Zoom) et libellés complétés par la variable modifiée : validés ;
- `test_modele_reel_de_silero` : admis (petit modèle livré avec le paquet, hors ligne), mais marqué `modele` comme les tests d'ECAPA, pour pouvoir l'exclure pendant les expériences.

## 2026-11-02 — Retours de B8 et du complément d'E7 (cockpit)

Décisions :
- Gel : un moteur absent de `configs/demo.yaml` n'est plus proposé, au lieu de bloquer le lancement. Il est mentionné dans l'en-tête (« non retenu pour la démonstration »). Seule l'absence du moteur par défaut, ou une incohérence du fichier, arrête le lancement.
- Validés : en comparaison avec une fourchette, la baseline estime elle-même son nombre de locuteurs ; contenu du mode présentation ; zoom maximal à 150 px/s.
- Cohérence des intervalles : aucun IC sous 5 réunions, partout. A-0002 n'a pas encore tourné : sa configuration reçoit `ic_min_fichiers: 5` avant exécution, et le groupe Zoom (3 réunions) n'a qu'un écart, sans intervalle, comme dans `docs/rendu/`.
- Processus : le `git checkout` qui a annulé du travail non commité (session B) relève de la même prudence que la règle 11 de CLAUDE.md ; une règle 12 interdit toute commande git qui écrase des modifications non commitées sans en avoir d'abord fait un commit ou une remise de côté.
- Sessions B et E : en pause après ces chantiers, pour alléger la machine pendant A3 et A6 ; elles reprendront pour la fusion, le gel et les retouches de la démonstration.

## 2026-11-02 — Bilan face à l'énoncé ; D28 (cockpit)

Objectif : vérifier la couverture de l'énoncé.
Résultats : toutes les exigences sont couvertes ou en cours, sauf deux manques, les cas d'échec (aucune analyse d'ensemble) et les spectrogrammes (calculés, jamais montrés). VoxConverse, étudié mais non utilisé, doit être justifié dans le rendu (anglais, pas des réunions, vu à l'entraînement par pyannote et Nemotron 3).
Décisions : D28 — analyse A-0003 des cas d'échec et vue spectrogramme ; planning en version 2.1 (chantiers B9 et E8, calendrier recalé sur l'avancement réel).

## 2026-11-02 — Retours de B9 (spectrogramme) et E8 (script d'A-0003) (cockpit)

Décisions :
- Catégories d'erreur (carte « Expliquer cette erreur » et A-0003, une seule définition) : chaque seconde d'erreur reçoit une **catégorie principale**, exclusive, selon cet ordre de priorité :
  1. décalage de frontière : la zone tient entièrement dans ±0,25 s d'une frontière de tour de la référence, c'est-à-dire dans ce que le collar pardonne ;
  2. chevauchement dans la référence ;
  3. locuteur de référence non apparié ;
  4. locuteur trouvé en trop, c'est-à-dire non apparié dans l'hypothèse (nouvelle catégorie) ;
  5. tour de référence de moins de 0,5 s ;
  6. pause de 1 s au plus ;
  7. autre.

  Les catégories principales somment à 100 %. Contrôle attendu : la part « décalage de frontière » doit être proche de l'écart entre le DER sans collar et le DER avec collar. La carte de l'interface affiche la catégorie principale, puis les autres constats comme aujourd'hui. La modification est faite côté interface (session B, `app/sortie.py`) ; A-0003 la reprend sans seconde définition.
- A-0003 : partitions dev et test réunies par corpus (analyse descriptive, avec la partition en colonne), zone comme unité pondérée par sa durée, fenêtres de 15 s et plafonds validés. La grille d'écoute remplie par la candidate porte sur des corpus publics : elle est versionnée dans `analyses/A-0003_cas-echec/`. Celle du corpus maison reste locale.
- B9 : tous les choix validés (image côté serveur, 40 bandes de la baseline, plage de 60 dB, rampe grise, énergie dans une bande séparée avec les régions de parole, calcul en tâche de fond). Écart à la règle 11 consigné, sans suite.
- Rappel : la décision sur les moteurs absents de `configs/demo.yaml` (entrée B8 du 02/11) est à faire par la session B.

## 2026-11-02 — Catégorie « décalage de frontière » : décision (cockpit)

Constat (session B, 007a_ECRH) : la règle « zone entière dans ±0,25 s » classe 47,5 s en décalage de frontière, alors que le collar pardonne 155,6 s d'erreur. Les 108,1 s restantes sont des morceaux de zones plus longues.
Décision : option b. La catégorisation se fait sur le temps, pas sur la zone entière. Chaque zone d'erreur est découpée aux bords des intervalles de ±0,25 s autour des frontières de la référence. La partie située dans ces intervalles est classée « décalage de frontière » ; le reste reçoit sa catégorie principale selon les règles du 02/11. Le contrôle devient exact en secondes : décalage de frontière = erreur pardonnée par le collar. On compare en secondes et non en points, puisque le collar retire aussi de la parole de référence du dénominateur. Les autres catégories décrivent alors ce que le collar ne pardonne pas, la lecture la plus utile. Dans l'interface, une zone garde une seule catégorie affichée, celle de sa partie hors collar ; la carte « Expliquer cette erreur » ajoute « dont x s dans la tolérance d'une frontière (pardonnés par le collar) ». Une zone entièrement dans la tolérance reste classée « décalage de frontière ».

## 2026-11-02 — Pause volontaire de la piste A (cockpit)

EXP-0020 a été mise en pause par la candidate à 15 h 02 (déplacement), au fichier 186 sur 259 ; reprise prévue cette nuit. Ce n'est pas un incident. À la reprise, les fichiers déjà produits sont gardés s'ils sont complets, et les temps de l'exécution sont marqués comme interrompus. Le calendrier glisse d'une demi-journée : A6 la nuit du 2 au 3/11, A4 et A5 les 3 et 4/11.

## 2026-11-02 — Audit visuel de l'interface (cockpit)

Objectif : rendre l'interface la plus propre possible, corriger les artefacts signalés par la candidate et mieux représenter le pipeline.
Réalisé : `docs/audit/audit-visuel-2026-11-02.md`. Captures de la branche `ui` (59a83b8) en clair, en sombre, à 375 px et en mode présentation ; deux recherches web (représentation des pipelines ; finition de Gradio 6.31, dont la lecture de son code) ; 13 défauts relevés (V1 à V13).
Résultats : artefacts des radios en sombre expliqués par les variantes `_dark` non définies du thème et par le point blanc codé en dur de `radio_circle` ; séparateurs du tableau des locuteurs portés par les cellules ; cinq styles de boutons dans la barre de la timeline ; rangée du pipeline qui passe à la ligne, sans formes de données.
Décisions : système visuel unique fondé sur les jetons du thème (§4) ; nouvelle représentation du pipeline (§6) ; chantiers B10 à B13 ajoutés au planning, à faire avant le gel.

## 2026-11-02 — Retour de B10 (système visuel) (cockpit)

Décisions :
- validés : `launch(head=…)` plutôt que `head_paths` ; bouton « Mode présentation » en interrupteur ; Ko = 1 000 octets (SI) ; signe moins typographique (−).
- Restriction : le signe moins typographique et l'espace fine ne servent qu'à l'affichage. Les fichiers exportés (RTTM, JSON, étiquettes Audacity) gardent des nombres lisibles par machine (point décimal, tiret ASCII, aucune espace) ; un test le vérifie.
- Champs de texte : le filet clair est accepté si le fond du champ ou sa bordure atteint 3:1 face à la carte (WCAG 1.4.11) ; sinon, bordure contrastée comme pour les ronds et les cases.
- Note sur le cockpit : le correctif `radio_circle` proposé par l'audit ne suffisait pas ; la session l'a constaté et corrigé par une règle de `jetons.css`. C'est la raison de la mention « probable » dans l'audit.
Suite : B11.

## 2026-11-02 — Retour de B11 (cockpit)

Décisions : choix validés (« S1 » = rang du locuteur trouvé, cohérent avec les touches et les codes Audacity ; « Énergie et seuil » derrière la loupe à 375 px ; carte « Comment ça marche » à la place du panneau d'état avant la première analyse). Une condition : l'état du préchauffage (« Préchauffage… », « Moteurs prêts ») reste visible en permanence, mode présentation compris, sous la forme d'un petit indicateur dans l'en-tête, pour savoir avant la démonstration que les moteurs sont prêts. Le panneau « Détails » qui se referme au changement de moteur est accepté ; à garder ouvert si c'est simple.
Suite : B12.

## 2026-11-02 — Retour de l'adaptation d'A-0003 (cockpit)

Décisions : amendement du 02/11 de D28 (seuil du « tour court » porté à 1 s, croisement des catégories avec le type d'erreur). Validés : « décalage de frontière » exclu des extraits d'écoute (ce que le collar pardonne n'est pas un échec à écouter) ; part dans la tolérance répartie uniformément sur la zone pour le seul choix des fenêtres. L'écart résiduel de −1,2 s (ECAPA, SUMM-RE, 102c_EBPH) est à vérifier : il pourrait venir d'un appariement des locuteurs recalculé avec le collar ; il sera consigné tel quel s'il est confirmé. Figures de `docs/rendu/` à régénérer après la fusion dans main.

## 2026-11-02 — Retour de B12 (onglet Pipeline) (cockpit)

Décisions : validés, la section `formes` du catalogue (mots seulement, valeurs lues dans la configuration effective), le bloc « un seul réseau » en un seul onglet avec ses étapes numérotées 2 et 3, et le badge limité aux trois composantes du DER. Correction : dans la barre « naissance des erreurs », la confusion est rattachée aux empreintes **et** au regroupement, pas au regroupement seul. Nos mesures montrent que la représentation en est la cause principale : passer des MFCC à ECAPA divise la confusion par trois (C05). Un clic sur le segment sélectionne « Empreintes » et met aussi en évidence « Regroupement ».
Suite : B13.

## 2026-11-02 — Retour de B13 (cockpit)

Décisions :
- Avancement à moins de 840 px : la frise montre les cinq dernières expériences, suivies d'un bouton « Afficher les N autres » ; affichage complet au-delà de 840 px. Pas de retour au tableau défilant.
- Retour du menu « … » de Gradio sous environ 340 px de large : accepté (aucun écran visé n'est aussi étroit).
- Validés : dates au format JJ/MM/AAAA, masquages du mode présentation, coupe des noms de pistes en fin de nom.
- Règle 11 : précision à ajouter à CLAUDE.md. La commande de tests qui précède `&&` n'est jamais filtrée par un tube (`| tail`, `| grep`) : soit pas de tube, soit `set -o pipefail`.
Suite : piste B en pause après ces retouches ; fusion d'`ui` dans `main` par la piste A à sa prochaine pause ; essai au vidéoprojecteur par la candidate.

## 2026-11-02 — Outils : E8, script de l'analyse A-0003 (cas d'échec, D28 §1) (Claude Code)

Objectif : chantier E8 dans le worktree `outils`, sans modèle chargé, fusion vers `main` ni dépendance ajoutée.
Réalisé :
- Resynchronisation : `main` (`666171a`) fusionné dans `outils` (`a5a7158`) ; conflit de `docs/journal.md` résolu en gardant les entrées des deux côtés.
- `analyses/A-0003_cas-echec/config.yaml` commité avant toute exécution (`3816cd0`) : systèmes pyannote (EXP-0001 AMI, EXP-0007 SUMM-RE) et baseline ECAPA (EXP-0010, EXP-0012), partitions dev et test réunies par corpus ; ajouts prévus en commentaire (Nemotron 3, DiariZen, V2 de D25, conditions de D24 par `corpus: summre-<condition>`, corpus maison).
- `scripts/analyses/a0003_cas_echec.py` (`c14a794`, `8dca98e`, `55f68a1`) : classement par DER sans collar et 5 pires par système et corpus ; descripteurs tirés de la référence restreinte à l'UEM (nombre de locuteurs, part de chevauchement rapportée à la parole, part des tours de moins de 1 s en nombre, durée moyenne d'un tour, part de parole, type de réunion Zoom ou autre pour SUMM-RE) et erreur sur le nombre de locuteurs (K̂ − K et sa valeur absolue) ; rho de Spearman par système et corpus, sans p-valeur ; catégories des secondes d'erreur par `app.sortie.error_map` et les seuils de `app.sortie`, avec référence et hypothèse restreintes à l'UEM officiel (contrôle : totaux de la carte comparés aux composantes des per_file, arrêt au-delà de 0,01 s) ; secondes par catégorie, secondes de la seule catégorie, et sans catégorie ; extraits d'écoute de 15 s : un par catégorie (fenêtre où elle a le plus d'erreur et domine), puis les pires fichiers, jusqu'à 8, un fichier au plus une fois, 4 au plus par système, 5 au plus par corpus ; page `index.html` (référence, hypothèse et erreurs de la fenêtre, cases des causes de D28 §1.5, champs libres, grille remplie téléchargée en CSV, réponses gardées dans le navigateur) et `grille.csv`. Corpus maison refusé dans les extraits publics ; ses extraits vont dans `data/processed/a0003/ecoute_maison/`, avec leur liste, jamais dans le dossier de l'analyse. Options `--donnees`, `--experiences`, `--sortie` (essai, interdit sous `analyses/`), `--sans-extraits` ; `execution.json` avec commit, arbre, empreintes des per_file, RTTM, références et de `app/sortie.py`, seuils de la carte.
- `tests/test_a0003_cas_echec.py` : 12 tests sur un dépôt fabriqué (références tirées au hasard, bruit synthétique, per_file de l'évaluateur du protocole) : constats identiques à ceux de la carte zone par zone, seuils lus dans l'application, totaux égaux aux composantes du protocole avec UEM, décomptes, descripteurs, Spearman, fenêtres et dominance, refus du corpus maison, exécution complète, extraits publics et locaux, essai et immuabilité, lancement hors de pytest.
- Essai sur EXP-0001, 0007, 0010 et 0012 (`--sortie data/processed/a0003/essai`, commit `8dca98e`, arbre propre), lecture de RTTM seulement, sous `nice -n 19`, 1 min 33 s. Page d'écoute vérifiée dans le navigateur (affichage, export de la grille).
Résultats : essai, non versionné, `analyses/A-0003_cas-echec/` sans résultat.
- Contrôle des totaux : écart nul entre la carte et les per_file pour les 4 sources.
- Part de l'erreur sans collar par catégorie (une zone pouvant relever de plusieurs) : pyannote AMI chevauchement 52,1 %, tour court 12,4 %, frontière 85,7 %, pause 15,6 %, non apparié 0,8 %, aucune 10,3 % ; pyannote SUMM-RE 35,5, 10,7, 96,0, 43,1, 3,3, 2,5 % ; ECAPA AMI 43,9, 11,9, 63,1, 7,9, 6,8, 32,2 % ; ECAPA SUMM-RE 51,6, 14,5, 87,5, 26,5, 11,2, 10,9 %. Durée médiane d'une zone : 0,10 s (pyannote SUMM-RE) à 0,37 s (ECAPA AMI).
- Pires fichiers : pyannote SUMM-RE 080b_EBDH (66,0 %, 2 locuteurs pour 3), 008a_EARH (44,9 %) ; pyannote AMI IB4002 (29,3 %) ; ECAPA AMI ES2011a (67,1 %) ; ECAPA SUMM-RE 019a_EARD (55,0 %).
- Spearman, DER sans collar contre part de chevauchement : 0,59 et 0,65 (pyannote AMI, SUMM-RE), 0,42 et 0,73 (ECAPA) ; contre durée moyenne d'un tour : −0,60, −0,65, −0,57, −0,49.
- 8 extraits : 4 par système, 4 par corpus (chevauchement, tour court, frontière, pause, non apparié, aucune, puis 2 pires fichiers).
Décisions : aucune. Choix de la session, à valider : partitions réunies par corpus pour le classement et les corrélations ; unité de catégorisation = la zone de la carte ; parts calculées en nombre de tours et rapportées à la parole ; fenêtres de 15 s ; plafonds par système et par corpus ; colonnes « seule » ajoutées.
Problèmes :
- La catégorie « frontière » couvre 63 à 96 % de l'erreur : les zones de la carte sont courtes (médiane 0,1 à 0,4 s) et leurs bords tombent presque toujours à 0,25 s au plus d'une frontière de tour. Le constat est juste mais peu discriminant pour l'analyse ; le changer demande une décision (dans la carte et dans A-0003 à la fois, pour garder une seule définition).
- La catégorie « non apparié » ne couvre que les locuteurs de référence ; une surestimation du nombre de locuteurs (locuteur trouvé en trop) n'a pas de catégorie.
- EXP-0020 (piste A) tournait pendant les tests et l'essai : tout a tourné sous `nice -n 19` ; la suite complète a exclu les tests `modele` en plus des lents.
- D28, la règle 12 de CLAUDE.md, A-0002 et EXP-0020/0021 ne sont pas commités sur `main` : ils ne sont pas dans `outils` après la resynchronisation.
- L'essai a tourné sur `8dca98e` ; `55f68a1` ne change que l'ordre des colonnes de `extraits.csv` et un message.
Résultats des tests : ciblés pendant le travail ; suite complète une fois, sans lents ni `modele` : 524 réussis, 12 ignorés, 7 désélectionnés.
Suite : première exécution officielle après A3 et A6 (vers le 4/11), depuis `main` après fusion : décommenter ou ajouter les systèmes (EXP-0020, EXP-0021, V2…) dans la configuration, puis `uv run python scripts/analyses/a0003_cas_echec.py --config analyses/A-0003_cas-echec/config.yaml` ; écoute des extraits par la candidate (`data/processed/a0003/ecoute/index.html`), grille remplie à remettre au cockpit.

## 2026-11-02 — Interface : zoom relevé, mode présentation, configuration de démonstration (B8) (Claude Code)

Objectif : chantier B8 dans le worktree `ui` (resynchronisé avec `main` en avance rapide), moteur factice, sans modèle, fusion ni dépendance ajoutée : zoom maximal relevé si la fluidité tient sur 30 min, mode présentation, lecture de `configs/demo.yaml` (D17, amendement 1).
Réalisé :
- Zoom : fluidité mesurée sur une réunion fabriquée de 30 min, 2 moteurs et une référence (10 581 segments et zones). À 60 comme à 150 px/s, la lecture suivie tombait à 20 à 44 images/s, à cause des pistes (la forme d'onde n'y était pour rien). Correctif : les segments et zones hors de la vue sont masqués (une largeur de vue de part et d'autre gardée). À 150 px/s : 118 à 120 images/s en lecture suivie et en glissement, sans image au-delà de 50 ms. Zoom maximal relevé à 150 px/s.
- Mode présentation (`--presentation` et bouton de l'en-tête) : texte et commandes agrandis d'un quart, pistes et boutons du visualiseur plus grands, contrastes renforcés (texte secondaire, filets, fonds de piste, cartes cernées), périphérique, cache, aide en ligne et étapes terminées masqués. Vérifié à 1280 × 720 en clair et en sombre.
- Gel : `moteurs.demo_config` lit `configs/demo.yaml` (moteur par défaut, expérience source de chaque moteur, nombre de locuteurs par défaut) et retombe sinon sur `app/moteurs.py`. Fichier incohérent refusé au lancement avec ce qu'il faut corriger. Option `--config-demo` pour essayer un fichier. `configs/demo.exemple.yaml` écrit (fourchette de 2 à 6 pour pyannote), pas `configs/demo.yaml`. Configuration et moteur en vigueur dans l'en-tête ; `configuration_demo` (fichier, gel, SHA-256) dans la fiche de reproductibilité.
- Comparaison : avec la fourchette par défaut, comparer pyannote à la baseline ECAPA était refusé. Le second moteur estime désormais lui-même le nombre de locuteurs ; l'annonce, une notification et le bandeau le disent.
- Corrigés en passant : coche et point radio invisibles en sombre ; chemin du RTTM du mode factice qui élargissait la page à 375 px ; en mode présentation, tailles de Gradio redéclarées sur `body.dark`.
- Tests : `tests/test_app_presentation_gel.py` (26). Tests ciblés pendant le travail, suite complète une fois à la fin : 509 réussis, 12 ignorés, 3 lents exclus.
Résultats : aucune expérience. Mesures de fluidité dans `app/README.md` (B8).
Décisions : aucune. Choix de la session, à valider :
- Un moteur absent de `configs/demo.yaml` est refusé (le gel décrit chaque moteur), au lieu d'être masqué ou repris de `app/moteurs.py`.
- En comparaison avec une fourchette, le second moteur (baseline) tourne en nombre automatique au lieu d'être refusé.
- En mode présentation, la liste des étapes terminées est masquée, et le sous-titre gardé.
- Contenu du mode présentation : agrandissement d'un quart, teintes renforcées, réglages masqués (périphérique, cache).
Problèmes :
- Mesures faites dans le panneau masqué du navigateur de l'application : images calculées sans ralentissement (122 images/s au repos), mais affichage réel à l'écran non mesuré ; 90 min non mesurées à 150 px/s.
- Au zoom maximal, la tabulation ne parcourt plus que les segments affichés, ceux de l'écran et de ses abords.
- Mon erreur : une commande a annulé par `git checkout` mes modifications non commitées de `visualiseur.js` ; je les ai réappliquées à l'identique et revérifiées (tests, comportement dans le navigateur).
Suite : au gel du 10/11, copier `configs/demo.exemple.yaml` en `configs/demo.yaml` avec les expériences retenues ; essai du mode présentation sur le vidéoprojecteur réel.

## 2026-11-02 — Interface : vue spectrogramme et énergie de la baseline (B9, D28 §2) (Claude Code)

Objectif : chantier B9 du planning v2.1 (D28 §2) dans le worktree `ui`, resynchronisé avec `main` (fusion `aae2803`, conflit du journal résolu en gardant toutes les entrées), moteur factice, sans modèle, fusion dans `main` ni dépendance ajoutée.
Réalisé :
- Greffon Spectrogram de wavesurfer 7.12.12 : archive npm vérifiée de nouveau (intégrité sha512 du registre, mêmes empreintes pour les fichiers déjà embarqués, licence BSD-3-Clause, aucune URL), puis mesuré sur un banc hors de l'application (30 min, 150 px/s). Il ne tient pas : gels de 0,6 à 0,9 s au glissement et à chaque pas de zoom, avec ou sans travailleur. La variante windowed du même paquet reste fluide mais ne dessine qu'à l'arrêt (vue vide pendant un glissement). Les deux exigent de décoder tout l'audio dans le navigateur. Aucun n'est embarqué.
- Solution de repli de D28, image calculée côté serveur (`app/spectrogramme.py`) : spectrogramme mel dont la baseline tire ses MFCC (25 ms, 10 ms, 40 bandes, même appel à librosa), 60 dB sous le maximum, 8 bits, pyramide de résolutions (moyennes de 2^k trames), fichier binaire à côté de l'audio normalisé ; calcul lancé en tâche de fond dès la normalisation du fichier déposé. Dans le navigateur, bascule « Forme d'onde / Spectrogramme » : un canevas de la largeur de la vue sous la forme d'onde rendue transparente, seules les colonnes visibles mises en couleurs au niveau adapté au zoom ; graduations de 500 Hz à 8 kHz ; légende.
- Palette : rampe neutre interpolée en OKLab, du fond des pistes à l'encre (plus foncé = plus d'énergie en clair, plus clair en sombre) ; la couleur reste aux locuteurs (D26).
- Option « Énergie et seuil » quand un des moteurs est une baseline : bande à part sous la vue (énergie par trame, seuil en tirets, régions de parole retenues, infobulle), lue dans la trace du moteur (`engine.trace` demandé à la baseline seule), gardée dans le cache des résultats au dixième de dB. En mode factice, trace fabriquée par le moteur factice (énergie par tranche de 10 ms, seuil à la médiane), marquée « Trace factice ».
- Vérifié dans le navigateur intégré, réunion de 30 min (SUMM-RE 007a_ECRH bouclée, copie locale supprimée ensuite) : clair et sombre à 1280 × 720, sombre à 375 px (largeur de page 375 px), mode présentation (spectrogramme de 144 px), comparaison avec la trace prise sur le second moteur. Défaut corrigé : graduations 250 Hz et 500 Hz superposées.
- Tests : `tests/test_app_spectrogramme.py` (15 : spectrogramme identique à celui des MFCC de la baseline, quantification, pyramide, fichier, tâche de fond, graduations, palette monotone et régulière en OKLab, détection tirée d'une vraie trace de la baseline MFCC sur signal synthétique, aller-retour du cache, trace factice seulement pour une baseline, valeur du visualiseur, gabarit et script, analyse factice de bout en bout avec réaffichage depuis le cache). Tests ciblés pendant le travail, suite complète une fois à la fin : 536 réussis, 12 ignorés, 3 lents exclus.
Résultats : aucune expérience. Fluidité à 150 px/s sur 30 min (2 moteurs, référence, 5 833 segments et zones) : spectrogramme et énergie affichés, 108 à 114 images/s en lecture suivie, 120 et 100 images/s en glissement de 40 et 400 px par image, aucune image au-delà de 50 ms en glissement ; forme d'onde (témoin) : 113, 119 et 106 images/s. Calcul côté serveur : 3,0 s pour 30 min ; fichier de 14 Mo chargé en 0,31 s. Détail dans `app/README.md` (B9).
Décisions : aucune. Choix de la session, à valider :
- Image côté serveur plutôt que la variante windowed du greffon (fluide, mais vide pendant un glissement, et audio décodé dans le navigateur).
- Spectrogramme de la baseline (40 bandes) plutôt qu'un spectrogramme plus fin pour l'affichage : on voit ce que voit la baseline, au prix d'une image moins détaillée en hauteur.
- Plage de 60 dB sous le maximum du fichier (Praat : 50 dB) ; rampe neutre plutôt qu'une palette à plusieurs teintes (viridis, magma) ; hauteur de 112 px (144 px en mode présentation).
- Énergie dans une bande séparée avec sa propre échelle, plutôt que superposée au spectrogramme (pas de double axe) ; régions de parole retenues ajoutées à la courbe et au seuil ; option disponible dans les deux vues (forme d'onde et spectrogramme).
- Calcul du spectrogramme pour tout fichier déposé, en tâche de fond, même si la vue n'est jamais ouverte (3 s de calcul pour 30 min, en concurrence avec le moteur si l'analyse est lancée aussitôt).
Problèmes :
- Mesures faites pendant un calcul de la piste A (EXP-0020), panneau du navigateur affiché ; non mesuré à 90 min ; affichage réel à l'écran non mesuré, comme en B8.
- Trace réelle de la baseline non vérifiée dans l'application (moteur factice seulement) ; son extraction est testée sur une vraie trace de la baseline MFCC (signal synthétique, aucun modèle). `app/moteurs.py` modifié : l'empreinte du code des moteurs change, donc le cache des résultats est invalidé une fois.
- Mon erreur : la suite complète a été lancée avec sa sortie redirigée, sans commit enchaîné par `&&` (règle 11). Pour ne pas la relancer pendant le calcul de la piste A, le commit `dd140d9` suit par `&&` les tests ciblés (`tests/test_app_spectrogramme.py`, `test_app_interface.py`, `test_app_demonstration.py` : 48 réussis), sans changement du code entre les deux.
- Le retour du cockpit sur B8 (moteur absent de `configs/demo.yaml` non proposé au lieu de bloquer) n'était pas dans ce lot : non fait.
Suite : fusion d'`ui` dans `main` à l'arrêt de la piste A ; vérification de la trace de la vraie baseline à la fusion.

## 2026-11-02 — Interface : catégorie principale des erreurs, moteurs non retenus (retours de B8, B9 et E8) (Claude Code)

Objectif : appliquer les deux décisions du cockpit du 02/11 dans le worktree `ui`, moteur factice, sans modèle, fusion ni dépendance ajoutée.
Réalisé :
- Catégorie principale des zones d'erreur, une seule définition dans `app/sortie.py` (`ERROR_CATEGORIES`, `main_category`) : décalage de frontière (zone entièrement dans ±0,25 s d'une frontière de tour de la référence), chevauchement, locuteur de référence non apparié, locuteur trouvé en trop, tour de moins de 0,5 s, pause de 1 s au plus, autre. `error_map` donne la catégorie de chaque zone et les durées par catégorie et par type, cumulées segment par segment. Seuil de pause passé de « moins de 1 s » à « 1 s au plus ».
- Carte « Expliquer cette erreur » : catégorie principale et sa phrase en tête, puis les autres constats (celui que porte la catégorie n'est pas répété) ; la note rappelle que ce n'est pas une cause établie.
- Moteurs absents de `configs/demo.yaml` : non proposés (`DemoConfig.excluded`), mention « Non retenu pour la démonstration » dans l'en-tête et la console ; seuls l'absence du moteur par défaut et un fichier incohérent arrêtent le lancement ; second moteur proposé : ECAPA si retenue, sinon le premier autre moteur. `configs/demo.exemple.yaml` dit la nouvelle règle.
- Corrigé en passant : un long chemin passé à `--config-demo` élargissait la page à 409 px sur un écran de 375 px.
- Vérifié dans le navigateur, moteur factice, 007a_ECRH avec sa référence (copie locale supprimée ensuite) et une configuration sans la baseline WeSpeaker : carte en sombre à 1280 px et en clair à 375 px (largeur de page 375 px), en-tête, liste des moteurs.
- Tests : `tests/test_app_categories.py` (7 : sommes par catégorie face aux composantes du DER sur 60 paires aléatoires, égalité stricte sur des durées exactes en binaire, ordre de priorité, frontière stricte, part « décalage de frontière » égale à l'écart entre conditions de collar sur des cas construits, carte, gabarit) ; 3 tests du gel ajoutés, tests de la carte mis à jour. Tests ciblés pendant le travail, suite complète une fois à la fin, commit enchaîné par `&&` : 545 réussis, 12 ignorés, 3 lents exclus.
Résultats : aucune expérience. 007a_ECRH (sortie d'EXP-0007, toute la durée, sans UEM, comme l'interface) : DER 19,15 % sans collar, 9,23 % avec (écart 9,92 points, 155,6 s d'erreur) ; décalage de frontière 47,5 s, soit 4,00 points. Part de l'erreur sans collar : chevauchement 30,9 %, pause courte 24,8 %, autre 21,9 %, décalage de frontière 20,9 %, tour court 1,5 %, aucun locuteur non apparié. Détail dans `app/README.md`.
Décisions : aucune. Points à trancher :
- Le contrôle attendu (« décalage de frontière » proche de l'écart entre DER sans et avec collar) tient sur des cas construits, pas sur 007a_ECRH : 47,5 s contre 155,6 s. L'erreur située dans les zones du collar fait exactement 155,6 s, dont 108,1 s en morceaux de 282 zones plus longues classées ailleurs (chevauchement 45,1 s, pause 40,3 s, autre 19,8 s, tour court 2,9 s) ; en points, l'écart est aussi grossi par la parole de référence que retire le collar (1 188 → 779 s). Options : (a) garder la règle « zone entière » (actuelle), une catégorie par zone, et rapporter l'écart tel quel ; (b) découper les zones aux bords du collar et classer les morceaux, la part retrouvant alors l'écart en secondes, mais une zone de la carte aurait plusieurs catégories ; (c) catégorie de la zone par sa majorité de temps dans ou hors du collar.
- « Somment exactement » : la partition est exacte, et l'égalité stricte en flottants tient quand les durées sont exactes en binaire ; sur des durées quelconques, l'écart va jusqu'à 7·10⁻¹⁵ s (575 égalités strictes sur 600), par l'ordre des additions. Le test l'accepte à 10⁻¹² s près.
Problèmes : `app/moteurs.py` modifié : l'empreinte du code des moteurs change, le cache des résultats est invalidé une fois de plus. A-0003 (piste E) doit importer `sortie.main_category` et `ERROR_CATEGORIES` plutôt que recoder les règles.
Suite : fusion d'`ui` dans `main` à l'arrêt de la piste A ; décision du cockpit sur le contrôle du collar.

## 2026-11-02 — Interface : catégories des erreurs sur le temps (option b) (Claude Code)

Objectif : appliquer l'option b décidée par le cockpit le 02/11 dans le worktree `ui`, moteur factice, sans modèle, fusion dans `main` ni dépendance ajoutée.
Réalisé :
- `app/sortie.py` : chaque segment d'erreur est découpé aux bords des intervalles de ±0,25 s autour des frontières de tour de la référence. Ces intervalles sont construits par `extrude` de pyannote.metrics, comme pour le DER avec collar. La partie dans la tolérance va en « décalage de frontière ». Le reste reçoit la première catégorie vraie dans l'ordre du 02/11, évaluée sur ce reste (`_Context.describe_parts`). Chaque zone donne `tolerance_s`, `contexte_hors_tolerance` et `categorie`, la catégorie de sa partie hors tolérance (« décalage de frontière » si elle tient entièrement dans la tolérance).
- Carte « Expliquer cette erreur » : catégorie et sa phrase sur la partie hors tolérance (« Hors de la tolérance d'une frontière : … »), puis « Dont x s dans la tolérance d'une frontière (pardonnés par le collar) », puis les autres constats sur toute la zone. Le constat « un de ses bords est à 0,25 s au plus d'une frontière » est remplacé par cette part.
- Vérifié dans le navigateur, moteur factice, 007a_ECRH avec sa référence (copie locale supprimée ensuite) : carte à 1280 px et à 375 px (largeur de page 375 px), quatre catégories rencontrées.
- Tests : `tests/test_app_categories.py` (10) : sommes face aux composantes du DER sans collar ; ordre de priorité ; découpage sur le temps ; tours et pauses courts absorbés par la tolérance ; égalité « décalage de frontière » = erreur retirée par le collar, type par type, sur 3 cas construits et sur 007a_ECRH ; égalité exigée sur des paires aléatoires chaque fois que le collar garde l'appariement ; carte ; gabarit. Tests de la carte de `test_app_appariement.py` mis à jour. Tests ciblés pendant le travail, suite complète une fois à la fin, commit enchaîné par `&&` : 548 réussis, 12 ignorés, 3 lents exclus.
Résultats : aucune expérience. 007a_ECRH (sortie d'EXP-0007, toute la durée, sans UEM, comme l'interface) : décalage de frontière 155,625 s (45,959 s de parole manquée, 76,289 s de fausse alarme, 33,377 s de confusion), égal type par type à l'erreur retirée par le collar, écart résiduel nul. Répartition de l'erreur sans collar (227,5 s) : décalage de frontière 68,4 %, autre 15,6 %, chevauchement 10,9 %, pause courte 5,1 %, tour court et locuteurs non appariés 0.
Décisions : aucune. Points à signaler au cockpit :
- L'égalité exige que le DER avec collar garde l'appariement des locuteurs. Sur 200 paires d'annotations aléatoires, elle tient dans 189 cas. Les 11 autres (écart jusqu'à 2,09 s) sont exactement ceux où le collar change l'appariement : l'erreur hors tolérance change alors aussi, et aucune catégorisation de l'erreur sans collar ne peut la retrouver. Sur 007a_ECRH, l'appariement ne change pas.
- Conséquence de la règle évaluée sur la partie hors tolérance : un tour de moins de 0,5 s ou une pause de 0,5 s au plus tient entièrement dans la tolérance de ses frontières. « Tour court » est donc toujours vide, et « pause courte » ne compte que les pauses de plus de 0,5 s à 1 s. Ces contextes restent dans les constats de la carte. Variante possible, non appliquée : évaluer les règles 2 à 7 sur la zone entière plutôt que sur sa partie hors tolérance.
- Pour A-0003 (piste E) : lire `error_map(...)["categories"]` et les champs de zone, sans recoder les règles.
Problèmes : aucun. `app/moteurs.py` n'est pas modifié : l'empreinte du code des moteurs et le cache des résultats sont inchangés.
Suite : fusion d'`ui` dans `outils` par la session E, puis dans `main` à l'arrêt de la piste A.

## 2026-11-02 — Interface : système visuel, composants communs, formatage français, contrôle automatique (B10) (Claude Code)

Objectif : chantier B10 du planning (audit visuel du 02/11, §3, §4 et §7) dans le worktree `ui`, moteur factice, sans modèle, fusion ni dépendance Python ajoutée. `ui` contenait déjà tout `main` (aucune resynchronisation nécessaire). L'option b des frontières, demandée en préalable, était déjà faite et poussée (`229b578`, journal `a00ed7d`) : l'audit visuel avait été mené sur `59a83b8`, juste avant.
Réalisé :
- Jetons dans `app/static/jetons.css`, seul fichier contenant des valeurs (couleurs, ombres, arrondis, espacement, hauteur des contrôles, mouvement), injecté sans réécriture dans `<head>` par `launch(head=…)`, l'équivalent en chaîne de `head_paths`. Un fichier HTML versionné pour `head_paths` aurait dû contenir un chemin absolu. Les jetons composés (anneaux, filets) sont redéclarés sur `:root, .dark`, sans quoi ils gardaient les teintes claires en sombre.
- `app/theme.py` : les 104 variables du thème qui ont une variante `_dark` dans Gradio 6.31 sont toutes définies, dans les deux modes, par des jetons. Pas d'ombre sur les contrôles, filet en sombre pour les cartes. Grille d'espacement de 4 et 8 px ; arrondis uniques (carte 12 px, contrôle 8 px, marque, pilule, rond).
- V1 : bord des ronds et cases non cochés à 3:1 au moins (`#85878e` en clair, `#73757d` en sombre), sans ombre ni liseré. Point du radio coché en `radial-gradient` sur `var(--background-fill-primary)`. La variable du thème ne suffit pas (elle n'est lue que sous `.gradio-style`, la réinitialisation de Gradio impose un SVG blanc) : une règle de `jetons.css` l'applique. Anneau de focus rendu sur `label:has(input:focus-visible)`.
- `interface.css` et `visualiseur.css` réécrits avec les seuls jetons : aucune couleur, ombre ni arrondi en dur, pas de `:root`, `body`, `svelte-*` ni `prefers-color-scheme`, aucune règle `@` autre que `@media` et `@keyframes`. Couleurs de wavesurfer et des canevas lues dans les jetons.
- Composants communs : bouton secondaire, principal et icône (32 px, SVG en `currentColor`, `app/icones.py`, triangle ▶ centré sur son centre de gravité, V4), interrupteur avec `aria-pressed` (Suivre la lecture, Énergie et seuil, Mode présentation), contrôle segmenté (Forme d'onde / Spectrogramme), deux encadrés (information, attention avec filet et icône). Tableau des locuteurs (V2) : séparateur porté par la ligne, cellules centrées verticalement.
- `app/formatage.py`, une seule fonction de formatage français (virgule, U+202F pour les milliers et devant unités et %, signe moins typographique, s/min/h, o/Ko/Mo/Go), employée par `app.py`, `temps`, `graphique`, `avancement`, `pipeline`, `sortie` ; `visualiseur.js` suit la même règle ; chiffres tabulaires.
- Contrôle automatique dans `tests/visuel/` (Node, devDependencies locales) : 20 captures de référence Playwright (clair et sombre × 1440 et 375 px, plus le mode présentation, quatre onglets, forme d'onde et valeurs variables masquées, réunion de synthèse sans donnée de corpus), axe-core en clair et en sombre, stylelint (règles de l'audit). Commandes dans `app/README.md` (B10).
- Corrigé en passant : la coche des étapes terminées ne s'affichait pas (la réécriture du CSS par Gradio perd le raccourci `border: solid var(…)`).
- Captures avant et après de V1, V2 et V4, en clair et en sombre : `docs/audit/b10-avant-apres/`.
- Tests : `tests/test_app_systeme_visuel.py` (29 : couverture des variantes sombres, valeurs du thème par jetons, jetons dans l'en-tête, jetons employés tous définis, jetons composés, règles des deux feuilles, anneau de focus, contrastes WCAG AA dans les deux modes, composants, icône, boutons d'extrait, formatage, plus de formatage à la main) ; attentes de 12 fichiers de tests mises à jour (espace fine, classes des boutons, jetons du mode présentation). Tests ciblés pendant le travail, suite complète une fois à la fin, commit enchaîné par `&&` : 577 réussis, 12 ignorés, 3 lents exclus.
Résultats : aucune expérience. stylelint sans écart (et 9 écarts sur 9 détectés dans un fichier fautif d'essai) ; axe-core sans violation dans les deux modes, après exclusion de la seule règle `target-size` sur les segments de la timeline ; 20 captures de référence (4,9 Mo), identiques d'un lancement à l'autre, tolérance de 20 pixels.
Décisions : aucune. Choix de la session, à valider :
- `launch(head=…)` plutôt que `head_paths` (même effet, sans fichier à chemin absolu).
- Bord des ronds et cases au jeton `--ws-control-line` ; champs de texte gardés au filet clair (`--ws-line`), plus discret, faute de règle WCAG qui l'impose à un champ étiqueté.
- Exclusion de `target-size` (WCAG 2.2, 2.5.8) sur les segments de la timeline, dont la largeur est la durée représentée.
- Captures d'Avancement et de Glossaire sur la hauteur de l'écran seulement (pages longues tirées des documents du dépôt : en pleine page, 10 Mo et une référence à refaire à chaque entrée de journal).
- Tolérance des captures : 20 pixels (0,2 % laissait passer l'absence de la coche des étapes).
- Signe moins typographique (U+2212) et unités en puissances de 1 000 (Ko = 1 000 octets).
- Le bouton « Mode présentation » devient un interrupteur (forme demandée par V6, contenu de l'en-tête laissé à B11).
Problèmes :
- Dépendances Node ajoutées (développement seulement, hors `pyproject.toml` et `uv.lock`) : `@playwright/test` 1.56.1, `@axe-core/playwright` 4.11.0, `stylelint` 16.25.0, dans `tests/visuel/package.json`, avec `package-lock.json`. Navigateur : le Chrome installé ; aucun navigateur téléchargé.
- L'audit annonçait le correctif du radio par la seule variable `radio_circle` (« [probable] ») : insuffisant dans Gradio 6.31 ; règle complémentaire dans `jetons.css`.
- Le correctif de la coche montre que `--update-snapshots` ne réécrit, depuis Playwright 1.50, que les captures hors tolérance : `npm run captures:maj` passe `--update-snapshots=all`.
- Restent pour B11 : tailles des exports à l'anglaise (V11, composant de Gradio), barre d'outils sur quatre lignes à 375 px (V5), en-tête (V6), « Nouvelle analyse » serré en mode présentation.
Suite : B11 (onglet Analyse), puis B12 et B13.

## 2026-11-02 — Interface : onglet Analyse, finitions (B11) et retours de B10 (Claude Code)

Objectif : retours du cockpit sur B10, puis chantier B11 (audit visuel du 02/11, §5) dans le worktree `ui` (déjà à jour avec `main`), moteur factice, sans modèle, fusion ni dépendance ajoutée.
Réalisé :
- Retours de B10 : test des exports (RTTM, JSON, étiquettes Audacity) : point décimal, tiret ASCII, aucune espace fine ; bordure des champs de saisie au jeton `--ws-control-line` (thème `input_border_color`, nom des locuteurs, liste de fusion), le fond du champ étant celui de la carte.
- V3 : identifiant sous le nom seulement après renommage.
- V5 : barre d'outils en groupes (lecture ; vue ; zoom ; aide à droite) qui reviennent à la ligne en entier ; à 375 px, deux lignes, libellés courts (nom accessible long) et zoom avec « Énergie et seuil » derrière une loupe ; une ligne en mode présentation à 1280 px.
- V6 : configuration et moteur dans un panneau « Détails » replié, composant à part de l'en-tête ; en mode présentation, titre et interrupteur seulement.
- V7 : statuts collés à leur étape, colonnes égales lues de haut en bas, liste repliée en « 7 étapes terminées en 3 s » après une analyse réussie.
- V8 : carte « Comment ça marche » seule à droite avant toute analyse ; état et résultats au lancement.
- V9 : étiquettes « SPK_A → S1 » et « SPK_E → aucun », nom complet en infobulle.
- V10 : « pas de chevauchement dans la référence ».
- V11 : exports en liste HTML, tailles en français (`formatage.taille`).
- V13 : aides repliées sous « Comment lire ce tableau », masquées en mode présentation ; dans l'Évaluation, le résultat par zone reste visible, seule la méthode est repliée.
- « Nouvelle analyse » : largeur de son libellé, aussi en mode présentation.
- Captures avant et après (Playwright, `tests/visuel/avant-apres-b11.spec.ts`) : `docs/audit/b11-avant-apres/` (13 vues, 1440 px clair, 375 px sombre, présentation). Référence sans chevauchement ajoutée à la réunion de synthèse (`preparer.py`) pour V10.
- Tests : `tests/test_app_analyse_b11.py` (9) et 2 tests ajoutés à `test_app_systeme_visuel.py` (exports, champs) ; tests de l'appariement, de la fusion et des composants mis à jour (étiquettes courtes, liste HTML des exports, loupe). Tests ciblés pendant le travail, suite complète une fois à la fin, commit enchaîné par `&&` : 588 réussis, 12 ignorés, 3 lents exclus.
Résultats : aucune expérience. Contrôle visuel : stylelint sans écart ; 20 captures de référence mises à jour pour ces changements voulus (l'en-tête change sur les quatre onglets), puis stables ; axe-core sans violation en clair et en sombre.
Décisions : aucune. Choix de la session, à valider :
- « S1 » est le rang du locuteur trouvé (ordre de première prise de parole, comme les touches 1 à 9 et les codes Audacity), et non son nom, qui peut être long ou renommé.
- À 375 px, « Énergie et seuil » est replié avec le zoom derrière la loupe (sinon trois lignes) ; libellés courts « Onde », « Spectre », « Suivre ».
- La carte « Comment ça marche » masque aussi le panneau d'état avant la première analyse ; « Nouvelle analyse » garde les résultats précédents affichés.
- Dans l'Évaluation, la phrase du DER par zone et le nombre de locuteurs restent visibles ; seule la méthode est repliée.
- Statut sous la forme « · terminé » après le libellé de l'étape.
Problèmes : à 375 px, Avancement et Glossaire restent dans le menu « … » de Gradio (limite connue, B13). Le panneau « Détails » se referme quand on change de moteur (il est redessiné).
Suite : B12 (onglet Pipeline), puis B13.

## 2026-11-02 — Interface : onglet Pipeline, schéma de gauche à droite (B12) et retours de B11 (Claude Code)

Objectif : retours du cockpit sur B11, puis chantier B12 (audit visuel du 02/11, §6) dans le worktree `ui` (à jour avec `main`), moteur factice, sans modèle, fusion ni dépendance ajoutée.
Réalisé :
- Retours de B11 : indicateur du préchauffage visible en mode présentation ; panneau « Détails » qui garde son état ouvert au changement de moteur (petit script sur le composant).
- Schéma SVG de gauche à droite, une ligne dès 840 px ; étapes en onglets (`role="tab"` dans un `role="tablist"`, flèches, Origine, Fin, `aria-selected`, `aria-controls`, tabulation itinérante) ; fiches en `tabpanel` sous le schéma.
- Anatomie d'une étape : numéro, titre, modèle et révision abrégée, aperçu de 24 px, badge d'erreurs du DER en texte, nombre de constats.
- Flèches étiquetées par la forme des données : nouvelle section `formes` du catalogue (modèles à trous renvoyant aux réglages), remplie avec la configuration effective ; un réglage absent donne l'étiquette générique et un écart signalé (baseline MFCC : dimension d'empreinte absente).
- pyannote : détection et segmentation dans un cadre « Un seul réseau : PyanNet » ; baseline : étapes séparées. Évaluation à droite, derrière un filet pointillé, « mesure seulement ».
- Barre « naissance des erreurs » : DER test sans collar de l'expérience source, empilé (motifs de la carte des erreurs), segments qui sélectionnent l'étape (manquée et fausse alarme : détection ; confusion : regroupement), mention « Attribution simplifiée ».
- Aperçus schématiques et statiques, couleurs des locuteurs pour la segmentation et le regroupement seulement (trois jetons `--ws-spk-*`).
- 375 px : liste numérotée verticale, une étape dépliée à la fois, réglages en « clé : valeur ». Mode présentation : texte agrandi, révisions masquées, barre des erreurs en tête.
- Vérifié dans le navigateur (pyannote, baseline ECAPA ; clair, sombre, 375 px, présentation ; clavier réel). Captures avant et après : `docs/audit/b12-avant-apres/` (16 vues).
- Tests : `tests/test_app_pipeline_b12.py` (13) ; tests de la page Pipeline et des constats mis à jour (onglets, nombre de constats, segments). Tests ciblés pendant le travail, puis suite complète : un premier passage a relevé un test de B11 qui attendait l'ancienne règle de l'en-tête en présentation (sans commit, enchaîné par `&&`) ; test mis à jour, second passage, commit enchaîné par `&&` : 601 réussis, 12 ignorés, 3 lents exclus.
Résultats : aucune expérience. Contrôle visuel : stylelint sans écart, axe-core sans violation en clair et en sombre, 20 captures de référence (8 mises à jour pour ces changements, une neuvième réécrite pour un pixel d'anticrénelage et rétablie).
Décisions : aucune. Choix de la session, à valider :
- Formes des données décrites dans le catalogue (`formes`), modèles à trous ; aucune valeur écrite à la main, mais les mots des étiquettes le sont, comme les autres textes du catalogue.
- Le bloc « un seul réseau » est un seul onglet ; ses deux étapes gardent leur numéro (2 et 3).
- Badge réduit aux trois composantes du DER, en mots courts ; frontières et nombre de locuteurs restent dans la fiche.
- Attribution de la barre : parole manquée et fausse alarme à la détection, confusion au regroupement.
- Aperçus entièrement schématiques (la page Pipeline ne dispose d'aucun fichier analysé).
- `npm run captures:maj` repasse en `--update-snapshots=changed` (`=all` réécrivait des captures à un pixel près).
Problèmes : le catalogue fait partie de l'empreinte du code des moteurs : le cache des résultats est invalidé une fois. Le focus au clavier d'une étape est dessiné par son contour (l'anneau d'un groupe SVG n'est pas rendu). Le panneau du navigateur intégré fait moins de 640 px de large : le schéma ne s'y voit qu'avec une taille de fenêtre émulée.
Suite : B13 (Avancement, Glossaire, passe break-ui, essai au vidéoprojecteur).

## 2026-11-02 — Outils : A-0003 sur les catégories principales d'app/sortie.py (Claude Code)

Objectif : reprendre dans A-0003 les décisions du cockpit du 02/11 sur les catégories d'erreur (catégorie principale exclusive, puis option b), sans seconde définition, dans le worktree `outils`, sans modèle chargé, fusion vers `main` ni dépendance ajoutée, sous `nice` (piste A en calcul).
Réalisé :
- Fusion d'`origin/ui` (`a5129ff`) dans `outils` (`a9d5d7a`) : catégories d'erreur dans `app/sortie.py` (`ERROR_CATEGORIES`, `main_category`, `error_map` qui découpe aux bords de la tolérance de ±0,25 s) et système visuel de B10. Conflit de `docs/journal.md` résolu en gardant toutes les entrées.
- `scripts/rendu.py` (`42e1e22`) : les teintes des figures autonomes sont lues dans `app/static/jetons.css`, où B10 les a déplacées ; les règles `.av-chart` restent lues dans `interface.css`. Sans ce correctif, `test_figures_autonomes_comme_l_onglet_avancement` échouait après la fusion.
- `analyses/A-0003_cas-echec/config.yaml` (`9160412`), toujours sans exécution : section 4 réécrite (définition d'`app/sortie.py`, aucune catégorie déclarée dans la configuration), `extraits.categories_exclues: [frontiere]`, grille remplie `grille_ecoute.csv` dans le dossier de l'analyse.
- `scripts/analyses/a0003_cas_echec.py` (`f0946b4`) : secondes par catégorie principale lues dans `errors["categories"]` de la carte (somme égale à l'erreur sans collar) ; parts sur toute l'erreur (100 %) et hors décalage de frontière ; contrôle par fichier, par système et corpus et par type : décalage de frontière contre erreur pardonnée par le collar (per_file, sans collar moins avec collar), écart résiduel rapporté dans les CSV et dans `execution.json` (`controle_frontiere_collar_s`) ; extraits choisis par catégorie principale (part dans la tolérance répartie uniformément sur la zone pour la recherche des fenêtres, heuristique de sélection seulement) ; page et grille vide `grille_ecoute.csv` ; `--importer-grille` verse la grille remplie dans le dossier d'une analyse exécutée après contrôle (colonnes, mêmes extraits et fichiers audio que `extraits.csv`, causes cochées par « x », corpus maison refusé, grille déjà versée jamais remplacée). Grille du corpus maison : dans `data/processed/a0003/ecoute_maison/`, avec la mention « jamais versionnée ».
- `tests/test_a0003_cas_echec.py` : 18 tests (catégories lues dans l'application, « trouvé en trop » et « référence non appariée » sur un cas construit, contrôle exact du collar, parts à 100 % sur toute l'erreur et hors frontière, UEM officiel, fenêtres et exclusion de « frontière », exécution complète, extraits publics et locaux, grille versée et 5 cas de refus).
- Essai hors du dépôt (`--sortie data/processed/a0003/essai`, commit `f0946b4`, arbre propre) sur EXP-0001, 0007, 0010 et 0012, lecture de RTTM seulement, sous `nice -n 19`, 2 min 14 s ; page d'écoute relue dans le navigateur.
Résultats : essai, non versionné.
- Répartition de l'erreur sans collar par catégorie principale (frontière / chevauchement / référence non appariée / trouvé en trop / tour court / pause / autre, en %) : pyannote AMI 51,9 / 22,2 / 0,3 / 0,6 / 0,0 / 1,1 / 23,9 ; pyannote SUMM-RE 67,5 / 12,0 / 0,8 / 0,2 / 0,0 / 4,4 / 15,2 ; ECAPA AMI 32,6 / 18,9 / 3,6 / 2,8 / 0,0 / 0,2 / 42,0 ; ECAPA SUMM-RE 55,0 / 17,8 / 4,3 / 0,7 / 0,0 / 0,7 / 21,5.
- Hors décalage de frontière (chevauchement / référence non appariée / trouvé en trop / tour court / pause / autre, en %) : pyannote AMI 46,2 / 0,6 / 1,2 / 0,0 / 2,3 / 49,7 ; pyannote SUMM-RE 36,9 / 2,5 / 0,6 / 0,0 / 13,5 / 46,6 ; ECAPA AMI 28,0 / 5,3 / 4,1 / 0,0 / 0,2 / 62,4 ; ECAPA SUMM-RE 39,5 / 9,5 / 1,5 / 0,0 / 1,7 / 47,8.
- Contrôle du collar : écart nul pour pyannote (AMI 6 229,2 s, SUMM-RE 14 121,4 s) et ECAPA AMI (9 063,6 s) ; ECAPA SUMM-RE 14 157,5 s contre 14 158,8 s pardonnées (−1,2 s), toutes sur la confusion de 102c_EBPH. Totaux de la carte égaux aux composantes des per_file (écart nul).
- 8 extraits : chevauchement, référence non appariée, trouvé en trop, pause, autre, puis 3 pires fichiers (aucun extrait « tour court ») ; 4 par système ; 5 AMI, 3 SUMM-RE.
Décisions : aucune. Choix de la session, à valider : « frontière » exclue des extraits d'écoute (ce que le collar pardonne n'est pas un cas d'échec à écouter) ; répartition uniforme de la part dans la tolérance pour choisir les fenêtres.
Problèmes :
- « Tour court » vaut 0 partout, par construction : un tour de moins de 0,5 s tient entier dans la tolérance de ses propres frontières, donc aucune partie hors tolérance ne le recoupe (docstring de `main_category`). La catégorie est vide dans A-0003 comme dans la carte.
- L'écart résiduel de 102c_EBPH vient sans doute d'un appariement différent avec collar (le DER le recalcule) [probable, non vérifié].
- `docs/rendu/` n'a pas été régénéré après le correctif de `rendu.py` : les figures versionnées gardent les teintes d'avant B10.
- EXP-0020 (piste A) tournait : tests, suite complète et essai sous `nice -n 19`. La suite complète a été lancée deux fois : la première a révélé l'échec de `test_rendu.py`, la seconde a validé le correctif.
Résultats des tests : 18 ciblés pour A-0003, 19 pour le rendu ; suite complète sans lents ni `modele` : 612 réussis, 12 ignorés, 7 désélectionnés.
Suite : exécution officielle depuis `main`, après A3 et A6 et la fusion d'`outils` ; après l'écoute, `uv run python scripts/analyses/a0003_cas_echec.py --config analyses/A-0003_cas-echec/config.yaml --importer-grille <grille_ecoute.csv>`.

## 2026-11-02 — Outils : tour court à 1 s, croisement catégorie × type, écart de 102c_EBPH (Claude Code)

Objectif : appliquer l'amendement du 02/11 de D28 et le retour du cockpit sur l'adaptation d'A-0003, dans le worktree `outils`, sans modèle chargé, fusion vers `main` ni dépendance ajoutée, sous `nice` (piste A en calcul).
Réalisé :
- `app/sortie.py` (`5738a65`, à fusionner par la session B) : `SHORT_TURN_S` porté à 1 s ; docstring de `main_category` mise à jour (hors tolérance, « tour court » ne s'applique qu'aux tours de 0,5 à 1 s). Aucun autre fichier d'`app/` modifié. Tests : `tests/test_app_categories.py` (toutes les catégories atteintes, « tour court » compris, sur les paires aléatoires ; nouveau cas d'un tour de 0,8 s : 0,3 s en « tour court », 0,5 s en « frontière » ; un tour de 1 s exactement n'est pas court) et `tests/test_app_appariement.py` (constat affiché « moins de 1,0 s »).
- A-0003 (`2acb93b`, `3cbd071`) : `categories_par_type.csv`, une ligne par système × corpus × catégorie × type d'erreur : secondes, part de toute l'erreur, part de l'erreur hors décalage de frontière, part de l'erreur du type. Configuration mise à jour avant exécution (seuil, croisement, nouveau fichier de résultats). Tests : croisement (cellules égales aux secondes de la carte, sommes à 100 % sur toute l'erreur, hors frontière et par type) et exécution complète.
- Écart de −1,213 s (ECAPA, SUMM-RE, 102c_EBPH) vérifié : avec le collar, le DER apparie le locuteur trouvé SPK_01 à 222 au lieu de 217 (cooccurrence 62,27 s contre 61,06 s avec collar ; 142,55 s contre 156,00 s sans collar) ; SPK_00 → 024 et SPK_02 → 021 restent inchangés. Avec l'appariement sans collar imposé, la confusion avec collar serait de 80,411 s au lieu de 79,198 s : la différence fait 1,213 s, et le décalage de frontière égale alors exactement l'erreur pardonnée. Cause consignée : changement d'appariement par le collar, pas une erreur de découpage. Test ajouté (sauté sans les données).
- Essai hors du dépôt (`--sortie data/processed/a0003/essai`, commit `3cbd071`, arbre propre) sur EXP-0001, 0007, 0010 et 0012, lecture de RTTM seulement, sous `nice -n 19`, 2 min 13 s.
Résultats : essai, non versionné. Secondes d'erreur sans collar par catégorie (lignes) et type (parole manquée / fausse alarme / confusion), part de toute l'erreur entre parenthèses :
- pyannote AMI (12 001 s) : frontière 2 784 (23,2 %) / 1 678 (14,0 %) / 1 767 (14,7 %) ; chevauchement 1 896 (15,8 %) / 0 / 772 (6,4 %) ; référence non appariée 9 / 0 / 25 ; trouvé en trop 0 / 33 / 36 ; tour court 17 / 8 / 34 ; pause 0 / 131 (1,1 %) / 0 ; autre 1 278 (10,7 %) / 855 (7,1 %) / 678 (5,7 %).
- pyannote SUMM-RE (20 933 s) : frontière 3 184 (15,2 %) / 7 453 (35,6 %) / 3 484 (16,6 %) ; chevauchement 1 514 (7,2 %) / 0 / 996 (4,8 %) ; référence non appariée 3 / 0 / 166 (0,8 %) ; trouvé en trop 0 / 32 / 6 ; tour court 12 / 45 / 86 (0,4 %) ; pause 0 / 915 (4,4 %) / 0 ; autre 237 (1,1 %) / 1 713 (8,2 %) / 1 087 (5,2 %).
- ECAPA AMI (27 772 s) : frontière 6 625 (23,9 %) / 623 (2,2 %) / 1 816 (6,5 %) ; chevauchement 4 648 (16,7 %) / 0 / 590 (2,1 %) ; référence non appariée 238 (0,9 %) / 0 / 747 (2,7 %) ; trouvé en trop 0 / 516 (1,9 %) / 258 (0,9 %) ; tour court 33 / 0 / 34 ; pause 0 / 44 / 0 ; autre 7 891 (28,4 %) / 1 813 (6,5 %) / 1 895 (6,8 %).
- ECAPA SUMM-RE (25 755 s) : frontière 8 903 (34,6 %) / 1 697 (6,6 %) / 3 557 (13,8 %) ; chevauchement 4 164 (16,2 %) / 0 / 417 (1,6 %) ; référence non appariée 80 (0,3 %) / 0 / 1 024 (4,0 %) ; trouvé en trop 0 / 89 (0,3 %) / 85 (0,3 %) ; tour court 38 / 0 / 123 (0,5 %) ; pause 0 / 191 (0,7 %) / 0 ; autre 2 734 (10,6 %) / 958 (3,7 %) / 1 693 (6,6 %).
- Part de « autre » dans l'erreur hors décalage de frontière, par type (manquée / fausse alarme / confusion) : pyannote AMI 22,2 / 14,8 / 11,8 % ; pyannote SUMM-RE 3,5 / 25,2 / 16,0 % ; ECAPA AMI 42,2 / 9,7 / 10,1 % ; ECAPA SUMM-RE 23,6 / 8,3 / 14,6 %.
- Contrôles : totaux de la carte égaux aux per_file (écart nul) ; décalage de frontière égal à l'erreur pardonnée, sauf ECAPA SUMM-RE (−1,213 s, 102c_EBPH, expliqué ci-dessus).
- 8 extraits : chevauchement, référence non appariée, trouvé en trop, tour court (pyannote, 025b_EBDH), pause, autre, puis 2 pires fichiers ; 4 par système ; 4 AMI, 4 SUMM-RE.
Décisions : aucune.
Problèmes :
- La carte affiche « moins de 1,0 s » : `app/app.py` formate le seuil avec une décimale ; non modifié ici (fichier de la session B).
- Suite complète, sans lents ni `modele` : 615 réussis, 12 ignorés, 7 désélectionnés.
Suite : fusion de `5738a65` par la session B ; exécution officielle d'A-0003 depuis `main` après A3 et A6.

## 2026-11-02 — Interface : correction de B12, fusion d'outils, B13 (Avancement, Glossaire, passe break-ui) (Claude Code)

Objectif : retour du cockpit sur B12 (confusion rattachée aux empreintes et au regroupement), fusion d'`origin/outils` (tour court à 1 s), puis chantier B13 de l'audit visuel du 02/11 (§7), dans le worktree `ui`, moteur factice, sans modèle chargé, fusion vers `main` ni dépendance ajoutée.
Réalisé :
- Correction de B12 : dans la barre de la naissance des erreurs, la confusion sélectionne « Empreintes » (« Représentation » pour la baseline) et met « Regroupement » en évidence par un contour pointillé (`data-also`, classe `pl-also`) ; légende « → Empreintes vocales et regroupement » ; légende de la barre complétée (constat C05).
- Fusion d'`origin/outils` (`8e5f267`) : `SHORT_TURN_S` à 1 s, A-0003, rendu ; conflit de `docs/journal.md` résolu en gardant les entrées des deux côtés.
- B13, onglets Avancement et Glossaire au système de B10 : petit bouton `ws-btn-sm` (jeton `--ws-control-h-sm`), étiquette de confiance commune `ws-conf` (constats et glossaire, où « [probable] » devient une étiquette), aides repliées et masquées en présentation (« Comment lire ces constats », « Comment lire ce tableau », « À propos de ce glossaire »), replis `ws-fold` (valeurs du graphique, décisions de cadrage), dates en JJ/MM/AAAA (`formatage.date`, aussi dans Pipeline), corpus et nombre de locuteurs en clair, tableaux empilés en fiches à 375 px (`data-label`), chemins des fiches et sources des termes masqués en présentation, filet du glossaire sans arrondi.
- À 375 px, les quatre onglets tiennent sans le menu « … » : Gradio mesure une copie masquée de la barre (boutons sans rôle « tab »), que l'ancienne règle ne touchait pas ; la règle vise maintenant les deux copies.
- Passe break-ui sur les quatre onglets (fichiers de `tests/fabrique.py`, copies dans le dossier temporaire de la session, supprimables) : 12 locuteurs aux noms longs, 0 locuteur, 90 min, référence plus courte, comparaison de deux moteurs ; 1440, 1280 × 720 et 375 px, clair, sombre, présentation. Aucun débordement ni erreur de console. Corrigé : noms des pistes coupés au milieu (douze « Marie-Hélène … » indiscernables), champ du nom élargi, noms de la matrice limités à deux lignes, casse du titre en comparaison, « moins de 1 s » pour le tour court (signalé par la session E).
- Vérification à 1280 × 720 et 1920 × 1080, clair et sombre, sur les quatre onglets ; captures avant et après dans `docs/audit/b13-avant-apres/`.
- Contrôle visuel : stylelint, 20 captures de référence mises à jour pour ces seuls changements (chaque différence comparée à l'ancienne image), axe-core en clair et en sombre : au vert. Tests : `tests/test_app_b13.py` (12) ; tests de B12, des constats et de l'appariement mis à jour.
Résultats : aucune expérience.
Décisions : aucune. Choix de la session, à valider : dates en JJ/MM/AAAA ; tableaux d'Avancement empilés en fiches à 375 px (page plus longue, 18 700 px contre 9 200, mais plus de défilement horizontal) ; aides repliées et masquées en présentation ; sources des termes et chemins des fiches masqués en présentation ; coupe des noms de pistes au dernier mot court ou aux six derniers caractères ; onglets à 13 px sous 640 px.
Problèmes :
- Sous environ 340 px de large, le menu « … » de Gradio revient (quatre onglets à 13 px demandent 306 px).
- À 375 px, l'onglet Avancement reste long (21 expériences en fiches) ; options pour le cockpit : replier la frise au-delà des cinq dernières expériences, ou garder le tableau défilant à 375 px.
- Les captures pleine page de plus de 16 384 px répètent le haut de la page (limite de Chrome) : la passe break-ui à 375 px capture par vues successives.
- L'essai au vidéoprojecteur par la candidate reste à faire.
- Règle 11 enfreinte une fois : le premier commit a été enchaîné à la suite complète filtrée par `| tail` (le `&&` testait alors le filtre, pas pytest). Suite réussie (655 réussis, 12 ignorés, 3 désélectionnés) ; commit refait, journal compris, derrière `uv run pytest && git commit` sans filtre.
Suite : retour du cockpit sur B13 ; essai au vidéoprojecteur ; fusion d'`ui` dans `main` selon le planning.

## 2026-11-02 — Fin des chantiers B et E du 02/11 (cockpit)

Constats : l'essai d'A-0003 (hors dépôt) croise catégorie et type d'erreur. Pour pyannote sur SUMM-RE, la fausse alarme vient d'abord de frontières étirées (35,6 % de l'erreur, pardonnées par le collar), puis de « autre » (8,2 %) et de pauses courtes (4,4 %). C'est la cible de V2 (Silero). Pour la baseline ECAPA sur AMI, la parole manquée hors chevauchement et hors frontières pèse 28,4 % : des tours entiers manqués par la détection d'énergie, cohérent avec C01. L'écart de −1,213 s (102c_EBPH) est expliqué : avec collar, le DER recalcule l'appariement, qui bascule pour un locuteur (pyannote.metrics). Ce n'est pas un défaut du découpage. Pas de nouveau constat avant l'exécution officielle.
Décisions : aucune. Sessions B et E en pause ; leurs branches seront fusionnées dans main par la piste A à sa première pause.

## 2026-11-02 — README à jour pour la nuit (cockpit)

Réalisé : options de l'application (`--presentation`, `--config-demo`), spectrogramme et énergie, catégories d'erreur, nouveau schéma du pipeline, contrôles visuels automatiques, état d'avancement (D28, audit visuel, A-0002 et A-0003 prêtes, robustesse en cours, interface B1 à B13, outillage), `docs/rendu/` dans la documentation. Ces fonctions décrivent l'état de `main` après la fusion d'`ui` et d'`outils` prévue cette nuit.

## 2026-11-03 — Piste A : reprise d'A3, fusions, A3, A-0002, A6, A-0003 (Claude Code)

Objectif : reprendre A3 après la pause volontaire du 02/11, faire les tâches de la première pause (documents, règles 11 et 12, fusion d'`ui` et d'`outils`, contrôles, application réelle, rendu), puis A3, A-0002, A6 sur SUMM-RE et AMI, et A-0003.
Réalisé :
- Reprise d'EXP-0020 : le processus suspendu à 15:02 (186/259) était intact, mais l'ancien code ne pouvait pas marquer les temps comme interrompus dans `execution_*.json`, et une reprise par un nouveau code aurait mêlé deux commits et des mesures reconstituées depuis run.log : reprise jugée non sûre, expérience relancée entièrement le 02/11 à 20:15. Tentative interrompue arrêtée, son journal gardé dans `run_interrompu.log`, ses RTTM archivés hors du dépôt ; les 372 RTTM (186 fichiers, deux sorties) sont identiques à l'octet à ceux de la relance. Calculs lancés sous `caffeinate -i`.
- Pause : commits `docs:` (D28, audit visuel, planning v2.1, journal, README, CLAUDE.md : règle 12 et précision `pipefail` de la règle 11). Fusion d'`ui` (B8 à B13, qui contenait déjà `outils`, E7 et E8 : la fusion d'`outils` était sans objet) ; journal fusionné en gardant toutes les entrées (86). `uv sync` ; suite complète, lents et `modele` compris : 670 réussis. Contrôles visuels (`npm ci`, puis `npm run controle`) : stylelint et axe réussis ; 5 captures de l'onglet Avancement diffèrent de 82 à 172 pixels, uniquement sur la ligne des compteurs (expériences et en-têtes manquants du dépôt principal : EXP-0020, EXP-0021 et A-0002 sans notes.md à ce moment) ; références non mises à jour. A-0002 : `ic_min_fichiers` appliqué (pas d'IC sous 5 réunions), 1 test. `docs/rendu/` régénéré.
- Application, moteurs réels, sous hook d'audit et `lsof` (port 7870) : « Moteurs prêts » ; extrait de 3 min de 007a_ECRH et sa référence : pyannote 11,63 % sans collar (comme le 02/11) ; spectrogramme mel affiché, aligné sur la timeline ; carte des erreurs avec catégorie principale (Chevauchement, Pause courte) et part pardonnée par le collar ; baseline ECAPA 20,84 %, « Énergie et seuil » lu dans la trace du moteur (seuil −54,9 dB) ; onglet Pipeline complet. Réseau : seulement `127.0.0.1:7870` et le `bind` local de `::1`.
- A3 : EXP-0020 (pyannote, MPS, 4 h 20) et EXP-0021 (baseline ECAPA, CPU, 1 h 21), évaluées. A-0002 exécutée (`7bec667`).
- A6 : probabilités de Silero sur SUMM-RE dev sous hook d'audit (36 fichiers, environ 4 s pour 20 min d'audio ; aucun événement réseau) ; réglage (`results/reglage_silero/2026-11-03_02h17/`) ; exécutions partagées EXP-0023 (porteuse) et EXP-0022 sur SUMM-RE, EXP-0025 (porteuse) et EXP-0024 sur AMI, avec mesure CPU, évaluées.
- A-0003 : systèmes complétés (conditions de D24 d'EXP-0020 et EXP-0021 ; V2 d'EXP-0022 et EXP-0024) ; exécution officielle depuis `main` (`da05fc8`, arbre propre) ; dossier d'écoute `data/processed/a0003/ecoute/` (8 extraits, `index.html`, `grille_ecoute.csv`).
Résultats :
- EXP-0020, DER sans collar sur test (propre : 26,30 %) : rev04 28,78, rev08 41,24, bru15 26,83, bru05 30,15, cod16 25,51, cod08 30,24, salle 41,23 %. EXP-0021 (propre : 33,42 %) : 35,45, 40,81, 39,13, 47,38, 32,71, 38,43, 49,21 %.
- A-0002, écart à propre (bootstrap apparié, toutes réunions) : pyannote rev04 +2,49 [+0,77 ; +4,36], rev08 +14,94 [+11,25 ; +18,47], bru15 +0,53 [+0,25 ; +0,87], bru05 +3,85 [+1,97 ; +6,02], cod16 −0,79 [−1,57 ; +0,27], cod08 +3,94 [+0,63 ; +7,47], salle +14,93 [+11,45 ; +18,76] ; ECAPA rev04 +2,04, rev08 +7,39, bru15 +5,72, bru05 +13,96, cod16 −0,71, cod08 +5,01, salle +15,79 (IC dans `resultats.csv`). pyannote − ECAPA à condition égale : de −17,23 (bru05) à −6,67 (rev04), sauf rev08 +0,44 [−2,83 ; +3,64]. Zoom (3 réunions, écart seul) et autres dans `resultats.csv`. RT60 en T20 : médianes 0,404, 0,903, 0,659 s ; T60 en annexe : 0,534, 1,177, 0,861 s.
- Réglage de Silero : seuil 0,8, silence minimal 0,0 s, marge 0,03 s ; V2 sur dev 21,35 % sans collar (EXP-0007 : 26,00), 9,60 % avec collar (contrainte 10,76) ; point encore au bord après l'élargissement unique (seuil haut, silence bas), signalé.
- V2, règles de D25 : (1) SUMM-RE test −2,60 [−3,71 ; −1,64] sans collar (EXP-0022 : 23,70 %), 30 fichiers améliorés sur 37 ; (2) avec collar +0,29 [−0,50 ; +0,97], non significatif ; (3) AMI test +22,13 [+16,90 ; +27,12] (EXP-0024 : 42,05 %), 16 fichiers dégradés sur 16, parole manquée 37,76 contre 11,16. V2 ne passe pas la règle 3 : D24 pour V2 non lancé. V3 : SUMM-RE test −2,49 [−3,62 ; −1,55] face à EXP-0016 (27,90 % contre 30,40), AMI test +21,51 [+16,44 ; +26,56] face à EXP-0017.
- A-0003 : totaux concordants pour les 20 couples système × corpus ; contrôle « décalage de frontière = erreur pardonnée par le collar » exact sauf baseline ECAPA sur SUMM-RE (−1,21 s), rev08 (−14,06), cod16 (−4,63), cod08 (−3,48), salle (−0,90) et pyannote cod08 (−1,72), consignés tels quels. Extraits : chevauchement, locuteur de référence non apparié, locuteur trouvé en trop (baseline ECAPA, AMI), tour court et pause (pyannote, SUMM-RE), autre (pyannote, AMI), pires fichiers TS3003a (V2, AMI, 70,86 %) et 080b_EBDH (pyannote, SUMM-RE, 66,01 %).
Décisions : aucune.
Problèmes :
- `charge_concurrente` vraie pour toutes les exécutions de la nuit sauf la partie MPS d'EXP-0025 (charge sur 1 min jusqu'à 10,17 pour 6 cœurs) ; une application en mode factice (`app.app --factice`, port 7860, lancée hors de cette session) est restée ouverte, à environ 5 % de CPU.
- Le worktree `ui` contient des modifications non commitées (`app/app.py`, `app/avancement.py`, `app/static/interface.css`, etc.) : non fusionnées, laissées en place.
- `scripts/reglage_silero.py` a une option cachée (`--racine`, `argparse.SUPPRESS`), contraire à la règle « pas d'option cachée » (D18).
Suite : interprétation au cockpit (A3, A-0002, A6, A-0003) ; écoute des 8 extraits d'A-0003 par la candidate ; puis A4 (Nemotron 3) et A5 (DiariZen).

## 2026-11-03 — Interprétation d'A3, A6 et A-0003 (cockpit)

Objectif : interpréter la robustesse (D24), les variantes V2 et V3 de D25, et les cas d'échec.
Réalisé : interprétations et verdicts d'EXP-0020 à 0025 ; `notes.md` d'A-0002 et d'A-0003 ; constats C13 à C17 ; synthèse ; amendement du 03/11 de D25 (bilan).
Résultats : la réverbération forte est la faiblesse de pyannote (+14,9 points en rev08, surtout de la parole manquée ; avance sur la baseline perdue en rev08) ; le bruit est celle de la baseline ; un codec à bas débit dégrade l'attribution des deux. V2 gagne 2,6 points en français mais en perd 22 sur AMI (Silero coupe la parole lointaine). Le chevauchement est le premier facteur d'échec identifiable.
Décisions : V2 et V3 écartées, aucune variante de D25 retenue ; point de réglage au bord de la grille laissé tel quel (un seuil plus haut ne pourrait qu'aggraver AMI) ; A4 (Nemotron 3) lancé maintenant. L'option `--racine` de `scripts/reglage_silero.py` devient une option documentée et consignée dans la sortie, au lieu d'être cachée (traçabilité, D18).
