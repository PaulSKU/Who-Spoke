---
id: EXP-0012
question: "Gain réaliste des empreintes ECAPA en français (SUMM-RE)"
verdict: retenu
decisions: [D22]
---

# EXP-0012 — baseline ECAPA (D22), SUMM-RE (dev et test)

## Observations factuelles

Partition test : DER sans collar 33,4 % (parole manquée 21,9 ; fausse alarme 3,1 ; confusion 8,5), avec collar 24,4 %, JER 39,2 %, nombre de locuteurs exact 28/37. θ retenu sur dev : 1,00. Écart à EXP-0009 : −16,0 points [−19,5 ; −12,5], 36/37 fichiers améliorés ; dev −15,7 [−19,6 ; −12,2], 35/36. Temps non conforme (10 relevés sur batterie sur 52, D21) : RTF non exploité ; métriques valides.

## Interprétation (cockpit)

En français, le même schéma qu'en anglais : la confusion tombe de 24,4 à 8,5 points, et la parole manquée devient les deux tiers de l'erreur. L'écart à pyannote (EXP-0007) se réduit à 7,1 points sans collar et 9,6 avec collar (24,4 contre 14,8 %). La baseline ECAPA fait beaucoup moins de fausse alarme que pyannote (3,1 contre 11,3 points), mais beaucoup plus de parole manquée (21,9 contre 7,2). ECAPA est retenue pour la baseline.

Limites communes au lot (D22) : centrage-réduction des empreintes sur le fichier, qui pourrait pénaliser davantage WeSpeaker (empreintes conçues pour un traitement PLDA dans pyannote) **[incertain]** ; fenêtres de 1,5 s, plus courtes que les segments d'entraînement (3 s pour ECAPA) ; une seule variable changée à la fois, donc ni l'une ni l'autre n'a été testée. Les deux modèles ont été entraînés sur VoxCeleb d'après leurs recettes ; une contamination de WeSpeaker par AMI ne peut pas être exclue (`docs/corpus.md` §9).
