---
id: EXP-0020
question: "Comment pyannote se dégrade-t-il sur SUMM-RE test dégradé (D24) ?"
verdict: informatif
decisions: [D24]
---

# EXP-0020 — pyannote-c1-summre-degrade

## Observations factuelles

Configuration d'EXP-0007 ; seule variable : le signal (7 conditions de D24), références et UEM de SUMM-RE test. Partition test, 37 réunions par condition.

| Condition | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER |
|---|---|---|---|---|---|---|
| rev04 | 28,78 % | 11,17 | 8,33 | 9,28 | 17,44 % | 33,02 % |
| rev08 | 41,24 % | 23,16 | 9,19 | 8,89 | 28,42 % | 44,50 % |
| bru15 | 26,83 % | 7,39 | 11,43 | 8,00 | 15,18 % | 29,01 % |
| bru05 | 30,15 % | 9,57 | 11,54 | 9,03 | 18,46 % | 33,48 % |
| cod16 | 25,51 % | 7,83 | 9,31 | 8,36 | 14,70 % | 28,65 % |
| cod08 | 30,24 % | 10,10 | 5,69 | 14,44 | 21,98 % | 41,54 % |
| salle | 41,23 % | 23,41 | 8,41 | 9,41 | 29,19 % | 45,56 % |

Propre (EXP-0007, test) : 26,30 % sans collar. Écarts à propre par bootstrap apparié et sous-groupes (Zoom, autres) : A-0002.

Exécution : une première tentative a été suspendue le 02/11 à 15:02 au fichier 186/259 (pause volontaire), puis arrêtée ; son journal est gardé dans `run_interrompu.log`. L'expérience a été relancée entièrement le 02/11 à 20:15 sur le commit `fbbff49` (arbre propre) ; les 372 RTTM de la tentative interrompue (186 fichiers, sorties habituelle et exclusive) sont identiques à l'octet à ceux de la relance. Temps MPS : RTF 0,0509, alimentation conforme, `charge_concurrente` vraie (charge sur 1 min jusqu'à 9,94 pour 6 cœurs de performance). Pas de mesure CPU (configuration).

## Interprétation (cockpit)

pyannote résiste bien au bruit et au codec de visio, mais pas à la réverbération forte.
- **Bruit et codec à 16 kbit/s.** Ils coûtent moins d'un point, ou ne coûtent rien de significatif.
- **Bruit à 5 dB et Opus à 8 kbit/s.** Environ +4 points chacun, mais pas pour la même raison. Le codec dégrade surtout l'attribution : la confusion passe de 7,9 à 14,4 points, et la part d'erreur due à un locuteur de référence non apparié monte à 13 % (A-0003). Un timbre appauvri fait fusionner des voix.
- **Réverbération forte (rev08) et condition « salle ».** C'est la vraie faiblesse : +14,9 points. L'erreur est presque entièrement de la parole manquée (7,2 → 23,2 points) : la segmentation de pyannote ne reconnaît plus une partie de la parole réverbérée. La fausse alarme baisse même un peu.

Or la cible de la démonstration comprend précisément une salle avec un seul micro et de l'écho : c'est la condition qui compte le plus pour le choix final. La réverbération est simulée et le RT60 effectif (T20) est de 0,90 s pour une cible de 0,8 s ; la sévérité de rev08 est donc un peu surestimée par rapport à la cible **[certain pour la mesure, probable pour la portée]**.
