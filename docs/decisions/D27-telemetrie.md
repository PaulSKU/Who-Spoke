# D27 — Télémétrie des bibliothèques tierces

Statut : actée
Date : 2026-11-01

## Contexte

Le contrôle réseau du chantier V (D26) a révélé que pyannote.audio 4 envoie par défaut de la télémétrie vers `otel.pyannote.ai`. Elle porte sur le chargement des modèles et des pipelines, la durée de chaque fichier et le nombre de locuteurs demandé, sans l'audio. `HF_HUB_OFFLINE=1` ne la coupe pas, alors que `PYANNOTE_METRICS_ENABLED=false` la coupe (contrôle refait sur quatre séances). L'application la coupe désormais, mais pas `scripts/run_experiment.py`.

Il y a deux enjeux. Le premier est la souveraineté de la démonstration (D15). Le second est la notice de consentement du corpus maison, qui exclut tout envoi à un service en ligne : la durée et le nombre de locuteurs d'un enregistrement maison en seraient des métadonnées.

## Décision

1. **Coupure partout.** Toute télémétrie connue des bibliothèques tierces est coupée au niveau du paquet `whospoke`, avant tout import tiers, pour l'application, les expériences, les analyses et les scripts. Variables concernées : `PYANNOTE_METRICS_ENABLED=false`, `HF_HUB_DISABLE_TELEMETRY=1`, `GRADIO_ANALYTICS_ENABLED=False`, et celles de tout moteur ajouté (D23 : vérifier NeMo avant son intégration). La liste est tenue dans le code et dans `docs/methode.md`.
2. **Contrôle.** Un test vérifie que ces variables sont posées. Une exécution courte d'expérience (sous-ensemble) est faite sous relevé réseau avant toute exécution sur le corpus maison (9/11) et après l'intégration de chaque nouveau moteur local. Le résultat est consigné dans le journal.
3. **Passé.** Les expériences qui ont chargé pyannote (EXP-0001, 0005, 0007, 0008, 0013 à 0015) ont probablement transmis ces métadonnées pour des corpus publics, AMI et SUMM-RE. Aucun audio n'a été envoyé, et aucun enregistrement du corpus maison n'existe encore. Le fait est consigné dans leurs `notes.md`. Les métriques ne sont pas affectées : le DER est identique avec ou sans télémétrie.

## Justification

Couper au niveau du paquet plutôt que dans chaque point d'entrée évite qu'un nouveau script l'oublie. Le contrôle réseau est la seule preuve qu'une bibliothèque ne contacte pas l'extérieur ; la documentation ne suffit pas, comme ce cas le montre.

## Liens

D15, D16, D23, D26 ; `docs/corpus-maison/formulaire-consentement.md`.
