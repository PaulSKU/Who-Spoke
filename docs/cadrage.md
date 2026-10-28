# Cadrage du projet « Who Spoke? »

Document de travail, version 0.3 du 27 octobre 2026 (précisions du tuteur intégrées). Destination : `docs/cadrage.md` du dépôt, à l'initialisation.

**Statut.** Décisions D1 à D15 actées le 27/10/2026. Restent ouverts : le choix de la seconde amélioration de D9 (fin S1), la confirmation de D12 au premier prototype, et D14 (S3).

**Contraintes de la cible** (réponses du tuteur et de la candidate, 27/10). Les fichiers de test sont en français, en conditions variées, avec un nombre de locuteurs inconnu et variable. Ils sont remis au moment de la démonstration, en direct sur la machine de la candidate, avec accès réseau. Le tuteur peut aussi cloner le dépôt et tester lui-même. Le système doit estimer seul le nombre de locuteurs.

**Précisions du tuteur** (27/10, après-midi). Le cas d'usage est la réunion : majoritairement en français, mono, 2 à 6 personnes, conditions variées (salle avec un seul micro et de l'écho, visio, un peu de bruit), de quelques minutes à une demi-heure. La démonstration doit tourner en local (souveraineté des données). La comparaison principale porte sur les solutions open source locales ; un service cloud payant (pyannoteAI, AssemblyAI…) est un bonus apprécié. Les GPU externes (Colab, Kaggle) sont autorisés pour l'entraînement et les expériences, mais les temps d'inférence doivent être donnés sur la machine de la candidate, idéalement aussi en CPU seul. Le tuteur recommande de partir des modèles pré-entraînés, d'utiliser AMI en micro de salle plutôt qu'en micro-casque, VoxConverse pour la variété, Simsamu, et surtout 2 ou 3 conversations françaises consenties annotées à la main (environ 30 min), ainsi que l'augmentation de données en cas d'ajustement fin.

**Légende de confiance.** **[certain]** : vérifié sur une source primaire le 27/10/2026. **[probable]** : source secondaire, ou connaissance établie non revérifiée. **[incertain]** : à vérifier avant de s'appuyer dessus.

---

## 0. Vue d'ensemble

| ID | Décision | Recommandation | Quand | Dépend de |
|---|---|---|---|---|
| D1 | Protocole d'évaluation | DER sans collar, chevauchements comptés (principal) ; collar 0,25 s (secondaire) ; JER ; RTF | J1 | — |
| D2 | Corpus de référence anglophones | AMI (partition BUT, Mix-Headset) + VoxConverse | J1–J2 | — |
| D3 | Corpus francophone (**jeu de validation prioritaire**) | SUMM-RE (sous-ensemble dev/test) + 2 à 3 enregistrements maison consentis + Simsamu (contrôle téléphonique) | J2 | — |
| D4 | Partition et prévention des fuites | Partitions officielles, réglages sur dev uniquement, test gelé, contamination des modèles documentée | J2 | D2 |
| D5 | Condition acoustique AMI | **SDM (micro de salle) en principal** ; Mix-Headset seulement comme point de comparaison (révisé le 27/10) | J2 | D2 |
| D6 | Pipeline existante | Comparaison principale entre solutions open source locales : pyannote.audio 4 / community-1 obligatoire, NeMo en essai borné ; cloud payant en bonus | J2 | V5, V6 |
| D7 | Baseline classique | VAD par énergie + MFCC + fenêtres glissantes + clustering agglomératif | S1 | D1 |
| D8 | Embeddings neuronaux | ECAPA-TDNN (SpeechBrain) à la place des MFCC, reste inchangé | S2 | D7 |
| D9 | Axes d'ablation | Diagnostics « oracle » ; amélioration n° 1 imposée : estimation du nombre de locuteurs ; amélioration n° 2 choisie sur résultats | fin S1 | D7, D8 |
| D10 | Environnement Python | uv, Python 3.11, versions figées ; environnement séparé pour NeMo | J1 | V1–V4 |
| D11 | Suivi d'expériences | Maison : YAML + `results.json` + `leaderboard.csv` | J1 | — |
| D12 | Démonstration | Gradio, exécution locale | S2 | premier prototype |
| D13 | Données dans git | Jamais d'audio ; manifestes avec sommes de contrôle et scripts de téléchargement | J1 | — |
| D14 | Licence du dépôt | Licence libre pour le code ; données régies par leurs propres licences | S3 | D3 |
| D15 | Robustesse d'entrée et portabilité | Normalisation de tout audio en 16 kHz mono ; choix automatique CPU/CUDA/MPS ; modèles en cache ; installation testée sur environnement vierge | S1 puis S3 | V5 |

---

## 1. Décisions

### D1 — Protocole d'évaluation

**Enjeu.** Le DER (Diarization Error Rate) est le rapport entre la durée totale des erreurs et la durée totale de parole de référence. Les erreurs sont de trois types : parole manquée (*missed detection*), fausse alarme (*false alarm*) et confusion de locuteur (*speaker confusion*). Avant le calcul, les étiquettes du système (`SPK_0`, `SPK_1`…) sont appariées aux locuteurs de référence par une affectation optimale. Le système n'a donc pas à trouver les noms, seulement à grouper correctement. Deux paramètres de protocole modifient fortement le chiffre obtenu sur des sorties identiques.

Le *collar* est une zone de tolérance de ± t secondes autour de chaque frontière de référence, exclue du calcul. Il compense l'imprécision des annotateurs. Avec 0,25 s, les erreurs de frontière disparaissent largement. Sans collar, elles comptent intégralement.

Le traitement des chevauchements est le second paramètre. Dans une zone où deux personnes parlent, un système qui ne produit qu'un locuteur commet une parole manquée pour l'autre. Exclure ces zones du calcul (`skip_overlap`) avantage les systèmes qui ignorent le chevauchement, alors que le sujet demande justement d'étudier ce phénomène.

**Conventions existantes.** Le benchmark publié de pyannote utilise le réglage le plus strict : pas de collar, chevauchements comptés **[certain]**. La littérature sur VoxConverse rapporte souvent un collar de 0,25 s **[probable]**. Un comparatif récent note qu'un même système voit son DER sur VoxConverse presque divisé par deux selon la présence d'un collar **[probable, source secondaire]**.

**Métriques complémentaires.** Le JER (Jaccard Error Rate) calcule l'erreur par locuteur puis en fait la moyenne. Chaque locuteur pèse donc autant, quelle que soit sa durée de parole, ce qui pénalise l'oubli d'un locuteur minoritaire que le DER, pondéré par le temps, masque. Le RTF (Real-Time Factor) est le rapport entre le temps de calcul et la durée de l'audio.

**Recommandation.** La métrique principale est le DER sans collar, chevauchements comptés, décomposé en ses trois composants. La métrique secondaire est le DER avec collar de 0,25 s, chevauchements comptés, pour la comparabilité avec la littérature. S'y ajoutent le JER, le RTF et, en analyse, le DER calculé séparément sur les zones avec et sans chevauchement. L'implémentation de référence est `pyannote.metrics`, avec une vérification croisée unique sur quelques fichiers contre `dscore` (outil utilisé pour DIHARD) **[probable]**. Le protocole est figé dans `docs/protocole-eval.md` avant tout calcul.

### D2 — Corpus de référence anglophones

**AMI.** Environ 100 h de réunions en anglais, enregistrées avec micros-casques et micros distants **[certain]**. Les deux tiers sont des réunions scénarisées à quatre participants autour de la conception d'une télécommande **[certain]**. Les signaux et transcriptions sont publiés sous CC BY 4.0 sur le site officiel **[certain]**. Le miroir OpenSLR affiche une licence différente (CC BY-NC-SA 2.0 modifiée) **[certain]** : la référence à citer est le site d'Édimbourg. Les annotations natives sont au format NXT, au niveau du mot. La conversion en RTTM n'est pas triviale, et le dépôt `BUTSpeechFIT/AMI-diarization-setup` fournit les partitions et RTTM standard (variante *only_words*) utilisés par le benchmark pyannote **[probable]**.

**VoxConverse.** Plus de 50 h d'extraits YouTube (débats politiques, journaux), choisis pour leur taux de chevauchement **[certain]**. Licence CC BY 4.0, mais le droit d'auteur des vidéos reste aux propriétaires d'origine **[certain]**, d'où l'interdiction de redistribuer l'audio. La partition dev compte 216 fichiers et la partition test 232, soit environ 7,3 Go dans la version Hugging Face **[certain]**. Le nombre de locuteurs varie d'un fichier à l'autre (jusqu'à une vingtaine) **[probable]**.

**Pourquoi les deux.** AMI représente des réunions à quatre participants, longues, en salle. VoxConverse représente des contenus médiatiques à nombre de locuteurs variable et fort chevauchement. Leur contraste permet d'analyser la robustesse, ce qu'un seul corpus ne permet pas.

**Recommandation.** Utiliser AMI via la partition BUT, à partir des 16 réunions de test officielles (EN2002, ES2004, IS1009, TS3003, sessions a à d) **[probable]**, et VoxConverse via ses partitions officielles. Pour le dimensionnement sur le M2 Pro, mesurer le RTF de pyannote en V5 avant de fixer les volumes. Ne pas télécharger AMI en entier.

### D3 — Corpus francophone

**Enjeu.** L'évaluation porte sur des enregistrements inconnus, en français (Q1), dans des conditions différentes de celles d'AMI ou de VoxConverse. C'est le principal risque du projet. Il faut au moins un jeu de test hors domaine proche de la cible probable.

**SUMM-RE.** Environ 95 h de conversations spontanées de type réunion en français, dont 25 h de transcriptions corrigées manuellement et alignées sur le signal **[certain]**. Licence CC BY-SA 4.0 **[certain]**, publiée sur Hugging Face par LINAGORA **[certain]**. Le corpus fournit une piste audio par locuteur **[certain]**. Il faut donc reconstituer le mélange en sommant les pistes, ce qui donne une condition proche du « mix de casques » d'AMI, et dériver le RTTM des alignements. La précision des frontières pour la diarisation n'est pas documentée pour cet usage **[incertain]**. La clause SA impose de partager sous la même licence toute annotation dérivée que l'on redistribuerait **[probable]**.

**Autres pistes françaises.** ALLIES (environ 500 h de radio et télévision, avec un protocole d'évaluation de la diarisation) **[certain pour la description]**, mais ses conditions d'accès n'ont pas été vérifiées **[incertain]**. REPERE et les corpus LDC (CALLHOME, DIHARD) sont payants ou soumis à licence **[probable]** et sont à écarter pour un projet de trois semaines.

**Corpus maison.** Deux ou trois enregistrements de 5 à 10 minutes, à 2 à 4 locuteurs, dans des conditions proches de la cible (téléphone posé sur une table, salle de réunion). Annotation manuelle avec Audacity (pistes de labels) ou ELAN, puis export en RTTM. Le coût d'annotation est élevé, plusieurs fois la durée de l'audio **[incertain sur le ratio exact]**. Il faut donc rester petit. La voix enregistrée est une donnée personnelle au sens du RGPD **[certain]**. Sa qualification en donnée biométrique dépend de la finalité d'identification **[incertain]**. Prévoir un formulaire de consentement, un stockage local et aucune redistribution.

**Décision (actée).** Le jeu francophone est le jeu de validation prioritaire : toute décision de réglage finale doit y être confirmée. Il se compose de SUMM-RE (sous-ensemble dev pour le réglage, test pour l'évaluation française) et de deux ou trois enregistrements maison réalisés par la candidate. Ces derniers servent de test de généralisation et de matériel de démonstration. Leurs conditions et leurs nombres de locuteurs doivent différer d'un enregistrement à l'autre pour refléter la variabilité annoncée de la cible. Chaque participant signe un consentement écrit d'une demi-page, conservé hors dépôt et mentionné dans `corpus.md`. Les RTTM n'emploient que des identifiants anonymes.

### D4 — Partition et prévention des fuites

**Enjeu.** Une fuite survient quand une information du jeu de test influence le système. Trois formes sont pertinentes ici. La première est un même enregistrement présent dans deux partitions. La seconde est le réglage d'hyperparamètres (seuil de clustering, VAD) sur le test. La troisième, la plus insidieuse, est la contamination des modèles pré-entraînés : le modèle de segmentation de pyannote a été entraîné sur un mélange de corpus incluant notamment AMI et VoxConverse **[probable, à vérifier sur la fiche du modèle]**. Évaluer pyannote sur une partition qu'il a vue à l'entraînement surestimerait sa performance.

Le recouvrement de locuteurs entre partitions compte surtout si l'on entraîne ou affine un modèle de locuteurs. En inférence seule, il compte moins. La partition officielle d'AMI vise à séparer les locuteurs **[incertain, à vérifier]**.

**Recommandation.** Utiliser exclusivement les partitions officielles. Tout réglage se fait sur dev, et le test est évalué une seule fois par configuration retenue. La fiche corpus consigne, pour chaque modèle pré-entraîné, les jeux vus à l'entraînement d'après sa fiche. Les listes de fichiers par partition sont versionnées dans `data/splits/`.

### D5 — Condition acoustique AMI

**Enjeu.** AMI propose notamment le « Mix-Headset » (somme des micros-casques, signal propre) et le SDM (*single distant microphone*, un micro de table, champ lointain avec réverbération). Dans le benchmark pyannote 2.1, le DER passe d'environ 19 % (Mix-Headset) à environ 27 % (SDM), surtout par hausse de la parole manquée **[certain]**. Une table ou un téléphone dans une salle correspond plutôt au SDM.

**Décision (révisée le 27/10, demande du tuteur).** Le SDM (Array1-01) est la condition principale, car il est le plus proche des réunions cibles. Le Mix-Headset ne sert que de point de comparaison, pour isoler l'effet du champ lointain.

### D6 — Pipeline existante

**pyannote.audio.** La version 4.0 fournit le modèle ouvert *community-1*, présenté par ses auteurs comme supérieur à la version 3.1, notamment sur la confusion de locuteurs **[certain]**. Elle requiert Python 3.10 ou plus **[certain]**. Le modèle est soumis à conditions sur Hugging Face : il faut accepter les conditions d'utilisation et créer un jeton d'accès **[certain]**. Les pipelines tournent sur CPU par défaut **[certain]**. L'exécution sur le GPU Apple via MPS est rapportée par plusieurs projets tiers **[probable]**. La licence du modèle est CC BY 4.0 **[probable]**. Le modèle *precision-2* est payant et s'exécute sur les serveurs de pyannoteAI **[certain]** : à n'utiliser qu'avec l'accord des organisateurs (Q5), et jamais comme système principal.

**NVIDIA NeMo.** La documentation officielle indique que, sur Mac à puce Apple, seule la boîte à outils ASR est garantie de fonctionner et recommande un environnement Conda **[certain]**. Les modules de diarisation relèvent de la collection ASR **[probable]**. Sortformer, l'approche bout-en-bout récente de NeMo, est limité à 4 locuteurs **[probable]**. Le point de contrôle hors ligne v1 est sous licence non commerciale, et la version streaming v2 sous CC BY 4.0 **[probable]**.

La pipeline accepte un nombre exact de locuteurs ou des bornes (`num_speakers`, `min_speakers`, `max_speakers`) **[certain]**, ce qui permet les deux modes d'exécution retenus en D9.

**Recommandation.** pyannote 4 / community-1 est la pipeline existante imposée par le sujet. NeMo fait l'objet d'un essai d'installation et d'inférence borné à deux heures (V6). En cas d'échec, l'échec est documenté et l'option d'un GPU distant reste ouverte. DiariZen est une alternative ouverte bien classée dans les comparatifs récents **[probable]**, hors périmètre sauf temps disponible en S3.

### D7 — Baseline classique

**Enjeu.** La baseline sert de point de comparaison explicable. Chaque choix y correspond à un composant du DER.

| Étage | Choix proposé | Paramètres | Composant du DER affecté |
|---|---|---|---|
| Analyse | Trames de 25 ms, pas de 10 ms | — | — |
| VAD | Énergie log par trame, seuil relatif (percentile), lissage et durée minimale | seuil, lissage | Parole manquée, fausse alarme |
| Caractéristiques | 13 à 20 MFCC + dérivées | nombre de coefficients | Confusion |
| Segmentation | Fenêtres glissantes de 1,5 s, recouvrement de 0,75 s (alternative : détection de changement par BIC) | longueur, pas | Confusion, frontières |
| Représentation | Moyenne et écart-type des MFCC par fenêtre | — | Confusion |
| Clustering | Agglomératif, distance cosinus, arrêt par seuil ou nombre fixé | seuil, K | Confusion |
| Nombre de locuteurs | Seuil (inconnu) ou oracle (connu) | — | Confusion |

**Recommandation.** Une version minimale : VAD par énergie, fenêtres fixes et clustering agglomératif. On s'attend à une confusion élevée, et c'est voulu : la comparaison avec D8 rendra visible l'apport des embeddings neuronaux.

### D8 — Embeddings neuronaux

**Enjeu.** Isoler l'effet de la représentation des locuteurs. On remplace les statistiques MFCC par des embeddings ECAPA-TDNN pré-entraînés sur VoxCeleb (SpeechBrain) **[probable pour le modèle disponible]**, en gardant la même VAD, la même segmentation et le même clustering. Toute variation de la confusion est alors attribuable à la représentation.

**Recommandation.** C'est le premier élément d'ablation, et le plus démonstratif.

### D9 — Axes d'ablation

**Diagnostics « oracle ».** Ce sont les outils de compréhension les plus efficaces. On injecte la vérité terrain à un étage pour mesurer l'erreur résiduelle des autres. Avec une VAD oracle (régions de parole de référence), parole manquée et fausse alarme tombent à zéro hors chevauchement, et il ne reste que la confusion due au clustering. Avec un nombre de locuteurs oracle, on mesure ce que coûte son estimation.

**Améliorations candidates** (le sujet en exige au moins deux) : VAD énergie contre VAD neuronale ; balayage du seuil de clustering ; nombre de locuteurs connu contre estimé ; robustesse au bruit par ajout contrôlé à plusieurs SNR ; longueur des fenêtres et segments courts ; traitement du chevauchement (sortie standard contre sortie exclusive de community-1) ; champ proche contre champ lointain (Mix-Headset contre SDM).

**Décision (actée).** Les deux oracles sont inclus systématiquement. L'outil fonctionne par défaut en estimation automatique du nombre de locuteurs, avec un paramètre optionnel pour l'imposer ou le borner. L'amélioration n° 1 porte sur l'estimation du nombre de locuteurs : sur des fichiers hétérogènes, c'est la source d'erreur la plus probable, puisqu'une sous-estimation fusionne deux personnes et qu'une surestimation en scinde une. L'écart entre le mode estimé et le mode oracle en mesure le coût. L'amélioration n° 2 est choisie à la fin de S1, au vu du composant du DER qui domine sur le jeu francophone.

**Amendement du 28/10/2026 (après EXP-0003 à EXP-0006).** L'amélioration n° 1 est maintenue, mais sous condition. Sur AMI, même un nombre de locuteurs oracle n'apporte rien, ni à la baseline (EXP-0003, EXP-0006) ni à pyannote (EXP-0005). AMI compte toutefois toujours 4 participants, alors que la cible en compte de 2 à 6. Le maintien de cette amélioration dépend donc de son effet sur le jeu francophone (SUMM-RE et corpus maison) : si l'oracle n'y apporte rien non plus, elle sera remplacée par le traitement du chevauchement et de la détection, que les mesures sur AMI désignent comme le principal goulot.

### D10 — Environnement Python

**Recommandation.** uv pour l'environnement principal, avec Python 3.11 (compatible avec l'exigence 3.10+ de pyannote 4 ; compatibilité NeMo **[probable]**) et des versions figées par fichier de verrouillage. NeMo va dans un environnement séparé (Conda, conformément à sa documentation pour Mac) afin de ne pas déstabiliser l'environnement principal. ffmpeg s'installe via Homebrew pour le décodage audio **[probable que pyannote 4 en dépende pour certains formats]**.

### D11 — Suivi d'expériences

**Options.** Outils dédiés (MLflow, Weights & Biases) ou convention maison. Les outils dédiés ajoutent une dépendance et une interface sans bénéfice décisif à cette échelle.

**Recommandation.** Une convention maison : un YAML de configuration, un dossier `experiments/EXP-NNNN_slug/` immuable, un `results.json` à schéma fixe et un `leaderboard.csv` alimenté par le script d'évaluation (voir `docs/methode.md`).

### D12 — Démonstration

**Exigences du sujet.** Charger un audio, lancer l'analyse, afficher une timeline, écouter les segments, exporter en JSON ou RTTM.

**Recommandation.** Gradio, qui offre des composants audio natifs, avec une timeline tracée par Plotly et une exécution locale sur la machine de la candidate (Q2). À confirmer au premier prototype.

### D15 — Robustesse d'entrée et portabilité

**Enjeu.** Les fichiers de démonstration sont inconnus et remis en direct. Le tuteur peut aussi exécuter le dépôt sur sa propre machine, potentiellement sans GPU Apple.

**Décision (actée).** Tout audio entrant est normalisé en 16 kHz mono via ffmpeg, quel que soit son format (mp3, m4a, stéréo, 44,1 kHz…). Le périphérique de calcul est choisi automatiquement (CUDA, puis MPS, puis CPU) et peut être forcé. Les modèles sont téléchargés et mis en cache avant toute démonstration. Le RTF mesuré en V5 permet d'annoncer la durée de traitement d'une heure d'audio. Le README décrit l'obtention du jeton Hugging Face, et une installation complète est testée en S3 dans un environnement vierge.

### D13 — Données dans git

**Recommandation.** Aucun fichier audio dans git (`.gitignore` sur `data/raw/` et `data/processed/`). Un manifeste CSV par corpus (identifiant, source, licence, durée, empreinte SHA-256) et des scripts de téléchargement et de préparation qui reconstruisent les données. Les RTTM dérivés ne sont versionnés que si la licence le permet.

### D14 — Licence du dépôt

**Recommandation.** Une licence libre usuelle (MIT ou Apache 2.0) pour le code, et une section du README renvoyant aux licences propres des corpus et modèles. Décision finale en S3, une fois D3 tranchée, à cause de la clause SA de SUMM-RE.

---

## 2. Questions au tuteur — réponses du 27/10/2026

| Q | Objet | Réponse | Conséquence |
|---|---|---|---|
| Q1 | Enregistrements d'évaluation | En français ; conditions et nombres de locuteurs variés ; détails tenus secrets | D3 devient le jeu de validation prioritaire |
| Q2 | Démonstration | En direct sur la machine de la candidate, fichiers remis sur place, accès réseau probable ; le tuteur peut aussi cloner le dépôt | D15 |
| Q3 | Nombre de locuteurs | Estimé par le système ; mode « nombre imposé » conservé en option | D9 |
| Q4 | Notation | Le tuteur dispose de la vérité terrain ; protocole de calcul non communiqué | Double rapport collar 0 / 0,25 s (D1) |
| Q5 | Services cloud payants | Bonus apprécié, non obligatoire ; comparaison principale avec l'open source local | D6 |
| Q6 | Calcul | Pas de GPU du labo ; Colab ou Kaggle autorisés pour l'entraînement et les expériences ; inférence mesurée en local, en MPS et en CPU seul | Protocole §3.5 |
| Q7 | Consentement | Pas de cadre du labo | Consentement écrit d'une demi-page (D3), exigé par le sujet |
| Q8 | Évaluation du rendu | Qualité de l'outil comparée aux autres candidats, et surtout implication, curiosité, conduite de projet | Journal, décisions et ablation sont des pièces du rendu |
| Q9 | Visibilité du dépôt | Public, privé sur demande | `.env` ignoré dès le premier commit ; aucun nom réel dans les RTTM |

**Question restant à poser.** Les annotations de référence des fichiers de démonstration pourront-elles être transmises après la séance, pour calculer le DER et analyser les cas d'échec dans le rendu ?

---

## 3. Vérifications et actions sur la machine

| ID | Vérification | Commande ou action | Attendu |
|---|---|---|---|
| V1 | Système, mémoire, disque | `sw_vers` ; `sysctl -n hw.memsize` ; `df -h ~` | macOS récent ; mémoire notée ; au moins 30 Go libres **[estimation]** |
| V2 | Outils de base | `xcode-select -p` ; `brew --version` ; `git --version` ; `python3 --version` | Tous présents |
| V3 | ffmpeg et uv | `brew install ffmpeg uv` puis `ffmpeg -version` ; `uv --version` | Installés |
| V4 | PyTorch et MPS | Dans un environnement test : `python -c "import torch; print(torch.__version__, torch.backends.mps.is_available())"` | `True` |
| V5 | pyannote de bout en bout | Compte Hugging Face, acceptation des conditions de `pyannote/speaker-diarization-community-1`, jeton en variable d'environnement `HF_TOKEN` dans un `.env` non versionné ; inférence sur un fichier de 5 min en CPU puis en MPS | RTF mesuré dans les deux cas, consigné au journal |
| V6 | NeMo (borné à 2 h) | Environnement Conda séparé, `nemo_toolkit[asr]`, inférence d'un modèle de diarisation sur le même fichier | Succès ou échec documenté |
| V7 | GitHub | Dépôt `who-spoke` créé ; authentification (`gh auth status`) ; dépôt relié à Claude Code et à ce projet | Accès en lecture et en écriture |
| V8 | Claude Code | `claude --version` ; ouverture dans le dossier du dépôt | Fonctionnel |
| V9 | Longs calculs | Alimentation secteur ; `caffeinate -i <commande>` pour empêcher la mise en veille | — |

---

## 4. Ordre d'exécution proposé

| Moment | Contenu |
|---|---|
| J1 | V1 à V5 ; question résiduelle au tuteur (annotations post-démonstration) ; rédaction de `protocole-eval.md`, `methode.md` et `CLAUDE.md` |
| J2 | V6 ; fiche corpus candidate ; initialisation du dépôt par Claude Code (V7, V8) ; préparation du formulaire de consentement et du protocole d'enregistrement maison |
| S1 (reste) | Téléchargement et préparation des données, enregistrement et annotation du corpus maison, script d'évaluation validé, baseline D7, premiers diagnostics oracle |
| S2 | D8, pyannote et éventuellement NeMo, choix et conduite des ablations D9, premier prototype de démonstration |
| S3 | Améliorations mesurées, robustesse, finalisation de la démonstration, documentation, D14 |

---

## 5. Sources consultées le 27/10/2026

| Sujet | Source |
|---|---|
| pyannote 4.0 / community-1 | pyannoteAI, « Community-1: Unleashing open-source diarization » — https://pyannote.ai/blog/community-1 |
| pyannote, prérequis Python 3.10+ | pyannoteAI changelog — https://www.pyannote.ai/changelog/community-1-now-available |
| pyannote, installation, jeton HF, CPU par défaut | PyPI pyannote.audio 4.0.4 — https://pypi.org/project/pyannote-audio/4.0.4/ ; fiche HF — https://huggingface.co/pyannote-community/speaker-diarization-community-1 |
| Benchmark pyannote 2.1 (protocole sans collar, AMI Mix-Headset et SDM) | https://huggingface.co/pyannote/speaker-diarization |
| AMI, description et licence | https://groups.inf.ed.ac.uk/ami/corpus/ ; https://groups.inf.ed.ac.uk/ami/download |
| AMI, miroir OpenSLR (licence divergente) | https://openslr.org/16/ |
| VoxConverse, description et licence | https://mm.kaist.ac.kr/datasets/voxconverse/ (miroir de la page Oxford) |
| VoxConverse, partitions et volumes | https://huggingface.co/datasets/diarizers-community/voxconverse |
| SUMM-RE | Hunter et al., TALN 2024 — https://talnarchives.atala.org/TALN/TALN-2024/9633.html ; https://huggingface.co/datasets/linagora/SUMM-RE |
| ALLIES | Tahon et al., LREC-COLING 2024 — https://aclanthology.org/people/anna-silnova/unverified/ |
| NeMo sur Apple Silicon | README officiel — https://github.com/NVIDIA/NeMo |
| Sortformer, licences et limite à 4 locuteurs (source secondaire) | https://huggingface.co/mlboydaisuke/Streaming-Sortformer-Diar-CoreAI ; https://huggingface.co/emee-ai/Sortformer-Diarization |
| pyannote sur MPS (sources secondaires) | https://docs.rs/crate/speakrs/latest/source/README.md ; https://github.com/paberr/ownscribe/releases/tag/v0.5.0 |
| Effet du collar sur le DER (source secondaire) | Kili Technology, 2026 — https://kili-technology.com/blog/speaker-diarization-models-guide-benchmarks-and-failure-modes-2026 |
