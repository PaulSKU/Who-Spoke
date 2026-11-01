---
id: EXP-0015
question: "Gain réaliste des empreintes WeSpeaker en français (SUMM-RE)"
verdict: ecarte
decisions: [D22]
---

# EXP-0015 — baseline WeSpeaker (D22), SUMM-RE (dev et test)

## Observations factuelles

Partition test : DER sans collar 35,9 % (parole manquée 21,9 ; fausse alarme 3,1 ; confusion 10,9), avec collar 26,7 %, JER 44,3 %, nombre de locuteurs exact 23/37. θ retenu sur dev : 1,00. Écart à EXP-0009 : −13,5 points [−17,7 ; −9,8], 32/37 ; dev −12,9. Écart à ECAPA (EXP-0012) : +2,5 [+0,4 ; +4,3]. Écart à pyannote (EXP-0007) : +9,6 points, 4 fichiers sur 37 meilleurs, dont parole manquée +14,7, fausse alarme −8,2, confusion +3,0. RTF 0,0217 en CPU, conforme (environ 39 s pour 30 min).

## Interprétation (cockpit)

En français, l'avance de pyannote sur une baseline de même empreinte est trois fois plus faible que sur AMI (9,6 contre 29,3 points). Deux causes probables, non séparables ici : la contamination de pyannote par AMI (`docs/corpus.md` §9), et sa fausse alarme sur SUMM-RE (A-0001), qui compense une partie de son avantage en détection. La détection reste l'écart principal. Comme sur AMI, WeSpeaker est légèrement mais significativement moins bon qu'ECAPA : écarté comme représentation par défaut.

Limites communes au lot (D22) : centrage-réduction des empreintes sur le fichier, qui pourrait pénaliser davantage WeSpeaker (empreintes conçues pour un traitement PLDA dans pyannote) **[incertain]** ; fenêtres de 1,5 s, plus courtes que les segments d'entraînement (3 s pour ECAPA) ; une seule variable changée à la fois, donc ni l'une ni l'autre n'a été testée. Les deux modèles ont été entraînés sur VoxCeleb d'après leurs recettes ; une contamination de WeSpeaker par AMI ne peut pas être exclue (`docs/corpus.md` §9).
