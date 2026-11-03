---
id: EXP-0022
question: "V2 de D25 (sortie habituelle + masque de Silero) réduit-elle l'erreur de pyannote sur SUMM-RE ?"
verdict: en_cours
decisions: [D25]
---

# EXP-0022 — pyannote-c1-summre-silero

## Observations factuelles

Masque de Silero VAD 6.2.3 (seuil 0,8, silence minimal 0,0 s, marge 0,03 s), réglé sur SUMM-RE dev (`results/reglage_silero/2026-11-03_02h17/`, point resté au bord de la grille après l'élargissement unique). Référence : EXP-0007.

| Jeu | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER |
|---|---|---|---|---|---|---|
| dev | 21,35 % | 7,52 | 7,58 | 6,25 | 9,60 % | 26,72 % |
| test | 23,70 % | 10,83 | 5,49 | 7,38 | 15,10 % | 27,53 % |

Écart à EXP-0007 (bootstrap apparié, 1 000 tirages, graine 0) : test −2,60 [−3,71 ; −1,64] sans collar (30 fichiers améliorés, 7 dégradés), +0,29 [−0,50 ; +0,97] avec collar ; dev −4,66 [−5,66 ; −3,62] et −1,16 [−1,93 ; −0,31]. Test : FA 5,49 contre 11,28, parole manquée 10,83 contre 7,15, confusion 7,38 contre 7,87.

Exécution partagée portée par EXP-0023 (V3), qui rapporte le temps ; ce dossier en a le rappel (`execution_partagee.json`).

## Interprétation

À rédiger par le cockpit.
