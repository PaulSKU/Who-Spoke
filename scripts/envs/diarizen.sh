#!/bin/sh
# Environnement séparé de DiariZen (D23, amendement du 01/11, rang A5 ; chantier E4).
#
#   sh scripts/envs/diarizen.sh            # crée envs/diarizen/ (Python 3.10, versions de diarizen.txt)
#   sh scripts/envs/diarizen.sh --modeles  # en plus, télécharge les poids aux révisions figées (réseau)
#
# Installation documentée par DiariZen pour CUDA 12.1 seulement (conda, Python 3.10,
# torch 2.1.1). Adaptation pour macOS : uv au lieu de conda, roues torch 2.1.1 de PyPI
# (CPU et MPS), onnxruntime au lieu d'onnxruntime-gpu (absent sur macOS, non utilisé à
# l'inférence), sans jupyterlab ni pre-commit (outils de développement). Code au commit
# figé, fork de pyannote 3.1.1 fourni par le dépôt. Poids sous CC BY-NC 4.0 : usage non
# commercial seulement. Hors de l'environnement principal ; envs/ est ignoré par git.
set -eu

ENV=envs/diarizen
CODE_COMMIT=844f5555b0a98acd0931511fc641a8c5b8ba92c7          # = CODE_COMMIT de src/whospoke/pipelines/diarizen.py
MODEL=BUT-FIT/diarizen-wavlm-large-s80-md-v2
MODEL_REVISION=027b3e221b9d81dce2be794084f1dbd3ba2da403
EMBEDDING=pyannote/wespeaker-voxceleb-resnet34-LM
EMBEDDING_REVISION=837717ddb9ff5507820346191109dc79c958d614

mkdir -p "$ENV"
if [ ! -d "$ENV/src/.git" ]; then
    git clone -q https://github.com/BUTSpeechFIT/DiariZen.git "$ENV/src"
fi
git -C "$ENV/src" checkout -q "$CODE_COMMIT"

uv venv "$ENV/venv" --python 3.10
nice -n 19 uv pip install --python "$ENV/venv/bin/python" -r scripts/envs/diarizen.txt
nice -n 19 uv pip install --python "$ENV/venv/bin/python" --no-deps -e "$ENV/src" -e "$ENV/src/pyannote-audio"

if [ "${1:-}" = "--modeles" ]; then
    "$ENV/venv/bin/python" - "$MODEL" "$MODEL_REVISION" "$EMBEDDING" "$EMBEDDING_REVISION" <<'EOF'
import sys
from huggingface_hub import hf_hub_download, snapshot_download
print("Poids :", snapshot_download(sys.argv[1], revision=sys.argv[2]))
print("Empreintes :", hf_hub_download(sys.argv[3], "pytorch_model.bin", revision=sys.argv[4]))
EOF
fi

HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 PYANNOTE_METRICS_ENABLED=false "$ENV/venv/bin/python" -W ignore -c "
import torch, pyannote.audio
from diarizen.pipelines.inference import DiariZenPipeline
print('DiariZen : import correct ; torch', torch.__version__, '; pyannote.audio', pyannote.audio.__version__,
      '; MPS', torch.backends.mps.is_available())"
