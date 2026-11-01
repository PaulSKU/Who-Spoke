---
id: EXP-0010
question: "Gain réaliste des empreintes ECAPA sur AMI SDM"
verdict: retenu
decisions: [D22]
---

# EXP-0010 — baseline ECAPA (D22), AMI SDM (dev et test)

## Observations factuelles

Partition test : DER sans collar 45,9 % (parole manquée 32,3 ; fausse alarme 5,0 ; confusion 8,6), avec collar 40,9 %, JER 51,2 %, nombre de locuteurs exact 7/16. θ retenu sur dev : 1,00 (minimum intérieur à la plage balayée). Écart à EXP-0002 : −18,5 points [−23,7 ; −13,8], 15 fichiers sur 16 améliorés ; dev −21,6 [−24,9 ; −17,9], 18/18. Parole manquée et fausse alarme identiques à EXP-0002 (même détection). RTF 0,0143 en CPU, temps conforme (environ 26 s pour 30 min d'audio).

## Interprétation (cockpit)

Tout le gain vient de la confusion (27,1 → 8,6 points) : la représentation MFCC était le principal défaut d'attribution de la baseline, comme EXP-0006 le laissait prévoir. Le goulot d'étranglement s'est déplacé : la parole manquée par la détection d'énergie (et le chevauchement, qu'elle ne peut pas couvrir) représente maintenant 70 % de l'erreur restante (32,3 sur 45,9 points). ECAPA devient la représentation de la baseline pour les comparaisons suivantes.

Limites communes au lot (D22) : centrage-réduction des empreintes sur le fichier, qui pourrait pénaliser davantage WeSpeaker (empreintes conçues pour un traitement PLDA dans pyannote) **[incertain]** ; fenêtres de 1,5 s, plus courtes que les segments d'entraînement (3 s pour ECAPA) ; une seule variable changée à la fois, donc ni l'une ni l'autre n'a été testée. Les deux modèles ont été entraînés sur VoxCeleb d'après leurs recettes ; une contamination de WeSpeaker par AMI ne peut pas être exclue (`docs/corpus.md` §9).
