# Protocole d'évaluation

Version 1.1 du 27 octobre 2026, figée (décision D1). Révision 1.1 : sémantique du collar vérifiée par test ; RTF en CPU seul rendu obligatoire. Révision 1.2 (D18, 28/10) : précisions sur la zone sans chevauchement (§3.2), le comptage des locuteurs (§3.4) et le préchauffage (§3.5), qui entérinent ce qu'appliquait déjà EXP-0001 ; aucun résultat antérieur n'en est affecté. Révision 1.3 (D21, 31/10) : relevé de l'alimentation et champ `conforme` des temps (§3.5) ; les métriques ne sont pas touchées et les résultats antérieurs ne sont pas modifiés (leur `conforme` serait `null`). Toute modification passe par une fiche de décision et rend les résultats antérieurs non comparables. Ceux-ci doivent alors être recalculés ou signalés comme tels.

**Légende de confiance.** **[certain]** : vérifié sur une source primaire. **[probable]** : source secondaire ou connaissance établie non revérifiée. **[incertain]** : à vérifier.

---

## 1. Objet

Mesurer, sur des fichiers dont on possède une référence annotée, dans quelle mesure le système attribue la parole au bon locuteur au bon moment, avec quel coût de calcul, et pourquoi il échoue quand il échoue.

---

## 2. Formats d'entrée

| Élément | Format | Règle |
|---|---|---|
| Audio évalué | WAV PCM 16 bits, 16 kHz, mono | Produit par la normalisation commune (D15) ; c'est ce fichier, et non l'original, qui est évalué |
| Référence | RTTM, une ligne `SPEAKER <uri> 1 <début> <durée> <NA> <NA> <locuteur> <NA> <NA>` | Une référence par fichier, dans `data/processed/<corpus>/rttm/` |
| Hypothèse | RTTM, même format | Dans `experiments/EXP-…/rttm/` |
| Zone évaluée (UEM) | Fichier UEM du corpus s'il existe, sinon le fichier entier | Toujours explicite dans `data/splits/<corpus>/` |

---

## 3. Métriques

### 3.1 DER (*Diarization Error Rate*), métrique principale

DER = (parole manquée + fausse alarme + confusion) / durée totale de parole de référence.

La parole manquée est la parole de référence non couverte par l'hypothèse. La fausse alarme est la parole de l'hypothèse là où la référence n'en contient pas. La confusion est la parole attribuée au mauvais locuteur, après appariement optimal entre étiquettes de l'hypothèse et locuteurs de référence. Dans une zone de chevauchement, chaque locuteur de référence compte séparément : produire un seul locuteur là où deux parlent coûte une parole manquée.

Le DER est calculé dans deux conditions, toujours avec les chevauchements comptés.

| Condition | Tolérance aux frontières | Paramètres `pyannote.metrics` | Usage |
|---|---|---|---|
| `collar_0` (principale) | Aucune | `DiarizationErrorRate(collar=0.0, skip_overlap=False)` | Comparaisons internes, ablation |
| `collar_0_25` (secondaire) | 0,25 s de part et d'autre de chaque frontière de référence | `DiarizationErrorRate(collar=0.5, skip_overlap=False)` | Comparabilité avec la littérature |

**Point de vigilance.** Dans `pyannote.metrics`, le paramètre `collar` désigne la largeur totale de la zone exclue, répartie pour moitié avant et pour moitié après la frontière **[certain, vérifié par le test « collar » le 27/10 : pour un décalage de 0,2 s, le DER s'annule à partir de `collar=0.4`]**. Une tolérance de 0,25 s de part et d'autre, convention usuelle des outils NIST, correspond donc à `collar=0.5`.

### 3.2 Décomposition par zone

Le DER est recalculé séparément sur les zones sans chevauchement et sur les zones de chevauchement de la référence, en restreignant l'UEM à chacune d'elles, dans la condition `collar_0`. La zone de chevauchement est l'intersection de l'UEM et des instants où au moins deux locuteurs de référence parlent ; la zone sans chevauchement est tout le reste de l'UEM, silences compris, si bien que les fausses alarmes y sont comptées (D18). C'est cette décomposition qui permet de savoir si une erreur vient de la gestion du chevauchement.

### 3.3 JER (*Jaccard Error Rate*), métrique complémentaire

Le JER calcule pour chaque locuteur de référence une erreur de type Jaccard entre ses segments et ceux du locuteur hypothèse apparié, puis fait la moyenne sur les locuteurs. Chaque locuteur pèse autant, quelle que soit sa durée de parole. Le JER révèle donc l'oubli ou la fusion d'un locuteur minoritaire, que le DER, pondéré par le temps, masque. Implémentation : `pyannote.metrics.diarization.JaccardErrorRate`.

### 3.4 Nombre de locuteurs

Pour chaque fichier, on compare le nombre de locuteurs distincts dans l'hypothèse (K̂) et dans la référence (K), comptés dans les deux cas sur les seuls locuteurs présents dans l'UEM (D18). L'erreur absolue moyenne est la moyenne de |K̂ − K|, et le taux exact est la proportion de fichiers où K̂ = K. Ces deux grandeurs mesurent directement l'amélioration n° 1 de l'ablation (D9).

### 3.5 Temps d'inférence

Le RTF (*Real-Time Factor*) est le rapport entre le temps de calcul et la durée de l'audio. Le temps de calcul couvre le chargement de l'audio normalisé et l'exécution complète de la pipeline. Il exclut le chargement des modèles, mesuré et rapporté à part (`chargement_modeles_s`). La mesure est faite en temps réel écoulé (horloge murale), machine sur secteur, sans autre calcul lourd en parallèle. Le périphérique (`cpu`, `mps`, `cuda`) est consigné. Toute pipeline candidate au rendu est mesurée sur la machine locale deux fois, en MPS puis en CPU seul, sur un même sous-ensemble fixe de fichiers, et le temps de traitement d'une réunion de 30 minutes est rapporté explicitement (demande du tuteur). Pour éviter des heures de calcul sur CPU, la mesure en CPU seul se fait sur un **sous-ensemble de mesure du temps**, fixé une fois pour toutes par corpus dans `data/splits/<corpus>/temps.txt` (deux ou trois fichiers de la partition de test), et consignée dans le champ `temps_cpu` de `results.json`. La mesure principale (`temps`) porte sur l'exécution complète, sur le périphérique utilisé. Le préchauffage se fait sur les 60 premières secondes du premier fichier et n'est pas compté ; tous les fichiers sont ensuite comptés (D18).

**Alimentation (D21 §3).** Le script d'exécution relève l'état d'alimentation (`pmset -g batt` sur macOS) au début de l'exécution, puis toutes les 60 s, puis à la fin, et consigne les relevés dans le bloc `alimentation` de `execution_<device>.json`. Le script d'évaluation en tire le champ `conforme` des blocs `temps` et `temps_cpu` de `results.json` : `true` si tous les relevés de l'exécution concernée sont sur secteur, `false` si au moins un relevé ne l'est pas, `null` si l'état n'a pas pu être lu (par exemple hors macOS) ou n'a pas été relevé (exécutions antérieures à D21). Un temps non conforme n'est jamais reporté dans le README ni dans une comparaison de temps de calcul.

---

## 4. Agrégation

Les métriques globales d'un jeu de fichiers sont agrégées en sommant les durées d'erreur et les durées de référence sur l'ensemble des fichiers, puis en faisant le rapport. On ne fait pas la moyenne des DER par fichier, qui donnerait le même poids à un fichier de deux minutes et à un fichier d'une heure. Les valeurs par fichier sont conservées dans `per_file.csv`. Les métriques de nombre de locuteurs donnent, elles, un poids égal à chaque fichier.

Les jeux étant petits (quelques dizaines de fichiers au plus), toute comparaison entre deux expériences s'accompagne du nombre de fichiers où l'une fait mieux que l'autre. Pour les comparaisons qui fondent une décision, on ajoute un intervalle de confiance à 95 % de la différence de DER, obtenu par bootstrap sur les fichiers (1 000 tirages, graine fixée).

---

## 5. Partitions et intégrité

| Règle | Détail |
|---|---|
| Partitions | Partitions officielles de chaque corpus, listées dans `data/splits/<corpus>/` ; corpus maison entièrement en test |
| Réglage | Seuils, paramètres de VAD et de clustering réglés sur dev uniquement |
| Test | Évalué une fois par configuration retenue ; jamais de retour en arrière sur un paramètre à cause d'un résultat de test |
| Contamination | Pour chaque modèle pré-entraîné, les corpus vus à l'entraînement sont consignés dans `docs/corpus.md` ; un résultat obtenu sur une partition vue est signalé comme tel |
| Références | Règles de construction des RTTM de référence par corpus documentées dans `docs/corpus.md` (notamment la fusion des segments pour SUMM-RE) |

---

## 6. Tests obligatoires du protocole

Ces tests figurent dans `tests/test_protocole_eval.py` et doivent réussir avant la première expérience.

| Test | Construction | Attendu |
|---|---|---|
| Identité | Hypothèse égale à la référence, étiquettes renommées | DER = 0, JER = 0 |
| Appariement | Deux locuteurs dont les étiquettes sont permutées | DER = 0 |
| Silence | Hypothèse vide | DER = 100 %, entièrement en parole manquée |
| Collar | Frontières de l'hypothèse décalées de 0,2 s | DER > 0 en `collar_0` ; DER = 0 en `collar_0_25` (vérifie la sémantique de `collar=0.5`) |
| Chevauchement | Référence avec 2 s de chevauchement, hypothèse à un seul locuteur sur cette zone | 2 s de parole manquée exactement |
| Agrégation | Deux fichiers de durées très différentes | Le DER global égale le rapport des sommes, pas la moyenne des DER |

---

## 7. Analyse des échecs

Pour chaque évaluation sur le jeu francophone, les trois fichiers de plus fort DER sont examinés : composant dominant, nombre de locuteurs estimé contre réel, et écoute des zones en erreur. Le constat est consigné dans `notes.md` de l'expérience. Le sujet demande explicitement d'analyser les cas d'échec.

---

## 8. Sources

| Point | Source |
|---|---|
| Définition du collar, `skip_overlap`, métriques de comptage de locuteurs | Documentation pyannote.metrics — https://pyannote.github.io/pyannote-metrics/reference.html |
| Convention sans collar et chevauchements comptés du benchmark pyannote | https://huggingface.co/pyannote/speaker-diarization |
