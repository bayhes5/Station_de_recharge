# Notice de retour d'expérience : problèmes rencontrés et corrections mises en oeuvre

Cette notice regroupe des exemples concrets de problèmes rencontrés pendant le développement et l'intégration du projet de station de recharge intelligente.
L'objectif est de pouvoir expliquer, pendant la soutenance, comment les dysfonctionnements ont été diagnostiqués, corrigés et transformés en choix techniques plus robustes.

## 1. QR de session mobile invalide ou expiré

### Problème observé

La PWA fonctionnait sur smartphone, mais le QR code affiché sur le kiosk renvoyait vers une session mobile invalide ou expirée.

Dans certains tests, le téléphone pouvait accéder à l'application via une adresse de pont réseau, par exemple :

```text
https://10.156.171.37:8443
```

alors que le kiosk générait parfois un QR vers :

```text
https://192.168.10.10/mobile-session.html?token=...
```

Le téléphone pouvait donc ouvrir l'application, mais pas forcément la bonne origine applicative pour la session QR.

### Cause identifiée

Le projet distingue deux adresses :

- l'adresse utilisée par le Raspberry pour joindre l'API backend ;
- l'adresse publique que le smartphone doit ouvrir en scannant le QR.

Ces deux adresses ne sont pas toujours identiques, surtout en démonstration avec un pont réseau, un hotspot ou un accès HTTPS local.

### Correction mise en oeuvre

Le fonctionnement a été séparé proprement :

- `BACKEND_API_BASE_URL` sert au Raspberry pour appeler l'API ;
- `MOBILE_FRONTEND_BASE_URL` ou le paramètre `mobile_frontend` sert à générer l'URL du QR pour le smartphone.

Références principales :

- [raspberry/app/main.py](raspberry/app/main.py) injecte la configuration kiosk côté frontend ;
- [raspberry/app/app.js](raspberry/app/app.js) résout l'URL publique mobile avec `resolveMobileFrontendBaseUrl()` ;
- [backend/api/views.py](backend/api/views.py) construit l'URL de session mobile avec `_mobile_session_url()`.

Le kiosk renouvelle aussi automatiquement une session mobile proche de l'expiration, afin d'éviter d'afficher un QR périmé.

### Résultat

Le téléphone scanne un QR qui pointe vers la même origine que l'application mobile réellement utilisée.
Le Raspberry continue de communiquer avec le backend par son adresse réseau interne, sans imposer cette adresse au smartphone.

## 2. Confusion entre QR de réservation et QR de borne

### Problème observé

Pendant la conception, il y avait une ambiguïté entre deux QR codes :

- le QR généré lors de la réservation ;
- le QR affiché par la borne pour démarrer une session mobile.

Cela rendait le parcours utilisateur difficile à expliquer.

### Cause identifiée

Les deux QR n'ont pas le même rôle :

- le QR de réservation contient un secret lié à une réservation précise ;
- le QR de borne contient un jeton temporaire de liaison entre le téléphone et la borne.

Le QR de borne ne sait pas encore quel utilisateur ou quelle réservation sera utilisée. C'est seulement après connexion sur le téléphone que l'utilisateur choisit une réservation compatible.

### Correction mise en oeuvre

Le workflow a été clarifié :

1. la borne affiche un QR temporaire ;
2. l'utilisateur scanne le QR avec son téléphone ;
3. il se connecte à la PWA ;
4. la PWA liste les réservations compatibles avec la borne ;
5. l'utilisateur choisit la réservation ;
6. la borne consomme la session mobile et ouvre l'emplacement.

Références principales :

- [frontend/mobile-session.html](frontend/mobile-session.html) pour l'écran mobile ;
- [frontend/js/mobile-session.js](frontend/js/mobile-session.js) pour le choix de réservation ;
- [backend/api/views.py](backend/api/views.py) pour les endpoints `mobile-sessions`.

### Résultat

Le QR de réservation reste un moyen d'accès direct à la réservation.
Le QR de borne devient un mécanisme de liaison temporaire entre un téléphone et une borne physique.

## 3. Accès refusé après authentification RFID

### Problème observé

Lors d'un test réel, le badge RFID était détecté, mais la borne affichait un accès refusé.

### Cause identifiée

Le badge seul ne suffit pas. Le backend vérifie aussi :

- que le badge est associé à un utilisateur ;
- que l'utilisateur possède une réservation active ou proche du créneau ;
- que la réservation correspond bien à la station, à la borne et à l'emplacement concernés ;
- que l'accès n'est pas expiré, révoqué ou déjà consommé.

Une mauvaise configuration du terminal, des identifiants station/borne, ou un cache offline obsolète peut donc provoquer un refus même si le badge est reconnu.

### Correction mise en oeuvre

La configuration du terminal a été centralisée et synchronisée avec le backend :

- `TERMINAL_CODE` identifie la borne physique ;
- le backend renvoie la station, la borne, les emplacements et les topics MQTT associés ;
- le Raspberry synchronise un cache offline des réservations utilisables.

Références principales :

- [backend/api/views.py](backend/api/views.py) pour l'authentification terminal ;
- [raspberry/app/main.py](raspberry/app/main.py) pour la configuration terminal et les appels backend ;
- [raspberry/app/offline_store.py](raspberry/app/offline_store.py) pour le cache local.

### Résultat

Le badge RFID est traité comme un facteur d'accès, mais la décision finale reste contrôlée par le backend ou par le cache offline synchronisé.

## 4. Commande MQTT envoyée mais ACK non reçu

### Problème observé

Pendant un test, la serrure s'est déverrouillée physiquement, mais le kiosk a affiché une erreur du type :

```text
commande MQTT ACK non reçu
```

### Cause identifiée

Cela signifie que la commande MQTT a été publiée, mais que le Raspberry ou le backend n'a pas reçu l'accusé de réception attendu.

Les causes possibles sont :

- mauvais identifiant ou mot de passe Mosquitto ;
- ACL MQTT trop restrictive ;
- topic d'ACK différent de celui attendu ;
- ESP32 qui exécute l'action mais ne publie pas l'ACK ;
- latence ou timeout trop court.

### Correction mise en oeuvre

Le contrat MQTT a été formalisé :

- chaque commande contient un `command_id` ;
- l'ESP32 doit répondre avec un ACK contenant ce même `command_id` ;
- les topics sont structurés par station, borne et emplacement ;
- l'obligation d'ACK est configurable avec `MQTT_ACK_REQUIRED` ;
- un timeout clair permet de distinguer une action refusée d'une action non confirmée.

Références principales :

- [backend/api/services/mqtt_commands.py](backend/api/services/mqtt_commands.py) pour l'envoi des commandes ;
- [raspberry/app/mqtt_client.py](raspberry/app/mqtt_client.py) pour la communication Raspberry/ESP32 ;
- [docs/source/raspberry_esp32_contract.rst](docs/source/raspberry_esp32_contract.rst) pour le contrat technique.

### Résultat

La supervision ne se contente pas de supposer qu'une commande a fonctionné : elle attend une confirmation explicite.
C'est plus sûr pour un système industriel, car l'état logiciel doit rester cohérent avec l'état physique.

## 5. Session de recharge créée trop tôt

### Problème observé

Une session semblait démarrer juste après le passage du badge et le déverrouillage de la serrure.

### Cause identifiée

Le bon fonctionnement métier n'est pas :

```text
badge accepté -> charge démarrée
```

mais plutôt :

```text
badge accepté -> serrure ouverte -> attente branchement -> courant détecté -> charge en cours
```

Sans capteur de câble ni capteur d'ouverture, le prototype utilise provisoirement la détection de courant comme preuve de branchement.

### Correction mise en oeuvre

La machine d'état a été clarifiée :

- `reserved` : réservation créée ;
- `access_validated` : accès validé ;
- `waiting_plug` : emplacement ouvert, attente de branchement ;
- `charging` : courant détecté, charge en cours ;
- `stopping` : arrêt demandé ;
- `stopped` : session terminée ;
- `error` : anomalie.

Références principales :

- [backend/api/models.py](backend/api/models.py) pour les statuts métier ;
- [raspberry/app/charge_state.py](raspberry/app/charge_state.py) pour la logique kiosk ;
- [esp32/emplacement1/main.py](esp32/emplacement1/main.py) pour la détection courant et la télémétrie.

### Résultat

L'ouverture de la serrure ne signifie plus automatiquement que la charge a commencé.
La charge est considérée active lorsque la télémétrie indique un courant supérieur au seuil prévu.

## 6. Emplacement bloqué par une session non clôturée

### Problème observé

Pendant les tests QR, l'application a refusé l'accès avec un message indiquant que l'emplacement était déjà occupé par une autre session.

### Cause identifiée

Lors des essais successifs, certaines sessions de recharge pouvaient rester dans un état intermédiaire, par exemple `waiting_plug` ou `charging`, sans être clôturées proprement.

Avec un seul ESP32 et un seul emplacement réellement testé, cela empêchait de rejouer facilement un scénario de démonstration.

### Correction mise en oeuvre

La logique de consommation de session mobile et de validation terminal a été durcie :

- une ancienne session pré-charge peut être libérée lorsqu'elle est devenue incohérente ;
- les statuts de réservation et de session sont mieux distingués ;
- les tests automatisés couvrent le cas d'une session pré-charge bloquante.

Références principales :

- [backend/api/tests/test_terminal_auth.py](backend/api/tests/test_terminal_auth.py) ;
- [backend/api/views.py](backend/api/views.py).

### Résultat

Le système évite qu'un ancien état de test bloque définitivement l'emplacement.
La cohérence entre réservation, session et état physique est mieux maîtrisée.

## 7. Télémétrie visible dans Grafana mais pas liée au bon emplacement

### Problème observé

Au début des tests, plusieurs emplacements pouvaient apparaître en charge dans Grafana alors qu'un seul emplacement devait être simulé.

### Cause identifiée

La simulation publiait des données trop globales ou sur plusieurs slots, ce qui ne correspondait pas au scénario réel de démonstration avec un seul ESP32.

### Correction mise en oeuvre

La simulation a été limitée à l'emplacement réellement validé par la réservation.
Les métriques MQTT ont été rattachées à :

- la station ;
- la borne ;
- l'emplacement ;
- la session de recharge lorsque disponible.

Références principales :

- [backend/api/services/mqtt_simulator.py](backend/api/services/mqtt_simulator.py) ;
- [backend/api/mqtt.py](backend/api/mqtt.py) ;
- [grafana/dashboards/station-supervision.json](grafana/dashboards/station-supervision.json).

### Résultat

Grafana peut afficher une vision globale, mais aussi suivre un emplacement ou une session précise.
Cela évite de présenter des données de supervision incohérentes avec la démonstration physique.

## 8. Données électriques non réalistes

### Problème observé

Les premières valeurs simulées de courant, de puissance ou d'énergie variaient trop fortement.

### Cause identifiée

Une simulation trop aléatoire ne représente pas correctement une charge électrique.
Dans un comportement réaliste, les mesures doivent varier progressivement, avec une part de bruit faible.

### Correction mise en oeuvre

La simulation a été rendue plus progressive :

- courant autour d'une valeur nominale ;
- bruit limité ;
- puissance calculée avec `P = U x I` ;
- énergie cumulée par intégration dans le temps.

Références principales :

- [backend/api/services/mqtt_simulator.py](backend/api/services/mqtt_simulator.py) ;
- [backend/api/tests/test_mqtt_simulator.py](backend/api/tests/test_mqtt_simulator.py).

### Résultat

Les graphes de Grafana sont plus crédibles pour une démonstration.
Les valeurs suivent une logique physique compréhensible : courant, tension, puissance et énergie sont cohérents entre eux.

## 9. Carte OpenStreetMap difficile à afficher sur mobile

### Problème observé

La carte de réservation pouvait apparaître après rechargement sur PC, mais rester invisible sur smartphone.

### Cause identifiée

Leaflet nécessite un conteneur déjà visible et dimensionné pour calculer correctement la carte.
Sur mobile, les changements de layout, les onglets, le cache PWA ou un chargement tardif peuvent provoquer une carte vide si `invalidateSize()` n'est pas appelé au bon moment.

### Correction mise en oeuvre

Le chargement de la carte a été revu pour tenir compte :

- de la disponibilité du conteneur ;
- de l'affichage responsive ;
- du rechargement après navigation ;
- de l'accès aux tuiles OpenStreetMap.

Références principales :

- [frontend/js/reservation.js](frontend/js/reservation.js) ;
- [frontend/css/auth.css](frontend/css/auth.css).

### Résultat

La carte est traitée comme un composant dynamique, pas comme une image statique.
Cela améliore la robustesse sur smartphone et en démonstration.

## 10. Boutons et textes orientés développement dans l'interface

### Problème observé

Certaines pages affichaient des textes peu adaptés à une interface de production, par exemple :

- messages de prévisualisation ;
- indications trop techniques ;
- boutons inutiles ou redondants ;
- termes comme `ACK`, `cookie httponly` ou détails internes visibles au mauvais endroit.

### Cause identifiée

Pendant le développement, ces libellés étaient utiles pour comprendre l'état technique de l'application.
Mais ils n'ont pas leur place dans une interface destinée à un utilisateur, un administrateur ou un technicien.

### Correction mise en oeuvre

Les interfaces ont été revues par rôle :

- utilisateur : réservation, profil, accès ;
- administrateur : supervision, infrastructure, exports, utilisateurs ;
- technicien : stations affectées, maintenance, alertes ;
- kiosk : parcours tactile sobre et guidé.

Les libellés ont été remplacés par un vocabulaire métier compréhensible.

Références principales :

- [frontend/js/admin-dashboard.js](frontend/js/admin-dashboard.js) ;
- [frontend/js/dashboard.js](frontend/js/dashboard.js) ;
- [frontend/js/mobile-session.js](frontend/js/mobile-session.js) ;
- [raspberry/app/app.js](raspberry/app/app.js).

### Résultat

L'application est plus proche d'un produit industriel : les détails techniques restent disponibles dans les logs, les notices et la supervision, mais ne polluent plus l'expérience utilisateur.

## 11. Problèmes d'accès réseau entre PC, serveur, Raspberry et smartphone

### Problème observé

Selon le réseau utilisé, certaines parties du système étaient accessibles et d'autres non :

- backend accessible mais kiosk inaccessible ;
- application accessible sur PC mais pas sur smartphone ;
- QR de session mobile inaccessible ;
- ESP32 connecté au Wi-Fi mais incapable de joindre Mosquitto.

### Cause identifiée

Le projet utilise plusieurs équipements et plusieurs points de vue réseau :

- PC de développement ;
- serveur Debian ;
- Raspberry kiosk ;
- ESP32 ;
- smartphone ;
- broker MQTT.

Une adresse IP correcte pour le PC n'est pas forcément correcte pour le smartphone ou pour l'ESP32.

### Correction mise en oeuvre

La configuration a été séparée :

- serveur web HTTPS : adresse utilisée par les navigateurs ;
- backend API : adresse utilisée par les services internes ;
- MQTT broker : adresse utilisée par Raspberry, backend et ESP32 ;
- URL mobile : adresse encodée dans le QR kiosk.

Les variables d'environnement permettent d'adapter ces adresses sans modifier le code.

Références principales :

- [.env.example](.env.example) ;
- [docker-compose.prod.yml](docker-compose.prod.yml) ;
- [raspberry/app/main.py](raspberry/app/main.py) ;
- [esp32/emplacement1/main.py](esp32/emplacement1/main.py).

### Résultat

Le projet peut fonctionner en local, en démonstration réseau isolé ou sur serveur Debian, à condition d'aligner les URL selon le point de vue de chaque équipement.

## 12. Authentification et sécurité des secrets

### Problème observé

Le projet manipule plusieurs secrets :

- mots de passe utilisateurs ;
- secrets de borne ;
- tokens QR ;
- codes SMS ;
- identifiants MQTT ;
- certificats TLS.

Il fallait éviter de traiter ces secrets comme de simples chaînes affichées ou comparées sans précaution.

### Correction mise en oeuvre

Plusieurs mécanismes ont été retenus :

- Django gère le hachage des mots de passe avec sel, algorithme et vérification sécurisée ;
- les codes temporaires sont stockés sous forme hachée côté backend ;
- les comparaisons sensibles utilisent des méthodes résistantes aux attaques par timing lorsque nécessaire ;
- les secrets de terminal sont envoyés dans des en-têtes dédiés ;
- les QR et sessions mobiles ont une durée de validité limitée ;
- le rate limiting limite les essais abusifs.

Références principales :

- [backend/api/models.py](backend/api/models.py) ;
- [backend/api/views.py](backend/api/views.py) ;
- [backend/api/throttles.py](backend/api/throttles.py) ;
- [backend/config/settings.py](backend/config/settings.py).

### Résultat

Le projet applique une logique `security by design` : les contrôles ne sont pas ajoutés seulement à la fin, ils structurent le fonctionnement des accès, des tokens et des sessions.

## 13. Données personnelles, anonymisation et suppression de compte

### Problème observé

Lors de tests de suppression d'utilisateur, des réservations archivées affichaient encore des informations liées à un compte supprimé.

### Cause identifiée

Un système de réservation doit conserver certaines traces techniques pour l'audit ou la supervision, mais ne doit pas conserver inutilement les données directement identifiantes d'un utilisateur supprimé.

### Correction mise en oeuvre

La suppression de compte a été traitée comme une anonymisation métier :

- l'utilisateur n'est plus directement identifiable ;
- les historiques nécessaires restent exploitables ;
- les données personnelles sont remplacées par des valeurs anonymisées lorsque nécessaire.

Références principales :

- [backend/api/views.py](backend/api/views.py) ;
- [backend/api/models.py](backend/api/models.py) ;
- [docs/source/debian_production_deployment.rst](docs/source/debian_production_deployment.rst).

### Résultat

Le projet applique une logique `privacy by design` : les données conservées après suppression sont limitées à ce qui est nécessaire pour l'exploitation et la traçabilité.

## 14. Mauvais affichage ou incohérences dans le dashboard de supervision

### Problème observé

Certains indicateurs de supervision pouvaient être trompeurs :

- ESP32 affiché en ligne alors qu'il ne l'était pas ;
- emplacement affiché disponible sans données réelles ;
- sévérité haute pas assez visible ;
- termes trop techniques dans le dashboard.

### Cause identifiée

Un dashboard de supervision ne doit pas simplement afficher des données de test.
Il doit refléter un état opérationnel fiable et compréhensible.

### Correction mise en oeuvre

Les données de démonstration ont été rendues plus minimalistes et plus réalistes :

- pas d'adresse IP ou MAC inventée ;
- pas de session active fictive ;
- pas d'ESP32 en ligne sans télémétrie réelle ;
- vocabulaire orienté exploitation plutôt que développement.

Références principales :

- [backend/api/management/commands/bootstrap_demo_data.py](backend/api/management/commands/bootstrap_demo_data.py) ;
- [frontend/js/admin-dashboard.js](frontend/js/admin-dashboard.js) ;
- [grafana/dashboards/station-supervision.json](grafana/dashboards/station-supervision.json).

### Résultat

Le dashboard devient un outil d'aide à l'exploitation, pas seulement une page de démonstration.

## 15. Besoin d'un mode démonstration reproductible

### Problème observé

Avec un seul ESP32 et un seul prototype physique, les tests successifs pouvaient laisser des états incohérents :

- sessions en cours ;
- accès déjà consommés ;
- cache offline encore présent ;
- badge RFID déjà associé ;
- réservation passée ou archivée.

### Cause identifiée

La démonstration nécessite un état de départ propre.
Sans cela, un test précédent peut influencer le scénario suivant.

### Correction mise en oeuvre

Le projet prévoit :

- un jeu d'essai minimaliste ;
- des commandes de bootstrap ;
- une séparation entre données de démonstration et données réellement mesurées ;
- une procédure de redémarrage kiosk/Raspberry lorsque le cache offline doit être resynchronisé.

Références principales :

- [backend/api/management/commands/bootstrap_demo_data.py](backend/api/management/commands/bootstrap_demo_data.py) ;
- [raspberry/app/offline_store.py](raspberry/app/offline_store.py) ;
- [docs/source/testing_strategy.rst](docs/source/testing_strategy.rst).

### Résultat

La démonstration peut être rejouée plus facilement et les incidents de test sont plus simples à expliquer.

## Synthèse pour la soutenance

Ces problèmes montrent plusieurs compétences importantes :

- diagnostic réseau entre plusieurs équipements ;
- distinction entre état logiciel et état physique ;
- sécurisation des accès par tokens, secrets, TTL et rate limiting ;
- mise en place d'un contrat MQTT avec accusés de réception ;
- amélioration progressive de l'expérience utilisateur ;
- cohérence entre backend, kiosk, ESP32, supervision et documentation ;
- prise en compte de la sécurité et des données personnelles dès la conception.

La valeur du projet ne vient donc pas uniquement du fait qu'une réservation peut ouvrir une serrure.
Elle vient surtout de la robustesse construite autour du scénario : authentification, validation, télémétrie, supervision, traçabilité, mode dégradé et documentation.
