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
