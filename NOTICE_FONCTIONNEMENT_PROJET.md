# Notice de fonctionnement du projet

Cette notice explique le fonctionnement global de la station de recharge intelligente, en partant du parcours utilisateur jusqu'aux flux techniques entre le frontend, le backend, le Raspberry Pi, les ESP32, MQTT, Redis/Celery, PostgreSQL/TimescaleDB et Grafana.

Elle complète la documentation Sphinx présente dans `docs/source/` avec une lecture plus transversale du projet.

Pour préparer les questions de soutenance du type "où ?", "comment ?", "avec quelle librairie ?" ou "quelle donnée est stockée ?", utiliser aussi :

- [`NOTICE_TECHNIQUE_IMPLEMENTATION.md`](NOTICE_TECHNIQUE_IMPLEMENTATION.md)
- [`NOTICE_SOUTENANCE_TECHNIQUE_DETAILLEE.md`](NOTICE_SOUTENANCE_TECHNIQUE_DETAILLEE.md)

Couverture des notices :

| Sujet | Explication fonctionnelle | Explication technique |
| --- | --- | --- |
| Authentification web, mots de passe, JWT | sections 3 et 4 | notice technique sections 1 à 5, notice soutenance sections 1 à 6 |
| Réservation et disponibilité | section 5 | notice technique section 13, notice soutenance section 13 |
| Moyens d'accès RFID, QR, mobile et SMS | section 6 | notice technique sections 6 à 12, notice soutenance sections 7 à 12 |
| Kiosque Raspberry et mode tactile | sections 7 et 8 | docs `raspberry_kiosk.rst`, notice soutenance section 15 |
| Session de charge, START/STOP et machine d'état | sections 9 et 10 | notice technique sections 14 à 16, notice soutenance sections 14, 16 et 22 |
| Firmware ESP32, capteurs et calculs électriques | section 11 | notice technique sections 16 et 17, notice soutenance sections 17 et 18 |
| MQTT, Redis, Celery et ingestion backend | sections 12 et 13 | notice technique sections 18 à 21 et 25, notice soutenance sections 19 à 23 |
| Base, TimescaleDB, anonymisation et rétention | sections 14 et 22 | notice technique sections 24 et 31, docs `database_mcd.rst` |
| Grafana, dashboard session et supervision temps réel | sections 15 et 16 | notice technique sections 24 et 29, notice soutenance sections 25 et 29 |
| Alertes, notifications et techniciens | sections 17 et 18 | notice technique sections 22 et 23, notice soutenance sections 26 à 28 |
| Mode dégradé Raspberry | section 19 | notice technique section 26, notice soutenance section 30 |
| Performance applicative et supervision | section 27 | notice technique section 32, notice soutenance section 24 bis |
| Production Linux, Nginx, Docker et sécurité HTTP | sections 25 et 26 | notice technique sections 27 et 30, notice soutenance sections 35 et 36 |
| Gestion de projet, agile léger et DevOps | section 0 | notice technique section 0, notice soutenance section 0 |

## 0. Gestion de projet et méthodologie

Le projet a été organisé autour de trois périmètres clairement séparés :

- partie web/backend : application, API, base de données, supervision, sécurité ;
- partie Raspberry/kiosque : interface tactile, RFID, validation locale, commandes MQTT ;
- partie ESP32 : capteurs, serrure, télémétrie, alertes locales et actionneurs.

La méthode suivie est une méthode agile légère. L'équipe n'a pas mis en place un Scrum complet, mais a travaillé par itérations courtes :

```text
cadrer le besoin
  -> découper une fonctionnalité
  -> implémenter
  -> tester
  -> intégrer avec les autres parties
  -> ajuster selon les retours terrain
```

Les outils utilisés ont été :

- Teams pour les points de coordination, les décisions plus formelles et le suivi global ;
- Discord pour les échanges rapides, les captures d'erreurs, les tests réseau et les manipulations matérielles en direct ;
- GitHub pour le dépôt central, l'historique de commits, les branches, les pull requests, les merges et l'intégration continue ;
- les notices et la documentation Sphinx pour stabiliser les contrats entre les parties.

Le point clé de coordination a été la formalisation de contrats d'interface :

```text
Frontend / PWA
  -> API REST Django

Raspberry / kiosque
  -> API terminal Django
  -> MQTT cmd/ack/status

ESP32
  -> MQTT telemetry/status/ack/alert

Backend / supervision
  -> PostgreSQL/TimescaleDB
  -> Grafana
```

Cette approche a permis à chaque candidat d'avancer sur son périmètre sans obliger les autres à connaître tous les détails internes. Par exemple, le Raspberry n'a pas besoin de connaître les tables SQL, et l'ESP32 n'a pas besoin de connaître Django : ils respectent les endpoints et les topics MQTT documentés.

Le projet s'inspire également d'une démarche DevOps, avec prudence dans la formulation. Il ne s'agit pas d'une chaîne DevOps industrielle complète, mais plusieurs pratiques DevOps sont en place :

- versionnement GitHub ;
- branches, commits, pull requests et merge vers `main` ;
- CI GitHub Actions ;
- tests automatisés backend, frontend et Raspberry ;
- Ruff pour la qualité Python ;
- CodeQL pour l'analyse statique ;
- SBOM/Grype pour l'inventaire et l'analyse des composants ;
- Docker Compose pour rendre l'environnement reproductible ;
- documentation de déploiement Debian ;
- scripts de sauvegarde/restauration ;
- supervision applicative avec Grafana et alertes.

Pour une démarche DevOps totalement industrialisée, il resterait à ajouter :

- un déploiement continu réel vers un serveur de production ;
- un environnement de staging distinct ;
- une gestion de secrets plus avancée ;
- un rollback automatisé ;
- des tests E2E automatisés sur matériel réel ;
- une supervision système complète du serveur Linux.

## 1. Vue d'ensemble

Le projet est construit autour de trois parties principales :

- une application web de réservation, d'administration et de supervision ;
- un kiosque Raspberry Pi utilisé sur la borne physique ;
- un ESP32 par emplacement pour exécuter les commandes locales et remonter la télémétrie.

Le flux nominal est le suivant :

```text
Utilisateur
  -> Frontend/PWA
  -> API Django
  -> PostgreSQL/TimescaleDB

Raspberry Pi
  -> API Django pour valider les accès
  -> MQTT pour commander les ESP32
  -> cache SQLite local en mode dégradé

ESP32
  -> MQTT telemetry/status/ack/alert
  -> mqtt-bridge backend
  -> Celery/Redis
  -> PostgreSQL/TimescaleDB
  -> Grafana et supervision temps réel
```

Références principales :

- Backend Django : [`backend/api/`](backend/api/)
- Modèles métier : [`backend/api/models.py`](backend/api/models.py)
- Routes API : [`backend/api/api_urls.py`](backend/api/api_urls.py)
- Frontend/PWA : [`frontend/`](frontend/)
- Kiosque Raspberry : [`raspberry/app/`](raspberry/app/)
- Firmware ESP32 : [`esp32/emplacement1/main.py`](esp32/emplacement1/main.py)
- Dashboards Grafana : [`grafana/dashboards/`](grafana/dashboards/)
- Stack Docker locale : [`docker-compose.yml`](docker-compose.yml)
- Stack Docker production : [`docker-compose.prod.yml`](docker-compose.prod.yml)

## 2. Modèle métier

Le modèle physique retenu est :

```text
Station
  -> Borne
    -> Emplacement
      -> Device ESP32
```

La station représente le site. La borne représente l'armoire ou le kiosque physique. L'emplacement représente la place de recharge réellement réservée. Le device représente l'ESP32 installé sur cet emplacement.

Références :

- `Station`, `Borne`, `Emplacement`, `Device` : [`backend/api/models.py`](backend/api/models.py)
- Migration Station > Borne > Emplacement : [`backend/api/migrations/0016_borne_emplacement_borne.py`](backend/api/migrations/0016_borne_emplacement_borne.py)
- MCD/MLD : [`docs/source/database_mcd.rst`](docs/source/database_mcd.rst)
- DBML : [`docs/source/_static/dbdiagram/station_recharge.dbml`](docs/source/_static/dbdiagram/station_recharge.dbml)

Les objets essentiels sont :

```text
Utilisateur
  -> ProfilUtilisateur
  -> Consentement
  -> Authentification
  -> Reservation
  -> Session

Station
  -> Borne
  -> Emplacement
  -> Device

Device
  -> Capteur
  -> CapteurData
  -> DeviceCommandLog

Session
  -> SessionTelemetry
  -> Alerte

Technicien
  -> TechnicienStation
  -> Maintenance
```

La réservation est l'objet métier qui autorise l'accès à un créneau. La session est l'objet opérationnel ouvert à la borne après validation de l'accès ; elle permet de suivre l'ouverture, l'attente de branchement, la charge réelle, l'arrêt et les mesures associées. La charge électrique ne démarre qu'à l'état `charging`, après détection du câble/courant et commande `START`.

## 3. Frontend utilisateur et PWA

Le frontend est une application Vite multipage. Les pages HTML sont dans [`frontend/`](frontend/) et la logique JavaScript est dans [`frontend/js/`](frontend/js/).

Pages principales :

- accueil : [`frontend/index.html`](frontend/index.html), [`frontend/js/home.js`](frontend/js/home.js)
- inscription : [`frontend/register.html`](frontend/register.html), [`frontend/js/register.js`](frontend/js/register.js)
- connexion : [`frontend/login.html`](frontend/login.html), [`frontend/js/login.js`](frontend/js/login.js)
- tableau utilisateur : [`frontend/dashboard.html`](frontend/dashboard.html), [`frontend/js/dashboard.js`](frontend/js/dashboard.js)
- réservation : [`frontend/reservation.html`](frontend/reservation.html), [`frontend/js/reservation.js`](frontend/js/reservation.js)
- profil et moyens d'accès : [`frontend/profile.html`](frontend/profile.html), [`frontend/js/profile.js`](frontend/js/profile.js)
- session mobile de borne : [`frontend/mobile-session.html`](frontend/mobile-session.html), [`frontend/js/mobile-session.js`](frontend/js/mobile-session.js)
- administration : [`frontend/admin-dashboard.html`](frontend/admin-dashboard.html), [`frontend/js/admin-dashboard.js`](frontend/js/admin-dashboard.js)
- technicien : [`frontend/technician-dashboard.html`](frontend/technician-dashboard.html), [`frontend/js/technician-dashboard.js`](frontend/js/technician-dashboard.js)

Le client API commun est dans [`frontend/js/api.js`](frontend/js/api.js). Il centralise :

- la base d'URL API ;
- les appels `fetch` ;
- la gestion des tokens JWT ;
- le rafraîchissement du token via cookie HttpOnly ;
- les appels de réservation, profil, admin, technicien et session mobile.

Le service worker et le manifeste PWA sont dans :

- [`frontend/public/sw.js`](frontend/public/sw.js)
- [`frontend/public/manifest.webmanifest`](frontend/public/manifest.webmanifest)

La logique PWA permet d'utiliser la web app comme application mobile sans développer d'application native.

L'expérience mobile n'est pas seulement une page desktop réduite. Les pages
connectées utilisent une navigation basse sur smartphone pour accéder rapidement
à l'accueil utilisateur, à la réservation et au profil. Le tableau de bord met
en avant une carte "Prochaine action" : session active, réservation en cours ou
réservation à venir. L'utilisateur n'a donc pas besoin de parcourir toutes les
statistiques pour retrouver son prochain accès.

Sur un navigateur compatible, `frontend/js/pwa.js` affiche un bouton
"Installer l'application" lorsque l'événement `beforeinstallprompt` est fourni.
Le service worker reste désactivé en développement local Vite, mais il peut
s'enregistrer sur le serveur HTTPS, y compris si l'application est ouverte par
l'adresse IP locale du serveur. Cela permet une démonstration PWA réaliste avec
un certificat de confiance installé sur le téléphone.

La session mobile de borne est une page dédiée. Après scan du QR affiché par le
kiosque, elle affiche la borne scannée, les réservations compatibles et un
bouton d'action orienté terrain : déverrouiller l'emplacement. Après validation,
l'écran rappelle que la charge démarre automatiquement côté borne quand le câble
est détecté. Dans le prototype actuel, tant que le capteur câble n'est pas câblé,
cette preuve est remplacée par la détection d'un courant minimum sur le SEN0214.

## 4. Authentification web

L'utilisateur crée un compte avec pseudo, email, téléphone optionnel et consentements obligatoires.

Flux :

```text
register.html
  -> POST /api/register/
  -> RegisterSerializer
  -> Utilisateur + ProfilUtilisateur + Consentement
```

Références :

- Endpoint : `POST /api/register/` dans [`backend/api/api_urls.py`](backend/api/api_urls.py)
- Vue : `register()` dans [`backend/api/views.py`](backend/api/views.py)
- Validation : `RegisterSerializer` dans [`backend/api/serializers.py`](backend/api/serializers.py)
- Modèles : `Utilisateur`, `ProfilUtilisateur`, `Consentement` dans [`backend/api/models.py`](backend/api/models.py)

La connexion utilise SimpleJWT :

```text
login.html
  -> POST /api/login/
  -> access token en mémoire côté frontend
  -> refresh token en cookie HttpOnly
```

Références :

- Vue `login()` : [`backend/api/views.py`](backend/api/views.py)
- Rafraîchissement `refresh_token()` : [`backend/api/views.py`](backend/api/views.py)
- Client JS : [`frontend/js/api.js`](frontend/js/api.js)

Le choix du refresh token en cookie HttpOnly limite l'exposition du token long en JavaScript.

## 5. Réservation

Le parcours de réservation est :

```text
Utilisateur connecté
  -> choisit une station
  -> choisit un créneau
  -> choisit un moyen d'accès
  -> le backend attribue un emplacement disponible
  -> la réservation est créée
```

Références :

- Page : [`frontend/reservation.html`](frontend/reservation.html)
- JS : [`frontend/js/reservation.js`](frontend/js/reservation.js)
- Endpoint : `GET/POST /api/reservations/` dans [`backend/api/api_urls.py`](backend/api/api_urls.py)
- Vue : `reservations()` dans [`backend/api/views.py`](backend/api/views.py)
- Validation : `ReservationCreateSerializer` dans [`backend/api/serializers.py`](backend/api/serializers.py)
- Règles de durée : [`backend/api/reservation_rules.py`](backend/api/reservation_rules.py)

Les durées autorisées sont centralisées dans `reservation_rules.py`. Le frontend propose notamment 30 min, 1 h, 2 h et 4 h.

Le backend vérifie :

- que la station existe ;
- que le créneau est valide ;
- que la durée est autorisée ;
- qu'un emplacement est disponible ;
- que la réservation n'entre pas en conflit avec une autre réservation ;
- que le moyen d'accès choisi est cohérent.

La réservation stocke :

- un utilisateur ;
- un emplacement ;
- un début et une fin ;
- un statut ;
- un moyen d'accès ;
- une authentification temporaire ou persistante ;
- un code de référence lisible.

Modèle : `Reservation` dans [`backend/api/models.py`](backend/api/models.py).

Dans les tableaux utilisateur et administrateur, les réservations sont séparées pour éviter les ambiguïtés :

- réservations en cours : le créneau a commencé et n'est pas terminé ;
- réservations à venir : le créneau n'a pas encore commencé ;
- réservations archivées : le créneau est terminé ou la réservation a été annulée.

Une charge arrêtée avant la fin du créneau ne transforme pas automatiquement la réservation en archive : l'emplacement reste réservé jusqu'à la fin de la fenêtre payée, sauf annulation ou règle métier explicite.

## 6. Moyens d'accès

Le projet distingue trois moyens d'accès :

```text
RFID
QR de réservation
Code SMS temporaire
```

Ces moyens ne sont pas équivalents :

- RFID : moyen persistant associé au compte utilisateur ;
- QR de réservation : secret temporaire généré à la réservation ;
- SMS : code temporaire généré côté backend, envoyé au bon moment ou sur demande.

Références :

- Modèle `Authentification` : [`backend/api/models.py`](backend/api/models.py)
- Service de hash : [`backend/api/services/auth_methods.py`](backend/api/services/auth_methods.py)
- Endpoints utilisateur : `me/auth-methods/` dans [`backend/api/api_urls.py`](backend/api/api_urls.py)
- Politique SMS : [`backend/api/services/sms_access_policy.py`](backend/api/services/sms_access_policy.py)
- Service SMS : [`backend/api/services/sms.py`](backend/api/services/sms.py)

Les secrets ne sont pas stockés en clair. Le backend stocke un hash SHA-256 via `hash_secret()`.

### 6.1 RFID

Le badge RFID contient seulement un UID lu par le lecteur ACR122U. Cet UID est associé au compte utilisateur via un code court généré depuis le profil.

Flux d'association :

```text
Utilisateur connecté
  -> demande un code d'association RFID
  -> va à la borne
  -> saisit le code
  -> présente son badge
  -> Raspberry lit l'UID
  -> POST /api/terminal/link-rfid/
  -> backend associe l'UID au compte
```

Références :

- Création du code : `create_rfid_link_code()` dans [`backend/api/views.py`](backend/api/views.py)
- Association terminal : `terminal_link_rfid()` dans [`backend/api/views.py`](backend/api/views.py)
- Lecteur RFID Raspberry : [`raspberry/app/rfid_reader.py`](raspberry/app/rfid_reader.py)

Le lecteur ACR122U est supporté via PC/SC dans `_pcsc_loop()`.

### 6.2 QR de réservation

Le QR de réservation est généré dès la réservation. Il contient un payload sécurisé avec la référence de réservation et un token.

Format logique :

```json
{
  "v": 1,
  "type": "reservation_access",
  "reservation": "CODE",
  "token": "secret-temporaire"
}
```

Références :

- Construction du payload : `_build_qr_payload()` dans [`backend/api/views.py`](backend/api/views.py)
- Rendu SVG : `_build_qr_svg()` dans [`backend/api/views.py`](backend/api/views.py)
- Consultation utilisateur : `reservation_access_payload()` dans [`backend/api/views.py`](backend/api/views.py)
- Envoi email : [`backend/api/services/email_notifications.py`](backend/api/services/email_notifications.py)

Le QR envoyé par email et affiché dans la PWA est le QR de réservation. Il sert à identifier une réservation précise.

### 6.3 QR de session mobile

Le QR affiché par le kiosque n'est pas le QR de réservation. C'est un QR de session mobile temporaire.

Il sert à associer le téléphone de l'utilisateur à la borne physique.

Flux :

```text
Kiosque
  -> bouton Téléphone
  -> POST /api/terminal/mobile-sessions/
  -> backend crée un token temporaire
  -> kiosque affiche un QR avec /mobile-session.html?token=...

Téléphone
  -> scanne le QR
  -> ouvre la PWA
  -> utilisateur se connecte
  -> liste ses réservations compatibles
  -> choisit une réservation
  -> POST /api/mobile-sessions/<token>/authorize/
  -> affiche "Autorisation confirmée"
  -> suit GET /api/mobile-sessions/<token>/
  -> affiche "Borne autorisée" quand le kiosque a consommé l'autorisation

Kiosque
  -> interroge le statut
  -> consomme l'autorisation
  -> ouvre la session de charge
```

Le statut de la session mobile évolue ainsi : `pending` quand le QR de borne est
créé, `authorized` quand l'utilisateur a choisi une réservation sur son
téléphone, puis `consumed` quand le kiosque a consommé l'autorisation et démarré
le parcours de charge. Si la page mobile est rafraîchie après l'autorisation,
`mobile_session_detail()` renvoie la réservation sélectionnée afin que la PWA
retrouve le contexte affiché.

Références :

- Création session mobile : `terminal_create_mobile_session()` dans [`backend/api/views.py`](backend/api/views.py)
- Lecture côté mobile : `mobile_session_detail()` dans [`backend/api/views.py`](backend/api/views.py)
- Autorisation mobile : `mobile_session_authorize()` dans [`backend/api/views.py`](backend/api/views.py)
- Consommation côté kiosque : `terminal_consume_mobile_session()` dans [`backend/api/views.py`](backend/api/views.py)
- Page mobile : [`frontend/mobile-session.html`](frontend/mobile-session.html)
- JS mobile : [`frontend/js/mobile-session.js`](frontend/js/mobile-session.js)
- JS kiosque : [`raspberry/app/app.js`](raspberry/app/app.js)

Cette distinction est importante :

- QR de réservation : généré à la réservation, lié à une réservation.
- QR de session mobile : généré par la borne, lié à une borne temporaire, puis l'utilisateur choisit la réservation sur son téléphone.

### 6.4 Code SMS temporaire

Le code SMS est généré techniquement côté backend, mais il est envoyé à l'utilisateur seulement sur demande ou peu avant le créneau.

Politique de sécurité :

- alphabet compatible clavier matriciel : `0123456789ABCD` ;
- longueur par défaut : 8 caractères ;
- espace de recherche : `14^8` combinaisons ;
- nombre maximal d'essais : 5 ;
- renvoi limité par rate limiting ;
- téléphone requis ;
- vérification du téléphone configurable.

Références :

- Politique : [`backend/api/services/sms_access_policy.py`](backend/api/services/sms_access_policy.py)
- Service SMS : [`backend/api/services/sms.py`](backend/api/services/sms.py)
- Endpoint : `POST /api/reservations/<id>/send-access-code/`
- Vue : `send_reservation_access_code()` dans [`backend/api/views.py`](backend/api/views.py)
- Tests : [`backend/api/tests/test_sms_access_policy.py`](backend/api/tests/test_sms_access_policy.py)
- Tests réservation SMS : [`backend/api/tests/test_reservations.py`](backend/api/tests/test_reservations.py)

En développement, l'envoi peut être loggé en console. Pour un prestataire réel, le service est conçu pour être remplacé par un backend SMS configurable.

## 7. Kiosque Raspberry

Le Raspberry Pi héberge l'interface tactile locale et le proxy vers le backend.

Références :

- Serveur local : [`raspberry/app/main.py`](raspberry/app/main.py)
- Interface HTML : [`raspberry/app/index.html`](raspberry/app/index.html)
- Logique UI : [`raspberry/app/app.js`](raspberry/app/app.js)
- Styles : [`raspberry/app/style.css`](raspberry/app/style.css)
- RFID : [`raspberry/app/rfid_reader.py`](raspberry/app/rfid_reader.py)
- MQTT : [`raspberry/app/mqtt_client.py`](raspberry/app/mqtt_client.py)
- Cache offline : [`raspberry/app/offline_store.py`](raspberry/app/offline_store.py)
- État local de charge : [`raspberry/app/charge_state.py`](raspberry/app/charge_state.py)

Le serveur Raspberry écoute sur le port `9000`.

L'interface tactile est organisée pour une borne 1024x600 :

- accueil centré sur le badge RFID, qui reste le geste principal ;
- accès secondaires en bas d'écran : téléphone, code SMS, QR réservation,
  association badge ;
- écran `Recharger à l'emplacement X` uniquement après validation de l'accès ;
- écran `Chargement en cours` pendant la session, avec un seul bouton d'arrêt ;
- retour automatique à l'accueil après inactivité sur les écrans d'accès ;
- aucun bouton de démarrage visible tant que l'utilisateur n'est pas authentifié.

Routes locales importantes :

```text
GET  /rfid/status
GET  /rfid/scan
POST /rfid/scan
POST /mqtt/command
GET  /offline/status
POST /offline/sync
POST /offline/authenticate
GET  /charge/state
POST /charge/state/reset
```

Les appels API backend passent par un proxy local sous `/backend-api/...`. Le Raspberry ajoute le secret `X-Terminal-Secret` avant d'appeler le backend.

Références :

- Fonction `proxy_backend_json()` : [`raspberry/app/main.py`](raspberry/app/main.py)
- Protection backend terminal : `_terminal_secret_response()` dans [`backend/api/views.py`](backend/api/views.py)

## 8. Validation d'accès à la borne

Le kiosque ne décide pas seul en mode nominal. Il transmet les informations au backend, qui vérifie :

- le moyen d'accès ;
- la réservation ;
- la station ;
- la borne ;
- l'emplacement ;
- le créneau ;
- l'état de la réservation ;
- l'état de la session.

Endpoint principal :

```text
POST /api/terminal/authenticate/
```

Référence : `terminal_authenticate()` dans [`backend/api/views.py`](backend/api/views.py).

Flux RFID direct :

```text
Badge lu
  -> UID
  -> POST /api/terminal/authenticate/
  -> auth_mode = rfid
  -> backend retrouve le badge
  -> backend retrouve la réservation active compatible
  -> backend crée ou retrouve la session
  -> session = access_validated
  -> kiosque publie UNLOCK
  -> ESP32 ouvre la serrure par impulsion
  -> session = waiting_plug après ACK UNLOCK
```

Point important : le badge RFID ne démarre pas la charge électrique. Il valide
l'accès et déverrouille automatiquement le boîtier. Le démarrage électrique
est ensuite déclenché automatiquement quand l'ESP32 remonte `cable=true`.

Flux QR de réservation :

```text
QR scanné
  -> reservation_code + token
  -> POST /api/terminal/authenticate/
  -> auth_mode = qr
  -> backend vérifie le hash du token
  -> backend ouvre la session
```

Flux code SMS :

```text
Code de réservation + code SMS
  -> POST /api/terminal/authenticate/
  -> auth_mode = code
  -> backend vérifie le hash du code
  -> backend vérifie le nombre d'essais
  -> backend ouvre la session
```

Une fois l'accès validé, le backend place la session dans l'état `access_validated`.

Référence :

- Machine d'état backend : [`backend/api/services/charge_session_state.py`](backend/api/services/charge_session_state.py)
- Modèle `Session` : [`backend/api/models.py`](backend/api/models.py)

## 9. Machine d'état de charge

La session suit une machine d'état explicite :

```text
reserved
  -> access_validated
  -> waiting_plug
  -> charging
  -> stopping
  -> stopped

error peut être atteint depuis les états ouverts.
```

Références :

- Enum `ChargeSessionState` : [`backend/api/models.py`](backend/api/models.py)
- Transitions : [`backend/api/services/charge_session_state.py`](backend/api/services/charge_session_state.py)
- Tests de non-régression : [`backend/api/tests/test_terminal_auth.py`](backend/api/tests/test_terminal_auth.py)

Ce mécanisme évite :

- un double START sur une session déjà en charge ;
- un STOP incohérent ;
- une session terminée réouverte ;
- une session en erreur relancée sans contrôle ;
- une charge active sans état backend cohérent.

## 10. Commande Raspberry vers ESP32

Après validation par le backend, le Raspberry publie une commande MQTT vers l'ESP32 concerné.

Flux :

```text
Backend valide l'accès
  -> Raspberry reçoit session + slot_id + mqtt_prefix
  -> Raspberry publie UNLOCK sur MQTT
  -> ESP32 ouvre le boîtier par impulsion
  -> utilisateur branche le câble ou active le générateur du prototype
  -> ESP32 publie cable=true ou une mesure current récente
  -> Raspberry publie START automatiquement
  -> ESP32 répond par ACK
  -> Raspberry affiche l'écran de charge
```

Topic de commande :

```text
station/<mqtt_prefix>/<slot_id>/cmd
```

Payload UNLOCK :

```json
{
  "command_id": "uuid",
  "action": "UNLOCK",
  "issued_at": "2026-05-25T10:00:00Z",
  "session_id": "uuid-session",
  "station": "Station Demo",
  "borne": "Borne 1",
  "emplacement": 1,
  "source": "raspberry"
}
```

Payload START :

```json
{
  "command_id": "uuid",
  "action": "START",
  "issued_at": "2026-05-25T10:00:00Z",
  "session_id": "uuid-session",
  "station": "Station Demo",
  "borne": "Borne 1",
  "emplacement": 1,
  "source": "raspberry"
}
```

Références :

- Publication Raspberry : [`raspberry/app/mqtt_client.py`](raspberry/app/mqtt_client.py)
- Contrat MQTT : [`raspberry/app/mqtt_contract.py`](raspberry/app/mqtt_contract.py)
- Endpoint local `/mqtt/command` : [`raspberry/app/main.py`](raspberry/app/main.py)
- Firmware ESP32 : [`esp32/emplacement1/main.py`](esp32/emplacement1/main.py)
- Tests du contrat : [`raspberry/tests/test_mqtt_contract.py`](raspberry/tests/test_mqtt_contract.py)

Le Raspberry peut exiger un ACK avec `MQTT_ACK_REQUIRED=True`. Dans ce cas, l'interface ne considère pas la commande comme confirmée tant que l'ESP32 n'a pas répondu.

## 11. Firmware ESP32

Le firmware ESP32 actuel couvre le prototype matériel disponible :

- DHT22 sur GPIO15 ;
- capteur de courant SEN0214 sur GPIO34 ;
- tension fixe de prototype à 12 V ;
- calcul de puissance ;
- intégration de l'énergie en kWh ;
- remontée IP, MAC et version firmware ;
- serrure électromagnétique par relais actif-bas sur GPIO26 ;
- commandes START/STOP/LOCK/UNLOCK ;
- ACK MQTT ;
- status et telemetry ;
- capteurs porte, câble et relais de charge désactivés tant qu'ils ne sont pas câblés.

La serrure est ouverte lors d'un `UNLOCK` après authentification. Le firmware
ouvre alors une fenêtre d'accès de 15 secondes (`LOCK_AUTO_RELOCK_SECONDS`) :
si aucune charge ne démarre pendant ce délai, l'ESP32 reverrouille
automatiquement l'emplacement. `START` reste séparé de l'ouverture et démarre
uniquement la charge électrique après branchement ou détection du courant.
Dans le prototype sans capteur câble, le kiosk considère une mesure SEN0214
récente `current >= 0.1 A` comme preuve temporaire de branchement. Si un vrai
capteur câble remonte explicitement `cable=false`, ce signal physique reste
prioritaire.
`STOP` coupe la charge et peut rouvrir le boîtier pour permettre le retrait du
câble.

Référence : [`esp32/emplacement1/main.py`](esp32/emplacement1/main.py)

Topics utilisés :

```text
station/<mqtt_prefix>/<slot_id>/cmd
station/<mqtt_prefix>/<slot_id>/ack
station/<mqtt_prefix>/<slot_id>/status
station/<mqtt_prefix>/<slot_id>/telemetry
station/<mqtt_prefix>/<slot_id>/alert
```

Le firmware publie :

```json
{
  "session_id": "...",
  "state": "charging",
  "current": 1.2,
  "voltage": 12.0,
  "power": 14.4,
  "energy_kwh": 0.0012,
  "temperature": 28.4,
  "humidity": 46.0,
  "heat_index": 43.5,
  "door": null,
  "cable": null,
  "firmware_version": "1.1.0-sensors",
  "hardware_mac": "...",
  "ip_address": "..."
}
```

L'énergie augmente uniquement lorsque :

- l'état est `charging` ;
- une puissance est calculable ;
- du temps s'écoule entre deux mesures.

Référence du calcul : fonction `update_energy()` dans [`esp32/emplacement1/main.py`](esp32/emplacement1/main.py).

La MAC et l'adresse IP sont lues réellement par l'ESP32 via le Wi-Fi. La version
firmware est une donnée embarquée : le firmware lit `version.txt` sur LittleFS
si le fichier existe, sinon il publie la constante `FIRMWARE_VERSION`.

## 12. MQTT côté backend

Le backend ne lit pas directement les GPIO ni les capteurs. Il reçoit les données ESP32 via MQTT.

Flux :

```text
ESP32
  -> Mosquitto
  -> mqtt-bridge
  -> Celery/Redis
  -> service telemetry
  -> base de données
  -> Grafana et WebSocket
```

Références :

- Client bridge MQTT : [`backend/api/mqtt.py`](backend/api/mqtt.py)
- Commande de lancement : [`backend/api/management/commands/run_mqtt_bridge.py`](backend/api/management/commands/run_mqtt_bridge.py)
- Tâches d'ingestion : [`backend/api/tasks.py`](backend/api/tasks.py)
- Service d'ingestion : [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)
- Healthcheck du bridge : [`backend/api/management/commands/check_mqtt_bridge_health.py`](backend/api/management/commands/check_mqtt_bridge_health.py)

Le bridge s'abonne au préfixe :

```text
station/#
```

Il accepte quatre types de messages :

```text
ack
status
telemetry
alert
```

Le traitement est orienté topic :

```text
.../ack       -> ingest_slot_ack()
.../status    -> ingest_slot_status()
.../telemetry -> ingest_slot_telemetry()
.../alert     -> ingest_slot_telemetry() avec état error
```

Le topic permet de retrouver :

- le préfixe station/borne ;
- le slot ;
- le type de message.

La télémétrie est ensuite rattachée au bon `Device`, au bon `Emplacement` et, si possible, à la session active.

## 13. Redis et Celery

Redis est utilisé comme :

- broker Celery ;
- cache applicatif ;
- couche de diffusion Django Channels ;
- stockage court pour les sessions mobiles temporaires et certains codes.

Configuration :

- [`backend/config/settings.py`](backend/config/settings.py)
- [`backend/config/celery.py`](backend/config/celery.py)

Celery exécute :

- `api.process_mqtt_message` pour traiter les messages MQTT ;
- `api.scan_session_telemetry_gaps` pour détecter les sessions sans télémétrie ;
- `api.notify_pending_alerts` pour envoyer les notifications d'alertes ;
- `api.prune_old_telemetry` pour appliquer la rétention des mesures brutes ;
- `api.apply_privacy_retention` pour appliquer la rétention RGPD complète.

Références :

- Tâches : [`backend/api/tasks.py`](backend/api/tasks.py)
- Alertes opérationnelles : [`backend/api/services/operational_alerts.py`](backend/api/services/operational_alerts.py)
- Rétention : [`backend/api/services/retention.py`](backend/api/services/retention.py)
- Notifications : [`backend/api/services/email_notifications.py`](backend/api/services/email_notifications.py)

Ce découpage évite de bloquer le bridge MQTT lorsque beaucoup de mesures arrivent.

## 14. Base de données et TimescaleDB

La base utilisée en local est TimescaleDB, compatible PostgreSQL.

Références :

- Service Docker : [`docker-compose.yml`](docker-compose.yml)
- Service production : [`docker-compose.prod.yml`](docker-compose.prod.yml)
- Configuration PostgreSQL production : [`postgresql/prod/postgresql.conf`](postgresql/prod/postgresql.conf)
- Migrations : [`backend/api/migrations/`](backend/api/migrations/)

Les mesures sont stockées dans :

- `capteur_data` pour les données brutes par capteur ;
- `session_telemetry` pour les mesures électriques rattachées à une session.

Références :

- `Capteur`, `CapteurData` : [`backend/api/models.py`](backend/api/models.py)
- `SessionTelemetry` : [`backend/api/models.py`](backend/api/models.py)
- Activation TimescaleDB : [`backend/api/migrations/0015_enable_timescaledb_extension.py`](backend/api/migrations/0015_enable_timescaledb_extension.py)
- Policies conditionnelles : [`backend/api/migrations/0026_pg_stat_statements_and_timescale_policies.py`](backend/api/migrations/0026_pg_stat_statements_and_timescale_policies.py)
- Hypertables miroir et vues anonymisées : [`backend/api/migrations/0033_timescale_timeseries_and_anonymized_views.py`](backend/api/migrations/0033_timescale_timeseries_and_anonymized_views.py)

TimescaleDB apporte surtout un intérêt pour les séries temporelles : télémétrie, capteurs et historique de session. En production, le projet utilise deux hypertables miroir, `capteur_data_timeseries` et `session_telemetry_timeseries`. Les tables Django restent les sources d’écriture, puis des triggers recopient les mesures dans les hypertables. Ce choix évite de casser l’ORM avec les contraintes TimescaleDB tout en permettant compression, rétention et requêtes Grafana efficaces.

Les politiques TimescaleDB appliquées en production sont :

- compression après 7 jours ;
- rétention des mesures capteurs après 90 jours ;
- rétention de la télémétrie de session après 365 jours.

L’anonymisation SQL est également active via des vues dédiées : `utilisateur_anonyme`, `technicien_anonyme`, `journal_securite_anonyme` et `supervision_session_anonyme`. PostgreSQL Anonymizer (`anon`) reste optionnel : la migration `0027_optional_postgresql_anonymizer.py` l’active seulement si l’image PostgreSQL fournit l’extension.

## 15. Grafana

Grafana ne lit pas MQTT directement.

Grafana lit les tables PostgreSQL/TimescaleDB avec des requêtes SQL.

Flux :

```text
ESP32
  -> MQTT
  -> backend
  -> PostgreSQL/TimescaleDB
  -> Grafana
```

Références :

- Datasource : [`grafana/provisioning/datasources/datasource.yml`](grafana/provisioning/datasources/datasource.yml)
- Provisioning dashboards : [`grafana/provisioning/dashboards/dashboards.yml`](grafana/provisioning/dashboards/dashboards.yml)
- Dashboard global : [`grafana/dashboards/station-overview.json`](grafana/dashboards/station-overview.json)
- Dashboard technique : [`grafana/dashboards/station-supervision.json`](grafana/dashboards/station-supervision.json)
- Dashboard détail session : [`grafana/dashboards/session-detail.json`](grafana/dashboards/session-detail.json)
- Alerting Grafana : [`grafana/provisioning/alerting/station-alerts.yml`](grafana/provisioning/alerting/station-alerts.yml)

La supervision Grafana est volontairement découpée en trois niveaux :

1. `station-overview.json` donne la vue d'accueil : état global, sessions en cours, alertes ouvertes et navigation vers les vues plus techniques.
2. `station-supervision.json` donne la vue technique par station, borne et emplacement : séries capteurs, statut ESP32, télémétrie récente et historique opérationnel.
3. `session-detail.json` donne la vue d'une session de charge précise : contexte utilisateur/réservation, emplacement concerné, courant, tension, puissance, énergie, commandes UNLOCK/START/STOP, ACK et alertes rattachées.

Le point important est que la vue de session ne se contente pas de filtrer un emplacement. Elle part d'un `session_id` et lit `session_telemetry` pour éviter de mélanger plusieurs charges passées sur le même emplacement. Les mesures environnementales issues de `capteur_data` sont ensuite affichées seulement sur la fenêtre temporelle de cette session.

Les dashboards exploitent notamment :

- `device` pour l'état ESP32 ;
- `capteur_data` pour les mesures brutes ;
- `session_telemetry` pour les mesures liées à une session ;
- `charging_session` pour l'état de charge ;
- `alerte` pour les incidents ;
- `device_command_log` pour les UNLOCK/START/STOP et ACK ;
- `station`, `borne`, `emplacement` pour le contexte physique.

Après un badge RFID accepté, l'administration doit donc pouvoir observer :

- une session en `access_validated`, puis `waiting_plug` quand l'ESP32 confirme
  `UNLOCK` ;
- une ligne `DeviceCommandLog` avec `action=UNLOCK` et `status=unlocked` ;
- le dernier ordre du device ESP32 dans `device.last_command_action` et
  `device.last_command_status` ;
- les messages `status` et `telemetry` suivants si l'ESP32 publie après
  l'ouverture du boîtier.

## 16. Supervision applicative temps réel

En plus de Grafana, le projet expose une supervision temps réel côté frontend/admin via WebSocket.

Flux :

```text
Ingestion MQTT
  -> broadcast_supervision_update()
  -> Django Channels
  -> Redis channel layer
  -> WebSocket admin ou technicien
```

Références :

- ASGI : [`backend/config/asgi.py`](backend/config/asgi.py)
- Routing WebSocket : [`backend/api/routing.py`](backend/api/routing.py)
- Consumers : [`backend/api/consumers.py`](backend/api/consumers.py)
- Broadcast : [`backend/api/realtime.py`](backend/api/realtime.py)
- Payload supervision : [`backend/api/services/supervision.py`](backend/api/services/supervision.py)

Endpoints WebSocket :

```text
/ws/admin/supervision/
/ws/technician/supervision/
```

Le technicien ne voit que les stations de son périmètre grâce au modèle `TechnicienStation`.

## 17. Alertes

Les alertes sont créées à partir :

- de la télémétrie ESP32 ;
- de l'état d'une session ;
- du firmware ;
- de l'absence de télémétrie récente ;
- d'événements locaux.

Types d'alertes possibles :

- surchauffe ;
- surintensité ;
- câble retiré ;
- boîtier ouvert ;
- serrure déverrouillée ;
- charge sans session ;
- énergie sans session ;
- énergie de session trop élevée ;
- firmware non conforme ;
- session active sans télémétrie ;
- accès validé sans câble branché ;
- session bloquée en arrêt.

Références :

- Création/résolution depuis télémétrie : [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)
- Scan périodique session sans télémétrie : [`backend/api/services/operational_alerts.py`](backend/api/services/operational_alerts.py)
- Workflow technicien : [`backend/api/services/alert_workflow.py`](backend/api/services/alert_workflow.py)
- Modèle `Alerte` : [`backend/api/models.py`](backend/api/models.py)
- Tests : [`backend/api/tests/test_operational_alerts.py`](backend/api/tests/test_operational_alerts.py)

Le cycle est :

```text
nouvelle
  -> active
  -> prise_en_charge
  -> resolue
  -> fermee
```

Une anomalie persistante met à jour l'alerte existante au lieu de créer des doublons. Une télémétrie revenue à la normale peut résoudre automatiquement certaines alertes.

Le cas `waiting_plug` est traité séparément. Après validation de l'accès et ACK
`UNLOCK`, le système attend que l'ESP32 remonte `cable=true` ou, pour le
prototype actuel, un courant SEN0214 récent supérieur ou égal à `0.1 A`. Si cet
état dure plus de `SESSION_WAITING_PLUG_STALE_MINUTES` minutes, `5` par défaut, le backend
crée `session_waiting_plug_too_long`. Cette alerte évite de confondre une attente
de branchement avec une vraie perte de télémétrie pendant une charge.

## 18. Techniciens et moindre privilège

Le projet distingue :

- utilisateur standard ;
- technicien ;
- administrateur.

Un technicien peut être rattaché uniquement à certaines stations.

Références :

- Modèles `Technicien`, `TechnicienStation` : [`backend/api/models.py`](backend/api/models.py)
- Serializers : `TechnicianSerializer`, `TechnicianStationAssignmentSerializer` dans [`backend/api/serializers.py`](backend/api/serializers.py)
- Endpoints technicien : [`backend/api/api_urls.py`](backend/api/api_urls.py)
- Vue technicien : `technician_supervision()` dans [`backend/api/views.py`](backend/api/views.py)
- WebSocket technicien : `TechnicianSupervisionConsumer` dans [`backend/api/consumers.py`](backend/api/consumers.py)

Le tableau de bord technicien reprend ce périmètre dans l'interface. Les
contrôleurs ESP32, alertes, mesures et commandes récentes exposent leur
`station_id`, ce qui permet de filtrer la supervision par station sans afficher
un périmètre plus large que celui autorisé.

L'administrateur gère :

- les utilisateurs ;
- les stations ;
- les bornes ;
- les emplacements ;
- les devices ESP32 ;
- les techniciens ;
- les périmètres technicien ;
- les maintenances ;
- les alertes ;
- les accès.

## 19. Mode dégradé Raspberry

Le mode nominal dépend du backend. Le mode dégradé permet une continuité limitée si le backend tombe après synchronisation.

Flux :

```text
Backend disponible
  -> Raspberry synchronise les réservations proches
  -> stockage local SQLite

Backend indisponible
  -> Raspberry valide localement un droit déjà synchronisé
  -> enregistre un événement offline
  -> commande l'ESP32 via MQTT local

Backend rétabli
  -> Raspberry rejoue les événements offline
```

Références :

- Cache SQLite : [`raspberry/app/offline_store.py`](raspberry/app/offline_store.py)
- Synchronisation côté Raspberry : `sync_offline_cache()` et `sync_offline_events()` dans [`raspberry/app/main.py`](raspberry/app/main.py)
- Export backend : `terminal_offline_cache()` dans [`backend/api/views.py`](backend/api/views.py)
- Reconciliation backend : `terminal_offline_events()` dans [`backend/api/views.py`](backend/api/views.py)

Le cache offline ne doit pas créer de nouveaux secrets. Il ne valide que des droits déjà synchronisés, bornés à la station et à la borne locales.

Durée et contenu du cache :

- le cache ne garde pas les dernières réservations créées, mais les réservations
  dont le créneau approche ;
- par défaut, le backend exporte les réservations éligibles jusqu'à
  `TERMINAL_OFFLINE_CACHE_HOURS=24` heures dans le futur ;
- une réservation créée deux jours plus tôt peut donc être dans le cache si son
  créneau est aujourd'hui ou dans les prochaines 24 heures ;
- une réservation déjà terminée ou prévue au-delà de cette fenêtre n'est pas
  conservée localement ;
- les marges d'accès restent les mêmes qu'en ligne : 5 minutes avant le créneau
  et aucune tolérance après la fin par défaut ;
- le buffer technique de 5 minutes après le créneau sert uniquement au calcul de
  disponibilité entre deux réservations, pas à prolonger le droit d'accès.

Le mode dégradé peut donc fonctionner environ 24 heures sans serveur central,
mais uniquement pour les droits déjà synchronisés. Il ne permet pas de créer une
nouvelle réservation ni de générer un nouveau moyen d'accès. Une extension à 48
heures serait possible pour un site isolé, mais elle augmenterait le risque lié
à la conservation locale de droits d'accès.

En production terrain, le broker Mosquitto doit idéalement être sur le Raspberry pour que Raspberry et ESP32 continuent de communiquer même si le backend central est indisponible.

## 20. Placement du broker MQTT

Il y a deux configurations à distinguer.

Développement local :

```text
PC Docker
  -> Mosquitto conteneur mqtt
  -> backend, mqtt-bridge, grafana
  -> Raspberry et ESP32 pointent vers l'IP Wi-Fi du PC
```

Production terrain recommandée :

```text
Raspberry Pi de la borne
  -> Mosquitto local
  -> ESP32 connectés au même Wi-Fi local
  -> Raspberry utilise MQTT_HOST=localhost
  -> backend central peut ingérer depuis ce broker ou recevoir une resynchronisation
```

Références :

- Mosquitto dev : service `mqtt` dans [`docker-compose.yml`](docker-compose.yml)
- Mosquitto prod Docker : service `mqtt` dans [`docker-compose.prod.yml`](docker-compose.prod.yml)
- Configuration Mosquitto : [`mosquitto/config/`](mosquitto/config/)
- Client MQTT Raspberry : [`raspberry/app/mqtt_client.py`](raspberry/app/mqtt_client.py)
- Firmware ESP32 : [`esp32/emplacement1/main.py`](esp32/emplacement1/main.py)

Le principe de sécurité est que l'ESP32 exécute les commandes locales et remonte l'état, mais ne décide pas des droits utilisateur. L'autorité métier reste le backend, ou le cache local pré-synchronisé en mode dégradé.

## 21. Sécurité applicative

Le projet applique plusieurs protections :

- mots de passe validés côté backend ;
- JWT avec refresh token HttpOnly ;
- secrets d'accès hashés ;
- code SMS long et limité en essais ;
- rate limiting sur les endpoints sensibles ;
- secret terminal `X-Terminal-Secret` ;
- validation station/borne/emplacement ;
- rôles admin/technicien/utilisateur ;
- périmètre technicien par station ;
- CORS et host validation ;
- headers Nginx ;
- CSP ;
- migrations avec contraintes et index ;
- journalisation sécurité.

Références :

- Throttles : [`backend/api/throttles.py`](backend/api/throttles.py)
- Middleware host local dev : [`backend/api/middleware.py`](backend/api/middleware.py)
- Checks de déploiement : [`backend/api/checks.py`](backend/api/checks.py)
- Journal sécurité : `JournalSecurite` dans [`backend/api/models.py`](backend/api/models.py)
- Nginx dev : [`nginx/conf.d/station.conf`](nginx/conf.d/station.conf)
- Nginx prod : [`nginx/prod.conf.d/station.conf`](nginx/prod.conf.d/station.conf)
- Tests sécurité Nginx : [`backend/api/tests/test_nginx_security_config.py`](backend/api/tests/test_nginx_security_config.py)
- Tests durcissement production : [`backend/api/tests/test_production_hardening.py`](backend/api/tests/test_production_hardening.py)

Le mode développement accepte automatiquement les IP privées locales lorsque `DEV_AUTO_TRUST_PRIVATE_NETWORK=True`. En production, les hosts doivent être explicitement configurés.

### Exports administrateur et journaux archivés

L'onglet `Exports` du dashboard administrateur permet de filtrer puis de prévisualiser les données avant téléchargement. Deux jeux de données sont disponibles :

- instantané opérationnel : station, borne, emplacement, état serrure, ESP32, firmware, télémétrie récente, sessions, réservations et alertes ;
- journaux de sécurité archivés : date, utilisateur, action, statut et adresse IP.

Les filtres principaux sont la période, la station pour l'instantané opérationnel, le statut du journal (`success` ou `failure`) et une recherche textuelle sur l'utilisateur, l'action ou l'adresse IP. Les exports réels en CSV ou JSON sont journalisés dans `JournalSecurite`, ce qui permet de tracer qui a extrait quelles données et quand. Pour éviter les extractions trop larges, l'API limite la prévisualisation/export à 1000 lignes par requête.

Références :

- Endpoint export : [`backend/api/admin_exports.py`](backend/api/admin_exports.py)
- Interface admin : [`frontend/admin-dashboard.html`](frontend/admin-dashboard.html), [`frontend/js/admin-dashboard.js`](frontend/js/admin-dashboard.js)

## 22. Privacy by design

Le projet limite l'exposition des données personnelles :

- les secrets RFID/QR/SMS sont hashés ;
- le refresh token long est en cookie HttpOnly ;
- les exports de compte existent côté API ;
- les consentements sont historisés ;
- les numéros de téléphone peuvent être masqués ;
- les logs sécurité ne stockent que les informations nécessaires ;
- la suppression de compte anonymise le profil au lieu de supprimer brutalement l'historique technique ;
- une tâche Celery purge les données au-delà des durées de rétention configurées ;
- PostgreSQL Anonymizer est préparé de manière optionnelle.

Références :

- Consentements : `Consentement` dans [`backend/api/models.py`](backend/api/models.py)
- Export compte : `export_account()` dans [`backend/api/views.py`](backend/api/views.py)
- Suppression/anonymisation : `anonymize_user_account()` dans [`backend/api/services/retention.py`](backend/api/services/retention.py)
- Rétention RGPD : `apply_privacy_retention()` dans [`backend/api/services/retention.py`](backend/api/services/retention.py)
- Masquage téléphone : [`backend/api/services/sms.py`](backend/api/services/sms.py)
- Anonymizer optionnel : [`backend/api/migrations/0027_optional_postgresql_anonymizer.py`](backend/api/migrations/0027_optional_postgresql_anonymizer.py)
- Pages CGU/confidentialité : [`backend/api/page_views.py`](backend/api/page_views.py)

L'extension PostgreSQL Anonymizer est activée uniquement si elle est disponible dans l'image PostgreSQL utilisée. Sinon la migration passe sans casser le déploiement.

Durées par défaut :

- mesures brutes capteurs : 90 jours ;
- télémétrie de session : 365 jours ;
- commandes/ACK ESP32 : 365 jours ;
- journaux de sécurité : 365 jours ;
- alertes résolues : 365 jours ;
- secrets inactifs ou expirés : 90 jours ;
- comptes archivés non anonymisés : 1095 jours.

## 23. Firmware et OTA

Chaque ESP32 remonte :

- `firmware_version` ;
- `hardware_mac` ;
- `ip_address` ;
- `slot_id`.

Le backend compare la version remontée avec la version attendue.

La version remontée n'est pas calculée automatiquement par la carte : elle est
embarquée dans le firmware au moment du flash. Le fichier optionnel
`version.txt` permet de changer cette valeur sans modifier toute la logique du
fichier `main.py`.

Références :

- Champs firmware : `Device` dans [`backend/api/models.py`](backend/api/models.py)
- Service firmware : [`backend/api/services/firmware.py`](backend/api/services/firmware.py)
- Détection dans l'ingestion : [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)
- Endpoint admin OTA : `admin_device_schedule_ota()` dans [`backend/api/views.py`](backend/api/views.py)
- Documentation firmware : [`docs/source/esp32_firmware.rst`](docs/source/esp32_firmware.rst)

Si le firmware n'est pas conforme, le backend peut lever une alerte `firmware_outdated`. La mise à jour OTA reste pilotée côté admin.

## 24. Email et Mailpit

En développement, Mailpit sert de serveur SMTP local et d'interface de consultation des emails.

Références :

- Service Docker `mailpit` : [`docker-compose.yml`](docker-compose.yml)
- Service production contrôlé : [`docker-compose.prod.yml`](docker-compose.prod.yml)
- Envoi QR réservation : [`backend/api/services/email_notifications.py`](backend/api/services/email_notifications.py)
- Tests email QR : [`backend/api/tests/test_reservations.py`](backend/api/tests/test_reservations.py)

Flux QR email :

```text
Création réservation QR
  -> backend génère le QR
  -> backend envoie un email
  -> Mailpit capture le message en développement
```

## 25. Reverse proxy Nginx

Nginx expose une porte d'entrée unique :

```text
https://localhost/
  -> frontend

https://localhost/api/
  -> backend Django

https://localhost/admin/
  -> admin Django

https://localhost/ws/
  -> WebSocket Django Channels

https://localhost/grafana/
  -> Grafana

https://localhost/kiosk/
  -> simulation kiosque en stack locale uniquement
```

En production terrain, le kiosque n'est pas servi par le serveur Debian. Il tourne
sur le Raspberry physique, généralement sur `http://localhost:9000` côté
Raspberry. Le reverse proxy de production renvoie donc explicitement que le
kiosque doit être exécuté localement sur la borne.

Références :

- Configuration locale : [`nginx/conf.d/station.conf`](nginx/conf.d/station.conf)
- Configuration production : [`nginx/prod.conf.d/station.conf`](nginx/prod.conf.d/station.conf)
- Configuration globale : [`nginx/nginx.conf`](nginx/nginx.conf), [`nginx/nginx.prod.conf`](nginx/nginx.prod.conf)

Nginx applique :

- TLS ;
- redirection HTTP vers HTTPS ;
- taille de requête maximale ;
- headers de sécurité ;
- proxy WebSocket ;
- routage vers les services internes.

## 26. Déploiement Docker

Stack locale :

```text
db
redis
mailpit
mqtt
backend
celery
celery-beat
mqtt-bridge
mqtt-simulator
grafana
frontend
raspberry
nginx
```

Référence : [`docker-compose.yml`](docker-compose.yml)

Stack production :

- images pinnées par digest pour plusieurs services ;
- logs Docker limités ;
- ports internes non exposés directement ;
- backend servi par un serveur ASGI de production ;
- Nginx en point d'entrée ;
- volumes persistants ;
- healthchecks.

Référence : [`docker-compose.prod.yml`](docker-compose.prod.yml)

Scripts d'exploitation :

- sauvegarde : [`scripts/backup-prod.sh`](scripts/backup-prod.sh)
- restauration : [`scripts/restore-prod.sh`](scripts/restore-prod.sh)
- génération SBOM : [`scripts/generate-sbom.ps1`](scripts/generate-sbom.ps1)
- initialisation MQTT auth : [`scripts/init-mqtt-auth.ps1`](scripts/init-mqtt-auth.ps1)

## 27. Performance et scalabilité

La performance a été traitée à plusieurs niveaux. L'objectif n'est pas de
dimensionner un réseau national, mais d'éviter les blocages évidents et de rendre
le prototype extensible.

Base de données :

- index sur les dates de réservation, les fenêtres de session, les timestamps de
  télémétrie, les statuts de device, les alertes et les relations
  station/borne/emplacement ;
- contraintes `CHECK` et `UNIQUE` pour éviter de corriger en application des
  incohérences qui peuvent être refusées directement en base ;
- TimescaleDB disponible pour les séries temporelles et `pg_stat_statements`
  préparé pour analyser les requêtes lentes en production ;
- rétention des mesures brutes à 90 jours pour éviter une croissance illimitée.

API Django :

- `select_related()` et `prefetch_related()` sur les vues qui affichent des
  objets liés, pour éviter le problème N+1 ;
- pagination sur les listes d'administration ;
- cache Redis du catalogue stations pendant 60 secondes ;
- tests de performance de requêtes dans
  [`backend/api/tests/test_query_performance.py`](backend/api/tests/test_query_performance.py).

Traitements asynchrones :

- Celery absorbe l'ingestion MQTT, les alertes, les notifications et les tâches
  de rétention ;
- le thread MQTT ne fait pas de traitement lourd : il délègue au worker ;
- Redis sert de broker Celery, cache applicatif et couche Channels.

Frontend et reverse proxy :

- frontend Vite construit en assets statiques ;
- Nginx sert les assets avec cache long sur `/assets/` et `/static/` ;
- gzip activé côté Nginx production ;
- `client_max_body_size`, timeouts et rate limiting Nginx pour éviter les abus
  simples ;
- logs Nginx avec temps de réponse upstream pour diagnostiquer les lenteurs.

Limites connues :

- il n'y a pas encore de test de charge massif ;
- les hypertables TimescaleDB restent une évolution si le volume de télémétrie
  devient important ;
- la supervision Grafana dépend de la qualité des requêtes SQL et devra être
  revue si le nombre de stations augmente fortement.

## 28. Tests automatisés

Le projet contient des tests sur les points critiques :

- API d'authentification ;
- réservation ;
- terminal ;
- mode dégradé ;
- ingestion MQTT ;
- scénario A à Z ;
- supervision ;
- alertes ;
- sécurité Nginx ;
- durcissement production ;
- performance des requêtes ;
- contrat MQTT Raspberry/ESP32.

Références :

- Tests backend : [`backend/api/tests/`](backend/api/tests/)
- Test A à Z : [`backend/api/tests/test_end_to_end_charge_flow.py`](backend/api/tests/test_end_to_end_charge_flow.py)
- Tests terminal : [`backend/api/tests/test_terminal_auth.py`](backend/api/tests/test_terminal_auth.py)
- Tests MQTT : [`backend/api/tests/test_mqtt_ingestion.py`](backend/api/tests/test_mqtt_ingestion.py)
- Tests Raspberry : [`raspberry/tests/`](raspberry/tests/)
- Tests frontend : [`frontend/tests/e2e/`](frontend/tests/e2e/)

Le test A à Z couvre :

```text
création réservation QR
  -> session mobile
  -> autorisation utilisateur
  -> consommation kiosque
  -> création session
  -> ACK UNLOCK
  -> ACK START
  -> télémétrie uniquement sur l'emplacement réservé
  -> ACK STOP
  -> clôture session
  -> données Grafana/Timescale exploitables
```

## 29. Parcours complet nominal

Voici le scénario complet le plus représentatif :

```text
1. L'utilisateur se connecte à la PWA.
2. Il choisit une station et un créneau.
3. Le backend attribue un emplacement libre.
4. La réservation est créée.
5. L'utilisateur arrive devant la borne.
6. Il badge, scanne son QR ou utilise la session mobile.
7. Le kiosque transmet l'accès au backend.
8. Le backend valide station, borne, emplacement, créneau et secret.
9. Une Session est créée ou retrouvée.
10. Le backend renvoie slot_id et mqtt_prefix au kiosque.
11. Le Raspberry publie UNLOCK vers l'ESP32.
12. L'ESP32 ouvre le boîtier par impulsion et répond par ACK.
13. L'utilisateur branche le câble ou active le générateur de charge du prototype.
14. L'ESP32 publie `cable=true`, ou une mesure `current >= 0.1 A` récente tant
    que le capteur câble n'est pas câblé, puis le Raspberry publie START vers l'ESP32.
15. L'ESP32 répond par ACK, publie status et telemetry.
16. Le mqtt-bridge ingère les messages.
17. Celery écrit les mesures en base.
18. Grafana affiche la session, les mesures et l'état device.
19. L'utilisateur arrête la charge.
20. Le Raspberry publie STOP.
21. L'ESP32 répond par ACK stopped.
22. Le backend clôture la session.
```

Référence de test : [`backend/api/tests/test_end_to_end_charge_flow.py`](backend/api/tests/test_end_to_end_charge_flow.py)

## 30. Règle d'or du projet

Le backend est l'autorité métier.

Le Raspberry est l'autorité locale d'exécution sur la borne.

L'ESP32 est l'exécutant matériel de l'emplacement.

Grafana est un outil de supervision, pas une source de vérité.

Redis est une file et un cache, pas la base métier.

PostgreSQL/TimescaleDB est la source persistante des réservations, sessions, mesures, alertes et journaux.
