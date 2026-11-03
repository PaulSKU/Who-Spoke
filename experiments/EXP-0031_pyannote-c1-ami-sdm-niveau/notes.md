---
id: EXP-0031
question: "La normalisation du niveau en entrée modifie-t-elle les résultats de pyannote sur AMI ?"
verdict: informatif
decisions: [D25, D29]
---

# EXP-0031 — pyannote-c1-ami-sdm-niveau

## Observations factuelles

Moteur : pyannote community-1, MPS, comme EXP-0001 ; mesure CPU (`mesure_cpu`) non reprise. Référence : EXP-0001. Variable modifiée : `normalisation_niveau` (sonie intégrée ITU-R BS.1770-4 ramenée à −29,3 LUFS, médiane de SUMM-RE dev ; gain linéaire unique par fichier, garde de crête à −1 dBFS ; appliquée après la normalisation de D16, dans la section chronométrée). Analyse liée : A-0004.

| Jeu | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER | K exact |
|---|---|---|---|---|---|---|---|
| ami dev | 18,66 % | 8,08 | 4,89 | 5,69 | 11,17 % | 23,78 % | 88,89 % |
| ami test | 19,96 % | 11,13 | 3,86 | 4,97 | 13,20 % | 27,07 % | 75,00 % |

Écart à EXP-0001 (bootstrap apparié, 1 000 tirages, graine 0 ; fichiers améliorés, dégradés) :

- ami_dev c0 : EXP-0031 - EXP-0001 = +0,02 [-0,02 ; +0,08] ; améliorés 8, dégradés 9, égaux 1
- ami_dev c025 : EXP-0031 - EXP-0001 = +0,02 [-0,02 ; +0,07] ; améliorés 8, dégradés 9, égaux 1
- manquee c0 : 8,08 contre 8,10 ; fausse_alarme c0 : 4,89 contre 4,86 ; confusion c0 : 5,69 contre 5,68
- ami_test c0 : EXP-0031 - EXP-0001 = +0,04 [-0,06 ; +0,15] ; améliorés 7, dégradés 8, égaux 1
- ami_test c025 : EXP-0031 - EXP-0001 = -0,01 [-0,11 ; +0,10] ; améliorés 7, dégradés 8, égaux 1
- manquee c0 : 11,13 contre 11,16 ; fausse_alarme c0 : 3,86 contre 3,81 ; confusion c0 : 4,97 contre 4,94

Nombre de locuteurs VBx identique à EXP-0001 sur les 34 fichiers ; KMeans sur 0 fichier. Garde de crête : comme EXP-0029 (30 fichiers sur 34). RTF 0,0538 (dev) et 0,0527 (test), MPS. Contrôle d'arbre propre : à l'exécution et à l'évaluation (commit `0269b68`). Alimentation conforme ; `charge_concurrente` true (charge sur 1 min jusqu'à 8,19).

Conditions de D24 non exécutées avec la normalisation (règle 4 de D25 non vérifiée).

## Interprétation (cockpit)

La normalisation du niveau en entrée n'a d'effet significatif ni sur Nemotron 3 ni sur pyannote, sur AMI comme sur SUMM-RE. Pour Nemotron 3 sur AMI, la parole manquée ne bouge pas (24,9 contre 24,9 points), même sur les fichiers qui ont reçu le plus de gain (jusqu'à +19 dB). L'hypothèse du niveau d'entrée (D29 §1) est donc écartée. Une réserve : la garde de crête a limité le gain sur 30 des 34 fichiers d'AMI, et la cible de −29,3 LUFS n'est pas atteinte partout. Mais l'absence d'effet sur les fichiers les plus amplifiés suffit à conclure **[probable]** ; la variante sans garde de crête n'est pas testée. Les règles 2 et 3 de D25 sont respectées, la règle 1 ne l'est pas : la normalisation n'est pas retenue.
