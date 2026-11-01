"""Côté exécutant du protocole de `whospoke.pipelines.externe` (bibliothèque standard seulement).

Exécuté par l'interpréteur d'un environnement séparé, où le paquet `whospoke` n'est pas
installé : chaque exécutant importe ce module depuis son propre dossier. Compatible avec
Python 3.10 (DiariZen).
"""

import json
import os
import sys
import time
import traceback

# Imposées avant tout import tiers, en plus de celles que pose l'enveloppe (D27).
TELEMETRY_OFF = {
    "PYANNOTE_METRICS_ENABLED": "false", "HF_HUB_DISABLE_TELEMETRY": "1", "GRADIO_ANALYTICS_ENABLED": "False",
    "OTEL_SDK_DISABLED": "true", "HF_HUB_OFFLINE": "1", "WANDB_MODE": "disabled", "WANDB_DISABLED": "true",
}


def disable_telemetry():
    os.environ.update(TELEMETRY_OFF)
    os.environ.pop("ONE_LOGGER_EXPORTER_CONFIG_PATH", None)


def serve(load, handle):
    """Charge (`load(config) -> (état, infos)`), annonce, puis traite les requêtes (`handle(état, requête) -> dict`).

    La sortie standard est réservée au protocole : tout ce que les bibliothèques y écrivent
    est redirigé vers la sortie d'erreur.
    """
    channel = os.fdopen(os.dup(1), "w", buffering=1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr

    def send(message):
        channel.write(json.dumps(message) + "\n")
        channel.flush()

    config = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    start = time.perf_counter()
    try:
        state, infos = load(config)
    except Exception as error:  # remonté à l'enveloppe
        traceback.print_exc()
        send({"erreur": f"chargement : {type(error).__name__}: {error}"})
        return
    send(dict(infos, pret=True, chargement_s=round(time.perf_counter() - start, 3)))
    for line in sys.stdin:
        if not line.strip():
            continue
        request = json.loads(line)
        if request.get("commande") == "fin":
            break
        try:
            send(dict(handle(state, request), ok=True))
        except Exception as error:  # remonté à l'enveloppe, l'exécutant continue
            traceback.print_exc()
            send({"erreur": f"traitement : {type(error).__name__}: {error}"})


def write_rttm(path, uri, segments):
    """`segments` : (début, fin, locuteur) en secondes ; même écriture que pyannote (3 décimales)."""
    with open(path, "w") as handle:
        for start, end, speaker in sorted(segments):
            if end > start:
                handle.write(f"SPEAKER {uri} 1 {start:.3f} {end - start:.3f} <NA> <NA> {speaker} <NA> <NA>\n")
