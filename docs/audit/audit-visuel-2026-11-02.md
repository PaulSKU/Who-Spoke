# Audit visuel de l'interface et plan de finition

Rédigé par le cockpit le 2 novembre 2026, à la demande de la candidate : rendre l'interface la plus propre possible avec les moyens actuels (Gradio 6.31, HTML, CSS et SVG embarqués, hors ligne), corriger les artefacts et mieux représenter le pipeline. Les recommandations retenues deviennent les chantiers B10 à B13 (§7).

**Légende de confiance.** **[certain]** : constaté sur les captures, lu dans le code de Gradio 6.31.0 ou sur la source primaire. **[probable]** : déduction, ou source lue par un agent de recherche sans relecture du cockpit. **[incertain]** : à vérifier.

## 1. Méthode

- **Captures.** Branche `ui` au commit `59a83b8`, en mode factice, avec un audio de synthèse et la référence de 007a_ECRH. Quatre configurations : clair et sombre en 1440 × 900, mobile 375 px en sombre, mode présentation 1280 × 720 en sombre. Pour chacune : onglet Analyse vide, pendant l'analyse et après, puis Pipeline et Avancement.
- **Signalements de la candidate.** Le choix « Automatique » en sombre, le bouton ▶ du plus long monologue, et les séparateurs du tableau des locuteurs.
- **Deux recherches web.**
  - Représentation des pipelines : scikit-learn, Airflow, Node-RED, n8n, GOV.UK, WAI-ARIA, Tufte, skills de conception.
  - Finition de Gradio 6 : code source 6.31.0, guides officiels, tickets GitHub, Vercel Web Interface Guidelines, impeccable, emilkowalski/skills, Apple HIG, outils de contrôle.

## 2. Artefacts et défauts relevés

| # | Où | Constat | Cause probable | Confiance |
|---|---|---|---|---|
| V1 | Analyse, « Nombre de locuteurs » (sombre) | Le coin bas-gauche du cadre de l'option sélectionnée paraît rogné. Les ronds des options non sélectionnées sont presque invisibles (contraste insuffisant, WCAG 1.4.11). Le rond sélectionné est un disque clair avec un point sombre, en décalage avec le reste | Couleurs `_dark` du thème non définies pour les cases et radios : le mode sombre hérite des valeurs claires. Le point du radio est un SVG blanc codé en dur (`radio_circle`, sans variante sombre). Une ombre héritée (`input_shadow`, `checkbox_label_shadow`) dessine le liseré | [certain] pour le constat ; [probable] pour la cause |
| V2 | Tableau des locuteurs | Les séparateurs des lignes ne sont pas à la même hauteur dans la colonne du nom et dans celle du bouton ▶ : la ligne paraît cassée | Cellules de hauteurs et d'alignements différents, séparateur porté par les cellules et non par la ligne | [certain] |
| V3 | Tableau des locuteurs | L'identifiant est affiché deux fois (dans le champ, puis dessous) tant que le locuteur n'est pas renommé | Mise en page fixe | [certain] |
| V4 | Boutons ▶ (extrait typique, plus long monologue) | Le triangle n'est pas centré optiquement dans son cercle, et il est petit par rapport au cercle | Glyphe texte « ▶ » centré géométriquement, alors qu'un triangle doit être décalé d'environ 1 px vers la droite | [certain] |
| V5 | Barre d'outils de la timeline | Cinq styles de boutons cohabitent : contour, contour épais (« Suivre la lecture »), plein noir (contrôle segmenté), gris désactivé (« Tout afficher »), icône. L'état actif de « Suivre la lecture » ne se lit pas. La barre passe sur deux lignes en mode présentation et sur quatre à 375 px | Pas de système de boutons commun | [certain] |
| V6 | En-tête | « Configuration : correspondance de app/moteurs.py, avant le gel » : une information de développement, visible aussi en mode présentation. Le bouton « Mode présentation » a l'allure d'un badge d'état | — | [certain] |
| V7 | Avancement de l'analyse | Les statuts « terminé » flottent loin de leur étape, et les colonnes sont de largeurs inégales. Une fois l'analyse finie, la liste n'apporte plus rien, sauf en mode présentation | — | [certain] |
| V8 | Onglet Analyse avant toute analyse | Six cartes vides empilées (« s'afficheront après l'analyse ») occupent l'écran avant le moindre résultat | États vides conçus carte par carte, et non pour l'écran entier | [certain] |
| V9 | Timeline | Les étiquettes de la référence sont tronquées (« SPK_00 ↔ SPEAKER_… ») | Colonne d'étiquettes trop étroite pour la double étiquette | [certain] |
| V10 | Évaluation | Deux styles d'encadré différents pour une information et un avertissement. Une phrase est incomplète : « 26,59 % hors chevauchement, — en chevauchement » quand la référence n'a pas de chevauchement | — | [certain] |
| V11 | Exports | Les tailles s'affichent à l'anglaise (« 7.2 KB ») | Composant de fichier de Gradio | [certain] |
| V12 | Pipeline | La rangée d'étapes passe à la ligne, et « Évaluation » tombe en dessous. Un trait vertical parasite apparaît après « Sortie ». Les boîtes sont de largeurs inégales. Rien n'indique ce qui circule entre les étapes, et la page détaillée ressemble à un document plus qu'à un schéma | — | [certain] |
| V13 | Textes d'aide | De longs paragraphes explicatifs sous les tableaux (Locuteurs, Interactions, Appariement) alourdissent l'écran de démonstration | — | [certain] |

## 3. Ce que dit Gradio 6.31 (vérifié dans le code)

- **Mode sombre du thème.** Chaque couleur a une variante `_dark` ; si elle n'est pas définie, le mode sombre reprend la couleur claire. Il faut donc définir explicitement toutes les `_dark` du thème : cases, radios, champs, blocs, tableaux, panneaux. **[certain]**
- **Radio.** Son point est un SVG `fill='white'` posé sur `--checkbox-background-color-selected`, et `radio_circle` n'a pas de variante `_dark`. Correctif robuste : `radio_circle = radial-gradient(circle, var(--background-fill-primary) 0 3px, transparent 3.5px)`. Le point prend alors la couleur du fond dans les deux modes. **[certain]** pour le code ; **[probable]** pour l'effet, à vérifier.
- **Réécriture du CSS personnalisé.** Le CSS passé par `css` ou `css_paths` est réécrit et préfixé :
  - dans un `@media`, les sélecteurs `:root`, `body` et `.gradio-container` ne ciblent plus rien ;
  - `@supports`, `@container`, `@layer` et `@property` sont supprimés sans avertissement.

  Ces règles doivent passer par `head` ou `head_paths` de `launch()`. Le mode sombre se cible avec `.dark …`, pas avec `prefers-color-scheme`. **[certain]** pour la réécriture ; **[probable]** pour le contournement.
- **Focus.** Gradio supprime l'anneau de focus des radios et des cases (`outline: none`). Il faut le rétablir sur l'étiquette (`label:has(input:focus-visible)`). **[certain]**
- **Sélecteurs.** Seuls `elem_id` et `elem_classes` sont stables d'une version à l'autre. Les classes `svelte-…` changent à chaque compilation. **[certain]**
- **`gr.HTML`.** Toute modification de sa valeur reconstruit son contenu. Les éléments qui ont un état (wavesurfer) doivent rester hors du gabarit et être mis à jour par `watch`. **[probable]**

## 4. Système visuel retenu

Un seul système, défini par des jetons dans `app/theme.py` (`theme.set`) et par des variables CSS. Aucune valeur en dur ailleurs.

| Élément | Règle |
|---|---|
| Espacement | Grille de 4 et 8 px (`gr.themes.Size` : 2, 4, 4, 8, 8, 12, 16 px) ; espaces entre cartes et marges intérieures pris dans cette échelle |
| Arrondis | Une valeur de base pour les cartes, une seule plus petite pour les contrôles ; arrondi d'un enfant inférieur ou égal à celui de son parent (Vercel) |
| Ombres | Cartes seulement (ombre en couches de `block_shadow`) ; aucune ombre sur les contrôles ; en sombre, ombre remplacée par un filet de bordure semi-transparent |
| Boutons | Trois variantes et deux tailles en tout :<br>- **primaire** (« Analyser »), un seul par écran ;<br>- **secondaire** (contour fin) ;<br>- **icône** (carrée, 32 px, zone cliquable d'au moins 24 px, 44 px sur mobile).<br>Plus un **contrôle segmenté** pour les choix exclusifs (Forme d'onde / Spectrogramme) et un **interrupteur** avec `aria-pressed` et état visible pour les bascules (Suivre la lecture). Désactivé : opacité réduite, même forme |
| Encadrés | Deux styles seulement : **information** (fond discret) et **attention** (filet gauche et icône) ; pas d'encadré coloré |
| Typographie | Échelle à 4 tailles (titre, sous-titre, texte, note) ; `tabular-nums` sur tous les nombres comparés (tableaux, SVG) ; nombres alignés à droite |
| Nombres en français | Une seule fonction de formatage en Python : virgule décimale, espace fine insécable (U+202F) pour les milliers et devant les unités et `%`, unités en français (Ko, Mo, s, min) ; réutilisée par les tableaux, les SVG et les exports |
| Couleur | Inchangée : neutre, couleur réservée aux locuteurs (D26) ; motifs pour les types d'erreur |
| Focus | Anneau visible avec `:focus-visible`, jamais rogné, sur tous les contrôles, y compris dans les `gr.HTML` |
| Mouvement | Transitions explicites de 200 ms au plus, en `ease-out`, jamais `transition: all` ; retour de clic par `scale(0.97)` sur `:active` ; tout coupé en mouvement réduit (emilkowalski/skills, Vercel) |
| Contraste | WCAG AA partout ; 7:1 visé pour le texte en mode présentation (Apple HIG) |

## 5. Onglet Analyse : corrections

| Point | Correction |
|---|---|
| V1 | Correctif du thème (§3), contrôlé en clair, en sombre et en mode présentation |
| V2, V3 | Tableau des locuteurs reconstruit : séparateur porté par la ligne (`border-collapse`), toutes les cellules centrées verticalement, hauteur de ligne fixe ; identifiant affiché sous le nom seulement si le locuteur a été renommé |
| V4 | Bouton ▶ en SVG (triangle décalé d'environ 1 px vers la droite), même taille d'icône que les autres boutons-icônes |
| V5 | Barre d'outils réorganisée en trois groupes alignés sur une ligne : lecture (▶/⏸, temps) ; vue (contrôle segmenté, Suivre la lecture) ; zoom (−, curseur, +, Tout afficher). Aide « ? » à droite. Retour à la ligne par groupe entier, jamais au milieu d'un groupe |
| V6 | Configuration et moteur en vigueur déplacés dans un panneau « Détails » (ou une infobulle) ; le bouton du mode présentation prend la forme d'un bouton |
| V7 | Statuts collés à leur étape ; une fois l'analyse terminée, la liste se replie en une ligne (« 7 étapes terminées en 3 s »), dépliable |
| V8 | Avant toute analyse, la colonne de droite est remplacée par une seule carte « Comment ça marche » : les trois étapes (déposer, choisir, analyser), ce qu'on obtiendra, et un lien vers l'onglet Pipeline |
| V9 | Étiquette de référence courte (« SPK_00 → S2 » ou pastille de la couleur appariée), nom complet en infobulle |
| V10 | Deux styles d'encadré (§4) ; phrase corrigée (« pas de chevauchement dans la référence ») |
| V11 | Liste d'exports rendue en HTML, tailles formatées en français |
| V13 | Textes d'aide repliés sous un « Comment lire ce tableau » par carte ; masqués en mode présentation |

## 6. Onglet Pipeline : nouvelle représentation

Il est inspiré de la représentation des pipelines de scikit-learn (étapes, réglages par étape), du motif maître-détail, du stepper vertical du système de conception GOV.UK pour les petits écrans, et des sparklines de Tufte.

1. **Schéma de gauche à droite en SVG**, sans retour à la ligne à partir de 840 px de large et lisible à 1280 × 720. Les étapes sont des boutons dans un `role="tablist"`, navigables au clavier (flèches, Origine et Fin).
2. **Anatomie d'une étape** : numéro, titre, modèle en sous-titre (« WeSpeaker ResNet34 », révision abrégée), petit aperçu de 24 px de haut, et badge d'erreurs en texte (« manquée · fausse alarme » ou « confusion »), jamais la couleur seule.
3. **Flèches étiquetées par la forme des données**, avec des valeurs lues dans la configuration effective et jamais écrites à la main : par exemple « signal 16 kHz mono » → « trames par fenêtre de 10 s, 3 locuteurs locaux » → « vecteurs de dimension 256 » → « groupes » → « tours de parole (RTTM) ».
4. **Groupe** : pour pyannote, détection et segmentation sont deux sous-blocs dans un même cadre, intitulé « un seul réseau » ; pour la baseline, le cadre disparaît et les étapes se séparent. La différence entre les deux familles de systèmes se voit au premier coup d'œil.
5. **Évaluation** détachée à droite, derrière un filet pointillé, avec la mention « mesure seulement ».
6. **Naissance des erreurs** : sous le schéma, une barre empilée du DER de l'expérience source (parole manquée, fausse alarme, confusion, avec les motifs habituels). Chaque segment désigne l'étape où l'erreur naît (détection pour la parole manquée et la fausse alarme ; empreintes et regroupement pour la confusion) et la sélectionne au clic. Une mention précise que cette attribution est une simplification pédagogique.
7. **Détail** sous le schéma, sur toute la largeur : rôle, modèle et révision, fichier, tableau des réglages, constats. Contenu actuel conservé, mise en page allégée.
8. **Aperçus** (statiques, dessinés à partir de l'expérience source ou schématiques) : courbe d'énergie après la normalisation, bandes d'activité après la segmentation, nuage de points après les empreintes, points colorés par groupe après le regroupement. Seuls ces deux derniers aperçus portent les couleurs des locuteurs.
9. **Mobile (375 px)** : stepper vertical numéroté, flèches verticales avec leur étiquette de forme, une étape dépliée à la fois, réglages en liste « clé : valeur » plutôt qu'en tableau.
10. **Mode présentation** : texte des étapes agrandi, révisions masquées, barre des erreurs mise en avant.

## 7. Contrôle et chantiers

**Contrôle automatique**, sans réseau, à mettre en place dès le premier chantier pour figer les acquis :

- **Captures de référence Playwright** : clair et sombre × 1440 et 375 px, plus le mode présentation, sur les quatre onglets, avec la forme d'onde masquée. Toute différence échoue au test.
- **Contrôle d'accessibilité axe-core**, dans les deux modes.
- **Règles stylelint** : arrondis, ombres et couleurs seulement par variables, aucun hexadécimal hors des jetons.

| Chantier | Contenu | Effort estimé |
|---|---|---|
| B10 | Système visuel (§4) dans le thème et le CSS ; correctif des radios et cases (V1) ; focus ; règles déplacées vers `head_paths` ; formatage français ; captures de référence, axe et stylelint | 6 à 8 h |
| B11 | Onglet Analyse (§5, V2 à V13) | 5 à 7 h |
| B12 | Onglet Pipeline (§6) | 10 à 14 h |
| B13 | Onglets Avancement et Glossaire passés au même système ; passe `break-ui` finale ; vérification au vidéoprojecteur par la candidate | 3 à 4 h |

Ordre : B10, puis B11 et B12, puis B13, avant le gel du 10/11. Si le temps manque, B12 se limite aux points 1 à 7 du §6, sans les aperçus.

## 8. Sources

Relues par le cockpit : captures du 02/11 ; code de l'application (branche `ui`).

Lues par les agents de recherche, non relues par le cockpit :

- Gradio 6.31.0 : guides Theming, Custom CSS and JS, CSS Variables Reference, Gradio 6 Migration Guide, Styling the Dataframe ; paquet PyPI (`themes/base.py`, CSS compilé) ; tickets #12563 et #12951 (https://github.com/gradio-app/gradio/issues).
- Vercel, Web Interface Guidelines : https://github.com/vercel-labs/web-interface-guidelines ; skill `web-design-guidelines` (https://github.com/vercel-labs/agent-skills).
- P. Bakaus, impeccable : https://github.com/pbakaus/impeccable ; E. Kowalski, skills : https://github.com/emilkowalski/skills ; Anthropic, `frontend-design` : https://github.com/anthropics/skills.
- Apple, Human Interface Guidelines (Dark Mode, Layout) ; Wathan et Schoger, *Refactoring UI* (page d'accueil seulement).
- scikit-learn 1.9.1, « Displaying estimators and complex pipelines » ; Apache Airflow 3.3.2, « UI Overview » ; Node-RED, « Nodes » ; n8n, « Data ».
- GOV.UK Design System, « Step by step navigation » ; W3C WAI-ARIA APG, « Tabs pattern » ; E. Tufte, « Sparkline theory and practice ».
- B. Victor, « Explorable Explanations » (2011) ; Olah et Carter, « Research Debt », Distill (2017).
- Playwright, « Visual comparisons » et « Accessibility testing » ; Deque, axe-core ; Chrome DevTools, « CSS Overview » ; stylelint, règles.
