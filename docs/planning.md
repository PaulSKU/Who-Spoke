# Planning et feuille de route du sprint final

Version 2.1 du 2 novembre 2026 : recommandations de l'audit du 01/11 retenues, file D23 réordonnée (D23, amendement du 01/11) ; analyse des cas d'échec et vue spectrogramme ajoutées (D28). Fin du projet : **lundi 16 novembre 2026** (démonstration et rendu). Mis à jour par le cockpit à chaque changement de date ou de périmètre.

## Principes

**Priorités depuis l'avis du tuteur du 03/11** : (1) corpus maison, priorité absolue, enregistrements d'ici au 8/11, annotation, évaluation fichier par fichier ; (2) diagnostic de Nemotron 3 sur AMI (D29) ; (3) synthèse de 2 pages et préparation de l'oral. Plus aucun polissage de l'interface (piste B en pause, seul reste l'essai au vidéoprojecteur). DiariZen écarté.

- **Configuration de démonstration.** Pas de date de gel fixe (décision de la candidate, 03/11). `configs/demo.yaml` est écrit dès que la règle de D29 peut être appliquée, c'est-à-dire quand le corpus maison est évalué.
- **Machine.** Une seule expérience tourne à la fois, sur secteur. Aucun autre calcul lourd ne tourne pendant une expérience (tests avec modèles, analyses), pour ne pas fausser les temps.
- **Parallélisme.** Les travaux sans calcul (interface avec le moteur factice, outils, documents) avancent en parallèle dans des worktrees git séparés.
- **Fusions.** Une fusion dans `main` n'a lieu que lorsque aucune expérience ne tourne. Seule la piste A ajoute des dépendances (`uv add`) ; les autres pistes demandent au cockpit.
- **Corpus maison.** Les enregistrements arrivent au fil des jours. Chacun est traité dès son arrivée (pré-annotation, annotation, évaluation par fichier), sans aucun réglage sur ce corpus. Il n'est jamais envoyé hors de la machine (D27).
- **Coupe.** Ce qui n'est pas lancé le 9/11 au soir est coupé.

## Pistes de travail

| Piste | Qui | Où | Nature |
|---|---|---|---|
| A — Expériences | Claude Code, session « expériences » | `~/Dev/Who-Spoke` (`main`) | File D23 : une expérience après l'autre, de nuit si possible |
| B — Interface et démonstration | Claude Code, session « interface » | worktree `~/Dev/Who-Spoke-ui` (branche `ui`) | Chantiers C2 à C6 de l'audit, moteur factice |
| E — Outils | Claude Code, session « outils » | worktree `~/Dev/Who-Spoke-outils` (branche `outils`) | Licence, commande en ligne, intégration continue, chaîne du corpus maison |
| C — Cockpit | Cockpit | Documents du dépôt | Fiches, interprétations, synthèse, scénario de démonstration, prompts |
| D — Candidate | Candidate | — | Enregistrements, annotation, écoutes, répétitions, relais entre les sessions |

Pas de conversation « orchestratrice » supplémentaire : le cockpit tient ce rôle et lit directement le dépôt (journal, résultats). Chaque session Claude Code reçoit un prompt en lot, avec plusieurs étapes et des conditions d'arrêt, et consigne son rapport dans `docs/journal.md`. La candidate n'a qu'à signaler au cockpit qu'une session a fini.

## File d'attente de la piste A (D23, amendement du 01/11)

| Rang | Contenu | Calcul estimé | Prérequis |
|---|---|---|---|
| A1 | pyannote à révision figée, sorties habituelle et exclusive enregistrées ; V1 de D25 sur SUMM-RE et AMI ; contrôle que la sortie habituelle reproduit EXP-0007 et EXP-0001 | ≈ 2 h | — |
| A2 | pyannote borné entre 2 et 6 locuteurs, avec consignation du passage au KMeans | ≈ 2 h | A1 |
| A3 | D24 : génération du SUMM-RE dégradé, écoute de contrôle, puis pyannote et baseline ECAPA sur les 7 conditions | génération ≈ 1 h ; calcul ≈ 6 h (nuit) | Écoute par la candidate |
| A4 | Nemotron 3 Diarization (essai borné à 2 h) : AMI, SUMM-RE, puis D24 | ≈ 3 h | Licence et contamination consignées (corpus.md §9) |
| A5 | DiariZen (essai borné à 4 h) : AMI, SUMM-RE, puis D24 | ≈ 3 à 6 h en CPU | Idem |
| A6 | D25 V2 et V3 : réglage de Silero VAD sur SUMM-RE dev, puis évaluation complète | ≈ 2 h | A1, A3 |
| A7 | Option : réglage du seuil de regroupement de pyannote sur SUMM-RE dev (audit R-Q5) | ≈ 3 h | A2 |
| A8 | Options : NeMo Sortformer v2 ; Voxtral (corpus publics seulement) | — | S'il reste du temps avant le 9/11 |
| A9 | Corpus maison : évaluation de tous les moteurs retenus, au fil des références disponibles ; évaluation complète le 9/11 | court | Références (piste D) |

Nemotron 3.5 Transcribe est retiré : il ne tourne que sur GPU NVIDIA.

## Chantiers des pistes B et E (audit du 01/11)

| Ordre | Piste | Chantier | Contenu |
|---|---|---|---|
| B1 | B | C2 | Finitions (libellés en français, pied de page, éléments rognés, tête de lecture, ordre des étapes) ; timeline en pleine largeur après l'analyse |
| B2 | B | C5 | Démonstration : préchauffage des modèles au démarrage avec l'indicateur « moteurs prêts », durée annoncée avant lancement, cache des résultats (plan de repli) |
| B3 | B | C3 | Vue d'ensemble (mini-forme d'onde), lecture suivie, raccourcis clavier |
| B4 | B | C4 | Appariement visible, « Expliquer cette erreur », extrait typique par locuteur, renommage dans le tableau |
| B5 | B | C6 | Avancement raconté (graphique, synthèse), Pipeline relié aux mesures |
| B6 | B | P2 | Fusion de locuteurs avec le DER avant et après, indicateurs d'interaction, exports Audacity et PNG, bascule de la sortie exclusive (selon A1) |
| E1 | E | C7 | Licence MIT et tableau des licences tierces ; commande en ligne `whospoke diarize` ; intégration continue (suite rapide, torch en CPU) |
| B9 | B | D28 §2 | Vue spectrogramme (échelle mel, alignée sur la timeline) ; courbe d'énergie et seuil de détection de la baseline |
| E8 | E | D28 §1 | Script de l'analyse A-0003 (cas d'échec) ; première exécution après A3 et A6, mise à jour avec le corpus maison le 9/11 |
| B10 | B | Audit visuel §4 et §7 | Système visuel (thème, jetons, boutons, encadrés, focus, formatage français) ; correctif des radios ; captures de référence, axe, stylelint |
| B11 | B | Audit visuel §5 | Finitions de l'onglet Analyse (tableau des locuteurs, barre d'outils, en-tête, états vides, aides repliables) |
| B12 | B | Audit visuel §6 | Nouvelle représentation du pipeline (schéma de gauche à droite, formes des données, naissance des erreurs, stepper mobile) |
| B13 | B | Audit visuel §7 | Avancement et Glossaire au même système ; passe break-ui ; essai au vidéoprojecteur |
| E2 | E | — | Chaîne du corpus maison : synchronisation par le clap, pré-annotation à partir des pistes d'aide, export des étiquettes Audacity, conversion en RTTM avec fusion à 200 ms et UEM, contrôle de qualité |

Points de fusion : après B2, après B4, après B6 et après E1 et E2, chaque fois entre deux expériences de la piste A.

## Calendrier

| Date | A — Expériences | B — Interface | E — Outils | C — Cockpit | D — Candidate |
|---|---|---|---|---|---|
| Dim. 1/11 (soir) | A1 (nuit) | B1 | E1 | D23 à D25, feuille de route, prompts | Premiers enregistrements |
| Lun. 2/11 | A3 (pyannote puis ECAPA sur les 7 conditions) ; A6 (Silero, SUMM-RE et AMI) la nuit | B1 à B8 faits ; B9 (spectrogramme) | E1 à E7 faits ; E8 (script d'A-0003) | Interprétations d'A1 et A2 ; README ; D28 ; `docs/demo.md` | Écoute de D24 (faite) ; enregistrements |
| Mar. 3/11 | Fusions ; A4 (Nemotron 3) | Pause | Pause | Interprétations d'A3 et A6 ; glossaire | Enregistrements ; premier passage dans la chaîne d'annotation (avec une session E) |
| Mer. 4/11 | A5 (DiariZen) ; D24 pour V2 si elle passe les règles 1 à 3 de D25 | — | A-0003, première exécution | Interprétation d'A4 ; A-0003 | Enregistrements, annotation ; écoute des extraits d'A-0003 |
| Jeu. 5/11 | Suite de A5 ; A7 (réglage du seuil de pyannote) si le temps le permet | — | — | Interprétation d'A5 ; mise à jour de la synthèse | Annotation |
| Ven. 6/11 | A9 sur les premières références ; A8 en option | — | — | Interprétations ; `docs/demo.md` | Annotation, contrôle qualité |
| Sam. 7/11 | Réserve | — | — | Synthèse à jour | Annotation (fin) |
| Dim. 8/11 | Réserve | Réserve | — | — | Réserve |
| Lun. 9/11 | A9 complet ; A-0003 avec le corpus maison ; coupe de ce qui n'a pas commencé | Fusion finale | Rapport du corpus maison | Choix de la configuration de démonstration | Écoute des cas d'échec |
| Mar. 10/11 | Application de D29 dès que le corpus maison est évalué ; `configs/demo.yaml` | — | — | Décision sur le moteur de démonstration | Essai au vidéoprojecteur |
| Mer. 11/11 | Férié : réserve | — | — | — | — |
| Jeu. 12/11 | Campagne de temps, machine au repos (D21, amendement du 01/11) ; installation sur machine vierge | — | — | README de reproduction | Répétition sur des fichiers inédits |
| Ven. 13/11 | — | — | — | Document de synthèse | Relecture |
| Sam. 14/11 – dim. 15/11 | Réserve | — | — | Scénario final | Répétitions chronométrées, réseau coupé |
| **Lun. 16/11** | — | — | — | — | **Démonstration et rendu** |

## Chemin critique et risques

Le corpus maison est le seul élément qui dépend de personnes extérieures : sans références le 9/11, le choix de la configuration se fait sur SUMM-RE et D24, et le corpus maison ne sert qu'à la démonstration. Côté technique, le risque principal est l'installation de Nemotron 3 et de DiariZen sur Mac (support non documenté) : les essais sont bornés, et un échec est un résultat documenté. Le risque de surcharge vient du relais entre trois sessions ; il est limité par les prompts en lot et par la lecture directe du dépôt par le cockpit.

## Hors périmètre (coupes assumées)

| Élément | Motif |
|---|---|
| Ajustement fin et entraînement avec augmentation | Coût et risque trop élevés ; fuite de locuteurs dans SUMM-RE (D20) |
| NOTSOFAR-1 | Volume ; la robustesse est mesurée par simulation (D24) |
| Nemotron 3.5 Transcribe | GPU NVIDIA seulement (D23, amendement du 01/11) |
| Service cloud ou GPU loué comme moteur de démonstration | La démonstration reste locale (D23) |
| Transcription, enregistrement au micro, modification de réglage depuis l'interface | Hors sujet ou exclus par D26 |
| Annulation réelle d'une analyse, fusion DOVER-Lap, débruitage en amont | Gain incertain ou risque de régression (audit, P3) |
