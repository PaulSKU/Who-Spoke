# Fiche des corpus

Livrable exigé. Version 0.1 du 27 octobre 2026 (fiche candidate, à discuter avec le tuteur). Elle est mise à jour avant tout premier téléchargement d'un corpus (`docs/methode.md` §7). Pour chaque corpus : source, accès, licence, volume, composition, limites, partitions utilisées, règles de construction des RTTM de référence, et jeux vus à l'entraînement par chaque modèle pré-entraîné (`docs/protocole-eval.md` §5).

Les consentements du corpus maison sont conservés hors du dépôt ; cette fiche mentionne seulement leur existence et leur date.

La recherche complète qui fonde cette fiche est dans `docs/recherche/corpus-diarisation-reunions-francais.md`.

**Légende de confiance.** **[certain]** : vérifié sur source primaire. **[probable]** : source secondaire ou non revérifiée. **[incertain]** : à vérifier.

---

## 0. Synthèse

| Corpus | Rôle | Statut | Licence | Volume local visé |
|---|---|---|---|---|
| Corpus maison (M01–M03) | Test français principal (réel, inédit) | Retenu | Consentement des participants | < 0,1 Go |
| SUMM-RE | Validation française ; test français élargi ; ajustement fin éventuel | Retenu | CC BY-SA 4.0 | 2,6 Go (dev + test, mesuré) |
| AMI, micro distant (SDM) | Vérification de reproduction ; robustesse au champ lointain | Retenu | CC BY 4.0 | ~2,2 Go (dev + test) |
| Simsamu | Contrôle : français, téléphone, 2 locuteurs | Retenu | MIT | 0,06 Go |
| VoxConverse | Variété (nombre de locuteurs, conditions) | Candidat | CC BY 4.0 (recherche) | ~2 à 6 Go selon le sous-ensemble |
| NOTSOFAR-1 (monocanal) | Test en champ lointain non contaminé (anglais) | Candidat, question au tuteur | CC BY 4.0 | inconnu |
| OpenSLR 28 + bruits MUSAN | Augmentation (si ajustement fin) | Candidat | Apache 2.0 ; CC BY 4.0 | ~1,9 Go |

---

## 1. Corpus maison

Trois réunions en français enregistrées par la candidate (salle réverbérante, visio, bruit de fond), d'environ 30 minutes au total, de 2 à 6 locuteurs. Protocole, consentement et conventions d'annotation dans `docs/corpus-maison/`. Tout le corpus sert au test ; il est traité uniquement en local.

| Champ | Valeur |
|---|---|
| Consentements | à recueillir (dates à consigner ici) |
| Référence | annotation manuelle selon `docs/corpus-maison/conventions-annotation.md` ; bruit d'annotation mesuré par ré-annotation de 2 minutes |
| Contamination | aucune (enregistrements inédits) |

## 2. SUMM-RE

| Champ | Valeur |
|---|---|
| Source | https://huggingface.co/datasets/linagora/SUMM-RE ; Hunter et al., TALN 2024 |
| Licence, accès | CC BY-SA 4.0, sans restriction d'accès **[certain]** |
| Composition | 283 conversations d'environ 20 min de type réunion, en français, 3 à 4 locuteurs (rarement 2), 207 participants ; 248 en présentiel, 35 en Zoom **[certain, d'après la fiche et l'article]** |
| Partitions | train 210 conversations (~67 h, alignement automatique) ; dev 36 (~12 h) ; test 37 (~12 h) ; dev et test transcrits et alignés à la main d'après la fiche **[certain]** (l'article reste contradictoire pour test) |
| Audio | **pistes individuelles de micros-casques uniquement** (48 kHz, 32 kHz pour Zoom) ; le micro d'ambiance décrit dans l'article n'est pas publié **[probable]** ; 93,8 Go en tout |
| Référence | reconstruite à partir des alignements au mot, avec fusion des pauses de 200 ms ou moins (même convention que le corpus maison), après retrait des jetons non lexicaux SPPAS (amendement 1 de D20) ; UEM du premier mot − 1 s au dernier mot + 1 s (D20 §3) |
| Construction du signal | moyenne des pistes individuelles rééchantillonnées à 16 kHz (D20 §2, proche d'un « mix de casques ») ; une condition réverbérée sera simulée par augmentation (décision distincte) |
| Dérivé disponible | `ggfox00000/dia-summre-test` : les 37 réunions de test en 16 kHz avec RTTM (2,81 Go) ; sa variante dite « far-field » est une moyenne de micros-casques, pas un enregistrement de salle **[probable]** ; ses RTTM gardent les jetons non lexicaux, et ne diffèrent des nôtres que par eux (contrôle croisé ci-dessous) ; jamais utilisé pour noter |
| Limites | pas de champ lointain réel ; 18 locuteurs communs à dev et test (mesuré, voir ci-dessous) : fuite négligeable pour le réglage d'un seuil unique comme θ **[probable]**, mais pas pour un ajustement fin, avant lequel un test sans les locuteurs vus à l'entraînement devra être défini (amendement 4 de D20) |
| Contamination | absent des listes d'entraînement publiées de pyannote segmentation-3.0 et de NeMo Sortformer v2 **[probable]** |
| Téléchargements effectués | Dev et test le 28/10/2026 par `scripts/data/get_summre.py` (D20), dépôt `linagora/SUMM-RE` à la révision `47cb4ec3437ef5497b6092b8c6d1e0b5b1d86dc0` : 57 fichiers Parquet (29 dev, 28 test), 25,8 Go téléchargés, SHA-256 contrôlé contre celui du dépôt puis consigné ; brut supprimé après extraction. Conservés : mélanges 16 kHz et RTTM dans `data/processed/summre/` (2,6 Go), manifeste `data/manifests/summre.csv`, listes `data/splits/summre/{dev,test,temps,zoom_dev,zoom_test}.txt`, UEM dans `data/splits/summre/uem/` |

**Statistiques mesurées (29/10/2026, `get_summre.py --references`, après retrait des jetons non lexicaux).** La parole et le chevauchement sont mesurés dans l'UEM, à partir des références construites selon D20 §3 et l'amendement 1 du 28/10. La part de chevauchement est le temps où au moins deux locuteurs parlent, rapporté au temps où au moins un locuteur parle.

| Jeu | Réunions | Pistes | Locuteurs distincts | Locuteurs par réunion (2 / 3 / 4) | Signal | Parole | Chevauchement |
|---|---|---|---|---|---|---|---|
| dev | 36 | 130 | 81 | 2 / 10 / 24 | 11,89 h | 9,33 h | 12,6 % |
| test | 37 | 124 | 91 | 2 / 20 / 15 | 12,17 h | 9,91 h | 15,7 % |
| dev, Zoom | 5 | 19 | 8 | 0 / 1 / 4 | 1,51 h | 1,03 h | 8,5 % |
| test, Zoom | 3 | 9 | 9 | 0 / 3 / 0 | 0,97 h | 0,65 h | 5,9 % |

Avant le retrait des jetons non lexicaux (préparation du 28/10), la parole valait 9,59 h en dev et 10,02 h en test, et le chevauchement 14,5 % et 17,2 % de la parole.

| Contrôle | Résultat |
|---|---|
| Réunions et pistes | 36 / 130 (dev) et 37 / 124 (test), conformes à la fiche |
| Participants sans parole | aucun : chaque piste contient des mots, et les réunions à 3 participants n'ont que 3 pistes (le cas de la quatrième piste muette ne se présente pas dans dev et test) |
| Temps de parole par locuteur et par réunion | médiane 5,0 min (dev) et 5,2 min (test) ; de 0,2 à 11,5 min (dev), de 0,6 à 25,9 min (test) |
| Locuteurs communs à dev et test | 18 `speaker_id` : 019, 025, 047, 053, 097, 100, 104, 105, 106, 107, 109, 110, 137, 139, 140, 174, 175, 176. Dev et test ne sont donc pas disjoints en locuteurs. Pour le réglage d'un seuil unique (θ de la baseline), la fuite est négligeable **[probable]** ; pour un ajustement fin, elle ne l'est plus : un test sans les locuteurs vus à l'entraînement devra être défini avant tout ajustement fin sur SUMM-RE (amendement 4 de D20) |
| Mots sans horodatage | 0 |
| Jetons non lexicaux SPPAS (`+` pause courte, `*` bruit, `@` rire) | retirés de la référence (amendement 1 de D20) : tout jeton composé uniquement de ces symboles. Inventaire des jetons retirés, par forme exacte : dev `+` 2 285, `@` 1 089, `*` 404 (3 778 sur 152 249 jetons) ; test `@` 1 091, `*` 598, aucun `+` (1 689 sur 153 099). Aucune forme composée (`@@`, `*+`…) ne se présente. Le retrait ôte 2,73 % du temps de parole en dev et 1,11 % en test ; aucun locuteur ne disparaît ; l'UEM change pour 9 réunions (013c, 014c, 017a, 039b, 043a, 072c, 074c, 091b, 093c). Détail par réunion dans le manifeste (`jetons_retires`) |
| Fréquences d'origine | 48 kHz ou 32 kHz (Zoom), et 22,05 kHz pour au moins une piste de 10 réunions (018a, 020b, 027a, 032b, 033a, 033c, 034a, 035b, 036c, 069c), conformément à la liste d'exceptions de la fiche |
| Crête des mélanges | 0,998 au plus : aucun écrêtage |
| Synchronisation (diaphonie, D20 §2) | aucun décalage mesurable supérieur à 50 ms ; plus grand décalage par réunion : médiane 5,2 ms, maximum 26,9 ms. Non mesurable (pas de diaphonie entre micros) pour les 8 réunions Zoom et pour 101c_EDPH, codée en présentiel mais enregistrée à 32 kHz comme les réunions `101*` de la fiche ; 38 pistes sur 254 au total |
| Contrôle croisé avec `ggfox00000/dia-summre-test` (révision `d6f8f2f2`) | DER sans collar entre nos références du test et les siennes, dans nos UEM : de 0,32 % à 9,82 % (102a_EBRH), médiane 1,90 % (29/10, après retrait des jetons). Le dérivé garde les jetons non lexicaux : avec nos références du 28/10, qui les gardaient aussi, le DER était de 0,00 % (arrondi) pour 26 réunions sur 37 et de 0,49 % au plus (008a_EARH) ; le DER entre nos références avant et après retrait reproduit le contrôle croisé à 0,49 point près. RTTM identiques dans ses variantes A et B. Seuls les RTTM ont été téléchargés, puis supprimés après le contrôle |
| Sous-ensemble de mesure du temps (`temps.txt`) | 007a_ECRH (présentiel) et 012c_EBPZ (Zoom), 39,5 min |

## 3. AMI, micro distant (SDM)

| Champ | Valeur |
|---|---|
| Source | https://groups.inf.ed.ac.uk/ami/corpus/ ; partition et références : dépôt GitHub `pyannote/AMI-diarization-setup` (même partition que BUT) |
| Licence | CC BY 4.0 selon le site d'Édimbourg **[certain]** ; le miroir OpenSLR SLR16 affiche une licence CC BY-NC-SA 2.0 modifiée **[certain]** ; la licence de référence citée est celle d'Édimbourg |
| Composition | réunions en anglais (locuteurs largement non natifs), en majorité scénarisées, 4 participants ; chevauchement d'environ 13,6 % **[probable]** |
| Partitions | train 136, dev 18, test 16 réunions **[certain]** ; test : EN2002a–d, ES2004a–d, IS1009a–d, TS3003a–d ; dev : ES2011a–d, IB4001–4004, IB4010, IB4011, IS1008a–d, TS3004a–d |
| Signal | `Array1-01.wav` (premier micro de la première antenne) ; dev ~1,11 Go, test ~1,04 Go **[certain, tailles mesurées]** |
| Référence | RTTM `only_words` ; UEM commun `uems/{partition}/` (il n'existe pas d'UEM propre à `only_words`), qui couvre la réunion entière pour ES2004a |
| Contamination | AMI figure dans l'entraînement de pyannote segmentation-3.0 et de NeMo Sortformer v2 **[certain, d'après les fiches des modèles]** : les résultats sur AMI mesurent la reproduction, pas la généralisation |
| Valeur publiée | community-1 : DER 19,9 % sur AMI SDM, sans collar, chevauchements comptés **[certain, fiche du modèle]** |
| Téléchargements effectués | ES2004a (signal SDM, RTTM, UEM) le 27/10/2026 pour la vérification V5 ; ce premier téléchargement a précédé la mise à jour de cette fiche, en dérogation à `methode.md` §7. Partitions dev (18 réunions, 9,67 h) et test (16 réunions, 9,06 h) complètes le 27/10/2026 par `scripts/data/get_ami.py` : signal `Array1-01` (miroir d'Édimbourg), RTTM `only_words` et UEM du dépôt `pyannote/AMI-diarization-setup` au commit `67c2d539286e89f68952d5dcf83912bd9f01dfae`. Fichiers renommés `ami__<réunion>` (champ uri des RTTM et UEM réécrit) ; manifeste `data/manifests/ami.csv` (SHA-256 du signal brut) ; listes `data/splits/ami/{dev,test}.txt` ; UEM dans `data/splits/ami/uem/`. Contrôles : UEM égal au signal à 0,2 s près pour chaque réunion ; aucun segment de référence hors UEM ; 4 locuteurs par réunion, sauf EN2002c (3). Sous-ensemble de mesure du temps CPU (`temps.txt`) : ES2004a et TS3003a, 42,6 min, deux sites d'enregistrement différents |

## 4. Simsamu

| Champ | Valeur |
|---|---|
| Source | https://huggingface.co/datasets/medkit/simsamu |
| Licence | MIT **[certain]** |
| Composition | 61 appels simulés de régulation médicale (SAMU) en français, 3 h 15 en tout, ~3 min par appel, 2 rôles (appelant et médecin) ; voix de l'appelant transmise par le réseau téléphonique **[certain]** |
| Audio | m4a, 8 kHz ; 56,8 Mo |
| Référence | RTTM fourni ; étiquette `patient_1` dans le miroir `diarizers-community/simsamu` à vérifier |
| Usage | contrôle de cohérence en bande étroite ; ce ne sont pas des réunions |

## 5. VoxConverse (candidat)

| Champ | Valeur |
|---|---|
| Source | https://github.com/joonson/voxconverse (références v0.3) |
| Licence | CC BY 4.0 pour la recherche ; droits d'auteur des vidéos conservés par leurs propriétaires **[certain]** ; audio non redistribuable |
| Composition | débats et journaux issus de YouTube ; dev 216 fichiers (~20 h, 1 à 20 locuteurs), test 232 fichiers (~43 h, 1 à 21 locuteurs) ; chevauchement de 3 à 4 % ; majoritairement en anglais **[probable]** |
| Téléchargement | dev 1,99 Go, test 4,27 Go **[certain, mesuré]** ; un sous-ensemble à 6 locuteurs au plus suffira |
| Contamination | vu à l'entraînement par pyannote segmentation-3.0 et NeMo Sortformer v2 **[certain]** |
| Valeur publiée | community-1 : DER 11,2 %, sans collar **[certain, fiche du modèle]** |

## 6. NOTSOFAR-1 (candidat)

Réunions réelles en anglais d'environ 6 minutes, avec 4 à 8 participants, enregistrées par des appareils de salle commerciaux monocanaux. Licence CC BY 4.0. Les jeux d'évaluation sont publiés avec leur vérité terrain **[probable]**. C'est le seul corpus en champ lointain réel absent des listes d'entraînement des deux modèles. Il permettrait aussi de tester la limite de 4 locuteurs de Sortformer. La taille du sous-ensemble monocanal n'est pas publiée. Son usage dépend de l'accord du tuteur sur un test non francophone.

## 7. Ressources d'augmentation (candidates)

| Ressource | Licence | Taille | Usage |
|---|---|---|---|
| OpenSLR 28 (RIRS_NOISES) | Apache 2.0 **[probable]** | 1,3 Go | Réponses impulsionnelles de salles réelles et simulées |
| MUSAN, sous-dossier `noise` | CC BY 4.0 **[certain]** | ~0,6 Go (11 Go pour MUSAN complet) | Bruits d'ambiance |
| Simulation de codec (Opus, bande téléphonique) | — | — | Par ffmpeg, pré-calculée |

## 8. Corpus écartés

| Corpus | Motif |
|---|---|
| ETAPE, ALLIES, REPERE, ESTER (ELRA) | Payants (300 € à 2 500 € en tarif académique) ; délai de licence ; REPERE est vu par pyannote segmentation-3.0 |
| CEFC-ORFEO, ESLO, TCOF, CLAPI, MPF, CFPP2000 | Transcriptions linguistiques aux frontières imprécises pour un DER ; licences non commerciales ; éventuellement un ou deux fichiers en contrôle hors domaine |
| CHiME-6, DiPCo, AliMeeting, AISHELL-4, MSDWild, MISP | Archives lourdes, langue, contamination ou chevauchement non représentatif |
| CALLHOME (Hugging Face) | Pas de partie française |
| Common Voice FR, LibriMix | Volume (30,7 Go et plus de 400 Go) |
| FREDSum, VoxPopuli, mTEDx | Pas de minutage multi-locuteur exploitable |
| Vidéos de l'Assemblée nationale et du Sénat | Accord préalable requis pour la réutilisation |

## 9. Contamination des modèles pré-entraînés

| Modèle | Corpus vus à l'entraînement (d'après la fiche) | Conséquence |
|---|---|---|
| pyannote segmentation-3.0 (base de community-1) | AISHELL, AliMeeting, AMI, AVA-AVD, DIHARD, Ego4D, MSDWild, REPERE, VoxConverse **[certain]** | Résultats optimistes sur AMI et VoxConverse |
| pyannote community-1 | Données d'entraînement non listées sur la fiche **[certain]** | Contamination au moins égale à celle de segmentation-3.0 **[probable]** |
| NeMo Sortformer v2 | Fisher, AMI, VoxConverse v0.3, ICSI, AISHELL-4, DIHARD III dev, NIST SRE 2000, DiPCo, AliMeeting **[probable]** ; 4 locuteurs au plus | Résultats optimistes sur AMI et VoxConverse ; inadapté aux réunions de 5 à 6 personnes |
