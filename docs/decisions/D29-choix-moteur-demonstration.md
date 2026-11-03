# D29 — Choix du moteur de démonstration : pyannote ou Nemotron 3 Diarization

Statut : actée (règle de choix) ; décision finale le 9/11
Date : 2026-11-03

## Contexte

D23 prévoit de rediscuter le moteur de démonstration avant le gel du 10/11, si un moteur local dépasse pyannote en français. C'est le cas de Nemotron 3 Diarization (EXP-0026 à 0028), avec trois résultats :

| Jeu (test, DER sans collar) | Nemotron 3 | pyannote | Écart (IC à 95 %) |
|---|---|---|---|
| SUMM-RE | 14,6 % | 26,3 % | −11,7 [−15,3 ; −8,3], 36 fichiers sur 37 meilleurs |
| D24, 7 conditions | 14,8 à 18,5 % | 25,5 à 41,2 % | −10,5 à −25,2, tous significatifs ; −25,2 en rev08 |
| AMI SDM | 27,5 % | 19,9 % | +7,6 [+5,5 ; +9,5], 15 fichiers sur 16 moins bons |

Nemotron 3 tourne en CPU avec un RTF de 0,012, environ 22 s pour 30 min d'audio. En MPS, il plante. Ses confusions sont presque nulles, mais il manque plus de parole : sur AMI, 24,9 points de parole manquée contre 11,2 pour pyannote, y compris hors chevauchement (DER hors chevauchement de 23,4 % contre 13,8 %). Ce défaut ne dépend pas de la durée des réunions (corrélation de rang de 0,05 sur AMI). AMI est en champ lointain, comme la cible. Ce défaut est donc un risque réel, qu'il faut comprendre avant de choisir.

Pour éviter de choisir après avoir vu les résultats du corpus maison, la règle de choix est fixée ici, avant ces résultats.

## Décision

### 1. Diagnostic préalable (piste A, borné à 3 h de travail)

Deux hypothèses sur la parole manquée de Nemotron 3 sur AMI, testées dans cet ordre :

1. **Niveau d'entrée.** Le micro distant d'AMI enregistre à bas niveau, et Nemotron 3 serait sensible au niveau, alors que les conditions dégradées de D24 sont produites à un niveau normalisé. On mesure le niveau de parole par fichier et sa corrélation avec la parole manquée. Si le lien existe, une normalisation du niveau en entrée est testée **pour les deux moteurs** : une seule variable, AMI et SUMM-RE, dev et test.
2. **Seuil de décision** (sigmoïde, 0,5 par défaut). Il est réglé sur SUMM-RE dev seulement, puis évalué sur les tests et sur AMI, selon les règles de D25.

Une correction n'est retenue qu'aux conditions de D25 : gain significatif sur le jeu visé, et aucune dégradation significative sur les autres.

### 2. Règle de choix (appliquée le 9/11)

Nemotron 3 devient le moteur de démonstration si les quatre conditions sont réunies :

1. **Français public.** Il reste significativement meilleur que pyannote sur SUMM-RE test et sur l'ensemble des conditions de D24 (acquis à ce jour).
2. **Champ lointain.** Après le diagnostic, il n'est pas significativement moins bon que pyannote sur AMI test. À défaut, l'écart restant est expliqué et ne se retrouve pas sur le corpus maison (condition 3).
3. **Corpus maison** (réunions réelles en français, test décisif) : son DER total sans collar n'est pas supérieur à celui de pyannote, et il n'est pas moins bon sur la majorité des enregistrements. Lecture descriptive, sans test statistique ; le DER avec collar est donné aussi.
4. **Pratique.** Il est intégré à l'application, fonctionne hors ligne, a été vérifié sur un fichier de 30 min et a passé l'essai de démonstration.

Sinon, pyannote reste le moteur de démonstration (configuration d'EXP-0007, bornes de 2 à 6 locuteurs). Dans les deux cas, l'autre moteur reste proposé dans l'application, pour la comparaison.

### 3. DiariZen

Il est écarté de l'évaluation. Il s'installe, mais tourne à un RTF de 2,1 en CPU (environ 1 h pour une réunion de 30 min, et 90 h pour les deux corpus de test) et plante en MPS avec la version de torch qu'il impose. L'échec est documenté et tient au calcul, pas à l'installation. Il ne peut pas être un moteur de démonstration.

## Justification

Fixer la règle avant les résultats du corpus maison empêche de choisir le moteur après coup. La règle donne au corpus maison, seul test réel en français et en champ lointain, le dernier mot. Elle ne retient pas pour autant un moteur qui serait nettement moins bon en champ lointain sans explication.

## Amendement du 04/11/2026 — bilan du diagnostic

Statut : actée

- **Niveau d'entrée.** Écarté : une normalisation sans effet (EXP-0029 à 0032), et une corrélation expliquée par les salles d'AMI (A-0004).
- **Seuil de décision.** Retenu à 0,35, réglé sur SUMM-RE dev. Il donne un gain faible mais significatif partout (EXP-0033 à 0035). Nemotron 3 est désormais évalué et proposé avec ce seuil.
- **Condition 2.** Elle n'est pas remplie par AMI : l'écart à pyannote reste de +6,5 points [+4,8 ; +8,2], dû à une parole manquée environ deux fois plus forte. L'écart est caractérisé (prudence générale du modèle, amplifiée en champ lointain), mais sa cause n'est pas identifiée.

Conformément au §2, c'est le corpus maison qui tranche : Nemotron 3 n'est retenu que si son avantage en français se confirme en salle réelle et si sa parole manquée n'y réapparaît pas. On ne lance plus d'autre expérience sur les corpus publics.

## Liens

D23, D24, D25, D17 ; EXP-0001, EXP-0007, EXP-0020, EXP-0026 à EXP-0028 ; `docs/corpus.md` §9.
