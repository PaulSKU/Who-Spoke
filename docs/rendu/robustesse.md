# Robustesse (D24)

SUMM-RE test dégradé, références et UEM inchangés ; une expérience par moteur, un jeu évalué par condition (`results_summre-<condition>_test.json`). Écart au propre : DER dans la condition moins DER sur l'audio propre, sur les mêmes réunions, en points, intervalle de confiance à 95 % par bootstrap apparié sur les fichiers (1 000 tirages, graine 0). Propre : le jeu propre de l'expérience s'il existe, sinon le test de SUMM-RE de sa référence déclarée.

Aucun résultat d'A3 pour l'instant : ce tableau se remplit dès qu'une expérience contient des `results_summre-<condition>_test.json`.

Conditions prévues (`configs/summre_degrade.yaml`) : `rev04` (réverbération, RT60 visé 0,4 s) ; `rev08` (réverbération, RT60 visé 0,8 s) ; `bru15` (bruit, RSB 15 dB) ; `bru05` (bruit, RSB 5 dB) ; `cod16` (codec Opus 16 kbit/s) ; `cod08` (codec Opus 8 kbit/s) ; `salle` (réverbération, RT60 visé 0,6 s et bruit, RSB 10 dB).

**Sources.** Aucune expérience.
Fichiers : `results/leaderboard.csv` (contrôle), `results_<corpus>_<partition>.json` et `per_file_<corpus>_<partition>.csv` de chaque expérience.
