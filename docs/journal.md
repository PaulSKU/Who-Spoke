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
