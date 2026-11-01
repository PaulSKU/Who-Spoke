# E5 — Détection fine par Silero VAD (D25, V2 et V3)

Chantier E5 du 1er novembre 2026 (planning v2.0, rang A6). Code, tests et script de réglage seulement : **aucune inférence**, aucun modèle chargé. silero-vad n'est pas encore dans `uv.lock` : la piste A l'ajoute à la fusion.

**Légende de confiance.** **[certain]** : vérifié (fiche, code ou commande lancée). **[probable]** : lu sans vérification. **[incertain]** : non vérifié.

## 1. Silero VAD : vérifications (D27, D18)

| | |
|---|---|
| Paquet | `silero-vad` **6.2.3** (PyPI, 23/09/2026), dernière version publiée le 01/11/2026 **[certain]** |
| Licence | **MIT** (fichier `LICENSE` de la roue, classificateur PyPI) **[certain]**. Le badge du README porte encore le texte « CC BY-NC 4.0 », mais il affiche MIT et renvoie au fichier MIT : texte de badge périmé, sans effet sur la licence **[certain]** |
| Révision figée | Version 6.2.3 ; roue `7b7f5436cfcb…` ; poids `silero_vad.jit`, SHA-256 `e1122837f4154c511485fe0b9c64455f7b929c96fbb8d79fbdb336383ebd3720` **[certain]**. Les poids sont dans le paquet : aucun dépôt du Hub, aucun jeton. `whospoke.pipelines.silero.load_model` contrôle la version et cette empreinte au chargement |
| Dépendances | `packaging` et `torch>=1.12` seulement **[certain]**. **Ne pas** installer l'option `audio` (ni `all`, ni `test`) : elle impose `torchaudio<2.10`, alors que `uv.lock` a torchaudio 2.11.0. Le signal est passé en mémoire, sans `read_audio` |
| Télémétrie et réseau | Aucune **[certain, code lu]**. `load_silero_vad` lit le fichier de poids dans le paquet (`importlib.resources`). Le seul appel réseau du code est `torch.hub.download_url_to_file`, dans la classe `Validator` (outil de validation de Silero), jamais appelée ici. Le README l'affirme aussi : « no telemetry, no keys, no registration ». Aucune variable à ajouter à `TELEMETRY_OFF` |
| Effet de bord | **`import silero_vad` exécute `torch.set_num_threads(1)` pour tout le processus** **[certain, `silero_vad/model.py`]** : pyannote, dans le même processus, tournerait sur un seul fil, et la campagne de temps en serait faussée. `whospoke.pipelines.silero` rétablit le nombre de fils après l'import, puis calcule les probabilités de Silero sur un seul fil, comme le prévoit Silero ; un test le vérifie avec un faux paquet |
| Données d'entraînement | Non publiées ; le README annonce des corpus de plus de 6 000 langues **[probable]**. Recouvrement avec AMI ou SUMM-RE impossible à exclure (docs/corpus.md §9) |
| Périphérique | CPU (modèle JIT) ; moins de 1 ms par fenêtre de 32 ms sur un fil, d'après le README **[probable]** |

## 2. Post-traitement (`src/whospoke/pipelines/silero.py`)

La sortie de pyannote est intersectée avec le masque de parole de Silero (`refine`, `Annotation.crop(mask, mode="intersection")`) : chaque tour est coupé là où Silero n'entend pas de voix. Le post-traitement **ne crée jamais de parole ni de locuteur** ; un test aléatoire le vérifie (50 tirages : chaque locuteur après ⊆ avant, et ⊆ masque).

Masque en deux temps :

1. **Probabilités** (`speech_probabilities`) : une par fenêtre de 512 échantillons (32 ms), états remis à zéro, dernière fenêtre complétée par des zéros, comme dans `get_speech_timestamps` de Silero.
2. **Binarisation** (`speech_mask`) par la fonction de Silero elle-même, `get_speech_timestamps_from_probs` (6.2.3), sans réimplémentation.

| Réglage (catalogue) | Défaut | Passé à Silero | Effet |
|---|---|---|---|
| `silero.seuil` | 0,5 | `threshold` (Silero referme un tour sous `seuil − 0,15`) | Plus haut : plus de pauses rouvertes, plus de parole faible coupée |
| `silero.silence_min_s` | 0,2 s | `min_silence_duration_ms = silence_min_s + 2 × marge_s` | Durée minimale d'un silence rouvert, marge déduite, à une fenêtre près. La référence fusionne les pauses de 200 ms au plus : rouvrir plus court ne peut qu'ajouter de la parole manquée |
| `silero.marge_s` | 0,03 s (défaut de Silero) | `speech_pad_ms` | Marge gardée de part et d'autre de chaque zone de parole |
| `silero.parole_min_s` | 0,25 s, fixe | `min_speech_duration_ms` | Défaut de Silero, consigné mais non réglé |

**Moteur composé.** `SileroRefinement(inner, seuil, silence_min_s, marge_s)` enveloppe un moteur au contrat D19 et s'appelle `<moteur>-silero`. Il calcule le masque avant d'appeler le moteur suivi, ce qui garde l'ordre des étapes dans la barre de progression. Il applique le même masque à toutes ses sorties : sortie évaluée et `autres_sorties`, l'attribut que l'enveloppe à deux sorties de `main` ajoute à `Resultat`. Il consigne le temps de Silero (`durees_etapes["detection_fine"]`) et la parole retirée (`infos["silero"]`), et refuse la détection oracle. Ses réglages sont ajoutés à l'étape `detection` de `describe()`. Au catalogue, l'entrée `pyannote-community-1-silero` reprend celles de pyannote (ancre YAML) et y ajoute les six réglages `silero.*`.

**Fabrique pour `run_experiment.py`** : `whospoke.pipelines.silero.pyannote_silero`, de même signature que les classes de `PIPELINES`. Les paramètres de pyannote vont dans `pipeline.parametres`, et ceux du masque sous `pipeline.parametres.silero`.

## 3. Script de réglage (`scripts/reglage_silero.py`)

- **Sans relancer pyannote** : hypothèses relues dans `rttm/` d'EXP-0007 (V2, sortie habituelle) et d'EXP-0016 (V3, sortie exclusive) sur SUMM-RE dev (36 fichiers).
- **Silero une fois par fichier** : probabilités mises en cache dans `data/processed/summre/silero/6.2.3-e1122837f415/<uri>.npz`, avec contrôle de la version et de l'empreinte. Chaque point de la grille ne fait que rebinariser.
- **Contrôle de reproduction.** Avant la grille, les RTTM sources évalués sans post-traitement doivent redonner, au centième, les DER de leur `results_summre_dev.json` ; sinon, arrêt. Vérifié le 01/11 sur les vraies données, en lecture seule dans `~/Dev/Who-Spoke` : EXP-0007 redonne 26,00 / 10,76 % et EXP-0016 29,18 / 12,97 % (sans collar / collar 0,25). Coût : 11 s par point pour les deux collars, soit environ 6 min pour la grille par défaut, plus le passage de Silero.
- **Grille par défaut** (3 × 3 × 3 = 27 points, modifiable par `--seuils`, `--silences`, `--marges`) :
  - seuil : {0,35 ; 0,5 ; 0,65} ;
  - silence minimal rouvert : {0,2 ; 0,4 ; 0,8} s ;
  - marge : {0,03 ; 0,1 ; 0,2} s.
- **Point retenu** : DER sans collar le plus bas sur dev. Une alerte est levée si son DER avec collar dépasse celui de la source. Les conditions de D25 se jugent ensuite sur test, AMI et D24, par le bootstrap apparié.
- **V3** : sortie exclusive d'EXP-0016 avec le réglage retenu pour V2 (D25 : « réglage de V2 repris »).
- **Sorties** : `results/reglage_silero/<date>_<heure>/` contient `reglage.json`, `grille.csv` et `reglage.md`.

## 4. Pas-à-pas pour la piste A

1. **Après la fusion d'`outils`**, dans `~/Dev/Who-Spoke`, ajouter la dépendance avec accès réseau :

   ```bash
   uv add silero-vad==6.2.3
   ```

   Aucune option : l'option `audio` exige torchaudio < 2.10. Vérifier que `uv.lock` ne change que par silero-vad (et `packaging`, déjà présent). Commit `chore:`.
2. **Tests** : `uv run pytest tests/test_silero.py`. Les deux tests réservés jusqu'ici s'activent :
   - la vraie binarisation de Silero, qui vérifie le sens de `silence_min_s` et de la marge ;
   - le vrai modèle (marqueur `modele`), qui vérifie version, empreinte, nombre de fils et probabilités sur un signal synthétique.
3. **Contrôle réseau (D27)** : lancer `uv run python scripts/reglage_silero.py --probabilites` sous relevé réseau (même procédure qu'au premier fichier des moteurs de E4). Aucune connexion n'est attendue. Ce passage calcule aussi le cache des 36 fichiers de dev ; temps consigné par fichier.
4. **Réglage** : `uv run python scripts/reglage_silero.py`. Il refuse de tourner si EXP-0007 ou EXP-0016 ne se reproduisent pas. Reporter `reglage.md` dans le journal et versionner le dossier de sortie (commit `exp:` ou `docs:`, au choix du cockpit).
5. **Brancher le moteur** dans `scripts/run_experiment.py` :

   ```python
   from whospoke.pipelines.silero import pyannote_silero
   PIPELINES[pyannote_silero.name] = pyannote_silero
   ```

   `SOURCE_FILES` d'`app/pipeline.py` peut aussi pointer `pyannote-community-1-silero` vers `src/whospoke/pipelines/silero.py`.
6. **Expériences V2** : configuration d'EXP-0007 (SUMM-RE) et d'EXP-0001 (AMI), à une seule variable modifiée. `variable_modifiee: post_traitement` et `reference: EXP-0007` (ou EXP-0001). Bloc à ajouter :

   ```yaml
   pipeline:
     nom: pyannote-community-1-silero
     parametres:
       num_speakers: null
       min_speakers: null
       max_speakers: null
       silero: {seuil: …, silence_min_s: …, marge_s: …}   # point retenu sur dev
   ```

   pyannote est relancé : les temps du protocole incluent ainsi Silero (`detection_fine` dans `etapes_s`).
7. **Expériences V3** : même chose avec la sortie exclusive (`sortie: exclusive` de l'enveloppe de `main`), en référence à EXP-0016 et EXP-0017. Avec l'enveloppe à deux sorties, une seule exécution produit V3 (`rttm/`) et V2 (`rttm_habituelle/`, même masque) : au cockpit de dire si ce double usage est admis, ou s'il faut deux expériences.
8. **Règle de choix de D25** : bootstrap apparié sur SUMM-RE test et AMI test, puis conditions de D24 dès qu'elles existent.

## 5. Risques et points ouverts

- **Granularité.** Silero décide par fenêtres de 32 ms : les frontières rouvertes sont au mieux à 32 ms près, ce qui pèse sur le DER sans collar, pas avec collar.
- **Parole faible ou superposée.** Silero ne connaît pas les locuteurs : un masque qui coupe une voix faible coupe tous les locuteurs à cet instant. Le DER par zone (avec ou sans chevauchement) des expériences complètes le montrera.
- **Choix sur dev.** Le critère « DER sans collar minimal » est une proposition, à confirmer par le cockpit : D25 ne fixe que les conditions sur test.
- **Pas de vérification réelle ici.** Lancer, dans l'environnement principal, la fonction de binarisation tirée de la roue téléchargée a été refusé (code externe non encore admis comme dépendance). Le sens des réglages est donc vérifié par lecture du code 6.2.3 et par un masque simulé. Le test sur la vraie fonction (étape 2 du pas-à-pas) le confirmera après le `uv add`.
