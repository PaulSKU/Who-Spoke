# Glossaire

Concepts et vocabulaire du projet, au format de `docs/methode.md` §4.6, triés alphabétiquement. Version 1.0 du 27 octobre 2026 (séance de compréhension de la chaîne, cockpit).

**Légende de confiance.** **[certain]** : vérifié. **[probable]** : non revérifié. **[incertain]** : à vérifier.

## La chaîne en une phrase

Un système de diarisation suit six étapes : normaliser l'audio, détecter la parole, segmenter en tours, représenter chaque tour par une empreinte vocale, regrouper les empreintes en locuteurs, puis écrire un fichier RTTM. Les deux premières étapes de traitement produisent les erreurs de **détection** (parole manquée, fausse alarme). Les deux suivantes produisent les erreurs d'**attribution** (confusion, mauvais nombre de locuteurs).

---

### Appariement optimal (*optimal mapping*)
Définition : avant le calcul du DER, association des étiquettes arbitraires du système (`SPEAKER_00`…) aux locuteurs de la référence, choisie pour minimiser l'erreur.
Rôle dans la chaîne : étape de l'évaluation, pas du système.
Effet sur les métriques : le système n'a pas à trouver les noms, seulement à grouper correctement.
Source : `docs/protocole-eval.md` §3.1.

### Bout en bout (*end-to-end*, EEND, Sortformer)
Définition : famille de systèmes dans laquelle un seul réseau prédit directement, trame par trame, l'activité de chaque locuteur.
Rôle dans la chaîne : remplace la segmentation, les empreintes et le regroupement.
Effet sur les métriques : gère naturellement le chevauchement, mais avec un nombre maximal de locuteurs fixé (4 pour Sortformer v2 **[probable]**). Au-delà, les locuteurs en trop sont forcément mal traités.
Source : `docs/recherche/corpus-diarisation-reunions-francais.md`.

### Champ lointain (*far-field*)
Définition : enregistrement par un micro éloigné des locuteurs (micro de table, de salle), par opposition au micro-casque (champ proche).
Rôle dans la chaîne : dégrade surtout la détection de parole (voix faibles, réverbération, bruit).
Effet sur les métriques : hausse de la parole manquée. Sur AMI, pyannote 2.1 passait d'environ 19 % de DER en micros-casques à environ 27 % en micro distant **[certain]**.
Source : fiche du modèle pyannote/speaker-diarization (version 2.1).

### Chevauchement (*overlapped speech*)
Définition : intervalle où au moins deux personnes parlent en même temps.
Rôle dans la chaîne : doit être repéré par la segmentation ; les systèmes classiques l'ignorent.
Effet sur les métriques : chaque locuteur compte séparément. Ne détecter qu'une personne sur deux coûte de la parole manquée. AMI contient environ 13,6 % de chevauchement **[probable]**.
Source : `docs/protocole-eval.md` §3.1–3.2.

### Collar
Définition : zone de tolérance autour de chaque frontière de la référence, exclue du calcul. Dans `pyannote.metrics`, `collar=0.5` correspond à ±0,25 s **[certain, vérifié par test]**.
Rôle dans la chaîne : paramètre de l'évaluation.
Effet sur les métriques : il efface les erreurs de frontière. Sur V5, il retire 7,5 points de DER.
Source : `docs/protocole-eval.md` §3.1.

### Confusion de locuteur (*speaker confusion*)
Définition : parole attribuée au mauvais locuteur, après appariement optimal.
Rôle dans la chaîne : naît des empreintes vocales et du regroupement.
Effet sur les métriques : un des trois composants du DER (4,3 points sur V5).
Source : `docs/protocole-eval.md` §3.1.

### Contamination
Définition : présence, dans les données d'entraînement d'un modèle pré-entraîné, du corpus sur lequel on l'évalue.
Rôle dans la chaîne : concerne l'interprétation des résultats.
Effet sur les métriques : résultats optimistes. pyannote et Sortformer ont vu AMI et VoxConverse.
Source : `docs/corpus.md` §9.

### DER (*Diarization Error Rate*)
Définition : (parole manquée + fausse alarme + confusion) / durée totale de parole de la référence.
Rôle dans la chaîne : métrique principale de l'évaluation.
Effet sur les métriques : pondéré par le temps. Un locuteur qui parle peu pèse peu.
Source : `docs/protocole-eval.md` §3.1.

### Détection d'activité vocale (VAD, *voice activity detection*)
Définition : décision, trame par trame, entre parole et non-parole.
Rôle dans la chaîne : première étape de traitement. Baseline : seuil d'énergie ; pyannote : réseau de neurones.
Effet sur les métriques : source principale de la parole manquée (parole jugée silence) et de la fausse alarme (bruit jugé parole).
Source : cours de traitement de la parole ; `docs/cadrage.md` D7.

### Diarisation (*speaker diarization*)
Définition : répondre à « qui parle, et quand ? » dans un enregistrement, sans connaître les personnes à l'avance.
Rôle dans la chaîne : la tâche entière.
Effet sur les métriques : mesurée par le DER et le JER.
Source : sujet de la piscine.

### Empreinte vocale (*speaker embedding*)
Définition : vecteur de quelques centaines de nombres résumant les caractéristiques d'une voix sur un segment ; deux segments d'une même voix donnent des vecteurs proches. Exemples : x-vector, ECAPA-TDNN.
Rôle dans la chaîne : représentation sur laquelle opère le regroupement.
Effet sur les métriques : sa qualité détermine la confusion.
Source : `docs/cadrage.md` D8.

### Estimation du nombre de locuteurs
Définition : nombre de groupes retenu par le regroupement, quand on ne l'impose pas.
Rôle dans la chaîne : sortie du regroupement, réglée par un seuil.
Effet sur les métriques : une sous-estimation fusionne des personnes, une surestimation en scinde une. Mesurée par l'erreur absolue moyenne et le taux exact (§3.4).
Source : `docs/cadrage.md` D9 (amélioration n° 1).

### Fausse alarme (*false alarm*)
Définition : parole produite par le système là où la référence n'en contient pas.
Rôle dans la chaîne : naît de la détection de parole (bruit, rires, claquements).
Effet sur les métriques : un des trois composants du DER (4,5 points sur V5).
Source : `docs/protocole-eval.md` §3.1.

### Hybride (système)
Définition : système qui combine un réseau de neurones local (segmentation sur des fenêtres de quelques secondes) et un regroupement classique à l'échelle de l'enregistrement. C'est le cas de pyannote.
Rôle dans la chaîne : gère le chevauchement localement, et le nombre de locuteurs globalement, sans maximum fixé.
Effet sur les métriques : il évite la limite de locuteurs des systèmes de bout en bout.
Source : `docs/cadrage.md` D6.

### JER (*Jaccard Error Rate*)
Définition : erreur moyenne par locuteur, chaque locuteur pesant autant quelle que soit sa durée de parole.
Rôle dans la chaîne : métrique complémentaire.
Effet sur les métriques : révèle l'oubli ou la fusion d'un locuteur minoritaire. Sur V5, un JER (30 %) supérieur au DER (25 %) suggère un locuteur mal couvert.
Source : `docs/protocole-eval.md` §3.3.

### MFCC (*Mel-Frequency Cepstral Coefficients*)
Définition : description classique du spectre de la voix, par trames de 25 ms, en une vingtaine de coefficients adaptés à la perception humaine.
Rôle dans la chaîne : caractéristiques de la baseline, à la place des empreintes neuronales.
Effet sur les métriques : moins discriminantes entre locuteurs, d'où une confusion attendue plus élevée.
Source : `docs/cadrage.md` D7.

### Oracle
Définition : diagnostic qui remplace une étape du système par la vérité terrain (détection de parole oracle, nombre de locuteurs oracle).
Rôle dans la chaîne : outil d'analyse, pas de production.
Effet sur les métriques : isole l'erreur des autres étapes. Avec une détection oracle, il ne reste que l'erreur d'attribution, hors chevauchement.
Source : `docs/cadrage.md` D9.

### Parole manquée (*missed detection*)
Définition : parole de la référence non couverte par le système, y compris le second locuteur d'un chevauchement.
Rôle dans la chaîne : naît de la détection de parole et de la segmentation.
Effet sur les métriques : un des trois composants du DER. Composant dominant sur V5 (16,4 points sur 25,2).
Source : `docs/protocole-eval.md` §3.1.

### Regroupement (*clustering*)
Définition : rassemblement des empreintes vocales proches en groupes ; chaque groupe devient un locuteur. Exemple : clustering agglomératif hiérarchique, arrêté par un seuil.
Rôle dans la chaîne : décide qui est qui, et combien de personnes parlent.
Effet sur les métriques : confusion et erreur sur le nombre de locuteurs.
Source : `docs/cadrage.md` D7.

### RTF (*Real-Time Factor*)
Définition : temps de calcul / durée de l'audio. Un RTF de 0,05 signifie qu'une réunion de 30 min se traite en 1 min 30 s.
Rôle dans la chaîne : mesure de coût.
Effet sur les métriques : mesuré en MPS et en CPU seul (protocole §3.5). V5 : 0,055 en MPS, 0,87 en CPU.
Source : `docs/protocole-eval.md` §3.5.

### RTTM (*Rich Transcription Time Marked*)
Définition : format texte standard de la diarisation, une ligne par segment : fichier, début, durée, locuteur.
Rôle dans la chaîne : format de sortie du système et des références.
Effet sur les métriques : entrée du calcul du DER.
Source : `docs/protocole-eval.md` §2.

### Segmentation
Définition : découpage du signal en tours de parole homogènes (un locuteur par morceau), avec repérage des changements de locuteur et des chevauchements. Baseline : fenêtres fixes d'1,5 s ; pyannote : réseau local sur des fenêtres d'une dizaine de secondes **[probable]**.
Rôle dans la chaîne : prépare les morceaux à représenter.
Effet sur les métriques : erreurs de frontière (atténuées par le collar) et parole manquée en chevauchement.
Source : `docs/cadrage.md` D7.

### UEM (*Un-partitioned Evaluation Map*)
Définition : intervalles de l'enregistrement sur lesquels porte l'évaluation.
Rôle dans la chaîne : paramètre de l'évaluation.
Effet sur les métriques : ce qui est hors UEM n'est pas compté (par exemple les claquements de synchronisation du corpus maison).
Source : `docs/protocole-eval.md` §2.
