# Veille — modèles de diarisation et de transcription récents

Rédigée par le cockpit le 1er novembre 2026, à la demande de la candidate, à partir de deux publications sur X du 28 octobre 2026 (NVIDIA et Mistral AI). X bloque la lecture automatique : les publications ont été identifiées par leur date (décodée de leur identifiant) et confirmées par la candidate.

**Légende de confiance.** **[certain]** : lu sur la source primaire. **[probable]** : source secondaire ou déduction. **[incertain]** : non vérifié.

## 1. NVIDIA Nemotron 3.5 Transcribe (annoncé le 28/10/2026)

| Point | Information | Confiance |
|---|---|---|
| Nature | Modèle de transcription (40 langues) qui produit aussi des étiquettes de locuteurs ; jusqu'à 8 locuteurs dans les données d'entraînement | [certain] |
| Français | Pris en charge (France et Canada), y compris la transcription multi-locuteurs | [certain] |
| Taille | 34 milliards de paramètres, dont 4,3 actifs (mélange d'experts), encodeur audio d'environ 800 millions compris | [certain] |
| Licence | OpenMDW-1.1, usage commercial ou non commercial | [certain] |
| Matériel | Cible : 1 H100 de 80 Go (aussi A100, B200, RTX 5090, L40S en FP8) ; ni CPU ni Mac mentionnés | [certain] |
| Diarisation | Produite par un encodeur de locuteurs intégré, nommé « Nemotron-3-Diarization » ou « Sortformer speaker encoder » selon les passages de la fiche. Le champ de sortie `diarization` contient des segments d'activité par locuteur, recommandés par NVIDIA pour évaluer la diarisation | [certain] |
| Évaluation publiée | En cpWER (erreur de mots après appariement des locuteurs), pas en DER ; corpus AMI (IHM et SDM), CALLHOME, Mixer 6, NOTSOFAR-1 | [certain] |
| Durée maximale | 1 h par enregistrement | [certain] |

**Intérêt pour le projet.** Sa diarisation peut être utilisée sans sa transcription, en ne gardant que les segments du champ `diarization`. Il faut cependant exécuter tout le modèle, hors de portée du MacBook M2 Pro de 16 Go **[probable]**. Il ne peut donc pas être le système de démonstration locale. Il peut être évalué sur un GPU loué. Si son encodeur de locuteurs est bien Nemotron 3 Diarization **[probable, non confirmé par la fiche]**, ce dernier offre la même fonction en local. La contamination par AMI et NOTSOFAR-1 est probable, puisque ces corpus figurent parmi ses jeux d'évaluation et, vraisemblablement, d'entraînement **[incertain]**.

Sources : [fiche Hugging Face](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B) ; [TechCrunch, 28/10/2026](https://techcrunch.com/2026/10/28/voice-ai-in-vogue-nvidia-releases-new-open-transcription-model/).

## 2. Mistral Voxtral Mini Transcribe 3 (famille Voxtral 3, annoncée le 20/10/2026)

| Point | Information | Confiance |
|---|---|---|
| Nature | Modèle de transcription par lots d'environ 4 milliards de paramètres, avec diarisation | [probable] |
| Poids | Fermés : accès par l'API de Mistral (hébergement européen possible) ou déploiement privé sous contrat | [probable] |
| Français | Vraisemblablement couvert (50 langues, dont les 24 langues officielles de l'UE) ; non nommé explicitement | [probable] |
| Diarisation | Erreur annoncée de 30,9 % (Mini Transcribe 2) à 18,6 % (Mini Transcribe 3), métrique et corpus non précisés ; segments diarisés pouvant se chevaucher | [probable] |
| Prix | Environ 0,0035 $ par minute | [probable] |

**Intérêt pour le projet.** Ce modèle ne peut pas servir de système local. C'est en revanche un bon candidat pour la comparaison avec un service cloud payant : européen, peu coûteux (environ 3 $ pour SUMM-RE test), et dont les segments diarisés se convertissent en RTTM. Contrainte de consentement : seuls des corpus publics peuvent lui être envoyés, **jamais le corpus maison**, dont la notice exclut tout envoi à un service en ligne.

Source : [eesel, 28/10/2026 (source secondaire)](https://www.eesel.ai/blog/voxtral-3) ; à confirmer sur la documentation de Mistral avant usage.

## 3. NVIDIA Nemotron 3 Diarization (annoncé le 23/09/2026), découvert pendant cette veille

| Point | Information | Confiance |
|---|---|---|
| Nature | Diariseur de bout en bout (famille Sortformer, en flux), 100 millions de paramètres | [certain, annonce NVIDIA] |
| Locuteurs | Jusqu'à 8, chevauchement pris en charge | [certain, annonce NVIDIA] |
| Poids | Ouverts, sur Hugging Face | [certain, annonce NVIDIA] |
| Apple Silicon | Des portages CoreML tiers existent ; un portage annonce 9,36 % de DER sur AMI | [probable, source secondaire] |
| Licence, données d'entraînement | À vérifier sur la fiche | [incertain] |

**Intérêt pour le projet.** C'est l'intérêt le plus direct des trois. Il lève la limite de 4 locuteurs de Sortformer v2, incompatible avec des réunions de 5 à 6 personnes, et il peut probablement tourner en local. Il est ajouté aux moteurs à tester (D23).

Sources : [NVIDIA AI sur X, 23/09/2026](https://x.com/NVIDIAAI/status/2102775666366435450) ; [MarkTechPost, 23/09/2026](https://www.marktechpost.com/2026/09/23/nvidia-releases-nemotron-3-diarization/) ; [portage CoreML (source secondaire)](https://huggingface.co/aidsoid/nemotron-3-diarization-coreml).
