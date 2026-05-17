Contrat Raspberry Pi et ESP32
=============================

Cette page fixe le contrat d'échange entre le kiosque Raspberry Pi, le broker
Mosquitto local et les ESP32 installés dans les emplacements de charge. Elle
sert de référence commune pour le firmware MicroPython, le kiosque tactile, les
tests simulateur et la supervision.

Principes
---------

* Le Raspberry reste l'orchestrateur local de la borne : il valide l'accès avec
  le backend ou le cache dégradé, puis publie les commandes physiques.
* Chaque ESP32 contrôle un seul emplacement : serrure, relais, DHT22, INA219,
  état câble et état boîtier.
* Le backend ingère la télémétrie et les ACK via le bridge MQTT, mais ne doit
  pas être nécessaire pour couper localement une charge dangereuse.
* En production, ``MQTT_ACK_REQUIRED`` doit être activé sur le Raspberry.

Topics
------

Le format production est structuré par station, borne et emplacement :

.. code-block:: text

   station/<mqtt_prefix>/<slot_id>/cmd
   station/<mqtt_prefix>/<slot_id>/ack
   station/<mqtt_prefix>/<slot_id>/status
   station/<mqtt_prefix>/<slot_id>/telemetry
   station/<mqtt_prefix>/<slot_id>/alert

Exemple avec ``mqtt_prefix=station-demo/borne-1`` et ``slot_id=slot1`` :

.. code-block:: text

   station/station-demo/borne-1/slot1/cmd
   station/station-demo/borne-1/slot1/telemetry

Le format historique ``station/<slot_id>/...`` reste accepté pour les tests
locaux, mais le format structuré doit être privilégié pour la production.

Commande START
--------------

Le Raspberry publie ``START`` après validation de l'accès et création de la
session backend ou locale.

.. code-block:: json

   {
     "command_id": "cmd-start-001",
     "action": "START",
     "issued_at": "2026-05-17T14:00:00+00:00",
     "session_id": "d4b8b4d1-8b67-45e7-aef6-0123456789ab",
     "station": "Station Demo",
     "borne": "Borne 1",
     "emplacement": "1",
     "source": "raspberry"
   }

Comportement attendu côté ESP32 :

* refuser la commande si une charge est déjà active sur l'emplacement ;
* vérifier que la serrure et le relais peuvent être commandés ;
* répondre par ACK avec le même ``command_id`` ;
* passer en ``reserved`` ou ``waiting_plug`` si l'accès est accepté ;
* passer en ``charging`` uniquement quand le câble est présent et le boîtier
  fermé.

Commande STOP
-------------

Le Raspberry publie ``STOP`` lorsqu'un utilisateur arrête la charge, lorsqu'une
session est clôturée ou lorsqu'une anomalie impose l'arrêt.

.. code-block:: json

   {
     "command_id": "cmd-stop-001",
     "action": "STOP",
     "issued_at": "2026-05-17T14:30:00+00:00",
     "session_id": "d4b8b4d1-8b67-45e7-aef6-0123456789ab",
     "station": "Station Demo",
     "borne": "Borne 1",
     "emplacement": "1",
     "source": "raspberry"
   }

Comportement attendu côté ESP32 :

* couper le relais de charge ;
* remettre l'emplacement dans un état sûr ;
* publier un ACK ``stopped`` ou ``idle`` ;
* continuer à publier ``status`` pour confirmer l'état physique.

ACK
---

Chaque commande doit produire un ACK sur ``.../<slot_id>/ack``.

.. code-block:: json

   {
     "command_id": "cmd-start-001",
     "action": "START",
     "status": "accepted",
     "session_id": "d4b8b4d1-8b67-45e7-aef6-0123456789ab",
     "message": "Emplacement réservé.",
     "source": "esp32",
     "timestamp": "2026-05-17T14:00:01Z"
   }

Statuts acceptés :

.. list-table::
   :header-rows: 1

   * - Action
     - Statuts confirmants
     - Statuts de refus
   * - ``START``
     - ``accepted``, ``reserved``, ``ready``, ``charging``, ``charging_started``
     - ``denied``, ``error``, ``failed``, ``fault``, ``rejected``
   * - ``STOP``
     - ``accepted``, ``stopped``, ``idle``
     - ``denied``, ``error``, ``failed``, ``fault``, ``rejected``

Le Raspberry ignore un ACK dont le ``command_id`` ou l'action ne correspond pas
à la commande en cours.

Status
------

Le status est un heartbeat métier léger.

.. code-block:: json

   {
     "state": "charging",
     "session_id": "d4b8b4d1-8b67-45e7-aef6-0123456789ab",
     "timestamp": "2026-05-17T14:01:00Z"
   }

États canoniques côté Raspberry :

.. code-block:: text

   reserved -> access_validated -> waiting_plug -> charging -> stopping -> stopped
                                      \                         /
                                       ---------- error --------

``waiting_cable`` est encore accepté en lecture comme alias historique de
``waiting_plug``.

Télémétrie
----------

La télémétrie est publiée régulièrement sur ``.../<slot_id>/telemetry``.

.. code-block:: json

   {
     "slot_id": "slot1",
     "session_id": "d4b8b4d1-8b67-45e7-aef6-0123456789ab",
     "state": "charging",
     "client_id": "esp32-slot1",
     "firmware_version": "1.0.0",
     "hardware_mac": "AA:BB:CC:DD:EE:FF",
     "ip_address": "192.168.1.42",
     "current": 1.35,
     "voltage": 41.7,
     "power": 56.3,
     "energy_kwh": 0.12,
     "temperature": 31.5,
     "humidity": 44.0,
     "door": true,
     "cable": true,
     "timestamp": "2026-05-17T14:02:00Z"
   }

Le backend crée une télémétrie de session uniquement si ``session_id`` correspond
à une session active de l'emplacement. Les données capteurs restent stockées
pour la supervision même si la session est absente ou invalide.

Les champs ``firmware_version``, ``hardware_mac`` et ``ip_address`` peuvent être
présents dans les messages ``status``, ``ack`` et ``telemetry``. Le backend les
utilise pour mettre à jour l'inventaire du ``Device`` associé au ``slot_id``.
``slot_id`` reste l'identifiant logique de l'emplacement ; ``hardware_mac`` est
l'identité physique de la carte ESP32.

Incidents attendus
------------------

.. list-table::
   :header-rows: 1

   * - Incident
     - Détection ESP32
     - Action locale attendue
     - Message backend
   * - Câble retiré
     - ``cable=false`` pendant ``charging``
     - couper le relais, publier ``alert`` et ``status``
     - alerte ``cable_removed``
   * - Boîtier ouvert
     - ``door=false`` pendant ``charging``
     - couper le relais, publier ``alert`` et ``status``
     - alerte ``intrusion``
   * - Surchauffe
     - ``temperature >= 60``
     - couper le relais si la charge est active
     - alerte ``overheat``
   * - Surintensité
     - ``current >= 3.0``
     - couper le relais si la charge est active
     - alerte ``overcurrent``
   * - État critique
     - ``state=error`` ou ``state=fault``
     - passer en état sûr
     - alerte ``state_error``

Tests de contrat
----------------

Les tests automatisés verrouillent déjà les points principaux :

* ``raspberry/tests/test_mqtt_client.py`` vérifie les topics, payloads START/STOP
  et ACK ;
* ``raspberry/tests/test_charge_state.py`` vérifie la machine d'état locale ;
* ``backend/api/tests/test_mqtt_ingestion.py`` vérifie l'ingestion des status,
  ACK, télémétries et alertes ;
* ``backend/api/tests/test_end_to_end_charge_flow.py`` vérifie le scénario QR
  mobile -> kiosque -> START -> télémétrie de l'emplacement réservé -> STOP.
