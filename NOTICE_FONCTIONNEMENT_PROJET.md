# Notice de fonctionnement du projet

Cette notice explique le fonctionnement global de la station de recharge intelligente, en partant du parcours utilisateur jusqu'aux flux techniques entre le frontend, le backend, le Raspberry Pi, les ESP32, MQTT, Redis/Celery, PostgreSQL/TimescaleDB et Grafana.

Elle complète la documentation Sphinx présente dans `docs/source/` avec une lecture plus transversale du projet.

Pour préparer les questions de soutenance du type "où ?", "comment ?", "avec quelle librairie ?" ou "quelle donnée est stockée ?", utiliser aussi :

- [`NOTICE_TECHNIQUE_IMPLEMENTATION.md`](NOTICE_TECHNIQUE_IMPLEMENTATION.md)
- [`NOTICE_SOUTENANCE_TECHNIQUE_DETAILLEE.md`](NOTICE_SOUTENANCE_TECHNIQUE_DETAILLEE.md)

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

La réservation est l'objet métier qui autorise l'accès. La session est l'objet opérationnel créé lorsque l'utilisateur démarre réellement une charge.

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
  -> affiche "Session démarrée sur la borne" quand le kiosque a consommé l'autorisation

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
```

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
  -> Raspberry publie START sur MQTT
  -> ESP32 répond par ACK
  -> Raspberry affiche l'écran de charge
```

Topic de commande :

```text
station/<mqtt_prefix>/<slot_id>/cmd
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

La serrure est ouverte par impulsion de 5 secondes lors d'un `START`, `STOP` ou
`UNLOCK`, puis le relais revient au repos. Le firmware envoie l'ACK `START`
avant l'impulsion pour ne pas dépasser le timeout MQTT côté Raspberry.

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
- `api.prune_old_telemetry` pour appliquer la rétention des mesures.

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

TimescaleDB apporte surtout un intérêt pour les séries temporelles : télémétrie, capteurs et historique de session. Le projet reste compatible avec PostgreSQL classique si l'extension n'est pas disponible.

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
- Alerting Grafana : [`grafana/provisioning/alerting/station-alerts.yml`](grafana/provisioning/alerting/station-alerts.yml)

Les dashboards exploitent notamment :

- `device` pour l'état ESP32 ;
- `capteur_data` pour les mesures brutes ;
- `session_telemetry` pour les mesures liées à une session ;
- `charging_session` pour l'état de charge ;
- `alerte` pour les incidents ;
- `device_command_log` pour les START/STOP et ACK ;
- `station`, `borne`, `emplacement` pour le contexte physique.

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

## 22. Privacy by design

Le projet limite l'exposition des données personnelles :

- les secrets RFID/QR/SMS sont hashés ;
- le refresh token long est en cookie HttpOnly ;
- les exports de compte existent côté API ;
- les consentements sont historisés ;
- les numéros de téléphone peuvent être masqués ;
- les logs sécurité ne stockent que les informations nécessaires ;
- PostgreSQL Anonymizer est préparé de manière optionnelle.

Références :

- Consentements : `Consentement` dans [`backend/api/models.py`](backend/api/models.py)
- Export compte : `export_account()` dans [`backend/api/views.py`](backend/api/views.py)
- Masquage téléphone : [`backend/api/services/sms.py`](backend/api/services/sms.py)
- Anonymizer optionnel : [`backend/api/migrations/0027_optional_postgresql_anonymizer.py`](backend/api/migrations/0027_optional_postgresql_anonymizer.py)
- Pages CGU/confidentialité : [`backend/api/page_views.py`](backend/api/page_views.py)

L'extension PostgreSQL Anonymizer est activée uniquement si elle est disponible dans l'image PostgreSQL utilisée. Sinon la migration passe sans casser le déploiement.

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
  -> kiosque Raspberry
```

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

## 27. Tests automatisés

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
  -> ACK START
  -> télémétrie uniquement sur l'emplacement réservé
  -> ACK STOP
  -> clôture session
  -> données Grafana/Timescale exploitables
```

## 28. Parcours complet nominal

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
11. Le Raspberry publie START vers l'ESP32.
12. L'ESP32 répond par ACK.
13. L'ESP32 publie status et telemetry.
14. Le mqtt-bridge ingère les messages.
15. Celery écrit les mesures en base.
16. Grafana affiche la session, les mesures et l'état device.
17. L'utilisateur arrête la charge.
18. Le Raspberry publie STOP.
19. L'ESP32 répond par ACK stopped.
20. Le backend clôture la session.
```

Référence de test : [`backend/api/tests/test_end_to_end_charge_flow.py`](backend/api/tests/test_end_to_end_charge_flow.py)

## 29. Règle d'or du projet

Le backend est l'autorité métier.

Le Raspberry est l'autorité locale d'exécution sur la borne.

L'ESP32 est l'exécutant matériel de l'emplacement.

Grafana est un outil de supervision, pas une source de vérité.

Redis est une file et un cache, pas la base métier.

PostgreSQL/TimescaleDB est la source persistante des réservations, sessions, mesures, alertes et journaux.
