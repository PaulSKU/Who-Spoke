# Systèmes par corpus

Partition test, condition réaliste (nombre de locuteurs non donné, détection non oracle). DER en %, chevauchements comptés ; composantes sans collar. Nombre de locuteurs exact : réunions où le nombre estimé égale celui de la référence.

## SUMM-RE

| Système | Expérience | Verdict | DER sans collar | DER collar 0,25 s | Parole manquée | Fausse alarme | Confusion | Nombre de locuteurs exact |
|---|---|---|---|---|---|---|---|---|
| pyannote community-1 | EXP-0007 (pyannote-c1-summre) | référence | 26,30 % | 14,82 % | 7,15 | 11,28 | 7,87 | 31/37 (83,8 %) |
| Baseline MFCC | EXP-0009 (baseline-mfcc-summre) | référence | 49,36 % | 42,66 % | 21,87 | 3,08 | 24,42 | 17/37 (45,9 %) |
| Baseline ECAPA | EXP-0012 (baseline-ecapa-summre) | retenu | 33,42 % | 24,42 % | 21,87 | 3,08 | 8,47 | 28/37 (75,7 %) |
| Baseline WeSpeaker | EXP-0015 (baseline-wespeaker-summre) | écarté | 35,86 % | 26,74 % | 21,87 | 3,08 | 10,92 | 23/37 (62,2 %) |
| pyannote community-1 (sortie) | EXP-0016 (pyannote-c1-summre-exclusive) | en cours | 30,40 % | 17,78 % | 15,55 | 8,30 | 6,55 | 31/37 (83,8 %) |
| pyannote community-1 (mode_n_locuteurs) | EXP-0018 (pyannote-c1-summre-borne-2-6) | en cours | 25,82 % | 14,31 % | 7,15 | 11,28 | 7,39 | 31/37 (83,8 %) |

Écart à la référence déclarée (SUMM-RE, test) : DER de l'expérience moins DER de sa référence, en points, intervalle de confiance à 95 % par bootstrap apparié sur les fichiers (1 000 tirages, graine 0). Un écart négatif est une amélioration.

| Expérience | Référence (variable modifiée) | Écart sans collar [IC 95 %] | Écart collar 0,25 s [IC 95 %] | Fichiers où l'expérience fait mieux / moins bien (sans collar) |
|---|---|---|---|---|
| EXP-0012 | EXP-0009 (representation) | −15,95 [−19,49 ; −12,53] | −18,25 [−22,58 ; −14,02] | 36 / 1 sur 37 |
| EXP-0015 | EXP-0009 (representation) | −13,50 [−17,68 ; −9,78] | −15,92 [−20,78 ; −11,44] | 32 / 5 sur 37 |
| EXP-0016 | EXP-0007 (sortie) | +4,10 [+3,24 ; +5,03] | +2,97 [+2,21 ; +3,81] | 1 / 36 sur 37 |
| EXP-0018 | EXP-0007 (mode_n_locuteurs) | −0,48 [−1,48 ; +0,00] | −0,50 [−1,58 ; +0,00] | 1 / 0 sur 37 |

## AMI (SDM)

| Système | Expérience | Verdict | DER sans collar | DER collar 0,25 s | Parole manquée | Fausse alarme | Confusion | Nombre de locuteurs exact |
|---|---|---|---|---|---|---|---|---|
| pyannote community-1 | EXP-0001 (pyannote-c1-ami-sdm) | référence | 19,92 % | 13,21 % | 11,16 | 3,81 | 4,94 | 12/16 (75,0 %) |
| Baseline MFCC | EXP-0002 (baseline-mfcc-ami-sdm) | référence | 64,38 % | 61,21 % | 32,28 | 4,99 | 27,11 | 0/16 (0,0 %) |
| Baseline ECAPA | EXP-0010 (baseline-ecapa-ami-sdm) | retenu | 45,88 % | 40,85 % | 32,27 | 4,99 | 8,63 | 7/16 (43,8 %) |
| Baseline WeSpeaker | EXP-0013 (baseline-wespeaker-ami-sdm) | écarté | 49,17 % | 43,95 % | 32,27 | 4,99 | 11,90 | 0/16 (0,0 %) |
| pyannote community-1 (sortie) | EXP-0017 (pyannote-c1-ami-sdm-exclusive) | en cours | 24,48 % | 16,76 % | 18,48 | 2,52 | 3,48 | 12/16 (75,0 %) |
| pyannote community-1 (mode_n_locuteurs) | EXP-0019 (pyannote-c1-ami-sdm-borne-2-6) | en cours | 19,92 % | 13,21 % | 11,16 | 3,81 | 4,94 | 12/16 (75,0 %) |

Écart à la référence déclarée (AMI (SDM), test) : DER de l'expérience moins DER de sa référence, en points, intervalle de confiance à 95 % par bootstrap apparié sur les fichiers (1 000 tirages, graine 0). Un écart négatif est une amélioration.

| Expérience | Référence (variable modifiée) | Écart sans collar [IC 95 %] | Écart collar 0,25 s [IC 95 %] | Fichiers où l'expérience fait mieux / moins bien (sans collar) |
|---|---|---|---|---|
| EXP-0010 | EXP-0002 (representation) | −18,50 [−23,70 ; −13,83] | −20,36 [−25,93 ; −15,06] | 15 / 1 sur 16 |
| EXP-0013 | EXP-0002 (representation) | −15,22 [−20,10 ; −10,54] | −17,26 [−22,75 ; −11,85] | 14 / 2 sur 16 |
| EXP-0017 | EXP-0001 (sortie) | +4,56 [+2,79 ; +6,32] | +3,55 [+1,87 ; +5,27] | 0 / 16 sur 16 |
| EXP-0019 | EXP-0001 (mode_n_locuteurs) | +0,00 [+0,00 ; +0,00] | +0,00 [+0,00 ; +0,00] | 0 / 0 sur 16 |

**Sources.** Expériences (commit d'exécution) : EXP-0001 (`d9f177a`), EXP-0002 (`540bb5e`), EXP-0007 (`568efbb`), EXP-0009 (`568efbb`), EXP-0010 (`fba633a`), EXP-0012 (`3856355`), EXP-0013 (`2a08ff7`), EXP-0015 (`5bcb295`), EXP-0016 (`12a67a6`), EXP-0017 (`4dc5e63`), EXP-0018 (`2fcf766`), EXP-0019 (`45b309d`).
Fichiers : `results/leaderboard.csv` (contrôle), `results_<corpus>_<partition>.json` et `per_file_<corpus>_<partition>.csv` de chaque expérience.

**Constats liés** (`docs/constats.yaml`, version 1 du 2026-11-01) :

- C01 (certain) : La détection par énergie est le premier défaut de la baseline : avec ECAPA, la parole manquée fait 32,3 des 45,9 points de DER sur AMI test, et 21,9 des 33,4 points sur SUMM-RE test. Sources : EXP-0010, EXP-0012.
- C02 (certain) : Une détection de parole parfaite retire 15,3 points de DER à la baseline MFCC sur AMI test (64,4 → 49,1 %). Sources : EXP-0002, EXP-0004.
- C03 (certain) : À empreinte identique (WeSpeaker), pyannote devance la baseline de 29,3 points sur AMI test, dont 21,1 de parole manquée : son avance vient surtout de la segmentation neuronale, qui détecte la parole et le chevauchement. Sources : EXP-0001, EXP-0013.
- C04 (certain) : En français (SUMM-RE test), la fausse alarme est la première erreur de pyannote : 11,3 des 26,3 points de DER ; 34 à 44 % se trouve dans des pauses de 1 s au plus d'un même locuteur, que pyannote recouvre, et environ un quart vient de faux chevauchements. Sources : EXP-0007, A-0001.
- C05 (certain) : Remplacer les MFCC par des empreintes ECAPA fait tomber la confusion de la baseline de 27,1 à 8,6 points sur AMI test, et de 24,4 à 8,5 sur SUMM-RE test. Sources : EXP-0002, EXP-0010, EXP-0009, EXP-0012.
- C06 (certain) : Sous oracles, ECAPA et WeSpeaker ne se distinguent pas (écart +2,2 points, IC à 95 % [−0,1 ; +4,6]) ; en condition réaliste, WeSpeaker est légèrement moins bon (+2,5 à +3,3 points). Sources : EXP-0011, EXP-0014, EXP-0013, EXP-0015.
- C08 (certain) : Avec le seuil réglé pour minimiser le DER, la baseline WeSpeaker ne trouve jamais le bon nombre de locuteurs sur AMI test (0/16), alors que son DER reste proche de celui d'ECAPA (7/16). Sources : EXP-0013, EXP-0010.
- C10 (probable) : AMI surestime pyannote, qui l'a vu à l'entraînement : à empreinte identique, son avance sur la baseline est de 29,3 points sur AMI test, mais de 9,6 points en français (SUMM-RE test). Sources : EXP-0013, EXP-0001, EXP-0015, EXP-0007.

Graphique : `figures/systemes_reference.svg` (systèmes de référence, comme l'onglet Avancement).
