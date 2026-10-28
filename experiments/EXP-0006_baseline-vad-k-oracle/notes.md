# EXP-0006 — baseline MFCC, détection de parole oracle et nombre de locuteurs oracle, AMI SDM (dev et test)

## Observations factuelles

Rédigées par le cockpit le 28/10/2026. Référence : EXP-0004 ; variable : nombre de locuteurs oracle (en plus de la détection oracle).

| Mesure (sans collar) | dev | test |
|---|---|---|
| DER | 51,72 % (EXP-0004 : 54,23) | 48,92 % (EXP-0004 : 49,09) |
| Manquée / fausse alarme / confusion | 13,51 / 0,18 / 38,04 | 14,59 / 0,14 / 34,19 |
| Écart de DER à EXP-0004, IC à 95 % | −2,51 [−3,76 ; −1,37] ; 14/18 | −0,16 [−2,80 ; +2,22] ; 10/16 |

## Interprétation (cockpit)

Avec la détection et le nombre de locuteurs parfaits, il ne reste que deux sources d'erreur : le chevauchement (14,6 points de parole manquée, plancher structurel de la baseline) et la représentation (34 points de confusion sur le test). **La représentation MFCC est donc responsable à elle seule de près de 70 % de l'erreur restante.** C'est la mesure la plus nette en faveur de D8 : les empreintes neuronales doivent être comparées sur cette même configuration (EXP-0006 comme référence) pour isoler leur seul effet.
