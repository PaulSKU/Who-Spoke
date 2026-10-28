# D19 — Baseline classique et contrat commun des moteurs

Statut : actée
Date : 2026-10-28 (proposée et actée le même jour)

## Contexte

Le sujet exige une baseline explicable : spectrogrammes et MFCC, détection de parole par énergie et seuils, segmentation puis regroupement des voix. D7 en fixe les grandes lignes. D17 impose que chaque moteur expose la même interface (exécution sur un signal en mémoire, progression par étape, description de sa configuration effective) pour l'application et la page Pipeline. EXP-0001 montre aussi qu'il faut un vrai mode « nombre de locuteurs oracle ». L'enveloppe pyannote actuelle prend un `num_speakers` fixe pour tous les fichiers, ce qui n'est un oracle que si tous les fichiers ont le même nombre de locuteurs : c'est vrai sur AMI (4), faux sur VoxConverse ou SUMM-RE.

## Décision

### 1. Contrat commun des moteurs (`src/whospoke/pipelines/base.py`)

| Élément | Contenu |
|---|---|
| Construction | Paramètres du moteur et périphérique ; chargement des modèles une seule fois |
| Appel | `run(waveform, sample_rate, uri, num_speakers=None, speech=None, progress=None)` → `Resultat` |
| `num_speakers` | Nombre de locuteurs **par fichier**. Le script d'exécution le lit dans la référence quand la configuration demande `mode_n_locuteurs: oracle` |
| `speech` | Régions de parole imposées (détection de parole oracle). Facultatif ; un moteur qui ne le prend pas en charge le refuse explicitement (pyannote) |
| `progress` | Rappel `(étape, fraction)` utilisé par l'interface |
| `Resultat` | Annotation (avec chevauchements quand le moteur en produit), durée par étape, trace facultative (§3) |
| `describe()` | Configuration effective par étape : pour chaque réglage, le nom, la valeur et l'origine. Le texte explicatif vient du catalogue `src/whospoke/pipelines/catalogue.yaml` (D17) |
| `speaker_mode` | `estime`, `borne` ou `oracle`, d'après la configuration de l'expérience |

L'enveloppe pyannote est mise au contrat sans changement de comportement en mode estimé : EXP-0001 doit rester reproductible.

### 2. Baseline (`src/whospoke/pipelines/baseline.py`)

| Étape | Traitement | Réglages et valeurs initiales | Joue sur |
|---|---|---|---|
| Analyse | Trames de 25 ms, pas de 10 ms ; énergie logarithmique ; 20 MFCC (librosa) sur 40 filtres mel | `n_mfcc` = 20 ; `n_mels` = 40 (amendement 1) | — |
| Normalisation cepstrale | Soustraction de la moyenne des MFCC sur le fichier | activée | confusion (atténue l'effet du canal et de la salle) |
| Détection de parole | Seuil sur l'énergie : plancher = 10e centile, niveau de parole = 90e centile, seuil = plancher + α × (niveau − plancher) ; lissage par filtre médian ; durées minimales | α = 0,3 ; médian sur 11 trames (110 ms) ; parole ≥ 0,3 s ; silence ≥ 0,2 s | parole manquée, fausse alarme |
| Segmentation | Fenêtres fixes sur les régions de parole, bornées à leur région ; fenêtre gardée si au moins 50 % de sa durée tombe dans la région ; une région plus courte qu'une fenêtre (mais ≥ 0,5 s) donne une fenêtre unique | 1,5 s, pas de 0,75 s | frontières, confusion |
| Représentation | Moyenne et écart-type des MFCC sur les seules trames de parole de la fenêtre (40 valeurs), centrés-réduits sur le fichier | — | confusion |
| Regroupement | Agglomératif hiérarchique, distance cosinus, lien moyen ; coupe par seuil θ, ou par le nombre de locuteurs s'il est donné | θ réglé sur dev (§4) | confusion, nombre de locuteurs |
| Attribution | Chaque trame de parole reçoit l'étiquette de la fenêtre dont le centre est le plus proche ; fusion des tours d'un même locuteur séparés par 200 ms ou moins | — | frontières |
| Sortie | Annotation sans chevauchement (par construction) | — | parole manquée en chevauchement |

Ce dernier point est assumé : une baseline qui ne produit qu'un locuteur à la fois manque mécaniquement le second locuteur de chaque chevauchement. Sur AMI, cela borne déjà son DER par le bas d'une part importante de la parole en chevauchement (27 % de la parole de référence sur le test). C'est précisément ce que la comparaison avec pyannote doit montrer.

### 3. Trace

Avec l'option `--trace`, la baseline enregistre pour chaque fichier, dans `experiments/EXP-…/trace/<uri>/`, la courbe d'énergie et le seuil, les régions de parole, les fenêtres, la matrice des représentations, la matrice de liaison du regroupement avec θ, et les étiquettes. La trace alimente la page Pipeline et l'analyse des échecs. Elle n'est pas versionnée (`.gitignore` : `experiments/*/trace/`).

### 4. Réglage et expériences prévues

Un **balayage** de réglage est une seule expérience. Il produit un fichier `balayage_<corpus>_<partition>.csv` (une ligne par valeur, métriques du protocole) et retient la valeur de plus faible DER sans collar. Le test n'est évalué qu'avec cette valeur. θ est réglé sur AMI dev tant que SUMM-RE n'est pas prêt ; il sera réglé à nouveau sur SUMM-RE dev, qui reste le jeu de validation prioritaire (D3).

| Expérience | Moteur | Variable par rapport à la référence | Référence | Question |
|---|---|---|---|---|
| EXP-0002 | Baseline | — (balayage de θ sur dev, puis test) | — | Que vaut une chaîne classique ? |
| EXP-0003 | Baseline | Nombre de locuteurs oracle | EXP-0002 | Combien coûte l'estimation du nombre de locuteurs ? |
| EXP-0004 | Baseline | Détection de parole oracle | EXP-0002 | Quelle part de l'erreur vient de la détection ? |
| EXP-0005 | pyannote | Nombre de locuteurs oracle | EXP-0001 | Même question pour pyannote |

Les empreintes neuronales (D8) suivront, en remplaçant la seule représentation MFCC, sur la référence EXP-0002.

## Justification

Chaque réglage de la baseline correspond à un composant identifiable du DER, ce qui la rend explicable. Les deux oracles décomposent l'erreur par étape, et le contrat commun permet de comparer les moteurs sur les mêmes fichiers, de les afficher dans l'interface et de générer la page Pipeline sans rien recopier. Les valeurs initiales sont des choix raisonnables **[probable]**, pas des optimums ; seul θ est réglé, pour garder l'ablation lisible.

## Conséquences

Fichiers concernés : `src/whospoke/pipelines/base.py`, `baseline.py` et `catalogue.yaml`, l'enveloppe pyannote mise au contrat, et `scripts/run_experiment.py` (mode oracle par fichier, balayage, `--trace`). Des tests sur des signaux synthétiques valident chaque étape. Le temps de calcul de la baseline est mesuré comme les autres (MPS non pertinent : CPU seul).

## Amendements du 28/10/2026 (après EXP-0002)

1. **Filtres mel.** 40 filtres (`n_mels` = 40). Avec des trames de 25 ms, la valeur par défaut de librosa (128) laisse des filtres vides ; 40 est une valeur usuelle en traitement de la parole **[probable]**.
2. **Fenêtres bornées à leur région de parole**, et statistiques calculées sur les seules trames de parole. Sinon, les fenêtres de bord débordent sur le silence ou sur la région suivante et forment des groupes parasites (constaté sur signal synthétique).
3. **Temps CPU d'un moteur exécuté en CPU.** `temps_cpu` est tiré de l'exécution principale, restreinte aux fichiers de `temps.txt`.
4. **Fusion des pauses de 200 ms.** Elle est conservée, même si elle est presque toujours redondante avec la durée minimale de silence de la détection (0,2 s). Elle garantit la même règle de découpage que celle des références (`conventions-annotation.md` §2).
5. **Test de reproduction d'EXP-0001** (RTTM d'ES2004a identique à l'octet près). Il est marqué comme test lent (`pytest -m lent`), exclu de la suite par défaut et lancé avant toute modification de l'enveloppe pyannote.

## Liens

D7, D8, D9, D17 ; EXP-0001 ; `docs/glossaire.md` partie 3.
