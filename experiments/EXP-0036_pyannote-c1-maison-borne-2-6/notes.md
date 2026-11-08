---
id: EXP-0036
question: "Sur le corpus maison (M01), quel DER fait pyannote community-1 dans la configuration de démonstration ?"
verdict: informatif
decisions: [D23, D29]
---

# EXP-0036 — pyannote-c1-maison-borne-2-6

## Observations factuelles

Moteur : pyannote community-1, configuration de démonstration actuelle (EXP-0018 : EXP-0007, nombre de locuteurs borné entre 2 et 6), MPS. Jeu : corpus maison, M01 (voiture, environ 9 min, 3 locuteurs), référence manuelle et UEM par repères manuels (`data/processed/maison/`, non versionnées). Aucun réglage sur ce corpus. Un seul fichier : aucun intervalle de confiance.

Confidentialité : les RTTM d'hypothèse (`rttm/`, `rttm_exclusive/`) restent en local, ignorés par git ; seules les métriques agrégées sont versionnées.

| Condition d'UEM | DER c0 | Manquée | FA | Confusion | JER c0 | DER c0,25 | Manquée | FA | Confusion | JER c0,25 |
|---|---|---|---|---|---|---|---|---|---|---|
| UEM complète | 34,11 % | 4,34 | 15,41 | 14,37 | 55,80 % | 19,57 % | 2,06 | 7,73 | 9,78 | 48,36 % |
| Sans la zone de musique (A-0005) | 33,67 % | 4,04 | 15,08 | 14,56 | 55,70 % | 19,12 % | 1,93 | 7,31 | 9,89 | 48,19 % |

Écart sans musique − UEM complète : −0,44 point sans collar, −0,45 point avec collar.

Locuteurs : 2 trouvés pour 3 attendus (VBx : 2 groupes, avant les bornes). DER hors chevauchement 36,83 %, dans le chevauchement 19,41 % (UEM complète).

Catégories d'erreur de l'application (`app/sortie.py`, A-0005), UEM complète, en points de DER sans collar :

| Catégorie | Manquée | FA | Confusion | Total |
|---|---|---|---|---|
| Décalage de frontière | 3,02 | 10,46 | 8,11 | 21,59 |
| Chevauchement | 0,61 | 0,00 | 0,41 | 1,02 |
| Locuteur de référence non apparié | 0,03 | 0,00 | 1,84 | 1,87 |
| Locuteur trouvé en trop | 0,00 | 0,00 | 0,00 | 0,00 |
| Tour court | 0,10 | 0,18 | 0,57 | 0,85 |
| Pause courte | 0,00 | 1,07 | 0,00 | 1,07 |
| Autre | 0,58 | 3,70 | 3,44 | 7,72 |

Temps : 30,61 s de calcul, RTF 0,0555 en MPS, chargement des modèles 1,93 s. Alimentation conforme (secteur) ; `charge_concurrente` true (charge sur 1 min de 5,07 au début à 6,04, pour 6 cœurs de performance). Pas de mesure CPU. Arbre propre à l'exécution et à l'évaluation (commit `bf460b8`). Exécution sous relevé réseau continu (`lsof`), précédée de l'essai court de D27 : aucune connexion hors local.

## Interprétation (cockpit)

Sur M01, pyannote fait 34,1 % de DER sans collar et 19,6 % avec collar, soit plus du double de Nemotron 3 dans les deux conditions (EXP-0037). Deux défauts dominent.

Le premier est le regroupement. VBx ne forme que deux groupes, et la confusion atteint 14,4 points. Le locuteur le moins présent, le plus éloigné du téléphone, représente environ 7 % du temps de parole de référence (chevauchement compté par locuteur) : sa fusion dans un autre groupe explique au plus 7 points de confusion environ. Au moins 7 points restants mélangent les deux autres locuteurs **[certain, par l'arithmétique des composantes]**. Les bornes de 2 à 6 n'ont pas joué, puisque VBx est resté dans l'intervalle. Sur les corpus publics, donner le nombre exact de locuteurs n'aidait pas pyannote (C07) ; ici, l'erreur de nombre est réelle, mais elle n'explique qu'une partie de la confusion.

Le second est la fausse alarme (15,4 points), première erreur de pyannote en français comme sur SUMM-RE (C04). Sur M01, elle se trouve surtout près des frontières de tour (10,5 points à 0,25 s au plus d'une frontière de référence) et peu dans les pauses courtes (1,1 point) ; le collar la divise par deux. Une part tient probablement à la référence elle-même, dont les frontières sont serrées et excluent les respirations (conventions §2 ; C09) **[probable]**. Cette part touche aussi Nemotron 3 et ne change pas le classement des deux moteurs.

Le chevauchement n'est pas en cause : le DER hors chevauchement (36,8 %) dépasse le DER global. Point ouvert : la catégorie « décalage de frontière » (21,6 points) dépasse de 7 points l'erreur que retire le collar (14,5). Le réappariement des locuteurs sous collar en explique une partie (voir A-0003), mais l'écart n'est pas expliqué à ce stade **[incertain]**. Le RTF (0,056) est mesuré sous forte charge et n'est pas un temps de référence (D21).
