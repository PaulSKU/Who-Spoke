---
id: EXP-0030
question: "La normalisation du niveau en entrée modifie-t-elle les résultats de Nemotron 3 sur SUMM-RE ?"
verdict: en_cours
decisions: [D25, D29]
---

# EXP-0030 — nemotron3-summre-niveau

## Observations factuelles

Moteur : Nemotron 3 Diarization, CPU, comme EXP-0027. Référence : EXP-0027. Variable modifiée : `normalisation_niveau` (sonie intégrée ITU-R BS.1770-4 ramenée à −29,3 LUFS, médiane de SUMM-RE dev ; gain linéaire unique par fichier, garde de crête à −1 dBFS ; appliquée après la normalisation de D16, dans la section chronométrée). Analyse liée : A-0004.

| Jeu | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER | K exact |
|---|---|---|---|---|---|---|---|
| summre dev | 10,55 % | 7,31 | 2,72 | 0,52 | 4,47 % | 11,49 % | 91,67 % |
| summre test | 15,34 % | 11,65 | 1,89 | 1,81 | 11,99 % | 15,08 % | 83,78 % |

Écart à EXP-0027 (bootstrap apparié, 1 000 tirages, graine 0 ; fichiers améliorés, dégradés) :

- summre_dev c0 : EXP-0030 - EXP-0027 = +0,05 [-0,00 ; +0,13] ; améliorés 16, dégradés 19, égaux 1
- summre_dev c025 : EXP-0030 - EXP-0027 = +0,06 [-0,00 ; +0,15] ; améliorés 19, dégradés 16, égaux 1
- manquee c0 : 7,31 contre 7,28 ; fausse_alarme c0 : 2,72 contre 2,71 ; confusion c0 : 0,52 contre 0,50
- summre_test c0 : EXP-0030 - EXP-0027 = +0,73 [-0,06 ; +1,94] ; améliorés 23, dégradés 14, égaux 0
- summre_test c025 : EXP-0030 - EXP-0027 = +0,77 [-0,07 ; +2,05] ; améliorés 21, dégradés 16, égaux 0
- manquee c0 : 11,65 contre 11,61 ; fausse_alarme c0 : 1,89 contre 1,91 ; confusion c0 : 1,81 contre 1,10

Garde de crête : gain réduit sur 2 fichiers sur 73 (1,22 dB au plus). RTF 0,0116 (dev) et 0,0123 (test), CPU. Contrôle d'arbre propre : à l'exécution et à l'évaluation (commit `0269b68`). Alimentation conforme ; `charge_concurrente` true (charge sur 1 min jusqu'à 8,5).

Conditions de D24 non exécutées avec la normalisation (règle 4 de D25 non vérifiée).

## Interprétation (cockpit)

À rédiger.
