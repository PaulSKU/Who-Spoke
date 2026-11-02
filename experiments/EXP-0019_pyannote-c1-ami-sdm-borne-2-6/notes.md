---
id: EXP-0019
question: "Borner le nombre de locuteurs entre 2 et 6 change-t-il pyannote sur AMI (D23, rang A2) ?"
verdict: informatif
decisions: [D23]
---

# EXP-0019 — pyannote-c1-ami-sdm-borne-2-6

## Observations factuelles

Bornes `min_speakers: 2`, `max_speakers: 6` ; configuration d'EXP-0001 par ailleurs.

DER sans collar 18,64 % (dev) et 19,92 % (test), identiques à EXP-0001. Nombre de groupes de VBx dans [2, 6] pour les 34 fichiers (de 2 pour TS3003a à 6 pour ES2004b) : aucun KMeans. Les 34 RTTM sont identiques à l'octet à ceux d'EXP-0001, et la sortie exclusive à celle d'EXP-0017. Écart à EXP-0001 : 0,00 sur dev et test.

Temps conformes (MPS et CPU). Exécution concurrente des sessions B et E (D21, amendement du 01/11), sans relevé de charge.

## Interprétation (cockpit)

Sur AMI, VBx reste dans les bornes pour tous les fichiers ; le résultat est identique à EXP-0001. Les bornes ne coûtent donc rien quand l'estimation est correcte.
