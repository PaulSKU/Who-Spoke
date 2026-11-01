---
id: EXP-0014
question: "Effet pur de la représentation WeSpeaker (détection et nombre oracles), AMI SDM"
verdict: informatif
decisions: [D22]
---

# EXP-0014 — baseline WeSpeaker (D22), AMI SDM, détection et nombre de locuteurs oracles (dev et test)

## Observations factuelles

Partition test : DER sans collar 27,6 % (parole manquée 14,6 ; fausse alarme 0,1 ; confusion 12,9), avec collar 21,0 %. Écart à EXP-0006 : −21,3 points [−25,9 ; −16,9], 15/16 ; dev −26,3. Écart à ECAPA sous oracles (EXP-0011) : +2,2 [−0,1 ; +4,6].

## Interprétation (cockpit)

Sous oracles, l'écart entre WeSpeaker et ECAPA n'est pas significatif : comme représentations, les deux ne se distinguent pas sur cet échantillon. L'écart significatif en condition réaliste (EXP-0013) vient donc plutôt de l'interaction avec le regroupement par seuil, c'est-à-dire l'estimation du nombre de locuteurs **[probable]**.

Limites communes au lot (D22) : centrage-réduction des empreintes sur le fichier, qui pourrait pénaliser davantage WeSpeaker (empreintes conçues pour un traitement PLDA dans pyannote) **[incertain]** ; fenêtres de 1,5 s, plus courtes que les segments d'entraînement (3 s pour ECAPA) ; une seule variable changée à la fois, donc ni l'une ni l'autre n'a été testée. Les deux modèles ont été entraînés sur VoxCeleb d'après leurs recettes ; une contamination de WeSpeaker par AMI ne peut pas être exclue (`docs/corpus.md` §9).
