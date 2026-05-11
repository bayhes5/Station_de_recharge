Firmware ESP32
==============

Chaque emplacement de recharge est piloté par un ESP32 connecté au réseau Wi-Fi
local. L'ESP32 ne connaît pas les règles métier de réservation : il reçoit des
commandes déjà validées, applique les sécurités physiques et publie la
télémétrie.

Périmètre matériel
------------------

Le firmware de référence se trouve dans ``esp32/emplacement1/main.py``. Il sert
de base pour les trois emplacements en changeant uniquement :

* ``SLOT_ID`` ;
* ``CLIENT_ID`` ;
* les identifiants Wi-Fi ;
* l'adresse du broker MQTT ;
* les pins réels des capteurs, relais et serrure.

Le code cible actuellement :

* un relais de charge ;
* une sortie de serrure ;
* un contact de boîtier ;
* un détecteur de présence câble ;
* un DHT22 pour température et humidité ;
* un INA219 pour courant, tension et puissance.

Configuration minimale
----------------------

Extrait de configuration :

.. code-block:: python

   WIFI_SSID = "WIFI_SSID"
   WIFI_PASSWORD = "WIFI_PASSWORD"
   MQTT_HOST = "192.168.1.10"
   MQTT_PORT = 1883
   MQTT_BASE_TOPIC = "station"
   SLOT_ID = "slot1"
   CLIENT_ID = "esp32-slot1"

   DHT_PIN = 4
   INA219_SDA_PIN = 21
   INA219_SCL_PIN = 25
   LOCK_PIN = 23
   CHARGE_PIN = 22
   BOOT_UNLOCKED = False

``BOOT_UNLOCKED = False`` signifie que l'emplacement démarre verrouillé. La
serrure est ouverte uniquement lorsqu'une commande ``START`` ou ``UNLOCK`` est
reçue.

Déploiement avec Thonny
-----------------------

Procédure de test sur carte physique :

1. installer MicroPython sur l'ESP32 ;
2. ouvrir Thonny avec l'interpréteur MicroPython ESP32 ;
3. adapter ``WIFI_SSID``, ``WIFI_PASSWORD`` et ``MQTT_HOST`` ;
4. adapter ``SLOT_ID`` et ``CLIENT_ID`` pour l'emplacement ;
5. enregistrer ``esp32/emplacement1/main.py`` sur la carte sous le nom
   ``main.py`` ;
6. redémarrer la carte ;
7. vérifier les topics MQTT depuis le PC.

Commande d'écoute :

.. code-block:: bash

   docker compose exec mqtt mosquitto_sub -h localhost -t 'station/#' -v

Si l'ESP32 utilise le broker Docker du PC, ``MQTT_HOST`` doit être l'adresse IP
du PC sur le même réseau Wi-Fi, pas ``localhost``.

Topics MQTT
-----------

Topics publiés par l'ESP32 :

.. code-block:: text

   station/<slot_id>/ack
   station/<slot_id>/telemetry
   station/<slot_id>/status
   station/<slot_id>/alert

Topic écouté par l'ESP32 :

.. code-block:: text

   station/<slot_id>/cmd

Commandes acceptées
-------------------

Payload de commande :

.. code-block:: json

   {
     "command_id": "uuid-ou-token-court",
     "action": "START",
     "session_id": "<uuid-session>"
   }

Actions :

``START``
   Déverrouille l'emplacement, coupe le relais par sécurité, passe en état
   ``reserved`` et attend câble présent + boîtier fermé avant de démarrer la
   charge.

``STOP``
   Arrête la charge, déverrouille et publie un statut d'arrêt.

``LOCK``
   Verrouille l'emplacement.

``UNLOCK``
   Déverrouille l'emplacement.

ACK de commande
---------------

Chaque commande doit produire un acquittement :

.. code-block:: json

   {
     "command_id": "meme-valeur-que-la-commande",
     "action": "START",
     "status": "accepted",
     "message": "Emplacement reserve.",
     "state": "reserved",
     "slot_id": "slot1",
     "session_id": "<uuid-session>"
   }

Le Raspberry utilise cet ACK pour confirmer que l'ESP32 a bien reçu et appliqué
la commande. En production, une commande sans ACK doit être traitée comme un
échec opérationnel.

Machine d'état
--------------

Les états embarqués restent volontairement simples :

.. code-block:: text

   idle      : emplacement au repos
   reserved  : accès autorisé, attente câble + boîtier fermé
   charging  : relais de charge actif

Transitions principales :

* ``START`` fait passer de ``idle`` à ``reserved`` ;
* câble présent et boîtier fermé font passer de ``reserved`` à ``charging`` ;
* ``STOP`` ou une anomalie font revenir à ``idle``.

Sécurités locales
-----------------

Pendant ``charging``, l'ESP32 arrête la charge si :

* le boîtier est ouvert ;
* le câble est retiré ;
* le courant dépasse ``MAX_CURRENT_A`` ;
* la température dépasse ``MAX_TEMPERATURE_C``.

Ces règles doivent rester locales. Elles ne doivent pas attendre une réponse du
backend, car elles protègent l'utilisateur, le matériel et la traçabilité en cas
de coupure réseau.

Télémétrie capteurs
-------------------

Payload publié sur ``station/<slot_id>/telemetry`` :

.. code-block:: json

   {
     "slot_id": "slot1",
     "session_id": "<uuid-session>",
     "state": "charging",
     "current": 1.42,
     "voltage": 42.1,
     "power": 59.78,
     "energy_kwh": 0.0,
     "temperature": 31.5,
     "humidity": 45.0,
     "door": true,
     "cable": true
   }

Le firmware lit le DHT22 et l'INA219 lorsque les capteurs répondent. Si un
capteur est absent pendant le développement, le firmware publie des valeurs
simulées afin de tester immédiatement la chaîne MQTT, l'ingestion backend et
Grafana.

Chaîne de supervision
---------------------

La télémétrie ESP32 suit ce chemin :

1. publication MQTT par l'ESP32 ;
2. réception par Mosquitto ;
3. consommation par ``mqtt-bridge`` ;
4. tâche Celery ``api.process_mqtt_message`` ;
5. stockage dans ``Device``, ``CapteurData`` et éventuellement
   ``SessionTelemetry`` ;
6. lecture par l'API admin et Grafana.

Pour tester sans ESP32 physique :

.. code-block:: bash

   docker compose up -d backend mqtt mqtt-bridge celery grafana
   docker compose run --rm mqtt-simulator python manage.py simulate_mqtt_telemetry --slots slot1 --scenario normal --interval 1 --count 5

Vérifier le stockage :

.. code-block:: bash

   docker compose exec backend python manage.py shell -c "from api.models import CapteurData; print(CapteurData.objects.count())"

Simulation Wokwi
----------------

Le dossier ``esp32/wokwi/`` permet de tester la logique sans matériel. Il publie
les mêmes champs que le firmware physique et accepte les mêmes commandes MQTT.

En local, privilégier le broker Docker du projet pour valider toute la chaîne
avec Grafana. Le broker public ``test.mosquitto.org`` reste utile pour une
démonstration isolée, mais il ne doit pas être utilisé comme dépendance de
production.

Limites actuelles
-----------------

Le firmware est prêt pour les tests d'intégration, mais certains points doivent
être validés sur le matériel final :

* sens électrique réel des contacts ``door`` et ``cable`` ;
* polarité de la serrure ;
* calibration INA219 selon le shunt ;
* seuils réels de courant et température ;
* stratégie de reconnexion Wi-Fi/MQTT longue durée ;
* journal local LittleFS pour événements non transmis.
