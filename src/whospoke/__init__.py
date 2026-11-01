"""Who Spoke? — diarisation de locuteurs.

La télémétrie des bibliothèques tierces est coupée ici, avant tout import tiers (D27) :
tout code qui importe `whospoke` en hérite (application, expériences, analyses, scripts).
"""

from whospoke.telemetry import disable_telemetry

disable_telemetry()
