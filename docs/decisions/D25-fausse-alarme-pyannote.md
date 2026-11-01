# D25 — Amélioration n° 2 : fausse alarme de pyannote

Statut : actée
Date : 2026-11-01

## Contexte

Sur SUMM-RE test, la fausse alarme est la première erreur de pyannote : 11,3 points sur 26,3 sans collar (EXP-0007). D'après A-0001, elle se répartit ainsi :

- **Pauses courtes d'un même locuteur.** 34 à 44 % de la fausse alarme vient de pauses de 1 s au plus, que pyannote recouvre (84 % de ces pauses sont pontées).
- **Faux chevauchement.** Environ 1 200 s par partition.

`segmentation.min_duration_off` vaut déjà 0 : le pontage vient de la segmentation elle-même (audit du 01/11). La convention de la référence (fusion à 200 ms) a été fixée avant toute mesure, et c'est aussi celle du corpus maison.

## Décision

### 1. Variantes

Chaque variante ne change qu'une chose par rapport à la configuration d'EXP-0007.

| Variante | Principe | Réglage |
|---|---|---|
| V1 — sortie exclusive | `output.exclusive_speaker_diarization` de community-1 : au plus un locuteur par trame | Aucun |
| V2 — détection fine en post-traitement | La sortie de pyannote est intersectée avec le masque de parole de Silero VAD (licence MIT, à vérifier), qui rouvre les pauses pontées | Seuil de Silero et durée minimale de silence, réglés sur SUMM-RE dev (petite grille) |
| V3 — V1 + V2 | Combinaison | Réglage de V2 repris |

V1 ne coûte aucun calcul supplémentaire si l'enveloppe pyannote enregistre les deux sorties lors d'une même exécution.

### 2. Évaluation et règle de choix

Chaque variante est évaluée sur SUMM-RE dev et test, sur AMI dev et test et, dès qu'elles existent, sur les conditions de D24. Une variante n'est retenue pour la démonstration que si quatre conditions sont réunies :

1. sur SUMM-RE test, le gain de DER sans collar est significatif (intervalle de confiance du bootstrap apparié qui exclut 0) ;
2. sur SUMM-RE test, le DER avec collar ne se dégrade pas significativement ;
3. sur AMI test, aucune dégradation significative ;
4. sur l'ensemble des conditions dégradées de D24, aucune dégradation significative.

Si le gain n'apparaît que sans collar, il est présenté comme un meilleur accord avec la convention de découpage, et non comme un gain perçu. La convention de la référence, elle, ne change pas (D21 §2).

## Justification

La fausse alarme est la composante d'erreur la plus forte de pyannote en français. V1 et V2 s'attaquent séparément à ses deux causes mesurées, et V3 à leur somme. La règle de choix protège contre un gain propre à SUMM-RE, un corpus en micros-casques, qui serait payé ailleurs.

## Liens

D9, D21, D23, D24 ; A-0001 ; EXP-0007 ; audit du 01/11 (R-Q1, R-Q4).
