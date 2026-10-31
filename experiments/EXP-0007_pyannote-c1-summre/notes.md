# EXP-0007 — pyannote community-1, SUMM-RE (dev et test)

## Observations factuelles

Rédigées par le cockpit le 29/10/2026, à partir des résultats et des fichiers par réunion.

| Mesure | dev (36) | test (37) | Zoom dev (5) | Zoom test (3) | AMI test (EXP-0001) |
|---|---|---|---|---|---|
| DER sans collar | 26,00 % | 26,30 % | 17,19 % | 17,39 % | 19,92 % |
| Manquée / fausse alarme / confusion | 5,13 / 14,24 / 6,64 | 7,15 / 11,28 / 7,87 | 4,50 / 6,63 / 6,06 | 4,27 / 6,86 / 6,26 | 11,16 / 3,81 / 4,94 |
| DER avec collar de 0,25 s | 10,76 % | 14,82 % | 7,20 % | 8,64 % | 13,21 % |
| Fausse alarme en secondes, sans → avec collar | 5 447 → 1 319 | 4 711 → 1 386 | | | |
| DER hors / en chevauchement | 24,45 / 31,13 % | 23,57 / 33,17 % | 14,88 / 29,41 % | 15,77 / 30,11 % | 13,76 / 36,59 % |
| JER | 29,28 % | 28,73 % | 31,24 % | 30,32 % | 27,07 % |
| Nombre de locuteurs exact | 33/36 | 31/37 | 3/5 | 1/3 | 12/16 |
| RTF | 0,051 (MPS) | 0,050 (MPS) ; 0,783 (CPU) | | | |

Réunions au DER le plus élevé. En dev : 097c_EBPH (41,3 % ; 4 → 3 locuteurs ; 44,9 % de la parole en chevauchement), 033c_EBPH (36,5 % ; fausse alarme 20,3 points ; 38,7 %), 097b_EBDH (35,7 % ; 45,5 %). En test : 080b_EBDH (66,0 % ; 3 → 2 locuteurs ; confusion 45,5 points), 008a_EARH (44,9 % ; parole manquée 33,5 points ; 71,5 % de la parole en chevauchement), 102c_EBPH (38,4 % ; 42,3 %).

## Interprétation (cockpit)

**Le DER sans collar est plus élevé qu'à AMI, mais pas pour les mêmes raisons.** Sur AMI, l'erreur dominante était la parole manquée. Ici, c'est la fausse alarme (11 à 14 points), alors que le signal est plus propre (micros-casques additionnés) et le chevauchement plus faible. Trois quarts des secondes de fausse alarme disparaissent avec un collar de 0,25 s, et le DER avec collar (14,8 % sur le test) redevient comparable à celui d'AMI (13,2 %). La fausse alarme se situe donc presque entièrement contre les frontières de la référence. L'explication la plus vraisemblable tient à la convention de référence, pas au système. Notre référence, construite mot à mot, compte comme silence toute pause de plus de 200 ms, alors que pyannote produit des tours continus qui enjambent ces pauses **[probable]**. C'est à vérifier en réévaluant les RTTM existants contre des variantes de la référence (fusion à 300 et 500 ms, jetons non lexicaux conservés).

**Les réunions Zoom sont les plus faciles** (17 % sans collar, 7 à 9 % avec), en cohérence avec leur faible chevauchement (7 à 10 %).

**Les échecs ont deux visages.** 080b_EBDH est un échec de regroupement : un locuteur manquant, et 45 points de confusion. 008a_EARH est un échec de chevauchement : 71,5 % de la parole s'y superpose, et la parole manquée atteint 33,5 points. L'écoute de ces deux réunions (protocole §7) reste à faire ; c'est à la candidate de la mener.
