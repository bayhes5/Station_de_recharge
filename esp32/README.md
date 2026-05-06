# ESP32

Le projet cible trois ESP32, soit trois emplacements de recharge.

Le dossier `emplacement1/` contient le prototype MicroPython commun. Les cartes
physiques peuvent reutiliser la meme base firmware en changeant simplement:

- `SLOT_ID` (`slot1`, `slot2`, `slot3`)
- `CLIENT_ID`
- `MQTT_HOST`
- les identifiants WiFi

Le dossier `wokwi/` contient une simulation ESP32 interactive pour tester le
flux MQTT vers le backend et Grafana.

## Topics MQTT

Chaque ESP32 publie:

```text
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
  "action": "START",
  "session_id": "<uuid-session>"
}
```

Actions supportees:

- `START`: ouvre le boitier et attend cable + fermeture avant charge
- `STOP`: arrete la charge et deverrouille
- `LOCK`: verrouille le boitier
- `UNLOCK`: deverrouille le boitier

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
