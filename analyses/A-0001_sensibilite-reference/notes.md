# A-0001 — sensibilité de la référence de SUMM-RE

## Observations factuelles

Rédigées par le cockpit le 31/10/2026, à partir de `resultats.csv` et `repartition_erreurs.csv`.

**DER selon la variante de référence** (jetons non lexicaux retirés ; entre parenthèses, avec collar de 0,25 s) :

| Système, partition | 200 ms (officielle) | 300 ms | 500 ms | 1 000 ms |
|---|---|---|---|---|
| pyannote, dev | 26,00 (10,76) | 25,11 (10,73) | 22,39 (10,86) | 18,35 (11,36) |
| pyannote, test | 26,30 (14,82) | 26,26 (14,87) | 25,72 (14,89) | 21,13 (14,72) |
| baseline, dev | 46,54 (37,04) | 46,69 (37,82) | 47,29 (39,79) | 49,00 (43,84) |
| baseline, test | 49,36 (42,66) | 49,34 (42,70) | 49,48 (43,12) | 51,43 (47,03) |

Conserver les jetons non lexicaux change le DER sans collar de pyannote de −1,7 point en dev et de +0,1 point en test.

**Répartition des erreurs (référence officielle, sans collar)** :

| | pyannote dev | pyannote test | baseline dev | baseline test |
|---|---|---|---|---|
| Fausse alarme totale | 5 447 s | 4 711 s | 1 648 s | 1 286 s |
| (a) dans les pauses d'un même locuteur ≤ 1 s | 2 381 s (43,7 %) | 1 613 s (34,2 %) | 513 s (31,2 %) | 253 s (19,7 %) |
| (b) dans les pauses entre locuteurs ≤ 1 s | 872 s (16,0 %) | 892 s (18,9 %) | 346 s (21,0 %) | 309 s (24,1 %) |
| (c) ailleurs | 2 193 s (40,3 %) | 2 206 s (46,8 %) | 788 s (47,8 %) | 724 s (56,3 %) |
| dont pendant la parole de la référence (second locuteur en trop) | 1 213 s | 1 158 s | 0 s | 0 s |
| dont silences de plus de 1 s | 957 s | 1 022 s | 771 s | 702 s |
| Part des pauses d'un même locuteur ≤ 1 s couvertes par une fausse alarme | 84 % (2 381 / 2 829 s) | 84 % (1 613 / 1 924 s) | 18 % | 13 % |
| Parole manquée sur des tours de moins de 0,5 s | 9,8 % | 7,6 % | 7,2 % | 5,9 % |

La référence de dev contient deux fois plus de pauses courtes d'un même locuteur que celle de test (5 531 pauses, 2 829 s contre 2 965 pauses, 1 924 s), pour une parole de référence comparable. Les jetons de pause courte « + » n'apparaissent que dans dev (2 285 contre 0).

## Interprétation (cockpit)

**L'hypothèse est confirmée, mais elle n'explique que la moitié de la fausse alarme de pyannote.** pyannote ne découpe pas ses tours sur les pauses courtes : il recouvre 84 % de la durée des pauses de 1 s au plus d'un même locuteur, dans les deux partitions. Ces pauses expliquent 34 à 44 % de sa fausse alarme, et les pauses courtes entre locuteurs 16 à 19 % de plus. Le reste a deux causes qui ne tiennent pas à la convention. La première est un **faux chevauchement** : environ 1 200 s par partition (22 à 25 % de la fausse alarme), où pyannote ajoute un second locuteur alors qu'un seul parle. La seconde est de la parole posée sur des silences de plus de 1 s (environ 1 000 s).

**Le DER avec collar est robuste à la convention, pas le DER sans collar.** Avec collar, les variantes ne déplacent le DER de pyannote que de 0,6 point au plus. Sans collar, elles le déplacent de 5 à 8 points. Le classement des deux systèmes ne change dans aucune variante, et la baseline se dégrade quand la fusion s'allonge, puisqu'elle découpe finement et manque d'autant plus de parole. Sur SUMM-RE, le DER sans collar mesure donc en partie l'accord entre la granularité du système et celle de la référence. Il faut le lire avec le DER avec collar.

**Décision : pas de changement de convention.** Conformément à D21 §2, la référence reste à 200 ms. Ce seuil est celui de DIHARD et du corpus maison, et un annotateur humain sépare bien deux tours au-delà de pauses de cet ordre **[probable]**. Le changer parce qu'il pénalise pyannote reviendrait à ajuster la mesure au système. En revanche, tout résultat sur SUMM-RE sera rapporté dans les deux conditions de collar, avec un renvoi à cette analyse.

**Une hétérogénéité entre partitions, à signaler.** Les jetons « + » n'existent que dans dev, et dev contient deux fois plus de pauses courtes que test. Les deux partitions semblent avoir été transcrites avec des conventions de pause différentes **[probable]**. Cela explique pourquoi la variante à 500 ms fait baisser le DER de pyannote de 3,6 points en dev, contre 0,6 en test. Cela fragilise aussi un réglage fait sur dev et appliqué au test, pour toute grandeur liée aux frontières. θ, qui ne règle que le regroupement, n'est pas concerné. La limite est à consigner dans `docs/corpus.md` §2.

**Deux pistes d'amélioration, à garder pour l'ablation.** (1) Le faux chevauchement de pyannote coûte environ 3 points de DER. Un post-traitement qui supprime les seconds locuteurs très courts, ou la sortie « exclusive » de community-1, en est le test direct. Le gain serait à mettre en balance avec la parole perdue dans les vrais chevauchements, plus fréquents dans les réunions denses comme 008a_EARH. (2) Les écarts entre dev et test rappellent qu'aucun réglage de frontière ne doit être choisi sur SUMM-RE dev seul.
