---
id: EXP-0021
question: "Comment la baseline ECAPA se dégrade-t-elle sur SUMM-RE test dégradé (D24) ?"
verdict: informatif
decisions: [D24]
---

# EXP-0021 — baseline-ecapa-summre-degrade

## Observations factuelles

Configuration d'EXP-0012 avec θ = 1,00 (balayage d'EXP-0012) ; seule variable : le signal (7 conditions de D24). Partition test, 37 réunions par condition.

| Condition | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER |
|---|---|---|---|---|---|---|
| rev04 | 35,45 % | 21,34 | 3,98 | 10,12 | 25,46 % | 42,22 % |
| rev08 | 40,81 % | 22,13 | 5,34 | 13,34 | 30,13 % | 47,98 % |
| bru15 | 39,13 % | 27,56 | 2,67 | 8,90 | 30,80 % | 45,02 % |
| bru05 | 47,38 % | 28,05 | 7,96 | 11,37 | 38,38 % | 50,71 % |
| cod16 | 32,71 % | 20,56 | 3,22 | 8,93 | 23,54 % | 38,09 % |
| cod08 | 38,43 % | 20,62 | 3,23 | 14,58 | 29,54 % | 48,03 % |
| salle | 49,21 % | 31,86 | 4,02 | 13,33 | 41,47 % | 55,21 % |

Propre (EXP-0012, test) : 33,4 % sans collar. Écarts à propre et comparaison à pyannote par bootstrap apparié, sous-groupes : A-0002.

Exécution en CPU sur le commit `fbbff49` (arbre propre), RTF 0,0158, alimentation conforme, `charge_concurrente` vraie (jusqu'à 10,17).

## Interprétation (cockpit)

La baseline ECAPA a le profil inverse de pyannote.
- **Bruit.** C'est son point faible : +5,7 points à 15 dB, +14,0 points à 5 dB, surtout en parole manquée. Le seuil de sa détection par énergie, calé sur les percentiles du fichier, monte avec le plancher de bruit et coupe la parole faible **[probable]**.
- **Réverbération.** Elle la gêne moins (+7,4 points en rev08) : la détection par énergie ne perd pas de parole, et c'est la confusion qui augmente (8,5 → 13,3 points).
- **Codec à 8 kbit/s.** Comme pour pyannote, il dégrade l'attribution (confusion 8,5 → 14,6 points).

Conséquence : en rev08, pyannote perd l'essentiel de son avance (écart de +0,4 point, non significatif, A-0002). C'est la seule condition où ce n'est pas le cas.
