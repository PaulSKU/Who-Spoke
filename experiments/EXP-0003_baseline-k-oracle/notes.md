# EXP-0003 — baseline MFCC, nombre de locuteurs oracle par fichier, AMI SDM (dev et test)

## Observations factuelles

Rédigées par le cockpit le 28/10/2026. Référence : EXP-0002 ; variable : nombre de locuteurs oracle par fichier.

| Mesure (sans collar) | dev | test |
|---|---|---|
| DER | 64,06 % (EXP-0002 : 64,95) | 63,42 % (EXP-0002 : 64,38) |
| Manquée / fausse alarme / confusion | 30,19 / 4,64 / 29,23 | 32,28 / 4,99 / 26,15 |
| JER | 72,40 % (EXP-0002 : 70,53) | 72,78 % (EXP-0002 : 70,55) |
| Écart de DER à EXP-0002, IC à 95 % | −0,89 [−2,33 ; +0,87] ; 13/18 fichiers améliorés | −0,96 [−2,44 ; +0,78] ; 12/16 |

## Interprétation (cockpit)

Connaître le bon nombre de locuteurs n'aide pas la baseline : le gain n'est pas significatif (l'intervalle contient 0), et le JER se dégrade même légèrement. Imposer quatre groupes ne sert à rien si les représentations ne séparent pas les voix : les quatre groupes restent des mélanges. EXP-0003 confirme ainsi la lecture d'EXP-0002 : le goulot de la baseline est la représentation MFCC, pas l'estimation du nombre de locuteurs.
