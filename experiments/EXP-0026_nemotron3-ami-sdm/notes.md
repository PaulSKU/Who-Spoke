---
id: EXP-0026
question: "Nemotron 3 Diarization fait-il mieux que pyannote sur AMI SDM ?"
verdict: en_cours
decisions: [D23]
---

# EXP-0026 — nemotron3-ami-sdm

## Observations factuelles

Moteur : Nemotron 3 Diarization (`nvidia/Nemotron-3-Diarization@f667ed73`), environnement séparé `envs/nemotron` (transformers 5.22.1, librosa 0.11.0 ajouté au premier fichier), en CPU : en MPS, l'exécutant s'arrête sur une exception Metal (NSException). Référence : EXP-0001 (pyannote community-1), variable modifiée : le moteur.

| Jeu | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER | K exact |
|---|---|---|---|---|---|---|---|
| ami dev | 22,37 % | 19,82 | 1,74 | 0,81 | 19,93 % | 23,50 % | 100,00 % |
| ami test | 27,47 % | 24,93 | 1,47 | 1,08 | 25,15 % | 29,56 % | 87,50 % |

Écart à EXP-0001 sans collar (bootstrap apparié, 1 000 tirages, graine 0 ; fichiers améliorés, dégradés) :

- ami_dev c0 : EXP-0026 - EXP-0001 = +3,73 [+2,21 ; +5,77] ; améliorés 1, dégradés 17, égaux 0
- manquee c0 : 19,82 contre 8,10
- fausse_alarme c0 : 1,74 contre 4,86
- confusion c0 : 0,81 contre 5,68
- ami_test c0 : EXP-0026 - EXP-0001 = +7,55 [+5,47 ; +9,45] ; améliorés 1, dégradés 15, égaux 0
- manquee c0 : 24,93 contre 11,16
- fausse_alarme c0 : 1,47 contre 3,81
- confusion c0 : 1,08 contre 4,94

Temps : RTF 0,0122 en CPU (commit `0358ccf`, arbre propre), alimentation conforme, `charge_concurrente` true (charge sur 1 min jusqu'à 8,00). Contamination (corpus.md §9) : AMI train et dev, VoxConverse vus à l'entraînement ; SUMM-RE absent de la liste.

## Interprétation

À rédiger par le cockpit.
