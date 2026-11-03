---
id: EXP-0024
question: "V2 de D25 dégrade-t-elle AMI (règle 3) ?"
verdict: ecarte
decisions: [D25]
---

# EXP-0024 — pyannote-c1-ami-sdm-silero

## Observations factuelles

Masque de Silero VAD 6.2.3 (seuil 0,8, silence minimal 0,0 s, marge 0,03 s), réglé sur SUMM-RE dev (`results/reglage_silero/2026-11-03_02h17/`, point resté au bord de la grille après l'élargissement unique). Référence : EXP-0001.

| Jeu | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER |
|---|---|---|---|---|---|---|
| dev | 34,31 % | 27,86 | 2,16 | 4,30 | 29,50 % | 38,02 % |
| test | 42,05 % | 37,76 | 1,32 | 2,97 | 37,55 % | 46,24 % |

Écart à EXP-0001 : test +22,13 [+16,90 ; +27,12] sans collar, +24,34 [+18,59 ; +30,00] avec collar, 16 fichiers sur 16 dégradés ; dev +15,68 [+10,68 ; +21,10]. Test : parole manquée 37,76 contre 11,16, FA 1,32 contre 3,81, confusion 2,97 contre 4,94.

Exécution partagée portée par EXP-0025 (V3), qui rapporte le temps ; ce dossier en a le rappel (`execution_partagee.json`).

## Interprétation (cockpit)

C'est l'échec décisif de V2 : +22,1 points sur AMI test (IC [+16,9 ; +27,1]), 16 fichiers sur 16 moins bons, parole manquée de 11,2 à 37,8 points. Silero, entraîné sur de la parole proche du micro **[probable]**, classe en non-parole une grande partie de la parole lointaine. Un post-traitement réglé sur des micros-casques est dangereux pour une démonstration en micro de table.
