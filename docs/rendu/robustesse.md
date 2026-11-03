# Robustesse (D24)

SUMM-RE test dégradé, références et UEM inchangés ; une expérience par moteur, un jeu évalué par condition (`results_summre-<condition>_test.json`). Écart au propre : DER dans la condition moins DER sur l'audio propre, sur les mêmes réunions, en points, intervalle de confiance à 95 % par bootstrap apparié sur les fichiers (1 000 tirages, graine 0). Propre : le jeu propre de l'expérience s'il existe, sinon le test de SUMM-RE de sa référence déclarée.

| Moteur | Condition | DER sans collar | DER collar 0,25 s | Écart au propre sans collar [IC 95 %] | Écart au propre collar 0,25 s [IC 95 %] | Réunions améliorées / dégradées (sans collar) |
|---|---|---|---|---|---|---|
| pyannote community-1 — EXP-0020 | propre (EXP-0007) | 26,30 % | 14,82 % | — | — | — |
| pyannote community-1 — EXP-0020 | `rev04` (réverbération, RT60 visé 0,4 s) | 28,78 % | 17,44 % | +2,49 [+0,77 ; +4,36] | +2,63 [+0,85 ; +4,82] | 15 / 22 sur 37 |
| pyannote community-1 — EXP-0020 | `rev08` (réverbération, RT60 visé 0,8 s) | 41,24 % | 28,42 % | +14,94 [+11,25 ; +18,47] | +13,60 [+9,76 ; +17,65] | 0 / 37 sur 37 |
| pyannote community-1 — EXP-0020 | `bru15` (bruit, RSB 15 dB) | 26,83 % | 15,18 % | +0,53 [+0,25 ; +0,87] | +0,36 [+0,11 ; +0,66] | 15 / 22 sur 37 |
| pyannote community-1 — EXP-0020 | `bru05` (bruit, RSB 5 dB) | 30,15 % | 18,46 % | +3,85 [+1,97 ; +6,02] | +3,64 [+1,67 ; +5,96] | 7 / 30 sur 37 |
| pyannote community-1 — EXP-0020 | `cod16` (codec Opus 16 kbit/s) | 25,51 % | 14,70 % | −0,79 [−1,57 ; +0,27] | −0,12 [−0,91 ; +1,05] | 31 / 6 sur 37 |
| pyannote community-1 — EXP-0020 | `cod08` (codec Opus 8 kbit/s) | 30,24 % | 21,98 % | +3,94 [+0,63 ; +7,47] | +7,17 [+3,72 ; +11,27] | 17 / 20 sur 37 |
| pyannote community-1 — EXP-0020 | `salle` (réverbération, RT60 visé 0,6 s et bruit, RSB 10 dB) | 41,23 % | 29,19 % | +14,93 [+11,45 ; +18,76] | +14,38 [+10,43 ; +18,83] | 0 / 37 sur 37 |
| Baseline ECAPA — EXP-0021 | propre (EXP-0012) | 33,42 % | 24,42 % | — | — | — |
| Baseline ECAPA — EXP-0021 | `rev04` (réverbération, RT60 visé 0,4 s) | 35,45 % | 25,46 % | +2,04 [+0,15 ; +3,67] | +1,05 [−1,21 ; +2,99] | 8 / 29 sur 37 |
| Baseline ECAPA — EXP-0021 | `rev08` (réverbération, RT60 visé 0,8 s) | 40,81 % | 30,13 % | +7,39 [+5,27 ; +9,56] | +5,71 [+3,42 ; +8,25] | 2 / 35 sur 37 |
| Baseline ECAPA — EXP-0021 | `bru15` (bruit, RSB 15 dB) | 39,13 % | 30,80 % | +5,72 [+4,27 ; +7,37] | +6,38 [+4,76 ; +8,36] | 1 / 36 sur 37 |
| Baseline ECAPA — EXP-0021 | `bru05` (bruit, RSB 5 dB) | 47,38 % | 38,38 % | +13,96 [+11,48 ; +16,82] | +13,96 [+10,85 ; +17,43] | 1 / 36 sur 37 |
| Baseline ECAPA — EXP-0021 | `cod16` (codec Opus 16 kbit/s) | 32,71 % | 23,54 % | −0,71 [−1,22 ; −0,20] | −0,87 [−1,33 ; −0,41] | 26 / 11 sur 37 |
| Baseline ECAPA — EXP-0021 | `cod08` (codec Opus 8 kbit/s) | 38,43 % | 29,54 % | +5,01 [+2,92 ; +7,17] | +5,12 [+2,86 ; +7,54] | 7 / 30 sur 37 |
| Baseline ECAPA — EXP-0021 | `salle` (réverbération, RT60 visé 0,6 s et bruit, RSB 10 dB) | 49,21 % | 41,47 % | +15,79 [+13,62 ; +18,12] | +17,06 [+14,36 ; +20,04] | 1 / 36 sur 37 |
| nemotron3-diarization — EXP-0028 | `rev04` (réverbération, RT60 visé 0,4 s) | 14,84 % | 11,09 % | propre introuvable | — | — |
| nemotron3-diarization — EXP-0028 | `rev08` (réverbération, RT60 visé 0,8 s) | 16,04 % | 11,71 % | propre introuvable | — | — |
| nemotron3-diarization — EXP-0028 | `bru15` (bruit, RSB 15 dB) | 16,08 % | 12,45 % | propre introuvable | — | — |
| nemotron3-diarization — EXP-0028 | `bru05` (bruit, RSB 5 dB) | 18,46 % | 13,40 % | propre introuvable | — | — |
| nemotron3-diarization — EXP-0028 | `cod16` (codec Opus 16 kbit/s) | 14,99 % | 11,39 % | propre introuvable | — | — |
| nemotron3-diarization — EXP-0028 | `cod08` (codec Opus 8 kbit/s) | 16,44 % | 12,60 % | propre introuvable | — | — |
| nemotron3-diarization — EXP-0028 | `salle` (réverbération, RT60 visé 0,6 s et bruit, RSB 10 dB) | 17,67 % | 12,74 % | propre introuvable | — | — |
| nemotron3-diarization — EXP-0035 | `rev04` (réverbération, RT60 visé 0,4 s) | 14,51 % | 10,91 % | propre introuvable | — | — |
| nemotron3-diarization — EXP-0035 | `rev08` (réverbération, RT60 visé 0,8 s) | 15,68 % | 11,42 % | propre introuvable | — | — |
| nemotron3-diarization — EXP-0035 | `bru15` (bruit, RSB 15 dB) | 15,64 % | 12,27 % | propre introuvable | — | — |
| nemotron3-diarization — EXP-0035 | `bru05` (bruit, RSB 5 dB) | 17,71 % | 12,88 % | propre introuvable | — | — |
| nemotron3-diarization — EXP-0035 | `cod16` (codec Opus 16 kbit/s) | 14,57 % | 11,15 % | propre introuvable | — | — |
| nemotron3-diarization — EXP-0035 | `cod08` (codec Opus 8 kbit/s) | 16,11 % | 12,41 % | propre introuvable | — | — |
| nemotron3-diarization — EXP-0035 | `salle` (réverbération, RT60 visé 0,6 s et bruit, RSB 10 dB) | 16,98 % | 12,27 % | propre introuvable | — | — |

## Sous-groupes : réunions Zoom et autres

Réunions Zoom : liste `data/splits/summre/zoom_test.txt` ; autres : le reste de SUMM-RE test. Une réunion Zoom réverbérée dans une seule salle est moins plausible : les deux groupes sont donnés à part (décision du cockpit du 02/11). Pas d'intervalle sous 5 réunions.

| Moteur | Condition | Zoom : écart sans collar | Zoom : écart collar 0,25 s | Zoom : réunions | Autres : écart sans collar [IC 95 %] | Autres : écart collar 0,25 s [IC 95 %] | Autres : réunions |
|---|---|---|---|---|---|---|---|
| pyannote community-1 — EXP-0020 | `rev04` | +1,68 | +0,97 | 3 | +2,54 [+0,73 ; +4,72] | +2,74 [+0,90 ; +5,33] | 34 |
| pyannote community-1 — EXP-0020 | `rev08` | +9,83 | +5,35 | 3 | +15,27 [+11,46 ; +19,02] | +14,16 [+9,94 ; +18,53] | 34 |
| pyannote community-1 — EXP-0020 | `bru15` | +2,10 | +1,68 | 3 | +0,43 [+0,15 ; +0,78] | +0,27 [+0,03 ; +0,58] | 34 |
| pyannote community-1 — EXP-0020 | `bru05` | +4,21 | +3,11 | 3 | +3,83 [+1,89 ; +6,19] | +3,68 [+1,67 ; +6,13] | 34 |
| pyannote community-1 — EXP-0020 | `cod16` | +0,73 | +0,56 | 3 | −0,89 [−1,75 ; +0,33] | −0,16 [−1,03 ; +1,11] | 34 |
| pyannote community-1 — EXP-0020 | `cod08` | +1,35 | +2,51 | 3 | +4,10 [+0,47 ; +8,16] | +7,48 [+3,67 ; +11,93] | 34 |
| pyannote community-1 — EXP-0020 | `salle` | +8,73 | +5,67 | 3 | +15,32 [+11,49 ; +19,45] | +14,97 [+10,85 ; +19,64] | 34 |
| Baseline ECAPA — EXP-0021 | `rev04` | +6,59 | +2,61 | 3 | +1,75 [−0,22 ; +3,43] | +0,94 [−1,37 ; +2,93] | 34 |
| Baseline ECAPA — EXP-0021 | `rev08` | +15,46 | +9,45 | 3 | +6,88 [+4,73 ; +9,28] | +5,46 [+2,80 ; +8,06] | 34 |
| Baseline ECAPA — EXP-0021 | `bru15` | +2,03 | +3,05 | 3 | +5,95 [+4,45 ; +7,56] | +6,61 [+4,88 ; +8,41] | 34 |
| Baseline ECAPA — EXP-0021 | `bru05` | +17,36 | +16,87 | 3 | +13,75 [+11,08 ; +16,63] | +13,77 [+10,52 ; +17,31] | 34 |
| Baseline ECAPA — EXP-0021 | `cod16` | +1,99 | +1,42 | 3 | −0,88 [−1,39 ; −0,36] | −1,03 [−1,47 ; −0,55] | 34 |
| Baseline ECAPA — EXP-0021 | `cod08` | −1,03 | −0,51 | 3 | +5,39 [+3,25 ; +7,56] | +5,50 [+3,21 ; +8,10] | 34 |
| Baseline ECAPA — EXP-0021 | `salle` | +6,94 | +6,55 | 3 | +16,35 [+14,25 ; +18,70] | +17,77 [+15,07 ; +20,70] | 34 |

## Comparaison à pyannote community-1, à condition égale (D24 §3)

Écart : DER du moteur moins DER de pyannote community-1 — EXP-0020, dans la même condition et sur les mêmes réunions, en points, intervalle de confiance à 95 % par bootstrap apparié (1 000 tirages, graine 0) ; un écart négatif signifie que le moteur fait mieux que pyannote.

| Moteur | Condition | Écart à pyannote community-1 — EXP-0020, sans collar [IC 95 %] | Écart à pyannote community-1 — EXP-0020, collar 0,25 s [IC 95 %] | Réunions où le moteur fait mieux / moins bien que pyannote (sans collar) |
|---|---|---|---|---|
| Baseline ECAPA — EXP-0021 | propre | +7,12 [+3,72 ; +9,77] | +9,60 [+6,59 ; +12,40] | 4 / 33 sur 37 |
| Baseline ECAPA — EXP-0021 | `rev04` | +6,67 [+3,61 ; +9,34] | +8,02 [+5,03 ; +10,72] | 3 / 34 sur 37 |
| Baseline ECAPA — EXP-0021 | `rev08` | −0,44 [−3,64 ; +2,83] | +1,71 [−1,81 ; +5,21] | 22 / 15 sur 37 |
| Baseline ECAPA — EXP-0021 | `bru15` | +12,30 [+9,36 ; +14,77] | +15,62 [+12,62 ; +18,45] | 2 / 35 sur 37 |
| Baseline ECAPA — EXP-0021 | `bru05` | +17,23 [+14,65 ; +19,57] | +19,92 [+17,04 ; +22,57] | 1 / 36 sur 37 |
| Baseline ECAPA — EXP-0021 | `cod16` | +7,20 [+3,77 ; +10,10] | +8,84 [+5,67 ; +11,78] | 4 / 33 sur 37 |
| Baseline ECAPA — EXP-0021 | `cod08` | +8,19 [+4,77 ; +11,55] | +7,55 [+3,65 ; +11,35] | 6 / 31 sur 37 |
| Baseline ECAPA — EXP-0021 | `salle` | +7,98 [+4,86 ; +10,91] | +12,28 [+8,79 ; +15,61] | 6 / 31 sur 37 |
| nemotron3-diarization — EXP-0028 | `rev04` | −13,94 [−17,92 ; −10,28] | −6,35 [−10,15 ; −3,19] | 36 / 1 sur 37 |
| nemotron3-diarization — EXP-0028 | `rev08` | −25,21 [−30,35 ; −20,00] | −16,70 [−22,08 ; −11,76] | 36 / 1 sur 37 |
| nemotron3-diarization — EXP-0028 | `bru15` | −10,75 [−14,63 ; −6,51] | −2,73 [−6,07 ; +0,71] | 35 / 2 sur 37 |
| nemotron3-diarization — EXP-0028 | `bru05` | −11,68 [−14,46 ; −9,08] | −5,06 [−7,57 ; −2,98] | 36 / 1 sur 37 |
| nemotron3-diarization — EXP-0028 | `cod16` | −10,52 [−13,71 ; −7,53] | −3,31 [−6,11 ; −0,96] | 36 / 1 sur 37 |
| nemotron3-diarization — EXP-0028 | `cod08` | −13,79 [−18,40 ; −9,47] | −9,38 [−14,05 ; −5,22] | 35 / 2 sur 37 |
| nemotron3-diarization — EXP-0028 | `salle` | −23,56 [−28,40 ; −18,73] | −16,45 [−21,71 ; −11,95] | 37 / 0 sur 37 |
| nemotron3-diarization — EXP-0035 | `rev04` | −14,27 [−18,20 ; −10,61] | −6,53 [−10,22 ; −3,42] | 36 / 1 sur 37 |
| nemotron3-diarization — EXP-0035 | `rev08` | −25,57 [−30,66 ; −20,36] | −16,99 [−22,42 ; −12,01] | 36 / 1 sur 37 |
| nemotron3-diarization — EXP-0035 | `bru15` | −11,19 [−15,04 ; −7,00] | −2,91 [−6,19 ; +0,49] | 35 / 2 sur 37 |
| nemotron3-diarization — EXP-0035 | `bru05` | −12,44 [−15,13 ; −9,96] | −5,58 [−8,08 ; −3,57] | 37 / 0 sur 37 |
| nemotron3-diarization — EXP-0035 | `cod16` | −10,94 [−14,09 ; −7,97] | −3,55 [−6,30 ; −1,28] | 36 / 1 sur 37 |
| nemotron3-diarization — EXP-0035 | `cod08` | −14,13 [−18,62 ; −9,89] | −9,57 [−14,16 ; −5,47] | 35 / 2 sur 37 |
| nemotron3-diarization — EXP-0035 | `salle` | −24,26 [−29,34 ; −19,43] | −16,92 [−22,36 ; −12,39] | 37 / 0 sur 37 |

**Sources.** Expériences (commit d'exécution) : EXP-0007 (`568efbb`), EXP-0012 (`3856355`), EXP-0020 (`fbbff49`), EXP-0021 (`fbbff49`), EXP-0028 (`0358ccf`), EXP-0035 (`f78a220`).
Fichiers : `results/leaderboard.csv` (contrôle), `results_<corpus>_<partition>.json` et `per_file_<corpus>_<partition>.csv` de chaque expérience.
Conditions : `configs/summre_degrade.yaml`.

**Constats liés** (`docs/constats.yaml`, version 1 du 2026-11-04) :

- C01 (certain) : La détection par énergie est le premier défaut de la baseline : avec ECAPA, la parole manquée fait 32,3 des 45,9 points de DER sur AMI test, et 21,9 des 33,4 points sur SUMM-RE test. Sources : EXP-0010, EXP-0012.
- C04 (certain) : En français (SUMM-RE test), la fausse alarme est la première erreur de pyannote : 11,3 des 26,3 points de DER ; 34 à 44 % se trouve dans des pauses de 1 s au plus d'un même locuteur, que pyannote recouvre, et environ un quart vient de faux chevauchements. Sources : EXP-0007, A-0001.
- C05 (certain) : Remplacer les MFCC par des empreintes ECAPA fait tomber la confusion de la baseline de 27,1 à 8,6 points sur AMI test, et de 24,4 à 8,5 sur SUMM-RE test. Sources : EXP-0002, EXP-0010, EXP-0009, EXP-0012.
- C10 (probable) : AMI surestime pyannote, qui l'a vu à l'entraînement : à empreinte identique, son avance sur la baseline est de 29,3 points sur AMI test, mais de 9,6 points en français (SUMM-RE test). Sources : EXP-0013, EXP-0001, EXP-0015, EXP-0007.
- C13 (certain) : La réverbération forte est la faiblesse de pyannote : en salle simulée à RT60 ≈ 0,9 s, son DER passe de 26,3 à 41,2 % sur SUMM-RE test, presque entièrement en parole manquée (7,2 → 23,2 points), et il perd son avance sur la baseline (+0,4 point, non significatif). Il résiste en revanche au bruit et au codec à 16 kbit/s (moins d'un point). Sources : EXP-0020, EXP-0021, A-0002.
- C14 (certain) : Le bruit est la faiblesse de la baseline : sa détection par énergie perd de la parole (+14,0 points de DER à 5 dB de RSB), alors que la réverbération la gêne moins (+7,4 points). Sources : EXP-0021, A-0002.
- C15 (certain) : Un codec de visio à bas débit (Opus 8 kbit/s) dégrade surtout l'attribution : la confusion de pyannote passe de 7,9 à 14,4 points, et des locuteurs sont fusionnés (13 % de l'erreur vient d'un locuteur de référence non apparié). Sources : EXP-0020, A-0003.
- C18 (certain) : En français, Nemotron 3 Diarization (bout en bout, 100 M de paramètres) divise presque par deux le DER de pyannote sur SUMM-RE test (14,6 contre 26,3 %) et résiste à toutes les dégradations de D24 (14,8 à 18,5 %), y compris la réverbération forte où pyannote atteint 41,2 % ; son gain vient de la fausse alarme et de la confusion, presque nulles. Sources : EXP-0027, EXP-0028.
- C21 (certain) : Régler le seuil de décision de Nemotron 3 sur SUMM-RE dev (0,35 au lieu de 0,5) l'améliore un peu partout, en français (−0,4 point), sur AMI (−1,0) et dans les 7 conditions dégradées : il manque moins de parole, au prix d'un peu plus de fausse alarme. Sources : EXP-0033, EXP-0034, EXP-0035.
