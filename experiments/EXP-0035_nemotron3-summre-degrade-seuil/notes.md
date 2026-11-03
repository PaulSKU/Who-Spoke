---
id: EXP-0035
question: "Le seuil retenu sur SUMM-RE dev dégrade-t-il Nemotron 3 sur les conditions de D24 (règle 4 de D25) ?"
verdict: en_cours
decisions: [D25, D29]
---

# EXP-0035 — nemotron3-summre-degrade-seuil

## Observations factuelles

Moteur : Nemotron 3 Diarization, CPU, comme EXP-0028. Référence : EXP-0028. Variable modifiée : le seuil de décision de Nemotron 3 (sigmoïde par trame, 0,5 par défaut), réglé par balayage sur SUMM-RE dev seulement (EXP-0033 : grille de 0,20 à 0,80 au pas de 0,05, DER sans collar le plus bas, D19 §4) : **0,35** retenu.

Seuil fixé à 0,35 (`parametres.threshold`), sans réglage sur ces jeux ; références et UEM de SUMM-RE test.

| Jeu | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER | K exact |
|---|---|---|---|---|---|---|---|
| summre-bru05 test | 17,71 % | 13,28 | 2,41 | 2,02 | 12,88 % | 18,78 % | 89,19 % |
| summre-bru15 test | 15,64 % | 11,49 | 2,27 | 1,88 | 12,27 % | 15,47 % | 86,49 % |
| summre-cod08 test | 16,11 % | 10,32 | 3,52 | 2,27 | 12,41 % | 16,92 % | 100,00 % |
| summre-cod16 test | 14,57 % | 10,87 | 2,43 | 1,27 | 11,15 % | 14,40 % | 89,19 % |
| summre-rev04 test | 14,51 % | 10,65 | 2,88 | 0,99 | 10,91 % | 14,13 % | 97,30 % |
| summre-rev08 test | 15,68 % | 10,84 | 3,47 | 1,37 | 11,42 % | 15,57 % | 97,30 % |
| summre-salle test | 16,98 % | 12,78 | 2,73 | 1,47 | 12,27 % | 17,09 % | 97,30 % |

Écart à EXP-0028 (bootstrap apparié, 1 000 tirages, graine 0 ; fichiers améliorés, dégradés) :

- summre-bru05_test c0 : EXP-0035 - EXP-0028 = -0,76 [-1,02 ; -0,53] ; améliorés 35, dégradés 2, égaux 0
- summre-bru05_test c025 : EXP-0035 - EXP-0028 = -0,52 [-0,82 ; -0,27] ; améliorés 32, dégradés 5, égaux 0
- manquee c0 : 13,28 contre 15,00
- fausse_alarme c0 : 2,41 contre 1,57
- confusion c0 : 2,02 contre 1,90
- summre-bru15_test c0 : EXP-0035 - EXP-0028 = -0,44 [-0,56 ; -0,30] ; améliorés 35, dégradés 2, égaux 0
- summre-bru15_test c025 : EXP-0035 - EXP-0028 = -0,18 [-0,30 ; -0,03] ; améliorés 33, dégradés 4, égaux 0
- manquee c0 : 11,49 contre 12,70
- fausse_alarme c0 : 2,27 contre 1,58
- confusion c0 : 1,88 contre 1,81
- summre-cod08_test c0 : EXP-0035 - EXP-0028 = -0,34 [-0,57 ; -0,04] ; améliorés 31, dégradés 6, égaux 0
- summre-cod08_test c025 : EXP-0035 - EXP-0028 = -0,19 [-0,36 ; +0,04] ; améliorés 28, dégradés 8, égaux 1
- manquee c0 : 10,32 contre 12,14
- fausse_alarme c0 : 3,52 contre 2,09
- confusion c0 : 2,27 contre 2,21
- summre-cod16_test c0 : EXP-0035 - EXP-0028 = -0,42 [-0,50 ; -0,33] ; améliorés 36, dégradés 1, égaux 0
- summre-cod16_test c025 : EXP-0035 - EXP-0028 = -0,24 [-0,31 ; -0,17] ; améliorés 33, dégradés 4, égaux 0
- manquee c0 : 10,87 contre 11,95
- fausse_alarme c0 : 2,43 contre 1,81
- confusion c0 : 1,27 contre 1,22
- summre-rev04_test c0 : EXP-0035 - EXP-0028 = -0,33 [-0,46 ; -0,18] ; améliorés 33, dégradés 4, égaux 0
- summre-rev04_test c025 : EXP-0035 - EXP-0028 = -0,18 [-0,28 ; -0,03] ; améliorés 33, dégradés 4, égaux 0
- manquee c0 : 10,65 contre 11,78
- fausse_alarme c0 : 2,88 contre 2,11
- confusion c0 : 0,99 contre 0,94
- summre-rev08_test c0 : EXP-0035 - EXP-0028 = -0,36 [-0,47 ; -0,24] ; améliorés 33, dégradés 4, égaux 0
- summre-rev08_test c025 : EXP-0035 - EXP-0028 = -0,29 [-0,37 ; -0,21] ; améliorés 32, dégradés 5, égaux 0
- manquee c0 : 10,84 contre 12,38
- fausse_alarme c0 : 3,47 contre 2,38
- confusion c0 : 1,37 contre 1,28
- summre-salle_test c0 : EXP-0035 - EXP-0028 = -0,69 [-0,94 ; -0,45] ; améliorés 35, dégradés 2, égaux 0
- summre-salle_test c025 : EXP-0035 - EXP-0028 = -0,47 [-0,71 ; -0,22] ; améliorés 35, dégradés 2, égaux 0
- manquee c0 : 12,78 contre 14,44
- fausse_alarme c0 : 2,73 contre 1,82
- confusion c0 : 1,47 contre 1,41

RTF de 0,0103 à 0,0115 selon la condition, CPU. Contrôle d'arbre propre : à l'exécution et à l'évaluation (commit `f78a220`). Alimentation conforme ; `charge_concurrente` true (charge sur 1 min jusqu'à 11,08).

## Interprétation (cockpit)

À rédiger.
