---
id: EXP-0013
question: "Gain réaliste des empreintes WeSpeaker sur AMI SDM"
verdict: ecarte
decisions: [D22]
---

# EXP-0013 — baseline WeSpeaker (D22), AMI SDM (dev et test)

## Observations factuelles

Partition test : DER sans collar 49,2 % (parole manquée 32,3 ; fausse alarme 5,0 ; confusion 11,9), avec collar 44,0 %, JER 51,0 %, nombre de locuteurs exact 0/16 (erreur absolue moyenne 3,2). θ retenu sur dev : 0,95. Écart à EXP-0002 : −15,2 points [−20,1 ; −10,5], 14/16 ; dev −21,0. Écart à ECAPA (EXP-0010) : +3,3 [+1,2 ; +5,9]. Écart à pyannote (EXP-0001, même modèle d'empreintes) : +29,3 points, aucun fichier meilleur, dont parole manquée +21,1, fausse alarme +1,2, confusion +7,0. RTF 0,0198 en CPU, conforme (environ 36 s pour 30 min).

## Interprétation (cockpit)

Cette expérience décompose l'avance de pyannote sur AMI, puisque les deux systèmes partagent le même modèle d'empreintes. Environ 72 % de l'écart vient de la détection (segmentation neuronale, dont le chevauchement) et environ 24 % de l'attribution. Cette dernière part s'explique par la segmentation locale sur 10 s, des empreintes calculées sur des tours d'un seul locuteur et le regroupement PLDA puis VBx, contre des fenêtres de 1,5 s et un regroupement hiérarchique cosinus. Le nombre de locuteurs n'est jamais exact alors que le DER reste proche de celui d'ECAPA : le seuil réglé sur dev pour minimiser le DER produit probablement de petits groupes parasites, qui coûtent peu de DER mais faussent le nombre affiché **[probable]**. WeSpeaker n'est jamais meilleur qu'ECAPA dans la baseline : il est écarté comme représentation par défaut, mais reste proposé dans l'interface pour montrer cette décomposition.

Limites communes au lot (D22) : centrage-réduction des empreintes sur le fichier, qui pourrait pénaliser davantage WeSpeaker (empreintes conçues pour un traitement PLDA dans pyannote) **[incertain]** ; fenêtres de 1,5 s, plus courtes que les segments d'entraînement (3 s pour ECAPA) ; une seule variable changée à la fois, donc ni l'une ni l'autre n'a été testée. Les deux modèles ont été entraînés sur VoxCeleb d'après leurs recettes ; une contamination de WeSpeaker par AMI ne peut pas être exclue (`docs/corpus.md` §9).

## Note du 01/11/2026 (D27)

Cette exécution a chargé pyannote.audio 4 sans couper sa télémétrie : elle a probablement transmis à `otel.pyannote.ai` des métadonnées (chargement des modèles, durée de chaque fichier, nombre de locuteurs demandé), sans audio. Le corpus est public. Les métriques ne sont pas affectées.
