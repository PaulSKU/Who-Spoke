---
id: EXP-0023
question: "V3 de D25 (sortie exclusive + masque de Silero) réduit-elle l'erreur de pyannote sur SUMM-RE ?"
verdict: ecarte
decisions: [D25]
---

# EXP-0023 — pyannote-c1-summre-exclusive-silero

## Observations factuelles

Masque de Silero VAD 6.2.3 (seuil 0,8, silence minimal 0,0 s, marge 0,03 s), réglé sur SUMM-RE dev (`results/reglage_silero/2026-11-03_02h17/`, point resté au bord de la grille après l'élargissement unique). Référence : EXP-0016.

| Jeu | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER |
|---|---|---|---|---|---|---|
| dev | 24,66 % | 15,53 | 4,19 | 4,94 | 11,85 % | 29,47 % |
| test | 27,90 % | 19,21 | 2,66 | 6,04 | 18,09 % | 31,28 % |

Écart à EXP-0016 : test −2,49 [−3,62 ; −1,55] sans collar (30 améliorés, 7 dégradés), +0,31 [−0,48 ; +0,99] avec collar ; dev −4,52 [−5,54 ; −3,48]. Écart à EXP-0007 (sortie habituelle seule) : test 27,90 contre 26,30 sans collar.

Porte l'exécution partagée avec l'expérience V2 ; temps : voir `execution_*.json` (alimentation conforme, charge concurrente relevée).

## Interprétation (cockpit)

V3 cumule la sortie exclusive, déjà écartée (EXP-0016), et le masque de Silero. Elle hérite des deux défauts : perte du chevauchement réel et coupure de la parole faible. Écartée.
