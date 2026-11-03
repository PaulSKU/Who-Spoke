---
id: EXP-0032
question: "La normalisation du niveau en entrée modifie-t-elle les résultats de pyannote sur SUMM-RE ?"
verdict: en_cours
decisions: [D25, D29]
---

# EXP-0032 — pyannote-c1-summre-niveau

## Observations factuelles

Moteur : pyannote community-1, MPS, comme EXP-0007 ; mesure CPU (`mesure_cpu`) non reprise. Référence : EXP-0007. Variable modifiée : `normalisation_niveau` (sonie intégrée ITU-R BS.1770-4 ramenée à −29,3 LUFS, médiane de SUMM-RE dev ; gain linéaire unique par fichier, garde de crête à −1 dBFS ; appliquée après la normalisation de D16, dans la section chronométrée). Analyse liée : A-0004.

| Jeu | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER | K exact |
|---|---|---|---|---|---|---|---|
| summre dev | 26,01 % | 5,13 | 14,24 | 6,64 | 10,76 % | 29,30 % | 91,67 % |
| summre test | 26,29 % | 7,16 | 11,28 | 7,86 | 14,81 % | 28,72 % | 83,78 % |

Écart à EXP-0007 (bootstrap apparié, 1 000 tirages, graine 0 ; fichiers améliorés, dégradés) :

- summre_dev c0 : EXP-0032 - EXP-0007 = +0,01 [-0,01 ; +0,02] ; améliorés 16, dégradés 16, égaux 4
- summre_dev c025 : EXP-0032 - EXP-0007 = +0,01 [-0,02 ; +0,04] ; améliorés 14, dégradés 14, égaux 8
- manquee c0 : 5,13 contre 5,13 ; fausse_alarme c0 : 14,24 contre 14,24 ; confusion c0 : 6,64 contre 6,64
- summre_test c0 : EXP-0032 - EXP-0007 = -0,00 [-0,01 ; +0,00] ; améliorés 18, dégradés 12, égaux 7
- summre_test c025 : EXP-0032 - EXP-0007 = -0,01 [-0,02 ; +0,00] ; améliorés 20, dégradés 8, égaux 9
- manquee c0 : 7,16 contre 7,15 ; fausse_alarme c0 : 11,28 contre 11,28 ; confusion c0 : 7,86 contre 7,87

Nombre de locuteurs VBx : 80b_EBDH passe à 1 locuteur VBx pour 2 en sortie (référence : 3) ; KMeans sur 0 fichier. Garde de crête : comme EXP-0030 (2 fichiers sur 73). RTF 0,0515 (dev) et 0,0525 (test), MPS. Contrôle d'arbre propre : à l'exécution et à l'évaluation (commit `0269b68`). Alimentation conforme ; `charge_concurrente` true (charge sur 1 min jusqu'à 9,01).

Conditions de D24 non exécutées avec la normalisation (règle 4 de D25 non vérifiée).

## Interprétation (cockpit)

À rédiger.
