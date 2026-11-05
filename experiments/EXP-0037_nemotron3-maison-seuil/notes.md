---
id: EXP-0037
question: "Sur le corpus maison (M01), quel DER fait Nemotron 3 Diarization au seuil de 0,35 ?"
verdict: informatif
decisions: [D29]
---

# EXP-0037 — nemotron3-maison-seuil

## Observations factuelles

Moteur : Nemotron 3 Diarization, seuil de décision 0,35 (configuration d'EXP-0033, comme EXP-0034 et l'application), CPU. Jeu : corpus maison, M01 (voiture, environ 9 min, 3 locuteurs), référence manuelle et UEM par repères manuels (`data/processed/maison/`, non versionnées). Aucun réglage sur ce corpus. Un seul fichier : aucun intervalle de confiance.

Confidentialité : les RTTM d'hypothèse (`rttm/`) restent en local, ignorés par git ; seules les métriques agrégées sont versionnées.

| Condition d'UEM | DER c0 | Manquée | FA | Confusion | JER c0 | DER c0,25 | Manquée | FA | Confusion | JER c0,25 |
|---|---|---|---|---|---|---|---|---|---|---|
| UEM complète | 14,70 % | 6,62 | 7,35 | 0,73 | 18,43 % | 6,88 % | 3,04 | 3,55 | 0,29 | 8,03 % |
| Sans la zone de musique (A-0005) | 14,03 % | 6,59 | 6,81 | 0,63 | 17,26 % | 6,23 % | 3,07 | 2,91 | 0,24 | 6,46 % |

Écart sans musique − UEM complète : −0,67 point sans collar, −0,65 point avec collar.

Locuteurs : 3 trouvés pour 3 attendus. DER hors chevauchement 14,64 %, dans le chevauchement 15,04 % (UEM complète).

Catégories d'erreur de l'application (`app/sortie.py`, A-0005), UEM complète, en points de DER sans collar :

| Catégorie | Manquée | FA | Confusion | Total |
|---|---|---|---|---|
| Décalage de frontière | 4,68 | 5,07 | 0,55 | 10,30 |
| Chevauchement | 0,59 | 0,05 | 0,00 | 0,64 |
| Locuteur de référence non apparié | 0,00 | 0,00 | 0,00 | 0,00 |
| Locuteur trouvé en trop | 0,00 | 0,00 | 0,00 | 0,00 |
| Tour court | 0,05 | 0,13 | 0,05 | 0,23 |
| Pause courte | 0,00 | 0,21 | 0,00 | 0,21 |
| Autre | 1,31 | 1,88 | 0,14 | 3,33 |

Temps : 5,96 s de calcul, RTF 0,0108 en CPU, chargement du modèle 3,88 s. Alimentation conforme (secteur) ; `charge_concurrente` true (charge sur 1 min de 6,04, pour 6 cœurs de performance). Arbre propre à l'exécution et à l'évaluation (commit `bf460b8`). Exécution sous relevé réseau continu (`lsof`), précédée de l'essai court de D27 : aucune connexion hors local.

## Interprétation (cockpit)

Nemotron 3 fait 14,7 % de DER sans collar et 6,9 % avec collar, soit 43 % et 35 % du DER de pyannote, et trouve les trois locuteurs. Sa confusion est presque nulle (0,7 point), comme en français public (C18) : c'est là que se fait l'essentiel de l'écart avec pyannote (−13,6 points), puis sur la fausse alarme (7,4 contre 15,4 points).

Il manque un peu plus de parole que pyannote : 6,6 contre 4,3 points, soit un rapport de 1,5. C'est une trace atténuée du défaut vu sur AMI, où le rapport était d'environ 2,4 (C20). Sur M01, ce surplus de 2,3 points est largement compensé. M01 est un habitacle de voiture, avec des distances de 0,5 à 1,2 m et peu de réverbération : il ne teste pas le champ lointain d'une salle de réunion, où ce défaut a pesé sur AMI **[probable]**. Un enregistrement en salle, avec des participants à plus de 2 m du téléphone, reste nécessaire pour la condition 2 de D29.

Le RTF (0,011) est mesuré sous forte charge, comme celui de pyannote ; il n'est pas un temps de référence (D21). L'exécution sous relevé réseau, sans connexion extérieure, vérifie une partie de la condition 4 de D29 (fonctionnement hors ligne).
