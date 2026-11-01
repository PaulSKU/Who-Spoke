# D23 — Moteurs supplémentaires et file d'attente des expériences

Statut : actée
Date : 2026-11-01

## Contexte

La candidate a décidé de tester tous les moteurs identifiés, sans en remplacer aucun : NeMo Sortformer v2 (prévu par D6), Nemotron 3 Diarization, Voxtral Mini Transcribe 3 et Nemotron 3.5 Transcribe (veille du 1er novembre, `docs/recherche/veille-2026-11-01-modeles-recents.md`). Les expériences tournent l'une après l'autre : à la fin d'une expérience, la suivante est lancée.

## Décision

### 1. Règles communes aux moteurs externes

| Point | Règle |
|---|---|
| Intégration | Une enveloppe par moteur, conforme au contrat de D19 §1 (signal en mémoire, nombre de locuteurs par fichier si le moteur le permet, `describe()`), dans `src/whospoke/pipelines/` |
| Environnement | Un moteur dont les dépendances sont incompatibles avec l'environnement principal (NeMo) tourne dans un environnement séparé (D10) ; l'enveloppe l'appelle en sous-processus et relit un RTTM |
| Évaluation | Même protocole, mêmes partitions (AMI SDM test, SUMM-RE test ; dev si le moteur a un réglage) |
| Contamination | Données d'entraînement consignées dans `docs/corpus.md` §9 avant toute exécution |
| Temps de calcul | RTF mesuré pour les moteurs locaux (protocole §3.5) ; pour un service cloud, temps de réponse consigné à part, jamais comparé aux RTF locaux |
| Données envoyées hors de la machine | Corpus publics seulement (AMI, SUMM-RE) ; **jamais le corpus maison** ; coût consigné |
| Essai borné | Toute installation qui échoue après 2 h de tentative est abandonnée, et l'échec est documenté |

### 2. File d'attente

| Rang | Expérience ou chantier | Moteur, condition | Prérequis |
|---|---|---|---|
| 0 | EXP-0013 à EXP-0015 (en cours) | Baseline avec empreintes WeSpeaker | — |
| 1 | NeMo Sortformer v2 (essai borné) | Local, environnement séparé ; 4 locuteurs au plus | Installation de NeMo sur Mac |
| 2 | Nemotron 3 Diarization | Local, environnement séparé ou portage ; 8 locuteurs au plus | Licence et données d'entraînement vérifiées |
| 3 | pyannote, nombre de locuteurs borné entre 2 et 6 | Local | — |
| 4 | Robustesse : SUMM-RE test dégradé | Tous les moteurs locaux retenus | Fiche D24 |
| 5 | Amélioration n° 2 : faux chevauchement de pyannote | Local | Fiche D25 |
| 6 | Voxtral Mini Transcribe 3 | API Mistral, payant | Clé d'API ; coût estimé et accepté par la candidate |
| 7 | Nemotron 3.5 Transcribe | GPU loué (80 Go) | Accord de la candidate sur la location ; s'exécute après le gel du 10/11 si nécessaire, comme comparaison |

Les rangs 6 et 7 sont des comparaisons : ils ne peuvent pas devenir le système de démonstration, qui doit rester local. Si un moteur local (rang 1 ou 2) dépasse pyannote sur le français, le choix du moteur de démonstration est rediscuté avant le gel du 10 novembre.

## Justification

Tester tous les moteurs renforce la comparaison exigée par le sujet. Les règles communes garantissent que les résultats restent comparables. La file d'attente évite la concurrence sur le CPU, qui fausserait les temps de calcul.

## Conséquences

Le planning (`docs/planning.md`) est mis à jour. Chaque moteur fait l'objet d'un prompt dédié, préparé par le cockpit à la fin de l'expérience précédente.

## Amendement du 01/11/2026 — file réordonnée après l'audit

Statut : actée

L'audit du 01/11 (`docs/audit/audit-2026-11-01.md`), dont la candidate a retenu les recommandations, conduit à réordonner la file :

- **Sortformer v2 recule.** Il est limité à 4 locuteurs, et sa version v2.1 est nettement dépassée par Nemotron 3 Diarization sur tous les jeux publiés par NVIDIA.
- **DiariZen entre dans la file.** Il annonce 13,9 % de DER sur AMI-SDM, contre 19,9 % pour community-1 ; ses poids sont sous CC BY-NC 4.0.
- **Nemotron 3.5 est retiré.** Il ne tourne que sur GPU NVIDIA.

La file en vigueur est celle de `docs/planning.md` (version 2.0, rangs A1 à A9). Elle remplace le tableau du §2. Les règles communes du §1 restent inchangées. Deux précisions s'ajoutent :

- l'essai d'installation de DiariZen est borné à 4 h, parce que son installation n'est documentée que pour CUDA ;
- avant toute exécution, la contamination de Nemotron 3 Diarization est consignée dans `docs/corpus.md` §9 : AMI train et dev, VoxConverse dev et test.

## Liens

D6, D10, D17, D19, D21 ; `docs/recherche/veille-2026-11-01-modeles-recents.md`.
