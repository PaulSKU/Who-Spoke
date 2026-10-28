# EXP-0004 — baseline MFCC, détection de parole oracle, AMI SDM (dev et test)

## Observations factuelles

Rédigées par le cockpit le 28/10/2026. Référence : EXP-0002 ; variable : détection de parole oracle (θ = 0,95 inchangé).

| Mesure (sans collar) | dev | test |
|---|---|---|
| DER | 54,23 % (EXP-0002 : 64,95) | 49,09 % (EXP-0002 : 64,38) |
| Manquée / fausse alarme / confusion | 13,51 / 0,17 / 40,55 | 14,59 / 0,14 / 34,35 |
| DER hors chevauchement / en chevauchement | 48,64 / 68,80 % | 42,25 / 66,31 % |
| Écart de DER à EXP-0002, IC à 95 % | −10,71 [−14,42 ; −7,70] ; 18/18 | −15,29 [−17,79 ; −13,07] ; 16/16 |

## Interprétation (cockpit)

**La détection par énergie coûte 11 à 15 points de DER.** Avec une détection parfaite, la parole manquée tombe de 30–32 à 13,5–14,6 points, et la fausse alarme disparaît. Ce qui reste manqué, c'est exactement le plancher du chevauchement : la baseline ne produit qu'un locuteur à la fois. Le calcul de D19 (environ 13 points) est donc vérifié.

**La confusion augmente, et ce n'est pas paradoxal.** La parole que l'énergie manquait (voix faibles, lointaines) est maintenant détectée et doit être attribuée. Elle est attribuée mal, et ce qui était de la parole manquée devient de la confusion. Une partie du gain de la détection est ainsi « reprise » par la représentation, ce qui renforce le diagnostic d'EXP-0002 et d'EXP-0003.
