# Planning du sprint final

Version 1.1 du 1er novembre 2026 (file d'attente de D23). Fin du projet : **lundi 16 novembre 2026** (démonstration et rendu). Mis à jour par le cockpit à chaque changement de date ou de périmètre.

## Principes

Le système présenté en démonstration est **pyannote community-1**, éventuellement amélioré ; la baseline sert à la comparaison et à la compréhension. **La configuration de démonstration est gelée le mardi 10 novembre.** Après le jeudi 12 novembre, plus aucune nouvelle expérience : seulement des corrections, la documentation et la répétition. Chaque jour, une seule session Claude Code à la fois sur le dépôt.

## File d'attente des expériences (D23)

Tous les moteurs identifiés sont testés, sans qu'aucun en remplace un autre. Les expériences tournent l'une après l'autre : à la fin d'une expérience, le cockpit prépare le prompt de la suivante. L'ordre de la file prévaut sur les dates du calendrier, qui restent indicatives.

| Rang | Expérience ou chantier | Condition |
|---|---|---|
| 0 | EXP-0013 à EXP-0015, baseline avec empreintes WeSpeaker | En cours |
| 1 | NeMo Sortformer v2 | Local ; essai d'installation borné à 2 h |
| 2 | Nemotron 3 Diarization | Local ; essai borné à 2 h ; licence et données d'entraînement vérifiées avant exécution |
| 3 | pyannote, nombre de locuteurs borné entre 2 et 6 | Local |
| 4 | Robustesse : SUMM-RE test dégradé | Fiche D24 |
| 5 | Amélioration n° 2 : faux chevauchement de pyannote | Fiche D25 |
| 6 | Voxtral Mini Transcribe 3 (API Mistral) | Clé d'API et coût acceptés ; corpus publics seulement |
| 7 | Nemotron 3.5 Transcribe (GPU loué) | Accord sur la location ; possible après le gel, comme comparaison |

## Calendrier

| Date | Claude Code (avec le cockpit) | Candidate | Livrable du jour |
|---|---|---|---|
| Dim. 1/11 | Fin des expériences WeSpeaker (EXP-0013 à 0015) | Recrutement des participants | Comparaison MFCC / ECAPA / WeSpeaker / pyannote |
| Lun. 2/11 | File D23, rangs 1 à 3 : NeMo Sortformer v2 (V6), Nemotron 3 Diarization, pyannote borné entre 2 et 6 locuteurs | Dates d'enregistrement fixées, consentements envoyés | Statut des deux moteurs NVIDIA ; résultats disponibles |
| Mar. 3/11 | Prototype de l'onglet Analyse de l'interface (D17) | Préparation du matériel (téléphones, pièce, visio) | Démo minimale de bout en bout |
| Mer. 4/11 | Robustesse : SUMM-RE test dégradé (réverbération, bruit, codec de visio), pyannote et baseline | **Enregistrements M01–M03** | Tableau de robustesse |
| Jeu. 5/11 | Amélioration n° 2 : faux chevauchement de pyannote (post-traitement, sortie exclusive) ; si le temps le permet : détection neuronale pour la baseline | **Enregistrements** (fin) | Ablation n° 2 |
| Ven. 6/11 | Scripts de pré-annotation à partir des pistes d'aide, conversion en RTTM | **Annotation** | Corpus maison pré-annoté |
| Sam. 7/11 | — | **Annotation, contrôle qualité** (2 min ré-annotées) | Références du corpus maison |
| Dim. 8/11 | Réserve | Réserve | — |
| Lun. 9/11 | Évaluation de tous les systèmes sur le corpus maison | Écoute des cas d'échec | Décision finale sur l'amélioration n° 1 (D9) |
| Mar. 10/11 | Page Pipeline ; finitions de l'interface ; **gel de la configuration de démonstration** | Essai de l'interface | Configuration gelée |
| Mer. 11/11 | Férié (Armistice) : réserve | — | — |
| Jeu. 12/11 | Test d'installation dans un environnement vierge ; README de reproduction | Répétition sur des fichiers inédits | Dépôt reproductible |
| Ven. 13/11 | Synthèse : tableau comparatif, ablation, cas d'échec, temps de calcul | Relecture | Document de synthèse |
| Sam. 14/11 – dim. 15/11 | Réserve ; comparaisons cloud (D23, rangs 6 et 7) si elles n'ont pas pu tourner avant | Répétition de la démonstration | — |
| **Lun. 16/11** | — | **Démonstration et rendu** | — |

## Chemin critique

Le corpus maison est le seul chantier qui dépend de personnes extérieures. Les étapes s'enchaînent ainsi : enregistrement (4–5/11), annotation (6–7/11), évaluation (9/11), puis gel (10/11). Tout retard sur les enregistrements décale la décision sur l'amélioration n° 1 et le choix de la configuration de démonstration. Si les enregistrements glissent au-delà du 6/11, le gel est fixé sur SUMM-RE et le corpus maison ne sert plus qu'au test final.

## Hors périmètre (coupes assumées)

| Élément | Motif |
|---|---|
| Ajustement fin (fine-tuning) et entraînement avec augmentation | Coût et risque trop élevés en 15 jours ; fuite de locuteurs dans SUMM-RE (D20) |
| NOTSOFAR-1 | Volume, test en anglais ; la robustesse est mesurée par simulation sur SUMM-RE |
| Installation d'un moteur externe au-delà de 2 h d'essai | Règle d'essai borné (D23) ; l'échec est documenté |
| Service cloud ou GPU loué comme moteur de démonstration | La démonstration reste locale ; Voxtral et Nemotron 3.5 sont des comparaisons (D23) |
