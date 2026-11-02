#!/bin/sh
# Environnement séparé de Nemotron 3 Diarization (D23 §1, rang A4 ; chantier E4).
#
#   sh scripts/envs/nemotron.sh            # crée envs/nemotron/ (Python 3.12, versions de nemotron.txt)
#   sh scripts/envs/nemotron.sh --modeles  # en plus, télécharge les poids à la révision figée (réseau)
#
# Voie retenue : transformers (>= 5.18, qui intègre nemotron3_diarization), poids fp32
# (model.safetensors). Hors de l'environnement principal : pyproject.toml et uv.lock ne
# sont pas touchés. Le dossier envs/ est ignoré par git. Lancé depuis la racine du dépôt.
set -eu

ENV=envs/nemotron
MODEL=nvidia/Nemotron-3-Diarization
REVISION=f667ed73aee57d40cc39428eb768b4fd87a0a29e   # = MODEL_REVISION de src/whospoke/pipelines/nemotron3.py

uv venv "$ENV" --python 3.12
nice -n 19 uv pip install --python "$ENV/bin/python" -r scripts/envs/nemotron.txt

if [ "${1:-}" = "--modeles" ]; then
    # Seuls les fichiers de la voie transformers (le dépôt contient aussi .nemo, GGUF et vidéos).
    "$ENV/bin/python" - "$MODEL" "$REVISION" <<'EOF'
import sys
from huggingface_hub import snapshot_download
path = snapshot_download(sys.argv[1], revision=sys.argv[2],
                         allow_patterns=["config.json", "processor_config.json", "model.safetensors"])
print("Poids :", path)
EOF
fi

HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 "$ENV/bin/python" -c "
import torch, transformers
from transformers import Nemotron3DiarizationForAudioFrameClassification, Nemotron3DiarizationProcessor
print('Nemotron 3 : import correct ; torch', torch.__version__, '; transformers', transformers.__version__,
      '; MPS', torch.backends.mps.is_available())"
