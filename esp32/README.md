# ESP32

Le projet cible trois ESP32, soit trois emplacements de recharge.

Le dossier `emplacement1/` contient le prototype MicroPython commun. Les cartes
physiques peuvent réutiliser la même base firmware en changeant simplement :

- `SLOT_ID` (`slot1`, `slot2`, `slot3`)
- `CLIENT_ID`
- `MQTT_HOST`
- les identifiants Wi-Fi
- les pins DHT22 / INA219 / relais selon le câblage

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
MQTT_USER = "esp32_slot1"
MQTT_PASSWORD = "mot-de-passe-mqtt"
MQTT_BASE_TOPIC = "station"
SLOT_ID = "slot1"
CLIENT_ID = "esp32-slot1"
```

Depuis un ESP32, `localhost` ne doit jamais être utilisé : il désignerait
l'ESP32 lui-même, pas le Raspberry ni le PC de développement.

## Capteurs du prototype physique

Le firmware `emplacement1/main.py` publie un payload compatible Grafana avec :

- DHT22: `temperature`, `humidity`
- INA219: `current`, `voltage`, `power`
- contacts: `door`, `cable`
- état : `state`

Pins par défaut :

```python
DHT_PIN = 4
INA219_SDA_PIN = 21
INA219_SCL_PIN = 25
LOCK_PIN = 23
CHARGE_PIN = 22
```

Si le DHT22 ou l'INA219 n'est pas détecté, le firmware publie des valeurs
simulées. C'est volontaire pour tester rapidement le flux MQTT -> backend ->
Grafana avant le câblage final.

L'ESP32 démarre serrure fermée, puis le `START` envoyé par le Raspberry
déverrouille l'emplacement. La charge ne démarre qu'après détection du câble et
fermeture du boîtier.

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

- `START` : ouvre le boîtier et attend câble + fermeture avant charge
- `STOP` : arrête la charge et déverrouille
- `LOCK` : verrouille le boîtier
- `UNLOCK` : déverrouille le boîtier

Chaque commande doit produire un ACK sur `station/<slot_id>/ack` :

```json
{
  "command_id": "même-valeur-que-la-commande",
  "action": "START",
  "status": "accepted",
  "message": "Emplacement réservé.",
  "state": "reserved",
  "slot_id": "slot1",
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
