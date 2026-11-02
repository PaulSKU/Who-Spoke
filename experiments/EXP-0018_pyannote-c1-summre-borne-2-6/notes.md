---
id: EXP-0018
question: "Borner le nombre de locuteurs entre 2 et 6 change-t-il pyannote sur SUMM-RE (D23, rang A2) ?"
verdict: en_cours
decisions: [D23]
---

# EXP-0018 — pyannote-c1-summre-borne-2-6

## Observations factuelles

Bornes `min_speakers: 2`, `max_speakers: 6` ; configuration d'EXP-0007 par ailleurs.

| Jeu | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER |
|---|---|---|---|---|---|---|
| dev | 26,00 % | 5,13 | 14,24 | 6,64 | 10,76 % | 29,28 % |
| test | 25,82 % | 7,15 | 11,28 | 7,39 | 14,31 % | 28,39 % |

Nombre de groupes de VBx avant les bornes : dans [2, 6] pour 72 fichiers sur 73. Un seul passage au KMeans : test, `summre__080b_EBDH` (VBx : 1 groupe ; KMeans : 2 ; référence : 3 locuteurs), DER sans collar 66,01 → 51,25 %. Les 72 autres RTTM sont identiques à l'octet à ceux d'EXP-0007 (sortie exclusive : identiques à EXP-0016).

Écart à EXP-0007, bootstrap apparié (1 000 tirages, graine 0) : dev 0,00 (36 fichiers égaux) ; test −0,48 [−1,48 ; 0,00] sans collar, −0,50 [−1,58 ; 0,00] avec collar, 1 fichier amélioré, 36 égaux.

Temps conformes (MPS et CPU). Exécution concurrente des sessions B et E (D21, amendement du 01/11), sans relevé de charge.

## Interprétation

À rédiger par le cockpit.
