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
* l'adresse du broker MQTT local du Raspberry ;
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
   MQTT_HOST = "192.168.1.10"  # IP du Raspberry Pi qui héberge Mosquitto
   MQTT_PORT = 1883
   MQTT_USER = "esp32_slot1"
   MQTT_PASSWORD = "mot-de-passe-mqtt"
   MQTT_BASE_TOPIC = "station"
   SLOT_ID = "slot1"
   CLIENT_ID = "esp32-slot1"

   DHT_PIN = 4
   INA219_SDA_PIN = 21
   INA219_SCL_PIN = 25
   LOCK_PIN = 23
   CHARGE_PIN = 22

L'emplacement démarre verrouillé. La serrure est ouverte uniquement lorsqu'une
commande ``START`` ou ``UNLOCK`` est reçue.

Déploiement avec Thonny
-----------------------

Procédure de test sur carte physique :

1. installer MicroPython sur l'ESP32 ;
2. ouvrir Thonny avec l'interpréteur MicroPython ESP32 ;
3. adapter ``WIFI_SSID``, ``WIFI_PASSWORD`` et ``MQTT_HOST`` ;
4. renseigner ``MQTT_USER`` et ``MQTT_PASSWORD`` si le broker sécurisé est actif ;
5. adapter ``SLOT_ID`` et ``CLIENT_ID`` pour l'emplacement ;
6. enregistrer ``esp32/emplacement1/main.py`` sur la carte sous le nom
   ``main.py`` ;
7. redémarrer la carte ;
8. vérifier les topics MQTT depuis le PC ou le Raspberry.

Commande d'écoute :

.. code-block:: bash

   docker compose exec mqtt mosquitto_sub -h localhost -t 'station/#' -v

En production, ``MQTT_HOST`` doit être l'adresse IP du Raspberry sur le réseau
Wi-Fi local de la borne. En développement, si l'ESP32 utilise le broker Docker
du PC, ``MQTT_HOST`` doit être l'adresse IP du PC sur le même réseau Wi-Fi, pas
``localhost``. Depuis un ESP32, ``localhost`` désigne l'ESP32 lui-même.

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

Pour une borne de production, ``MQTT_BASE_TOPIC`` peut être configuré avec un
préfixe plus précis, par exemple ``station/<station_id>/<borne_id>``. Les topics
deviennent alors ``station/<station_id>/<borne_id>/<slot_id>/telemetry`` et
``station/<station_id>/<borne_id>/<slot_id>/cmd``. Le firmware n'a pas besoin de
logique métier supplémentaire : il concatène toujours ``MQTT_BASE_TOPIC``,
``SLOT_ID`` et le suffixe.

Le backend retire le préfixe global ``station`` et compare la partie
``<station_id>/<borne_id>`` au champ ``mqtt_prefix`` de la borne. En production,
chaque borne doit donc avoir un ``mqtt_prefix`` stable, par exemple
``station-centre/borne-1``. Cela évite qu'un ``slot1`` publié par deux bornes
différentes soit rattaché au mauvais emplacement.

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
     "command_id": "même-valeur-que-la-commande",
     "action": "START",
     "status": "accepted",
     "message": "Emplacement reserve.",
     "state": "reserved",
     "slot_id": "slot1",
     "client_id": "esp32-slot1",
     "firmware_version": "1.0.0",
     "hardware_mac": "AA:BB:CC:DD:EE:FF",
     "ip_address": "192.168.1.42",
     "session_id": "<uuid-session>"
   }

Le Raspberry utilise cet ACK pour confirmer que l'ESP32 a bien reçu et appliqué
la commande. En production, une commande sans ACK doit être traitée comme un
échec opérationnel.

Un ACK doit reprendre le ``command_id`` et, si le champ ``action`` est présent,
il doit correspondre à l'action demandée. Côté Raspberry, un ACK reçu n'est
accepté comme confirmation que si son ``status`` est cohérent avec la commande :

* ``START`` : ``accepted``, ``reserved``, ``ready``, ``charging`` ou
  ``charging_started`` ;
* ``STOP`` : ``accepted``, ``stopped`` ou ``idle`` ;
* ``LOCK`` : ``accepted`` ou ``locked`` ;
* ``UNLOCK`` : ``accepted`` ou ``unlocked``.

Les statuts ``error``, ``rejected``, ``denied``, ``failed`` et ``fault`` doivent
être réservés aux refus explicites. Ils bloquent le parcours kiosk même en mode
développement.

Le backend ingère également les ACK via le bridge MQTT. Le dernier
acquittement connu est conservé sur le ``Device`` pour la supervision :
identifiant de commande, action, statut, message lisible et horodatage. Cette
trace ne remplace pas les statuts ``reserved`` ou ``charging_started`` ; elle
sert à prouver que l'ordre ``START``, ``STOP``, ``LOCK`` ou ``UNLOCK`` a été reçu
par l'ESP32.

Machine d'état
--------------

Les états embarqués restent volontairement simples. Ils décrivent uniquement
l'état physique de l'emplacement, pas la décision métier de réservation :

.. code-block:: text

   idle      : emplacement au repos
   reserved  : accès autorisé, attente câble + boîtier fermé
   charging  : relais de charge actif

Transitions principales :

* ``START`` fait passer de ``idle`` à ``reserved`` ;
* câble présent et boîtier fermé font passer de ``reserved`` à ``charging`` ;
* ``STOP`` ou une anomalie font revenir à ``idle``.

Le Raspberry maintient en parallèle une machine d'état locale plus explicite
(``reserved``, ``access_validated``, ``waiting_plug``, ``charging``,
``stopping``, ``stopped``, ``error``). Elle évite les doubles commandes et
signale les états douteux côté kiosk. L'ESP32 reste responsable des sécurités
immédiates : relais, serrure, câble, boîtier, courant et température.

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
     "client_id": "esp32-slot1",
     "firmware_version": "1.0.0",
     "hardware_mac": "AA:BB:CC:DD:EE:FF",
     "ip_address": "192.168.1.42",
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

Les champs d'inventaire sont publiés automatiquement par le firmware :

* ``slot_id`` identifie l'emplacement logique et le topic MQTT ;
* ``hardware_mac`` identifie la carte ESP32 physique ;
* ``ip_address`` décrit l'adresse Wi-Fi courante ;
* ``firmware_version`` permet au backend de détecter une version non conforme
  avec ``EXPECTED_ESP32_FIRMWARE_VERSION``.

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
