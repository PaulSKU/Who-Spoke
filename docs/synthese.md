# Synthèse vivante

Version de travail du 02/11, tenue par le cockpit à chaque interprétation (audit du 01/11, R-M3). Elle prépare le document de synthèse du 13/11. Les constats chiffrés, avec leurs sources, sont dans `docs/constats.yaml` ; ce document les relie et dit ce qui reste ouvert.

**Légende de confiance.** **[certain]** : mesuré dans nos expériences. **[probable]** : déduit de plusieurs mesures. **[incertain]** : hypothèse non testée.

## 1. Question

Qu'est-ce qui fait la qualité d'une diarisation de réunions en français, enregistrées par un seul micro, et quel système proposer pour une démonstration locale sur un Mac ?

## 2. Ce que nous savons (au 01/11)

**La détection de parole, plus que la reconnaissance des voix, sépare les systèmes.** Une baseline classique (détection par énergie, empreintes, regroupement) devient correcte sur l'attribution dès qu'on lui donne de bonnes empreintes. ECAPA divise la confusion par trois (C05). Son erreur restante vient alors surtout de la parole manquée (C01). À empreinte identique, l'avance de pyannote vient pour près des trois quarts de sa segmentation neuronale, qui détecte la parole et le chevauchement (C03) **[certain]**.

**En français, pyannote reste devant, mais son défaut change de nature.** Sur SUMM-RE, sa première erreur n'est plus la parole manquée mais la fausse alarme. Une part vient de pauses courtes qu'il recouvre, une autre de faux chevauchements (C04) **[certain]**. Son avance sur la baseline y est trois fois plus faible que sur AMI, corpus qu'il a vu à l'entraînement (C10) **[probable]**.

**Le nombre de locuteurs n'est pas le levier attendu.** Donner à pyannote le nombre exact de locuteurs ne l'améliore pas (C07) **[certain]**. L'amélioration n° 1 initialement envisagée (D9) n'est donc pas justifiée par les corpus publics ; elle ne sera rouverte que si le corpus maison le demande.

**Le chevauchement réel compte plus que le faux.** Supprimer tout chevauchement de la sortie de pyannote (sortie exclusive) dégrade le DER de 4 points sur les deux corpus : la fausse alarme baisse, mais la parole manquée augmente deux fois plus (C11) **[certain]**. Borner le nombre de locuteurs entre 2 et 6 ne change presque rien, mais évite qu'une réunion soit réduite à un seul locuteur ; ces bornes sont gardées comme garde-fou (C12).

**La mesure elle-même doit être lue avec prudence.** Le DER sans collar dépend de la convention de découpage de la référence ; avec collar, presque pas (C09) **[certain]**.

## 3. Ce qui est en cours (file D23, planning v2.0)

| Question | Expériences | État |
|---|---|---|
| La sortie exclusive réduit-elle la fausse alarme sans trop perdre de chevauchement réel ? | A1 : EXP-0016, EXP-0017 (D25, V1) | Non : écartée (C11) |
| Borner le nombre de locuteurs entre 2 et 6 aide-t-il, et que fait le passage au KMeans ? | A2 : EXP-0018, EXP-0019 | Effet non significatif ; gardé comme garde-fou (C12) |
| Quel système résiste le mieux à la réverbération, au bruit et au codec de visio ? | A3 (D24) | Conditions générées, écoute de contrôle en cours |
| Nemotron 3 Diarization et DiariZen font-ils mieux que pyannote en français ? | A4, A5 | Installation en préparation |
| Une détection fine en post-traitement réduit-elle la fausse alarme de pyannote ? | A6 (D25, V2 et V3) | En attente |
| Que donnent les systèmes sur de vraies réunions en français, en salle et en visio ? | A9, corpus maison | Enregistrements en cours |

## 4. Limites connues

- SUMM-RE est enregistré en micros-casques : il ne représente pas le champ lointain de la cible (D24 compense en partie).
- AMI est contaminé pour pyannote et pour Nemotron 3 Diarization : il ne sert pas à les départager.
- Le corpus maison n'aura que quelques enregistrements : il sert de test qualitatif, sans statistique.
- Les temps de calcul des expériences menées pendant le travail en parallèle ne sont pas comparables ; les temps de référence viendront de la campagne du 12/11 (D21).
