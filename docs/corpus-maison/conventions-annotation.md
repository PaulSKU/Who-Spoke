# Conventions d'annotation du corpus maison

Version 1.0 du 27 octobre 2026. Ces conventions s'appliquent aussi aux références reconstruites à partir d'autres corpus (SUMM-RE), afin que toutes les références françaises soient comparables. Toute modification passe par une fiche de décision.

**Légende de confiance.** **[certain]** : vérifié. **[probable]** : non revérifié. **[incertain]** : à vérifier.

---

## 1. Ce que l'on annote

Pour chaque locuteur, les intervalles de temps pendant lesquels il parle. On n'annote ni ce qui est dit ni qui est la personne (un code `S1`, `S2`… suffit).

| Phénomène | Convention |
|---|---|
| Parole, y compris les mots inachevés et les hésitations (« euh ») | Parole |
| Acquiescements verbaux brefs (« oui », « mm », « d'accord ») | Parole, même pendant que quelqu'un d'autre parle |
| Rires, toux, respirations, raclements de gorge | **Non-parole** (non annotés) |
| Rire mêlé à des mots | Parole |
| Chevauchement | Chaque locuteur est annoté indépendamment ; les intervalles se recouvrent |
| Voix extérieure (passant, télévision, personne hors réunion) | Non annotée ; noter l'intervalle dans la fiche de session et l'exclure de l'UEM s'il est long |
| Claquements de mains et annonces de début et de fin | Hors UEM |

Le traitement des rires et des bruits respiratoires varie d'un corpus à l'autre. Nos conventions sont proches de VoxConverse, qui n'attribue pas les rires **[probable, d'après les notes de recherche]**. Elles diffèrent de DIHARD III, qui inclut davantage de phénomènes **[probable]**. Ce choix est consigné dans `docs/corpus.md`.

## 2. Règles de découpage

| Règle | Valeur |
|---|---|
| Fusion | Deux segments d'un même locuteur séparés par une pause de **200 ms ou moins** sont fusionnés. C'est la convention de DIHARD III **[probable]**, appliquée automatiquement par le script de conversion |
| Durée minimale | Aucune ; un « mm » de 150 ms reste un segment |
| Précision des frontières | Viser environ ±50 ms, en zoomant sur la forme d'onde au début et à la fin de chaque segment |
| UEM | Du claquement de début + 1 s au claquement de fin − 1 s, moins les zones exclues pour voix extérieure |

## 3. Outil et format

L'outil est **Audacity**, avec une piste de labels par locuteur, nommée `S1`, `S2`… Chaque label couvre un segment de parole. L'export se fait par *Fichier > Exporter > Exporter les labels*, une piste à la fois, sous `M0x_S1.txt`… Le format exporté est une ligne par segment : début, fin et texte, séparés par des tabulations. Ce format est simple et se convertit facilement en RTTM. ELAN est une alternative plus puissante, mais l'export en RTTM demande un convertisseur supplémentaire.

## 4. Chaîne de production de la référence

| Étape | Action | Outil |
|---|---|---|
| 1 | Aligner les pistes d'aide sur le signal de test grâce aux deux claquements, en corrigeant la dérive | Script (à écrire) |
| 2 | Pré-annoter : détection de parole par énergie sur chaque piste d'aide, puis export en labels Audacity | Script (à écrire) |
| 3 | **Corriger à l'écoute** sur le signal de test : supprimer la voix des voisins captée par chaque piste d'aide, ajuster les frontières, ajouter les acquiescements manqués | Audacity |
| 4 | Convertir les labels en RTTM, avec fusion à 200 ms, et produire l'UEM | Script (à écrire) |
| 5 | Contrôler : vérifier qu'aucun segment ne sort de l'UEM, que chaque locuteur a des segments et que les statistiques sont plausibles (taux de chevauchement, temps de parole par personne) | Script (à écrire) |

Sans piste d'aide (visio sans pistes séparées), on saute les étapes 1 et 2 et on annote à partir de zéro. Ne **jamais** pré-annoter avec pyannote ni avec aucun système évalué dans le projet : la référence favoriserait ce système.

## 5. Contrôle qualité

Pour connaître le bruit de la référence elle-même, on ré-annote **deux minutes** d'une session, à partir de zéro, au moins un jour après la première annotation. On calcule ensuite le DER entre les deux versions (condition `collar_0`). Ce chiffre est un plancher : aucun système ne peut être jugé meilleur qu'à cette précision près. Il est consigné dans `docs/corpus.md`.

## 6. Coût estimé

Avec pré-annotation à partir des pistes d'aide, il faut compter environ 3 à 5 heures de travail par heure d'audio, soit **2 à 3 heures pour les 30 minutes du corpus maison**, plus environ une heure pour M02 si elle est annotée à partir de zéro **[estimation, à partir des coûts publiés pour la vérification de références VoxConverse et des mesures de Broux et al., 2018]**. Le temps réel est noté dans le journal, car c'est en soi une donnée intéressante pour le rendu.
