# EXP-0009 — baseline MFCC (D19), SUMM-RE (dev et test)

## Observations factuelles

Rédigées par le cockpit le 29/10/2026.

| Mesure | dev | test | Zoom dev | Zoom test | AMI test (EXP-0002) |
|---|---|---|---|---|---|
| DER sans collar | 46,54 % | 49,36 % | 34,52 % | 29,07 % | 64,38 % |
| Manquée / fausse alarme / confusion | 17,74 / 4,31 / 24,48 | 21,87 / 3,08 / 24,42 | 9,05 / 9,21 / 16,25 | 8,41 / 8,34 / 12,32 | 32,28 / 4,99 / 27,11 |
| DER avec collar de 0,25 s | 37,04 % | 42,66 % | 24,31 % | 19,18 % | 61,21 % |
| JER | 60,41 % | 61,17 % | 58,66 % | 44,61 % | 70,55 % |
| Nombre de locuteurs exact | 33,3 % | 45,9 % | 20 % | 100 % | 0 % |
| RTF (CPU) | 0,0009 | 0,0009 | | | 0,0015 |

Balayage de θ sur dev : minimum à θ = 1,00 (46,54 % ; 2,8 locuteurs en moyenne), contre 0,95 sur AMI (48,72 % à 0,95). Un seul locuteur pour toute la parole (θ ≥ 1,25) donne 66,55 %. Parole manquée et fausse alarme sont constantes sur toute la plage. Pires réunions : 017a_EBRZ en dev (82,8 % ; fausse alarme 39,1 points, Zoom) ; 102a_EBRH en test (72,9 % ; 4 → 2 locuteurs ; confusion 44,5 points).

## Interprétation (cockpit)

**La baseline fait mieux sur le français que sur AMI (49 % contre 64 %), parce que le signal est plus propre**, pas parce qu'elle s'adapte mieux. La parole manquée est réduite de moitié avec des micros-casques additionnés, et la confusion baisse un peu. Le diagnostic reste celui d'AMI. Elle ne gagne que 20 points sur un système à un seul locuteur (66,6 %), et la confusion plafonne autour de 24 points quel que soit θ : la représentation MFCC reste le goulot.

**Le seuil se transpose bien** (1,00 contre 0,95 sur AMI). La valeur retenue pour le français est 1,00.

**La fausse alarme de la baseline est faible (3 à 4 points), à l'inverse de celle de pyannote** (11 à 14). Les deux systèmes encadrent la référence : la baseline est prudente (beaucoup de parole manquée), pyannote est généreux. Cela conforte l'idée que la référence mot à mot est « serrée » et que la convention de fusion pèse lourd sur ce corpus. Une exception : les réunions Zoom, où la baseline prend du bruit pour de la parole (017a_EBRZ, 39 points de fausse alarme).
