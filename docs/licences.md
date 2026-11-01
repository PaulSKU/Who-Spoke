# Licences

Version du 1er novembre 2026 (chantier E1, audit du 01/11, R-R1).

**Légende de confiance.** **[certain]** : lu sur la source primaire à la date indiquée. **[probable]** : non revérifié.

## 1. Ce dépôt

Le code et la documentation de ce dépôt sont publiés sous **licence MIT** (fichier `LICENSE` à la racine ; titulaire : l'auteur déclaré dans `pyproject.toml`). Les fichiers de tiers inclus dans le dépôt gardent leur propre licence (section 3).

Le dépôt ne contient **aucun poids de modèle ni aucun audio**. Les modèles sont téléchargés par chaque utilisateur depuis le Hub Hugging Face (`scripts/prefetch_models.py`), sous les conditions de leurs auteurs. Les corpus sont reconstruits par les scripts de `scripts/data/` (`docs/corpus.md`).

## 2. Modèles pré-entraînés

| Composant | Usage dans le projet | Révision figée | Licence | Vérification |
|---|---|---|---|---|
| `pyannote/speaker-diarization-community-1` | Moteur pyannote (segmentation, empreintes WeSpeaker ResNet34, regroupement) ; empreintes WeSpeaker de la baseline | `3533c8cf8e36` | **CC-BY-4.0** ; modèle à accès restreint (conditions à accepter sur le Hub) | Fiche et API du Hub, 01/11/2026 **[certain]** |
| `speechbrain/spkrec-ecapa-voxceleb` | Empreintes ECAPA-TDNN de la baseline (D22) | `0f99f2d0ebe8` | **Apache-2.0** | Fiche et API du Hub, 01/11/2026 **[certain]** |
| `BUT-FIT/diarizen-wavlm-large-s80-md-v2` (DiariZen) | Moteur DiariZen, environnement séparé (D23, rang A5 ; enveloppe préparée, chantier E4) | `027b3e221b9d` | **CC BY-NC 4.0** : usage non commercial (recherche, démonstration de la piscine) ; code DiariZen sous MIT (commit `844f5555b0a9`) | Fiche, `MODEL_LICENSE` et API du Hub, 01/11/2026 **[certain]** |
| `pyannote/wespeaker-voxceleb-resnet34-LM` | Empreintes de DiariZen | `837717ddb9ff` | **CC-BY-4.0** | API du Hub, 01/11/2026 **[certain]** |
| `nvidia/Nemotron-3-Diarization` | Moteur Nemotron 3, environnement séparé (D23, rang A4 ; enveloppe préparée, chantier E4) | `f667ed73aee5` | **OpenMDW-1.1** (licence ouverte de NVIDIA pour les modèles) ; non restreint | Fiche et API du Hub, 01/11/2026 **[certain]** |
| Silero VAD (`silero-vad`, poids `silero_vad.jit` inclus dans le paquet) | Détection fine en post-traitement de pyannote (D25, V2 et V3 ; chantier E5) | version 6.2.3, poids `e1122837f415` (SHA-256) | **MIT** ; ni dépôt du Hub ni jeton | `LICENSE` et métadonnées de la roue PyPI, 01/11/2026 **[certain]** |

CC-BY-4.0 impose de citer l'auteur, de donner un lien vers la licence et d'indiquer les modifications, en cas de partage du modèle ou d'une œuvre adaptée. Le projet ne redistribue pas les poids et ne les modifie pas. L'attribution est faite par ce tableau, auquel renvoie le README : auteur, identifiant, révision et licence de chaque modèle.

## 3. Fichiers de tiers inclus dans le dépôt

| Composant | Emplacement | Version | Licence | Vérification |
|---|---|---|---|---|
| wavesurfer.js et son greffon `regions` | `app/static/wavesurfer-7.12.12/` | 7.12.12 | **BSD-3-Clause** (texte joint dans le dossier) | Fichier `LICENSE` du paquet, 01/11/2026 **[certain]** |

## 4. Dépendances Python principales

Versions figées par `uv.lock`, licences lues dans les métadonnées des paquets installés le 01/11/2026 **[certain]**. Les dépendances indirectes ne sont pas listées ; `uv tree` les affiche.

| Paquet | Version | Licence |
|---|---|---|
| pyannote.audio | 4.0.7 | MIT |
| pyannote.core | 6.1.0 | MIT |
| pyannote.metrics | 4.2.0 | MIT |
| speechbrain | 1.1.2 | Apache-2.0 |
| torch | 2.14.1 | BSD-3-Clause pour l'essentiel (expression complète : Apache-2.0, BSD-2-Clause, BSD-3-Clause, BSL-1.0, MIT) |
| torchaudio | 2.11.0 | BSD-2-Clause |
| gradio | 6.31.0 | Apache-2.0 |
| huggingface_hub | 2.3.0 | Apache-2.0 |
| numpy | 2.4.6 | BSD-3-Clause (avec des parties 0BSD, MIT, Zlib, CC0-1.0) |
| scipy | 1.17.1 | BSD-3-Clause |
| scikit-learn | 1.9.1 | BSD-3-Clause |
| pandas | 3.1.0 | BSD-3-Clause |
| pyarrow | 26.0.0 | Apache-2.0 |
| librosa | 0.11.0 | ISC |
| PyYAML | 6.0.3 | MIT |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| pytest (développement) | 9.1.1 | MIT |

Aucune de ces licences n'empêche la publication du dépôt sous MIT : aucune n'est copyleft.

Environnements séparés des moteurs externes (`envs/`, hors du dépôt ; versions dans `scripts/envs/*.txt`) : transformers 5.22.1 (Apache-2.0) et torch 2.15.0 pour Nemotron 3 ; torch 2.1.1, fork de pyannote.audio 3.1.1 (MIT, fourni par DiariZen) et lightning 2.6.6 (Apache-2.0) pour DiariZen. Explorés sans être retenus : NeMo 3.0.0 (Apache-2.0) et NeMo-Speech.cpp 0.3.0 (Apache-2.0).

À ajouter à `uv.lock` par la piste A à la fusion d'`outils` (chantier E5) : silero-vad 6.2.3 (MIT), qui ne dépend que de `packaging` et de torch.

## 5. Corpus

Détail dans `docs/corpus.md` ; rien n'est redistribué par le dépôt, sauf les listes de partition, les UEM et les manifestes (`data/splits/`, `data/manifests/`).

| Corpus | Licence |
|---|---|
| AMI | CC BY 4.0 (site d'Édimbourg) |
| SUMM-RE | CC BY-SA 4.0 |
| Corpus maison | Aucune diffusion : enregistrements traités uniquement en local, selon le consentement des participants (`docs/corpus-maison/`) |
