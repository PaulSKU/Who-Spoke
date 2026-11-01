# Application de démonstration (D17)

## Lancement

```bash
uv run python -m app.app             # moteurs réels, préchauffés au démarrage
uv run python -m app.app --factice   # moteur factice : aucune inférence
```

Puis ouvrir http://127.0.0.1:7860 (serveur local uniquement, pas de lien public). Options : `--port`, `--factice-max-s` (durée maximale simulée d'une analyse en mode factice), `--sans-prechauffage` (moteurs chargés au premier usage), `--vider-cache` (vide le cache des résultats avant le lancement), `--depot` (racine du dépôt dont sont lus, en lecture seule, les expériences, les analyses, `results/leaderboard.csv`, le catalogue et les documents de `docs/` ; par défaut ce dépôt). Pendant le développement sur la branche `interface`, qui n'a pas toutes les expériences :

```bash
uv run python -m app.app --factice --depot ~/Dev/Who-Spoke
``` Lancer par `python -m app.app` (ou `python app/app.py`) : c'est ce point d'entrée qui fixe l'environnement ci-dessous avant tout import.

## Installation des modèles (D15 ; D17, amendement 1)

```bash
uv run python scripts/prefetch_models.py              # téléchargement, puis vérification hors ligne
uv run python scripts/prefetch_models.py --verifier   # vérification hors ligne seule
```

À lancer une fois, avec accès réseau et `HF_TOKEN` dans `.env` (le modèle pyannote est à accès restreint : accepter ses conditions sur le Hub au préalable). Le script place dans le cache Hugging Face (`~/.cache/huggingface/hub`, ou `$HF_HOME/hub`) :

| Dépôt | Révision | Moteurs |
|---|---|---|
| `pyannote/speaker-diarization-community-1` | `3533c8c…` (figée, D18 amendement du 01/11) | pyannote community-1 (segmentation, empreintes, PLDA) et baseline WeSpeaker : WeSpeakerResNet34 est le sous-dossier `embedding` de community-1, pas un dépôt séparé |
| `speechbrain/spkrec-ecapa-voxceleb` | `0f99f2d…` (figée) | baseline ECAPA |

La baseline MFCC n'utilise aucun modèle. Le script vérifie ensuite, dans un processus séparé avec `HF_HUB_OFFLINE=1` et un dossier courant vide, que chaque modèle se charge sans réseau et que rien n'est écrit dans le dossier de lancement. Les fichiers d'ECAPA sont lus en place dans le cache, jamais copiés dans un `pretrained_models/` du dossier courant (`whospoke.embeddings.ecapa_load_options`).

## Carte des erreurs (D26, chantier I4)

Quand une référence RTTM est déposée, avant ou après l'analyse, trois rangées, légendées « Erreurs sans collar », s'ajoutent sous les pistes des locuteurs : parole manquée (encre pleine), fausse alarme (hachures), confusion (contour). La rangée nommée porte l'identité, le motif la double. Chaque zone s'écoute au clic et se repère sur la forme d'onde, comme un segment ; l'infobulle donne le locuteur de référence et, pour une confusion, le locuteur auquel la parole a été attribuée. Les rangées sont dans le même canevas que les pistes : elles suivent le zoom. Une ligne donne la durée totale et la part de chaque type.

Calcul (`sortie.error_map`), sans collar, chevauchements comptés, sur toute la durée du fichier comme le DER affiché : rien n'est recodé. Les étapes de `DiarizationErrorRate.compute_components` de pyannote.metrics sont reprises dans le même ordre (restriction à l'UEM, étiquettes renommées, appariement hongrois `optimal_mapping`), puis `IdentificationErrorAnalysis.difference` donne le statut de chaque segment sur l'hypothèse appariée. Les durées sont cumulées comme le fait le DER (durée × nombre d'erreurs du segment). Les tests exigent l'égalité stricte (`==`, sans tolérance) des trois durées et de la parole de référence avec les composantes du DER sans collar, sur des cas construits et sur 25 paires d'annotations aléatoires, ainsi que l'égalité des parts affichées avec les cellules du tableau du DER.

## Comparaison de deux moteurs (D26, chantier I5)

Case « Comparer avec un second moteur » dans les réglages de l'onglet Analyse. Le nombre de locuteurs et le périphérique sont communs aux deux moteurs (une fourchette est refusée si l'un des deux ne la prend pas en charge ; ECAPA et WeSpeaker restent en CPU). Les deux moteurs tournent l'un après l'autre sur le même fichier normalisé :

| Élément | Comportement |
|---|---|
| Avancement | Étapes des deux moteurs, préfixées par leur nom ; temps restant cumulé (`temps.cumulative_remaining_s`) : reste du moteur en cours plus estimation complète du suivant, d'après leurs RTF mesurés ; inconnu si un RTF manque |
| Timeline | Groupes superposés dans le même canevas, donc alignés et zoomés ensemble : premier moteur (couleurs des locuteurs), second moteur et référence (gris neutre : la même couleur dans deux groupes laisserait croire au même locuteur), puis la carte des erreurs de chaque moteur. Chaque segment ou zone s'écoute et se repère sur la forme d'onde |
| Comparaison | Tableau côte à côte : nombre de locuteurs (et celui de la référence), DER sans collar et avec collar de 0,25 s si une référence est déposée, temps de calcul, RTF |
| Temps de traitement, DER | Un bloc par moteur |
| Exports | RTTM et JSON des deux moteurs, suffixés par le moteur (`007a_ECRH_pyannote-community-1.rttm`…) ; hors comparaison, au nom du fichier seul |
| Statistiques et renommage | Premier moteur seulement |

La référence, quand elle est déposée, est aussi affichée comme groupe de la timeline en analyse simple.

## Onglet « Pipeline » (D17, D26 chantier I1)

Consultation en lecture seule de la configuration de chaque moteur, générée à l'ouverture, jamais rédigée à la main (`app/pipeline.py`, `app/static/pipeline.js`) :

| Contenu | Source |
|---|---|
| Réglages, valeurs, origine (expérience, défaut du moteur, modèle pré-entraîné, code), par étape | `configuration_effective` de `execution_<périphérique>.json` de l'expérience source du moteur (exécution principale) |
| Libellé, rôle de l'étape, effet, composantes du DER, décision | `src/whospoke/pipelines/catalogue.yaml` de la même racine de dépôt |
| Étape Normalisation, commune | `whospoke.audio` (fréquence d'échantillonnage) ; canaux, format et entrée en mémoire : propriétés du code de `normalize` (D15, D16) |
| Étape Évaluation, séparée et marquée « mesure seulement » | `whospoke.evaluation.metrics` (collars et `skip_overlap` lus sur les métriques instanciées), `evaluation.references` du config.yaml de l'expérience, protocole §2 et §4 |
| En-tête | expérience, périphérique, date, commit et versions de l'exécution |

Révision des modèles : lue dans la valeur d'un réglage `*.modele` au format `dépôt@commit (architecture)`, ou dans un réglage `*.revision` ; à défaut, « révision non consignée » (cas de pyannote jusqu'au chantier V, D18 amendement du 01/11). ECAPA l'affiche déjà (`0f99f2d`).

Écarts signalés en tête de page : réglages de la configuration absents du catalogue, entrées du catalogue absentes de la configuration, étapes différentes. Constat au 01/11 (dépôt principal) : aucun pour pyannote (EXP-0007) ni ECAPA (EXP-0012) ; pour la baseline MFCC (EXP-0009), les cinq réglages des empreintes neuronales (`empreintes.*`, `normalisation`), que le catalogue du moteur « baseline » décrit pour ses variantes ECAPA et WeSpeaker. WeSpeaker : page indisponible tant qu'EXP-0015 n'a pas été exécutée.

La maquette du 27/10 (`docs/maquettes/pipeline-maquette-2026-10-27.html`) a servi pour le contenu ; son style et ses polices distantes ne sont pas repris.

## Onglet « Avancement » (D26, chantier I2)

Récapitulatif de la conduite du projet, régénéré à chaque ouverture de l'onglet, en lecture seule sous la racine `--depot` (`app/avancement.py`) :

| Section | Source |
|---|---|
| Frise des expériences et analyses, dans l'ordre chronologique (date de `results_*.json` ou d'`execution.json`) : identifiant, question, corpus, DER test puis dev dans les deux conditions de collar, verdict, décisions, bouton « notes.md » qui affiche les notes dans la page | En-tête YAML de `notes.md` (D26 §2 : `id`, `question`, `verdict`, `decisions`), `results_<corpus>_<partition>.json` |
| Décomposition de l'erreur par les oracles : EXP-0002 à EXP-0006, puis EXP-0010 et EXP-0011 ; DER test et ses trois composantes, écart avec l'expérience de référence | `results_*.json` (`reference`, `variable_modifiee`, `systeme`) |
| Décisions et statuts, amendements compris | D1 à D15 : tableau du §0 et phrase « Statut » de `docs/cadrage.md` (points restés ouverts compris) ; D16 et suivantes : ligne `Statut :` de chaque fiche et de ses amendements (« statut non indiqué » à défaut) |
| File d'attente de D23, avec un « État constaté » calculé : expériences citées créées ou ayant des résultats, fiches citées présentes ou absentes | Tableau « File d'attente » de `docs/planning.md`, dossiers d'expériences, fiches |

Contrôle du 01/11 sur le dépôt principal, après l'ajout des en-têtes et des lignes « Statut » d'amendement : 16 en-têtes lus sans problème, aucun « en-tête manquant », aucun « statut non indiqué » ; restent signalés les fiches D24 et D25 absentes (file D23) et l'absence de DER pour EXP-0015, non exécutée. Un `notes.md` sans en-tête s'affiche « en-tête manquant », un en-tête mal formé « en-tête illisible » ; un `id` qui ne correspond pas au dossier ou un verdict hors de la liste de D26 §2 sont signalés à côté de la question. Un résultat portant un bloc `invalidee` est marqué « invalidée ». 

## Glossaire intégré (D26, chantier I3)

Onglet Glossaire généré depuis `docs/glossaire.md` de la racine `--depot` (`app/glossaire.py`) : introduction, index des termes, parties, une ancre par terme (`gl-<terme sans accents>`, par exemple `gl-parole-manquee`) ; les définitions renvoient entre elles, jamais à elles-mêmes.

Renvois dans les onglets Analyse (titres, panneau d'avancement, tableaux des locuteurs, des temps et du DER), Pipeline et Avancement : chaque terme du glossaire est lié à sa définition, à sa première occurrence dans chaque bloc (paragraphe, cellule, élément de liste, titre). Un clic ouvre l'onglet Glossaire sur la définition (`app/static/glossaire.js`) ; le survol l'affiche en infobulle. Correspondance automatique, sans liste tenue à la main :

| Règle | Exemple |
|---|---|
| Variantes d'un terme : terme français, termes anglais en italique, éléments entre parenthèses contenant une majuscule, formes de la ligne facultative « Formes courtes : a, b, c. » sous le titre de l'entrée (D26, amendement du 01/11) | « VAD » renvoie à « Détection d'activité vocale », « Sortformer » à « Bout en bout », « Confusion » à « Confusion de locuteur » ; « (système) » dans « Hybride (système) » n'est pas une variante ; une forme revendiquée par deux entrées renvoie à la première et est signalée (`Linker.conflicts`) |
| Mot entier seulement, jamais dans un identifiant ou une expression | rien dans `der_c0`, `clustering.threshold`, `VBxClustering`, `collar=0.5` ; « DER sans collar » donne deux liens, DER et collar |
| Pluriel accepté mot à mot | « Empreintes vocales », « chevauchements » |
| Plus long d'abord à une même position | « Parole manquée » plutôt que « Parole » si les deux sont des termes |
| Sigles sensibles à la casse, autres termes non | « DER » oui, « der » non ; « Regroupement » et « regroupement » oui |
| Jamais dans du code, un bouton, un lien ni un attribut | les boutons d'étape de l'onglet Pipeline et les libellés des composants Gradio (listes, cases) ne sont pas liés |

Limites. Les libellés des composants Gradio (« Moteur », « Nombre de locuteurs »…) et la timeline dessinée en JavaScript ne portent pas de renvois. Une forme abrégée n'est reconnue que si elle figure dans la ligne « Formes courtes » de son entrée.

## Fonctionnement hors ligne et dossiers temporaires (D17, amendement 1)

| Point | Comportement | Où |
|---|---|---|
| Modèles | Hors mode factice, `HF_HUB_OFFLINE=1` est fixé au démarrage, avant tout import de huggingface_hub, pyannote ou speechbrain : les modèles sont lus dans le cache local, sans requête au Hub. Le cache doit donc être rempli au préalable, une fois, avec accès réseau et `HF_TOKEN` dans `.env` : `uv run python scripts/prefetch_models.py` (voir ci-dessous). Si un modèle manque, l'analyse s'arrête sur un message qui renvoie à ce script | `app/travail.py`, `moteurs.missing_model_message` |
| Dossiers temporaires | Chaque lancement travaille dans `<tmp>/whospoke-app/run-<pid>/` : audio normalisé, exports, et fichiers déposés ou servis par Gradio (`GRADIO_TEMP_DIR`). Le dossier est supprimé à la fermeture (sortie normale, Ctrl+C, SIGTERM). Ceux d'un lancement tué brutalement sont supprimés au lancement suivant | `app/travail.py`, `app.main` |

## Onglet « Analyse »

| Élément | Où |
|---|---|
| Normalisation de tout audio déposé en WAV 16 kHz mono (D15, D16) | `whospoke.audio.normalize`, dans un dossier de travail temporaire hors du dépôt |
| Moteurs et expérience source de chaque moteur (paramètres, θ retenu, RTF) : EXP-0009 (MFCC), EXP-0012 (ECAPA), EXP-0007 (pyannote), EXP-0015 (WeSpeaker, indisponible tant qu'elle n'existe pas ou n'a pas tourné) ; `configs/demo.yaml` au gel | `app/moteurs.py` |
| Temps annoncé en fourchette (D17, amendement 2) : de surcoût + RTF × durée à surcoût + 1,3 × RTF × durée, avant le lancement (sous le bouton « Analyser ») et pendant l'analyse. RTF mesuré (`results/leaderboard.csv`) : colonne du périphérique choisi (`rtf_cpu` en CPU, `rtf` sur le périphérique de l'expérience), plus grande valeur entre dev et test. Surcoût fixe du premier appel après chargement, daté, par moteur et périphérique (`moteurs.FIXED_OVERHEAD`, `scripts/measure_overhead.py`), compté seulement si le moteur est froid. Pendant l'analyse, recalage sur la vitesse observée dans l'étape la plus longue (voir ci-dessous). Affichage seulement, pas une mesure au sens de D21 | `app/temps.py`, `app/moteurs.py` |
| Statistiques par locuteur, renommage, exports RTTM et JSON, DER face à une référence (deux conditions de collar, sur toute la durée du fichier, référence coupée à cette durée ; mention « durée entière du fichier, sans UEM : non comparable aux résultats sur corpus ») | `app/sortie.py`, `app/app.py` |
| Forme d'onde neutre (D26) : seul le segment sélectionné, dernier cliqué, y est mis en évidence par une bande d'encre et entouré sur sa piste ; timeline par locuteur, écoute d'un segment au clic, zoom (curseur, boutons, Ctrl + molette ; jusqu'à 60 px par seconde) | `app/static/visualiseur.js` et `.css` |
| Thème (teintes neutres, polices système) et feuille de style | `app/theme.py`, `app/static/interface.css` |
| Onglet Pipeline | `app/pipeline.py`, `app/static/pipeline.js` |
| Onglet Avancement | `app/avancement.py` |
| Onglet Glossaire et renvois | `app/glossaire.py`, `app/static/glossaire.js` |

## Principes d'affichage

L'interface est monochrome : la couleur est réservée aux locuteurs (palette catégorielle à huit teintes en ordre fixe, gris au-delà). Les polices sont celles du système, aucun fichier de police n'est chargé. Les ombres sont en couches légères. Le mouvement se limite au retour d'appui des boutons, à la barre d'avancement et à l'indicateur de l'étape en cours, et il est coupé avec `prefers-reduced-motion`. L'état de chaque étape est écrit en toutes lettres (« terminé », « 45 % », « en attente »), le focus clavier est visible partout, et les noms saisis sont échappés avant affichage. Ces principes sont tirés des skills frontend-design, beautiful-shadows, emil-design-eng, apple-design, interaction-design, accessibility et unslop, lus et non installés.

### Palette des locuteurs : vérification (01/11/2026)

Huit teintes en ordre fixe (palette validée de la skill dataviz), une variante par mode ; à partir du 9e locuteur, un gris neutre unique. Les couleurs sont attribuées dans l'ordre de première prise de parole. Écarts mesurés par le validateur de la skill (OKLab ΔE × 100, simulation de Machado 2009 à sévérité 1), sur le fond des pistes (`#f0f0ed` en clair, `#232428` en sombre) :

| Condition | Clair | Sombre |
|---|---|---|
| Paires adjacentes (pistes voisines), daltonisme rouge-vert | pire ΔE 9,1 : réussi (cible ≥ 8) | pire ΔE 8,4 : réussi |
| Paires adjacentes, vision normale | pire ΔE 19,6 : réussi (plancher 15) | pire ΔE 19,3 : réussi |
| Toutes les paires, deutéranopie | pire ΔE 4,5 (1↔7) ; sous 8 : 1↔7, 2↔8, 3↔5, 3↔8 | pire ΔE 1,6 (3↔5, quasi identiques) ; sous 8 : 7 paires |
| Toutes les paires, vision normale | pire ΔE 7,1 (2↔8, orange et rouge) | pire ΔE 7,1 (2↔8) |
| Contraste sur la piste | 4 teintes sous 3:1 (2, 3, 4, 5) : étiquettes requises | toutes ≥ 3:1 |

Pire paire en deutéranopie selon le nombre de locuteurs (toutes paires) : clair 31,7 (2), 9,2 (3 et 4), 6,1 (5 et 6), 4,5 (7 et 8) ; sombre 28,6 (2), 9,4 (3), 4,8 (4), 1,6 (5 à 8).

Conclusion. La couleur seule ne distingue toutes les paires que **jusqu'à 3 locuteurs** (deutéranopie comprise) ; au-delà, l'identité repose sur l'encodage secondaire : une piste par locuteur, toujours dans le même ordre et étiquetée par son nom (les pistes voisines restent distinguables, c'est le cas que la palette garantit), pastille accompagnée du nom dans le tableau, nom et horaires au survol de chaque segment. En conséquence (D26, « Couleurs »), la forme d'onde est neutre : les teintes par locuteur qu'elle portait, qui ne reposaient que sur la couleur, sont retirées ; seul le segment sélectionné y est mis en évidence.

Au-delà de 8 locuteurs : tous les suivants reçoivent le même gris (`#8a8985` en clair, `#a3a29c` en sombre). Ils sont indiscernables entre eux par la couleur et ne se distinguent que par leur piste, leur nom et le survol ; en deutéranopie, ce gris est en outre proche de l'aqua (3) en clair (ΔE 4,8). Aucune teinte n'est générée en plus, conformément à la règle de la palette (pas de 9e teinte inventée).

Moteur factice : il respecte le contrat de `src/whospoke/pipelines/base.py`, simule les étapes du moteur choisi, puis renvoie le RTTM produit par l'expérience source pour le fichier déposé, reconnu à son nom (`007a_ECRH.mp3` ou `summre__007a_ECRH.wav` pour `summre__007a_ECRH`), coupé à la durée de l'audio. La contrainte sur le nombre de locuteurs est ignorée, et l'interface le signale.

## Bibliothèques JavaScript embarquées

| Bibliothèque | Version | Fichiers | Source et contrôle |
|---|---|---|---|
| wavesurfer.js (BSD-3-Clause) | 7.12.12 (publiée le 10/09/2026) | `static/wavesurfer-7.12.12/wavesurfer.min.js`, `regions.min.js`, `minimap.min.js` (ajouté le 01/11 au chantier B3), `LICENSE` | Archive npm `wavesurfer.js-7.12.12.tgz`, intégrité sha512 vérifiée contre le registre (de nouveau le 01/11 pour le greffon Minimap : mêmes empreintes pour les fichiers déjà embarqués) ; licence BSD-3-Clause du paquet, couvrant les greffons ; aucune URL dans les fichiers copiés |

SHA-256 : `wavesurfer.min.js` cb9fff59e7ce18932fab801771589ca48bc0362db82218d86cf05f5b60f0bc5e ; `regions.min.js` fa36e84bd0f22e332e5ac4d0264967e350375fa00418bc18d095bb0e0116e16d ; `minimap.min.js` f671920e50c1bd6e53b381c6b996b06952df3336e062f96f5472a6ecdce3fa73 (le greffon embarque sa propre copie de wavesurfer pour la forme d'onde miniature).

## Contrôle hors ligne (01/11/2026, Gradio 6.31.0)

Amendement 1 (même jour) : en mode réel, démarrage du serveur et requête de la page sous relevé d’audit, sans lancer d'analyse (aucun modèle chargé) : seules connexions vers `127.0.0.1`. En mode factice, parcours complet avec zoom : idem. Le chargement des modèles réels sous `HF_HUB_OFFLINE=1` reste à contrôler (voir plus bas).

Contrôle refait après la refonte visuelle du même jour : 88 requêtes, toutes vers `http://127.0.0.1:7860`, plus une icône SVG intégrée en `data:` (sans réseau) ; aucun fichier de police chargé (polices système). Côté serveur, relevés identiques à ceux du tableau ci-dessous, sur neuf sessions.

| Côté | Méthode | Résultat |
|---|---|---|
| Navigateur | Liste des requêtes de la page (outil réseau du navigateur et `performance.getEntriesByType`) pendant un parcours complet : chargement, dépôt d'un mp3 et d'une référence, analyse, écoute de segments, renommage, exports | Plus d'une centaine de requêtes, toutes vers `http://127.0.0.1:7860`. Polices du thème (Source Sans Pro, IBM Plex Mono) servies par Gradio depuis `/static/fonts/` ; wavesurfer.js depuis `app/static/` ; audio lu par requêtes partielles (206) |
| Serveur | Hook d'audit Python (`sys.addaudithook`) sur `socket.connect`, `socket.getaddrinfo`, `socket.sendto`, `socket.gethostbyname`, sur trois sessions de l'application | Seules connexions : `127.0.0.1:7860` (vérification de démarrage de Gradio), deux par session |

Réglages qui y contribuent : `PYANNOTE_METRICS_ENABLED=false` (télémétrie de pyannote.audio, constatée au chantier V), `GRADIO_ANALYTICS_ENABLED=False` posé avant l'import de Gradio, thème à polices système uniquement (`app/theme.py`), `share=False`, `ssr_mode=False`, `mcp_server=False`.

## Vérification avec les vrais moteurs (chantier V de D26, 01/11/2026)

Branche `interface` fusionnée dans `main` ; `uv run pytest` complet : 258 réussis, plus le test lent de reproduction d'EXP-0001, réussi avant et après le figeage de pyannote. Machine sur secteur, aucune expérience en cours. Application réelle lancée par `uv run python -m app.app`, sous relevé d'audit Python des connexions (`socket.connect`, `socket.getaddrinfo`), navigateur contrôlé par `performance.getEntriesByType`.

| Contrôle | Résultat |
|---|---|
| Révisions | Un seul instantané de community-1 dans le cache (`3533c8c…`, `refs/main` y pointe) ; pyannote figé à ce commit ; `configuration_effective` consigne `…@3533c8c…` pour la segmentation, les empreintes et la PLDA de pyannote et pour WeSpeaker, `…@0f99f2d…` pour ECAPA. Les exécutions antérieures (EXP-0001, EXP-0007) ne consignent pas de révision : l'onglet Pipeline affiche pour pyannote « révision non consignée » jusqu'à la prochaine expérience |
| `scripts/prefetch_models.py` | Réussi : deux dépôts aux révisions figées, puis chargement des trois modèles hors ligne depuis un dossier vide, sans `pretrained_models/` |
| Réseau, première séance | **Une connexion sortante** : `otel.pyannote.ai:443` (51.45.22.112), télémétrie OpenTelemetry de pyannote.audio 4, active par défaut (chargement des modèles et pipelines, durée des fichiers, nombre de locuteurs demandé ; pas d'audio). `HF_HUB_OFFLINE=1` ne la coupe pas. Corrigé : `PYANNOTE_METRICS_ENABLED=false` posé au lancement (`app/travail.py`) et dans la vérification du préchargement |
| Réseau, après correction | Quatre séances (pyannote, WeSpeaker, modèles absents, réunion de 27 min) : aucune connexion hors `127.0.0.1` côté serveur ; navigateur : toutes les requêtes vers `127.0.0.1:7860` |
| Temps restant, extrait de 3 min | pyannote (MPS) : annoncé 9 s, réel 12,4 s à froid, 11,1 s à chaud ; MFCC : 0,2 s, réel 2,4 s au premier appel puis 0,13 s ; ECAPA : 2,9 s, réel 3,2 puis 3,8 s ; WeSpeaker : 3,5 s, réel 4,3 puis 4,5 s. Le RTF des expériences exclut un préchauffage et porte sur des fichiers longs : sur 3 min, l'annonce sous-estime de 20 à 30 % (et beaucoup plus au tout premier appel de la baseline MFCC) |
| Temps restant, réunion de 26 min 48 s (pyannote, MPS) | Annoncé 82 s, réel 95 s (RTF 0,0591 contre 0,0512 mesuré) |
| Fourchette de pyannote | Automatique : 3 locuteurs (4 dans la référence) ; fourchette 4–6 : 4 locuteurs ; DER sans collar 11,63 → 14,06 %, JER 34,70 → 27,93 % |
| Nombre imposé de la baseline MFCC | Automatique : 2 locuteurs ; imposé 4 : 4 locuteurs |
| Modèle absent du cache | Cache d'ECAPA, puis de community-1, renommés temporairement : dans les deux cas, message « Modèle de … absent du cache local … uv run python scripts/prefetch_models.py » ; pyannote lève bien une erreur reconnue (l'incertitude est levée). Caches restaurés, préchargement revérifié hors ligne |
| Zoom maximal, réunion de 26 min 48 s, avec référence | 3 181 segments dont 1 678 zones d'erreur ; largeur 96 465 px (60 px/s), 4 canevas seulement (rendu paresseux de wavesurfer) ; passage au zoom maximal en 66 ms ; défilement de bout en bout en 120 pas : 11,4 ms par image en médiane, 16,7 ms au 95e centile, 42,7 ms au plus ; lecture avec suivi : 12,6 ms en médiane, 18,7 ms au 95e centile ; tas JavaScript stable autour de 28 Mo ; pistes et forme d'onde restent alignées |

Points relevés pendant la vérification : après une erreur (modèle absent), le panneau d'avancement reste sur l'étape en cours au lieu d'indiquer l'échec ; l'erreur s'affiche dans une notification. Corrigé le même jour : le panneau passe à l'état « échec » sur l'étape en cause, avec le message dans le panneau (voir ci-dessous).

## Temps restant avec surcoût fixe, et panneau après erreur (01/11/2026)

Surcoût fixe mesuré par `scripts/measure_overhead.py mesure` : 3 processus neufs par moteur, chacun charge le moteur comme l'application puis traite 60 s de `summre__004c_PAPH` (dev, à partir de 600 s) ; surcoût = premier appel − RTF × 60 s. Sur secteur, charge moyenne de la machine de 2,7 à 3,8 (8,8 au plus pendant pyannote en CPU).

| Moteur (périphérique) | RTF (source) | Premiers appels (s) | Second appel (s) | Surcoût retenu |
|---|---|---|---|---|
| Baseline MFCC (CPU) | 0,0009 (EXP-0009) | 1,86 ; 1,40 ; 1,40 | 0,02 à 0,03 | 1,5 s |
| Baseline ECAPA (CPU) | 0,0163 (EXP-0012) | 2,71 ; 2,03 ; 2,09 | 1,07 à 1,49 | 1,3 s |
| Baseline WeSpeaker (CPU) | 0,0194 (EXP-0015) | 2,84 ; 3,18 ; 2,28 | 1,26 à 1,54 | 1,6 s |
| pyannote community-1 (MPS) | 0,0512 (EXP-0007) | 4,28 ; 3,95 ; 4,24 | 2,64 à 2,97 | 1,1 s |
| pyannote community-1 (CPU) | 0,783 (EXP-0007) | 49,65 ; 56,75 ; 54,31 | 49,84 à 67,16 | 6,6 s (2,7 à 9,8 selon le lancement) |

Vérification (`scripts/measure_overhead.py verification`) : un processus neuf par moteur et par fichier, premier appel après chargement, charge moyenne de 5,8 à 9,3 (application Claude et indexation de macOS actives).

| Fichier | Moteur (périphérique) | Annoncé sans surcoût | Annoncé | Réel | Écart (avant → après) |
|---|---|---|---|---|---|
| Extrait de 3 min (mp3 stéréo 44,1 kHz normalisé) | MFCC (CPU) | 0,2 s | 1,7 s | 2,2 s | −93 % → −24 % |
| | ECAPA (CPU) | 2,9 s | 4,2 s | 4,7 s | −38 % → −11 % |
| | WeSpeaker (CPU) | 3,5 s | 5,1 s | 8,0 s | −56 % → −36 % |
| | pyannote (MPS) | 9,2 s | 10,3 s | 11,8 s | −22 % → −13 % |
| | pyannote (CPU) | 140,9 s | 147,5 s | 156,6 s | −10 % → −6 % |
| Réunion de 26 min 48 s (`summre__036c_EAPH`) | MFCC (CPU) | 1,4 s | 2,9 s | 3,6 s | −60 % → −18 % |
| | ECAPA (CPU) | 26,2 s | 27,5 s | 28,9 s | −9 % → −5 % |
| | WeSpeaker (CPU) | 31,2 s | 32,8 s | 36,3 s | −14 % → −10 % |
| | pyannote (MPS) | 82,3 s | 83,4 s | 101,6 s | −19 % → −18 % |

L'annonce reste inférieure au réel dans tous les cas. Sur la réunion, l'écart de pyannote ne vient pas d'un coût fixe : le RTF obtenu est 0,0632, contre 0,0512 dans EXP-0007 (29/10). L'exécution de contrôle de D27 (même code, mêmes versions) donne aussi 0,059 sur deux réunions de dev, avec des RTTM identiques à l'octet à ceux d'EXP-0007 : le calcul est le même, la machine est plus lente ce jour-là. pyannote en CPU sur la réunion n'a pas été vérifié (environ 25 min de calcul).

Panneau après erreur, vérifié dans le navigateur en mode factice : fichier `.wav` valide sans RTTM source → « Échec : Segmentation locale », normalisation et chargement « terminé », message dans le panneau ; fichier texte nommé `.mp3` → « Échec : Normalisation audio (ffmpeg) » avec le message de ffmpeg. Dans les deux cas la notification de Gradio s'affiche aussi.

## Finitions et démonstration (planning v2.0, chantiers B1 et B2, 01/11/2026)

### Finitions (audit R-U1, R-U5)

| Point | Comportement | Où |
|---|---|---|
| Zones de dépôt | « Déposez le fichier ici – ou – cliquez pour le choisir », quelle que soit la langue du navigateur : clés `upload_text.drop_file`, `upload_text.click_to_upload` et `common.or` redéfinies par `gr.I18n` pour les 27 langues de Gradio 6.3 | `theme.UPLOAD_TEXT`, `app.main` |
| Pied de page de Gradio | Masqué (`footer_links=[]`) ; le thème clair ou sombre suit celui du système | `app.main` |
| Zone de la référence | Même hauteur que celle de l'audio (150 px) : le texte n'est plus rogné | `app.build_app` |
| Intitulés de la timeline | Les rangées d'intitulé (moteur, référence, erreurs) sont opaques et passent au-dessus de la tête de lecture, qui s'interrompt à leur hauteur | `visualiseur.css` (`.wsp-spacer`) |
| Dernière graduation | Alignée à droite quand elle touche le bord : « 5:00 » n'est plus rogné | `visualiseur.js` (`drawAxis`), `.wsp-tick-end` |
| Étapes de l'avancement | Lues en colonne (de haut en bas, puis colonne suivante), dans l'ordre du pipeline | `interface.css` (`.st-steps`) |
| Après l'analyse (R-U1) | Colonne des réglages masquée ; bandeau pleine largeur (fichier, durée, moteurs, nombre de locuteurs, périphérique) avec le bouton « Nouvelle analyse », qui rouvre les réglages ; timeline et résultats en pleine largeur | `app.build_app`, `_band_html` |
| 375 px | Gouttière de 16 px et onglets resserrés par `clamp()` : Gradio préfixe les sélecteurs placés dans un `@media`, la règle mobile de `.gradio-container` ne s'appliquait donc pas. Tableaux et timeline à largeur intrinsèque nulle (`width: 0; min-width: 100%`) : ils défilent dans leur cadre au lieu d'élargir la page. Au-dessous d'environ 380 px, Gradio range les onglets en trop dans son menu « … » | `interface.css`, `visualiseur.css` |

L'onglet Avancement lit le nouveau tableau « File d'attente de la piste A » de `docs/planning.md` (colonnes Rang, Contenu, Calcul estimé, Prérequis). L'« État constaté » ne retient plus que les fiches citées, présentes ou absentes : les expériences citées le sont comme références (EXP-0007 à reproduire en A1), les compter « avec résultats » aurait fait croire le rang fait.

### Préchauffage et indicateur « moteurs prêts » (audit R-D2)

Au lancement, un fil dédié charge chaque moteur disponible sur le périphérique de « auto » (pyannote d'abord, puis les baselines en CPU) et fait un appel à blanc sur 20 s de signal synthétique (deux voix harmoniques alternées, modulées à 4 Hz) : aucun fichier audio n'est lu. L'en-tête affiche « Préchauffage des moteurs (k/n) : moteur… », puis « Moteurs prêts », ou « Moteurs prêts, sauf X » si un appel a échoué (raison au survol ; le moteur reste chargé au premier usage). Une minuterie de 1 s rafraîchit l'indicateur et la durée annoncée, puis s'arrête. Une analyse lancée pendant le préchauffage attend la fin du moteur en cours. En mode factice, le préchauffage est simulé (0,8 s par moteur). **Le préchauffage réel n'a pas été exécuté** (aucun modèle chargé sur cette branche) : il est à vérifier à la fusion.

### Durée annoncée et recalage (D17, amendement 2)

Dès le dépôt, le fichier est normalisé (la normalisation est réutilisée par l'analyse) et la durée est annoncée sous le bouton « Analyser », par moteur : état (moteur prêt, ou froid avec le surcoût compté), RTF et expérience source ; « réaffichage immédiat » si le résultat est en cache. Pendant l'analyse, tant que l'étape la plus longue de l'expérience source (`etapes_s` de `execution_<périphérique>.json` : empreintes pour pyannote, représentation pour les baselines) n'a pas avancé d'au moins 2 % pendant au moins 1 s, le panneau affiche la fourchette moins le temps écoulé ; ensuite, « reste environ X, recalé sur la vitesse observée » : durée complète de l'étape extrapolée de la fraction faite, plus les étapes suivantes à proportion de leur part. Les baselines ne rapportent leur avancement qu'en fin d'étape : le recalage n'intervient pour elles qu'une fois la représentation terminée.

### Cache des résultats (audit R-D3 ; décisions du cockpit du 01/11)

Clé : SHA-256 des échantillons de l'audio normalisé, du moteur (et du mode factice), des réglages (périphérique, nombre de locuteurs, paramètres repris de l'expérience source, θ compris), de la configuration effective de l'expérience source (`configuration_effective` de `execution_<périphérique>.json`, celle de la page Pipeline, `moteurs.effective_configuration`) des révisions figées des modèles (`moteurs.model_revisions` : community-1 pour pyannote et WeSpeaker, `spkrec-ecapa-voxceleb` pour ECAPA, aucune pour MFCC) et de l'empreinte du code des moteurs (`cache.engine_code_fingerprint` : chemins et contenu de tous les fichiers de `src/whospoke/` et de `app/moteurs.py`, caches Python exclus, calculée au lancement). Le commit n'entre pas dans la clé : un commit de documents ou de l'interface ne l'invalide pas, un changement du code des moteurs si. Le commit reste consigné dans l'entrée.

Rangé dans `~/.cache/whospoke/resultats/` (`$WHOSPOKE_CACHE_DIR/resultats/` si défini), hors du dépôt, un JSON par résultat (format 3 ; les entrées des formats précédents sont ignorées) : segments, durées par étape, temps de calcul, réglages consignés, commit ; ni audio ni nom de fichier. Le même enregistrement déposé sous un autre nom retrouve son résultat. Le replié « Cache des résultats (plan de repli) » des réglages contient la case « Réafficher un résultat déjà calculé », **décochée par défaut**, la taille du cache et « Vider le cache » ; `--vider-cache` fait de même au lancement. Case décochée, l'annonce signale qu'un résultat est en cache et qu'il sera recalculé. Un résultat réaffiché porte dans le panneau d'avancement le badge « Résultat réaffiché depuis le cache, calculé le … » (préfixé par le moteur en comparaison), et « Temps de traitement » donne les durées de l'analyse d'origine.

## Vue d'ensemble, lecture suivie et raccourcis (chantier B3, audit R-U2 et R-U3, 01/11/2026)

| Élément | Comportement | Où |
|---|---|---|
| Vue d'ensemble | Forme d'onde miniature de tout le fichier (greffon Minimap), sous la barre d'outils. La fenêtre encadrée est la partie visible de la timeline : elle se fait glisser (souris, doigt), ou, une fois sélectionnée au clavier, se déplace avec ← → par pas de 10 % de la vue. Un clic ailleurs sur la vue d'ensemble y amène la lecture et la vue. Le greffon dessine la fenêtre sans la rendre déplaçable (`pointer-events: none`) : le script la rend interactive et la place au-dessus de la miniature | `visualiseur.js` (`initWindow`) |
| Lecture suivie | La vue suit la lecture (`autoScroll` et `autoCenter` de wavesurfer). Déplacer la vue à la main (fenêtre, Maj + molette) arrête le suivi ; le bouton « Suivre la lecture » (`aria-pressed`) le rétablit | `setFollow` |
| Raccourcis | Espace : lecture ou pause ; ← → : tour précédent ou suivant du premier moteur (du locuteur isolé s'il y en a un ; ← revient au début du tour en cours s'il a commencé depuis plus de 0,3 s) ; 1 à 9 : isoler un locuteur du premier moteur (les autres pistes sont estompées) ; 0 : tous ; ? : aide (Échap la ferme), aussi par le bouton « ? ». Inactifs quand le focus est dans un champ (input, textarea, select, contenu éditable, listes déroulantes, tableau de renommage), avec Ctrl, Cmd ou Alt, et quand l'onglet Analyse n'est pas affiché ; Espace et ← → laissent leur action native aux boutons, onglets et boutons radio hors du visualiseur | `onKey` |
| Pastille « parle : X » | Pendant la lecture, le ou les locuteurs du premier moteur à l'instant lu (« parlent : X, Y » en chevauchement, « silence » sinon), avec leur couleur ; masquée à l'arrêt | `showSpeaking` |

Vérifié dans le navigateur en mode factice, en clair, en sombre et à 375 px (largeur de page 375 px, barre d'outils sans débordement après un correctif : la ligne du zoom ne rétrécissait pas). Le simulateur de clavier du navigateur intégré n'émet pas la touche « ? » (évènement à `key` vide) : elle a été vérifiée par un évènement clavier synthétique, ainsi que par le bouton.

## Appariement, « Expliquer cette erreur », extrait typique, renommage (chantier B4, audit R-U4 et R-U6, 01/11/2026)

| Élément | Comportement | Où |
|---|---|---|
| Appariement visible | Avec une référence, chaque piste de référence prend la couleur du locuteur du premier moteur qui lui est apparié et l'étiquette « 021 ↔ SPEAKER_03 » (nom choisi s'il a été renommé) ; non appariée, elle reste grise avec « (non apparié) ». C'est l'appariement optimal du DER (`optimal_mapping` de pyannote.metrics), calculé une seule fois avec la carte des erreurs (`sortie._Matching`) : les couleurs, la carte et le DER ne peuvent pas diverger. La colonne des étiquettes s'élargit (184 px, 112 px à 375 px) | `sortie.pairing`, `app._reference_group` |
| Tableau d'appariement | Sous le DER, dans l'Évaluation : locuteur de référence, locuteur trouvé (ou « non apparié »), temps commun (cooccurrence de pyannote.core), couverture du locuteur de référence (`DiarizationCoverage` restreinte à ce locuteur) et pureté du locuteur trouvé (`DiarizationPurity` restreinte à ce locuteur), puis les locuteurs trouvés non appariés. Pondérées par la durée, ces valeurs redonnent la pureté et la couverture globales de pyannote.metrics (test) | `sortie.matching_report`, `app._matching_html` |
| « Expliquer cette erreur » | Un clic (ou Entrée) sur une zone de la carte des erreurs la fait écouter et ouvre une carte sous la timeline : type, durée au dixième de seconde, locuteur de référence et locuteur trouvé, chacun avec son appariement, et des constats calculés sur la référence : chevauchement (part de la zone), tour de référence de moins de 0,5 s qui la recoupe, pause de la référence de moins de 1 s qui la recoupe ou lui est contiguë (à 0,05 s près), bord de la zone à moins de 0,25 s d'une frontière de tour (la valeur du collar du protocole). Formulation factuelle, jamais une cause ; la carte le rappelle (« Constats sur la référence autour de la zone, pas une cause établie »). Échap ou × la ferme ; elle suit les renommages | `sortie._Context`, `app._context_sentences`, `visualiseur.js` (`explain`) |
| Extrait typique | Bouton ▶ par locuteur dans le tableau des locuteurs : lit, dans la timeline, son plus long tour hors de tout chevauchement, limité à ses 10 premières secondes, et le repère sur la forme d'onde ; désactivé si toute sa parole est en chevauchement | `sortie.typical_excerpts`, `visualiseur.js` (`onExcerpt`) |
| Renommage | Un champ par ligne dans le tableau des locuteurs (identifiant du moteur en dessous) ; validé par Entrée ou en quittant le champ, Échap rétablit le nom affiché ; la grille Gradio séparée est supprimée. Noms en double refusés (le tableau revient aux noms en vigueur), 60 caractères au plus, blancs de bord retirés. Les noms sont échappés partout (valeur du champ comprise) ; les raccourcis clavier sont inactifs pendant la saisie | `app._stats_html`, `STATS_JS`, `rename` |

Vérifié dans le navigateur en mode factice, avec l'audio de `summre__007a_ECRH` (20 min 11 s) et sa référence, copiés dans le dossier temporaire du lancement, supprimé à la fermeture : quatre pistes de référence appariées (021 ↔ SPEAKER_03, 022 ↔ SPEAKER_00, 023 ↔ SPEAKER_01, 024 ↔ SPEAKER_02), DER sans collar 19,15 %, couvertures de 83,3 à 93,2 %, puretés de 81,0 à 92,2 % ; explications d'une confusion, d'une parole manquée en chevauchement et d'une fausse alarme ; extrait de SPEAKER_02 (13:18,8 à 13:28,6) avec la pastille « parle : SPEAKER_02 » ; renommage saisi au clavier (« Camille 1 ») repris par la timeline, la piste de référence, le tableau d'appariement et la carte ouverte, sans que le « 1 » tapé n'isole un locuteur ; en clair, en sombre et à 375 px (largeur de page 375 px).

## Avancement raconté et Pipeline relié aux mesures (chantier B5, audit R-U7 et R-U8, 01/11/2026)

Sources, tenues par le cockpit et lues en lecture seule sous `--depot` : `docs/constats.yaml` (constats mesurés, rattachés à une étape du catalogue ou à « evaluation », avec moteurs, sources, confiance et `cle`) et `docs/synthese.md`. Lecture et contrôle des constats : `app/constats.py` (champs manquants, confiance inconnue, fichier illisible : signalés, jamais ignorés en silence).

| Élément | Comportement | Où |
|---|---|---|
| « Ce que nous avons appris » | En tête de l'onglet Avancement : les constats `cle: true`, leur confiance (certain, probable, incertain, écrite et marquée) et un bouton par source qui affiche ses notes dans la page ; source absente du dépôt signalée sans bouton. Bouton « Lire la synthèse » qui rend `docs/synthese.md` dans la page | `avancement._learned_html`, `notes_markdown("synthese")` |
| Graphique | « Erreurs des systèmes de référence » : barres horizontales empilées du DER test sans collar (parole manquée, fausse alarme, confusion), par corpus, SUMM-RE (D3) puis AMI. Systèmes : baseline MFCC, ECAPA, WeSpeaker et pyannote community-1, chacun par sa première expérience en condition réaliste (nombre de locuteurs estimé, détection non oracle, résultat non invalidé), puis automatiquement toute autre expérience au verdict « retenu » ou « référence ». Le système se lit dans `systeme.pipeline` des résultats et `pipeline.parametres.representation` de config.yaml | `avancement.reference_systems` |
| Rendu du graphique | SVG généré côté serveur, sans bibliothèque. Méthode du skill dataviz : une seule échelle, barres de 20 px, 2 px de surface entre segments, bout arrondi de 4 px côté données, grille en filet ; couleurs = trois premiers emplacements de la palette catégorielle de l'application, validées par `validate_palette.js` sur #ffffff et sur #1b1c1f (vert sous 3:1 en clair : compensé par les valeurs écrites et le tableau), doublées de motifs (plein, hachures à 45° et à 135°) ; légende toujours présente ; DER écrit au bout de chaque barre ; `title` et `desc` (toutes les valeurs) pour les lecteurs d'écran ; info-bulle par segment ; tableau des valeurs repliable. Teintes en variables CSS (`--av-err-*`), donc lisible en clair et en sombre ; deux mises en page du même graphique, large et étroite (étiquette au-dessus de la barre, sous 560 px) | `app/graphique.py`, `interface.css` |
| Décisions | D16 et suivantes visibles ; D1 à D15 repliées par défaut (« Décisions de cadrage D1 à D15 (15, dont 3 avec un point ouvert) ») | `avancement._decisions_html` |
| Chemin local | Le chemin du dépôt lu n'est plus affiché | `avancement.render` |
| Pipeline, constats | Sous chaque étape, les constats dont l'`etape` est celle-ci et dont les `moteurs` comprennent le moteur affiché (liste vide : tous), avec confiance et sources ; « evaluation » sous l'étape Évaluation ; le bouton de l'étape annonce leur nombre. Un constat dont l'étape n'existe pas au catalogue, ou mal formé, est signalé en tête de page, pour tout moteur | `pipeline._attach_constats` |
| Pipeline, segmentation neuronale | Pour pyannote, détection et segmentation sont un seul bloc « Segmentation neuronale (détection et segmentation) », placé à la position de la détection, réglages et constats distingués par étape. Le regroupement est déclaré dans le catalogue (section `regroupements`, ajoutée en fin de `src/whospoke/pipelines/catalogue.yaml` : la page reste générée, sans texte écrit dans le code) ; si le catalogue de `--depot` ne la contient pas encore, celle de ce code est utilisée | `pipeline._grouped`, `catalogue.yaml` |

Vérifié dans le navigateur en mode factice sur le dépôt principal (`--depot ~/Dev/Who-Spoke`, constats et synthèse non encore commités par le cockpit) : 7 constats clés, sources et synthèse affichées dans la page, D1 à D15 repliées ; graphique (SUMM-RE : MFCC 49,36 %, ECAPA 33,42 %, WeSpeaker 35,86 %, pyannote 26,30 % ; AMI : 64,38 %, 45,88 %, 49,17 %, 19,92 %) en clair, en sombre et à 375 px (mise en page étroite, largeur de page 375 px) ; Pipeline de pyannote (bloc unique, C03 et C04 sous leur étape, C07 sous Regroupement, C09 et C10 sous Évaluation) et de la baseline ECAPA (C01, C05, C06, C09).
