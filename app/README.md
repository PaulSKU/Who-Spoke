# Application de démonstration (D17)

## Lancement

```bash
uv run python -m app.app             # moteurs réels, préchauffés au démarrage
uv run python -m app.app --factice   # moteur factice : aucune inférence
```

Puis ouvrir http://127.0.0.1:7860 (serveur local uniquement, pas de lien public). Options : `--port`, `--factice-max-s` (durée maximale simulée d'une analyse en mode factice), `--sans-prechauffage` (moteurs chargés au premier usage), `--vider-cache` (vide le cache des résultats avant le lancement), `--factice-rttm DOSSIER` (mode factice : sorties fabriquées `<nom du fichier déposé>.rttm`, cherchées avant celles de l'expérience source ; cas limites, B7), `--presentation` (ouvre en mode présentation, B8), `--config-demo FICHIER` (configuration de démonstration à lire à la place de `configs/demo.yaml`, B8), `--depot` (racine du dépôt dont sont lus, en lecture seule, les expériences, les analyses, `results/leaderboard.csv`, le catalogue et les documents de `docs/` ; par défaut ce dépôt). Pendant le développement sur la branche `interface`, qui n'a pas toutes les expériences :

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
| Statistiques par locuteur, renommage et fusion, indicateurs d'interaction, exports (RTTM, JSON avec fiche de reproductibilité, étiquettes Audacity, image de la timeline), DER face à une référence (deux conditions de collar, sur toute la durée du fichier, référence coupée à cette durée ; mention « durée entière du fichier, sans UEM : non comparable aux résultats sur corpus ») | `app/sortie.py`, `app/app.py` |
| Forme d'onde neutre (D26) : seul le segment sélectionné, dernier cliqué, y est mis en évidence par une bande d'encre et entouré sur sa piste ; timeline par locuteur, écoute d'un segment au clic, zoom (curseur, boutons, Ctrl + molette ; jusqu'à 150 px par seconde, B8) | `app/static/visualiseur.js` et `.css` |
| Vue spectrogramme (D28 §2, B9) : « Forme d'onde / Spectrogramme » dans la barre du visualiseur ; spectrogramme mel calculé côté serveur, même zoom et même défilement que la timeline ; « Énergie et seuil » pour une baseline | `app/spectrogramme.py`, `app/static/visualiseur.js` |
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
| « Expliquer cette erreur » | Un clic (ou Entrée) sur une zone de la carte des erreurs la fait écouter et ouvre une carte sous la timeline : type, durée au dixième de seconde, locuteur de référence et locuteur trouvé, chacun avec son appariement, la catégorie de la zone et sa part dans la tolérance d'une frontière (depuis le 02/11, voir « Catégories des erreurs, sur le temps » plus bas), et des constats calculés sur la référence : chevauchement (part de la zone), tour de référence de moins de 0,5 s qui la recoupe, pause de la référence de 1 s au plus (moins de 1 s jusqu'au 02/11) qui la recoupe ou lui est contiguë (à 0,05 s près), bord de la zone à moins de 0,25 s d'une frontière de tour (remplacé, depuis l'option b, par la part de la zone dans la tolérance). Formulation factuelle, jamais une cause ; la carte le rappelle (« Constats sur la référence autour de la zone, pas une cause établie »). Échap ou × la ferme ; elle suit les renommages | `sortie._Context`, `app._context_sentences`, `visualiseur.js` (`explain`) |
| Extrait typique | Bouton ▶ par locuteur dans le tableau des locuteurs : lit, dans la timeline, son plus long tour hors de tout chevauchement, limité à ses 10 premières secondes, et le repère sur la forme d'onde ; désactivé si toute sa parole est en chevauchement | `sortie.typical_excerpts`, `visualiseur.js` (`onExcerpt`) |
| Renommage | Un champ par ligne dans le tableau des locuteurs (identifiant du moteur en dessous) ; validé par Entrée ou en quittant le champ, Échap rétablit le nom affiché ; la grille Gradio séparée est supprimée. Noms en double refusés (le tableau revient aux noms en vigueur), 60 caractères au plus, blancs de bord retirés. Les noms sont échappés partout (valeur du champ comprise) ; les raccourcis clavier sont inactifs pendant la saisie | `app._stats_html`, `STATS_JS`, `rename` |

Vérifié dans le navigateur en mode factice, avec l'audio de `summre__007a_ECRH` (20 min 11 s) et sa référence, copiés dans le dossier temporaire du lancement, supprimé à la fermeture : quatre pistes de référence appariées (021 ↔ SPEAKER_03, 022 ↔ SPEAKER_00, 023 ↔ SPEAKER_01, 024 ↔ SPEAKER_02), DER sans collar 19,15 %, couvertures de 83,3 à 93,2 %, puretés de 81,0 à 92,2 % ; explications d'une confusion, d'une parole manquée en chevauchement et d'une fausse alarme ; extrait de SPEAKER_02 (13:18,8 à 13:28,6) avec la pastille « parle : SPEAKER_02 » ; renommage saisi au clavier (« Camille 1 ») repris par la timeline, la piste de référence, le tableau d'appariement et la carte ouverte, sans que le « 1 » tapé n'isole un locuteur ; en clair, en sombre et à 375 px (largeur de page 375 px).

## Avancement raconté et Pipeline relié aux mesures (chantier B5, audit R-U7 et R-U8, 01/11/2026)

Sources, tenues par le cockpit et lues en lecture seule sous `--depot` : `docs/constats.yaml` (constats mesurés, rattachés à une étape du catalogue ou à « evaluation », avec moteurs, sources, confiance et `cle`) et `docs/synthese.md`. Lecture et contrôle des constats : `app/constats.py` (champs manquants, confiance inconnue, fichier illisible : signalés, jamais ignorés en silence).

| Élément | Comportement | Où |
|---|---|---|
| « Ce que nous avons appris » | En tête de l'onglet Avancement : les constats `cle: true`, leur confiance (certain, probable, incertain, écrite et marquée) et un bouton par source qui affiche ses notes dans la page ; source absente du dépôt signalée sans bouton. Bouton « Lire la synthèse » qui rend `docs/synthese.md` dans la page | `avancement._learned_html`, `notes_markdown("synthese")` |
| Graphique | « Erreurs des systèmes de référence » : barres horizontales empilées du DER test sans collar (parole manquée, fausse alarme, confusion), par corpus, SUMM-RE (D3) puis AMI. Systèmes : baseline MFCC, ECAPA, WeSpeaker et pyannote community-1, chacun par sa première expérience en condition réaliste (nombre de locuteurs estimé, détection non oracle, résultat non invalidé), puis automatiquement toute autre expérience au verdict « retenu » ou « référence ». Le système se lit dans `systeme.pipeline` des résultats et `pipeline.parametres.representation` de config.yaml | `avancement.reference_systems` |
| Rendu du graphique | SVG généré côté serveur, sans bibliothèque. Méthode du skill dataviz : une seule échelle, barres de 20 px, 2 px de surface entre segments, bout arrondi de 4 px côté données, grille en filet ; couleurs = trois premiers emplacements de la palette catégorielle de l'application, le vert pris un pas plus foncé (#199e70) pour passer le contraste de 3:1 en clair ; toutes validées par `validate_palette.js` sur #ffffff et sur #1b1c1f, sans avertissement ; doublées des motifs de la carte des erreurs de l'Analyse (parole manquée pleine, fausse alarme hachurée, confusion en contour : un même type d'erreur a la même apparence partout, décision du cockpit du 01/11) ; légende toujours présente ; DER écrit au bout de chaque barre ; `title` et `desc` (toutes les valeurs) pour les lecteurs d'écran ; info-bulle par segment ; tableau des valeurs repliable. Teintes en variables CSS (`--av-err-*`), donc lisible en clair et en sombre ; deux mises en page du même graphique, large et étroite (étiquette au-dessus de la barre, sous 560 px) | `app/graphique.py`, `interface.css` |
| Décisions | D16 et suivantes visibles ; D1 à D15 repliées par défaut (« Décisions de cadrage D1 à D15 (15, dont 3 avec un point ouvert) ») | `avancement._decisions_html` |
| Chemin local | Le chemin du dépôt lu n'est plus affiché | `avancement.render` |
| Pipeline, constats | Sous chaque étape, les constats dont l'`etape` est celle-ci et dont les `moteurs` comprennent le moteur affiché (liste vide : tous), avec confiance et sources ; « evaluation » sous l'étape Évaluation ; le bouton de l'étape annonce leur nombre. Un constat dont l'étape n'existe pas au catalogue, ou mal formé, est signalé en tête de page, pour tout moteur | `pipeline._attach_constats` |
| Pipeline, segmentation neuronale | Pour pyannote, détection et segmentation sont un seul bloc « Segmentation neuronale (détection et segmentation) », placé à la position de la détection, réglages et constats distingués par étape. Le regroupement est déclaré dans le catalogue (section `regroupements`, ajoutée en fin de `src/whospoke/pipelines/catalogue.yaml` : la page reste générée, sans texte écrit dans le code) ; si le catalogue de `--depot` ne la contient pas encore, celle de ce code est utilisée | `pipeline._grouped`, `catalogue.yaml` |

Vérifié dans le navigateur en mode factice sur le dépôt principal (`--depot ~/Dev/Who-Spoke`, constats et synthèse non encore commités par le cockpit) : 7 constats clés, sources et synthèse affichées dans la page, D1 à D15 repliées ; graphique (SUMM-RE : MFCC 49,36 %, ECAPA 33,42 %, WeSpeaker 35,86 %, pyannote 26,30 % ; AMI : 64,38 %, 45,88 %, 49,17 %, 19,92 %) en clair, en sombre et à 375 px (mise en page étroite, largeur de page 375 px) ; Pipeline de pyannote (bloc unique, C03 et C04 sous leur étape, C07 sous Regroupement, C09 et C10 sous Évaluation) et de la baseline ECAPA (C01, C05, C06, C09).

## Fusion de locuteurs, interactions, exports et fiche de reproductibilité (chantier B6, audit R-U9, R-U10, R-U11 et R-D5, 01/11/2026)

R-U12 (bascule de la sortie exclusive) est abandonné : la sortie exclusive dégrade SUMM-RE test (journal du cockpit du 01/11, premier regard sur EXP-0016).

| Élément | Comportement | Où |
|---|---|---|
| Fusion de deux locuteurs (R-U9) | Liste « Fusionner avec… » sur chaque ligne du tableau des locuteurs : la parole du locuteur de la ligne rejoint celle du locuteur choisi, qui garde son identifiant, son nom et sa couleur (la couleur suit le locuteur, pas son rang : les autres ne sont pas repeints). La parole réunie est fusionnée (segments qui se recouvrent ou se touchent). Fusions en chaîne possibles, listées sous le tableau, avec un bouton « Annuler la dernière fusion ». Statistiques, interactions, timeline, comparaison, exports et, avec une référence, DER, appariement et carte des erreurs sont recalculés ; l'Évaluation affiche « DER sans collar avant → après » (et avec collar). La fusion s'applique à une copie : l'annotation du moteur (`annotation_origine`) et le résultat en cache ne sont jamais modifiés. Un nom repris par un autre locuteur pendant une fusion est rendu à son identifiant à l'annulation, avec un avertissement | `sortie.merge_speakers`, `app.speakers_changed`, `_merge_der_html` |
| Durée d'une fusion | Le DER d'avant (annotation du moteur, même référence) est calculé une fois puis gardé dans le résultat ; le DER d'après sert à la fois au tableau et à l'affichage « avant → après ». Sur 007a_ECRH (20 min), avec référence : 3,3 s pour la première fusion, 2,2 s pour la suivante (10 s avant cette mise en mémoire) | `_merge_der_html` |
| Indicateurs d'interaction (R-U10) | Carte « Interactions », sans transcription, sur les tours du premier moteur (erreurs comprises). Tour : plage continue de parole d'un locuteur (comme une intervention). Plus long monologue (avec ▶ pour en écouter le début) ; par locuteur : tours, durée moyenne d'un tour, plus long tour, latence médiane de réponse et nombre de réponses. Passage de parole : un locuteur prend la parole quand son tour finit après celui de qui l'avait (« floor transfer offset », Heldner et Edlund, 2010) ; un tour inclus dans celui d'un autre (acquiescement, chevauchement bref) ne compte pas, une reprise après sa propre pause non plus. Latence : début du tour moins fin du tour précédent, négative quand le locuteur commence avant que l'autre ait fini | `app/interactions.py`, `_interactions_html` |
| Matrice « qui suit qui » | Vrai tableau N × N (en-têtes de ligne et de colonne, légende pour les lecteurs d'écran) : ligne, qui avait la parole ; colonne, qui la prend ; effectif écrit dans chaque case, teinte d'encre proportionnelle en plus (même sens en clair et en sombre), diagonale « sans objet » | `_follow_matrix_html` |
| Étiquettes Audacity (R-U11) | `<fichier>_audacity.txt` : une ligne par tour, `début<TAB>fin<TAB>code`, secondes à six décimales, code `S1`, `S2`… dans l'ordre de première prise de parole. C'est le format lu par la chaîne du corpus maison (`whospoke.maison.reference.read_labels`, branche `outils` ; conventions-annotation.md §3) : le locuteur est tiré du texte de chaque étiquette. La correspondance code → identifiant et nom est dans le JSON (`etiquettes_audacity`), Audacity n'ayant pas de ligne de commentaire | `sortie.to_audacity`, `sortie.audacity_codes` |
| Image de la timeline (R-U11) | `<fichier>_timeline.svg` : mêmes groupes que la timeline (premier moteur, second moteur, référence appariée, cartes des erreurs avec leurs motifs), toute la durée sur une seule échelle, couleurs fixes du mode clair sur fond blanc, police système, `title` et `desc`. PNG : bouton « Image PNG de la timeline », le navigateur dessine ce SVG dans un canevas deux fois plus fin et l'enregistre, sans dépendance (Pillow et matplotlib ne sont présents qu'indirectement, ils ne sont pas déclarés). Une seule image par analyse, comparaison comprise | `app/image.py`, `_image_html`, `IMAGE_JS` |
| Fiche de reproductibilité (R-D5) | Dans chaque JSON exporté, `reproductibilite` : date de l'analyse et du calcul (celle du calcul d'origine pour un résultat réaffiché depuis le cache), commit (celui du calcul), empreintes du code des moteurs et de l'audio normalisé, moteur, factice ou non, expérience source, révisions des modèles, configuration effective (celle de la page Pipeline), réglages, nombre de locuteurs, versions (Python, whospoke, torch, torchaudio, pyannote.audio, .core, .metrics, speechbrain, numpy, scipy, scikit-learn, librosa, gradio, ffmpeg), machine (système, architecture, processeur, cœurs, périphérique, carte graphique en CUDA), durées (audio, normalisation, chargement, étapes, calcul, RTF) et fusions en vigueur. Ni audio, ni nom de fichier d'origine, ni chemin local | `app/reproductibilite.py`, `result_item` (`tracabilite`) |
| Petits écrans | Sous 720 px, « Temps de traitement » et « Exports » s'empilent (côte à côte, les noms des exports n'avaient plus la place) et les noms longs passent à la ligne | `interface.css` (`.ws-pair`) |

Vérifié dans le navigateur en mode factice avec l'audio de `summre__007a_ECRH` et sa référence : clair et sombre à 1280 px, clair et sombre à 375 px (largeur de page 375 px). Fusion de SPEAKER_03 dans SPEAKER_01 : DER sans collar 19,15 % → 31,12 % (collar ± 0,25 s : 9,23 % → 22,00 %), couleurs des autres locuteurs inchangées, annulation qui rend 19,15 % ; matrice 4 × 4 de 287 passages ; PNG de 2400 × 808 px tiré du SVG. Latence médiane de 0,00 s pour chaque locuteur sur ce fichier : 85 des 287 passages de la sortie de pyannote sont exactement jointifs, et les autres se répartissent à peu près autant en négatif qu'en positif.

## Robustesse face à des fichiers inconnus (chantier B7, démonstration du 16/11, 02/11/2026)

Démarche inspirée du skill break-ui (emilkowalski/skills, lu sans être installé) : des données réalistes de pire cas, entrées par la même porte que les vraies (fichier déposé, sortie du moteur, référence déposée), puis, pour chaque cas, comportement attendu, comportement observé et correctif. Fichiers fabriqués sans aucune donnée personnelle par `tests/fabrique.py` (audio synthétique généré par ffmpeg, RTTM écrits par le script) :

```bash
uv run python -m tests.fabrique /tmp/b7 --longs
uv run python -m app.app --factice --factice-rttm /tmp/b7/sorties
```

puis déposer les fichiers de `/tmp/b7/audio` et de `/tmp/b7/references`. Un message d'erreur nomme le fichier, donne la cause probable et dit quoi faire ; il ne montre ni chemin local ni sortie brute de ffmpeg.

### Fichiers audio

| Cas | Attendu | Observé avant B7 | Correctif | Test |
|---|---|---|---|---|
| Vidéo mp4 et mov (son AAC 48 kHz stéréo) | Son extrait, normalisé en 16 kHz mono | Correct | — | `test_formats_lisibles_normalises` |
| Vidéo sans piste son | Message : pas de piste son, déposer un fichier avec l'audio | Sortie brute de ffmpeg, chemins compris (« Output file does not contain any stream ») | `_audio_error` : cause d'après la sortie de ffmpeg, conseil, détail technique sans chemin | `test_fichiers_illisibles_message_qui_dit_quoi_faire` |
| WAV stéréo 44,1 kHz, WAV stéréo 48 kHz 24 bits, m4a, ogg | Normalisés, durée exacte | Correct | — | `test_formats_lisibles_normalises` |
| m4a coupé (enregistrement interrompu) | Message : fichier incomplet, récupérer le fichier complet | Sortie brute de ffmpeg (« moov atom not found ») | `_audio_error` | `test_fichiers_illisibles_…` |
| Texte renommé en `.wav` | Message : pas un fichier audio, quelle que soit l'extension | Sortie brute de ffmpeg (« Invalid data found ») | `_audio_error` | `test_fichiers_illisibles_…` |
| Audio de 3 s | Analyse, zoom inutile désactivé | Correct ; « 1 locuteur(s) en 0 s » | Pluriels (`_plural`), durées sous la seconde au centième (`temps.format_duration`) | `test_formats_lisibles_normalises` |
| Silence complet | Avertir avant le lancement ; après, dire qu'aucun locuteur n'est détecté et quoi vérifier | Aucun avertissement ; tableaux vides réduits à leurs en-têtes, timeline sans piste | Silence repéré à la préparation (niveau maximal sous −80 dB) et annoncé sous le bouton ; état « Aucun locuteur détecté », message dans Locuteurs et Interactions, piste « Aucun locuteur » | `test_formats_lisibles_…`, `test_zero_locuteur` |
| 30 min (m4a) | Fluide | Préparation 2 s, analyse factice et rendus 1,3 s, fusion 1,5 s | — | `test_trente_et_quatre_vingt_dix_minutes` (lent) |
| 90 min (m4a) | Utilisable | Préparation 8 s, analyse factice et rendus 7 s, fusion 10 s, 1,1 Go de mémoire ; dans le navigateur, résultat 13 s après le dépôt, zoom maximal (324 000 px) en 0,45 s, forme d'onde et pistes rendues à 45:00 ; aucune indication pendant les secondes de mise en forme | Étape d'état « Mise en forme des résultats, calcul du DER et de la carte des erreurs » | `test_trente_…` (lent), `test_quatre_vingt_dix_minutes_de_tours` |
| Fichier inconnu du moteur factice | Message : déposer un fichier du corpus, ajouter une sortie fabriquée ou lancer sans `--factice` | « aucun RTTM pour … dans experiments/… » | Message de `moteurs.find_rttm` | `test_recherche_du_rttm`, `test_moteur_factice_…` |
| Titre des notifications | En français | « Error », « Warning » : Gradio y écrit le type du message, sans traduction | Titres remplacés en CSS (« Erreur », « Attention », « Information ») | — (vérifié dans le navigateur) |

### Résultats (sorties fabriquées, 60 s)

| Cas | Attendu | Observé avant B7 | Correctif | Test |
|---|---|---|---|---|
| 0 locuteur | « Aucun locuteur détecté », quoi vérifier | « 0 locuteur(s) » ; tableaux vides ; exports vides mais valides | Voir silence ci-dessus | `test_zero_locuteur` |
| 1 locuteur | Pas de matrice, pas de fusion, latence « — » | Correct ; « 1 locuteur(s) » | Pluriels | `test_un_locuteur` |
| 6, 9, 12 locuteurs | Lisible ; au-delà de 8, gris, l'identité portée par le nom | Couleurs correctes ; touches 1 à 9 seulement : locuteurs 10 à 12 impossibles à isoler ; matrice de 12 noms longs large de 2 232 px, noms des lignes perdus au défilement | Clic sur le nom d'une piste pour isoler (et le dire dans l'aide) ; matrice : au-delà de 4 locuteurs ou d'un nom de plus de 14 caractères, colonnes numérotées comme les lignes (nom en info-bulle et pour les lecteurs d'écran), noms des lignes figés à gauche | `test_six_neuf_douze_locuteurs`, `test_au_dela_de_neuf_…` |
| Noms très longs (60 caractères, la limite du champ) | Coupés par « … », nom complet en info-bulle et dans les tableaux | Colonne des noms de la timeline élargie par le nom le plus long : le nom passait sous les pistes, coupé net | Colonne des noms bornée à sa piste (`minmax(0, 1fr)`), texte dans son propre bloc à « … » | `test_noms_longs_speciaux_et_doublons` |
| Noms en double | Refusés, avec la raison | Refus seulement à l'identique ; « Alice » et « alice » acceptés ; « Alice Martin » et « Alice_Martin » refusés sans dire pourquoi | Comparaison à la casse, aux blancs et à « _ » près, message qui l'explique | `test_noms_longs_…` |
| Caractères spéciaux (`<script>`, guillemets, &, emoji, arabe, chinois, vietnamien) | Affichés tels quels, jamais interprétés | Correct partout (tableaux, timeline, image, RTTM, JSON) | — | `test_noms_longs_…` |
| Chevauchement massif (4 locuteurs en même temps) | Extraits désactivés, aucun passage de parole | Correct ; « 0 passages de parole » | « Aucun passage de parole » | `test_chevauchement_massif` |
| Tours de 50 ms (1 200 segments en 60 s) | Durées lisibles, segments cliquables | Info-bulle « 0:00 – 0:00 (0,0 s) », durée moyenne « 0,1 s », plus long tour « 0 s » ; segment de 3 px au zoom maximal | Au dixième pour l'intervalle et au centième pour la durée sous la seconde (`fmtSpan`), durées sous la seconde au centième | `test_tours_de_50_ms` |

### Références

| Cas | Attendu | Observé avant B7 | Correctif | Test |
|---|---|---|---|---|
| Colonnes manquantes | Message : ligne, champs attendus, corriger | Plantage du gestionnaire (`IndexError`) | `sortie.read_reference` contrôle chaque ligne `SPEAKER` | `test_references_mal_formees` |
| Nombre illisible (`zéro`, `1,5`) | Message : ligne, écrire en secondes avec un point | « could not convert string to float » | Idem | `test_references_mal_formees` |
| Durée négative | Refusée : la 5e colonne est une durée | Acceptée : DER de 1 245 % | Idem | `test_references_mal_formees` |
| Fichier vide, binaire, étiquettes Audacity, plusieurs enregistrements | Message qui dit quoi déposer | « aucune ligne SPEAKER », « 'utf-8' codec can't decode… » | Messages par cas, Audacity reconnu | `test_references_mal_formees` |
| Référence contrôlée dès le dépôt | Erreur visible avant l'analyse | « Référence chargée : le DER s'affichera après l'analyse », même illisible | Lecture dès le dépôt | `test_references_mal_formees` |
| Référence d'un autre fichier | Avertir, calculer quand même | Silencieux (DER de 90,74 %) | « À vérifier » : l'identifiant de la référence ne correspond pas au nom de l'audio (`summre__007a_ECRH` et `007a_ECRH` reconnus comme le même) | `test_reference_d_un_autre_fichier_…` |
| Référence plus longue que l'audio | Avertir : la parole au-delà est ignorée | Silencieux (référence coupée) | « À vérifier » au-delà de 1 s de parole ignorée | Idem |
| Référence plus courte que l'audio | Avertir : la parole trouvée après compte en fausse alarme | Silencieux (DER de 188 %) | « À vérifier » au-delà de 10 s et 5 % de la parole trouvée, avec le conseil de couper l'audio | Idem |

### Limite connue

Une sortie très morcelée reste lente : `Timeline.co_iter` de pyannote.core, qu'utilisent le DER de pyannote.metrics, les statistiques et la carte des erreurs, croît à peu près comme le carré de la densité de segments. 1 200 tours de 50 ms en 60 s : DER en 0,33 s ; 3 600 en 3 min : 2,1 s ; 36 000 en 30 min : plusieurs minutes (extrapolé, non mené à terme). Une analyse réelle en produit bien moins (environ 1 000 segments pour 20 min sur 007a_ECRH). L'écran affiche désormais l'étape de mise en forme au lieu de rester figé. Le comportement des moteurs réels sur ces fichiers (3 s, silence, 90 min) reste à vérifier à la fusion, sans modèle chargé ici.

## Zoom relevé, mode présentation et configuration de démonstration (chantier B8, 02/11/2026)

### Zoom maximal : 150 px/s (au lieu de 60)

Relevé parce que la fluidité tient sur 30 min, une fois corrigé ce qui la faisait tomber. Mesure dans le navigateur intégré, moteur factice, 1280 × 720 : réunion fabriquée de 30 min (4 locuteurs, 1 422 tours de 0,3 à 3 s avec chevauchements brefs), comparée à un second moteur et à une référence décalée, soit 10 581 segments et zones d'erreur dans la timeline, le pire cas d'affichage. Intervalle entre images (`requestAnimationFrame`), médiane, 95e centile, maximum ; « lecture suivie » : lecture avec « Suivre la lecture », au zoom maximal ; « glissement » : 40 px de défilement par image, « rapide » : 400 px.

| Zoom maximal | Lecture suivie | Glissement | Glissement rapide | Pas de zoom |
|---|---|---|---|---|
| 60 px/s, avant B8 | 22 à 44 images/s selon le passage ; au pire 41 ms, 65 ms, 73 ms | 47 images/s ; 24 ms, 33 ms | 36 images/s ; 25 ms, 41 ms | 150 à 170 ms |
| 150 px/s, avant B8 | 20 images/s ; 48 ms, 70 ms, 82 ms (15 images au-delà de 50 ms en 3,5 s) | 44 images/s ; 24 ms, 32 ms | 35 images/s ; 25 ms, 41 ms | 145 à 187 ms |
| 150 px/s, segments hors vue masqués | 118 à 119 images/s ; 8,3 ms, 10,1 ms, 23 ms | 120 images/s ; 8,3 ms, 10,1 ms | 116 images/s ; 8,3 ms, 10,3 ms | 35 à 45 ms aux forts zooms, 140 à 240 ms aux premiers pas, 280 ms pour « Tout afficher » |

Le coût venait des pistes, pas de la forme d'onde : pistes masquées, la lecture suivie montait à 122 images/s ; segments hors de la vue masqués à la main, aussi. Correctif (`cullBars` dans `visualiseur.js`) : segments et zones d'erreur triés par début ; à chaque défilement ou zoom, seuls ceux d'une largeur de vue de part et d'autre de la partie visible restent affichés (115 éléments sur 10 581 au zoom maximal), et seuls ceux qui entrent ou sortent de cette plage changent. À zoom nul, tout reste affiché. Canevas de 270 000 px au zoom maximal sur 30 min ; un tour de 50 ms y fait 7,5 px (3 px à 60 px/s). Les segments masqués ne sont plus atteignables à la tabulation : au zoom maximal, la tabulation parcourt ceux de l'écran et de ses abords. Mesures faites dans le panneau du navigateur de l'application de bureau, masqué : le navigateur y calcule les images comme dans une fenêtre visible tant qu'il ne les ralentit pas (vérifié : 122 images/s au repos), mais l'affichage réel à l'écran n'est pas mesuré. Non mesuré à 90 min (canevas de 810 000 px au zoom maximal).

### Mode présentation (`--presentation` ou bouton « Mode présentation » de l'en-tête)

Pour un vidéoprojecteur ou un écran partagé, lu de loin à 1280 × 720. Classe `ws-presentation` sur `<html>`, posée au chargement par l'option et basculée par le bouton (`app/static/presentation.js`, `aria-pressed` tenu à jour même quand Gradio redessine l'en-tête) ; le visualiseur recalcule son zoom au basculement.

| Effet | Détail |
|---|---|
| Texte et commandes agrandis d'un quart | Racine à 20 px (nos tailles sont en rem) ; tailles de texte de Gradio relevées (`--text-md` 14 → 18 px), aussi sur `body.dark`, où Gradio les redéclare ; boutons du visualiseur de 32 à 40 px ; pistes de 14 à 20 px, rangées de 24 à 30 px ; colonne des noms de 132 à 176 px (184 à 236 avec une référence appariée) ; tête de lecture de 3 px |
| Contrastes renforcés | Texte secondaire #5f616a → #44464d en clair, #a3a49e → #c8c9c3 en sombre ; filets #e2e2df → #b6b7b1 et #2d2e33 → #4f5158 ; fond des pistes plus marqué ; cartes cernées d'un filet (un projecteur délave les gris clairs) |
| Masqué | Périphérique et « Cache des résultats » (classe `ws-secondary`), aide en ligne sous la timeline (les raccourcis restent sous « ? »), liste des étapes une fois toutes terminées (à 720 px de haut, elle repoussait la timeline sous le bord de l'écran) |

Vérifié dans le navigateur à 1280 × 720, clair et sombre, analyse comparée de 30 min avec référence : en-tête, bandeau, état, timeline et tableau des locuteurs lisibles ; bascule aller-retour (réglages secondaires masqués puis rendus, zoom recalculé). À 375 px (sombre), avec et sans mode présentation, après une analyse comparée : pas de défilement horizontal.

Corrigés en passant : en sombre, la coche des cases et le point des boutons radio cochés étaient blancs sur le fond clair d'un choix coché, donc invisibles (règle de Gradio en dur, remplacée) ; le chemin du RTTM affiché en mode factice dans « Temps de traitement » élargissait la page à 523 px sur un écran de 375 px (coupé n'importe où désormais).

### Configuration de démonstration (D17, amendement 1 : gel du 10/11)

L'application lit `configs/demo.yaml` s'il existe : moteur proposé par défaut, expérience source de chaque moteur, nombre de locuteurs par défaut de chaque moteur. Sinon, elle garde la correspondance de `app/moteurs.py` (`SPECS`, `DEFAULT_ENGINE`, nombre automatique). Seul `configs/demo.exemple.yaml` est versionné aujourd'hui (fourchette de 2 à 6 pour pyannote, garde-fou retenu le 02/11) ; `configs/demo.yaml` sera écrit au gel. Essai d'un fichier sans le mettre en place :

```bash
uv run python -m app.app --factice --config-demo configs/demo.exemple.yaml
```

| Point | Comportement |
|---|---|
| Affichage | En-tête : « Configuration : `configs/demo.yaml`, gel du 10/11/2026 » (ou « correspondance de `app/moteurs.py`, avant le gel ») et le moteur choisi avec son expérience source et son nombre de locuteurs par défaut ; suit le choix du moteur. Au lancement, la console l'écrit aussi |
| Moteur absent du fichier (décision du 02/11) | Non proposé (listes « Moteur », « Second moteur » et page Pipeline) ; l'en-tête ajoute « Non retenu pour la démonstration : … », la console aussi. Second moteur proposé : la baseline ECAPA si elle est retenue, sinon le premier autre moteur retenu |
| Nombre de locuteurs | Valeur par défaut de chaque moteur (`automatique`, `impose` avec `valeur`, `fourchette` avec `min` et `max`), appliquée à l'ouverture et à chaque changement de moteur |
| Comparaison avec une fourchette | La fourchette ne vaut que pour pyannote (D17, amendement 1) : le second moteur, une baseline, estime lui-même le nombre de locuteurs ; l'annonce de durée et une notification le disent, le bandeau donne le réglage de chaque moteur. Avant, la comparaison par défaut (pyannote et baseline ECAPA) aurait été refusée dès que la fourchette était le réglage par défaut |
| Fichier incohérent | Le lancement s'arrête sur un message qui dit quoi corriger : moteur inconnu, identifiant EXP-NNNN, fourchette sur une baseline, `min` au-dessus de `max`, entier attendu, mode inconnu, moteur par défaut absent, YAML illisible |
| Reproductibilité | La fiche de l'export JSON consigne `configuration_demo` : fichier, date du gel, SHA-256 (`null` avant le gel) |
| Cache | Inchangé : l'expérience source et les réglages font déjà partie de la clé |

Tests : `tests/test_app_presentation_gel.py` (26). Suite complète : 509 réussis, 12 ignorés, 3 lents exclus.

## Vue spectrogramme et énergie de la baseline (chantier B9, D28 §2, 02/11/2026)

### Greffon Spectrogram : mesuré, écarté

Archive npm `wavesurfer.js-7.12.12.tgz` téléchargée de nouveau le 02/11 : intégrité sha512 conforme au registre (`fyKNuREQ…uutWw==`), mêmes SHA-256 pour les quatre fichiers déjà embarqués, licence BSD-3-Clause identique, aucune URL dans `dist/plugins/spectrogram.min.js` (SHA-256 6f3e233b0044a85cdea275494dce469bfcf5a6f7f0cb33e5a8350a347b957ae9) ni dans sa variante `spectrogram-windowed.min.js` ; leur travailleur est inclus en base64 et lancé depuis un `blob:`. Les deux greffons lisent l'audio décodé par wavesurfer (`getDecodedData()`) : avec les pics précalculés de l'application, il faut décoder tout le fichier dans le navigateur (0,5 s et environ 115 Mo pour 30 min à 16 kHz), ce que l'application évitait.

Banc d'essai hors de l'application (wavesurfer seul, audio de 30 min décodé à 16 kHz, 1100 px de large, `fftSamples` 512, échelle mel, navigateur intégré de l'application de bureau, panneau affiché, 120 images/s au repos ; la piste A calculait en même temps) :

| Greffon | Pas de zoom vers 150 px/s | Lecture suivie | Glissement 40 px/image | Glissement 400 px/image |
|---|---|---|---|---|
| Spectrogram, FFT dans la page | 3,7 s de calcul, dont un gel de 0,87 s | 118 images/s, une image de 92 ms | gel de 0,78 s (nouveau canevas de 30 000 px) | gel de 0,58 s |
| Spectrogram, FFT dans un travailleur | gel de 0,88 s | 118 images/s, une image de 74 ms | gel de 0,60 s | gel de 0,59 s |
| Spectrogram-windowed (variante du même paquet) | aucun gel | 118 images/s, une tâche de 127 ms | 120 images/s, mais vue dessinée sur 0 % des images | 121 images/s, vue dessinée sur 5 % des images |

Le greffon Spectrogram ne tient pas (gels de plus d'une demi-seconde au défilement et à chaque pas de zoom). La variante windowed reste fluide parce qu'elle ne dessine qu'à l'arrêt : 80 à 200 ms après un saut, une vue vide pendant tout glissement. D'où la solution de repli de D28 : une image calculée côté serveur. Aucun des deux greffons n'est embarqué.

### Image calculée côté serveur, à résolution adaptée au zoom

| Point | Comportement | Où |
|---|---|---|
| Contenu | Spectrogramme mel dont la baseline tire ses MFCC (D19) : trames de 25 ms, pas de 10 ms, 40 bandes, même appel à librosa que `Baseline.analyse` (le test le vérifie : les MFCC recalculés à partir de ce spectrogramme sont ceux de la baseline). En dB, sur 60 dB sous le maximum du fichier, quantifié sur 8 bits | `spectrogramme.mel_power`, `mel_db`, `quantize` |
| Résolution | Pyramide : niveau 0 à 100 trames par seconde, puis moyenne de 2, 4, 8… trames, jusqu'à 256 trames au plus. Le navigateur prend le niveau le plus grossier qui garde au moins une trame par pixel. Fichier binaire à côté de l'audio normalisé (`<fichier>.spectrogramme.bin`, 14 Mo pour 30 min), lu une fois | `spectrogramme.pyramid`, `compute` |
| Calcul | Lancé en tâche de fond dès la normalisation du fichier déposé, un seul à la fois ; la mise en forme des résultats l'attend s'il n'a pas fini. 3,0 s pour 30 min (pendant un calcul de la piste A). Un échec rend la vue indisponible (bouton grisé), sans bloquer l'analyse | `spectrogramme.start`, `result` ; `prepare` |
| Dessin | Un canevas de la largeur de la vue, sous la forme d'onde rendue transparente : curseur, sélection et clic pour se déplacer restent ceux de wavesurfer. À chaque défilement, zoom ou redimensionnement, seules les colonnes visibles sont mises en couleurs et dessinées (au plus une image par rafraîchissement) : coût constant quelle que soit la durée | `drawSpectrogram`, `scheduleLayers` |
| Axe | Graduations 500 Hz, 1, 2, 4 et 8 kHz dans la colonne des noms, placées sur l'échelle mel des bandes | `spectrogramme.band_ticks` |
| Hauteur | 112 px (144 px en mode présentation), variable `--wsp-spec-h` | `visualiseur.css` |

### Palette

Rampe à une seule teinte neutre, interpolée en OKLab du fond des pistes à l'encre : clarté régulière d'un pas à l'autre (perceptuellement uniforme), sans chroma, ce qui garde la couleur aux locuteurs (D26) et ne dépend d'aucune vision des couleurs. En clair, `#f0f0ed` → `#18191d` (plus foncé = plus d'énergie) ; en sombre, `#232428` → `#ecece9` (plus clair = plus d'énergie), comme une rampe séquentielle de la skill dataviz, dont l'ancrage s'inverse en sombre. Une légende sous l'image donne la rampe et son sens. Le thème basculé redessine l'image. Le test vérifie la monotonie et l'écart à la droite idéale en OKLab (moins de 0,004, arrondi à 8 bits compris).

### Énergie et seuil de la baseline (« Énergie et seuil »)

Bouton visible quand le premier moteur, ou à défaut le second, est une baseline. Bande de 56 px sous la vue, avec sa propre échelle (pas de second axe sur le spectrogramme) : énergie par trame (enveloppe minimum et maximum par pixel), seuil de détection en tirets, régions de parole retenues en bande pleine en bas ; infobulle au survol (instant, énergie, position par rapport au seuil, parole détectée ou non). Données lues dans la trace du moteur (`Resultat.trace` : `energie_db`, `seuil_db`, `pas_trame_s`, `regions_parole`), demandée à la baseline (`engine.trace`) et à elle seule, écrites dans `<fichier>.<moteur>.energie.bin`. Le cache des résultats garde l'énergie au dixième de dB (champ `detection` de l'entrée, format inchangé) : un résultat réaffiché la montre aussi ; une entrée antérieure à B9 n'en a pas. Le moteur factice fabrique une trace quand il imite une baseline (énergie par tranche de 10 ms sans recouvrement, seuil à la médiane, sans lissage), marquée « Trace factice » dans la légende.

### Fluidité dans l'application (30 min, 150 px/s)

Même réunion de 30 min qu'au banc (SUMM-RE 007a_ECRH bouclée, copie locale supprimée après la séance), moteur factice : baseline MFCC puis baseline ECAPA, avec une référence (5 833 segments et zones), 1280 × 720, panneau affiché ; mêmes mesures qu'en B8 (intervalle entre images, médiane, 95e centile, maximum).

| Vue | Lecture suivie | Glissement 40 px/image | Glissement 400 px/image | Pas de zoom |
|---|---|---|---|---|
| Forme d'onde (témoin) | 113 images/s ; 8,3 ms, 15,7 ms, 32 ms | 119 images/s ; 8,3, 10,2, 17,6 ms | 106 images/s ; 8,5, 16,7, 20,8 ms | 29 à 46 ms |
| Spectrogramme et énergie | 108 à 114 images/s ; 8,3 ms, 15 à 17 ms, 26 à 67 ms (une image au-delà de 50 ms au départ de la lecture) | 120 images/s ; 8,3, 10,2, 17,4 ms | 100 images/s ; 8,6, 17,4, 24,8 ms | 24 à 86 ms |

Chargement du fichier du spectrogramme : 14 Mo en 0,31 s ; énergie : 0,7 Mo ; tas JavaScript 104 Mo. Non mesuré à 90 min (fichier d'environ 43 Mo, même coût de dessin).

Vérifié dans le navigateur intégré : clair et sombre à 1280 × 720, sombre à 375 px (largeur de page 375 px, barre d'outils sur trois lignes, sans défilement horizontal), mode présentation (hauteur 144 px, aller-retour), alignement des harmoniques sur les tours des pistes au zoom maximal, retour à la forme d'onde (80 px, couleurs d'origine), « Tout afficher », infobulle, trace prise sur le second moteur en comparaison. Défaut corrigé pendant la vérification : graduations 250 Hz et 500 Hz superposées (250 Hz retirée).

Tests : `tests/test_app_spectrogramme.py` (15). Suite complète : 536 réussis, 12 ignorés, 3 lents exclus.

## Catégorie principale des erreurs et moteurs non retenus (décisions du cockpit du 02/11, retours de B8, B9 et E8)

### Catégories des erreurs, sur le temps (option b, décision du cockpit du 02/11)

Une seule définition, dans `app/sortie.py` (`ERROR_CATEGORIES`, `main_category`, `error_map`), reprise par la carte « Expliquer cette erreur » et par l'analyse A-0003. La catégorisation se fait sur le temps. Chaque segment d'erreur de la carte (sans collar) est découpé aux bords des intervalles de ±0,25 s autour des frontières de tour de la référence. Ces intervalles sont construits par pyannote.metrics lui-même (`extrude`, `collar=0.5`, comme pour le DER avec collar). La partie dans ces intervalles est un « décalage de frontière ». Le reste reçoit la première catégorie vraie dans l'ordre ci-dessous, évaluée sur ce reste :

| Rang | Catégorie | Règle, sur la partie hors tolérance |
|---|---|---|
| 1 | Décalage de frontière | La partie dans ±0,25 s d'une frontière de tour de la référence, ce que pardonne le collar |
| 2 | Chevauchement | Elle recoupe un chevauchement de la référence |
| 3 | Locuteur de référence non apparié | Le locuteur de référence de la zone (parole manquée, confusion) n'est apparié à aucun locuteur trouvé |
| 4 | Locuteur trouvé en trop | Le locuteur trouvé de la zone (fausse alarme, confusion) n'est apparié à aucun locuteur de la référence |
| 5 | Tour court | Elle recoupe un tour de la référence de moins de 0,5 s |
| 6 | Pause courte | Elle recoupe une pause de la référence de 1 s au plus, ou la touche à 0,05 s près |
| 7 | Autre | Aucune des précédentes |

Conséquence de la règle : un tour de moins de 0,5 s, ou une pause de 0,5 s au plus, tient entièrement dans la tolérance de ses propres frontières. « Tour court » est donc toujours vide, et « pause courte » ne compte que les pauses de plus de 0,5 s à 1 s. Ces contextes restent écrits dans les constats de la carte.

La zone garde une seule catégorie affichée, celle de sa partie hors tolérance. Une zone entièrement dans la tolérance est un « décalage de frontière ». La carte affiche la catégorie et sa phrase (« Hors de la tolérance d'une frontière : … » quand une partie y est), puis « Dont x s dans la tolérance d'une frontière (pardonnés par le collar) », puis les autres constats sur toute la zone. Le constat « un de ses bords est à 0,25 s au plus d'une frontière » est remplacé par cette part. Données par zone : `tolerance_s`, `contexte_hors_tolerance` (None si la zone tient dans la tolérance), `categorie`.

Sommes : `error_map(...)["categories"]` donne, par type d'erreur, les secondes de chaque catégorie, cumulées segment par segment comme les totaux. Elles partitionnent l'erreur et redonnent les composantes du DER sans collar, à 10⁻¹² s près (ordre des additions en virgule flottante ; égalité stricte sur des durées exactes en binaire).

Contrôle : « décalage de frontière » égale, en secondes et type par type, l'erreur retirée par le collar (composantes sans collar moins composantes avec collar).

| Cas | Décalage de frontière | Erreur retirée par le collar | Écart résiduel |
|---|---|---|---|
| 3 cas construits (frontières décalées, zones longues qui débordent des tolérances, chevauchement, locuteur en trop) | égal | | moins de 10⁻⁹ s (test) |
| SUMM-RE 007a_ECRH, sortie d'EXP-0007, toute la durée, sans UEM (comme l'interface) | 45,959 s manquée, 76,289 s fausse alarme, 33,377 s confusion ; 155,625 s en tout | idem | nul, type par type (test) |
| 200 paires d'annotations aléatoires | | | nul dans 189 cas ; jusqu'à 2,09 s dans les 11 autres, tous ceux où le DER avec collar choisit un autre appariement des locuteurs (test : égalité exigée dès que l'appariement est le même) |

L'égalité ne tient que si le collar ne change pas l'appariement optimal. Sinon, l'erreur hors tolérance change aussi et aucune catégorisation de l'erreur sans collar ne peut la retrouver. Sur 007a_ECRH, l'appariement est le même.

Répartition sur 007a_ECRH, en part de l'erreur sans collar (227,5 s) : décalage de frontière 68,4 % (155,6 s), autre 15,6 % (35,6 s), chevauchement 10,9 % (24,8 s), pause courte 5,1 % (11,6 s), tour court et locuteurs non appariés 0. Zones affichées : 870 en décalage de frontière, 131 autre, 105 chevauchement, 64 pause courte. On compare en secondes et non en points de DER : le collar retire aussi 409 s de parole de référence du dénominateur (DER 19,15 % sans collar, 9,23 % avec).

Règle remplacée (02/11, avant l'option b) : catégorie par zone entière, « décalage de frontière » seulement si toute la zone tenait dans la tolérance. Sur 007a_ECRH, elle classait 47,5 s en décalage de frontière, contre 155,6 s retirées par le collar.

### Moteurs absents de `configs/demo.yaml`

Un moteur absent de `moteurs` n'est plus refusé : il n'est pas proposé, et l'en-tête le dit (« Non retenu pour la démonstration : Baseline WeSpeaker »). Seuls l'absence du moteur par défaut (`moteur_par_defaut`, ou `pyannote-community-1` si la clé manque) et un fichier incohérent arrêtent le lancement. Le chemin du fichier passé à `--config-demo` se coupe désormais dans l'en-tête (il élargissait la page à 409 px sur un écran de 375 px).

Vérifié dans le navigateur, moteur factice, 007a_ECRH avec sa référence et une configuration sans la baseline WeSpeaker : carte en sombre à 1280 px, en clair à 375 px (largeur de page 375 px), quatre catégories rencontrées (décalage de frontière, chevauchement, pause courte, autre), en-tête et liste des moteurs (Baseline MFCC, Baseline ECAPA, pyannote).

Tests : `tests/test_app_categories.py` (10 depuis l'option b), tests du gel (`test_app_presentation_gel.py`, 3 nouveaux) et de la carte mis à jour. Suite complète après l'option b : 548 réussis, 12 ignorés, 3 lents exclus.

## Système visuel et contrôle automatique (chantier B10, audit visuel du 02/11, §3, §4 et §7)

### Jetons, thème et feuilles de style

| Élément | Règle | Où |
|---|---|---|
| Jetons | Seul endroit où figurent des valeurs de couleur, d'ombre, d'arrondi et d'espacement : teintes neutres, bord des contrôles (`--ws-control-line`, au moins 3:1 sur les trois fonds, WCAG 1.4.11), arrondis (carte 12 px, contrôle 8 px, marque, pilule, rond), ombre des cartes (filet en sombre), anneaux et filets nommés, espacement de 4 et 8 px, hauteur des contrôles (32 px ; 40 px en présentation ; 44 px sur écran tactile), mouvement. Redéfinis sous `.dark` et en mode présentation ; les jetons composés (anneaux, filets) sont déclarés sur `:root, .dark` pour être recalculés dans chaque mode | `app/static/jetons.css` |
| Injection | Les jetons, les règles globales (mouvement réduit, écran tactile) et les correctifs des radios et des cases sont placés dans `<head>` par `launch(head=…)`, l'équivalent en chaîne de `head_paths` : Gradio ne les réécrit pas. Le reste passe par `css` | `theme.head`, `app.page_head` |
| Thème | Chacune des 104 variables du thème qui ont une variante `_dark` dans Gradio 6.31 est définie dans les deux modes, avec le même jeton (`var(--ws-…)`), qui change de valeur sous `.dark`. Aucune ombre sur les contrôles. Grille d'espacement `gr.themes.Size(2, 4, 4, 8, 8, 12, 16 px)`, arrondis par jetons | `theme.WITH_DARK`, `theme.WITHOUT_DARK` |
| Radios et cases (V1) | Ronds et cases non cochés bordés de `--ws-control-line` (3,1:1 au moins en clair, 3,4:1 en sombre) ; ni ombre ni liseré ; point du radio coché de la couleur du fond (`radio_circle` en `radial-gradient` sur `var(--background-fill-primary)`). La variable n'étant lue que sous `.gradio-style`, une règle de `jetons.css` l'applique aux radios de l'application (sinon, la feuille de réinitialisation de Gradio impose un SVG blanc, invisible en sombre). Coche des cases de la couleur du fond en sombre | `theme.py`, `jetons.css` |
| Focus | Anneau de 2 px à l'encre, décalé de 2 px, sur tous les contrôles ; rendu aux radios et cases sur leur étiquette (`label:has(input:focus-visible)`), Gradio le retirant de l'entrée | `interface.css` |
| Feuilles | `interface.css` et `visualiseur.css` n'emploient que des jetons : aucune couleur, ombre ni arrondi en dur, aucun sélecteur `svelte-*`, pas de `:root` ni de `body`, aucune règle `@` autre que `@media`, `@keyframes` et `@font-face`, mode sombre par `.dark` seulement | stylelint et `tests/test_app_systeme_visuel.py` |
| Canevas et wavesurfer | Couleurs lues dans les jetons au rendu (`token('--ws-wave')` …), plus de valeurs en dur dans `visualiseur.js` | `visualiseur.js` |

Corrigés en passant : la coche des étapes terminées n'apparaissait pas, car la réécriture du CSS par Gradio perd le raccourci `border: solid var(…)` (propriétés détaillées désormais) ; les jetons composés gardaient les teintes claires en sombre.

### Composants communs

| Composant | Classe | Emploi |
|---|---|---|
| Bouton secondaire | `ws-btn` | « Tout afficher », « Annuler la dernière fusion », « Image PNG de la timeline », notes et sources de l'Avancement ; contour fin, pas d'ombre |
| Bouton principal | `ws-btn ws-btn-primary` (et le bouton « Analyser » de Gradio, même thème) | Un seul par écran |
| Bouton-icône | `ws-btn ws-btn-icon` | 32 px de côté (44 px sur écran tactile), icône SVG de 16 px en `currentColor`, nom accessible par `aria-label` : extraits ▶ du tableau des locuteurs et du plus long monologue, zoom − et +, aide « ? », fermeture de l'explication. Triangle ▶ centré sur son centre de gravité, soit 1,2 px à droite de sa boîte (V4) | 
| Interrupteur | `ws-btn ws-switch` + `aria-pressed` | « Suivre la lecture », « Énergie et seuil », « Mode présentation » : curseur à gauche ou à droite et contour renforcé, l'état ne repose pas sur la seule couleur |
| Contrôle segmenté | `ws-segmented` | Forme d'onde / Spectrogramme |
| Encadrés | `ws-callout` (information : fond discret) ; `ws-attention` (attention : filet gauche et icône « ! ») | Les encadrés existants sont ramenés à ces deux styles (annonce de durée, avertissements, erreur d'analyse, écarts du Pipeline, portée du DER, fusions, constats, aide des raccourcis, « Expliquer cette erreur ») |
| Bouton lecture | `ws-btn wsp-play` | Icône et libellé (« Lecture » ou « Pause ») ; largeur fixe |

Icônes : `app/icones.py`. Tableau des locuteurs (V2) : séparateur porté par la ligne (`border-collapse`), toutes les cellules centrées verticalement ; le filet est continu d'un bord à l'autre.

### Nombres en français

`app/formatage.py`, seule fonction de formatage des nombres affichés : virgule décimale, espace fine insécable (U+202F) entre les milliers et devant les unités et `%`, signe moins typographique, unités françaises (`duree` : « 2 min 05 s » ; `taille` : « 7,2 Ko », « 3,4 Mo »). Employée par les tableaux, les textes, le graphique de l'Avancement, la page Pipeline et les messages ; `visualiseur.js` suit la même règle. Jamais pour les fichiers lus par une machine (RTTM, JSON, étiquettes Audacity). Reste à faire (B11, V11) : les tailles des exports, affichées par le composant de fichiers de Gradio (« 7.2 KB »).

### Contrôle automatique

Outils Node de développement, en `devDependencies` de `tests/visuel/package.json` (`@playwright/test` 1.56.1, `@axe-core/playwright` 4.11.0, `stylelint` 16.25.0, versions exactes, `package-lock.json` versionné) ; rien dans `pyproject.toml` ni `uv.lock`. Navigateur : le Chrome installé (`channel: 'chrome'`) ; à défaut, `npx playwright install chromium` puis `PW_CHROMIUM=1`. Playwright lance lui-même l'application en mode factice (port 7872) sur une réunion de synthèse sans donnée de corpus (`tests/visuel/preparer.py` : audio de 90 s, 4 locuteurs, référence à 5 locuteurs).

```bash
cd tests/visuel && npm ci
```

```bash
cd tests/visuel && npm run controle
```

| Commande (dans `tests/visuel`) | Contrôle |
|---|---|
| `npm run styles` | stylelint (`.stylelintrc.json`) : couleurs (`color-no-hex`, `color-named`, fonctions `rgb()`…), ombres et arrondis seulement par jetons, règles `@` permises, pas de `prefers-color-scheme`, pas de `:root`, `body` ni `svelte-*` ; `jetons.css` est la seule exception pour les valeurs |
| `npm run captures` | 20 captures de référence (`tests/visuel/references/`) : clair et sombre × 1440 et 375 px, plus le mode présentation (sombre, 1280 × 720), sur les quatre onglets ; Analyse et Pipeline en pleine page, Avancement et Glossaire sur la hauteur de l'écran. Écart toléré : 20 pixels (les captures sont identiques d'un lancement à l'autre ; à 0,2 %, l'absence de la coche des étapes passait inaperçue). Masqués : forme d'onde et vue d'ensemble, durées mesurées, bandeau (périphérique), temps et exports, indicateur des moteurs. Vérifie aussi qu'aucune page ne déborde en largeur |
| `npm run captures:maj` | Régénère les références qui sortent de la tolérance (`--update-snapshots=changed`) après un changement voulu, à relire avant de les commiter ; `=all` réécrirait aussi les captures qui ne diffèrent que d'un pixel d'anticrénelage |
| `npm run accessibilite` | axe-core, règles WCAG 2.0, 2.1 et 2.2 A et AA, en clair et en sombre, sur les quatre onglets après une analyse. Une seule exclusion : la taille des cibles (2.5.8) sur les segments de la timeline, dont la largeur est la durée représentée (exception « présentation essentielle » ; le zoom les agrandit et ← → parcourent les tours au clavier) |
| `npm run controle` | Les trois à la suite |
| `npm run defauts:avant`, `npm run defauts:apres` | Captures des défauts V1, V2 et V4, hors références (`tests/visuel/defauts/`, non versionné) |

Résultat au 02/11 : stylelint sans écart ; axe-core sans violation dans les deux modes ; 20 captures de référence (4,9 Mo). Les captures avant et après des défauts V1, V2 et V4 sont dans `docs/audit/b10-avant-apres/`. Tests Python : `tests/test_app_systeme_visuel.py` (couverture des variantes sombres, jetons employés tous définis, jetons composés, règles des feuilles, contrastes WCAG AA, composants, icône, formatage).

## Onglet Analyse : finitions (chantier B11, audit visuel du 02/11, §5)

| Défaut | Correction | Où |
|---|---|---|
| V3 | Identifiant du moteur sous le nom seulement quand le locuteur a été renommé | `_stats_html` |
| V5 | Barre d'outils en groupes qui reviennent à la ligne en entier : lecture (bouton, temps, pastilles) ; vue (Forme d'onde / Spectrogramme, Suivre la lecture, Énergie et seuil) ; zoom (−, curseur, +, Tout afficher) ; aide « ? » à droite. Sous 640 px : deux lignes (lecture et aide, puis la vue, en libellés courts « Onde », « Spectre », « Suivre », le long restant le nom accessible) ; zoom et « Énergie et seuil » repliés derrière une loupe (`aria-expanded`). Mode présentation : une ligne à 1280 px | `VIEWER_TEMPLATE`, `visualiseur.css`, `visualiseur.js` |
| V6 | Configuration et moteur en vigueur dans un panneau « Détails » replié, sous l'en-tête, composant à part (le redessin de l'en-tête pendant le préchauffage ne le referme pas). Mode présentation : en-tête réduit au titre et à l'interrupteur | `_header_html`, `_details_html` |
| V7 | Statut collé à son étape (« Détection de parole · terminé ») ; trois colonnes de même largeur, lues de haut en bas ; une fois l'analyse réussie, liste repliée en une ligne dépliable (« 7 étapes terminées en 3 s ») | `_status_html` (`done_s`) |
| V8 | Avant toute analyse, une seule carte « Comment ça marche » à droite (trois étapes, ce qu'on obtiendra, bouton vers l'onglet Pipeline) ; l'état et les résultats apparaissent au lancement | `_howto_html`, `results_col` ; `data-ws-tab` dans `glossaire.js` |
| V9 | Étiquettes de la référence courtes : « SPK_A → S1 » (S1 : rang du locuteur trouvé, comme les touches 1 à 9 et les codes Audacity), « SPK_E → aucun » ; nom complet en infobulle ; colonne des noms à sa largeur normale | `_reference_group` (`titre`) |
| V10 | « 12,96 % ; pas de chevauchement dans la référence » au lieu de « —  en chevauchement » ; deux styles d'encadré seulement (B10) | `_zone_text` |
| V11 | Exports en liste HTML : lien de téléchargement, nature et taille en français (« JSON, fiche de reproductibilité · 8,8 Ko ») | `_exports_html` |
| V13 | Textes d'aide repliés sous « Comment lire ce tableau » (Locuteurs, Interactions, matrice, Évaluation, Appariement, image) ; masqués en mode présentation | `_how_to_read` |
| « Nouvelle analyse » | Largeur de son libellé et marges propres, aussi en mode présentation | `interface.css` |

Retours de B10 appliqués : la bordure des champs de saisie (thème `input_border_color`, nom des locuteurs, liste de fusion) prend le jeton `--ws-control-line`, à 3:1 au moins face à la carte, dont le fond est le même ; un test vérifie que RTTM, JSON et étiquettes Audacity gardent point décimal, tiret ASCII et aucune espace fine.

Vérifié avec les captures Playwright (`tests/visuel/avant-apres-b11.spec.ts`, `ETAT=avant|apres`) : 1440 px en clair, 375 px en sombre, mode présentation 1280 × 720 ; avant et après dans `docs/audit/b11-avant-apres/`. Captures de référence mises à jour pour ces changements voulus (l'en-tête change sur les quatre onglets), puis contrôle complet sans écart (stylelint, 20 captures, axe-core en clair et en sombre). Tests : `tests/test_app_analyse_b11.py` (9).

## Onglet Pipeline : schéma de gauche à droite (chantier B12, audit visuel du 02/11, §6)

| Élément | Comportement | Où |
|---|---|---|
| Schéma | SVG unique, mis à l'échelle de la carte (1 180 unités de large) : sans retour à la ligne dès 840 px, lisible à 1280 × 720 ; texte coupé en Python avec les tailles du mode présentation, pour tenir dans les deux modes | `pipeline._diagram` |
| Onglets | Chaque étape est un `role="tab"` (avec `aria-selected`, `aria-controls`, tabulation itinérante) d'un `role="tablist"` ; ← → ↑ ↓, Origine et Fin, activation immédiate ; fiche de l'étape en `role="tabpanel"` sous le schéma, pleine largeur ; focus au clavier par un contour épaissi | `pipeline.js` |
| Anatomie d'une étape | Numéro, titre, modèle (architecture, sinon nom du dépôt) et révision abrégée, aperçu de 24 px, badge d'erreurs du DER en texte (« manquée · fausse alarme », « confusion ») ; nombre de constats en haut à droite | `pipeline._box` |
| Flèches | Étiquetées par la forme des données en sortie de l'étape, d'après la section `formes` du catalogue : modèle à trous dont chaque `{réglage}` est lu dans la configuration effective (dans le code pour la normalisation), mis en forme comme le tableau des réglages. Un réglage absent laisse l'étiquette générique, et l'écart est signalé avec les autres (baseline MFCC : pas de dimension d'empreinte) ; à défaut de section dans le catalogue de `--depot`, celle de ce code | `catalogue.yaml` (`formes`), `pipeline._shapes` |
| Un seul réseau | pyannote : détection et segmentation, deux sous-blocs numérotés (2, 3) dans un cadre « Un seul réseau : PyanNet », un seul onglet ; baseline : étapes séparées | section `regroupements` du catalogue |
| Évaluation | À droite, derrière un filet pointillé, flèche pointillée depuis la sortie, cadre pointillé, « mesure seulement » | |
| Naissance des erreurs | DER test sans collar de l'expérience source (`results_<corpus>_test.json`), empilé avec les motifs de la carte des erreurs (plein, hachures, contour) ; chaque segment est un bouton qui sélectionne l'étape où l'erreur naît (parole manquée et fausse alarme : détection ; confusion : regroupement) ; légende écrite et mention « Attribution simplifiée » | `pipeline._errors_bar` |
| Aperçus | Schématiques et statiques (la page n'a pas les données d'un fichier) : forme d'onde, trames, marche-arrêt de la détection, nuage de vecteurs, tours ; couleurs des locuteurs (jetons `--ws-spk-1` à `3`) pour la segmentation et le regroupement seulement | `pipeline._preview` |
| 375 px | Liste numérotée verticale, une étape dépliée à la fois (`aria-expanded`), réglages en liste « clé : valeur », forme des données entre deux étapes | `pipeline._stepper` |
| Mode présentation | Texte du schéma agrandi, révisions masquées, barre de la naissance des erreurs en tête de page et plus haute | `interface.css` |

Retours de B11 : l'indicateur du préchauffage reste dans l'en-tête en mode présentation ; le panneau « Détails » garde l'état ouvert ou fermé que la personne lui a donné quand il est redessiné au changement de moteur (`DETAILS_JS`).

Vérifié dans le navigateur, pyannote et baseline ECAPA : clair et sombre à 1440 px, sombre à 375 px, mode présentation (1280 × 720) ; clavier (flèches, Origine, Fin, Maj + Tab vers l'onglet sélectionné), segment de la barre qui sélectionne l'étape, une étape dépliée à la fois à 375 px. Captures avant et après : `docs/audit/b12-avant-apres/` (`tests/visuel/avant-apres-b12.spec.ts`). Captures de référence mises à jour pour ces changements (pages Pipeline, indicateur du préchauffage en présentation) ; stylelint, 20 captures et axe-core (clair, sombre) sans écart. Tests : `tests/test_app_pipeline_b12.py` (13).

Le catalogue (`src/whospoke/pipelines/catalogue.yaml`) fait partie de l'empreinte du code des moteurs : le cache des résultats est invalidé une fois.
