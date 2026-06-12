# Notice de retour d'expÃ©rience : problÃ¨mes rencontrÃ©s et corrections mises en oeuvre

Cette notice regroupe des exemples concrets de problÃ¨mes rencontrÃ©s pendant le dÃ©veloppement et l'intÃ©gration du projet de station de recharge intelligente.
L'objectif est de pouvoir expliquer, pendant la soutenance, comment les dysfonctionnements ont Ã©tÃ© diagnostiquÃ©s, corrigÃ©s et transformÃ©s en choix techniques plus robustes.

## 1. QR de session mobile invalide ou expirÃ©

### ProblÃ¨me observÃ©

La PWA fonctionnait sur smartphone, mais le QR code affichÃ© sur le kiosk renvoyait vers une session mobile invalide ou expirÃ©e.

Dans certains tests, le tÃ©lÃ©phone pouvait accÃ©der Ã  l'application via une adresse de pont rÃ©seau, par exemple :

```text
https://10.156.171.37:8443
```

alors que le kiosk gÃ©nÃ©rait parfois un QR vers :

```text
https://192.168.10.10/mobile-session.html?token=...
```

Le tÃ©lÃ©phone pouvait donc ouvrir l'application, mais pas forcÃ©ment la bonne origine applicative pour la session QR.

### Cause identifiÃ©e

Le projet distingue deux adresses :

- l'adresse utilisÃ©e par le Raspberry pour joindre l'API backend ;
- l'adresse publique que le smartphone doit ouvrir en scannant le QR.

Ces deux adresses ne sont pas toujours identiques, surtout en dÃ©monstration avec un pont rÃ©seau, un hotspot ou un accÃ¨s HTTPS local.

### Correction mise en oeuvre

Le fonctionnement a Ã©tÃ© sÃ©parÃ© proprement :

- `BACKEND_API_BASE_URL` sert au Raspberry pour appeler l'API ;
- `MOBILE_FRONTEND_BASE_URL` ou le paramÃ¨tre `mobile_frontend` sert Ã  gÃ©nÃ©rer l'URL du QR pour le smartphone.

RÃ©fÃ©rences principales :

- [raspberry/app/main.py](raspberry/app/main.py) injecte la configuration kiosk cÃ´tÃ© frontend ;
- [raspberry/app/app.js](raspberry/app/app.js) rÃ©sout l'URL publique mobile avec `resolveMobileFrontendBaseUrl()` ;
- [backend/api/views.py](backend/api/views.py) construit l'URL de session mobile avec `_mobile_session_url()`.

Le kiosk renouvelle aussi automatiquement une session mobile proche de l'expiration, afin d'Ã©viter d'afficher un QR pÃ©rimÃ©.

### RÃ©sultat

Le tÃ©lÃ©phone scanne un QR qui pointe vers la mÃªme origine que l'application mobile rÃ©ellement utilisÃ©e.
Le Raspberry continue de communiquer avec le backend par son adresse rÃ©seau interne, sans imposer cette adresse au smartphone.

## 2. Confusion entre QR de rÃ©servation et QR de borne

### ProblÃ¨me observÃ©

Pendant la conception, il y avait une ambiguÃ¯tÃ© entre deux QR codes :

- le QR gÃ©nÃ©rÃ© lors de la rÃ©servation ;
- le QR affichÃ© par la borne pour dÃ©marrer une session mobile.

Cela rendait le parcours utilisateur difficile Ã  expliquer.

### Cause identifiÃ©e

Les deux QR n'ont pas le mÃªme rÃ´le :

- le QR de rÃ©servation contient un secret liÃ© Ã  une rÃ©servation prÃ©cise ;
- le QR de borne contient un jeton temporaire de liaison entre le tÃ©lÃ©phone et la borne.

Le QR de borne ne sait pas encore quel utilisateur ou quelle rÃ©servation sera utilisÃ©e. C'est seulement aprÃ¨s connexion sur le tÃ©lÃ©phone que l'utilisateur choisit une rÃ©servation compatible.

### Correction mise en oeuvre

Le workflow a Ã©tÃ© clarifiÃ© :

1. la borne affiche un QR temporaire ;
2. l'utilisateur scanne le QR avec son tÃ©lÃ©phone ;
3. il se connecte Ã  la PWA ;
4. la PWA liste les rÃ©servations compatibles avec la borne ;
5. l'utilisateur choisit la rÃ©servation ;
6. la borne consomme la session mobile et ouvre l'emplacement.

RÃ©fÃ©rences principales :

- [frontend/mobile-session.html](frontend/mobile-session.html) pour l'Ã©cran mobile ;
- [frontend/js/mobile-session.js](frontend/js/mobile-session.js) pour le choix de rÃ©servation ;
- [backend/api/views.py](backend/api/views.py) pour les endpoints `mobile-sessions`.

### RÃ©sultat

Le QR de rÃ©servation reste un moyen d'accÃ¨s direct Ã  la rÃ©servation.
Le QR de borne devient un mÃ©canisme de liaison temporaire entre un tÃ©lÃ©phone et une borne physique.

## 3. AccÃ¨s refusÃ© aprÃ¨s authentification RFID

### ProblÃ¨me observÃ©

Lors d'un test rÃ©el, le badge RFID Ã©tait dÃ©tectÃ©, mais la borne affichait un accÃ¨s refusÃ©.

### Cause identifiÃ©e

Le badge seul ne suffit pas. Le backend vÃ©rifie aussi :

- que le badge est associÃ© Ã  un utilisateur ;
- que l'utilisateur possÃ¨de une rÃ©servation active ou proche du crÃ©neau ;
- que la rÃ©servation correspond bien Ã  la station, Ã  la borne et Ã  l'emplacement concernÃ©s ;
- que l'accÃ¨s n'est pas expirÃ©, rÃ©voquÃ© ou dÃ©jÃ  consommÃ©.

Une mauvaise configuration du terminal, des identifiants station/borne, ou un cache offline obsolÃ¨te peut donc provoquer un refus mÃªme si le badge est reconnu.

### Correction mise en oeuvre

La configuration du terminal a Ã©tÃ© centralisÃ©e et synchronisÃ©e avec le backend :

- `TERMINAL_CODE` identifie la borne physique ;
- le backend renvoie la station, la borne, les emplacements et les topics MQTT associÃ©s ;
- le Raspberry synchronise un cache offline des rÃ©servations utilisables.

RÃ©fÃ©rences principales :

- [backend/api/views.py](backend/api/views.py) pour l'authentification terminal ;
- [raspberry/app/main.py](raspberry/app/main.py) pour la configuration terminal et les appels backend ;
- [raspberry/app/offline_store.py](raspberry/app/offline_store.py) pour le cache local.

### RÃ©sultat

Le badge RFID est traitÃ© comme un facteur d'accÃ¨s, mais la dÃ©cision finale reste contrÃ´lÃ©e par le backend ou par le cache offline synchronisÃ©.

## 4. Commande MQTT envoyÃ©e mais ACK non reÃ§u

### ProblÃ¨me observÃ©

Pendant un test, la serrure s'est dÃ©verrouillÃ©e physiquement, mais le kiosk a affichÃ© une erreur du type :

```text
commande MQTT ACK non reÃ§u
```

### Cause identifiÃ©e

Cela signifie que la commande MQTT a Ã©tÃ© publiÃ©e, mais que le Raspberry ou le backend n'a pas reÃ§u l'accusÃ© de rÃ©ception attendu.

Les causes possibles sont :

- mauvais identifiant ou mot de passe Mosquitto ;
- ACL MQTT trop restrictive ;
- topic d'ACK diffÃ©rent de celui attendu ;
- ESP32 qui exÃ©cute l'action mais ne publie pas l'ACK ;
- latence ou timeout trop court.

### Correction mise en oeuvre

Le contrat MQTT a Ã©tÃ© formalisÃ© :

- chaque commande contient un `command_id` ;
- l'ESP32 doit rÃ©pondre avec un ACK contenant ce mÃªme `command_id` ;
- les topics sont structurÃ©s par station, borne et emplacement ;
- l'obligation d'ACK est configurable avec `MQTT_ACK_REQUIRED` ;
- un timeout clair permet de distinguer une action refusÃ©e d'une action non confirmÃ©e.

RÃ©fÃ©rences principales :

- [backend/api/services/mqtt_commands.py](backend/api/services/mqtt_commands.py) pour l'envoi des commandes ;
- [raspberry/app/mqtt_client.py](raspberry/app/mqtt_client.py) pour la communication Raspberry/ESP32 ;
- [docs/source/raspberry_esp32_contract.rst](docs/source/raspberry_esp32_contract.rst) pour le contrat technique.

### RÃ©sultat

La supervision ne se contente pas de supposer qu'une commande a fonctionnÃ© : elle attend une confirmation explicite.
C'est plus sÃ»r pour un systÃ¨me industriel, car l'Ã©tat logiciel doit rester cohÃ©rent avec l'Ã©tat physique.

## 5. Session de recharge crÃ©Ã©e trop tÃ´t

### ProblÃ¨me observÃ©

Une session semblait dÃ©marrer juste aprÃ¨s le passage du badge et le dÃ©verrouillage de la serrure.

### Cause identifiÃ©e

Le bon fonctionnement mÃ©tier n'est pas :

```text
badge acceptÃ© -> charge dÃ©marrÃ©e
```

mais plutÃ´t :

```text
badge acceptÃ© -> serrure ouverte -> attente branchement -> courant dÃ©tectÃ© -> charge en cours
```

Sans capteur de cÃ¢ble ni capteur d'ouverture, le prototype utilise provisoirement la dÃ©tection de courant comme preuve de branchement.

### Correction mise en oeuvre

La machine d'Ã©tat a Ã©tÃ© clarifiÃ©e :

- `reserved` : rÃ©servation crÃ©Ã©e ;
- `access_validated` : accÃ¨s validÃ© ;
- `waiting_plug` : emplacement ouvert, attente de branchement ;
- `charging` : courant dÃ©tectÃ©, charge en cours ;
- `stopping` : arrÃªt demandÃ© ;
- `stopped` : session terminÃ©e ;
- `error` : anomalie.

RÃ©fÃ©rences principales :

- [backend/api/models.py](backend/api/models.py) pour les statuts mÃ©tier ;
- [raspberry/app/charge_state.py](raspberry/app/charge_state.py) pour la logique kiosk ;
- [esp32/emplacement1/main.py](esp32/emplacement1/main.py) pour la dÃ©tection courant et la tÃ©lÃ©mÃ©trie.

### RÃ©sultat

L'ouverture de la serrure ne signifie plus automatiquement que la charge a commencÃ©.
La charge est considÃ©rÃ©e active lorsque la tÃ©lÃ©mÃ©trie indique un courant supÃ©rieur au seuil prÃ©vu.

## 6. Emplacement bloquÃ© par une session non clÃ´turÃ©e

### ProblÃ¨me observÃ©

Pendant les tests QR, l'application a refusÃ© l'accÃ¨s avec un message indiquant que l'emplacement Ã©tait dÃ©jÃ  occupÃ© par une autre session.

### Cause identifiÃ©e

Lors des essais successifs, certaines sessions de recharge pouvaient rester dans un Ã©tat intermÃ©diaire, par exemple `waiting_plug` ou `charging`, sans Ãªtre clÃ´turÃ©es proprement.

Avec un seul ESP32 et un seul emplacement rÃ©ellement testÃ©, cela empÃªchait de rejouer facilement un scÃ©nario de dÃ©monstration.

### Correction mise en oeuvre

La logique de consommation de session mobile et de validation terminal a Ã©tÃ© durcie :

- une ancienne session prÃ©-charge peut Ãªtre libÃ©rÃ©e lorsqu'elle est devenue incohÃ©rente ;
- les statuts de rÃ©servation et de session sont mieux distinguÃ©s ;
- les tests automatisÃ©s couvrent le cas d'une session prÃ©-charge bloquante.

RÃ©fÃ©rences principales :

- [backend/api/tests/test_terminal_auth.py](backend/api/tests/test_terminal_auth.py) ;
- [backend/api/views.py](backend/api/views.py).

### RÃ©sultat

Le systÃ¨me Ã©vite qu'un ancien Ã©tat de test bloque dÃ©finitivement l'emplacement.
La cohÃ©rence entre rÃ©servation, session et Ã©tat physique est mieux maÃ®trisÃ©e.

## 7. TÃ©lÃ©mÃ©trie visible dans Grafana mais pas liÃ©e au bon emplacement

### ProblÃ¨me observÃ©

Au dÃ©but des tests, plusieurs emplacements pouvaient apparaÃ®tre en charge dans Grafana alors qu'un seul emplacement devait Ãªtre simulÃ©.

### Cause identifiÃ©e

La simulation publiait des donnÃ©es trop globales ou sur plusieurs slots, ce qui ne correspondait pas au scÃ©nario rÃ©el de dÃ©monstration avec un seul ESP32.

### Correction mise en oeuvre

La simulation a Ã©tÃ© limitÃ©e Ã  l'emplacement rÃ©ellement validÃ© par la rÃ©servation.
Les mÃ©triques MQTT ont Ã©tÃ© rattachÃ©es Ã  :

- la station ;
- la borne ;
- l'emplacement ;
- la session de recharge lorsque disponible.

RÃ©fÃ©rences principales :

- [backend/api/services/mqtt_simulator.py](backend/api/services/mqtt_simulator.py) ;
- [backend/api/mqtt.py](backend/api/mqtt.py) ;
- [grafana/dashboards/station-supervision.json](grafana/dashboards/station-supervision.json).

### RÃ©sultat

Grafana peut afficher une vision globale, mais aussi suivre un emplacement ou une session prÃ©cise.
Cela Ã©vite de prÃ©senter des donnÃ©es de supervision incohÃ©rentes avec la dÃ©monstration physique.

## 8. DonnÃ©es Ã©lectriques non rÃ©alistes

### ProblÃ¨me observÃ©

Les premiÃ¨res valeurs simulÃ©es de courant, de puissance ou d'Ã©nergie variaient trop fortement.

### Cause identifiÃ©e

Une simulation trop alÃ©atoire ne reprÃ©sente pas correctement une charge Ã©lectrique.
Dans un comportement rÃ©aliste, les mesures doivent varier progressivement, avec une part de bruit faible.

### Correction mise en oeuvre

La simulation a Ã©tÃ© rendue plus progressive :

- courant autour d'une valeur nominale ;
- bruit limitÃ© ;
- puissance calculÃ©e avec `P = U x I` ;
- Ã©nergie cumulÃ©e par intÃ©gration dans le temps.

RÃ©fÃ©rences principales :

- [backend/api/services/mqtt_simulator.py](backend/api/services/mqtt_simulator.py) ;
- [backend/api/tests/test_mqtt_simulator.py](backend/api/tests/test_mqtt_simulator.py).

### RÃ©sultat

Les graphes de Grafana sont plus crÃ©dibles pour une dÃ©monstration.
Les valeurs suivent une logique physique comprÃ©hensible : courant, tension, puissance et Ã©nergie sont cohÃ©rents entre eux.

## 9. Carte OpenStreetMap difficile Ã  afficher sur mobile

### ProblÃ¨me observÃ©

La carte de rÃ©servation pouvait apparaÃ®tre aprÃ¨s rechargement sur PC, mais rester invisible sur smartphone.

### Cause identifiÃ©e

Leaflet nÃ©cessite un conteneur dÃ©jÃ  visible et dimensionnÃ© pour calculer correctement la carte.
Sur mobile, les changements de layout, les onglets, le cache PWA ou un chargement tardif peuvent provoquer une carte vide si `invalidateSize()` n'est pas appelÃ© au bon moment.

### Correction mise en oeuvre

Le chargement de la carte a Ã©tÃ© revu pour tenir compte :

- de la disponibilitÃ© du conteneur ;
- de l'affichage responsive ;
- du rechargement aprÃ¨s navigation ;
- de l'accÃ¨s aux tuiles OpenStreetMap.

RÃ©fÃ©rences principales :

- [frontend/js/reservation.js](frontend/js/reservation.js) ;
- [frontend/css/auth.css](frontend/css/auth.css).

### RÃ©sultat

La carte est traitÃ©e comme un composant dynamique, pas comme une image statique.
Cela amÃ©liore la robustesse sur smartphone et en dÃ©monstration.

## 10. Boutons et textes orientÃ©s dÃ©veloppement dans l'interface

### ProblÃ¨me observÃ©

Certaines pages affichaient des textes peu adaptÃ©s Ã  une interface de production, par exemple :

- messages de prÃ©visualisation ;
- indications trop techniques ;
- boutons inutiles ou redondants ;
- termes comme `ACK`, `cookie httponly` ou dÃ©tails internes visibles au mauvais endroit.

### Cause identifiÃ©e

Pendant le dÃ©veloppement, ces libellÃ©s Ã©taient utiles pour comprendre l'Ã©tat technique de l'application.
Mais ils n'ont pas leur place dans une interface destinÃ©e Ã  un utilisateur, un administrateur ou un technicien.

### Correction mise en oeuvre

Les interfaces ont Ã©tÃ© revues par rÃ´le :

- utilisateur : rÃ©servation, profil, accÃ¨s ;
- administrateur : supervision, infrastructure, exports, utilisateurs ;
- technicien : stations affectÃ©es, maintenance, alertes ;
- kiosk : parcours tactile sobre et guidÃ©.

Les libellÃ©s ont Ã©tÃ© remplacÃ©s par un vocabulaire mÃ©tier comprÃ©hensible.

RÃ©fÃ©rences principales :

- [frontend/js/admin-dashboard.js](frontend/js/admin-dashboard.js) ;
- [frontend/js/dashboard.js](frontend/js/dashboard.js) ;
- [frontend/js/mobile-session.js](frontend/js/mobile-session.js) ;
- [raspberry/app/app.js](raspberry/app/app.js).

### RÃ©sultat

L'application est plus proche d'un produit industriel : les dÃ©tails techniques restent disponibles dans les logs, les notices et la supervision, mais ne polluent plus l'expÃ©rience utilisateur.

## 11. ProblÃ¨mes d'accÃ¨s rÃ©seau entre PC, serveur, Raspberry et smartphone

### ProblÃ¨me observÃ©

Selon le rÃ©seau utilisÃ©, certaines parties du systÃ¨me Ã©taient accessibles et d'autres non :

- backend accessible mais kiosk inaccessible ;
- application accessible sur PC mais pas sur smartphone ;
- QR de session mobile inaccessible ;
- ESP32 connectÃ© au Wi-Fi mais incapable de joindre Mosquitto.

### Cause identifiÃ©e

Le projet utilise plusieurs Ã©quipements et plusieurs points de vue rÃ©seau :

- PC de dÃ©veloppement ;
- serveur Debian ;
- Raspberry kiosk ;
- ESP32 ;
- smartphone ;
- broker MQTT.

Une adresse IP correcte pour le PC n'est pas forcÃ©ment correcte pour le smartphone ou pour l'ESP32.

### Correction mise en oeuvre

La configuration a Ã©tÃ© sÃ©parÃ©e :

- serveur web HTTPS : adresse utilisÃ©e par les navigateurs ;
- backend API : adresse utilisÃ©e par les services internes ;
- MQTT broker : adresse utilisÃ©e par Raspberry, backend et ESP32 ;
- URL mobile : adresse encodÃ©e dans le QR kiosk.

Les variables d'environnement permettent d'adapter ces adresses sans modifier le code.

RÃ©fÃ©rences principales :

- [.env.example](.env.example) ;
- [docker-compose.prod.yml](docker-compose.prod.yml) ;
- [raspberry/app/main.py](raspberry/app/main.py) ;
- [esp32/emplacement1/main.py](esp32/emplacement1/main.py).

### RÃ©sultat

Le projet peut fonctionner en local, en dÃ©monstration rÃ©seau isolÃ© ou sur serveur Debian, Ã  condition d'aligner les URL selon le point de vue de chaque Ã©quipement.

## 12. Authentification et sÃ©curitÃ© des secrets

### ProblÃ¨me observÃ©

Le projet manipule plusieurs secrets :

- mots de passe utilisateurs ;
- secrets de borne ;
- tokens QR ;
- codes SMS ;
- identifiants MQTT ;
- certificats TLS.

Il fallait Ã©viter de traiter ces secrets comme de simples chaÃ®nes affichÃ©es ou comparÃ©es sans prÃ©caution.

### Correction mise en oeuvre

Plusieurs mÃ©canismes ont Ã©tÃ© retenus :

- Django gÃ¨re le hachage des mots de passe avec sel, algorithme et vÃ©rification sÃ©curisÃ©e ;
- les codes temporaires sont stockÃ©s sous forme hachÃ©e cÃ´tÃ© backend ;
- les comparaisons sensibles utilisent des mÃ©thodes rÃ©sistantes aux attaques par timing lorsque nÃ©cessaire ;
- les secrets de terminal sont envoyÃ©s dans des en-tÃªtes dÃ©diÃ©s ;
- les QR et sessions mobiles ont une durÃ©e de validitÃ© limitÃ©e ;
- le rate limiting limite les essais abusifs.

RÃ©fÃ©rences principales :

- [backend/api/models.py](backend/api/models.py) ;
- [backend/api/views.py](backend/api/views.py) ;
- [backend/api/throttles.py](backend/api/throttles.py) ;
- [backend/config/settings.py](backend/config/settings.py).

### RÃ©sultat

Le projet applique une logique `security by design` : les contrÃ´les ne sont pas ajoutÃ©s seulement Ã  la fin, ils structurent le fonctionnement des accÃ¨s, des tokens et des sessions.

## 13. DonnÃ©es personnelles, anonymisation et suppression de compte

### ProblÃ¨me observÃ©

Lors de tests de suppression d'utilisateur, des rÃ©servations archivÃ©es affichaient encore des informations liÃ©es Ã  un compte supprimÃ©.

### Cause identifiÃ©e

Un systÃ¨me de rÃ©servation doit conserver certaines traces techniques pour l'audit ou la supervision, mais ne doit pas conserver inutilement les donnÃ©es directement identifiantes d'un utilisateur supprimÃ©.

### Correction mise en oeuvre

La suppression de compte a Ã©tÃ© traitÃ©e comme une anonymisation mÃ©tier :

- l'utilisateur n'est plus directement identifiable ;
- les historiques nÃ©cessaires restent exploitables ;
- les donnÃ©es personnelles sont remplacÃ©es par des valeurs anonymisÃ©es lorsque nÃ©cessaire.

RÃ©fÃ©rences principales :

- [backend/api/views.py](backend/api/views.py) ;
- [backend/api/models.py](backend/api/models.py) ;
- [docs/source/debian_production_deployment.rst](docs/source/debian_production_deployment.rst).

### RÃ©sultat

Le projet applique une logique `privacy by design` : les donnÃ©es conservÃ©es aprÃ¨s suppression sont limitÃ©es Ã  ce qui est nÃ©cessaire pour l'exploitation et la traÃ§abilitÃ©.

## 14. Mauvais affichage ou incohÃ©rences dans le dashboard de supervision

### ProblÃ¨me observÃ©

Certains indicateurs de supervision pouvaient Ãªtre trompeurs :

- ESP32 affichÃ© en ligne alors qu'il ne l'Ã©tait pas ;
- emplacement affichÃ© disponible sans donnÃ©es rÃ©elles ;
- sÃ©vÃ©ritÃ© haute pas assez visible ;
- termes trop techniques dans le dashboard.

### Cause identifiÃ©e

Un dashboard de supervision ne doit pas simplement afficher des donnÃ©es de test.
Il doit reflÃ©ter un Ã©tat opÃ©rationnel fiable et comprÃ©hensible.

### Correction mise en oeuvre

Les donnÃ©es de dÃ©monstration ont Ã©tÃ© rendues plus minimalistes et plus rÃ©alistes :

- pas d'adresse IP ou MAC inventÃ©e ;
- pas de session active fictive ;
- pas d'ESP32 en ligne sans tÃ©lÃ©mÃ©trie rÃ©elle ;
- vocabulaire orientÃ© exploitation plutÃ´t que dÃ©veloppement.

RÃ©fÃ©rences principales :

- [backend/api/management/commands/bootstrap_demo_data.py](backend/api/management/commands/bootstrap_demo_data.py) ;
- [frontend/js/admin-dashboard.js](frontend/js/admin-dashboard.js) ;
- [grafana/dashboards/station-supervision.json](grafana/dashboards/station-supervision.json).

### RÃ©sultat

Le dashboard devient un outil d'aide Ã  l'exploitation, pas seulement une page de dÃ©monstration.

## 15. Besoin d'un mode dÃ©monstration reproductible

### ProblÃ¨me observÃ©

Avec un seul ESP32 et un seul prototype physique, les tests successifs pouvaient laisser des Ã©tats incohÃ©rents :

- sessions en cours ;
- accÃ¨s dÃ©jÃ  consommÃ©s ;
- cache offline encore prÃ©sent ;
- badge RFID dÃ©jÃ  associÃ© ;
- rÃ©servation passÃ©e ou archivÃ©e.

### Cause identifiÃ©e

La dÃ©monstration nÃ©cessite un Ã©tat de dÃ©part propre.
Sans cela, un test prÃ©cÃ©dent peut influencer le scÃ©nario suivant.

### Correction mise en oeuvre

Le projet prÃ©voit :

- un jeu d'essai minimaliste ;
- des commandes de bootstrap ;
- une sÃ©paration entre donnÃ©es de dÃ©monstration et donnÃ©es rÃ©ellement mesurÃ©es ;
- une procÃ©dure de redÃ©marrage kiosk/Raspberry lorsque le cache offline doit Ãªtre resynchronisÃ©.

RÃ©fÃ©rences principales :

- [backend/api/management/commands/bootstrap_demo_data.py](backend/api/management/commands/bootstrap_demo_data.py) ;
- [raspberry/app/offline_store.py](raspberry/app/offline_store.py) ;
- [docs/source/testing_strategy.rst](docs/source/testing_strategy.rst).

### RÃ©sultat

La dÃ©monstration peut Ãªtre rejouÃ©e plus facilement et les incidents de test sont plus simples Ã  expliquer.

## SynthÃ¨se pour la soutenance

Ces problÃ¨mes montrent plusieurs compÃ©tences importantes :

- diagnostic rÃ©seau entre plusieurs Ã©quipements ;
- distinction entre Ã©tat logiciel et Ã©tat physique ;
- sÃ©curisation des accÃ¨s par tokens, secrets, TTL et rate limiting ;
- mise en place d'un contrat MQTT avec accusÃ©s de rÃ©ception ;
- amÃ©lioration progressive de l'expÃ©rience utilisateur ;
- cohÃ©rence entre backend, kiosk, ESP32, supervision et documentation ;
- prise en compte de la sÃ©curitÃ© et des donnÃ©es personnelles dÃ¨s la conception.

La valeur du projet ne vient donc pas uniquement du fait qu'une rÃ©servation peut ouvrir une serrure.
Elle vient surtout de la robustesse construite autour du scÃ©nario : authentification, validation, tÃ©lÃ©mÃ©trie, supervision, traÃ§abilitÃ©, mode dÃ©gradÃ© et documentation.
