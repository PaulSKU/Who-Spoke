# D28 — Analyse des cas d'échec (A-0003) et vue spectrogramme

Statut : actée
Date : 2026-11-02

## Contexte

Le bilan du 02/11 face à l'énoncé relève deux manques. Le premier : l'énoncé demande les « cas d'échec » dans l'évaluation technique. L'interface explique chaque zone d'erreur d'un fichier, mais aucune analyse ne recense ni ne classe les échecs sur l'ensemble des corpus. Le second : l'énoncé demande de « calculer spectrogrammes et MFCC ». La baseline calcule les MFCC à partir d'un spectrogramme mel, mais rien ne les montre.

## Décision

### 1. A-0003 — cas d'échec

Analyse a posteriori (D21 §1) : aucun système n'est exécuté, seules les sorties existantes sont lues.

**Systèmes.** pyannote community-1 (EXP-0001, EXP-0007), baseline ECAPA (EXP-0010, EXP-0012). S'y ajoutent, dès qu'ils existent, les moteurs et variantes retenus (Nemotron 3, DiariZen, V2 de D25), les conditions de D24 (EXP-0020, EXP-0021) et le corpus maison.

**Calculs.**

1. Classement des fichiers par DER sans collar pour chaque système et chaque corpus, et liste des 5 pires.
2. Descripteurs de chaque fichier, tirés de la référence :
   - nombre de locuteurs ;
   - part de chevauchement ;
   - part des tours de moins de 1 s ;
   - durée moyenne d'un tour ;
   - part de parole ;
   - type de réunion (Zoom ou autre, pour SUMM-RE).

   Erreur sur le nombre de locuteurs, tirée de l'hypothèse.
3. Liens entre composantes du DER et descripteurs : corrélations de rang de Spearman, présentées comme descriptives. Les fichiers ne sont pas des tirages indépendants d'une même population, et aucun test n'est conclusif.
4. Catégorisation des secondes d'erreur de chaque système, avec les règles de la carte « Expliquer cette erreur » de l'interface, pour qu'un même constat ait partout la même définition :
   - chevauchement dans la référence ;
   - tour de référence de moins de 0,5 s ;
   - frontière de tour à 0,25 s au plus ;
   - pause de 1 s au plus ;
   - locuteur de référence non apparié (mauvais nombre de locuteurs) ;
   - autre.

   Une seconde d'erreur peut relever de plusieurs catégories. On rapporte donc chaque catégorie, ainsi que la part de l'erreur qui ne relève d'aucune.
5. Sélection de 6 à 8 extraits d'écoute, de 10 à 20 s, sur les corpus publics : un par catégorie dominante, et les pires fichiers. La candidate écoute chaque extrait et note la cause qu'elle perçoit : voix proches, rires, acquiescements, micro éloigné, bruit, etc. Ces extraits servent aussi à la démonstration. Les extraits du corpus maison restent strictement locaux et ne sont jamais publiés.

**Calendrier.** Script écrit maintenant (session outils). Première exécution après A3 et A6 (vers le 4/11). Mise à jour avec le corpus maison le 9/11. Les constats sont reportés dans `docs/constats.yaml` et la synthèse.

### 2. Vue spectrogramme

Dans l'onglet Analyse, un choix « Forme d'onde / Spectrogramme » remplace la forme d'onde par un spectrogramme en échelle mel, aligné sur la timeline et soumis au même zoom. Contraintes :

- hors ligne : greffon Spectrogram de wavesurfer 7.12.12, embarqué et vérifié comme le greffon Minimap, ou image calculée côté serveur si le greffon ne tient pas sur 30 min ;
- fluidité mesurée sur 30 min ;
- palette perceptuellement uniforme, lisible en clair et en sombre.

Pour la baseline, une option affiche en plus la courbe d'énergie et le seuil de sa détection de parole (D19), lus dans la trace du moteur. On voit ainsi pourquoi elle manque une partie de la parole (C01).

## Justification

Les cas d'échec sont demandés explicitement par l'énoncé, et c'est là que se lit la compréhension du sujet : ce qui fait échouer un système, et pas seulement de combien. La vue spectrogramme répond à la lettre de l'énoncé, et montre en démonstration ce que voit la baseline.

## Amendement du 02/11/2026 — catégories d'erreur

Statut : actée

Les catégories d'A-0003 et de la carte « Expliquer cette erreur » sont désormais définies une seule fois, dans `app/sortie.py`. Trois changements par rapport au §1 :

1. **Classement sur le temps.** Chaque seconde d'erreur reçoit une catégorie principale exclusive, par ordre de priorité (journal du 02/11). Les zones d'erreur sont découpées aux bords de la tolérance de ±0,25 s autour des frontières de la référence. La partie dans la tolérance est un « décalage de frontière », égal en secondes à l'erreur pardonnée par le collar.
2. **Locuteur trouvé en trop.** C'est une nouvelle catégorie.
3. **Tour court.** Son seuil passe de 0,5 s à 1 s. Un tour de moins de 0,5 s tient entièrement dans la tolérance de ses propres frontières : la catégorie était vide par construction. À 1 s, elle couvre les acquiescements et les interventions brèves, dont seule la partie hors tolérance est comptée.

Les secondes d'erreur sont rapportées par catégorie et par type d'erreur (parole manquée, fausse alarme, confusion). Le rapport ne donne pas seulement la catégorie : « autre » pèse 47 à 62 % de l'erreur hors tolérance dans l'essai du 02/11, et le type d'erreur est nécessaire pour l'interpréter.

## Liens

D19, D21, D24, D25, D26 ; A-0001 ; `docs/constats.yaml`.
