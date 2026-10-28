# Données

Le contenu de `data/` n'est pas versionné, à l'exception de ce fichier, de `manifests/` et de `splits/` (décision D13, `docs/methode.md` §2 et §7). Aucun fichier audio n'entre dans git.

| Dossier | Contenu | Versionné |
|---|---|---|
| `manifests/` | Un CSV par corpus : identifiant, source, licence, durée, SHA-256 | Oui |
| `splits/<corpus>/` | Listes de fichiers par partition (`dev.txt`, `test.txt`) et UEM éventuels | Oui |
| `raw/` | Téléchargements bruts | Non |
| `processed/` | Audio normalisé WAV 16 kHz mono et RTTM de référence | Non |

## Reconstruction

Chaque corpus est obtenu par un script `scripts/data/get_<corpus>.py`, qui télécharge, vérifie les sommes de contrôle du manifeste, normalise l'audio en 16 kHz mono via ffmpeg et produit le RTTM de référence. Les sources, licences et conditions d'accès sont décrites dans `docs/corpus.md`.

| Corpus | Commande | Volume |
|---|---|---|
| AMI SDM, dev et test | `uv run python scripts/data/get_ami.py` | ~2,2 Go bruts, ~2,2 Go normalisés |
| SUMM-RE, dev et test | `uv run python scripts/data/get_summre.py` | 25,8 Go téléchargés (Parquet supprimés après extraction), 2,6 Go conservés |
