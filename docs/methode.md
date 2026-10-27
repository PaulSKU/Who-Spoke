# Méthode de travail

Version 1.0 du 27 octobre 2026. Ce document fixe les conventions du projet : où se range chaque chose, sous quel format, et qui la produit. Il s'applique à toutes les sessions, qu'elles se déroulent dans la conversation de conception (« cockpit ») ou dans Claude Code. Toute dérogation passe par une fiche de décision.

---

## 1. Principes

Le dépôt est la source de vérité. Une décision, un résultat ou une définition qui n'existe que dans une conversation est réputé inexistant.

Toute expérience est reproductible à partir d'un commit, d'un fichier de configuration et de listes de fichiers versionnées.

Une ablation ne modifie qu'une variable à la fois, par rapport à une expérience de référence nommée, sur les mêmes fichiers.

Le jeu de test d'un corpus n'est jamais utilisé pour régler quoi que ce soit. Tout réglage se fait sur dev.

Aucun audio, aucun jeton d'accès et aucune donnée nominative n'entre dans git.

---

## 2. Arborescence

```
Who-Spoke/
├── CLAUDE.md                 consignes permanentes pour Claude Code
├── README.md                 installation, reproduction, démonstration
├── pyproject.toml, uv.lock   dépendances figées (uv)
├── .env.example              modèle de variables d'environnement (HF_TOKEN) ; .env jamais versionné
├── docs/
│   ├── cadrage.md            décisions initiales D1 à D15, contraintes de la cible
│   ├── methode.md            ce document
│   ├── protocole-eval.md     protocole d'évaluation figé
│   ├── corpus.md             fiche des corpus (livrable exigé)
│   ├── glossaire.md          concepts et vocabulaire
│   ├── journal.md            journal de bord daté
│   └── decisions/            une décision = un fichier (D16-slug.md, D17-…)
├── configs/                  configurations YAML réutilisables (pipelines, jeux de données)
├── data/                     non versionné, sauf README.md, manifests/ et splits/
│   ├── README.md             comment reconstruire data/ à partir des scripts
│   ├── manifests/            un CSV par corpus : identifiant, source, licence, durée, SHA-256
│   ├── splits/<corpus>/      listes de fichiers par partition (dev.txt, test.txt) et UEM éventuels
│   ├── raw/                  téléchargements bruts (ignoré par git)
│   └── processed/            audio normalisé 16 kHz mono et RTTM de référence (ignoré par git)
├── src/whospoke/             bibliothèque : audio, vad, features, embeddings, clustering, pipelines, evaluation
├── scripts/                  points d'entrée en ligne de commande (préparation, exécution, évaluation)
├── experiments/
│   └── EXP-NNNN_slug/        une expérience, immuable une fois exécutée
├── results/
│   └── leaderboard.csv       une ligne par évaluation, alimentée uniquement par le script d'évaluation
├── app/                      démonstration Gradio
└── tests/                    tests unitaires, dont ceux du protocole d'évaluation
```

---

## 3. Identifiants

| Objet | Format | Règle |
|---|---|---|
| Décision | `D<n>` | Espace de numérotation unique : D1 à D15 dans `cadrage.md`, puis D16, D17… dans `docs/decisions/` |
| Expérience | `EXP-NNNN` | Séquentiel, sur quatre chiffres, jamais réutilisé, même pour une expérience abandonnée |
| Fichier audio | `<corpus>__<identifiant d'origine>` | Exemples : `ami__ES2004a`, `voxconverse__abjxc`, `summre__<id>`, `maison__M01` |
| Locuteur de référence | identifiant du corpus, ou `M01_S1`, `M01_S2`… pour le corpus maison | Jamais de nom réel |

---

## 4. Formats

### 4.1 Fiche de décision — `docs/decisions/D<n>-slug.md`

```markdown
# D<n> — <titre>

Statut : proposée | actée | remplacée par D<m>
Date : AAAA-MM-JJ

## Contexte
<ce qui oblige à décider, en quelques phrases>

## Options
| Option | Avantages | Inconvénients |
|---|---|---|

## Décision
<l'option retenue, formulée sans ambiguïté>

## Justification
<pourquoi ; expériences ou sources à l'appui>

## Conséquences
<ce que cela implique pour le code, les données ou le calendrier>

## Liens
<EXP-…, D…, sources>
```

### 4.2 Expérience — `experiments/EXP-NNNN_slug/`

| Fichier | Contenu | Produit par |
|---|---|---|
| `config.yaml` | Configuration complète et autonome : corpus, partition, pipeline, paramètres, graine aléatoire, expérience de référence, variable modifiée | Claude Code, avant exécution |
| `results.json` | Métriques agrégées au schéma du §4.3 | Script d'évaluation |
| `per_file.csv` | Métriques par fichier | Script d'évaluation |
| `rttm/` | Hypothèses du système, un RTTM par fichier | Script d'exécution |
| `run.log` | Journal d'exécution | Script d'exécution |
| `notes.md` | Interprétation des résultats | Rédigé après analyse dans le cockpit |

Une expérience exécutée n'est plus modifiée. Les seules exceptions sont `notes.md`, que l'on complète, et un bloc `invalidee` ajouté à `results.json` si un défaut est découvert. Une correction donne lieu à une nouvelle expérience.

### 4.3 Schéma de `results.json`

Les taux sont exprimés en pourcentage, avec deux décimales.

```json
{
  "exp_id": "EXP-0001",
  "slug": "baseline-mfcc",
  "date": "2026-10-28T14:00:00+01:00",
  "git_commit": "abc1234",
  "arbre_propre": true,
  "reference": null,
  "variable_modifiee": null,
  "donnees": {"corpus": "summre", "partition": "dev", "n_fichiers": 10, "duree_audio_s": 3600.0},
  "systeme": {"pipeline": "baseline", "mode_n_locuteurs": "estime", "vad": "energie", "device": "mps"},
  "materiel": {"machine": "MacBook Pro M2 Pro", "ram_go": null},
  "metriques": {
    "collar_0": {"der": 0.0, "manquee": 0.0, "fausse_alarme": 0.0, "confusion": 0.0, "jer": 0.0},
    "collar_0_25": {"der": 0.0, "manquee": 0.0, "fausse_alarme": 0.0, "confusion": 0.0, "jer": 0.0},
    "der_zones_sans_chevauchement": 0.0,
    "der_zones_chevauchement": 0.0,
    "n_locuteurs": {"erreur_absolue_moyenne": 0.0, "taux_exact": 0.0}
  },
  "temps": {"chargement_modeles_s": 0.0, "calcul_s": 0.0, "rtf": 0.0},
  "invalidee": null
}
```

Les définitions exactes de chaque champ figurent dans `docs/protocole-eval.md`.

### 4.4 `results/leaderboard.csv`

Colonnes, dans cet ordre : `exp_id, date, slug, reference, variable_modifiee, corpus, partition, pipeline, mode_n_locuteurs, der_c0, manquee_c0, fausse_alarme_c0, confusion_c0, der_c025, jer_c0, mae_n_locuteurs, rtf, git_commit`. Une ligne correspond à une évaluation (expérience × corpus × partition). Le fichier n'est jamais édité à la main.

### 4.5 Entrée de journal — `docs/journal.md`

Les entrées sont ajoutées en fin de fichier, au format suivant.

```markdown
## AAAA-MM-JJ — <titre de la session> (<cockpit | Claude Code | manuel>)

Objectif : …
Réalisé : …
Résultats : EXP-…
Décisions : D…
Problèmes : …
Suite : …
```

### 4.6 Entrée de glossaire — `docs/glossaire.md`

Une entrée par terme, triée alphabétiquement.

```markdown
### <Terme français> (*<terme anglais>*)
Définition : …
Rôle dans la chaîne : …
Effet sur les métriques : …
Source : …
```

---

## 5. Boucle de travail

| Étape | Lieu | Produit |
|---|---|---|
| 1. Discussion d'une question de conception | Cockpit | — |
| 2. Formalisation | Cockpit, écrit dans le dossier local | Fiche `D<n>`, mise à jour de `docs/` |
| 3. Prompt d'implémentation, court, renvoyant aux fiches | Cockpit | Texte à coller dans Claude Code |
| 4. Implémentation, tests, exécution | Claude Code | Code, `experiments/EXP-…`, ligne du leaderboard, entrée de journal factuelle |
| 5. Commit et push | Claude Code | Historique git |
| 6. Lecture et interprétation | Cockpit, depuis le dépôt | `notes.md` de l'expérience, entrée de journal, éventuelle nouvelle décision |

Les documents écrits par le cockpit dans le dossier local sont commités par Claude Code au début de sa session suivante, avec un commit `docs:` distinct.

---

## 6. Conventions git

| Règle | Détail |
|---|---|
| Branche | `main` uniquement ; une branche temporaire seulement pour un essai risqué |
| Messages | En français, préfixés : `feat:`, `fix:`, `docs:`, `exp:`, `data:`, `test:`, `chore:` |
| Expérience | Un commit `exp: EXP-NNNN <slug>` contenant le dossier de l'expérience et la ligne du leaderboard |
| Arbre propre | Une expérience s'exécute sur un code commité ; le script d'évaluation enregistre `arbre_propre: false` sinon, et une telle expérience ne peut pas figurer dans le rendu |
| Exclusions | `.env`, `data/raw/`, `data/processed/`, tout fichier audio (`*.wav`, `*.mp3`, `*.m4a`, `*.flac`), caches de modèles |

---

## 7. Données

Chaque corpus est obtenu par un script `scripts/data/get_<corpus>.py` qui télécharge, vérifie les sommes de contrôle, normalise l'audio en 16 kHz mono et produit le RTTM de référence. Le manifeste `data/manifests/<corpus>.csv` est versionné. La fiche `docs/corpus.md` est mise à jour avant tout premier téléchargement d'un corpus : source, accès, licence, volume, composition, limites et jeux vus par chaque modèle pré-entraîné. Les consentements du corpus maison sont conservés hors du dépôt. `corpus.md` mentionne seulement leur existence et leur date.
