# Firmware ESP32 - Emplacement 1

Ce dossier contient le firmware MicroPython à flasher avec Thonny sur l'ESP32 de l'emplacement 1.

## Câblage pris en compte

- DHT22 sur `GPIO15` pour la température et l'humidité.
- Capteur de courant analogique DFRobot SEN0214 sur `GPIO34`.
- Serrure électromagnétique via relais actif-bas sur `GPIO26`.
- Identité ESP32 remontée automatiquement : version firmware, adresse IP et adresse MAC.
- Tension bus fixe de prototype à `12 V` pour estimer la puissance.
- Relais de charge, détection de câble et contact de porte non câblés pour l'instant.

Le fichier [main.py](main.py) active uniquement les éléments câblés :

```python
PHYSICAL_INPUTS_ENABLED = False
LOCK_OUTPUT_ENABLED = True
CHARGE_RELAY_OUTPUT_ENABLED = False
SIMULATE_CABLE_PRESENT_FOR_AUTO_START = False
CURRENT_SENSOR_MODE = "sen0214"
VOLTAGE_SENSOR_MODE = "fixed"
FIXED_BUS_VOLTAGE = 12.0
DHT_PIN = 15
ADC_CURRENT_PIN = 34
LOCK_PIN = 26
LOCK_RELAY_ACTIVE_LOW = True
LOCK_UNLOCK_PULSE_SECONDS = 5
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

## Capteur de courant SEN0214

Le SEN0214 est un capteur de courant analogique. Sa sortie est une tension de mesure, mais cette tension ne doit pas être publiée comme tension de charge. Le firmware l'utilise uniquement pour calculer le champ MQTT `current`.

Configuration actuelle :

```python
CURRENT_SENSOR_MODE = "sen0214"
ADC_CURRENT_PIN = 34
ADC_CURRENT_INPUT_SCALE = 1.515
SEN0214_AUTO_CALIBRATE_ZERO = True
SEN0214_SENSITIVITY_V_PER_A = 0.100
SEN0214_ABSOLUTE_CURRENT = True
ADC_NOISE_FLOOR_A = 0.05
ADC_AVERAGE_SAMPLES = 120
ADC_AVERAGE_DELAY_US = 500
```

Points de calibration à vérifier avec le montage réel :

- Au démarrage, l'ESP32 calibre automatiquement le zéro courant. Aucun consommateur ne doit être branché pendant les premières secondes.
- `SEN0214_ZERO_CURRENT_VOLTAGE` sert de valeur de secours si `SEN0214_AUTO_CALIBRATE_ZERO = False`.
- `SEN0214_SENSITIVITY_V_PER_A` dépend de la version exacte du module.
- Si un pont diviseur est ajouté entre le capteur et l'ESP32, `ADC_CURRENT_INPUT_SCALE` doit convertir la tension ADC en tension réelle du capteur.
- Si le SEN0214 est alimenté en 5 V, la broche ADC de l'ESP32 doit être protégée pour ne jamais recevoir plus de 3,3 V.

## Serrure par relais

Le test physique reçu utilise un relais sur `GPIO26`. Le relais est actif à l'état bas :

- `0` : relais actif, serrure alimentée, ouverture ;
- `1` : relais au repos, serrure non alimentée, fermeture.

Le firmware garde donc la serrure au repos au démarrage. La commande `UNLOCK` est envoyée par le kiosk juste après validation de l'authentification à la borne. Elle déclenche une impulsion d'ouverture de `5` secondes, puis remet le relais au repos pour éviter d'alimenter la serrure en continu.

La commande MQTT `START` ne sert plus à ouvrir le boîtier. Elle démarre uniquement la charge électrique après ouverture du boîtier et détection du câble. Quand les capteurs de porte et de câble seront câblés, le Raspberry déclenchera `START` automatiquement dès que la télémétrie indique `cable=true`, et l'ESP32 devra accepter la charge seulement si le boîtier est refermé et si le capteur Hall confirme la présence du câble.

La séquence cible est donc :

1. Badge, QR ou code SMS validé par le kiosk.
2. Kiosk -> ESP32 : `UNLOCK`.
3. Utilisateur ouvre le boîtier et branche le câble.
4. ESP32 publie `cable=true` en télémétrie.
5. Kiosk -> ESP32 : `START` automatique.
6. ESP32 vérifie câble et boîtier, puis active la charge.

Avec `PHYSICAL_INPUTS_ENABLED = False`, le capteur câble n'est pas encore remonté
par le firmware. Le kiosk restera donc sur l'écran "Branchez le câble" tant que
l'ESP32 ne publie pas `cable=true`. Pour un essai de banc sans capteur Hall, il
est possible de mettre `SIMULATE_CABLE_PRESENT_FOR_AUTO_START = True` : l'ESP32
publiera alors `cable=true` en phase `waiting_plug`, ce qui permet de tester le
démarrage automatique sans modifier le kiosk.

## Tension de charge et puissance

La tension de charge réelle n'est pas encore mesurée. Pour le prototype, le firmware utilise une tension bus fixe afin d'estimer la puissance et l'énergie :

```python
VOLTAGE_SENSOR_MODE = "fixed"
FIXED_BUS_VOLTAGE = 12.0
```

Le firmware publie donc :

- `current` : courant calculé depuis le SEN0214 ;
- `voltage` : `12.0`, valeur fixe de prototype, non mesurée ;
- `power` : puissance estimée avec `FIXED_BUS_VOLTAGE * current` ;
- `energy_kwh` : énergie estimée à partir de la puissance.

En production, cette tension fixe devra être remplacée par une mesure réelle. Quand un capteur de tension ou un INA219 sera ajouté, il faudra activer le mode correspondant :

```python
VOLTAGE_SENSOR_MODE = "adc"
ADC_VOLTAGE_PIN = 35
ADC_VOLTAGE_SCALE = 1.0
```

ou :

```python
CURRENT_SENSOR_MODE = "ina219"
VOLTAGE_SENSOR_MODE = "ina219"
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

La supervision backend/Grafana reçoit ensuite :

- température DHT22 ;
- humidité DHT22 ;
- courant SEN0214 publié dans le champ MQTT `current` ;
- tension fixe de prototype publiée dans `voltage` ;
- puissance et énergie estimées ;
- état de serrure `lock` quand le relais est activé dans le firmware ;
- version firmware ESP32 ;
- adresse IP Wi-Fi ;
- adresse MAC.

Le rythme de publication reste adapté à l'état de l'emplacement :

- toutes les `5` secondes pendant une charge ou une attente de branchement ;
- toutes les `30` secondes lorsque l'emplacement est au repos ;
- immédiatement après un changement d'état important : commande UNLOCK, commande START, commande STOP ou événement physique du boîtier.
