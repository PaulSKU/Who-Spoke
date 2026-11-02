"""Configuration de pytest à la racine du dépôt.

Les environnements séparés des moteurs externes (`envs/`, chantier E4) contiennent des
dépôts clonés avec leurs propres tests (DiariZen, son fork de pyannote) : ils ne font pas
partie de la suite du projet.
"""

collect_ignore_glob = ["envs/*"]
