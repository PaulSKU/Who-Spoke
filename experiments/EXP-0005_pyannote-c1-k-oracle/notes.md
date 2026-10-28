# EXP-0005 — pyannote community-1, nombre de locuteurs oracle par fichier, AMI SDM (dev et test)

## Observations factuelles

Rédigées par le cockpit le 28/10/2026. Référence : EXP-0001 ; variable : nombre de locuteurs oracle par fichier.

| Mesure (sans collar) | dev | test |
|---|---|---|
| DER | 18,71 % (EXP-0001 : 18,64) | 20,40 % (EXP-0001 : 19,92) |
| Confusion | 5,75 (EXP-0001 : 5,68) | 5,42 (EXP-0001 : 4,94) |
| JER | 23,60 % (EXP-0001 : 23,75) | 26,91 % (EXP-0001 : 27,07) |
| Écart de DER à EXP-0001, IC à 95 % | +0,07 [−0,16 ; +0,39] ; 1/18 amélioré, 16 égaux | +0,48 [−0,61 ; +2,50] ; 3/16 améliorés, 12 égaux |

Seuls changent les fichiers où EXP-0001 se trompait sur le nombre. Sur le test : IS1009b 16,37 → 13,21 % (5 → 4 locuteurs), ES2004b 16,02 → 15,24 % (6 → 4), ES2004c 14,21 → 13,70 % (5 → 4), TS3003a 26,10 → 49,36 % (2 → 4 ; confusion 7,26 → 30,52 points ; JER 69,79 → 68,04 %).

## Interprétation (cockpit)

**Pour pyannote, connaître le nombre de locuteurs ne fait rien gagner en moyenne.** Quand pyannote surestimait (3 réunions), imposer 4 améliore un peu le DER (de 0,5 à 3 points). Quand il sous-estimait fortement (TS3003a), imposer 4 est catastrophique : le DER double et la confusion passe de 7 à 31 points, sans que le JER s'améliore. Les deux locuteurs que pyannote ne trouvait pas ne sont pas retrouvés pour autant. Forcer deux groupes de plus découpe la parole des locuteurs principaux. Ces deux participants parlent probablement trop peu, ou trop faiblement, pour être modélisés **[probable : leur temps de parole dans la référence reste à vérifier]**.

**Conséquence pour D9.** L'amélioration n° 1 (estimation du nombre de locuteurs) reposait sur l'idée que c'était la source d'erreur la plus probable. Sur AMI, pour pyannote, ce n'est pas le cas : même un oracle n'apporte rien. Le chevauchement et la parole manquée concentrent l'erreur (EXP-0001). Ce constat devra être revérifié sur le jeu francophone, où le nombre de locuteurs varie de 2 à 6, alors qu'il vaut toujours 4 dans AMI. Il pèse néanmoins sur le choix des améliorations.
