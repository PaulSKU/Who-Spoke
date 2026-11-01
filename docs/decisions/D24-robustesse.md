# D24 — Robustesse : SUMM-RE test dégradé

Statut : actée
Date : 2026-11-01

## Contexte

La cible est faite de réunions en français enregistrées par un micro de table, avec réverbération, en visio ou dans le bruit. SUMM-RE est en français, mais enregistré en micros-casques ; AMI est en anglais et contaminé pour pyannote et Nemotron 3. Le corpus maison n'aura que quelques enregistrements, qui arriveront au fil des jours. Dégrader SUMM-RE test de façon contrôlée est donc la seule mesure à la fois proche de la cible et assez grande pour une comparaison statistique (audit du 01/11, R-E2).

## Décision

### 1. Conditions

Toutes les conditions portent sur SUMM-RE test (37 réunions), avec les références et l'UEM inchangés.

| Code | Dégradation | Réglage |
|---|---|---|
| `propre` | Aucune | Résultats existants |
| `rev04` | Réverbération simulée | Salle parallélépipédique, RT60 ≈ 0,4 s |
| `rev08` | Réverbération simulée | RT60 ≈ 0,8 s |
| `bru15` | Bruit additif non vocal | RSB 15 dB |
| `bru05` | Bruit additif non vocal | RSB 5 dB |
| `cod16` | Codec de visio | Opus mono 16 kbit/s |
| `cod08` | Codec de visio | Opus mono 8 kbit/s |
| `salle` | Combinaison réaliste | RT60 ≈ 0,6 s et RSB 10 dB |

**Réverbération.** Les réponses impulsionnelles sont simulées avec pyroomacoustics (méthode des images ; licence MIT à vérifier). Le micro est placé au centre de la table, et chaque locuteur à une position distincte, entre 1 et 2,5 m. Si les pistes individuelles de SUMM-RE sont encore disponibles localement, ou retéléchargeables dans la limite d'essai de 2 h (D23), chaque piste est convoluée avec la réponse impulsionnelle de son locuteur avant le mélange : c'est le cas réaliste. Sinon, une réponse impulsionnelle unique est appliquée au mélange, et cette limite est consignée.

**Bruit.** Le bruit est non vocal, pour ne pas ajouter de locuteur : ambiance de bureau, de café sans parole intelligible, ventilation. Source : MUSAN, sous-ensemble `noise` (CC BY 4.0), si son téléchargement reste raisonnable ; sinon DEMAND. La licence et la taille sont vérifiées avant le téléchargement. Le RSB est calculé sur les zones de parole de la référence.

**Codec.** L'encodage et le décodage passent par ffmpeg (libopus), avec un ré-échantillonnage à 16 kHz. Les pertes de paquets ne sont pas simulées : c'est une limite consignée.

Toute la génération est déterministe (graine fixée, affectation des bruits et des positions consignée). Les fichiers produits vont dans `data/processed/summre_degrade/<condition>/`, non versionné, et sont regénérables par script. Une empreinte de la configuration est enregistrée. Avant toute expérience, la candidate écoute trois extraits de 20 s par condition, pour vérifier que chaque dégradation est perceptible et plausible.

### 2. Moteurs et expériences

Une expérience par moteur ; chaque condition y est un jeu évalué (`results_summre-<condition>_test.json`).

| Moteur | Configuration |
|---|---|
| pyannote community-1 | Celle d'EXP-0007 ; sorties habituelle et exclusive (D25) |
| Baseline ECAPA | Celle d'EXP-0012 (θ = 1,00) |
| Nemotron 3 Diarization, DiariZen | Seulement s'ils sont intégrés (D23), avec la même grille |

### 3. Mesures

Toutes les métriques du protocole sont calculées, dans les deux conditions de collar. Pour chaque moteur et chaque condition, l'écart à `propre` est estimé par bootstrap apparié. À condition égale, les moteurs sont comparés par bootstrap apparié. La question principale est le classement des moteurs sous dégradation, et lequel se dégrade le moins.

### 4. Temps de calcul

Environ 12 h d'audio par condition. pyannote en MPS (RTF ≈ 0,05) demande environ 35 min par condition, soit 4 h pour les 7 conditions ; la baseline ECAPA en CPU environ 15 min par condition. Les exécutions se font de nuit, sur secteur.

## Justification

Seule une variable change par condition, sauf pour `salle`, qui donne un point réaliste. Les références restent les mêmes, ce qui isole l'effet du signal. Le codec et la réverbération correspondent aux deux situations de la cible que nos corpus ne couvrent pas.

## Liens

D3, D21, D23, D25 ; audit du 01/11 (R-E2) ; `docs/corpus.md`.
