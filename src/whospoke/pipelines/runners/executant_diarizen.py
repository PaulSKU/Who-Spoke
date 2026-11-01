"""Exécutant de DiariZen, dans envs/diarizen/venv/ (Python 3.10 ; chantier E4).

Lancé par `whospoke.pipelines.diarizen` ; configuration en premier argument (JSON) :
`modele`, `revision`, `empreintes`, `revision_empreintes`, `peripherique` (cpu ou mps).
`DiariZenPipeline.from_pretrained` ne fige pas de révision : les fichiers sont donc lus
dans le cache à la révision demandée (`snapshot_download`, `hf_hub_download`), puis le
pipeline est construit comme le fait `from_pretrained`. Le code de DiariZen choisit CUDA
ou le CPU ; MPS est imposé ici par `pipeline.to()` seulement s'il est demandé (non
documenté par DiariZen). Le nombre de locuteurs est borné ou imposé par `min_speakers`
et `max_speakers`, que le pipeline passe au regroupement (VBx).
"""

import os
import platform
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import protocole  # noqa: E402

protocole.disable_telemetry()


def load(config):
    from pathlib import Path

    import pyannote.audio
    import torch
    from huggingface_hub import hf_hub_download, snapshot_download
    from diarizen.pipelines.inference import DiariZenPipeline

    hub = snapshot_download(config["modele"], revision=config["revision"])
    embedding = hf_hub_download(config["empreintes"], "pytorch_model.bin", revision=config["revision_empreintes"])
    pipeline = DiariZenPipeline(diarizen_hub=Path(hub).expanduser().absolute(), embedding_model=embedding)
    device = config.get("peripherique", "cpu")
    if device != "cpu":
        pipeline.to(torch.device(device))
    defaults = {"min_speakers": pipeline.min_speakers, "max_speakers": pipeline.max_speakers}
    state = {"pipeline": pipeline, "defaults": defaults}
    import toml

    parsed = toml.load(str(Path(hub) / "config.toml"))
    infos = {"versions": {"python": platform.python_version(), "torch": torch.__version__,
                          "pyannote.audio": pyannote.audio.__version__},
             "configuration": {"peripherique": device, "inference": parsed["inference"]["args"],
                               "regroupement": parsed["clustering"]["args"]}}
    return state, infos


def handle(state, request):
    pipeline, defaults = state["pipeline"], state["defaults"]
    pipeline.min_speakers = request.get("min_speakers") or defaults["min_speakers"]
    pipeline.max_speakers = request.get("max_speakers") or defaults["max_speakers"]
    start = time.perf_counter()
    result = pipeline(request["entree"], sess_name=request["uri"])
    elapsed = time.perf_counter() - start
    protocole.write_rttm(request["sortie"], request["uri"],
                         [(turn.start, turn.end, f"SPK_{int(label):02d}" if str(label).isdigit() else str(label))
                          for turn, _, label in result.itertracks(yield_label=True)])
    return {"durees": {"diarisation": round(elapsed, 3)},
            "n_locuteurs_bornes": [pipeline.min_speakers, pipeline.max_speakers]}


if __name__ == "__main__":
    protocole.serve(load, handle)
