# D17 — Interface : application de démonstration et page Pipeline

Statut : actée (périmètre) ; détails d'écran à affiner au premier prototype
Date : 2026-10-27

## Contexte

Le sujet exige une application qui charge un audio, lance l'analyse, affiche une timeline des locuteurs, permet d'écouter les segments et exporte en JSON ou RTTM. La démonstration se fera en direct, sur la machine de la candidate, sur des fichiers inconnus ; le tuteur peut aussi exécuter le dépôt lui-même (D15). La candidate souhaite en outre une page de consultation du pipeline, pour inspecter les réglages de chaque étape et proposer des modifications à partir de cette inspection.

## Options

| Option | Avantages | Inconvénients |
|---|---|---|
| Gradio | Dépôt de fichier, suivi de progression et lecture audio natifs ; peu de code | Interactivité sur mesure (timeline cliquable) plus laborieuse |
| Streamlit | Simple | Modèle de réexécution complète peu adapté à un traitement long avec suivi |
| Application web sur mesure (FastAPI + page HTML) | Liberté totale | Coût de développement nettement plus élevé |

## Décision

**Application de démonstration** en Gradio, exécutée en local, organisée en deux onglets.

| Onglet | Contenu |
|---|---|
| Analyse | Dépôt d'un fichier audio (tout format, normalisé selon D15/D16) ; options : moteur (baseline, pyannote, NeMo), nombre de locuteurs (automatique, imposé, fourchette), périphérique ; suivi des étapes en direct avec une estimation du temps restant (fondée sur le RTF mesuré) ; résultat : forme d'onde et timeline colorée par locuteur, écoute d'un segment au clic, statistiques par locuteur (temps de parole, nombre d'interventions, part de chevauchement), renommage des locuteurs, temps de traitement ; export RTTM et JSON ; dépôt optionnel d'une référence pour afficher le DER décomposé |
| Pipeline | Page de **consultation en lecture seule** : schéma des étapes (normalisation, détection de parole, segmentation locale, empreintes vocales, regroupement, sortie), et une étape « Évaluation » séparée, signalée comme agissant sur la mesure seulement ; un clic sur une étape ouvre sa fiche (rôle, modèle et version, erreurs produites, fichier de définition, tableau des réglages : valeur en vigueur, origine, effet, composante concernée) ; sélecteur du moteur affiché. Aucune modification possible depuis la page : toute modification passe par une fiche de décision et une expérience |

**Source de vérité de la page Pipeline.** La page est générée, jamais rédigée à la main. Elle lit la configuration réellement utilisée par chaque moteur, y compris les réglages internes de pyannote lus sur la pipeline chargée, et un catalogue versionné (`src/whospoke/pipelines/catalogue.yaml`). Ce catalogue décrit chaque réglage : libellé, effet, composante du DER concernée et décision qui le fixe. Chaque moteur expose pour cela une même méthode de description de sa configuration effective.

**Hors ligne.** Les bibliothèques JavaScript de l'interface sont embarquées dans le dépôt, sans CDN extérieur, conformément à la contrainte de souveraineté.

## Justification

Gradio couvre l'essentiel des besoins de la démonstration avec le moins de code. Générer la page Pipeline à partir de la configuration effective garantit qu'elle ne diverge jamais du système réel, et elle sert aussi de documentation pour le rendu. Une page en lecture seule respecte la méthode : les changements restent tracés.

## Conséquences

Chaque moteur suit une interface commune : exécution sur un signal en mémoire, rapport de progression par étape, description de sa configuration effective. Ce contrat doit être respecté dès la baseline. L'interface elle-même vient après les moteurs : premier prototype de l'onglet Analyse en semaine 2, page Pipeline ensuite, environ une demi-journée. Les bonus (référence et DER à l'écran, comparaison de deux moteurs) passent après les ablations.

## Liens

Maquette de la page Pipeline (validée dans son principe le 27/10) : https://claude.ai/artifact/8Mgk46ZzHiQ2r1Bg3CssPk ; D12 (Gradio), D15, D16 ; `docs/glossaire.md`.

## Amendement 1 — premier prototype de l'onglet Analyse (2026-11-01)

Statut : actée (appliquée sur la branche `interface` le 2026-11-01)

Le prototype de l'onglet Analyse (branche `interface`, moteur factice) fonctionne de bout en bout. Le présent amendement tranche les points laissés ouverts par la session et fixe les compléments avant fusion.

| Point | Décision |
|---|---|
| Expérience source de chaque moteur (réglages, θ, RTF) | Expérience sur SUMM-RE, jeu prioritaire (D3) : EXP-0009 (MFCC), EXP-0012 (ECAPA), EXP-0007 (pyannote), EXP-0015 (WeSpeaker, dès qu'elle existe). La correspondance reste dans `app/moteurs.py` jusqu'au gel ; au gel du 10/11, elle est remplacée par un fichier versionné `configs/demo.yaml`, qui décrit la configuration de démonstration |
| RTF pour le temps restant | La plus grande valeur entre dev et test, et la colonne correspondant au périphérique choisi (`rtf` ou `rtf_cpu`). L'estimation est un affichage, pas une mesure au sens de D21 : un temps non conforme peut l'alimenter, mais jamais un tableau de résultats |
| Périphérique | ECAPA et WeSpeaker en CPU (D22, amendement), pyannote au choix |
| Noms des locuteurs à l'export | RTTM avec les noms choisis (espaces remplacés par `_`) ; JSON avec les identifiants du moteur dans les segments et les noms dans la liste des locuteurs ; noms en double refusés |
| DER affiché | Sur toute la durée du fichier déposé, référence coupée à cette durée, dans les deux conditions de collar (protocole §3.1). L'écran indique qu'il n'est pas comparable aux résultats sur les corpus (pas d'UEM) |
| Mode factice | Ignore le nombre de locuteurs imposé et le signale |
| Choix du moteur | NeMo et Nemotron 3 Diarization ajoutés seulement si leur expérience aboutit (D23) |
| Fourchette min–max | pyannote seulement ; la baseline garde seuil θ ou nombre imposé (D19) |
| Fonctionnement hors ligne | Avec les vrais moteurs, l'application fixe `HF_HUB_OFFLINE=1` au démarrage et affiche un message explicite si un modèle manque dans le cache ; contrôle réseau refait avec les vrais moteurs et consigné dans `app/README.md` |
| Dossiers temporaires | Supprimés à la fermeture de l'application |
| Zoom de la timeline | À ajouter avant le gel : les réunions de démonstration peuvent durer 30 min |
| Préchargement des modèles | Script `scripts/prefetch_models.py` : télécharge une fois tous les modèles des moteurs proposés, avec le jeton Hugging Face, puis vérifie qu'ils se chargent hors ligne. Il est cité par le message « modèle absent du cache » et par le README d'installation (D15) |
| Emplacement des fichiers d'ECAPA | Dossier fixe indépendant du dossier courant (cache Hugging Face), jamais `pretrained_models/` du dossier de lancement |

**Séquence.** La fusion dans `main` attend la fin du lot EXP-0013 à EXP-0015, puisqu'elle modifie `uv.lock`. Viennent ensuite la suite de tests complète, puis l'essai avec les vrais moteurs sur l'extrait de 3 min, avant le rang 1 de D23.
