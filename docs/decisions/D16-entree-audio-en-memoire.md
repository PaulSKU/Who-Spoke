# D16 — Entrée audio de la pipeline : signal en mémoire

Statut : actée
Date : 2026-10-27 (proposée et actée le même jour)

## Contexte

La vérification V5 a montré que pyannote.audio 4 ne peut pas décoder lui-même un fichier audio sur la machine de travail. Son décodeur, torchcodec 0.17, ne trouve pas les bibliothèques partagées de ffmpeg 9.0.2, installé via conda-forge (`Library not loaded: @rpath/libavutil.61.dylib`). La pipeline fonctionne en revanche quand on lui passe un dictionnaire `{"waveform", "sample_rate"}` construit à partir du WAV normalisé (D15), lu avec `scipy.io.wavfile`. La démonstration se fera sur des fichiers inconnus, et le tuteur peut exécuter le dépôt sur une autre machine.

## Options

| Option | Avantages | Inconvénients |
|---|---|---|
| A. Signal en mémoire : ffmpeg en ligne de commande pour normaliser, lecture du WAV en Python, dictionnaire passé à la pipeline | Fonctionne déjà ; aucune dépendance aux bibliothèques partagées de ffmpeg ; même chemin d'entrée pour toutes les pipelines (baseline, pyannote, NeMo) ; portable | Charge l'audio entier en mémoire : environ 115 Mo pour 30 min en float32 à 16 kHz, négligeable |
| B. Rendre les bibliothèques de ffmpeg visibles pour torchcodec (variable `DYLD_LIBRARY_PATH`, liens symboliques, ou ffmpeg d'une version prise en charge) | La pipeline accepte des chemins de fichier | Fragile sur macOS (variables `DYLD_*` filtrées dans certains contextes **[probable]**) ; compatibilité de torchcodec avec ffmpeg 9 non garantie **[incertain]** ; à refaire sur chaque machine, y compris celle du tuteur |

## Décision

Option A. Tout audio entrant suit un chemin unique : normalisation par ffmpeg en sous-processus vers un WAV 16 kHz mono, puis lecture en Python, puis passage à chaque pipeline d'un signal en mémoire. Aucun code du projet ne passe de chemin de fichier à une pipeline pyannote. La fonction de chargement est unique (`src/whospoke/audio.py`) et testée.

## Justification

Le résultat de V5 est sans ambiguïté : cette option fonctionne sur MPS comme sur CPU, avec des métriques identiques. Elle prolonge D15 (normalisation commune) et supprime une dépendance système fragile, ce qui compte pour une démonstration en direct et pour une exécution par un tiers.

## Conséquences

`src/whospoke/audio.py` fournit deux fonctions : `normalize(src, dst)` (ffmpeg en sous-processus, contrôle du code de retour) et `load_waveform(path)` (renvoie un tenseur `(1, n)` en float32 et la fréquence d'échantillonnage, avec vérification de 16 kHz et du mono). Elles sont accompagnées de tests (fichier stéréo à 44,1 kHz, m4a). Le README précise que seul l'exécutable `ffmpeg` est requis, et non ses bibliothèques. torchcodec reste installé comme dépendance de pyannote, mais n'est pas utilisé.

## Liens

V5 (`docs/journal.md`, 27/10/2026) ; D15 (`docs/cadrage.md`).
