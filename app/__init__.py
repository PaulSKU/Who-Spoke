"""Application de démonstration Gradio (D17).

`whospoke` est importé en premier : la télémétrie des bibliothèques tierces est coupée
avant que tout module de l'application n'importe gradio, pyannote ou speechbrain (D27).
"""

import whospoke  # noqa: F401
