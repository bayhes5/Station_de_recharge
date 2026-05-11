# ESP32

Le projet cible trois ESP32, soit trois emplacements de recharge.

Le dossier `emplacement1/` contient le prototype MicroPython commun. Les cartes
physiques peuvent reutiliser la meme base firmware en changeant simplement:

- `SLOT_ID` (`slot1`, `slot2`, `slot3`)
- `CLIENT_ID`
- `MQTT_HOST`
- les identifiants WiFi
- les pins DHT22 / INA219 / relais selon le cablage

Le dossier `wokwi/` contient une simulation ESP32 interactive pour tester le
flux MQTT vers le backend et Grafana.

## Capteurs du prototype physique

Le firmware `emplacement1/main.py` publie un payload compatible Grafana avec:

- DHT22: `temperature`, `humidity`
- INA219: `current`, `voltage`, `power`
- contacts: `door`, `cable`
- etat: `state`

Pins par defaut:

```python
DHT_PIN = 4
INA219_SDA_PIN = 21
INA219_SCL_PIN = 25
LOCK_PIN = 23
CHARGE_PIN = 22
```

Si le DHT22 ou l'INA219 n'est pas detecte, le firmware publie des valeurs
simulees. C'est volontaire pour tester rapidement le flux MQTT -> backend ->
Grafana avant le cablage final.

L'ESP32 demarre serrure fermee, puis le `START` envoye par le Raspberry
deverrouille l'emplacement. La charge ne demarre qu'apres detection du cable et
fermeture du boitier.

Pour le test Thonny:

1. adapter `WIFI_SSID`, `WIFI_PASSWORD` et `MQTT_HOST`
2. enregistrer `esp32/emplacement1/main.py` sur l'ESP32 sous le nom `main.py`
3. redemarrer l'ESP32
4. verifier les messages sur `station/slot1/telemetry`

## Topics MQTT

Chaque ESP32 publie:

```text
station/<slot_id>/ack
station/<slot_id>/telemetry
station/<slot_id>/status
station/<slot_id>/alert
```

Chaque ESP32 ecoute:

```text
station/<slot_id>/cmd
```

## Commandes acceptees

Le payload peut etre un JSON:

```json
{
  "command_id": "uuid-ou-token-court",
  "action": "START",
  "session_id": "<uuid-session>"
}
```

Actions supportees:

- `START`: ouvre le boitier et attend cable + fermeture avant charge
- `STOP`: arrete la charge et deverrouille
- `LOCK`: verrouille le boitier
- `UNLOCK`: deverrouille le boitier

Chaque commande doit produire un ACK sur `station/<slot_id>/ack`:

```json
{
  "command_id": "meme-valeur-que-la-commande",
  "action": "START",
  "status": "accepted",
  "message": "Emplacement reserve.",
  "state": "reserved",
  "slot_id": "slot1",
  "session_id": "<uuid-session>"
}
```

Le Raspberry attend cet ACK pendant `MQTT_ACK_TIMEOUT_SECONDS`. En developpement,
`MQTT_ACK_REQUIRED=False` permet de tester sans ESP32. Sur une vraie borne,
`MQTT_ACK_REQUIRED=True` force l'erreur si l'ESP32 ne confirme pas.

## Test local MQTT -> Grafana sans ESP32

La stack Docker contient un simulateur qui publie les memes champs que le
firmware:

```powershell
docker compose up -d backend mqtt mqtt-bridge celery grafana
docker compose --profile simulation up -d mqtt-simulator
```

Puis ouvrir Grafana:

```text
http://localhost:3000/grafana/
```

Dashboard:

```text
Station - Supervision technique
```

Les panneaux a verifier en premier:

- Temperature par emplacement
- Humidite
- Courant de charge
- Tension
- Puissance

## Machine d'etat

```text
idle -> reserved -> charging -> idle
```

En `reserved`, l'ESP32 attend:

- cable detecte
- boitier ferme

En `charging`, l'ESP32 arrete immediatement en cas de:

- boitier ouvert
- cable retire
- courant superieur au seuil
- temperature superieure au seuil

## Continuité locale

Le chemin nominal reste la communication avec le backend : les reservations,
droits d'acces et sessions sont valides cote serveur, puis l'ESP32 execute les
commandes recues.

En cas de coupure temporaire du serveur ou de la liaison applicative, l'ESP32
doit conserver ses reflexes locaux de securite et journaliser les evenements qui
ne peuvent pas etre transmis. LittleFS est le stockage embarque cible pour garder
une file courte de mesures, alertes et changements d'etat a republier quand le
broker ou le backend redevient disponible.

Ce stockage local ne remplace pas la base centrale. Il sert a eviter une perte
de traces et a faciliter la reconciliation apres incident.

## Simulation Wokwi

Ouvrir `esp32/wokwi/` avec l'extension Wokwi.

La simulation contient:

- un ESP32
- un switch `Cable`
- un switch `Boitier`
- un potentiometre `Courant`
- un potentiometre `Temperature`
- une LED rouge pour la serrure
- une LED verte pour la charge

Par defaut, la simulation publie sur le broker public:

```text
test.mosquitto.org
```

Pour voir les donnees dans Grafana via le backend local, configurer
temporairement le bridge backend avec le meme broker:

```env
MQTT_HOST=test.mosquitto.org
MQTT_PORT=1883
MQTT_BASE_TOPIC=station
```

Puis lancer la stack. Les messages publies sur `station/slot1/telemetry` seront
traites par `mqtt-bridge`, stockes en base et visibles dans Grafana.
