---
id: EXP-0025
question: "V3 de D25 dégrade-t-elle AMI (règle 3) ?"
verdict: ecarte
decisions: [D25]
---

# EXP-0025 — pyannote-c1-ami-sdm-exclusive-silero

## Observations factuelles

Masque de Silero VAD 6.2.3 (seuil 0,8, silence minimal 0,0 s, marge 0,03 s), réglé sur SUMM-RE dev (`results/reglage_silero/2026-11-03_02h17/`, point resté au bord de la grille après l'élargissement unique). Référence : EXP-0017.

| Jeu | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER |
|---|---|---|---|---|---|---|
| dev | 38,60 % | 35,32 | 0,68 | 2,60 | 32,69 % | 41,14 % |
| test | 46,00 % | 43,92 | 0,37 | 1,70 | 40,63 % | 49,47 % |

Écart à EXP-0017 : test +21,51 [+16,44 ; +26,56] sans collar, 16 fichiers sur 16 dégradés ; dev +15,52 [+10,65 ; +20,80]. Test : parole manquée 43,92 contre 18,48.

Porte l'exécution partagée avec l'expérience V2 ; temps : voir `execution_*.json` (alimentation conforme, charge concurrente relevée).

## Interprétation (cockpit)

Même conclusion que pour EXP-0024, avec en plus la perte du chevauchement due à la sortie exclusive.
