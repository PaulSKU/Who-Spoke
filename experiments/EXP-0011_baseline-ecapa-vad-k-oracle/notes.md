---
id: EXP-0011
question: "Effet pur de la représentation ECAPA (détection et nombre oracles), AMI SDM"
verdict: informatif
decisions: [D22]
---

# EXP-0011 — baseline ECAPA (D22), AMI SDM, détection et nombre de locuteurs oracles (dev et test)

## Observations factuelles

Partition test : DER sans collar 25,4 % (parole manquée 14,6 ; fausse alarme 0,1 ; confusion 10,7), avec collar 18,7 %. Écart à EXP-0006 : −23,5 points [−28,8 ; −18,6], 16/16 fichiers améliorés ; dev −27,6 [−31,5 ; −23,5], 18/18.

## Interprétation (cockpit)

Avec une détection et un nombre de locuteurs parfaits, la confusion passe de 34,2 (MFCC) à 10,7 points : c'est l'effet pur de la représentation. La parole manquée restante (14,6 points, fausse alarme quasi nulle) correspond probablement au second locuteur des zones de chevauchement, que la baseline ne peut pas produire puisqu'elle attribue un seul locuteur par fenêtre **[probable]**. La confusion est un peu plus élevée qu'en condition réaliste (EXP-0010, 8,6) : la détection oracle introduit des zones courtes ou chevauchées, difficiles à attribuer, que la détection d'énergie comptait en parole manquée **[probable]**.

Limites communes au lot (D22) : centrage-réduction des empreintes sur le fichier, qui pourrait pénaliser davantage WeSpeaker (empreintes conçues pour un traitement PLDA dans pyannote) **[incertain]** ; fenêtres de 1,5 s, plus courtes que les segments d'entraînement (3 s pour ECAPA) ; une seule variable changée à la fois, donc ni l'une ni l'autre n'a été testée. Les deux modèles ont été entraînés sur VoxCeleb d'après leurs recettes ; une contamination de WeSpeaker par AMI ne peut pas être exclue (`docs/corpus.md` §9).
