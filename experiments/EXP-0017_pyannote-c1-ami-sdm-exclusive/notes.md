---
id: EXP-0017
question: "La sortie exclusive de pyannote dégrade-t-elle AMI (D25, V1, règle 3) ?"
verdict: en_cours
decisions: [D25]
---

# EXP-0017 — pyannote-c1-ami-sdm-exclusive

## Observations factuelles

Sortie exclusive évaluée ; configuration d'EXP-0001 par ailleurs. La sortie habituelle de la même exécution (`rttm_habituelle/`) est identique à l'octet aux 34 RTTM d'EXP-0001.

| Jeu | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER |
|---|---|---|---|---|---|---|
| dev | 23,09 % | 16,08 | 3,12 | 3,89 | 14,45 % | 26,52 % |
| test | 24,48 % | 18,48 | 2,52 | 3,48 | 16,76 % | 30,28 % |

Écart à EXP-0001, bootstrap apparié (1 000 tirages, graine 0) :

| Jeu | Sans collar | Avec collar | Fichiers améliorés / dégradés |
|---|---|---|---|
| dev | +4,45 [+3,72 ; +5,00] | +3,30 [+2,60 ; +3,93] | 0 / 18 (sans collar) |
| test | +4,56 [+2,79 ; +6,32] | +3,55 [+1,87 ; +5,27] | 0 / 16 (sans collar) |

Temps conformes (MPS et CPU). Exécution concurrente des sessions B et E (D21, amendement du 01/11), sans relevé de charge.

## Interprétation

À rédiger par le cockpit.
