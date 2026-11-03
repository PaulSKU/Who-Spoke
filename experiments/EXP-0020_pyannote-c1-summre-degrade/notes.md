---
id: EXP-0020
question: "Comment pyannote se dégrade-t-il sur SUMM-RE test dégradé (D24) ?"
verdict: en_cours
decisions: [D24]
---

# EXP-0020 — pyannote-c1-summre-degrade

## Observations factuelles

Configuration d'EXP-0007 ; seule variable : le signal (7 conditions de D24), références et UEM de SUMM-RE test. Partition test, 37 réunions par condition.

| Condition | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER |
|---|---|---|---|---|---|---|
| rev04 | 28,78 % | 11,17 | 8,33 | 9,28 | 17,44 % | 33,02 % |
| rev08 | 41,24 % | 23,16 | 9,19 | 8,89 | 28,42 % | 44,50 % |
| bru15 | 26,83 % | 7,39 | 11,43 | 8,00 | 15,18 % | 29,01 % |
| bru05 | 30,15 % | 9,57 | 11,54 | 9,03 | 18,46 % | 33,48 % |
| cod16 | 25,51 % | 7,83 | 9,31 | 8,36 | 14,70 % | 28,65 % |
| cod08 | 30,24 % | 10,10 | 5,69 | 14,44 | 21,98 % | 41,54 % |
| salle | 41,23 % | 23,41 | 8,41 | 9,41 | 29,19 % | 45,56 % |

Propre (EXP-0007, test) : 26,30 % sans collar. Écarts à propre par bootstrap apparié et sous-groupes (Zoom, autres) : A-0002.

Exécution : une première tentative a été suspendue le 02/11 à 15:02 au fichier 186/259 (pause volontaire), puis arrêtée ; son journal est gardé dans `run_interrompu.log`. L'expérience a été relancée entièrement le 02/11 à 20:15 sur le commit `fbbff49` (arbre propre) ; les 372 RTTM de la tentative interrompue (186 fichiers, sorties habituelle et exclusive) sont identiques à l'octet à ceux de la relance. Temps MPS : RTF 0,0509, alimentation conforme, `charge_concurrente` vraie (charge sur 1 min jusqu'à 9,94 pour 6 cœurs de performance). Pas de mesure CPU (configuration).

## Interprétation

À rédiger par le cockpit.
