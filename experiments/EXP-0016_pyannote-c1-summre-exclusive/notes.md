---
id: EXP-0016
question: "La sortie exclusive de pyannote réduit-elle la fausse alarme sans perte nette sur SUMM-RE (D25, V1) ?"
verdict: ecarte
decisions: [D25]
---

# EXP-0016 — pyannote-c1-summre-exclusive

## Observations factuelles

Sortie exclusive évaluée ; configuration d'EXP-0007 par ailleurs. La sortie habituelle de la même exécution (`rttm_habituelle/`) est identique à l'octet aux 73 RTTM d'EXP-0007.

| Jeu | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER |
|---|---|---|---|---|---|---|
| dev | 29,18 % | 13,15 | 10,68 | 5,36 | 12,97 % | 31,94 % |
| test | 30,40 % | 15,55 | 8,30 | 6,55 | 17,78 % | 32,31 % |

Écart à EXP-0007, bootstrap apparié (1 000 tirages, graine 0) :

| Jeu | Sans collar | Avec collar | Fichiers améliorés / dégradés |
|---|---|---|---|
| dev | +3,18 [+2,45 ; +3,92] | +2,21 [+1,56 ; +2,90] | 1 / 35 (sans collar) |
| test | +4,10 [+3,24 ; +5,03] | +2,97 [+2,21 ; +3,81] | 1 / 36 (sans collar) |

Composantes sur test, EXP-0016 contre EXP-0007 : parole manquée 15,55 contre 7,15 ; fausse alarme 8,30 contre 11,28 ; confusion 6,55 contre 7,87. Nombre de groupes de VBx consigné par fichier, aucun KMeans.

Temps : exécution MPS non conforme (un relevé sur batterie à 21:12:19, 17 s hors secteur d'après `pmset -g log`) ; mesure CPU conforme (RTF 0,8426). Exécution concurrente des sessions B et E (D21, amendement du 01/11), sans relevé de charge.

## Interprétation (cockpit)

La sortie exclusive dégrade nettement SUMM-RE test (+4,10 points, IC [+3,24 ; +5,03], 36 fichiers sur 37 moins bons). Elle retire bien 3 points de fausse alarme, mais en ajoute 8,4 de parole manquée : le chevauchement réel de SUMM-RE pèse beaucoup plus que le faux chevauchement produit par pyannote. Le DER des zones sans chevauchement baisse (23,6 → 20,5 %), celui des zones de chevauchement s'effondre (33,2 → 55,7 %). La variante V1 de D25 est écartée par sa règle 1, et la bascule exclusive de l'interface (R-U12) est abandonnée. L'effort de D25 se reporte sur V2 (détection fine en post-traitement), qui vise les pauses pontées sans toucher au chevauchement.
