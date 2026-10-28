# D18 — Définition de l'« arbre propre » et précisions du protocole

Statut : actée
Date : 2026-10-28 (proposée et actée le même jour)

## Contexte

EXP-0001 porte `arbre_propre: false`, alors que son exécution principale (MPS) a tourné sur un arbre propre, au commit d9f177a, et que le code n'a pas changé de toute l'expérience. La seule cause est que deux documents du cockpit (`docs/glossaire.md`, `docs/decisions/D17-interface.md`) ont été écrits dans le dossier de travail pendant la mesure en CPU ; `execution_cpu.json` les liste dans `fichiers_non_commites`. La règle actuelle (`methode.md` §6) ne distingue pas ce qui peut changer un résultat de ce qui ne le peut pas. Or le cockpit écrit régulièrement de la documentation pendant que Claude Code exécute. La session a aussi relevé plusieurs choix d'implémentation non couverts par une fiche.

## Options

| Option | Avantages | Inconvénients |
|---|---|---|
| A. Garder la règle et réexécuter EXP-0001 sur un arbre entièrement propre | Aucune règle modifiée | Environ 1 h de calcul pour un résultat identique ; le problème se reproduira à chaque expérience |
| B. Définir l'arbre propre sur les seuls chemins qui peuvent changer un résultat, et requalifier EXP-0001 à partir de la liste consignée | Règle juste et vérifiable ; aucun recalcul | Une modification de métadonnées d'une expérience exécutée, à tracer |

## Décision

Option B.

1. **Chemins contrôlés.** `arbre_propre` vaut `true` si aucun fichier non commité ne se trouve sous `src/`, `scripts/`, `configs/`, `tests/`, `data/splits/`, `data/manifests/`, ni ne s'appelle `pyproject.toml` ou `uv.lock`. Les fichiers non commités ailleurs (`docs/`, `results/`, `experiments/*/notes.md`, `README.md`) sont listés dans `fichiers_non_commites`, mais ne rendent pas l'arbre sale.
2. **Requalification d'EXP-0001.** Le script d'évaluation recalcule `arbre_propre` à partir des listes consignées dans `execution_mps.json` (vide) et `execution_cpu.json` (deux fichiers de `docs/`). Il ajoute aux fichiers `results_*.json` un bloc `requalification` : date, règle appliquée (D18), ancienne valeur, nouvelle valeur. Les métriques ne sont pas touchées. `methode.md` §4.2 admet désormais cette troisième exception à l'immuabilité, limitée aux métadonnées et toujours tracée.
3. **Précisions du protocole**, entérinant les choix faits dans EXP-0001 :

| Point | Règle |
|---|---|
| Préchauffage | Sur les 60 premières secondes du premier fichier ; tous les fichiers sont ensuite comptés (remplace « un premier fichier sert de préchauffage et n'est pas compté », protocole §3.5) |
| Zone « sans chevauchement » | Tout ce qui n'est pas en chevauchement dans la référence, silences compris ; les fausses alarmes y sont donc comptées (protocole §3.2) |
| Nombre de locuteurs | Compté sur les locuteurs présents dans l'UEM, pour la référence comme pour l'hypothèse (protocole §3.4) |
| Fichiers d'exécution | `execution_<device>.json` (temps par fichier, commit, état de l'arbre, versions) fait partie du dossier d'expérience (`methode.md` §4.2) |
| Empreintes des manifestes | Le SHA-256 porte sur le fichier brut téléchargé (`methode.md` §7) |
| Options des scripts | Toute option est documentée dans `--help` ; pas d'option cachée |
| Test de l'enveloppe pyannote | Test d'intégration sur un extrait court, ignoré automatiquement en l'absence de `HF_TOKEN` |

## Justification

Ce que garantit l'arbre propre, c'est que le code, la configuration et les données qui ont produit un résultat sont retrouvables depuis un commit. La documentation n'en fait pas partie. La liste des fichiers non commités, consignée par l'exécution elle-même, rend la requalification vérifiable par un tiers.

## Conséquences

Les modifications portent sur `methode.md` §4.2 et §6, ainsi que sur `protocole-eval.md` §3.2, §3.4 et §3.5. Elles touchent aussi `src/whospoke/experiment.py` (calcul de l'état de l'arbre), `scripts/evaluate.py` (recalcul, bloc `requalification`, option `--leaderboard` documentée) et un test d'intégration conditionnel. Le cockpit peut continuer à écrire dans `docs/` pendant une exécution.

## Amendement du 28/10/2026 (après EXP-0005)

**Exécutions d'une même expérience sur des commits différents.** C'est le cas d'EXP-0005 : exécution MPS au commit 3abe688, mesure CPU au commit e4701ba, des résultats d'autres expériences ayant été commités entre les deux. La requalification est admise si trois conditions sont réunies, et elle est alors consignée :

1. chaque exécution est propre au sens de D18 ;
2. `git diff` entre les commits des exécutions, restreint aux chemins contrôlés de D18, est vide ;
3. l'empreinte `config_sha256` est la même pour toutes les exécutions.

Le bloc `requalification` consigne alors, en plus des champs prévus, la liste des commits et le résultat de la vérification du `git diff` (`"diff_chemins_controles": "vide"`). Si l'une des conditions n'est pas remplie, l'expérience est refaite sous un nouveau numéro.

Vérification faite par le cockpit le 28/10/2026 pour EXP-0005 : les deux exécutions sont propres, le `git diff --stat 3abe688 e4701ba` sur les chemins contrôlés est vide, et `config_sha256` est identique (0e3666c06f5d…).

## Liens

EXP-0001 (`execution_mps.json`, `execution_cpu.json`) ; `docs/journal.md`, 27/10/2026.
