---
id: EXP-0027
question: "Nemotron 3 Diarization fait-il mieux que pyannote en français (SUMM-RE) ?"
verdict: informatif
decisions: [D23, D29]
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

## Interprétation (cockpit)

En français, Nemotron 3 fait beaucoup mieux que pyannote : −11,7 points sur test (36 fichiers sur 37 meilleurs), −15,5 sur dev. Le gain vient de la fausse alarme (11,3 → 1,9 points) et de la confusion (7,9 → 1,1). Il manque un peu plus de parole (7,2 → 11,6), un profil de système prudent qui n'attribue la parole qu'à coup sûr. Avec collar, l'écart reste net (11,2 contre 14,8 %). Il trouve le bon nombre de locuteurs dans 86 % des réunions de test (pyannote : 84 %). SUMM-RE n'apparaît pas dans ses données d'entraînement déclarées. Des sources multilingues (YODAS, David AI) peuvent contenir du français, mais une contamination par SUMM-RE n'est pas documentée **[incertain, peu probable]**. Verdict : informatif. Ces résultats, au seuil par défaut de 0,5, sont remplacés par ceux du seuil réglé à 0,35 (EXP-0033 à 0035, retenus) ; le choix du moteur reste régi par D29.
