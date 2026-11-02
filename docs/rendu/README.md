# Rendu : tableaux et figures

Fichiers générés par `scripts/rendu.py` : ne pas les modifier à la main. Pour les régénérer :

```bash
uv run python scripts/rendu.py
```

`--verifier` signale (code 1) un dossier qui n'est plus à jour.

| Fichier | Contenu |
|---|---|
| [systemes.md](systemes.md) | Systèmes par corpus : DER dans les deux conditions de collar, composantes, nombre de locuteurs exact, écart à la référence avec IC du bootstrap |
| [oracles.md](oracles.md) | Décomposition de l'erreur par les oracles |
| [robustesse.md](robustesse.md) | Robustesse (D24) : moteur × condition, écart au propre, sous-groupes Zoom et autres |
| [temps.md](temps.md) | Temps de calcul de la campagne du 12/11 (D21) |
| [figures/](figures/) | Graphique des systèmes de référence de l'onglet Avancement, en mise en page large et étroite |

![DER test sans collar des systèmes de référence](figures/systemes_reference.svg)

**Sources.** Expériences (commit d'exécution) : EXP-0001 (`d9f177a`), EXP-0002 (`540bb5e`), EXP-0007 (`568efbb`), EXP-0009 (`568efbb`), EXP-0010 (`fba633a`), EXP-0012 (`3856355`), EXP-0013 (`2a08ff7`), EXP-0015 (`5bcb295`), EXP-0018 (`2fcf766`).
Fichiers : `results/leaderboard.csv` (contrôle), `results_<corpus>_<partition>.json` et `per_file_<corpus>_<partition>.csv` de chaque expérience.
Barres : `app.avancement.reference_systems`, comme l'onglet Avancement.

## Contrôles

- `results/leaderboard.csv` et les results_*.json concordent (38 lignes, à 0,005 point près).
- En-têtes de notes.md manquants ou illisibles (verdict non affiché) : EXP-0020, EXP-0021.
