# Corpus maison — réunions françaises enregistrées et annotées

Version 1.0 du 27 octobre 2026. Ce dossier rassemble tout ce qui concerne le corpus maison (décision D3) : les documents à faire signer, le protocole d'enregistrement et les conventions d'annotation. Le corpus maison est le **seul test français, réel et inédit** pour les modèles pré-entraînés. Sa qualité conditionne la crédibilité de l'évaluation finale.

## Contenu

| Fichier | Rôle |
|---|---|
| `formulaire-consentement.md` | Notice d'information et formulaire de consentement, à imprimer ou envoyer à chaque participant avant l'enregistrement |
| `protocole-enregistrement.md` | Les trois sessions (conditions, matériel, déroulé, fiche de session) |
| `conventions-annotation.md` | Ce qui compte comme parole, règles de découpage, outil, chaîne de production du RTTM, contrôle qualité |

## Règles de confidentialité

| Élément | Emplacement | Dans git ? |
|---|---|---|
| Modèles de documents (ce dossier) | `docs/corpus-maison/` | Oui |
| Formulaires signés, table de correspondance noms ↔ identifiants | Dossier **hors du dépôt**, par exemple `~/Dev/Who-Spoke-confidentiel/` | **Jamais** |
| Audio brut et pistes individuelles | `data/raw/maison/` (ignoré par git) | Non |
| Audio évalué (micro de table, normalisé) | `data/processed/maison/` (ignoré par git) | Non |
| RTTM et UEM de référence | `data/processed/maison/` ; versionnés seulement si tous les participants ont coché l'option correspondante | Selon consentement |
| Fiches de session | `data/raw/maison/<session>/fiche.md` ; aucun nom réel | Non |

Les enregistrements maison sont traités **uniquement en local**. Ils ne sont jamais envoyés sur un GPU distant (Colab, Kaggle) ni sur un service cloud, car la notice d'information exclut tout transfert hors de la machine de la candidate et du laboratoire. C'est sans conséquence pour le projet, puisque ce corpus ne sert qu'à l'évaluation.

## Déroulé et état d'avancement

| Étape | Statut |
|---|---|
| Compléter les champs `[…]` du formulaire (responsable, contact, durée de conservation) | à faire |
| Recruter les participants (voir le protocole : 4–6, 3–4 et 2–3 personnes) | à faire |
| Faire signer les consentements avant chaque session | à faire |
| M01 — salle réverbérante, un appareil sur la table | à faire |
| M02 — visio | à faire |
| M03 — bruit de fond | à faire |
| Annotation et contrôle qualité de M01, M02, M03 | à faire |
| Mise à jour de `docs/corpus.md` (section corpus maison) | à faire |
