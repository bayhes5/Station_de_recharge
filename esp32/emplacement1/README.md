# Firmware ESP32 - Emplacement 1

Ce dossier contient le firmware MicroPython à flasher avec Thonny sur l'ESP32 de l'emplacement 1.

## Câblage pris en compte

- DHT22 sur `GPIO25` pour température et humidité.
- Capteur de courant analogique sur `GPIO15`, d'après le prototype `CURRENT.txt`.
- Serrure, relais, détection de câble et contact de porte non câblés pour l'instant.

Le fichier [main.py](main.py) désactive donc par défaut les entrées/sorties physiques non câblées :

```python
PHYSICAL_INPUTS_ENABLED = False
OUTPUTS_ENABLED = False
```

## Paramètres à modifier avant flash

```python
WIFI_SSID = "WIFI_SSID"
WIFI_PASSWORD = "WIFI_PASSWORD"
MQTT_HOST = "192.168.1.10"
MQTT_TOPIC_PREFIX = "station-demo/borne-1"
SLOT_ID = "slot1"
```

`MQTT_HOST` doit être l'adresse IP de la machine qui exécute Mosquitto :

- PC de développement avec Docker ;
- ou Raspberry Pi en borne réelle.

Avec la configuration de démonstration actuelle, l'ESP32 publie sur :

```text
station/station-demo/borne-1/slot1/telemetry
station/station-demo/borne-1/slot1/status
station/station-demo/borne-1/slot1/ack
```

et écoute :

```text
station/station-demo/borne-1/slot1/cmd
```

## Courant ADC ou INA219

Pour le test actuel, le courant est en mode ADC :

```python
CURRENT_SENSOR_MODE = "adc"
ADC_CURRENT_PIN = 15
```

Si le capteur INA219 est câblé plus tard, passer à :

```python
CURRENT_SENSOR_MODE = "ina219"
INA219_SDA_PIN = 21
INA219_SCL_PIN = 22
```

Dans ce cas, vérifier aussi que le relais de charge n'utilise pas le même GPIO que `INA219_SCL_PIN`.

## Vérification rapide

Après flash, la console Thonny doit afficher :

```text
Connected to WiFi: (...)
MQTT connected to <ip>:1883.
Listening: station/station-demo/borne-1/slot1/cmd
Telemetry: station/station-demo/borne-1/slot1/telemetry
```

La supervision backend/Grafana reçoit ensuite les mesures DHT22 et courant avec un rythme adapté à l'état de l'emplacement :

- toutes les `5` secondes pendant une charge ou une attente de branchement ;
- toutes les `30` secondes lorsque l'emplacement est au repos ;
- immédiatement après un changement d'état important : START, STOP, verrouillage ou déverrouillage.
