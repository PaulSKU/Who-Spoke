# EXP-0002 — baseline MFCC (D19), AMI SDM (dev et test)

## Observations factuelles

Rédigées par le cockpit le 28/10/2026, à partir de `results_ami_*.json` et `balayage_ami_dev.csv`.

| Mesure (sans collar, chevauchements comptés) | dev | test | EXP-0001 (pyannote), test |
|---|---|---|---|
| DER | 64,95 % | 64,38 % | 19,92 % |
| Manquée / fausse alarme / confusion (points) | 30,20 / 4,64 / 30,11 | 32,28 / 4,99 / 27,11 | 11,16 / 3,81 / 4,94 |
| DER avec collar de 0,25 s | 61,50 % | 61,21 % | 13,21 % |
| JER | 70,53 % | 70,55 % | 27,07 % |
| DER hors chevauchement / en chevauchement | 62,52 / 70,54 % | 61,70 / 70,06 % | 13,76 / 36,59 % |
| Nombre de locuteurs : erreur moyenne / taux exact | 2,06 / 11,1 % | 2,00 / 0 % | 0,38 / 75 % |
| RTF (CPU seul) | 0,0014 | 0,0015 | 0,80 |

Balayage de θ sur dev : le DER sans collar passe de 96,8 % (θ = 0,50, 367 locuteurs en moyenne) à un minimum de 64,95 % (θ = 0,95, 6,1 locuteurs), puis remonte jusqu'à 74,34 % (θ ≥ 1,25, un seul locuteur). Sur toute la plage, la parole manquée reste à 30,2 points et la fausse alarme à 4,6 points : θ n'agit que sur la confusion. À θ = 1,00, le DER est presque le même (65,06 %) avec 2,9 locuteurs en moyenne. La baseline fait moins bien que pyannote sur chaque réunion (18/18 en dev, 16/16 en test). Écart de DER sur le test : +44,5 points, IC à 95 % [40,7 ; 48,7], bootstrap apparié.

## Interprétation (cockpit)

**La représentation MFCC ne distingue presque pas les voix en champ lointain.** Un système trivial qui attribue toute la parole détectée à un seul locuteur (θ ≥ 1,25) atteint 74,3 % de DER. La baseline réglée ne gagne que 9,4 points sur ce système. Quel que soit le seuil, la confusion ne descend pas en dessous de 27 à 30 points. Le seuil n'est pas en cause : c'est la représentation qui plafonne, et le nombre de locuteurs estimé n'en est qu'un symptôme (0 réunion de test avec le bon nombre). C'est l'argument pour D8 : remplacer les seules statistiques MFCC par des empreintes neuronales, toutes choses égales par ailleurs.

**La détection par énergie manque près d'un tiers de la parole.** La parole manquée est de 30 à 32 points, contre 8 à 11 pour pyannote. Le chevauchement en explique une partie (un plancher d'environ 13 points, D19 **[probable]**). Le reste, soit environ 17 à 19 points, est vraisemblablement de la parole faible ou lointaine jugée silencieuse par le seuil d'énergie (α = 0,3) **[probable]**. La fausse alarme est basse (5 points) : le seuil est prudent. EXP-0004 (détection oracle) chiffrera exactement la part de la détection.

**Le collar ne change presque rien** (−3 points, contre −6,7 pour pyannote) : les erreurs de la baseline sont massives, elles ne tiennent pas à des frontières mal placées.

**Le coût est minime.** Avec un RTF de 0,0015, une réunion de 30 min se traite en 3 s sur CPU, environ 500 fois plus vite que pyannote en CPU. Cet écart est un élément du compromis à présenter.

**Suite.** Les oracles (EXP-0003 : nombre de locuteurs ; EXP-0004 : détection ; EXP-0005 : nombre de locuteurs pour pyannote) répartiront précisément l'erreur entre les étapes. EXP-0002 reste la référence de la baseline. θ devra être réglé à nouveau sur SUMM-RE dev.
