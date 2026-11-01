# Application de démonstration (D17)

## Lancement

```bash
uv run python -m app.app             # moteurs réels (modèles chargés au premier usage)
uv run python -m app.app --factice   # moteur factice : aucune inférence
```

Puis ouvrir http://127.0.0.1:7860 (serveur local uniquement, pas de lien public). Options : `--port`, `--factice-max-s` (durée maximale simulée d'une analyse en mode factice). Lancer par `python -m app.app` (ou `python app/app.py`) : c'est ce point d'entrée qui fixe l'environnement ci-dessous avant tout import.

## Fonctionnement hors ligne et dossiers temporaires (D17, amendement 1)

| Point | Comportement | Où |
|---|---|---|
| Modèles | Hors mode factice, `HF_HUB_OFFLINE=1` est fixé au démarrage, avant tout import de huggingface_hub, pyannote ou speechbrain : les modèles sont lus dans le cache local, sans requête au Hub. Le cache doit donc être rempli au préalable, avec accès réseau et `HF_TOKEN` dans `.env`. Si un modèle manque, l'analyse s'arrête sur un message qui le dit et indique comment remplir le cache | `app/travail.py`, `moteurs.missing_model_message` |
| Dossiers temporaires | Chaque lancement travaille dans `<tmp>/whospoke-app/run-<pid>/` : audio normalisé, exports, et fichiers déposés ou servis par Gradio (`GRADIO_TEMP_DIR`). Le dossier est supprimé à la fermeture (sortie normale, Ctrl+C, SIGTERM). Ceux d'un lancement tué brutalement sont supprimés au lancement suivant | `app/travail.py`, `app.main` |

## Onglet « Analyse »

| Élément | Où |
|---|---|
| Normalisation de tout audio déposé en WAV 16 kHz mono (D15, D16) | `whospoke.audio.normalize`, dans un dossier de travail temporaire hors du dépôt |
| Moteurs et expérience source de chaque moteur (paramètres, θ retenu, RTF) : EXP-0009 (MFCC), EXP-0012 (ECAPA), EXP-0007 (pyannote), EXP-0015 (WeSpeaker, indisponible tant qu'elle n'existe pas ou n'a pas tourné) ; `configs/demo.yaml` au gel | `app/moteurs.py` |
| Temps restant estimé à partir du RTF mesuré (`results/leaderboard.csv`) : colonne du périphérique choisi (`rtf_cpu` en CPU, `rtf` sur le périphérique de l'expérience), plus grande valeur entre dev et test. Affichage seulement, pas une mesure au sens de D21 | `app/temps.py` |
| Statistiques par locuteur, renommage, exports RTTM et JSON, DER face à une référence (deux conditions de collar, sur toute la durée du fichier, référence coupée à cette durée ; mention « durée entière du fichier, sans UEM : non comparable aux résultats sur corpus ») | `app/sortie.py`, `app/app.py` |
| Forme d'onde, timeline par locuteur, écoute d'un segment au clic, zoom (curseur, boutons, Ctrl + molette ; jusqu'à 60 px par seconde) | `app/static/visualiseur.js` et `.css` |
| Thème (teintes neutres, polices système) et feuille de style | `app/theme.py`, `app/static/interface.css` |

## Principes d'affichage

L'interface est monochrome : la couleur est réservée aux locuteurs (palette catégorielle à huit teintes en ordre fixe, gris au-delà). Les polices sont celles du système, aucun fichier de police n'est chargé. Les ombres sont en couches légères. Le mouvement se limite au retour d'appui des boutons, à la barre d'avancement et à l'indicateur de l'étape en cours, et il est coupé avec `prefers-reduced-motion`. L'état de chaque étape est écrit en toutes lettres (« terminé », « 45 % », « en attente »), le focus clavier est visible partout, et les noms saisis sont échappés avant affichage. Ces principes sont tirés des skills frontend-design, beautiful-shadows, emil-design-eng, apple-design, interaction-design, accessibility et unslop, lus et non installés.

Moteur factice : il respecte le contrat de `src/whospoke/pipelines/base.py`, simule les étapes du moteur choisi, puis renvoie le RTTM produit par l'expérience source pour le fichier déposé, reconnu à son nom (`007a_ECRH.mp3` ou `summre__007a_ECRH.wav` pour `summre__007a_ECRH`), coupé à la durée de l'audio. La contrainte sur le nombre de locuteurs est ignorée, et l'interface le signale.

## Bibliothèques JavaScript embarquées

| Bibliothèque | Version | Fichiers | Source et contrôle |
|---|---|---|---|
| wavesurfer.js (BSD-3-Clause) | 7.12.12 (publiée le 10/09/2026) | `static/wavesurfer-7.12.12/wavesurfer.min.js`, `regions.min.js`, `LICENSE` | Archive npm `wavesurfer.js-7.12.12.tgz`, intégrité sha512 vérifiée contre le registre ; aucune URL dans les fichiers copiés |

SHA-256 : `wavesurfer.min.js` cb9fff59e7ce18932fab801771589ca48bc0362db82218d86cf05f5b60f0bc5e ; `regions.min.js` fa36e84bd0f22e332e5ac4d0264967e350375fa00418bc18d095bb0e0116e16d.

## Contrôle hors ligne (01/11/2026, Gradio 6.31.0)

Amendement 1 (même jour) : en mode réel, démarrage du serveur et requête de la page sous relevé d’audit, sans lancer d'analyse (aucun modèle chargé) : seules connexions vers `127.0.0.1`. En mode factice, parcours complet avec zoom : idem. Le chargement des modèles réels sous `HF_HUB_OFFLINE=1` reste à contrôler (voir plus bas).

Contrôle refait après la refonte visuelle du même jour : 88 requêtes, toutes vers `http://127.0.0.1:7860`, plus une icône SVG intégrée en `data:` (sans réseau) ; aucun fichier de police chargé (polices système). Côté serveur, relevés identiques à ceux du tableau ci-dessous, sur neuf sessions.

| Côté | Méthode | Résultat |
|---|---|---|
| Navigateur | Liste des requêtes de la page (outil réseau du navigateur et `performance.getEntriesByType`) pendant un parcours complet : chargement, dépôt d'un mp3 et d'une référence, analyse, écoute de segments, renommage, exports | Plus d'une centaine de requêtes, toutes vers `http://127.0.0.1:7860`. Polices du thème (Source Sans Pro, IBM Plex Mono) servies par Gradio depuis `/static/fonts/` ; wavesurfer.js depuis `app/static/` ; audio lu par requêtes partielles (206) |
| Serveur | Hook d'audit Python (`sys.addaudithook`) sur `socket.connect`, `socket.getaddrinfo`, `socket.sendto`, `socket.gethostbyname`, sur trois sessions de l'application | Seules connexions : `127.0.0.1:7860` (vérification de démarrage de Gradio), deux par session |

Réglages qui y contribuent : `GRADIO_ANALYTICS_ENABLED=False` posé avant l'import de Gradio, thème à polices système uniquement (`app/theme.py`), `share=False`, `ssr_mode=False`, `mcp_server=False`.

## Reste à vérifier avec les vrais moteurs

Aucun modèle neuronal n'a été chargé pendant le développement (lot d'expériences EXP-0013 à EXP-0015 en cours). Après le lot :

1. Suite de tests complète (`uv run pytest`), dont les fichiers qui chargent ECAPA, WeSpeaker et pyannote.
2. Analyse réelle de l'extrait de 3 min avec chacun des moteurs, sous relevé d'audit réseau : aucune connexion hors `127.0.0.1` avec `HF_HUB_OFFLINE=1` ; durée de chargement des modèles ; temps restant annoncé face au temps réel.
3. Modèle absent du cache : vider ou renommer temporairement le cache d'un modèle et vérifier que l'erreur levée est bien reconnue (`LocalEntryNotFoundError` ou `OfflineModeIsEnabled` dans la chaîne des causes) et affichée telle quelle. Points d'incertitude : pyannote peut renvoyer `None` au lieu de lever, et speechbrain (ECAPA) peut chercher ses fichiers dans `pretrained_models/` du dossier courant **[incertain]**.
4. Fourchette min–max de pyannote et nombre imposé pour la baseline sur un vrai moteur (le moteur factice les ignore).
5. Zoom au maximal sur une réunion de 30 min : fluidité et mémoire.
