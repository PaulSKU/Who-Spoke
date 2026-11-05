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

