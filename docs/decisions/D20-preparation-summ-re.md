# D20 — Préparation de SUMM-RE (validation en français)

Statut : actée
Date : 2026-10-28 (proposée et actée le même jour)

## Contexte

SUMM-RE est le seul corpus libre de réunions en français (D3, `docs/corpus.md` §2) et notre jeu de validation prioritaire. Il conditionne trois suites : le nouveau réglage de θ de la baseline (D19 §4), le maintien de l'amélioration n° 1 (amendement de D9 du 28/10) et toute conclusion sur la cible. Il n'est pas directement exploitable pour la diarisation, pour quatre raisons :

- il ne fournit qu'une piste de micro-casque par participant ;
- la référence doit être reconstruite à partir d'alignements au mot ;
- il pèse 93,8 Go en tout ;
- le recouvrement de locuteurs entre partitions n'est pas documenté.

Faits établis sur la fiche Hugging Face (`linagora/SUMM-RE`, recherche du 27/10) **[certain]** : format Parquet ; champs `meeting_id`, `speaker_id`, `audio_id`, `audio`, `segments` (liste de {start, end, transcript, words: [{start, end, text}]}) et `transcript`. Le dev compte 36 conversations (130 pistes, environ 43 h de pistes, 12 h de conversation) et le test 37 conversations (124 pistes, environ 41 h de pistes, 12 h). Dev et test sont transcrits et alignés à la main. L'audio est à 48 kHz, à 32 kHz pour les réunions Zoom, avec quelques exceptions listées sur la fiche. Le code de lieu dans `meeting_id` vaut L, H, Z (Zoom) ou D. Lorsqu'une réunion n'a que trois participants, la piste du quatrième a un temps de parole nul.

## Décision

### 1. Périmètre et téléchargement

| Point | Règle |
|---|---|
| Partitions | dev et test seulement ; train exclu pour l'instant (il ne servirait qu'à un ajustement fin) |
| Version | révision du dépôt Hugging Face figée (hash consigné dans le manifeste), comme pour AMI |
| Accès | téléchargement des fichiers Parquet de `data/dev/` et `data/test/` via `huggingface_hub`, sans charger tout le jeu en mémoire |
| Brut conservé | non : après préparation réussie d'un fichier Parquet et enregistrement de son SHA-256 dans le manifeste, le brut est supprimé (environ 29 Go évités **[estimation]**). Le script peut le retélécharger à l'identique grâce à la révision figée |
| Volume conservé | mélanges à 16 kHz et références uniquement, environ 1,4 Go par partition **[estimation]** |

### 2. Construction du signal

Toutes les pistes d'une réunion sont rééchantillonnées à 16 kHz, complétées par des zéros jusqu'à la plus longue, puis additionnées et divisées par le nombre de pistes (pas d'écrêtage). La piste d'un participant sans temps de parole est incluse dans le mélange, mais ce participant n'est pas compté comme locuteur. Les pistes d'une même réunion sont supposées synchrones, puisqu'elles proviennent d'un même enregistreur ou de l'enregistrement Zoom **[probable]**. Un contrôle le vérifie en mesurant le décalage par corrélation croisée entre chaque piste et le mélange, et signale tout décalage supérieur à 50 ms.

Le résultat est une condition « micros-casques additionnés », proche d'AMI en micros-casques et non d'un micro de salle. La condition réverbérée (champ lointain simulé) fera l'objet d'une décision distincte, avec l'augmentation de données.

### 3. Construction de la référence

| Point | Règle |
|---|---|
| Unité | les mots alignés, et non les segments, qui contiennent des pauses internes |
| Découpage | union des intervalles de mots d'un même locuteur, avec fusion des écarts de 200 ms ou moins (même règle que le corpus maison, `conventions-annotation.md` §2) |
| Mots sans horodatage | remplacés par les bornes de leur segment ; leur nombre est consigné par fichier |
| Chevauchement | découle des intervalles de locuteurs différents qui se recouvrent |
| Identifiants | `summre__<meeting_id>` pour les fichiers, `speaker_id` d'origine pour les locuteurs |
| UEM | du premier mot moins 1 s au dernier mot plus 1 s, borné au signal, pour exclure d'éventuels échanges non transcrits en début et en fin d'enregistrement |

### 4. Contrôles et statistiques

| Contrôle | Attendu |
|---|---|
| Nombre de réunions et de pistes | 36 / 130 (dev), 37 / 124 (test) |
| Locuteurs par réunion dans la référence | 2 à 4 ; distribution consignée |
| Recouvrement de locuteurs entre dev et test | `speaker_id` communs comptés et consignés dans `docs/corpus.md` |
| Synchronisation des pistes | aucun décalage supérieur à 50 ms, sinon liste des réunions concernées |
| Statistiques | durée, part de parole en chevauchement et temps de parole par locuteur, par partition et pour le sous-ensemble Zoom |
| Contrôle croisé | DER sans collar entre nos références du test et celles de `ggfox00000/dia-summre-test`, réunion par réunion. C'est un contrôle de cohérence : ce dérivé n'est jamais utilisé pour noter |

### 5. Fichiers produits

`scripts/data/get_summre.py` ; `data/manifests/summre.csv` (une ligne par réunion : fichiers Parquet sources et leur SHA-256, révision, licence, durée, nombre de locuteurs) ; `data/splits/summre/dev.txt`, `test.txt`, `temps.txt` (deux réunions de test totalisant 30 à 45 min), `zoom_dev.txt` et `zoom_test.txt` ; les UEM dans `data/splits/summre/uem/`. Les références restent dans `data/processed/summre/rttm/`, non versionné. La licence CC BY-SA 4.0 autoriserait leur diffusion sous la même licence, mais rien ne l'exige ici.

### 6. Premières expériences

| Expérience | Moteur | Variable | Référence | Question |
|---|---|---|---|---|
| EXP-0007 | pyannote | — (SUMM-RE dev et test) | — | Que vaut pyannote sur des réunions en français ? |
| EXP-0008 | pyannote | nombre de locuteurs oracle | EXP-0007 | Condition de D9 : l'oracle aide-t-il quand le nombre varie ? |
| EXP-0009 | baseline | — (balayage de θ sur SUMM-RE dev, puis test) | — | Quel θ pour le français, et quel écart avec AMI ? |

Les résultats du sous-ensemble Zoom sont rapportés à part, à partir des fichiers par réunion, sans nouvelle expérience.

## Justification

Les mots alignés manuellement donnent des frontières plus fines que les segments. La même règle de fusion que celle du corpus maison rend les deux références françaises comparables. Ne pas conserver le brut est cohérent avec un disque limité, et la révision figée garantit la reproductibilité.

## Conséquences

Il faudra peut-être une dépendance pour lire le Parquet (`pyarrow`), si elle n'est pas déjà présente ; elle est à signaler. Une fois les références construites, `docs/corpus.md` §2 doit être mis à jour avec les statistiques. Sans champ lointain réel, SUMM-RE ne mesure que la langue et le style d'interaction, pas l'acoustique de la cible.

## Liens

D3, D9 (amendement du 28/10), D13, D19 ; `docs/corpus.md` §2 ; `docs/recherche/corpus-diarisation-reunions-francais.md`.
