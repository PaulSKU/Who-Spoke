---
id: A-0002
question: "Comment pyannote et la baseline ECAPA se dégradent-ils sur SUMM-RE test dégradé, par condition et par sous-groupe ?"
verdict: informatif
decisions: [D24]
---

# A-0002 — robustesse sur SUMM-RE test dégradé (D24)

## Observations factuelles

Sources : EXP-0020 (pyannote), EXP-0021 (baseline ECAPA) ; propre : EXP-0007, EXP-0012. 37 réunions (34 « autres », 3 Zoom ; pas d'intervalle de confiance sous 5 réunions). DER sans collar, écart au propre avec IC à 95 % (bootstrap apparié).

| Condition | pyannote | Écart | ECAPA | Écart | pyannote − ECAPA |
|---|---|---|---|---|---|
| propre | 26,3 % | — | 33,4 % | — | −7,1 [−9,8 ; −3,7] |
| cod16 | 25,5 % | −0,8 [−1,6 ; +0,3] | 32,7 % | −0,7 [−1,2 ; −0,2] | −7,2 [−10,1 ; −3,8] |
| bru15 | 26,8 % | +0,5 [+0,3 ; +0,9] | 39,1 % | +5,7 [+4,3 ; +7,4] | −12,3 [−14,8 ; −9,4] |
| rev04 | 28,8 % | +2,5 [+0,8 ; +4,4] | 35,5 % | +2,0 [+0,2 ; +3,7] | −6,7 [−9,3 ; −3,6] |
| bru05 | 30,2 % | +3,9 [+2,0 ; +6,0] | 47,4 % | +14,0 [+11,5 ; +16,8] | −17,2 [−19,6 ; −14,7] |
| cod08 | 30,2 % | +3,9 [+0,6 ; +7,5] | 38,4 % | +5,0 [+2,9 ; +7,2] | −8,2 [−11,6 ; −4,8] |
| salle | 41,2 % | +14,9 [+11,5 ; +18,8] | 49,2 % | +15,8 [+13,6 ; +18,1] | −8,0 [−10,9 ; −4,9] |
| rev08 | 41,2 % | +14,9 [+11,3 ; +18,5] | 40,8 % | +7,4 [+5,3 ; +9,6] | +0,4 [−2,8 ; +3,6] |

Composantes, pyannote : en rev08, parole manquée 7,2 → 23,2 points, fausse alarme 11,3 → 9,2 ; en cod08, confusion 7,9 → 14,4. Baseline ECAPA : en bru05, parole manquée 21,9 → 28,1 et fausse alarme 3,1 → 8,0 ; en rev08, confusion 8,5 → 13,3. RT60 mesurés (T20, médiane) : 0,40 s, 0,90 s et 0,66 s pour des cibles de 0,4, 0,8 et 0,6 s ; en T60, 30 à 45 % de plus (`rt60.csv`). Sous-groupe Zoom (3 réunions) : dégradations du même ordre ou plus faibles, sans intervalle.

## Interprétation (cockpit)

Les deux systèmes n'ont pas les mêmes faiblesses. pyannote tient le bruit et le codec moyen, mais la réverbération forte lui fait manquer de la parole. La baseline tient mieux la réverbération (sa détection par énergie ne perd pas de parole réverbérée), mais le bruit la fait chuter. Le codec bas débit dégrade l'attribution des deux systèmes, ce qui est cohérent avec un timbre appauvri qui rapproche les voix.

Pour la démonstration, la condition décisive est la salle réverbérante avec un seul micro, qui fait partie de la cible. En rev08, pyannote perd son avance ; dans la condition réaliste « salle » (réverbération moyenne et bruit), il garde 8 points d'avance. La réverbération simulée est un peu plus forte que visé (T20 de 0,90 s pour 0,8 s), et une salle de réunion réelle avec mobilier est probablement moins réverbérante **[probable]**. Le corpus maison, enregistré dans de vraies pièces, dira si cette faiblesse se retrouve en conditions réelles. Une déréverbération en amont est la piste d'amélioration logique, à tester seulement si le temps le permet avant le gel.
