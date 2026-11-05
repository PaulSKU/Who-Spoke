# Synthèse vivante

Version de travail du 03/11, tenue par le cockpit à chaque interprétation (audit du 01/11, R-M3). Elle prépare le document de synthèse du 13/11. Les constats chiffrés, avec leurs sources, sont dans `docs/constats.yaml` ; ce document les relie et dit ce qui reste ouvert.

**Légende de confiance.** **[certain]** : mesuré dans nos expériences. **[probable]** : déduit de plusieurs mesures. **[incertain]** : hypothèse non testée.

## 1. Question

Qu'est-ce qui fait la qualité d'une diarisation de réunions en français, enregistrées par un seul micro, et quel système proposer pour une démonstration locale sur un Mac ?

## 2. Ce que nous savons (au 01/11)

**La détection de parole, plus que la reconnaissance des voix, sépare les systèmes.** Une baseline classique (détection par énergie, empreintes, regroupement) devient correcte sur l'attribution dès qu'on lui donne de bonnes empreintes. ECAPA divise la confusion par trois (C05). Son erreur restante vient alors surtout de la parole manquée (C01). À empreinte identique, l'avance de pyannote vient pour près des trois quarts de sa segmentation neuronale, qui détecte la parole et le chevauchement (C03) **[certain]**.

**En français, pyannote reste devant, mais son défaut change de nature.** Sur SUMM-RE, sa première erreur n'est plus la parole manquée mais la fausse alarme. Une part vient de pauses courtes qu'il recouvre, une autre de faux chevauchements (C04) **[certain]**. Son avance sur la baseline y est trois fois plus faible que sur AMI, corpus qu'il a vu à l'entraînement (C10) **[probable]**.

**Le nombre de locuteurs n'est pas le levier attendu.** Donner à pyannote le nombre exact de locuteurs ne l'améliore pas (C07) **[certain]**. L'amélioration n° 1 initialement envisagée (D9) n'est donc pas justifiée par les corpus publics ; elle ne sera rouverte que si le corpus maison le demande.

**Le chevauchement réel compte plus que le faux.** Supprimer tout chevauchement de la sortie de pyannote (sortie exclusive) dégrade le DER de 4 points sur les deux corpus : la fausse alarme baisse, mais la parole manquée augmente deux fois plus (C11) **[certain]**. Borner le nombre de locuteurs entre 2 et 6 ne change presque rien, mais évite qu'une réunion soit réduite à un seul locuteur ; ces bornes sont gardées comme garde-fou (C12).

**La réverbération est la faiblesse de pyannote, le bruit celle de la baseline.** En salle très réverbérante simulée, pyannote manque une grande partie de la parole et perd son avance (C13) ; la baseline souffre surtout du bruit (C14) ; un codec de visio à bas débit fait confondre les voix aux deux (C15) **[certain]**. La salle avec un seul micro de la cible est donc la condition à surveiller pour la démonstration.

**Un réglage fait en champ proche est dangereux en champ lointain.** Le post-traitement par Silero VAD gagne 2,6 points en français (micros-casques) mais en perd 22 sur AMI (micro distant) ; la règle de D25 l'a écarté (C16) **[certain]**. Aucune variante de l'amélioration n° 2 n'est retenue.

**Le chevauchement est le premier facteur d'échec identifiable** (C17) **[probable]**, et une grande part du DER sans collar n'est qu'un décalage de frontière.

**Un modèle de bout en bout récent change la donne en français.** Nemotron 3 Diarization fait presque deux fois mieux que pyannote sur SUMM-RE et ne se dégrade presque pas en salle réverbérante simulée (C18) **[certain]**. Il fait pourtant moins bien sur AMI, en manquant de la parole (C19). Le choix du moteur de démonstration suit une règle fixée avant le corpus maison (D29).

**La mesure elle-même doit être lue avec prudence.** Le DER sans collar dépend de la convention de découpage de la référence ; avec collar, presque pas (C09) **[certain]**.

**Sur la première réunion réelle, l'écart se confirme, mais pas encore en champ lointain.** Sur M01 (voiture, 3 locuteurs), Nemotron 3 fait 14,7 % de DER sans collar contre 34,1 % pour pyannote, qui ne trouve que deux locuteurs et confond aussi les deux autres (C22) **[certain]**. Nemotron 3 y manque un peu plus de parole que pyannote, trace atténuée de son défaut sur AMI. M01 étant enregistré à courte distance, la question du champ lointain reste ouverte jusqu'à un enregistrement en salle (D29, amendement du 05/11) **[probable]**.

## 3. Ce qui est en cours (file D23, planning v2.0)

| Question | Expériences | État |
|---|---|---|
| La sortie exclusive réduit-elle la fausse alarme sans trop perdre de chevauchement réel ? | A1 : EXP-0016, EXP-0017 (D25, V1) | Non : écartée (C11) |
| Borner le nombre de locuteurs entre 2 et 6 aide-t-il, et que fait le passage au KMeans ? | A2 : EXP-0018, EXP-0019 | Effet non significatif ; gardé comme garde-fou (C12) |
| Quel système résiste le mieux à la réverbération, au bruit et au codec de visio ? | A3 (D24) : EXP-0020, EXP-0021, A-0002 | Fait : réverbération forte = faiblesse de pyannote (C13) |
| Nemotron 3 Diarization et DiariZen font-ils mieux que pyannote en français ? | A4 : EXP-0026 à 0028 ; A5 | Nemotron 3 : oui en français et sous dégradation, non sur AMI (diagnostic en cours, D29) ; DiariZen écarté (trop lent en CPU, plante en MPS) |
| Une détection fine en post-traitement réduit-elle la fausse alarme de pyannote ? | A6 (D25, V2 et V3) : EXP-0022 à 0025 | Non : gain en français, forte perte sur AMI, écartée (C16) |
| Que donnent les systèmes sur de vraies réunions en français, en salle et en visio ? | A9, corpus maison | M01 évaluée (EXP-0036, EXP-0037, A-0005) ; enregistrement en salle à faire |

## 4. Limites connues

- SUMM-RE est enregistré en micros-casques : il ne représente pas le champ lointain de la cible (D24 compense en partie).
- AMI est contaminé pour pyannote et pour Nemotron 3 Diarization : il ne sert pas à les départager.
- Le corpus maison n'aura que quelques enregistrements : il sert de test qualitatif, sans statistique.
- Les temps de calcul des expériences menées pendant le travail en parallèle ne sont pas comparables ; les temps de référence viendront de la campagne du 12/11 (D21).
