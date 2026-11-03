---
id: EXP-0027
question: "Nemotron 3 Diarization fait-il mieux que pyannote en français (SUMM-RE) ?"
verdict: en_cours
decisions: [D23]
---

# EXP-0027 — nemotron3-summre

## Observations factuelles

Moteur : Nemotron 3 Diarization (`nvidia/Nemotron-3-Diarization@f667ed73`), environnement séparé `envs/nemotron` (transformers 5.22.1, librosa 0.11.0 ajouté au premier fichier), en CPU : en MPS, l'exécutant s'arrête sur une exception Metal (NSException). Référence : EXP-0007 (pyannote community-1), variable modifiée : le moteur.

| Jeu | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER | K exact |
|---|---|---|---|---|---|---|---|
| summre dev | 10,50 % | 7,28 | 2,71 | 0,50 | 4,41 % | 11,44 % | 88,89 % |
| summre test | 14,62 % | 11,61 | 1,91 | 1,10 | 11,22 % | 14,37 % | 86,49 % |

Écart à EXP-0007 sans collar (bootstrap apparié, 1 000 tirages, graine 0 ; fichiers améliorés, dégradés) :

- summre_dev c0 : EXP-0027 - EXP-0007 = -15,51 [-17,03 ; -13,91] ; améliorés 36, dégradés 0, égaux 0
- manquee c0 : 7,28 contre 5,13
- fausse_alarme c0 : 2,71 contre 14,24
- confusion c0 : 0,50 contre 6,64
- summre_test c0 : EXP-0027 - EXP-0007 = -11,68 [-15,26 ; -8,33] ; améliorés 36, dégradés 1, égaux 0
- manquee c0 : 11,61 contre 7,15
- fausse_alarme c0 : 1,91 contre 11,28
- confusion c0 : 1,10 contre 7,87

Temps : RTF 0,0116 en CPU (commit `0358ccf`, arbre propre), alimentation conforme, `charge_concurrente` true (charge sur 1 min jusqu'à 8,94). Contamination (corpus.md §9) : AMI train et dev, VoxConverse vus à l'entraînement ; SUMM-RE absent de la liste.

## Interprétation

À rédiger par le cockpit.
