Runbook d'exploitation locale
=============================

Ce runbook regroupe les commandes utiles pour démarrer, vérifier et diagnostiquer
la station en environnement de développement ou de démonstration.

Démarrage standard
------------------

Copier la configuration locale :

.. code-block:: powershell

   Copy-Item .env.example .env

Démarrer la stack :

.. code-block:: bash

   docker compose up -d --build

Vérifier les services :

.. code-block:: bash

   docker compose ps

Services attendus pour une démonstration complète :

* ``backend`` ;
* ``frontend`` ;
* ``raspberry`` ;
* ``mqtt`` ;
* ``mqtt-bridge`` ;
* ``celery`` ;
* ``redis`` ;
* ``db`` ;
* ``grafana`` ;
* ``reverse-proxy``.

URLs utiles
-----------

Via Nginx :

.. code-block:: text

   https://localhost/          frontend
   https://localhost/api/      API Django
   https://localhost/admin/    admin Django
   https://localhost/kiosk/    kiosque Raspberry
   https://localhost/grafana/  Grafana

Ports directs :

.. code-block:: text

   8000  Django
   5173  Vite
   9000  kiosque Raspberry
   3000  Grafana
   1883  Mosquitto
   5432  PostgreSQL/TimescaleDB

Supervision MQTT et Grafana
---------------------------

Démarrer les services nécessaires à la supervision :

.. code-block:: bash

   docker compose up -d mqtt mqtt-bridge celery grafana

Publier cinq mesures simulées :

.. code-block:: bash

   docker compose run --rm mqtt-simulator python manage.py simulate_mqtt_telemetry --slots slot1 --scenario normal --interval 1 --count 5

Vérifier que les messages passent sur MQTT :

.. code-block:: bash

   docker compose exec mqtt mosquitto_sub -h localhost -t 'station/#' -v -C 10 -W 10

Vérifier que les mesures sont stockées :

.. code-block:: bash

   docker compose exec backend python manage.py shell -c "from api.models import CapteurData; from django.db.models import Count; print(list(CapteurData.objects.values('capteur__type').annotate(n=Count('id_data')).order_by('capteur__type')))"

Les types attendus sont :

* ``temperature`` ;
* ``humidity`` ;
* ``current`` ;
* ``voltage`` ;
* ``power`` ;
* ``door`` ;
* ``cable``.

Le dashboard Grafana à ouvrir est ``Station - Supervision technique``.

Diagnostic du bridge MQTT
-------------------------

Si les messages sont visibles sur MQTT mais pas en base :

1. vérifier que ``mqtt-bridge`` tourne ;
2. vérifier que ``celery`` tourne ;
3. lire les logs des deux services ;
4. republier une télémétrie de test.

Commandes :

.. code-block:: bash

   docker compose ps mqtt mqtt-bridge celery redis db
   docker compose logs --tail=100 mqtt-bridge
   docker compose logs --tail=100 celery
   docker compose restart mqtt-bridge celery

Le bridge reçoit les messages et les met en file. Celery exécute réellement
l'ingestion et écrit en base.

Test de commande ESP32
----------------------

Envoyer une commande via le Raspberry :

.. code-block:: bash

   curl -X POST http://localhost:9000/mqtt/command \
     -H "Content-Type: application/json" \
     -d '{"slot_id":"slot1","action":"START","session_id":"demo"}'

Observer les topics :

.. code-block:: bash

   docker compose exec mqtt mosquitto_sub -h localhost -t 'station/#' -v -C 5 -W 10

En présence d'un ESP32 réel, on doit voir :

* la commande sur ``station/slot1/cmd`` ;
* l'ACK sur ``station/slot1/ack`` ;
* les statuts sur ``station/slot1/status`` ;
* la télémétrie périodique sur ``station/slot1/telemetry``.

Test RFID Raspberry
-------------------

Sans lecteur physique :

.. code-block:: bash

   curl -X POST http://localhost:9000/rfid/scan \
     -H "Content-Type: application/json" \
     -d '{"uid":"04A3BC89F2"}'

Avec ACR122U sur Raspberry :

.. code-block:: bash

   sudo apt install pcscd pcsc-tools python3-dev swig
   sudo systemctl enable --now pcscd
   pcsc_scan

Variables à définir sur le Raspberry :

.. code-block:: bash

   export RFID_READER_BACKEND=acr122u
   export BACKEND_API_BASE_URL=http://<ip-pc>:8000/api
   export MQTT_HOST=<ip-pc>
   export TERMINAL_API_SECRET=<secret-du-.env>

Mode dégradé
------------

Forcer une synchronisation du cache :

.. code-block:: bash

   curl -X POST http://localhost:9000/offline/sync

Lire l'état local :

.. code-block:: bash

   curl http://localhost:9000/offline/status

Rejouer les événements offline :

.. code-block:: bash

   curl -X POST http://localhost:9000/offline/events/sync

Le mode dégradé n'est pas un mode autonome complet. Il sert uniquement à
réutiliser des droits déjà synchronisés et encore valides si le backend devient
temporairement indisponible.

Tests automatisés
-----------------

Tests backend ciblés télémétrie :

.. code-block:: bash

   docker compose run --rm backend-test python -m pytest api/tests/test_mqtt_ingestion.py api/tests/test_mqtt_simulator.py

Tests terminal et accès :

.. code-block:: bash

   docker compose run --rm backend-test python -m pytest api/tests/test_terminal_auth.py

Vérification syntaxe ESP32 :

.. code-block:: powershell

   python -m py_compile esp32\emplacement1\main.py esp32\wokwi\main.py

Documentation
-------------

Construire la documentation :

.. code-block:: powershell

   .\docs\make.bat html

Si ``sphinx-build`` n'est pas dans le ``PATH`` :

.. code-block:: powershell

   $env:DEBUG="True"
   $env:SECRET_KEY="docs-local-secret-key-not-for-production"
   .\.venv\Scripts\python.exe -m sphinx -b html docs\source docs\build\html

Contrôles avant démonstration
-----------------------------

Avant une présentation, vérifier :

* une réservation de test existe ;
* le backend est joignable depuis le Raspberry ;
* le broker MQTT est joignable depuis le Raspberry et les ESP32 ;
* ``mqtt-bridge`` et ``celery`` sont lancés pour alimenter Grafana ;
* le dashboard Grafana affiche des points récents ;
* le lecteur RFID lit bien un UID ;
* l'ESP32 répond aux commandes avec un ACK.
