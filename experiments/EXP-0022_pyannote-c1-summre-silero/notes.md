---
id: EXP-0022
question: "V2 de D25 (sortie habituelle + masque de Silero) réduit-elle l'erreur de pyannote sur SUMM-RE ?"
verdict: ecarte
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

## Interprétation (cockpit)

V2 améliore bien SUMM-RE test (−2,60 points, IC [−3,71 ; −1,64]) : la fausse alarme est divisée par deux (11,3 → 5,5 points), sans dégradation significative avec collar. C'était la cible visée (pauses pontées, A-0001). La règle 3 de D25 l'écarte cependant : sur AMI, Silero coupe la parole du micro distant (EXP-0024). Le gain sur SUMM-RE tient à des micros-casques, où la parole est forte et nette ; il ne se transporte pas en champ lointain, qui est la cible. C'est exactement le risque que la règle de D25 devait couvrir. Le point de réglage (seuil 0,8) est resté au bord de la grille : un seuil plus haut couperait encore davantage de parole faible, et n'aurait donc pas changé le verdict sur AMI. La grille n'est pas élargie davantage.
