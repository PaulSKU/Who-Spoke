---
id: A-0004
question: "La parole manquée de Nemotron 3 sur AMI s'explique-t-elle par le niveau d'enregistrement ?"
verdict: informatif
decisions: [D29]
---

# A-0004 — niveau d'entrée

## Observations factuelles

Niveau de la parole par fichier (RMS en dBFS sur les zones de parole de la référence) : médiane de −43,0 dBFS sur AMI, contre −29,1 sur SUMM-RE et les conditions de D24. Corrélation de rang entre ce niveau et la parole manquée de Nemotron 3 : −0,70 sur AMI (34 fichiers), −0,25 sur SUMM-RE, de −0,03 à −0,38 selon les conditions de D24 (`correlations.csv`).

Complément du cockpit, à partir des `per_file` d'EXP-0026 et d'EXP-0001, regroupés par site d'enregistrement d'AMI (préfixe de la réunion), parole manquée moyenne en points :

| Site (préfixe) | Fichiers | Nemotron 3 | pyannote | Niveau moyen |
|---|---|---|---|---|
| EN | 4 | 29,6 | 14,9 | −42,4 dBFS |
| ES | 8 | 25,2 | 10,4 | −46,9 dBFS |
| TS | 8 | 25,8 | 10,5 | −49,5 dBFS |
| IB | 6 | 18,4 | 7,9 | −32,2 dBFS |
| IS | 8 | 15,5 | 6,1 | −32,8 dBFS |

## Interprétation (cockpit)

La corrélation entre niveau et parole manquée est forte sur AMI, mais l'intervention la dément : amplifier jusqu'à +19 dB ne change rien (EXP-0029 à 0032). Le niveau n'est donc pas la cause. Il est le signe d'autre chose : les réunions à bas niveau sont celles de certaines salles (EN, ES, TS), plus difficiles pour les deux systèmes. Dans toutes les salles, Nemotron 3 manque environ 2,4 fois plus de parole que pyannote, et 1,6 fois plus sur SUMM-RE. C'est un comportement global, plus prudent, que le champ lointain amplifie. Le seuil de décision du modèle devient l'hypothèse suivante (D29 §1, étape 3). C'est aussi un exemple net, à présenter à l'oral, d'une corrélation qui n'est pas une cause, et que seule une expérience contrôlée permet de démêler.
