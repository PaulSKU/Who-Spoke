---
id: EXP-0028
question: "Nemotron 3 Diarization se dégrade-t-il moins que pyannote sur SUMM-RE test dégradé (D24) ?"
verdict: en_cours
decisions: [D23, D29]
---

# EXP-0028 — nemotron3-summre-degrade

## Observations factuelles

Moteur : Nemotron 3 Diarization (`nvidia/Nemotron-3-Diarization@f667ed73`), environnement séparé `envs/nemotron` (transformers 5.22.1, librosa 0.11.0 ajouté au premier fichier), en CPU : en MPS, l'exécutant s'arrête sur une exception Metal (NSException). Référence : EXP-0020 (pyannote community-1), variable modifiée : le moteur.

| Jeu | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER | K exact |
|---|---|---|---|---|---|---|---|
| summre-rev04 test | 14,84 % | 11,78 | 2,11 | 0,94 | 11,09 % | 14,58 % | 97,30 % |
| summre-rev08 test | 16,04 % | 12,38 | 2,38 | 1,28 | 11,71 % | 16,01 % | 97,30 % |
| summre-bru15 test | 16,08 % | 12,70 | 1,58 | 1,81 | 12,45 % | 16,11 % | 89,19 % |
| summre-bru05 test | 18,46 % | 15,00 | 1,57 | 1,90 | 13,40 % | 19,74 % | 91,89 % |
| summre-cod16 test | 14,99 % | 11,95 | 1,81 | 1,22 | 11,39 % | 14,95 % | 89,19 % |
| summre-cod08 test | 16,44 % | 12,14 | 2,09 | 2,21 | 12,60 % | 17,52 % | 100,00 % |
| summre-salle test | 17,67 % | 14,44 | 1,82 | 1,41 | 12,74 % | 18,00 % | 97,30 % |

Écart à EXP-0020 sans collar (bootstrap apparié, 1 000 tirages, graine 0 ; fichiers améliorés, dégradés) :

- summre-bru05_test c0 : EXP-0028 - EXP-0020 = -11,68 [-14,46 ; -9,08] ; améliorés 36, dégradés 1, égaux 0
- manquee c0 : 15,00 contre 9,57
- fausse_alarme c0 : 1,57 contre 11,54
- confusion c0 : 1,90 contre 9,03
- summre-bru15_test c0 : EXP-0028 - EXP-0020 = -10,75 [-14,63 ; -6,51] ; améliorés 35, dégradés 2, égaux 0
- manquee c0 : 12,70 contre 7,39
- fausse_alarme c0 : 1,58 contre 11,43
- confusion c0 : 1,81 contre 8,00
- summre-cod08_test c0 : EXP-0028 - EXP-0020 = -13,79 [-18,40 ; -9,47] ; améliorés 35, dégradés 2, égaux 0
- manquee c0 : 12,14 contre 10,10
- fausse_alarme c0 : 2,09 contre 5,69
- confusion c0 : 2,21 contre 14,44
- summre-cod16_test c0 : EXP-0028 - EXP-0020 = -10,52 [-13,71 ; -7,53] ; améliorés 36, dégradés 1, égaux 0
- manquee c0 : 11,95 contre 7,83
- fausse_alarme c0 : 1,81 contre 9,31
- confusion c0 : 1,22 contre 8,36
- summre-rev04_test c0 : EXP-0028 - EXP-0020 = -13,94 [-17,92 ; -10,28] ; améliorés 36, dégradés 1, égaux 0
- manquee c0 : 11,78 contre 11,17
- fausse_alarme c0 : 2,11 contre 8,33
- confusion c0 : 0,94 contre 9,28
- summre-rev08_test c0 : EXP-0028 - EXP-0020 = -25,21 [-30,35 ; -20,00] ; améliorés 36, dégradés 1, égaux 0
- manquee c0 : 12,38 contre 23,16
- fausse_alarme c0 : 2,38 contre 9,19
- confusion c0 : 1,28 contre 8,89
- summre-salle_test c0 : EXP-0028 - EXP-0020 = -23,56 [-28,40 ; -18,73] ; améliorés 37, dégradés 0, égaux 0
- manquee c0 : 14,44 contre 23,41
- fausse_alarme c0 : 1,82 contre 8,41
- confusion c0 : 1,41 contre 9,41

Temps : RTF 0,0122 en CPU (commit `0358ccf`, arbre propre), alimentation conforme, `charge_concurrente` true (charge sur 1 min jusqu'à 12,57). Contamination (corpus.md §9) : AMI train et dev, VoxConverse vus à l'entraînement ; SUMM-RE absent de la liste.

## Interprétation (cockpit)

Nemotron 3 reste entre 14,8 et 18,5 % de DER dans toutes les conditions dégradées : il se dégrade très peu, de 0,2 à 3,8 points par rapport à son propre résultat propre. Là où pyannote s'effondre (rev08 et salle, +15 points), Nemotron 3 ne perd que 1,4 à 3,1 points. L'écart y atteint −25,2 et −23,6 points. Le codec bas débit, qui faisait confondre les voix aux deux autres systèmes, ne lui fait presque rien (confusion de 2,2 points). C'est le résultat le plus important pour la cible, une salle réverbérante avec un seul micro. Il contraste avec AMI (EXP-0026), qu'il faut donc expliquer avant de conclure (D29). Verdict en attente de D29.
