---
id: EXP-0034
question: "Le seuil retenu sur SUMM-RE dev dégrade-t-il Nemotron 3 sur AMI (règle 3 de D25) ?"
verdict: en_cours
decisions: [D25, D29]
---

# EXP-0034 — nemotron3-ami-sdm-seuil

## Observations factuelles

Moteur : Nemotron 3 Diarization, CPU, comme EXP-0026. Référence : EXP-0026. Variable modifiée : le seuil de décision de Nemotron 3 (sigmoïde par trame, 0,5 par défaut), réglé par balayage sur SUMM-RE dev seulement (EXP-0033 : grille de 0,20 à 0,80 au pas de 0,05, DER sans collar le plus bas, D19 §4) : **0,35** retenu.

Seuil fixé à 0,35 (`parametres.threshold`), sans réglage sur AMI.

| Jeu | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER | K exact |
|---|---|---|---|---|---|---|---|
| ami dev | 21,70 % | 17,66 | 3,00 | 1,04 | 19,13 % | 22,79 % | 100,00 % |
| ami test | 26,44 % | 22,51 | 2,57 | 1,36 | 24,12 % | 28,48 % | 87,50 % |

Écart à EXP-0026 (bootstrap apparié, 1 000 tirages, graine 0 ; fichiers améliorés, dégradés) :

- ami_dev c0 : EXP-0034 - EXP-0026 = -0,67 [-0,93 ; -0,48] ; améliorés 18, dégradés 0, égaux 0
- ami_dev c025 : EXP-0034 - EXP-0026 = -0,81 [-1,09 ; -0,60] ; améliorés 18, dégradés 0, égaux 0
- manquee c0 : 17,66 contre 19,82
- fausse_alarme c0 : 3,00 contre 1,74
- confusion c0 : 1,04 contre 0,81
- ami_test c0 : EXP-0034 - EXP-0026 = -1,04 [-1,39 ; -0,65] ; améliorés 14, dégradés 2, égaux 0
- ami_test c025 : EXP-0034 - EXP-0026 = -1,03 [-1,35 ; -0,70] ; améliorés 16, dégradés 0, égaux 0
- manquee c0 : 22,51 contre 24,93
- fausse_alarme c0 : 2,57 contre 1,47
- confusion c0 : 1,36 contre 1,08

Face à pyannote (EXP-0001), information pour D29 (condition 2) :

- ami_test c0 : EXP-0034 - EXP-0001 = +6,51 [+4,77 ; +8,23] ; améliorés 1, dégradés 15, égaux 0
- manquee c0 : 22,51 contre 11,16

RTF 0,0103, CPU. Contrôle d'arbre propre : à l'exécution et à l'évaluation (commit `f78a220`). Alimentation conforme ; `charge_concurrente` true (charge sur 1 min jusqu'à 8,62).

## Interprétation (cockpit)

À rédiger.
