# D21 — Analyses a posteriori et contrôle de l'alimentation

Statut : actée
Date : 2026-10-31

## Contexte

Deux besoins sont apparus avec EXP-0007 à EXP-0009.

Le premier est de questionner l'évaluation sans relancer de système. Sur SUMM-RE, pyannote fait 11 à 14 points de fausse alarme sans collar, mais les trois quarts disparaissent avec un collar de 0,25 s. L'hypothèse est que notre référence mot à mot (fusion des pauses de 200 ms ou moins) est plus « serrée » que les tours produits par pyannote **[probable]**. La vérifier consiste à réévaluer des RTTM déjà produits contre des variantes de la référence. Ce n'est pas une expérience au sens de `methode.md` §4.2, puisqu'aucun système ne tourne.

Le second est qu'EXP-0008 a tourné en partie sur batterie sans que rien ne l'enregistre, alors que le protocole §3.5 exige une mesure sur secteur.

## Décision

### 1. Analyses a posteriori

| Point | Règle |
|---|---|
| Emplacement | `analyses/A-NNNN_slug/`, numérotation séquentielle propre aux analyses |
| Définition | Calcul sur des sorties existantes (RTTM, `per_file_*.csv`) et des références, sans exécution d'un système de diarisation |
| Contenu | `config.yaml` (expériences sources, références ou variantes utilisées, calculs) ; fichiers de résultats CSV ; `notes.md` (observations factuelles, puis interprétation du cockpit) |
| Immuabilité, arbre propre | Mêmes règles que les expériences (D18) ; le script consigne commit, arbre et empreinte de la configuration |
| Données intermédiaires | Variantes de référence dans `data/processed/<corpus>/rttm_variantes/<variante>/`, non versionnées, regénérables par script |
| Statut des conclusions | Une analyse ne change ni le protocole ni les références : tout changement de convention passe par une fiche de décision |

### 2. A-0001 — sensibilité de la référence de SUMM-RE

**Question.** Quelle part de l'erreur de pyannote et de la baseline sur SUMM-RE dépend de la convention de construction de la référence ?

**Sources.** RTTM d'EXP-0007 (pyannote) et d'EXP-0009 (baseline, θ = 1,00), SUMM-RE dev et test.

**Variantes de la référence** (8), construites à partir des mots par la même chaîne que la référence officielle (D20 §3) :

| Paramètre | Valeurs |
|---|---|
| Fusion des pauses d'un même locuteur | 200 ms (officielle), 300 ms, 500 ms, 1 000 ms |
| Jetons non lexicaux | retirés (officiel), conservés |

L'**UEM officiel est gardé pour toutes les variantes**, afin que seul le découpage change.

**Calculs.**

1. Pour chaque variante, système et partition : toutes les métriques du protocole (§3.1 à §3.4), dans les deux conditions de collar.
2. Pour la référence officielle seulement, répartition des secondes de fausse alarme de chaque système en trois catégories :
   - (a) dans une pause entre deux tours du même locuteur, de 1 s au plus ;
   - (b) dans une pause entre tours de locuteurs différents, de 1 s au plus ;
   - (c) ailleurs (silences plus longs, début et fin).
   La même répartition est faite pour la parole manquée, selon que le tour de référence manqué dure moins de 0,5 s ou plus.

**Résultats.** `resultats.csv` (une ligne par variante × système × partition), `repartition_erreurs.csv`, `notes.md`.

**Règle d'interprétation.** La convention de référence ne sera jamais choisie parce qu'elle améliore le score d'un système : cela reviendrait à ajuster la mesure au système. Si l'analyse montre une forte sensibilité, la convention pourra être revue uniquement sur un argument d'annotation (ce qu'un annotateur humain marque comme un tour, et la cohérence avec le corpus maison). Dans tous les cas, les deux conditions de collar continuent d'être rapportées.

### 3. Contrôle de l'alimentation

`scripts/run_experiment.py` relève l'état d'alimentation (`pmset -g batt` sur macOS) au début de l'exécution, puis toutes les 60 s, puis à la fin. Les relevés sont consignés dans `execution_<device>.json`. Le bloc `temps` des résultats reçoit un champ `conforme` (`true` si tous les relevés sont sur secteur, `false` sinon, `null` si l'état ne peut pas être lu, par exemple hors macOS). Un temps non conforme n'est jamais reporté dans le README ni dans une comparaison de temps de calcul.

EXP-0008 n'est pas requalifiée ; son temps de calcul n'est pas exploité (`notes.md`).

## Conséquences

Fichiers concernés : `methode.md` (§2 et nouveau §4.7, faits par le cockpit), `protocole-eval.md` §3.5 (champ `conforme`), le script d'analyse `scripts/analyses/a0001_sensibilite_reference.py`, une option de `get_summre.py` pour générer une variante de référence, et `run_experiment.py` avec `evaluate.py` pour l'alimentation.

## Liens

D18, D20 ; EXP-0007, EXP-0008, EXP-0009 ; `docs/protocole-eval.md` §3.5.
