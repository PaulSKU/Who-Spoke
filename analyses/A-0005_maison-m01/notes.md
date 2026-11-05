---
id: A-0005
question: "Sur M01, que coûte la zone de musique à chaque moteur, et quelles catégories d'erreur composent leur DER ?"
verdict: informatif
decisions: [D29]
---

# A-0005 — maison-m01

## Observations factuelles

Sources : hypothèses d'EXP-0036 (pyannote community-1, bornes 2 à 6) et d'EXP-0037 (Nemotron 3, seuil 0,35), gardées en local ; référence et UEM de M01 dans `data/processed/maison/`. Deux conditions d'UEM : complète, et sans la zone de musique sans paroles notée dans la fiche de séance (15,6 s retirées ; parole annotée dessous). L'UEM réduite reste hors de git (`data/processed/maison/uem_sans_musique/`) ; son empreinte est dans `execution.json`. Un seul fichier : aucun intervalle de confiance.

| Moteur | Condition | DER c0 | Manquée | FA | Confusion | DER c0,25 | JER c0 | Locuteurs (réf. 3) |
|---|---|---|---|---|---|---|---|---|
| pyannote (EXP-0036) | UEM complète | 34,11 % | 4,34 | 15,41 | 14,37 | 19,57 % | 55,80 % | 2 |
| pyannote (EXP-0036) | sans musique | 33,67 % | 4,04 | 15,08 | 14,56 | 19,12 % | 55,70 % | 2 |
| Nemotron 3 (EXP-0037) | UEM complète | 14,70 % | 6,62 | 7,35 | 0,73 | 6,88 % | 18,43 % | 3 |
| Nemotron 3 (EXP-0037) | sans musique | 14,03 % | 6,59 | 6,81 | 0,63 | 6,23 % | 17,26 % | 3 |

Catégories d'erreur (`categories.csv`) : carte des erreurs de l'application, sans collar, référence et hypothèse coupées à l'UEM comme dans A-0003 ; elles somment aux composantes du DER sans collar (contrôle à 0,01 point dans le script). Tableaux par moteur dans les notes d'EXP-0036 et d'EXP-0037.

Les métriques de l'UEM complète redonnent exactement celles de `scripts/evaluate.py` (34,11 % et 14,70 %). Arbre propre (commit `bf460b8`).

## Interprétation (cockpit)

La musique coûte peu aux deux moteurs. Retirer ses 15,6 s, soit 2,9 % de l'UEM, fait baisser le DER de 0,4 point pour pyannote et de 0,7 point pour Nemotron 3, avec ou sans collar. Le passage est donc un peu plus difficile que la moyenne, sans changer l'écart entre les deux. Sur 15 s, cette lecture reste descriptive.

Les catégories confirment deux profils distincts. Pour pyannote, l'erreur est d'abord aux frontières (21,6 points), puis dans « autre » (7,7 points, fausse alarme et confusion à parts presque égales). Pour Nemotron 3, elle est aux frontières (10,3 points), partagée entre parole manquée et fausse alarme, avec une confusion négligeable. La catégorie « locuteur de référence non apparié » reste faible pour pyannote (1,9 point), alors qu'un locuteur n'a pas de groupe. L'ordre de priorité des catégories range d'abord aux frontières la parole de ce locuteur, faite de tours courts **[probable]**.
