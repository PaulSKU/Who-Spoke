---
id: EXP-0033
question: "Le seuil de décision de Nemotron 3 réglé sur SUMM-RE dev réduit-il son DER sur SUMM-RE ?"
verdict: retenu
decisions: [D25, D29]
---

# EXP-0033 — nemotron3-summre-seuil

## Observations factuelles

Moteur : Nemotron 3 Diarization, CPU, comme EXP-0027. Référence : EXP-0027. Variable modifiée : le seuil de décision de Nemotron 3 (sigmoïde par trame, 0,5 par défaut), réglé par balayage sur SUMM-RE dev seulement (EXP-0033 : grille de 0,20 à 0,80 au pas de 0,05, DER sans collar le plus bas, D19 §4) : **0,35** retenu.

Balayage (`balayage_summre_dev.csv`, réseau passé une fois par fichier, 433,5 s de préparation, 737,4 s au total, hors RTF) : DER c0 de 10,44 % (0,20) à 12,35 % (0,80), minimum 10,28 % à 0,35 (10,29 % à 0,30, 10,30 % à 0,40), valeur intérieure à la grille. Contrôle : la ligne 0,5 redonne EXP-0027 dev (10,50 % ; manquée 7,28, FA 2,71, confusion 0,50). En baissant le seuil, la parole manquée diminue (7,28 à 0,50 ; 6,31 à 0,35 ; 5,36 à 0,20) et la fausse alarme augmente (2,71 ; 3,42 ; 4,51).

| Jeu | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER | K exact |
|---|---|---|---|---|---|---|---|
| summre dev | 10,28 % | 6,31 | 3,42 | 0,55 | 4,38 % | 11,13 % | 88,89 % |
| summre test | 14,25 % | 10,61 | 2,53 | 1,11 | 11,07 % | 13,87 % | 86,49 % |

Écart à EXP-0027 (bootstrap apparié, 1 000 tirages, graine 0 ; fichiers améliorés, dégradés) :

- summre_dev c0 : EXP-0033 - EXP-0027 = -0,22 [-0,37 ; -0,03] ; améliorés 27, dégradés 9, égaux 0
- summre_dev c025 : EXP-0033 - EXP-0027 = -0,03 [-0,18 ; +0,18] ; améliorés 25, dégradés 11, égaux 0
- manquee c0 : 6,31 contre 7,28
- fausse_alarme c0 : 3,42 contre 2,71
- confusion c0 : 0,55 contre 0,50
- summre_test c0 : EXP-0033 - EXP-0027 = -0,37 [-0,45 ; -0,28] ; améliorés 35, dégradés 2, égaux 0
- summre_test c025 : EXP-0033 - EXP-0027 = -0,16 [-0,24 ; -0,08] ; améliorés 33, dégradés 4, égaux 0
- manquee c0 : 10,61 contre 11,61
- fausse_alarme c0 : 2,53 contre 1,91
- confusion c0 : 1,11 contre 1,10

Face à pyannote (EXP-0007), information pour D29 :

- summre_test c0 : EXP-0033 - EXP-0007 = -12,05 [-15,66 ; -8,65] ; améliorés 36, dégradés 1, égaux 0
- manquee c0 : 10,61 contre 7,15

RTF 0,0104 (dev) et 0,0108 (test), CPU. Contrôle d'arbre propre : à l'exécution et à l'évaluation (commit `f78a220`). Alimentation conforme ; `charge_concurrente` true (charge sur 1 min jusqu'à 6,36).

## Interprétation (cockpit)

Le seuil de décision de Nemotron 3, réglé sur SUMM-RE dev seulement (minimum à 0,35, à l'intérieur de la grille de 0,20 à 0,80), apporte un gain faible mais net sur SUMM-RE test : −0,37 point sans collar, 35 fichiers sur 37 améliorés, −0,16 avec collar. Il échange un peu de parole manquée (11,6 → 10,6 points) contre un peu de fausse alarme (1,9 → 2,5). Les quatre règles de D25 sont respectées (EXP-0034 et EXP-0035). Le seuil de 0,35 est retenu pour Nemotron 3.
