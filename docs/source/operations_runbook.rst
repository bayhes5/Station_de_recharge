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

Vérifier la santé applicative Django :

.. code-block:: bash

   curl http://localhost:8000/api/health/live/
   curl http://localhost:8000/api/health/ready/

``live`` confirme que le processus HTTP répond. ``ready`` confirme que l'API
peut utiliser la base de données, le cache et la configuration critique. Le
healthcheck Docker du service ``backend`` utilise ``ready``.

Vérifier la chaîne asynchrone :

.. code-block:: bash

   docker compose exec celery celery -A config inspect ping --timeout=3
   docker compose exec mqtt-bridge python manage.py check_mqtt_bridge_health

Le worker ``celery`` est considéré sain s'il répond au ping Celery. Le service
``mqtt-bridge`` écrit un heartbeat local tant qu'il est connecté au broker MQTT ;
le healthcheck échoue si ce heartbeat est absent ou trop ancien.

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

Scénario complet sans matériel
------------------------------

Le script ``scripts/run-demo-scenario.ps1`` joue un parcours de démonstration de
bout en bout sans ESP32 physique :

1. création d'une réservation QR sur la station de démonstration ;
2. création d'une session mobile de borne ;
3. connexion de l'utilisateur de démonstration ;
4. sélection et autorisation de la réservation ;
5. consommation par le kiosque ;
6. publication ``START`` vers le slot MQTT ;
7. simulation de télémétrie uniquement pour l'emplacement validé ;
8. publication ``STOP`` ;
9. clôture de session backend ;
10. résumé final reservation/session/device.

Lorsque la borne possède un ``mqtt_prefix``, le script et le simulateur utilisent
le topic structuré ``station/<mqtt_prefix>/<slot_id>/telemetry``. Cela valide le
routage production station/borne/emplacement au lieu de publier sur un simple
``station/<slot_id>/telemetry``.

Commande :

.. code-block:: powershell

   .\scripts\run-demo-scenario.ps1 -Reference DEMOQR1 -Emplacement 1 -TelemetryCount 5

Résultat attendu :

* réservation ``terminee`` ;
* session ``closed`` ;
* télémétrie attachée à la session ;
* device de l'emplacement revenu ``online`` ;
* aucune simulation parasite sur les autres emplacements.

Pour rejouer plus vite lorsque la stack est déjà lancée :

.. code-block:: powershell

   .\scripts\run-demo-scenario.ps1 -SkipDockerStart -TelemetryCount 3

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

Le dashboard Grafana à ouvrir en premier est ``Station - Vue globale supervision``.
Il permet ensuite d'accéder au détail ``Station - Supervision technique``.

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

Validation ACK sans matériel
----------------------------

Même sans ESP32 physique, le comportement de sécurité peut être validé : si
``MQTT_ACK_REQUIRED`` vaut ``true``, le kiosque doit refuser de considérer une
commande comme réussie lorsqu'aucun ACK n'arrive sur ``station/<slot_id>/ack``.

Test automatisé du client MQTT Raspberry :

.. code-block:: powershell

   .\.venv\Scripts\python.exe -m pytest raspberry\tests -q

Test manuel avec la stack Docker, sans ESP32 connecté :

.. code-block:: powershell

   $env:MQTT_ACK_REQUIRED="true"
   docker compose up -d --force-recreate raspberry
   curl -X POST http://localhost:9000/mqtt/command `
     -H "Content-Type: application/json" `
     -d '{"slot_id":"slot1","action":"START","session_id":"ack-test"}'

Résultat attendu :

* réponse HTTP ``503`` ;
* message indiquant l'absence de confirmation ESP32 ;
* aucune charge considérée comme réellement démarrée côté kiosque.

Revenir au mode de développement sans ESP32 :

.. code-block:: powershell

   $env:MQTT_ACK_REQUIRED="false"
   docker compose up -d --force-recreate raspberry

Sur une vraie borne, ``MQTT_ACK_REQUIRED`` doit rester à ``true``.

Sécurisation Mosquitto sans matériel
------------------------------------

Le broker de développement accepte les connexions anonymes pour faciliter les
tests locaux. Avant un déploiement terrain, préparer les comptes MQTT :

.. code-block:: powershell

   .\scripts\init-mqtt-auth.ps1

Le script crée ``mosquitto/config/passwords`` avec les comptes :

* ``station_backend`` ;
* ``raspberry_kiosk`` ;
* ``esp32_slot1`` ;
* ``esp32_slot2`` ;
* ``esp32_slot3``.

Activer ensuite ``mosquitto/config/mosquitto.secure.conf`` comme configuration
Mosquitto et redémarrer le service. Les règles dans ``mosquitto/config/acl``
doivent garantir qu'un ESP32 ne peut publier que sur son propre slot.

Contrôle recommandé avec Mosquitto sécurisé :

.. code-block:: bash

   docker compose exec mqtt mosquitto_pub -h localhost -u esp32_slot1 -P <mot-de-passe> -t station/slot1/status -m '{"state":"idle"}'
   docker compose exec mqtt mosquitto_pub -h localhost -u esp32_slot1 -P <mot-de-passe> -t station/slot2/status -m '{"state":"idle"}'

La première commande doit réussir, la seconde doit être refusée par l'ACL.

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

Contrôles de déploiement
------------------------

Avant une bascule vers un environnement exposé, exécuter les contrôles Django
avec les variables de production chargées :

.. code-block:: bash

   docker compose exec backend python manage.py check --deploy

Le contrôle doit rester sans erreur ``api.E``. Les avertissements ``api.W`` sont
à traiter avant ouverture du service hors réseau de développement : activer HSTS
après validation HTTPS, limiter ``ALLOWED_HOSTS``, configurer les identifiants
MQTT, chiffrer MQTT si le trafic sort du réseau local de confiance et remplacer
le mot de passe Grafana de démonstration.

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
