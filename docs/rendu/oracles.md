# Décomposition de l'erreur par les oracles

Partition test, DER en %, chevauchements comptés ; composantes sans collar. Chaque expérience change une seule variable par rapport à sa référence (D9) : détection de parole oracle (`detection_oracle`), nombre de locuteurs oracle (`mode_n_locuteurs`) ou représentation. Écart : DER de l'expérience moins DER de sa référence, intervalle de confiance à 95 % par bootstrap apparié sur les fichiers (1 000 tirages, graine 0).

| Expérience | Moteur | Variable modifiée | DER sans collar | DER collar 0,25 s | Parole manquée | Fausse alarme | Confusion | Référence | Écart sans collar [IC 95 %] | Écart collar 0,25 s [IC 95 %] |
|---|---|---|---|---|---|---|---|---|---|---|
| EXP-0002 (baseline-mfcc-ami-sdm) | baseline ; locuteurs : estime ; détection : energie | — (référence) | 64,38 % | 61,21 % | 32,28 | 4,99 | 27,11 | — | — | — |
| EXP-0003 (baseline-k-oracle) | baseline ; locuteurs : oracle ; détection : energie | mode_n_locuteurs | 63,42 % | 60,41 % | 32,28 | 4,99 | 26,15 | EXP-0002 | −0,96 [−2,33 ; +0,81] | −0,81 [−2,34 ; +1,06] |
| EXP-0004 (baseline-vad-oracle) | baseline ; locuteurs : estime ; détection : oracle | detection_oracle | 49,09 % | 45,10 % | 14,59 | 0,14 | 34,35 | EXP-0002 | −15,29 [−17,68 ; −12,96] | −16,11 [−18,48 ; −13,76] |
| EXP-0005 (pyannote-c1-k-oracle) | pyannote-community-1 ; locuteurs : oracle ; détection : integree | mode_n_locuteurs | 20,40 % | 13,93 % | 11,16 | 3,81 | 5,42 | EXP-0001 | +0,48 [−0,63 ; +2,29] | +0,72 [−0,38 ; +2,79] |
| EXP-0006 (baseline-vad-k-oracle) | baseline ; locuteurs : oracle ; détection : oracle | mode_n_locuteurs | 48,92 % | 45,07 % | 14,59 | 0,14 | 34,19 | EXP-0004 | −0,16 [−2,84 ; +2,19] | −0,03 [−3,11 ; +2,74] |
| EXP-0010 (baseline-ecapa-ami-sdm) | baseline ; locuteurs : estime ; détection : energie | representation | 45,88 % | 40,85 % | 32,27 | 4,99 | 8,63 | EXP-0002 | −18,50 [−23,70 ; −13,83] | −20,36 [−25,93 ; −15,06] |
| EXP-0011 (baseline-ecapa-vad-k-oracle) | baseline ; locuteurs : oracle ; détection : oracle | representation | 25,39 % | 18,72 % | 14,59 | 0,13 | 10,67 | EXP-0006 | −23,53 [−28,78 ; −18,64] | −26,35 [−32,23 ; −20,96] |

Série : `app.avancement.ORACLE_SERIES` (EXP-0002, EXP-0003, EXP-0004, EXP-0005, EXP-0006, EXP-0010, EXP-0011), celle de l'onglet Avancement.

**Sources.** Expériences (commit d'exécution) : EXP-0001 (`d9f177a`), EXP-0002 (`540bb5e`), EXP-0003 (`3abe688`), EXP-0004 (`3abe688`), EXP-0005 (`3abe688`), EXP-0006 (`3abe688`), EXP-0010 (`fba633a`), EXP-0011 (`14fde7e`).
Fichiers : `results/leaderboard.csv` (contrôle), `results_<corpus>_<partition>.json` et `per_file_<corpus>_<partition>.csv` de chaque expérience.

**Constats liés** (`docs/constats.yaml`, version 1 du 2026-11-04) :

- C01 (certain) : La détection par énergie est le premier défaut de la baseline : avec ECAPA, la parole manquée fait 32,3 des 45,9 points de DER sur AMI test, et 21,9 des 33,4 points sur SUMM-RE test. Sources : EXP-0010, EXP-0012.
- C02 (certain) : Une détection de parole parfaite retire 15,3 points de DER à la baseline MFCC sur AMI test (64,4 → 49,1 %). Sources : EXP-0002, EXP-0004.
- C03 (certain) : À empreinte identique (WeSpeaker), pyannote devance la baseline de 29,3 points sur AMI test, dont 21,1 de parole manquée : son avance vient surtout de la segmentation neuronale, qui détecte la parole et le chevauchement. Sources : EXP-0001, EXP-0013.
- C05 (certain) : Remplacer les MFCC par des empreintes ECAPA fait tomber la confusion de la baseline de 27,1 à 8,6 points sur AMI test, et de 24,4 à 8,5 sur SUMM-RE test. Sources : EXP-0002, EXP-0010, EXP-0009, EXP-0012.
- C06 (certain) : Sous oracles, ECAPA et WeSpeaker ne se distinguent pas (écart +2,2 points, IC à 95 % [−0,1 ; +4,6]) ; en condition réaliste, WeSpeaker est légèrement moins bon (+2,5 à +3,3 points). Sources : EXP-0011, EXP-0014, EXP-0013, EXP-0015.
- C07 (certain) : Donner à pyannote le nombre exact de locuteurs ne l'améliore pas : +0,48 point sur AMI test, −0,72 point non significatif sur SUMM-RE test. Sources : EXP-0005, EXP-0008.
- C08 (certain) : Avec le seuil réglé pour minimiser le DER, la baseline WeSpeaker ne trouve jamais le bon nombre de locuteurs sur AMI test (0/16), alors que son DER reste proche de celui d'ECAPA (7/16). Sources : EXP-0013, EXP-0010.
- C10 (probable) : AMI surestime pyannote, qui l'a vu à l'entraînement : à empreinte identique, son avance sur la baseline est de 29,3 points sur AMI test, mais de 9,6 points en français (SUMM-RE test). Sources : EXP-0013, EXP-0001, EXP-0015, EXP-0007.
