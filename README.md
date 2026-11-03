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

Puis ouvrir http://127.0.0.1:7860 dans un navigateur. Le serveur est local : aucun lien public, aucune connexion vers l'extérieur. Les modèles sont lus dans le cache local, et la télémétrie des bibliothèques est coupée (D27). Il faut avoir lancé `scripts/prefetch_models.py` une fois auparavant. Au démarrage, les moteurs sont préchauffés (« Moteurs prêts » dans l'en-tête). Options : `--presentation` pour un vidéoprojecteur ou un écran partagé (texte agrandi, réglages secondaires masqués ; aussi par un interrupteur dans l'en-tête) ; `--port` ; `--depot` pour lire les expériences d'un autre dossier du dépôt ; `--config-demo` pour essayer une configuration de démonstration (par défaut `configs/demo.yaml`, écrit au gel du 10/11 ; modèle : `configs/demo.exemple.yaml`) ; `--sans-prechauffage` ; `--vider-cache` pour effacer les résultats gardés dans `~/.cache/whospoke/`. Fonctionne en clair et en sombre, de 375 px à 1920 px de large.

| Onglet | Rôle |
|---|---|
| Analyse | Dépôt d'un fichier audio ou vidéo de tout format ; choix du moteur (pyannote community-1, baseline MFCC, ECAPA ou WeSpeaker), du nombre de locuteurs (automatique, imposé ou fourchette) et du périphérique ; durée annoncée en fourchette, avancement par étape ; forme d'onde ou spectrogramme mel (celui dont la baseline tire ses MFCC), vue d'ensemble et timeline des locuteurs en pleine largeur ; pour la baseline, courbe d'énergie et seuil de sa détection de parole ; lecture suivie, zoom, raccourcis clavier (« ? » pour l'aide), extrait typique de chaque locuteur ; statistiques, indicateurs d'interaction (monologues, latence de réponse, « qui suit qui »), renommage et fusion de locuteurs ; exports RTTM, JSON (avec fiche de reproductibilité), étiquettes Audacity et image de la timeline. Avec une référence RTTM : DER décomposé dans les deux conditions de collar, appariement des locuteurs, carte des erreurs et « Expliquer cette erreur » (catégorie de chaque erreur : décalage de frontière pardonné par le collar, chevauchement, locuteur non apparié ou en trop, tour court, pause courte). Option de comparaison de deux moteurs sur le même fichier ; réaffichage facultatif d'un résultat déjà calculé |
| Pipeline | Schéma du pipeline de chaque moteur, de gauche à droite (liste numérotée sur mobile) : forme des données entre les étapes, « un seul réseau » pour la segmentation de pyannote, étape où naît chaque type d'erreur ; pour chaque étape, réglages effectifs, en lecture seule, et constats mesurés ; tout est généré depuis les expériences et le catalogue |
| Avancement | Ce que nous avons appris, graphique des erreurs par système et par corpus, expériences et verdicts, décomposition de l'erreur par les oracles, décisions et file d'attente, synthèse ; tout est généré depuis le dépôt |
| Glossaire | Vocabulaire du projet, lié depuis les autres onglets |

Pour une réunion de 30 min, l'analyse prend environ 1 min 30 s avec pyannote en MPS, et moins d'une minute avec les baselines en CPU. Détails techniques, vérifications hors ligne et limites connues : `app/README.md`. Des contrôles automatiques protègent l'affichage : captures de référence (Playwright), accessibilité (axe-core, WCAG AA) et règles CSS (stylelint), dans `tests/visuel/`.

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
| `docs/synthese.md`, `docs/constats.yaml` | Synthèse vivante du projet et constats chiffrés rattachés aux étapes du pipeline |
| `docs/audit/` | Audit du projet (01/11) et audit visuel (02/11), avec captures avant et après |
| `docs/rendu/` | Tableaux comparatifs, ablations, robustesse, temps et figures, générés par `scripts/rendu.py` depuis les résultats |
| `docs/recherche/` | Recherche documentaire (corpus, veille sur les modèles) |
| `docs/maquettes/` | Maquettes de l'interface |
| `app/README.md` | Application de démonstration : fonctionnement, vérifications, limites |
| [`docs/installation.md`](docs/installation.md) | Installation pas à pas, durées mesurées, problèmes connus, vérification sur machine vierge |
| [`docs/licences.md`](docs/licences.md) | Licences des modèles, des fichiers de tiers, des dépendances et des corpus |
| `docs/corpus-maison/guide-annotation.md` | Pas-à-pas de la chaîne du corpus maison (synchronisation, pré-annotation, annotation, contrôle) |
| `experiments/`, `analyses/` | Expériences et analyses a posteriori, avec leur interprétation (`notes.md`) |
| `docs/journal.md` | Journal de bord |
| `results/leaderboard.csv` | Une ligne par expérience et par jeu évalué |
| `results/reglage_silero/` | Réglage de Silero VAD sur SUMM-RE dev (D25), produit par `scripts/reglage_silero.py` (options dans `--help`, dont `--racine` : racine du dépôt lu, consignée dans la sortie) |
| [`docs/rendu/`](docs/rendu/README.md) | Tableaux et figures du rendu, générés par `scripts/rendu.py` (systèmes, oracles, robustesse, temps) |

## État d'avancement

Au 4 novembre 2026.

| Chantier | État |
|---|---|
| Cadrage, méthode, protocole d'évaluation | Fait (D1 à D29) ; audit du projet le 01/11, audit visuel le 02/11, avis du tuteur le 03/11 (priorité au corpus maison, plus de polissage de l'interface) |
| Chaîne d'évaluation (DER, JER, chevauchement, nombre de locuteurs, bootstrap) | Faite, testée |
| Corpus AMI, micro de salle (dev et test) | Préparé |
| pyannote community-1 | Intégré ; résultat publié reproduit sur AMI (EXP-0001) ; modèle figé à une révision (D18) |
| Baseline classique (énergie, MFCC, regroupement) | Faite (EXP-0002, EXP-0009) |
| Diagnostics oracles (détection, nombre de locuteurs) | Faits (EXP-0003 à EXP-0006) |
| Empreintes neuronales (D8, D22) | Faites (EXP-0010 à EXP-0015) : ECAPA retenue pour la baseline ; la parole manquée par la détection d'énergie devient l'erreur principale |
| Analyses a posteriori | Faites : A-0001 (sensibilité de la référence de SUMM-RE), A-0002 (robustesse par condition et sous-groupe), A-0003 (cas d'échec : le chevauchement est le premier facteur d'échec identifiable), A-0004 (niveau d'entrée : corrélé à la parole manquée de Nemotron 3 sur AMI, mais pas en cause) |
| Moteurs supplémentaires (D23) | Nemotron 3 Diarization évalué (EXP-0026 à 0035) : bien meilleur que pyannote en français et sous dégradation, moins bon sur AMI (parole manquée deux fois plus forte, cause non identifiée) ; seuil de décision réglé à 0,35 ; intégré à l'application. DiariZen écarté (RTF de 2,1 en CPU, échec en MPS). NeMo Sortformer v2, Voxtral et Nemotron 3.5 non évalués |
| Amélioration n° 2 : fausse alarme de pyannote (D25) | Aucune variante retenue : sortie exclusive (+4,1 points sur SUMM-RE, +4,6 sur AMI) et post-traitement par Silero VAD (−2,6 en français, mais +22,1 sur AMI, où il coupe la parole lointaine) écartés |
| Nombre de locuteurs borné entre 2 et 6 | Effet non significatif (EXP-0018, EXP-0019) ; gardé comme garde-fou pour la démonstration |
| Robustesse (D24) | Faite (EXP-0020, 0021, 0028, 0035) : la réverbération forte est la faiblesse de pyannote (+14,9 points), le bruit celle de la baseline ; Nemotron 3 reste entre 14,8 et 18,5 % dans toutes les conditions. La simulation ne reproduit pas tout un vrai micro de salle (classements opposés sur AMI) |
| SUMM-RE (validation en français) | Préparé (dev 36, test 37 réunions) ; pyannote, oracle et baselines MFCC, ECAPA et WeSpeaker évalués (EXP-0007 à EXP-0009, EXP-0012, EXP-0015) |
| Corpus maison (réunions en français) | Priorité absolue depuis le 03/11. Premier enregistrement fait (M01 : 9 min, 3 locuteurs, habitacle de voiture), annotation manuelle en cours ; d'autres enregistrements d'ici au 8/11. Il décidera du moteur de démonstration, pyannote ou Nemotron 3 (D29) |
| Interface de démonstration (D17, D26, D28) | Faite : chantiers B1 à B14 (système visuel unique, spectrogramme, schéma du pipeline, cas limites, mode présentation, sélecteur de thème), Nemotron 3 intégré ; cible : ordinateur et vidéoprojecteur ; fonctionnement hors ligne vérifié (D27). Polissage arrêté ; reste l'essai au vidéoprojecteur |
| Outillage | Commande en ligne, intégration continue, licence, vérification d'installation sur machine vierge, chaîne d'annotation du corpus maison, campagne de temps, génération des tableaux et figures du rendu (`docs/rendu/`) |

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
| EXP-0033 — Nemotron 3 Diarization (seuil 0,35) | SUMM-RE, français | 14,3 % | 11,1 % | 13,9 % | 32/37 | ≈ 20 s (CPU) |
| EXP-0034 — Nemotron 3 Diarization (seuil 0,35) | AMI, micro de salle | 26,4 % | 24,1 % | 28,5 % | 14/16 | ≈ 19 s (CPU) |

Les chiffres sur AMI sont optimistes pour pyannote, qui a vu ce corpus à l'entraînement (`docs/corpus.md` §9). SUMM-RE est en français, mais il est enregistré en micros-casques, pas en micro de salle. Sur SUMM-RE, le DER sans collar dépend fortement de la convention de découpage de la référence (jusqu'à 8 points pour pyannote), alors que le DER avec collar n'en dépend presque pas (analyse A-0001) : les deux sont toujours rapportés. WeSpeaker est le modèle d'empreintes de pyannote : l'écart entre EXP-0013 et EXP-0001 (29 points sur AMI, dont 21 de parole manquée) mesure ce que pyannote doit à sa segmentation neuronale et à son regroupement, et non à ses empreintes. Nemotron 3 fait presque deux fois mieux que pyannote en français, mais moins bien sur AMI, où il manque deux fois plus de parole ; le corpus maison tranchera (D29). Les temps sont ceux des expériences ; des temps de référence, machine au repos, seront mesurés le 12/11 (D21). Les expériences et leur interprétation sont dans `experiments/` et `results/leaderboard.csv`.

## Licence

Code et documentation sous licence MIT (`LICENSE`). Les modèles, fichiers de tiers et corpus gardent leur licence : voir [`docs/licences.md`](docs/licences.md). L'intégration continue (`.github/workflows/tests.yml`) lance la suite rapide à chaque envoi, sous Linux, avec torch en CPU, sans modèle ni jeton.
