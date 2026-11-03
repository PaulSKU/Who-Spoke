---
id: EXP-0029
question: "La normalisation du niveau en entrée réduit-elle la parole manquée de Nemotron 3 sur AMI ?"
verdict: en_cours
decisions: [D25, D29]
---

# EXP-0029 — nemotron3-ami-sdm-niveau

## Observations factuelles

Moteur : Nemotron 3 Diarization, CPU, comme EXP-0026. Référence : EXP-0026. Variable modifiée : `normalisation_niveau` (sonie intégrée ITU-R BS.1770-4 ramenée à −29,3 LUFS, médiane de SUMM-RE dev ; gain linéaire unique par fichier, garde de crête à −1 dBFS ; appliquée après la normalisation de D16, dans la section chronométrée). Analyse liée : A-0004.

| Jeu | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER | K exact |
|---|---|---|---|---|---|---|---|
| ami dev | 22,33 % | 19,78 | 1,82 | 0,74 | 19,83 % | 23,55 % | 100,00 % |
| ami test | 27,97 % | 24,91 | 1,50 | 1,56 | 25,73 % | 31,05 % | 93,75 % |

Écart à EXP-0026 (bootstrap apparié, 1 000 tirages, graine 0 ; fichiers améliorés, dégradés) :

- ami_dev c0 : EXP-0029 - EXP-0026 = -0,04 [-0,42 ; +0,22] ; améliorés 6, dégradés 12, égaux 0
- ami_dev c025 : EXP-0029 - EXP-0026 = -0,10 [-0,59 ; +0,20] ; améliorés 7, dégradés 11, égaux 0
- manquee c0 : 19,78 contre 19,82 ; fausse_alarme c0 : 1,82 contre 1,74 ; confusion c0 : 0,74 contre 0,81
- ami_test c0 : EXP-0029 - EXP-0026 = +0,50 [-0,35 ; +2,07] ; améliorés 9, dégradés 7, égaux 0
- ami_test c025 : EXP-0029 - EXP-0026 = +0,58 [-0,35 ; +2,31] ; améliorés 8, dégradés 8, égaux 0
- manquee c0 : 24,91 contre 24,93 ; fausse_alarme c0 : 1,50 contre 1,47 ; confusion c0 : 1,56 contre 1,08

Garde de crête : gain réduit sur 30 fichiers sur 34, de 0,4 à 15,5 dB (TS3003a : gain appliqué +6,66 dB, réduit de 15,49 dB), la cible n'est donc pas atteinte sur la plupart des fichiers d'AMI. Gains effectivement appliqués jusqu'à +19,1 dB (ES2011a, dev). RTF 0,0122 (dev) et 0,0120 (test), CPU. Contrôle d'arbre propre : à l'exécution et à l'évaluation (commit `0269b68`). Alimentation conforme ; `charge_concurrente` true (charge sur 1 min jusqu'à 6,64).

Conditions de D24 non exécutées avec la normalisation (règle 4 de D25 non vérifiée).

## Interprétation (cockpit)

À rédiger.
