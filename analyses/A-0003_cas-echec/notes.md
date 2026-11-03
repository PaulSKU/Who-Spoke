---
id: A-0003
question: "Où et pourquoi les systèmes échouent-ils : pires fichiers, descripteurs des réunions, catégories d'erreur ?"
verdict: informatif
decisions: [D28]
---

# A-0003 — cas d'échec

## Observations factuelles

Systèmes : pyannote (EXP-0001, EXP-0007, EXP-0020), baseline ECAPA (EXP-0010, EXP-0012, EXP-0021), V2 de D25 (EXP-0022, EXP-0024) ; partitions dev et test réunies (analyse descriptive). Catégories définies dans `app/sortie.py` (D28, amendement du 02/11), sur le temps, exclusives.

Répartition de l'erreur sans collar (toutes composantes) :

| Système, corpus | Décalage de frontière | Chevauchement | Réf. non appariée | Trouvé en trop | Tour court | Pause | Autre |
|---|---|---|---|---|---|---|---|
| pyannote, AMI | 51,9 % | 22,2 % | 0,3 % | 0,6 % | 0,5 % | 1,1 % | 23,4 % |
| pyannote, SUMM-RE | 67,5 % | 12,0 % | 0,8 % | 0,2 % | 0,7 % | 4,4 % | 14,5 % |
| pyannote, SUMM-RE cod08 | 50,9 % | 18,1 % | 13,1 % | 0,1 % | 0,4 % | 0,9 % | 16,5 % |
| pyannote, SUMM-RE rev08 | 53,5 % | 20,2 % | 3,7 % | 0,1 % | 0,6 % | 2,4 % | 19,6 % |
| ECAPA, AMI | 32,6 % | 18,9 % | 3,6 % | 2,8 % | 0,2 % | 0,2 % | 41,8 % |
| ECAPA, SUMM-RE | 55,0 % | 17,8 % | 4,3 % | 0,7 % | 0,6 % | 0,7 % | 20,9 % |

Corrélations de rang (DER sans collar et descripteurs, descriptives) : avec la part de chevauchement, de 0,59 (pyannote, AMI) à 0,65 (pyannote, SUMM-RE), 0,82 pour la parole manquée de pyannote sur SUMM-RE ; avec la durée moyenne d'un tour, −0,60 à −0,65. Le contrôle « décalage de frontière = erreur pardonnée par le collar » est exact pour pyannote sur AMI et SUMM-RE propre ; des écarts résiduels de −0,9 à −14,1 s apparaissent pour la baseline et pour pyannote en cod08, attribués au recalcul de l'appariement des locuteurs avec collar (cas vérifié sur 102c_EBPH). Pires fichiers : 080b_EBDH pour pyannote sur SUMM-RE (66,0 %, 2 locuteurs trouvés pour 3) ; ami__IB4002 (29,3 %), ami__ES2011a (29,0 %, 3 locuteurs trouvés pour 4) et ami__TS3003a (26,1 %, 2 pour 4) sur AMI. Huit extraits d'écoute dans `data/processed/a0003/ecoute/`.

## Interprétation (cockpit)

Trois enseignements.
1. **Une grande part du DER sans collar n'est qu'un décalage de frontière** : la moitié à deux tiers de l'erreur de pyannote. Avec collar, l'erreur restante vient d'abord du chevauchement et de zones sans cause simple.
2. **Le chevauchement est le premier facteur d'échec identifiable**, pour tous les systèmes et sur les deux corpus : c'est le descripteur le plus lié au DER, et la première catégorie hors frontière. Les réunions à tours courts et animés sont les plus difficiles.
3. **Les dégradations changent la nature de l'erreur.** Le codec bas débit fait fusionner des locuteurs : la part « locuteur de référence non apparié » passe à 13 % pour pyannote. La réverbération augmente le chevauchement manqué. Le pire fichier de pyannote en français est une réunion où un locuteur entier disparaît.

La catégorie « autre » reste importante (15 à 42 %). Elle regroupe surtout des tours entiers manqués (baseline, AMI) et des fausses alarmes hors pauses (pyannote, SUMM-RE). Ce sont des erreurs que les descripteurs de la référence ne suffisent pas à expliquer ; l'écoute des extraits par la candidate doit en préciser les causes perçues.
