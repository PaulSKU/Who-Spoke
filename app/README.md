# Application de démonstration (D17)

## Lancement

```bash
uv run python -m app.app             # moteurs réels (modèles chargés au premier usage)
uv run python -m app.app --factice   # moteur factice : aucune inférence
```

Puis ouvrir http://127.0.0.1:7860 (serveur local uniquement, pas de lien public). Options : `--port`, `--factice-max-s` (durée maximale simulée d'une analyse en mode factice).

## Onglet « Analyse »

| Élément | Où |
|---|---|
| Normalisation de tout audio déposé en WAV 16 kHz mono (D15, D16) | `whospoke.audio.normalize`, dans un dossier de travail temporaire hors du dépôt |
| Moteurs et expérience source de chaque moteur (paramètres, θ retenu, RTF) | `app/moteurs.py` |
| Temps restant estimé à partir du RTF mesuré (`results/leaderboard.csv`) | `app/temps.py` |
| Statistiques par locuteur, renommage, exports RTTM et JSON, DER face à une référence | `app/sortie.py` |
| Forme d'onde, timeline par locuteur, écoute d'un segment au clic | `app/static/visualiseur.js` et `.css` |
| Thème (teintes neutres, polices système) et feuille de style | `app/theme.py`, `app/static/interface.css` |

## Principes d'affichage

L'interface est monochrome : la couleur est réservée aux locuteurs (palette catégorielle à huit teintes en ordre fixe, gris au-delà). Les polices sont celles du système, aucun fichier de police n'est chargé. Les ombres sont en couches légères. Le mouvement se limite au retour d'appui des boutons, à la barre d'avancement et à l'indicateur de l'étape en cours, et il est coupé avec `prefers-reduced-motion`. L'état de chaque étape est écrit en toutes lettres (« terminé », « 45 % », « en attente »), le focus clavier est visible partout, et les noms saisis sont échappés avant affichage. Ces principes sont tirés des skills frontend-design, beautiful-shadows, emil-design-eng, apple-design, interaction-design, accessibility et unslop, lus et non installés.

Moteur factice : il respecte le contrat de `src/whospoke/pipelines/base.py`, simule les étapes du moteur choisi, puis renvoie le RTTM produit par l'expérience source pour le fichier déposé, reconnu à son nom (`007a_ECRH.mp3` ou `summre__007a_ECRH.wav` pour `summre__007a_ECRH`), coupé à la durée de l'audio. La contrainte sur le nombre de locuteurs est ignorée, et l'interface le signale.

## Bibliothèques JavaScript embarquées

| Bibliothèque | Version | Fichiers | Source et contrôle |
|---|---|---|---|
| wavesurfer.js (BSD-3-Clause) | 7.12.12 (publiée le 10/09/2026) | `static/wavesurfer-7.12.12/wavesurfer.min.js`, `regions.min.js`, `LICENSE` | Archive npm `wavesurfer.js-7.12.12.tgz`, intégrité sha512 vérifiée contre le registre ; aucune URL dans les fichiers copiés |

SHA-256 : `wavesurfer.min.js` cb9fff59e7ce18932fab801771589ca48bc0362db82218d86cf05f5b60f0bc5e ; `regions.min.js` fa36e84bd0f22e332e5ac4d0264967e350375fa00418bc18d095bb0e0116e16d.

## Contrôle hors ligne (01/11/2026, Gradio 6.31.0, mode factice)

Contrôle refait après la refonte visuelle du même jour : 88 requêtes, toutes vers `http://127.0.0.1:7860`, plus une icône SVG intégrée en `data:` (sans réseau) ; aucun fichier de police chargé (polices système). Côté serveur, relevés identiques à ceux du tableau ci-dessous, sur neuf sessions.

| Côté | Méthode | Résultat |
|---|---|---|
| Navigateur | Liste des requêtes de la page (outil réseau du navigateur et `performance.getEntriesByType`) pendant un parcours complet : chargement, dépôt d'un mp3 et d'une référence, analyse, écoute de segments, renommage, exports | Plus d'une centaine de requêtes, toutes vers `http://127.0.0.1:7860`. Polices du thème (Source Sans Pro, IBM Plex Mono) servies par Gradio depuis `/static/fonts/` ; wavesurfer.js depuis `app/static/` ; audio lu par requêtes partielles (206) |
| Serveur | Hook d'audit Python (`sys.addaudithook`) sur `socket.connect`, `socket.getaddrinfo`, `socket.sendto`, `socket.gethostbyname`, sur trois sessions de l'application | Seules connexions : `127.0.0.1:7860` (vérification de démarrage de Gradio), deux par session |

Réglages qui y contribuent : `GRADIO_ANALYTICS_ENABLED=False` posé avant l'import de Gradio, thème à polices système uniquement (`app/theme.py`), `share=False`, `ssr_mode=False`, `mcp_server=False`.

Non couvert : le chargement des modèles réels (pyannote, ECAPA, WeSpeaker) n'a pas été exercé, aucune inférence n'étant permise pendant le lot d'expériences en cours. Il peut interroger le Hub Hugging Face même quand les modèles sont en cache, sauf avec `HF_HUB_OFFLINE=1` **[probable]**. À vérifier en mode réel.
