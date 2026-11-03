# Systèmes par corpus

Partition test, condition réaliste (nombre de locuteurs non donné, détection non oracle). DER en %, chevauchements comptés ; composantes sans collar. Nombre de locuteurs exact : réunions où le nombre estimé égale celui de la référence.

## SUMM-RE

| Système | Expérience | Verdict | DER sans collar | DER collar 0,25 s | Parole manquée | Fausse alarme | Confusion | Nombre de locuteurs exact |
|---|---|---|---|---|---|---|---|---|
| pyannote community-1 | EXP-0007 (pyannote-c1-summre) | référence | 26,30 % | 14,82 % | 7,15 | 11,28 | 7,87 | 31/37 (83,8 %) |
| Baseline MFCC | EXP-0009 (baseline-mfcc-summre) | référence | 49,36 % | 42,66 % | 21,87 | 3,08 | 24,42 | 17/37 (45,9 %) |
| Baseline ECAPA | EXP-0012 (baseline-ecapa-summre) | retenu | 33,42 % | 24,42 % | 21,87 | 3,08 | 8,47 | 28/37 (75,7 %) |
| Baseline WeSpeaker | EXP-0015 (baseline-wespeaker-summre) | écarté | 35,86 % | 26,74 % | 21,87 | 3,08 | 10,92 | 23/37 (62,2 %) |
| pyannote community-1 (sortie) | EXP-0016 (pyannote-c1-summre-exclusive) | écarté | 30,40 % | 17,78 % | 15,55 | 8,30 | 6,55 | 31/37 (83,8 %) |
| pyannote community-1 (mode_n_locuteurs) | EXP-0018 (pyannote-c1-summre-borne-2-6) | retenu | 25,82 % | 14,31 % | 7,15 | 11,28 | 7,39 | 31/37 (83,8 %) |
| pyannote-community-1-silero | EXP-0022 (pyannote-c1-summre-silero) | écarté | 23,70 % | 15,10 % | 10,83 | 5,49 | 7,38 | 31/37 (83,8 %) |
| pyannote-community-1-silero (post_traitement) | EXP-0023 (pyannote-c1-summre-exclusive-silero) | écarté | 27,90 % | 18,09 % | 19,21 | 2,66 | 6,04 | 31/37 (83,8 %) |
| nemotron3-diarization | EXP-0027 (nemotron3-summre) | en cours | 14,62 % | 11,22 % | 11,61 | 1,91 | 1,10 | 32/37 (86,5 %) |
| nemotron3-diarization (normalisation_niveau) | EXP-0030 (nemotron3-summre-niveau) | écarté | 15,34 % | 11,99 % | 11,65 | 1,89 | 1,81 | 31/37 (83,8 %) |
| pyannote community-1 (normalisation_niveau) | EXP-0032 (pyannote-c1-summre-niveau) | informatif | 26,29 % | 14,81 % | 7,16 | 11,28 | 7,86 | 31/37 (83,8 %) |
| nemotron3-diarization (seuil) | EXP-0033 (nemotron3-summre-seuil) | retenu | 14,25 % | 11,07 % | 10,61 | 2,53 | 1,11 | 32/37 (86,5 %) |

Écarts (SUMM-RE, test) : DER de l'expérience moins DER du système comparé, en points, intervalle de confiance à 95 % par bootstrap apparié sur les fichiers (1 000 tirages, graine 0) ; un écart négatif est une amélioration. Première comparaison, principale : à la référence déclarée de l'expérience, qui ne diffère que par la variable modifiée (protocole, D9). Seconde comparaison : à pyannote community-1 (EXP-0007), moteur de démonstration, sur le même corpus ; ce n'est pas une comparaison à une seule variable (moteur, détection, représentation et réglages peuvent tous différer).

| Expérience | Référence déclarée (variable modifiée) | Écart à la référence déclarée, sans collar [IC 95 %] | Écart à la référence déclarée, collar 0,25 s [IC 95 %] | Fichiers où l'expérience fait mieux / moins bien que sa référence (sans collar) | Écart à pyannote community-1 (EXP-0007), sans collar [IC 95 %] | Écart à pyannote community-1 (EXP-0007), collar 0,25 s [IC 95 %] | Fichiers où l'expérience fait mieux / moins bien que pyannote community-1 (EXP-0007) (sans collar) |
|---|---|---|---|---|---|---|---|
| EXP-0007 | — | — | — | — | — (elle-même) | — | — |
| EXP-0009 | — | — | — | — | +23,06 [+19,05 ; +26,92] | +27,85 [+22,89 ; +32,71] | 4 / 33 sur 37 |
| EXP-0012 | EXP-0009 (representation) | −15,95 [−19,49 ; −12,53] | −18,25 [−22,58 ; −14,02] | 36 / 1 sur 37 | +7,12 [+3,72 ; +9,77] | +9,60 [+6,59 ; +12,40] | 4 / 33 sur 37 |
| EXP-0015 | EXP-0009 (representation) | −13,50 [−17,68 ; −9,78] | −15,92 [−20,78 ; −11,44] | 32 / 5 sur 37 | +9,56 [+6,02 ; +12,44] | +11,92 [+8,63 ; +14,88] | 4 / 33 sur 37 |
| EXP-0016 | EXP-0007 (sortie) | +4,10 [+3,24 ; +5,03] | +2,97 [+2,21 ; +3,81] | 1 / 36 sur 37 | +4,10 [+3,24 ; +5,03] | +2,97 [+2,21 ; +3,81] | 1 / 36 sur 37 |
| EXP-0018 | EXP-0007 (mode_n_locuteurs) | −0,48 [−1,48 ; +0,00] | −0,50 [−1,58 ; +0,00] | 1 / 0 sur 37 | −0,48 [−1,48 ; +0,00] | −0,50 [−1,58 ; +0,00] | 1 / 0 sur 37 |
| EXP-0022 | EXP-0007 (post_traitement) | −2,60 [−3,71 ; −1,64] | +0,29 [−0,50 ; +0,97] | 30 / 7 sur 37 | −2,60 [−3,71 ; −1,64] | +0,29 [−0,50 ; +0,97] | 30 / 7 sur 37 |
| EXP-0023 | EXP-0016 (post_traitement) | −2,49 [−3,62 ; −1,55] | +0,31 [−0,48 ; +0,99] | 30 / 7 sur 37 | +1,60 [+0,14 ; +2,92] | +3,27 [+2,29 ; +4,25] | 14 / 23 sur 37 |
| EXP-0027 | EXP-0007 (moteur) | −11,68 [−15,26 ; −8,33] | −3,59 [−6,59 ; −1,23] | 36 / 1 sur 37 | −11,68 [−15,26 ; −8,33] | −3,59 [−6,59 ; −1,23] | 36 / 1 sur 37 |
| EXP-0030 | EXP-0027 (normalisation_niveau) | +0,73 [−0,06 ; +1,94] | +0,77 [−0,07 ; +2,05] | 23 / 14 sur 37 | −10,95 [−14,79 ; −7,27] | −2,82 [−6,17 ; −0,06] | 34 / 3 sur 37 |
| EXP-0032 | EXP-0007 (normalisation_niveau) | −0,00 [−0,01 ; +0,00] | −0,01 [−0,02 ; +0,00] | 18 / 12 sur 37 | −0,00 [−0,01 ; +0,00] | −0,01 [−0,02 ; +0,00] | 18 / 12 sur 37 |
| EXP-0033 | EXP-0027 (seuil) | −0,37 [−0,45 ; −0,28] | −0,16 [−0,24 ; −0,08] | 35 / 2 sur 37 | −12,05 [−15,66 ; −8,65] | −3,75 [−6,76 ; −1,36] | 36 / 1 sur 37 |

## AMI (SDM)

| Système | Expérience | Verdict | DER sans collar | DER collar 0,25 s | Parole manquée | Fausse alarme | Confusion | Nombre de locuteurs exact |
|---|---|---|---|---|---|---|---|---|
| pyannote community-1 | EXP-0001 (pyannote-c1-ami-sdm) | référence | 19,92 % | 13,21 % | 11,16 | 3,81 | 4,94 | 12/16 (75,0 %) |
| Baseline MFCC | EXP-0002 (baseline-mfcc-ami-sdm) | référence | 64,38 % | 61,21 % | 32,28 | 4,99 | 27,11 | 0/16 (0,0 %) |
| Baseline ECAPA | EXP-0010 (baseline-ecapa-ami-sdm) | retenu | 45,88 % | 40,85 % | 32,27 | 4,99 | 8,63 | 7/16 (43,8 %) |
| Baseline WeSpeaker | EXP-0013 (baseline-wespeaker-ami-sdm) | écarté | 49,17 % | 43,95 % | 32,27 | 4,99 | 11,90 | 0/16 (0,0 %) |
| pyannote community-1 (sortie) | EXP-0017 (pyannote-c1-ami-sdm-exclusive) | écarté | 24,48 % | 16,76 % | 18,48 | 2,52 | 3,48 | 12/16 (75,0 %) |
| pyannote community-1 (mode_n_locuteurs) | EXP-0019 (pyannote-c1-ami-sdm-borne-2-6) | informatif | 19,92 % | 13,21 % | 11,16 | 3,81 | 4,94 | 12/16 (75,0 %) |
| pyannote-community-1-silero | EXP-0024 (pyannote-c1-ami-sdm-silero) | écarté | 42,05 % | 37,55 % | 37,76 | 1,32 | 2,97 | 12/16 (75,0 %) |
| pyannote-community-1-silero (post_traitement) | EXP-0025 (pyannote-c1-ami-sdm-exclusive-silero) | écarté | 46,00 % | 40,63 % | 43,92 | 0,37 | 1,70 | 12/16 (75,0 %) |
| nemotron3-diarization | EXP-0026 (nemotron3-ami-sdm) | en cours | 27,47 % | 25,15 % | 24,93 | 1,47 | 1,08 | 14/16 (87,5 %) |
| nemotron3-diarization (normalisation_niveau) | EXP-0029 (nemotron3-ami-sdm-niveau) | écarté | 27,97 % | 25,73 % | 24,91 | 1,50 | 1,56 | 15/16 (93,8 %) |
| pyannote community-1 (normalisation_niveau) | EXP-0031 (pyannote-c1-ami-sdm-niveau) | informatif | 19,96 % | 13,20 % | 11,13 | 3,86 | 4,97 | 12/16 (75,0 %) |
| nemotron3-diarization (seuil) | EXP-0034 (nemotron3-ami-sdm-seuil) | retenu | 26,44 % | 24,12 % | 22,51 | 2,57 | 1,36 | 14/16 (87,5 %) |

Écarts (AMI (SDM), test) : DER de l'expérience moins DER du système comparé, en points, intervalle de confiance à 95 % par bootstrap apparié sur les fichiers (1 000 tirages, graine 0) ; un écart négatif est une amélioration. Première comparaison, principale : à la référence déclarée de l'expérience, qui ne diffère que par la variable modifiée (protocole, D9). Seconde comparaison : à pyannote community-1 (EXP-0001), moteur de démonstration, sur le même corpus ; ce n'est pas une comparaison à une seule variable (moteur, détection, représentation et réglages peuvent tous différer).

| Expérience | Référence déclarée (variable modifiée) | Écart à la référence déclarée, sans collar [IC 95 %] | Écart à la référence déclarée, collar 0,25 s [IC 95 %] | Fichiers où l'expérience fait mieux / moins bien que sa référence (sans collar) | Écart à pyannote community-1 (EXP-0001), sans collar [IC 95 %] | Écart à pyannote community-1 (EXP-0001), collar 0,25 s [IC 95 %] | Fichiers où l'expérience fait mieux / moins bien que pyannote community-1 (EXP-0001) (sans collar) |
|---|---|---|---|---|---|---|---|
| EXP-0001 | — | — | — | — | — (elle-même) | — | — |
| EXP-0002 | — | — | — | — | +44,46 [+40,53 ; +48,35] | +48,00 [+43,43 ; +52,43] | 0 / 16 sur 16 |
| EXP-0010 | EXP-0002 (representation) | −18,50 [−23,70 ; −13,83] | −20,36 [−25,93 ; −15,06] | 15 / 1 sur 16 | +25,96 [+22,93 ; +28,53] | +27,64 [+24,51 ; +30,45] | 0 / 16 sur 16 |
| EXP-0013 | EXP-0002 (representation) | −15,22 [−20,10 ; −10,54] | −17,26 [−22,75 ; −11,85] | 14 / 2 sur 16 | +29,24 [+25,95 ; +32,42] | +30,74 [+27,18 ; +34,47] | 0 / 16 sur 16 |
| EXP-0017 | EXP-0001 (sortie) | +4,56 [+2,79 ; +6,32] | +3,55 [+1,87 ; +5,27] | 0 / 16 sur 16 | +4,56 [+2,79 ; +6,32] | +3,55 [+1,87 ; +5,27] | 0 / 16 sur 16 |
| EXP-0019 | EXP-0001 (mode_n_locuteurs) | +0,00 [+0,00 ; +0,00] | +0,00 [+0,00 ; +0,00] | 0 / 0 sur 16 | +0,00 [+0,00 ; +0,00] | +0,00 [+0,00 ; +0,00] | 0 / 0 sur 16 |
| EXP-0024 | EXP-0001 (post_traitement) | +22,13 [+16,90 ; +27,12] | +24,34 [+18,59 ; +30,00] | 0 / 16 sur 16 | +22,13 [+16,90 ; +27,12] | +24,34 [+18,59 ; +30,00] | 0 / 16 sur 16 |
| EXP-0025 | EXP-0017 (post_traitement) | +21,51 [+16,44 ; +26,56] | +23,87 [+18,18 ; +29,56] | 0 / 16 sur 16 | +26,07 [+20,53 ; +31,04] | +27,42 [+21,51 ; +32,84] | 0 / 16 sur 16 |
| EXP-0026 | EXP-0001 (moteur) | +7,55 [+5,47 ; +9,45] | +11,94 [+9,98 ; +13,78] | 1 / 15 sur 16 | +7,55 [+5,47 ; +9,45] | +11,94 [+9,98 ; +13,78] | 1 / 15 sur 16 |
| EXP-0029 | EXP-0026 (normalisation_niveau) | +0,50 [−0,35 ; +2,07] | +0,58 [−0,35 ; +2,31] | 9 / 7 sur 16 | +8,05 [+5,91 ; +10,24] | +12,51 [+10,29 ; +14,75] | 1 / 15 sur 16 |
| EXP-0031 | EXP-0001 (normalisation_niveau) | +0,04 [−0,06 ; +0,15] | −0,01 [−0,11 ; +0,10] | 7 / 8 sur 16 | +0,04 [−0,06 ; +0,15] | −0,01 [−0,11 ; +0,10] | 7 / 8 sur 16 |
| EXP-0034 | EXP-0026 (seuil) | −1,04 [−1,39 ; −0,65] | −1,03 [−1,35 ; −0,70] | 14 / 2 sur 16 | +6,51 [+4,77 ; +8,23] | +10,91 [+9,11 ; +12,69] | 1 / 15 sur 16 |

**Sources.** Expériences (commit d'exécution) : EXP-0001 (`d9f177a`), EXP-0002 (`540bb5e`), EXP-0007 (`568efbb`), EXP-0009 (`568efbb`), EXP-0010 (`fba633a`), EXP-0012 (`3856355`), EXP-0013 (`2a08ff7`), EXP-0015 (`5bcb295`), EXP-0016 (`12a67a6`), EXP-0017 (`4dc5e63`), EXP-0018 (`2fcf766`), EXP-0019 (`45b309d`), EXP-0022 (`2d81861`), EXP-0023 (`2d81861`), EXP-0024 (`2d81861`), EXP-0025 (`2d81861`), EXP-0026 (`0358ccf`), EXP-0027 (`0358ccf`), EXP-0029 (`0269b68`), EXP-0030 (`0269b68`), EXP-0031 (`0269b68`), EXP-0032 (`0269b68`), EXP-0033 (`f78a220`), EXP-0034 (`f78a220`).
Fichiers : `results/leaderboard.csv` (contrôle), `results_<corpus>_<partition>.json` et `per_file_<corpus>_<partition>.csv` de chaque expérience.

**Constats liés** (`docs/constats.yaml`, version 1 du 2026-11-04) :

- C01 (certain) : La détection par énergie est le premier défaut de la baseline : avec ECAPA, la parole manquée fait 32,3 des 45,9 points de DER sur AMI test, et 21,9 des 33,4 points sur SUMM-RE test. Sources : EXP-0010, EXP-0012.
- C02 (certain) : Une détection de parole parfaite retire 15,3 points de DER à la baseline MFCC sur AMI test (64,4 → 49,1 %). Sources : EXP-0002, EXP-0004.
- C03 (certain) : À empreinte identique (WeSpeaker), pyannote devance la baseline de 29,3 points sur AMI test, dont 21,1 de parole manquée : son avance vient surtout de la segmentation neuronale, qui détecte la parole et le chevauchement. Sources : EXP-0001, EXP-0013.
- C04 (certain) : En français (SUMM-RE test), la fausse alarme est la première erreur de pyannote : 11,3 des 26,3 points de DER ; 34 à 44 % se trouve dans des pauses de 1 s au plus d'un même locuteur, que pyannote recouvre, et environ un quart vient de faux chevauchements. Sources : EXP-0007, A-0001.
- C05 (certain) : Remplacer les MFCC par des empreintes ECAPA fait tomber la confusion de la baseline de 27,1 à 8,6 points sur AMI test, et de 24,4 à 8,5 sur SUMM-RE test. Sources : EXP-0002, EXP-0010, EXP-0009, EXP-0012.
- C06 (certain) : Sous oracles, ECAPA et WeSpeaker ne se distinguent pas (écart +2,2 points, IC à 95 % [−0,1 ; +4,6]) ; en condition réaliste, WeSpeaker est légèrement moins bon (+2,5 à +3,3 points). Sources : EXP-0011, EXP-0014, EXP-0013, EXP-0015.
- C08 (certain) : Avec le seuil réglé pour minimiser le DER, la baseline WeSpeaker ne trouve jamais le bon nombre de locuteurs sur AMI test (0/16), alors que son DER reste proche de celui d'ECAPA (7/16). Sources : EXP-0013, EXP-0010.
- C10 (probable) : AMI surestime pyannote, qui l'a vu à l'entraînement : à empreinte identique, son avance sur la baseline est de 29,3 points sur AMI test, mais de 9,6 points en français (SUMM-RE test). Sources : EXP-0013, EXP-0001, EXP-0015, EXP-0007.
- C11 (certain) : Sur des réunions, le chevauchement réel pèse plus que le faux chevauchement : la sortie exclusive de pyannote retire 3 points de fausse alarme sur SUMM-RE test, mais ajoute 8,4 points de parole manquée (DER +4,1 sur SUMM-RE, +4,6 sur AMI, significatif). Sources : EXP-0016, EXP-0017.
- C12 (certain) : Borner le nombre de locuteurs entre 2 et 6 ne change qu'une réunion sur 73, celle où VBx n'en trouvait qu'un ; l'effet global n'est pas significatif (−0,48 point sur SUMM-RE test). Sources : EXP-0018, EXP-0019.
- C16 (certain) : Un post-traitement par Silero VAD réglé sur SUMM-RE (micros-casques) réduit le DER de pyannote de 2,6 points en français, mais l'augmente de 22 points sur AMI (micro distant) en coupant la parole lointaine : un réglage fait en champ proche ne se transporte pas en champ lointain. Sources : EXP-0022, EXP-0024.
- C18 (certain) : En français, Nemotron 3 Diarization (bout en bout, 100 M de paramètres) divise presque par deux le DER de pyannote sur SUMM-RE test (14,6 contre 26,3 %) et résiste à toutes les dégradations de D24 (14,8 à 18,5 %), y compris la réverbération forte où pyannote atteint 41,2 % ; son gain vient de la fausse alarme et de la confusion, presque nulles. Sources : EXP-0027, EXP-0028.
- C19 (certain) : Sur AMI (anglais, micro distant), Nemotron 3 fait moins bien que pyannote (27,5 contre 19,9 %) : il manque environ deux fois plus de parole, même hors chevauchement. Ni la durée des réunions, ni le niveau d'enregistrement, ni le seuil de décision ne l'expliquent : avec le seuil réglé, l'écart reste de +6,5 points. Sources : EXP-0026, EXP-0034, A-0004.
- C20 (probable) : La parole manquée de Nemotron 3 sur AMI est fortement corrélée au niveau d'enregistrement (rang −0,70), mais amplifier le signal jusqu'à +19 dB ne la change pas : le niveau n'est pas la cause. Dans toutes les salles d'AMI, Nemotron 3 manque environ 2,4 fois plus de parole que pyannote : il est globalement plus prudent, et le champ lointain l'accentue. Sources : A-0004, EXP-0029, EXP-0031.
- C21 (certain) : Régler le seuil de décision de Nemotron 3 sur SUMM-RE dev (0,35 au lieu de 0,5) l'améliore un peu partout, en français (−0,4 point), sur AMI (−1,0) et dans les 7 conditions dégradées : il manque moins de parole, au prix d'un peu plus de fausse alarme. Sources : EXP-0033, EXP-0034, EXP-0035.

Graphique : `figures/systemes_reference.svg` (systèmes de référence, comme l'onglet Avancement).
