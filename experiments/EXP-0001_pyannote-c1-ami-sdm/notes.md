# EXP-0001 — pyannote community-1 par défaut, AMI SDM (dev et test)

## Observations factuelles

Rédigées par le cockpit le 28/10/2026, à partir de `results_ami_*.json` et `per_file_ami_*.csv`.

| Mesure (sans collar, chevauchements comptés) | dev (18) | test (16) |
|---|---|---|
| DER | 18,64 % | 19,92 % |
| Manquée / fausse alarme / confusion (points) | 8,10 / 4,86 / 5,68 | 11,16 / 3,81 / 4,94 |
| DER avec collar de 0,25 s | 11,15 % | 13,21 % |
| JER | 23,75 % | 27,07 % |
| Part de la parole de référence en chevauchement | 25,7 % | 27,0 % |
| DER sur les zones sans chevauchement / avec chevauchement | 13,55 % / 33,37 % | 13,76 % / 36,59 % |
| Part de l'erreur totale située en chevauchement | 46 % | 50 % |
| Nombre de locuteurs exact | 16/18 | 12/16 |
| Erreurs sur le nombre de locuteurs (réel → estimé) | IS1008b 4→5 ; ES2011a 4→3 | IS1009b 4→5 ; ES2004b 4→6 ; ES2004c 4→5 ; TS3003a 4→2 |
| DER par réunion (min – max) | 9,96 – 29,31 % | 11,00 – 26,10 % |
| RTF en MPS | 0,0504 (ensemble des deux jeux) | 0,0509 |

RTF en CPU seul (6 fils), sur ES2004a et TS3003a (42,6 min) : 0,798. Chargement des modèles : 6,05 s (MPS). Réunions de test au DER le plus élevé : TS3003a (26,10 % ; 2 locuteurs estimés sur 4 ; JER 69,8 %), EN2002d (26,00 % ; 49,6 % de la parole en chevauchement), ES2004a (25,23 %). La parole manquée domine dans les trois.

## Interprétation (cockpit)

**Reproduction.** Le DER de test sans collar (19,92 %) reproduit la valeur publiée pour community-1 sur AMI SDM (19,9 %). Toute la chaîne est donc validée de bout en bout : partition, références `only_words`, UEM, normalisation audio, entrée en mémoire, métriques et agrégation. Ce chiffre ne mesure pas la généralisation, puisque AMI fait partie de l'entraînement de pyannote (`docs/corpus.md` §9) : c'est une borne optimiste.

**Le chevauchement est la faiblesse principale.** Il ne représente qu'un peu plus d'un quart de la parole de référence, mais concentre la moitié de l'erreur, avec un DER de 37 % dans ces zones contre 14 % ailleurs. Cela explique la domination de la parole manquée : quand deux personnes parlent, le système n'en retient souvent qu'une. EN2002d, la réunion la plus chevauchée du test (près de 50 %), fait partie des trois pires.

**L'estimation du nombre de locuteurs se trompe dans un quart des réunions de test, dans les deux sens.** Trois surestimations (5 ou 6 au lieu de 4) et une forte sous-estimation (TS3003a, 2 au lieu de 4). TS3003a illustre ce que le JER apporte : son DER (26 %) reste comparable aux autres, alors que deux des quatre participants ont disparu. Ils parlent peu, si bien que le DER, pondéré par le temps, les masque ; le JER (70 %) les révèle. **[probable : à confirmer par le temps de parole par locuteur dans la référence]**.

**Frontières.** Le collar retire 6,7 points de DER sur le test. En durée, il supprime la moitié des secondes d'erreur (6 119 s contre 3 122 s), mais il exclut aussi 23 % de la parole de référence (30 714 s contre 23 629 s). Une part importante de l'erreur se situe donc près des frontières, dans des zones où l'annotation de référence est elle-même imprécise.

**Temps de calcul.** En MPS, une réunion de 30 min se traite en environ 1 min 30 s ; en CPU seul, en environ 24 min (RTF de 0,80). Le CPU seul reste utilisable hors ligne, mais il est trop lent pour une démonstration confortable sans GPU Apple.

**Conséquences pour la suite.** L'amélioration n° 1 (estimation du nombre de locuteurs, D9) est confirmée comme pertinente. Le chevauchement est le candidat naturel pour l'amélioration n° 2, à confirmer sur le jeu francophone, comme le prévoit D9. EXP-0001 devient l'expérience de référence de pyannote sur AMI. La prochaine comparaison utile ajoute le mode « nombre de locuteurs imposé » (oracle) sur les mêmes fichiers, pour mesurer exactement le coût de l'estimation.
