# Guide d'annotation du corpus maison, pas à pas

Version 1.0 du 1er novembre 2026 (chantier E2). Ce guide met en œuvre `conventions-annotation.md` pour une session (`M01`, `M02`, `M03`). Les règles sur ce qui compte comme parole restent celles des conventions. Ce guide dit seulement **comment** les appliquer avec les outils du dépôt.

**Légende de confiance.** **[certain]** : vérifié (commande testée sur signaux de synthèse). **[probable]** : non vérifié ici, en particulier les menus d'Audacity, qui n'est pas installé sur la machine où ce guide a été écrit. Vérifier ces menus à la première session et corriger ce guide si besoin.

**Règle absolue.** Tout se passe sur cette machine. Aucun fichier de `data/raw/maison/` ne part sur une messagerie, un stockage en ligne, un GPU distant ou un service de transcription (D27, notice de consentement). Rien de ce dossier n'entre dans git : `data/raw/` est ignoré.

---

## Vue d'ensemble

| Étape | Qui | Commande ou outil | Produit | Durée indicative pour 10 min d'audio |
|---|---|---|---|---|
| 0 | Candidate | Copie des fichiers | `M01/table.<ext>`, `S1.<ext>`…, `fiche.md` | 5 min |
| 1 | Script | `synchroniser M01` | `synchro.json`, pistes alignées | < 1 min |
| 2 | Script | `preannoter M01` | `preannotation/` | < 1 min |
| 3 | Candidate | Audacity | `annotation/` | 40 à 60 min |
| 4 | Script | `convertir M01` | `reference/` (RTTM, UEM, rapport) | < 1 min |
| 5 | Script, puis candidate | `tirer-controle M01` puis, **au moins un jour plus tard**, Audacity et `accord M01` | `controle/` | 15 à 20 min |

Toutes les commandes se lancent depuis la racine du dépôt :

```bash
uv run python scripts/data/maison.py etat M01
```

`etat` affiche ce qui est fait et **l'étape suivante**. En cas de doute, commencer par là. Chaque commande a une aide (`--help`).

---

## Étape 0 — Déposer les fichiers

Juste après la session (protocole §6), copier les fichiers par câble ou par AirDrop dans `data/raw/maison/M01/`, sous des noms neutres :

| Fichier | Contenu |
|---|---|
| `table.<ext>` | Signal de test : l'appareil posé au centre de la table, ou le mixage de la visio. Le seul audio donné aux systèmes |
| `S1.<ext>`, `S2.<ext>`… | Pistes d'aide : le téléphone posé devant chaque participant, sous son code de place à table |
| `fiche.md` | Fiche de session (protocole §7), sans aucun nom réel |

Tout format lu par ffmpeg convient (m4a, wav, mp3…) : le script normalise en WAV 16 kHz mono. Supprimer ensuite les copies restées sur les téléphones des participants.

---

## Étape 1 — Synchroniser les pistes d'aide sur la table

```bash
uv run python scripts/data/maison.py synchroniser M01
```

Le script repère les deux claquements de mains dans la table : le plus franc de la première minute, puis le plus franc de la dernière minute. Il retrouve ensuite chaque claquement dans chaque piste d'aide par corrélation croisée, ce qui donne le **décalage** de chaque téléphone et sa **dérive d'horloge**. Il consigne tout dans `synchro.json` et écrit les pistes d'aide recalées sur la table dans `travail/alignees/S1.wav`… **[certain]**

**À vérifier dans la sortie :**

| Ce que le script affiche | Valeur attendue | Sinon |
|---|---|---|
| Instants des claquements dans la table | Proches de ceux notés dans la fiche | Ouvrir `travail/table.wav` dans Audacity, lire l'instant exact du claquement, puis relancer avec `--clap-debut 12.34 --clap-fin 615.2` |
| Décalage de chaque piste | Quelques secondes, positif ou négatif selon l'ordre de démarrage des appareils | — |
| Dérive | Moins de 200 ppm environ (quelques dizaines de millisecondes sur 10 minutes) | Au-delà de 1 000 ppm, le script la refuse et l'annonce par une alerte |
| Corrélations | Au-dessus de 0,3 | Une ALERTE « claquement douteux » : vérifier à l'oreille (ci-dessous) |

**Vérification à l'oreille** (une fois par session) : dans Audacity, importer `travail/table.wav` et `travail/alignees/S1.wav`, zoomer sur le claquement de début, puis sur celui de fin. Les deux pics doivent coïncider à quelques millisecondes près. Un écart d'environ 3 ms par mètre entre l'appareil et les mains est normal : c'est le temps de propagation du son, négligeable devant la précision visée de ±50 ms.

**Session sans piste d'aide** (visio sans pistes séparées) : la commande trouve seulement les claquements de la table, qui servent à l'UEM. Passer directement à l'étape 3 et annoter à partir de zéro.

**Visio avec pistes séparées** (M02) : si les pistes séparées commencent au même instant que le mixage, ce qui est à vérifier à l'oreille, utiliser `--deja-alignees` (aucun décalage appliqué). Sinon, essayer la synchronisation normale. Si les claquements n'apparaissent pas dans les pistes séparées, annoter à partir de zéro.

---

## Étape 2 — Pré-annoter

```bash
uv run python scripts/data/maison.py preannoter M01
```

Principe : chaque participant parle près de son téléphone. À chaque instant (trames de 10 ms), **la piste d'aide la plus forte désigne le locuteur**, à condition de dépasser nettement son propre bruit de fond. La pré-annotation ne propose qu'un locuteur à la fois : les chevauchements sont ajoutés à la main, à l'étape 3. Aucun système évalué dans le projet n'intervient, comme l'exigent les conventions (§4) **[certain]**.

Fichiers produits dans `preannotation/` : `S1.txt`, `S2.txt`… (une étiquette par segment, de texte `S1`, `S2`…), `a_verifier.txt` (zones où deux pistes sont presque aussi fortes l'une que l'autre : chevauchement probable ou attribution incertaine) et `parametres.json` (seuils employés, plancher de bruit de chaque piste).

**Seuils** (choisis a priori, validés sur signaux de synthèse seulement) :

| Seuil | Défaut | Rôle | Quand le changer |
|---|---|---|---|
| Plancher de bruit | 10e percentile de l'énergie de chaque piste | Rend les pistes comparables malgré les gains différents des téléphones | — |
| `--seuil-activite-db` | 10 dB | Parole si la piste la plus forte dépasse son plancher de 10 dB | Bruit de fond fort (M03) et beaucoup de faux segments : 13 à 15 ; voix faibles manquées : 7 à 8 |
| `--marge-db` | 3 dB | Zone « à vérifier » si la deuxième piste est à moins de 3 dB de la première | Trop de zones à vérifier : 2 ; pas assez : 4 |
| Lissage | 0,1 s | Évite les changements de locuteur trame à trame | — |
| Fusion | 0,2 s | Pauses de 200 ms ou moins comblées, comme dans la référence | — |
| Durée minimale | 0,1 s | Retire les détections isolées (pré-annotation seulement : la référence n'en a pas) | — |

Relancer `preannoter` avec d'autres seuils écrase seulement `preannotation/`, jamais `annotation/`. Les seuils n'ont aucun effet sur l'évaluation : ils changent le travail de correction, pas la référence, qui est fixée à l'oreille.

---

## Étape 3 — Corriger dans Audacity

Toutes les règles de fond sont dans `conventions-annotation.md` §1 et §2. Ce qui suit est la manière de faire.

### 3.1 Ouvrir la session [probable pour les menus]

1. Lancer Audacity (application locale, sans compte ni connexion).
2. *Fichier > Importer > Audio…* : `travail/table.wav`. **C'est sur ce signal qu'on annote et qu'on règle les frontières.**
3. Même menu : les pistes alignées `travail/alignees/S1.wav`… Elles aident à reconnaître qui parle. Les rendre muettes et ne les écouter qu'en cas de doute (bouton *Solo*).
4. *Fichier > Importer > Labels…* : `preannotation/S1.txt`, `S2.txt`…, puis `a_verifier.txt`. Chaque fichier devient une piste de labels, nommée d'après le fichier.
5. *Fichier > Enregistrer le projet* dans `data/raw/maison/M01/` (fichier `.aup3`, hors de git).

### 3.2 Corriger

| À faire | Comment |
|---|---|
| Écouter tout l'enregistrement, piste de labels par piste ou d'un bout à l'autre | Lecture normale ; zoom sur chaque frontière pour la régler à ±50 ms |
| Corriger une frontière | Glisser le bord du label |
| Corriger un locuteur | Déplacer le label dans la bonne piste, ou le supprimer et le recréer, **et changer son texte** |
| Ajouter un segment oublié (acquiescement, « mm ») | Sélectionner la zone dans la bonne piste, *Édition > Labels > Ajouter un label à la sélection* (Ctrl+B), puis **taper le code** `S2` |
| Ajouter un chevauchement | Même chose dans la piste du second locuteur : les labels de deux pistes se recouvrent |
| Supprimer un faux segment (rire, toux, voix d'un voisin, bruit) | Sélectionner le label, puis Suppr |
| Zones « à vérifier » | Écouter chacune : chevauchement réel, ou locuteur à corriger. Supprimer ensuite cette piste, ou la laisser : elle est ignorée à la conversion, avec un avertissement |
| Pauses courtes | Inutile de réunir deux segments séparés de 200 ms ou moins : la conversion le fait |

**Le texte de chaque label est le code du locuteur** (`S1`, `S2`…). C'est lui, et non le nom de la piste, qui désigne le locuteur dans la référence. Un label sans texte prend le code du nom de son fichier (`M01_S1.txt`). Un texte inconnu (un prénom, par exemple) arrête la conversion : c'est voulu.

### 3.3 Exclure des zones de l'UEM

L'UEM va automatiquement du claquement de début + 1 s au claquement de fin − 1 s. L'annonce « Session M01, début » qui suit le claquement, toute voix extérieure longue (passant, télévision) et tout incident à écarter doivent être exclus à la main : créer une piste de labels (*Pistes > Ajouter nouvelle > Piste de labels*), y poser un label de texte **`exclusion`** sur chaque zone, et noter ces zones dans la fiche de session.

### 3.4 Exporter

*Fichier > Exporter > Exporter les labels…* : enregistrer dans `data/raw/maison/M01/annotation/` (dossier à créer), sous `M01.txt`. Si Audacity exporte toutes les pistes de labels dans un seul fichier, c'est très bien, puisque chaque label porte son code. S'il n'exporte qu'une piste à la fois, exporter chacune sous `M01_S1.txt`, `M01_S2.txt`, `M01_exclusions.txt` **[probable : comportement de l'export à vérifier]**. Tous les fichiers `.txt` du dossier `annotation/` sont relus.

Noter le temps passé (début, fin) pour le journal : c'est une donnée du rendu (conventions §6).

---

## Étape 4 — Convertir et contrôler

```bash
uv run python scripts/data/maison.py convertir M01
```

Le script relit `annotation/`, fusionne les pauses de 200 ms ou moins par locuteur (même règle que la référence de SUMM-RE), coupe à l'UEM et écrit `reference/maison__M01.rttm` (locuteurs `M01_S1`…), `reference/maison__M01.uem` et `reference/rapport.json` **[certain]**.

| Sortie | Signification | Action |
|---|---|---|
| **BLOQUANT** | Un participant sans aucun segment, un segment hors de l'UEM ou de durée nulle. Le RTTM et l'UEM ne sont **pas** écrits | Corriger dans Audacity, réexporter, relancer |
| Avertissement | Parole sur moins de 40 % ou plus de 98 % de l'UEM ; plus de 25 % de chevauchement ; un locuteur sous 2 % du temps de parole ; segment de plus de 30 s ; locuteur sans piste d'aide ; zone « à vérifier » ou label de durée nulle ignorés ; parties de labels coupées hors de l'UEM | Vérifier à l'oreille : un avertissement peut être juste (quelqu'un a très peu parlé) |
| Statistiques | Durée de l'UEM, parole, taux de chevauchement, temps et nombre de segments par locuteur | À transmettre au cockpit pour `docs/corpus.md` |

Si le nombre de participants diffère du nombre de pistes d'aide (un téléphone en panne), préciser `--locuteurs 5`.

---

## Étape 5 — Contrôle qualité : ré-annoter deux minutes

Objectif (conventions §5) : mesurer le bruit de la référence elle-même. Ce DER est un plancher : aucun système ne peut être jugé meilleur qu'à cette précision près.

1. Juste après la conversion, tirer la fenêtre au hasard (la graine est consignée) :

   ```bash
   uv run python scripts/data/maison.py tirer-controle M01
   ```

2. **Au moins un jour plus tard**, ouvrir un **nouveau** projet Audacity avec `travail/table.wav` et les pistes alignées, **sans** la pré-annotation ni le projet de l'étape 3. Annoter à partir de zéro la fenêtre affichée par la commande (aussi dans `controle/fenetre.json`), selon les mêmes règles, avec un label par segment portant le code du locuteur. Ce qui déborde de la fenêtre est ignoré.
3. Exporter les labels dans `data/raw/maison/M01/controle/`, puis lancer :

   ```bash
   uv run python scripts/data/maison.py accord M01
   ```

Le script calcule le DER de la ré-annotation face à la référence sur la fenêtre, sans collar et chevauchements compris (condition `collar_0` du protocole), avec le même code d'évaluation que pour les systèmes. Il l'écrit dans `controle/accord.json`. Il signale aussi une ré-annotation faite moins de 24 h après la première, d'après les dates des fichiers.

---

## Après la session

| Quoi | Où |
|---|---|
| Statistiques de `reference/rapport.json`, DER d'accord, temps passé, incidents | Message au cockpit, qui les reporte dans `docs/corpus.md` et le journal (aucun nom réel) |
| RTTM et UEM de référence | Restent dans `data/raw/maison/M01/reference/`. Leur installation pour l'évaluation (A9) et leur éventuel versionnement selon le consentement relèvent du cockpit |
| Projet Audacity, audio, étiquettes | Restent dans `data/raw/maison/M01/`, jamais dans git, jamais en ligne |

## Dépannage

| Problème | Solution |
|---|---|
| « un fichier table.<ext> attendu » | Renommer le signal de test en `table.<ext>` ; un seul fichier de ce nom |
| Claquement mal détecté (instant éloigné de celui de la fiche) | `--clap-debut` / `--clap-fin` avec les instants lus dans Audacity |
| « claquement de fin hors de la piste » | Le téléphone a été arrêté avant le claquement de fin : la dérive n'est pas corrigée. Vérifier à l'oreille la fin de l'enregistrement ; sur 10 min, l'écart reste en général de quelques dizaines de millisecondes |
| Pré-annotation presque vide ou pleine de bruit | Ajuster `--seuil-activite-db` (étape 2) |
| « texte '…' inconnu » à la conversion | Un label porte autre chose qu'un code `S1`… ou `exclusion` : corriger son texte dans Audacity |
| « code d'une autre session » | Un label `M02_S1` dans la session M01 : fichiers mélangés |
