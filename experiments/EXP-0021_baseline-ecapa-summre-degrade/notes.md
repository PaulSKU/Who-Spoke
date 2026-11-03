---
id: EXP-0021
question: "Comment la baseline ECAPA se dégrade-t-elle sur SUMM-RE test dégradé (D24) ?"
verdict: en_cours
decisions: [D24]
---

# EXP-0021 — baseline-ecapa-summre-degrade

## Observations factuelles

Configuration d'EXP-0012 avec θ = 1,00 (balayage d'EXP-0012) ; seule variable : le signal (7 conditions de D24). Partition test, 37 réunions par condition.

| Condition | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER |
|---|---|---|---|---|---|---|
| rev04 | 35,45 % | 21,34 | 3,98 | 10,12 | 25,46 % | 42,22 % |
| rev08 | 40,81 % | 22,13 | 5,34 | 13,34 | 30,13 % | 47,98 % |
| bru15 | 39,13 % | 27,56 | 2,67 | 8,90 | 30,80 % | 45,02 % |
| bru05 | 47,38 % | 28,05 | 7,96 | 11,37 | 38,38 % | 50,71 % |
| cod16 | 32,71 % | 20,56 | 3,22 | 8,93 | 23,54 % | 38,09 % |
| cod08 | 38,43 % | 20,62 | 3,23 | 14,58 | 29,54 % | 48,03 % |
| salle | 49,21 % | 31,86 | 4,02 | 13,33 | 41,47 % | 55,21 % |

Propre (EXP-0012, test) : 33,4 % sans collar. Écarts à propre et comparaison à pyannote par bootstrap apparié, sous-groupes : A-0002.

Exécution en CPU sur le commit `fbbff49` (arbre propre), RTF 0,0158, alimentation conforme, `charge_concurrente` vraie (jusqu'à 10,17).

## Interprétation

À rédiger par le cockpit.
