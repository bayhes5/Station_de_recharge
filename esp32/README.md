# ESP32

Le projet cible trois ESP32, soit trois emplacements de recharge.

Le dossier `emplacement1/` contient le prototype MicroPython commun. Les cartes
physiques peuvent réutiliser la même base firmware en changeant simplement :

- `SLOT_ID` (`slot1`, `slot2`, `slot3`)
- `CLIENT_ID`
- `MQTT_HOST`
- les identifiants Wi-Fi
- les pins DHT22 / courant / relais selon le câblage

Le dossier `wokwi/` contient une simulation ESP32 interactive pour tester le
flux MQTT vers le backend et Grafana.

## Architecture MQTT cible

En production, les ESP32 ne doivent pas dépendre directement du backend central.
Ils se connectent au broker Mosquitto local hébergé sur le Raspberry Pi de la
borne :

```text
ESP32 -> Mosquitto Raspberry -> bridge MQTT/backend -> base -> Grafana
Raspberry -> Mosquitto Raspberry -> ESP32 pour START / STOP / LOCK / UNLOCK
```

Cela permet au Raspberry de continuer à commander les ESP32 en mode dégradé,
même si le serveur central est momentanément indisponible. Le backend reste la
source de vérité pour les droits, les réservations et l'historique consolidé.

Configuration typique sur une vraie borne :

```python
MQTT_HOST = "192.168.1.10"  # IP du Raspberry Pi sur le Wi-Fi local
MQTT_PORT = 1883
MQTT_USER = "esp32_station_demo_borne_1_slot1"
MQTT_PASSWORD = "mot-de-passe-mqtt"
MQTT_BASE_TOPIC = "station"
MQTT_TOPIC_PREFIX = "station-demo/borne-1"
SLOT_ID = "slot1"
CLIENT_ID = "esp32-station-demo-borne-1-slot1"
```

Depuis un ESP32, `localhost` ne doit jamais être utilisé : il désignerait
l'ESP32 lui-même, pas le Raspberry ni le PC de développement.

Pour la migration du broker vers le Raspberry, remplacer l'ancienne IP du PC
Docker par l'IP Wi-Fi du Raspberry. Lors du dernier test du projet, le Raspberry
était joignable en `172.20.10.14`, mais cette valeur peut changer selon le
hotspot.

## Capteurs du prototype physique

Le firmware `emplacement1/main.py` publie un payload compatible Grafana avec :

- inventaire : `slot_id`, `client_id`, `firmware_version`, `hardware_mac`,
  `ip_address`
- DHT22: `temperature`, `humidity`
- SEN0214: `current`
- tension fixe de prototype ou capteur de tension futur : `voltage`, `power`,
  `energy_kwh`
- contacts: `door`, `cable`
- serrure: `lock`
- état : `state`

Pins par défaut :

```python
DHT_PIN = 15
ADC_CURRENT_PIN = 34
LOCK_PIN = 26
CHARGE_RELAY_PIN = 22
```

La serrure actuellement testée utilise un relais actif-bas sur `GPIO26`.
La fenêtre d'ouverture dure `15` secondes, puis le relais revient au repos si
la charge n'a pas démarré. Le relais revient aussi au repos dès que l'état passe
en `charging`, afin que la serrure reste fermée pendant la charge. La tension
réelle n'est pas encore mesurée : le prototype publie une tension fixe configurée
à `12 V` pour estimer la puissance et l'énergie.

L'ESP32 démarre serrure fermée. Après authentification à la borne, le Raspberry
envoie `UNLOCK` pour ouvrir le boîtier. Le `START` est envoyé seulement ensuite,
quand l'utilisateur a branché le câble et que la télémétrie remonte
`cable=true`. Le kiosk ne propose plus de bouton `Démarrer la charge` avant le
branchement : il déclenche automatiquement `START` lorsque l'emplacement autorisé
signale le câble. La charge ne démarre qu'après détection du câble et fermeture
du boîtier lorsque ces capteurs seront câblés.

Pour le test Thonny :

1. adapter `WIFI_SSID`, `WIFI_PASSWORD` et `MQTT_HOST` ;
2. renseigner `MQTT_USER` et `MQTT_PASSWORD` si Mosquitto sécurisé est activé ;
3. enregistrer `esp32/emplacement1/main.py` sur l'ESP32 sous le nom `main.py` ;
4. redémarrer l'ESP32 ;
5. vérifier les messages sur `station/slot1/telemetry`.

## Topics MQTT

Chaque ESP32 publie :

```text
station/<slot_id>/ack
station/<slot_id>/telemetry
station/<slot_id>/status
station/<slot_id>/alert
```

Chaque ESP32 écoute :

```text
station/<slot_id>/cmd
```

## Commandes acceptées

Le payload peut être un JSON :

```json
{
  "command_id": "uuid-ou-token-court",
  "action": "START",
  "session_id": "<uuid-session>"
}
```

Actions supportées :

- `UNLOCK` : ouvre le boîtier après authentification
- `START` : démarre la charge après branchement et fermeture du boîtier
- `STOP` : arrête la charge et déverrouille
- `LOCK` : verrouille le boîtier

Chaque commande doit produire un ACK sur `station/<slot_id>/ack` :

```json
{
  "command_id": "même-valeur-que-la-commande",
  "action": "START",
  "status": "accepted",
  "message": "Emplacement réservé.",
  "state": "reserved",
  "slot_id": "slot1",
  "client_id": "esp32-slot1",
  "firmware_version": "1.0.0",
  "hardware_mac": "AA:BB:CC:DD:EE:FF",
  "ip_address": "192.168.1.42",
  "session_id": "<uuid-session>"
}
```

Le Raspberry attend cet ACK pendant `MQTT_ACK_TIMEOUT_SECONDS`. En développement,
`MQTT_ACK_REQUIRED=False` permet de tester sans ESP32. Sur une vraie borne,
`MQTT_ACK_REQUIRED=True` force l'erreur si l'ESP32 ne confirme pas.

## Test local MQTT -> Grafana sans ESP32

La stack Docker contient un simulateur qui publie les mêmes champs que le
firmware :

```powershell
docker compose up -d backend mqtt mqtt-bridge celery grafana
docker compose --profile simulation up -d mqtt-simulator
```

Puis ouvrir Grafana :

```text
http://localhost:3000/grafana/
```

Dashboard:

```text
Station - Supervision technique
```

Les panneaux à vérifier en premier :

- Température par emplacement
- Humidité
- Courant de charge
- Tension
- Puissance

## Machine d'état

```text
idle -> reserved -> charging -> idle
```

En `reserved`, l'ESP32 attend :

- câble détecté
- boîtier fermé

En `charging`, l'ESP32 arrête immédiatement en cas de :

- boîtier ouvert
- câble retiré
- courant supérieur au seuil
- température supérieure au seuil

## Continuité locale

Le chemin nominal reste la communication avec le backend : les réservations,
droits d'accès et sessions sont validés côté serveur, puis l'ESP32 exécute les
commandes reçues via le broker local.

En cas de coupure temporaire du serveur ou de la liaison applicative, l'ESP32
doit conserver ses réflexes locaux de sécurité et journaliser les événements qui
ne peuvent pas être transmis. LittleFS est le stockage embarqué cible pour garder
une file courte de mesures, alertes et changements d'état à republier quand le
broker ou le backend redevient disponible.

Ce stockage local ne remplace pas la base centrale. Il sert à éviter une perte
de traces et à faciliter la réconciliation après incident.

## Déploiement persistant et reproductible

Sur MicroPython, le fichier `main.py` stocké dans LittleFS démarre
automatiquement à chaque mise sous tension de l'ESP32. Lancer le fichier depuis
Thonny ne suffit donc pas : il faut le sauvegarder **sur l'ESP32** sous le nom
exact `main.py`.

Déploiement automatisé avec `mpremote` :

```powershell
python -m pip install esptool mpremote
mpremote connect list

.\scripts\deploy-esp32-micropython.ps1 `
  -Port COM5 `
  -SourceDir esp32\emplacement1 `
  -FirmwareVersion "1.3.0-access-before-charge" `
  -OpenRepl
```

Pour préparer MQTT TLS avec la CA locale `Metropole Verte`, convertir la racine
Smallstep en DER puis la copier dans LittleFS :

```powershell
openssl x509 -in metropole-verte-root-ca.crt -outform DER -out certs\metropole-verte-root-ca.der

.\scripts\deploy-esp32-micropython.ps1 `
  -Port COM5 `
  -SourceDir esp32\emplacement1 `
  -FirmwareVersion "1.3.0-access-before-charge" `
  -RootCaPath certs\metropole-verte-root-ca.der `
  -OpenRepl
```

Configuration TLS côté firmware :

```python
MQTT_HOST = "mqtt.station.local"
MQTT_PORT = 8883
MQTT_TLS_ENABLED = True
MQTT_TLS_CA_CERT_FILE = "certs/metropole-verte-root-ca.der"
MQTT_TLS_SERVER_HOSTNAME = "mqtt.station.local"
```

La procédure complète est documentée dans `docs/source/esp32_firmware.rst`.

## Simulation Wokwi

Ouvrir `esp32/wokwi/` avec l'extension Wokwi.

La simulation contient :

- un ESP32
- un switch `Cable`
- un switch `Boitier`
- un potentiomètre `Courant`
- un potentiomètre `Température`
- une LED rouge pour la serrure
- une LED verte pour la charge

Par défaut, la simulation publie sur le broker public :

```text
test.mosquitto.org
```

Pour voir les données dans Grafana via le backend local, configurer
temporairement le bridge backend avec le même broker :

```env
MQTT_HOST=test.mosquitto.org
MQTT_PORT=1883
MQTT_BASE_TOPIC=station
```

Puis lancer la stack. Les messages publiés sur `station/slot1/telemetry` seront
traités par `mqtt-bridge`, stockés en base et visibles dans Grafana.
