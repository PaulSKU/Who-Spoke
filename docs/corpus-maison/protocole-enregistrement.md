# Protocole d'enregistrement du corpus maison

Version 1.0 du 27 octobre 2026.

**Légende de confiance.** **[certain]** : vérifié. **[probable]** : non revérifié. **[incertain]** : à vérifier.

---

## 1. Objectif

Produire environ 30 minutes de réunions en français qui ressemblent aux conditions annoncées par le tuteur : mono, 2 à 6 personnes, une salle avec un seul micro et de l'écho, une visio, un peu de bruit. Chaque session doit être annotable avec précision. Une **référence fiable** compte davantage que la quantité.

## 2. Principe : un signal de test, des pistes d'aide

Chaque session produit deux sortes d'audio, aux rôles strictement séparés.

| Audio | Rôle | Fourni au système ? |
|---|---|---|
| **Signal de test** : l'appareil unique posé sur la table, ou le mixage de la visio | C'est ce que le système doit diariser ; il reproduit les conditions de la démonstration | Oui, et c'est le seul |
| **Pistes d'aide** : un téléphone posé près de chaque participant (à 20–40 cm), ou les pistes séparées de la visio | Servent uniquement à l'annotation : sur la piste de chacun, sa propre voix domine, ce qui permet de pré-annoter ses tours de parole automatiquement puis de corriger | **Jamais** |

Cette pré-annotation à partir des pistes individuelles évite de pré-annoter avec pyannote. Une référence construite en corrigeant la sortie de pyannote favoriserait pyannote dans l'évaluation.

## 3. Les trois sessions

| Code | Condition | Participants | Durée visée | Signal de test | Pistes d'aide |
|---|---|---|---|---|---|
| `M01` | Salle réverbérante (pièce peu meublée, surfaces dures), un seul appareil au centre de la table, à 1–2 m des participants | 4 à 6 | 10–12 min | Téléphone ou ordinateur portable au centre | Un téléphone devant chaque participant |
| `M02` | Visio (chaque participant depuis un lieu différent, avec son propre matériel) | 3 à 4 | 10–12 min | Enregistrement local du mixage par le logiciel de visio | Pistes séparées par participant si le logiciel le permet (Zoom propose une option d'enregistrement audio séparé par participant **[probable]**) ; à défaut, aucune piste d'aide et annotation à partir de zéro (session courte) |
| `M03` | Bruit de fond (café, espace ouvert, musique d'ambiance modérée) | 2 à 3 | 8–10 min | Téléphone au centre de la table | Un téléphone devant chaque participant |

L'ensemble couvre de 2 à 6 locuteurs. Si possible, réunir dans une même session au moins deux personnes aux voix proches (même tranche d'âge et même registre). C'est le cas le plus difficile pour l'étape de regroupement, et il est utile de le mesurer.

## 4. Sujet de discussion

Le sujet doit faire parler tout le monde, provoquer des échanges rapides et quelques interruptions, sans aborder de sujet personnel. Trois propositions :

| Sujet | Consigne donnée aux participants |
|---|---|
| Organiser un événement | « Vous devez organiser un week-end pour 20 personnes avec un budget limité. Mettez-vous d'accord sur le lieu, les activités et le budget. » |
| Classement collectif | « Classez ensemble ces cinq objets par ordre d'utilité pour survivre sur une île déserte. Vous devez arriver à un classement commun. » |
| Débat léger | « Faut-il supprimer les réunions du lundi matin ? Défendez votre avis et cherchez un compromis. » |

Consignes communes : parler naturellement, se couper la parole est permis, éviter de prononcer les noms des autres participants et toute information personnelle.

## 5. Matériel et réglages

| Point | Réglage |
|---|---|
| Format | WAV si l'application le permet ; sinon le format par défaut (m4a/AAC), à la meilleure qualité disponible. La normalisation en 16 kHz mono se fait ensuite (D15) |
| Signal de test | Appareil posé à plat, micro dégagé, ni dans une poche ni sous un objet ; mode « réunion » ou « réduction de bruit » désactivé si possible |
| Pistes d'aide | Téléphones en mode avion (pas d'interruption), écran verrouillé, posés devant chaque participant, micro orienté vers lui |
| Synchronisation | **Un claquement de mains net au début et un à la fin**, après le démarrage de tous les appareils. Il permet d'aligner les pistes et de corriger la dérive d'horloge entre appareils |
| Visio | Tester la fonction d'enregistrement et l'option de pistes séparées avant la session |

## 6. Déroulé d'une session

| Moment | Action |
|---|---|
| Avant | Vérifier les consentements signés (option 1 au minimum) ; attribuer les codes `S1`, `S2`… selon la place à table, en les notant dans la table de correspondance confidentielle ; charger et vider les téléphones ; mesurer approximativement la pièce |
| Démarrage | Lancer tous les appareils ; claquement de mains ; énoncer « Session M0x, début » ; en visio, rappeler oralement le consentement |
| Pendant | Laisser la discussion se dérouler sans intervenir ; noter l'heure de tout incident (bruit soudain, arrivée d'une personne extérieure) |
| Fin | Claquement de mains ; énoncer « fin » ; arrêter les appareils |
| Juste après | Copier tous les fichiers dans `data/raw/maison/M0x/` sous des noms neutres (`table.wav`, `S1.wav`…) ; vérifier qu'ils s'ouvrent ; remplir la fiche de session ; supprimer les copies restées sur les téléphones des participants |

## 7. Fiche de session (modèle)

À enregistrer dans `data/raw/maison/M0x/fiche.md`, sans aucun nom réel :

```markdown
# Fiche de session M0x

Date : AAAA-MM-JJ
Condition : salle réverbérante | visio | bruit de fond
Lieu (type, sans adresse) : …
Pièce : dimensions approximatives, surfaces (carrelage, vitres, moquette…)
Signal de test : appareil (modèle), application, format, position, distance moyenne aux participants
Pistes d'aide : appareils et formats, ou pistes séparées du logiciel de visio
Logiciel de visio (M02) : nom et version
Participants : nombre ; codes S1…Sn et place à table
Bruit de fond : nature et niveau estimé
Sujet de discussion : …
Durée brute : … ; instants des claquements : …
Incidents : (heure, description)
Consentements : option 1 / 2 / 3 par code (oui / non)
```

## 8. Points de vigilance

Les participants doivent être majeurs. Aucune session n'est enregistrée tant qu'un participant n'a pas signé l'option 1. Une fois enregistrés, les fichiers ne transitent par aucun service en ligne : copie par câble ou par AirDrop, pas d'envoi par messagerie ou par stockage en ligne. La visio fait exception pendant la réunion elle-même, ce que la notice d'information signale. Utiliser l'enregistrement **local** du logiciel, jamais l'enregistrement dans le cloud.
