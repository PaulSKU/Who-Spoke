# E4 — Préparation de Nemotron 3 Diarization et de DiariZen

Chantier E4 du 1er novembre 2026 (planning v2.0 ; D23 §1 et amendement du 01/11 ; rangs A4 et A5). Installation seulement : **aucune inférence**, aucun poids téléchargé. La première exécution réelle revient à la piste A.

**Légende de confiance.** **[certain]** : vérifié (fiche, code ou commande lancée). **[probable]** : lu sans vérification. **[incertain]** : non vérifié.

## 1. Synthèse

| | Nemotron 3 Diarization (A4) | DiariZen Large s80 v2 (A5) |
|---|---|---|
| Voie retenue | transformers 5.22.1 (intégration native depuis 5.18), poids fp32 | Code DiariZen au commit figé, fork de pyannote 3.1.1 |
| Environnement | `envs/nemotron/` : Python 3.12.13, torch 2.15.0 | `envs/diarizen/` : Python 3.10.20, torch 2.1.1, numpy 1.26.4 |
| Recréation | `sh scripts/envs/nemotron.sh [--modeles]` | `sh scripts/envs/diarizen.sh [--modeles]` |
| Import en CPU sur macOS | Oui **[certain]** | Oui **[certain]** |
| MPS | Probable : code PyTorch pur, sans appel CUDA ; `torch.backends.mps.is_available()` vrai **[probable]** | Non prévu par le code (CUDA, sinon CPU) ; forçable par `pipeline.to("mps")` dans l'exécutant, non vérifié **[incertain]** |
| Révision figée | `f667ed73aee57d40cc39428eb768b4fd87a0a29e` | modèle `027b3e221b9d81dce2be794084f1dbd3ba2da403` ; empreintes `pyannote/wespeaker-voxceleb-resnet34-LM@837717ddb9ff5507820346191109dc79c958d614` ; code `844f5555b0a98acd0931511fc641a8c5b8ba92c7` |
| Accès | Non restreint, sans jeton | Non restreint, sans jeton |
| Licence | OpenMDW-1.1 | Poids CC BY-NC 4.0 (non commercial) ; code MIT |
| Nombre de locuteurs | Estimé, 8 au plus ; ni imposé ni borné | Estimé (bornes 1 à 20 de `config.toml`), borné ou imposé |
| Temps d'installation (borne D23) | 5 min 30 s (2 h) | 2 min 55 s (4 h) |
| Enveloppe | `src/whospoke/pipelines/nemotron3.py` | `src/whospoke/pipelines/diarizen.py` |

Temps mesurés à l'horloge murale, de la première lecture de la fiche à la fin de la vérification d'import. S'y ajoutent 7 min 40 s de travail commun aux deux moteurs (scripts d'installation, enveloppes, catalogue, tests), puis la documentation. La rapidité vient du cache local de uv, qui contenait déjà la plupart des paquets ; elle ne présage pas du temps sur une machine vierge (12/11). Les installations ont tourné avec `nice -n 19`, pendant que la piste A calculait.

## 2. Nemotron 3 Diarization : trois voies explorées

| Ordre | Voie | Résultat |
|---|---|---|
| 1 | **transformers** | `nemotron3_diarization` est présent dans transformers depuis la version 5.18.0 (publiée ; la fiche indique encore « depuis la source »). Installé en 5.22.1 avec torch 2.15.0, Python 3.12 (transformers demande ≥ 3.11). Import de `Nemotron3DiarizationForAudioFrameClassification` et du processeur, lecture de `config.json` : corrects. Inférence hors ligne par `processor(audio)` puis `model(**inputs).logits` (une trame de 10 ms, 8 sorties), segments par `processor.extract_speaker_dict(logits, mask, threshold=0.5)` **[certain]**. Retenue : première voie qui s'installe, poids fp32 identiques à ceux de NeMo |
| 2 | **NeMo** | `nemo-toolkit[asr]==3.0.0` (Apache-2.0) s'installe en Python 3.12 sur macOS, en 7 s depuis le cache ; `from nemo.collections.asr.models import SortformerEncLabelModel` réussit en CPU (67 s d'import) **[certain]**. Environnement d'essai `envs/nemotron-nemo/` (1,4 Go), non retenu : il tire wandb, tensorboard, OneLogger et OpenTelemetry. La fiche ne cite que Linux et les GPU NVIDIA |
| 3 | **NeMo-Speech.cpp** | Binaires officiels 0.3.0 pour macOS arm64, CPU et **Metal** (archive de 7 Mo, SHA-256 contrôlé, sans le script `curl \| sh` qui modifie le `PATH`). `nemo-speech diarize --format rttm --device metal` existe ; `--version` et `--help` répondent **[certain]**. Non retenu : seuls des poids quantifiés `q8_0` (GGUF) sont publiés pour ce moteur, différents des poids fp32. Option à garder si la vitesse en MPS déçoit. Essai dans `envs/nemotron-cpp/` |

## 3. DiariZen : adaptation de l'installation CUDA

L'installation documentée vise CUDA 12.1 (conda, Python 3.10, torch 2.1.1 cu121). Adaptations pour macOS, toutes consignées dans `scripts/envs/diarizen.sh` :

- uv au lieu de conda ; roues torch 2.1.1, torchaudio 2.1.1 et torchvision 0.16.1 de PyPI (CPU et MPS) ;
- `onnxruntime` au lieu d'`onnxruntime-gpu`, absent sur macOS et seulement utilisé par la vérification de locuteur ONNX de pyannote, que DiariZen n'appelle pas ;
- sans `jupyterlab` ni `pre-commit` (outils de développement), ni les options `[dev,testing]` du fork de pyannote ;
- `constraints.txt` du dépôt respecté (torch, numpy).

Import de `DiariZenPipeline` en CPU : correct **[certain]**. `DiariZenPipeline.from_pretrained` ne fige aucune révision : l'exécutant lit donc les fichiers dans le cache à la révision demandée, puis construit le pipeline comme le fait `from_pretrained`.

**Risque au premier chargement [incertain].** Le fork de pyannote date de 2023 (3.1.1), alors que l'environnement contient huggingface_hub 2.4.0 et lightning 2.6.6, les versions courantes sans contrainte du dépôt. Les modèles sont lus depuis des fichiers locaux, ce qui évite les appels au Hub avec `use_auth_token`, mais le chargement des points de contrôle n'a pas pu être vérifié sans les poids. En cas d'échec, contraindre ces deux paquets dans `scripts/envs/diarizen.txt` (temps compté dans la borne de 4 h).

## 4. Télémétrie (D27)

Détail dans `docs/methode.md` §7.1. L'exécutant reçoit `TELEMETRY_OFF`, `HF_HUB_OFFLINE=1`, `WANDB_MODE=disabled` et `WANDB_DISABLED=true`, perd `HF_TOKEN` et `ONE_LOGGER_EXPORTER_CONFIG_PATH`, et tourne dans un dossier temporaire vide (`whospoke.pipelines.externe.CHILD_ENV`) ; les exécutants imposent les mêmes variables avant tout import. Un test le vérifie avec un exécutant simulé. Le contrôle réseau de D27 (exécution courte sous relevé) reste à faire par la piste A, au premier fichier de chaque moteur.

## 5. Enveloppes

- **Contrat D19.** `run(waveform, sample_rate, uri, num_speakers, speech, progress)` → `Resultat` ; `describe()` avec modèle et révision, réglages lus dans la configuration effective annoncée par l'exécutant ; entrées du catalogue (`catalogue.yaml`, moteurs `nemotron3-diarization` et `diarizen`).
- **Sous-processus persistant** (`whospoke.pipelines.externe`). L'exécutant est lancé une fois à la construction et charge le modèle : le chargement n'entre pas dans le temps de calcul. Puis une requête par fichier : WAV PCM 16 bits sans perte, RTTM relu par `load_rttm`. La sortie standard est réservée au protocole, et ce que les bibliothèques y écrivent part sur la sortie d'erreur. Toute erreur remonte avec la fin de la sortie d'erreur de l'exécutant.
- **Exécutants** (`runners/executant_*.py`). Nommés ainsi pour ne pas masquer le paquet du moteur : un fichier `diarizen.py` cachait le paquet `diarizen`, erreur trouvée au premier lancement réel.
- **Vérifié sans modèle.** Les deux exécutants réels démarrent dans leur environnement, importent leur pile, puis s'arrêtent proprement au chargement des poids, absents du cache (« hors ligne, fichier absent »). 11 tests avec un exécutant simulé.

## 6. Premier fichier (piste A)

1. Dans `~/Dev/Who-Spoke`, après la fusion : `sh scripts/envs/nemotron.sh --modeles` et `sh scripts/envs/diarizen.sh --modeles`, avec accès réseau. Poids à télécharger : `model.safetensors` et ses deux fichiers de configuration pour Nemotron ; le dépôt DiariZen (`pytorch_model.bin`, PLDA, `config.toml`) et les empreintes WeSpeaker. Tailles non mesurées.
2. Un fichier court sous relevé réseau (D27).
3. Construire le moteur (`Nemotron3Diarization(device="cpu")`, puis `"mps"` ; `DiariZen(device="cpu")`), consigner `describe()` et le chargement.
4. Brancher les moteurs dans `scripts/run_experiment.py` : la correspondance entre les noms de configuration et les classes n'est pas faite ici. `run_experiment.py` est modifié sur `main` (sortie exclusive de pyannote), d'où ce choix.
