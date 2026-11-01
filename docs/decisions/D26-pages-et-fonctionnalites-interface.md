# D26 — Pages et fonctionnalités supplémentaires de l'interface

Statut : actée
Date : 2026-11-01

## Contexte

L'onglet Analyse fonctionne (D17, amendement 1). La candidate souhaite ajouter à l'application la page Pipeline prévue par D17, et une page qui récapitule l'avancement du projet : expériences, ce qui a été testé, retenu ou écarté. Le cockpit a proposé trois autres fonctionnalités, que la candidate a retenues. Elle a aussi validé deux exclusions.

## Décision

### 1. Contenu

| Élément | Contenu | Source des données |
|---|---|---|
| Onglet Pipeline | Conforme à D17 : schéma des étapes, fiche par étape, tableau des réglages (valeur, origine, effet, composante du DER), sélecteur de moteur, lecture seule | `configuration_effective` de `execution_<device>.json` de l'expérience source du moteur (D17, amendement 1) et `src/whospoke/pipelines/catalogue.yaml` ; aucun modèle chargé. Référence visuelle : `docs/maquettes/pipeline-maquette-2026-10-27.html` (maquette, non exécutable hors ligne) |
| Onglet Avancement | Expériences et analyses dans l'ordre (question, corpus, DER dans les deux conditions de collar, verdict, décisions liées, lien vers `notes.md`) ; décomposition de l'erreur par les oracles ; décisions avec leur statut ; file d'attente de D23 | En-têtes des `notes.md`, `results_*.json`, en-têtes des fiches `docs/decisions/`, tableau « File d'attente » de `docs/planning.md` |
| Glossaire intégré | Onglet Glossaire ; les termes des autres onglets renvoient à leur définition | `docs/glossaire.md` |
| Carte des erreurs (onglet Analyse) | Quand une référence est déposée : piste supplémentaire sous la timeline, qui montre parole manquée, fausse alarme et confusion (après appariement optimal des locuteurs), écoutables au clic ; durée totale de chaque type | Hypothèse et référence ; calcul cohérent avec le DER affiché |
| Comparaison de deux moteurs (onglet Analyse) | Deux moteurs sur le même fichier, l'un après l'autre ; timelines superposées, avec la référence et les deux cartes des erreurs si une référence est déposée | Moteurs existants ; temps restant cumulé |

**Couleurs.** La palette des locuteurs (8 teintes, puis un gris) ne distingue tous les locuteurs par la seule couleur que jusqu'à 3 locuteurs en deutéranopie. Au-delà, l'identification repose sur la piste, le nom et le survol, ce qui est accepté : la couleur ne porte jamais seule une information. La forme d'onde devient donc neutre, sans teinte par locuteur. Seul le segment sélectionné y est mis en évidence, et la couleur reste disponible pour la carte des erreurs (I4).

Toutes les pages sont **générées** à partir du dépôt, jamais rédigées à la main, et fonctionnent hors ligne.

### 2. En-tête des `notes.md`

Chaque `notes.md` d'expérience ou d'analyse commence par un en-tête YAML, rempli par le cockpit à l'interprétation :

```yaml
---
id: EXP-0012
question: "Gain réaliste des empreintes ECAPA en français"
verdict: en_cours   # reference | retenu | ecarte | informatif | en_cours
decisions: [D22]
---
```

Le cockpit ajoute cet en-tête aux expériences déjà faites lors de l'interprétation du lot WeSpeaker. `methode.md` est mis à jour en conséquence.

### 3. Exclusions

Ne sont pas retenus : l'enregistrement en direct au micro, hors sujet et inadapté à un moteur par lots ; toute modification de réglage depuis l'interface (D17).

### 4. Chantiers

Ils sont réalisés dans l'ordre, dans la branche `interface`, sans fusion ni modèle chargé avant la vérification V.

| Chantier | Contenu | Dépend de |
|---|---|---|
| I0 (en cours) | Préchargement des modèles, dossier fixe d'ECAPA, palette (D17, amendement 1) | — |
| I1 | Onglet Pipeline | I0 |
| I2 | Onglet Avancement | I1 ; en-têtes des `notes.md` |
| I3 | Glossaire intégré et liens depuis les autres onglets | I1, I2 |
| I4 | Carte des erreurs | I0 |
| I5 | Comparaison de deux moteurs | I4 |
| V | Fusion dans `main`, suite de tests complète, préchargement réel, essai avec les vrais moteurs sous relevé réseau | Fin du lot EXP-0013 à 0015 ; s'intercale entre les rangs 0 et 1 de D23 |

## Justification

La page Avancement rend visible la conduite du projet, critère majeur de l'évaluation. La carte des erreurs sert l'objectif d'apprentissage : montrer ce qui dégrade la diarisation sur un fichier précis. Générer les pages depuis le dépôt garantit qu'elles ne divergent jamais des résultats réels.

## Amendement du 01/11/2026 — arbitrages après les chantiers I1 à I5

Statut : actée

| Point | Décision |
|---|---|
| Textes et valeurs de l'étape Normalisation, écrits dans `app/pipeline.py` | Déplacés dans `catalogue.yaml` au chantier V, avec les valeurs lues dans le code de normalisation : la page Pipeline ne doit rien contenir d'écrit à la main (D17) |
| Formes abrégées du glossaire | Ligne facultative « Formes courtes : … » sous le titre d'une entrée (`docs/glossaire.md`), reconnue par l'onglet Glossaire |
| Statut des amendements | Ligne « Statut : » ajoutée sous chaque titre d'amendement ; règle reprise dans les fiches à venir |
| En-têtes YAML des `notes.md` | Ajoutés aux 16 expériences et analyses ; verdict `en_cours` pour EXP-0010 à 0015 jusqu'à leur interprétation |
| Choix faits par la session | Validés : second moteur et référence en gris neutre ; référence affichée aussi en analyse simple ; statistiques et renommage limités au premier moteur en comparaison ; règles de RTF de l'amendement 1 de D17 |
| Carte des erreurs sans collar seulement | Acceptée ; l'écran l'indique explicitement à côté de la carte |
| Correspondance moteurs et expériences sources | Reste dans `app/moteurs.py` jusqu'au gel du 10/11, puis passe dans `configs/demo.yaml` |
| Limites connues (retour depuis le glossaire, identifiants de SUMM-RE, couleurs après changement de thème) | Acceptées pour la démonstration |

## Liens

D17 et son amendement 1, D21, D23 ; `docs/glossaire.md`.
