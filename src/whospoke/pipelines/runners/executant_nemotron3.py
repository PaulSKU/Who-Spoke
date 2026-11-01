"""Exécutant de Nemotron 3 Diarization, dans envs/nemotron/ (voie transformers ; chantier E4).

Lancé par `whospoke.pipelines.nemotron3` ; configuration en premier argument (JSON) :
`modele`, `revision`, `peripherique` (cpu ou mps), `seuil`. Diarisation hors ligne
(`is_streaming=False`) du fichier entier, puis `processor.extract_speaker_dict` (sigmoïde
par trame de 10 ms au-dessus du seuil ; chevauchements conservés). Les locuteurs sont
numérotés dans l'ordre de première prise de parole.
"""

import os
import platform
import sys
import time
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import protocole  # noqa: E402

protocole.disable_telemetry()


def read_wav(path):
    import numpy as np

    with wave.open(path) as handle:
        if handle.getframerate() != 16000 or handle.getnchannels() != 1 or handle.getsampwidth() != 2:
            raise ValueError(f"{path} : WAV PCM 16 bits, 16 kHz, mono attendu")
        frames = handle.readframes(handle.getnframes())
    return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0


def load(config):
    import torch
    import transformers
    from transformers import AutoModelForAudioFrameClassification, AutoProcessor

    device = config.get("peripherique", "cpu")
    revision = config["revision"]
    processor = AutoProcessor.from_pretrained(config["modele"], revision=revision)
    model = AutoModelForAudioFrameClassification.from_pretrained(config["modele"], revision=revision)
    model.to(device).eval()
    state = {"torch": torch, "processor": processor, "model": model, "device": device,
             "seuil": float(config.get("seuil", 0.5))}
    infos = {"versions": {"python": platform.python_version(), "torch": torch.__version__,
                          "transformers": transformers.__version__},
             "configuration": {"peripherique": device, "seuil": state["seuil"],
                               "locuteurs_max": model.config.head_config.num_speakers,
                               "trame_s": processor.feature_extractor.hop_length / processor.feature_extractor.sampling_rate,
                               "mode": "hors ligne (is_streaming=False)"}}
    return state, infos


def handle(state, request):
    torch, processor, model = state["torch"], state["processor"], state["model"]
    start = time.perf_counter()
    audio = read_wav(request["entree"])
    inputs = processor(audio, sampling_rate=16000).to(state["device"], dtype=model.dtype)
    features_s = time.perf_counter() - start
    start = time.perf_counter()
    with torch.inference_mode():
        logits = model(**inputs).logits
    if state["device"] == "mps":
        torch.mps.synchronize()
    inference_s = time.perf_counter() - start
    segments = processor.extract_speaker_dict(logits, inputs.attention_mask, threshold=state["seuil"])[0]
    protocole.write_rttm(request["sortie"], request["uri"],
                         [(s["Start"], s["End"], f"SPK_{s['Speaker']:02d}") for s in segments])
    return {"durees": {"analyse": round(features_s, 3), "detection": round(inference_s, 3)},
            "n_trames": int(logits.shape[1])}


if __name__ == "__main__":
    protocole.serve(load, handle)
