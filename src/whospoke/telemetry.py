"""Coupure de la télémétrie des bibliothèques tierces (D27).

Importé par `whospoke/__init__.py` avant tout autre module du paquet : il ne doit importer
que la bibliothèque standard. Les variables sont imposées (et non posées par défaut) :
une valeur contraire de l'environnement de l'utilisateur est écrasée.

Inventaire du 01/11/2026 (recherche de télémétrie, d'analytique et d'OpenTelemetry dans
les paquets installés par uv.lock) :

- pyannote.audio 4 : traces OpenTelemetry vers otel.pyannote.ai, actives par défaut
  (chargement des modèles et des pipelines, durée de chaque fichier, nombre de locuteurs
  demandé). Variable lue à chaque envoi ; `HF_HUB_OFFLINE=1` ne la coupe pas (D27).
- huggingface_hub : statistiques d'usage envoyées au Hub ; variable lue une fois, à
  l'import de `huggingface_hub.constants`.
- gradio et gradio_client : analytique et vérification de version ; variable lue à
  chaque appel.
- FastAPI (sous Gradio) : télémétrie OpenTelemetry native, exportée seulement si un point
  d'arrivée OTLP est configuré ; coupée en plus par `OTEL_SDK_DISABLED`, qui neutralise
  aussi tout autre SDK OpenTelemetry (celui de pyannote.audio compris).
- Sans télémétrie trouvée : speechbrain, torch, torchaudio, lightning, optuna, librosa ;
  silero-vad 6.2.3 (chantier E5, ajouté à la fusion : poids lus dans le paquet, aucun
  appel réseau en usage). pyannoteai (client du service payant de pyannote) n'est jamais
  appelé.

Tout moteur ajouté (D23) complète cette liste avant son intégration, ainsi que
`docs/methode.md` §7. Les moteurs en environnement séparé (Nemotron 3, DiariZen ;
inventaire du 01/11/2026, chantier E4) reçoivent en plus les variables de
`whospoke.pipelines.externe.CHILD_ENV`.
"""

from __future__ import annotations

import os
from collections.abc import MutableMapping

TELEMETRY_OFF: dict[str, str] = {
    "PYANNOTE_METRICS_ENABLED": "false",   # pyannote.audio 4 → otel.pyannote.ai
    "HF_HUB_DISABLE_TELEMETRY": "1",       # huggingface_hub
    "GRADIO_ANALYTICS_ENABLED": "False",   # gradio, gradio_client
    "OTEL_SDK_DISABLED": "true",           # SDK OpenTelemetry (FastAPI, pyannote.audio)
}


def disable_telemetry(environ: MutableMapping[str, str] = os.environ) -> None:
    """Impose les variables de `TELEMETRY_OFF` dans `environ`."""
    environ.update(TELEMETRY_OFF)
