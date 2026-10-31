# D22 — Empreintes vocales neuronales dans la baseline

Statut : actée
Date : 2026-10-31 (proposée et actée le même jour)

## Contexte

D8 prévoit de remplacer les statistiques de MFCC de la baseline par des empreintes neuronales, sans rien changer d'autre, pour isoler l'effet de la représentation. Les oracles en ont fait la priorité : sur AMI, avec détection et nombre de locuteurs parfaits, la représentation MFCC cause 34 des 49 points de DER restants (EXP-0006). Sur les deux corpus, la confusion plafonne autour de 24 à 30 points quel que soit θ (EXP-0002, EXP-0009). Le sujet demande explicitement de « comparer la baseline avec des embeddings de locuteurs et une méthode de clustering ».

## Options

| Option | Avantages | Inconvénients |
|---|---|---|
| A. ECAPA-TDNN de SpeechBrain (`speechbrain/spkrec-ecapa-voxceleb`, vecteurs de dimension 192) | Prévu par D8 ; SpeechBrain est cité par le sujet ; modèle de référence, entraîné sur VoxCeleb **[probable]** | Nouvelle dépendance ; licence et données d'entraînement à vérifier sur la fiche du modèle |
| B. Empreintes de community-1 (WeSpeakerResNet34, dimension 256), déjà installées | Aucune dépendance ; même représentation que pyannote, donc l'écart restant entre baseline et pyannote mesure exactement l'apport de la segmentation neuronale et de VBx | Contamination éventuelle par AMI à vérifier (données d'entraînement non listées sur la fiche) |
| C. Les deux | Compare deux familles d'empreintes, et décompose l'écart entre baseline et pyannote | Deux fois plus d'expériences (rapides : la baseline tourne en quelques minutes) |

## Décision

Option C. Pour chaque modèle d'empreintes, seule la représentation change, dans la baseline de D19. L'empreinte est calculée sur les seules trames de parole de chaque fenêtre (amendement 2 de D19), puis normalisée. θ est balayé à nouveau sur dev, puisque l'échelle des distances change avec la représentation : le balayage fait partie de l'expérience.

| Expérience | Représentation | Corpus | Détection, nombre de locuteurs | Référence | Question |
|---|---|---|---|---|---|
| EXP-0010 | ECAPA | AMI SDM | énergie, estimé (balayage de θ) | EXP-0002 | Gain réaliste sur AMI |
| EXP-0011 | ECAPA | AMI SDM | oracles (détection et nombre) | EXP-0006 | Effet pur de la représentation |
| EXP-0012 | ECAPA | SUMM-RE | énergie, estimé (balayage de θ) | EXP-0009 | Gain réaliste en français |
| EXP-0013 | WeSpeaker | AMI SDM | énergie, estimé (balayage de θ) | EXP-0002 | Idem |
| EXP-0014 | WeSpeaker | AMI SDM | oracles | EXP-0006 | Idem |
| EXP-0015 | WeSpeaker | SUMM-RE | énergie, estimé (balayage de θ) | EXP-0009 | Idem |

La fenêtre (1,5 s, pas de 0,75 s) est conservée. Les modèles d'empreintes sont souvent entraînés sur des segments de 2 à 3 s **[probable]**, ce qui peut désavantager des fenêtres de 1,5 s. Ce point est noté comme limite, et non corrigé ici, pour respecter la règle d'une seule variable à la fois.

## Justification

La comparaison demandée par le sujet est faite proprement : une seule variable change, sur les mêmes fichiers, avec un réglage équitable de θ pour chaque représentation. Les expériences sous oracles mesurent la qualité de la représentation indépendamment des autres étapes. Utiliser l'empreinte de pyannote dans la baseline est le moyen le plus direct de savoir ce que pyannote doit à ses empreintes, et ce qu'il doit au reste de sa chaîne.

## Conséquences

Les fichiers concernés sont `src/whospoke/pipelines/baseline.py` (représentation configurable : `mfcc`, `ecapa`, `wespeaker`), le catalogue des réglages et `docs/corpus.md` §9 (données d'entraînement des deux modèles d'empreintes). La dépendance `speechbrain` est ajoutée par `uv add`. Calcul en MPS si possible, en CPU sinon, avec le temps mesuré selon le protocole §3.5.

## Liens

D8, D19, D21 ; EXP-0002, EXP-0006, EXP-0009.
