# EXP-0008 — pyannote community-1, nombre de locuteurs oracle par fichier, SUMM-RE (dev et test)

## Observations factuelles

Rédigées par le cockpit le 29/10/2026. Référence : EXP-0007 ; variable : nombre de locuteurs oracle par fichier.

| Mesure | dev | test | Zoom dev | Zoom test |
|---|---|---|---|---|
| DER sans collar | 26,50 % (EXP-0007 : 26,00) | 25,58 % (26,30) | 20,74 % (17,19) | 18,69 % (17,39) |
| Écart à EXP-0007, IC à 95 % | +0,49 [+0,00 ; +1,18] | −0,72 [−3,22 ; +0,89] | +3,56 [+0,00 ; +8,43] | +1,29 [−1,46 ; +4,91] |
| Fichiers améliorés / dégradés / égaux | 0 / 3 / 33 | 3 / 3 / 31 | | |

Seules changent les 9 réunions où EXP-0007 se trompait sur le nombre. Le gain sur le test vient presque entièrement de 080b_EBDH (3 → 2 estimés ; 66,01 → 32,80 %). Les plus fortes dégradations : 020c_EBPZ (16,82 → 28,60 %), 020b_EBDZ (18,47 → 25,09 %), 019a_EARD (32,21 → 41,27 % ; JER 34,9 → 53,2 %). Environ la moitié de l'exécution a tourné sur batterie (Mac débranché de 15 h 14 à 16 h 25) : le RTF d'EXP-0008 n'est pas conforme au protocole §3.5. Les métriques de diarisation n'en dépendent pas.

## Interprétation (cockpit)

**Le même constat qu'à AMI, sur des réunions françaises à 2 à 4 participants.** Imposer le bon nombre de locuteurs ne fait rien gagner en moyenne : l'écart n'est pas significatif sur le test, et il est légèrement défavorable sur le dev. Il corrige un échec franc (080b_EBDH, −33 points), mais il dégrade autant de réunions qu'il en améliore. Le pire cas est les réunions Zoom, où forcer le quatrième groupe découpe la parole des autres locuteurs. Un oracle est une borne supérieure de ce qu'une meilleure estimation pourrait apporter : la marge de l'amélioration n° 1 est donc quasi nulle sur SUMM-RE. Selon l'amendement de D9, il reste à confirmer ce constat sur le corpus maison, dont une réunion compte 4 à 6 personnes.

Le RTF de cette expérience n'est pas utilisé : c'est un diagnostic, pas une pipeline candidate au rendu. Aucune nouvelle exécution n'est nécessaire.
