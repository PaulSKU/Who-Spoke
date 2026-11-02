"""Chaîne de production des références du corpus maison (chantier E2).

Étapes de `docs/corpus-maison/conventions-annotation.md` §4, enregistrement par
enregistrement, dans `data/raw/maison/<Mxx>/` (non versionné, jamais envoyé hors de la
machine, D27) :

1. `synchro` : alignement de chaque piste d'aide (téléphone près d'un participant) sur
   le signal de test (appareil de table) par corrélation croisée autour des deux
   claquements de mains ; décalage et dérive consignés.
2. `preannotation` : sur les pistes d'aide alignées, la piste la plus forte désigne le
   locuteur ; export en étiquettes Audacity à corriger à la main.
3. `reference` : réimport des étiquettes corrigées, conversion en RTTM avec fusion des
   pauses de 200 ms ou moins, UEM, contrôles automatiques, accord entre deux annotations.

Le pas-à-pas destiné à la candidate est dans `docs/corpus-maison/guide-annotation.md` ;
le point d'entrée est `scripts/data/maison.py`. Aucun système évalué dans le projet
n'intervient dans la pré-annotation (conventions §4).
"""
