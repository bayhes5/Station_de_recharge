Supervision MQTT
================

Cette page documente le socle de supervision technique de la station. L'objectif
est de séparer clairement les décisions métier, la télémétrie IoT et
l'affichage de supervision.

Flux général
------------

Le flux normal de remontée capteurs est le suivant :

.. code-block:: text

   ESP32
      -> broker MQTT Mosquitto
      -> bridge MQTT backend
      -> tâche Celery
      -> base TimescaleDB/PostgreSQL
      -> API Django / Grafana

Le flux de commande vers les emplacements passe dans l'autre sens :

.. code-block:: text

   API Django ou Raspberry fallback
      -> broker MQTT Mosquitto
      -> ESP32
      -> serrure / module de charge

Dans le prototype actuel, le kiosque Raspberry expose aussi un endpoint local
``POST /mqtt/command``. Après une authentification réussie auprès de l'API, le
navigateur du kiosque appelle cet endpoint pour publier une commande ``START``
vers le slot concerné.

Le serveur Django reste la source de vérité pour les utilisateurs, les
réservations et les droits d'accès. Les ESP32 exécutent les commandes validées et
gardent seulement les réflexes de sécurité locale : arrêt en cas d'ouverture du
boîtier, retrait du câble, surchauffe ou surconsommation.

Services Docker
---------------

La stack locale contient les services de supervision suivants :

* ``mqtt`` : broker Mosquitto local, exposé sur le port ``1883`` ;
* ``redis`` : cache, broker Celery et support futur de Django Channels ;
* ``celery`` : worker de traitement asynchrone ;
* ``mqtt-bridge`` : client MQTT backend abonné aux télémétries ESP32 ;
* ``grafana`` : supervision technique exposée sur ``http://localhost:3000`` ;
* ``db`` : TimescaleDB/PostgreSQL, compatible avec les modèles Django existants.

Topics MQTT
-----------

Les ESP32 publient leur télémétrie sur :

.. code-block:: text

   station/<slot_id>/telemetry

Exemple de payload :

.. code-block:: json

   {
     "state": "charging",
     "current": 1.2,
     "voltage": 12.0,
     "energy_kwh": 0.04,
     "temperature": 32.5,
     "humidity": 45,
     "door": true,
     "cable": true,
     "timestamp": "2026-05-05T10:30:00Z"
   }

Les commandes vers un ESP32 utilisent :

.. code-block:: text

   station/<slot_id>/cmd

Le payload de commande est un JSON simple :

.. code-block:: json

   {
     "action": "START",
     "session_id": "<uuid-session>"
   }

Le Raspberry publie ce payload via son client MQTT local. Le backend dispose du
même mécanisme côté serveur avec la commande ``send_slot_command``.

Commandes utiles
----------------

Afficher l'etat des services de supervision :

.. code-block:: bash

   docker compose ps mqtt mqtt-bridge celery grafana db
   docker compose logs --tail=100 mqtt
   docker compose logs --tail=100 mqtt-bridge
   docker compose logs --tail=100 celery
   docker compose logs --tail=100 grafana

Lancer le bridge MQTT backend hors Docker :

.. code-block:: bash

   python manage.py run_mqtt_bridge

Relancer le bridge MQTT dans Docker :

.. code-block:: bash

   docker compose restart mqtt-bridge
   docker compose up -d --force-recreate mqtt-bridge

Envoyer une commande manuelle à un emplacement :

.. code-block:: bash

   python manage.py send_slot_command slot1 START --session-id <uuid-session>

Tester l'endpoint Raspberry local :

.. code-block:: bash

   curl -X POST http://localhost:9000/mqtt/command \
     -H "Content-Type: application/json" \
     -d '{"slot_id":"slot1","action":"START","session_id":"demo"}'

Ecouter les messages publies sur les topics de la station :

.. code-block:: bash

   docker compose exec mqtt mosquitto_sub -h localhost -t 'station/#' -v -C 5 -W 10

Publier une telemetrie de test sans ESP32 :

.. code-block:: bash

   docker compose exec mqtt mosquitto_pub -h localhost -t 'station/slot1/telemetry' -m '{"state":"charging","current":1.2,"voltage":12.0,"temperature":32.5,"humidity":45,"door":true,"cable":true}'

Verifier que Django et la base repondent :

.. code-block:: bash

   docker compose exec backend python manage.py check
   docker compose exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select now();"'

Simulateur MQTT local
---------------------

Wokwi peut rester de cote pendant le developpement de la supervision. Le projet
contient une commande Django capable de publier des donnees capteurs realistes
sur les memes topics que les ESP32 :

.. code-block:: powershell

   cd backend
   ..\.venv\Scripts\python.exe manage.py simulate_mqtt_telemetry --slots slot1 slot2 slot3 --scenario mixed --interval 2

La commande publie sur ``station/<slot_id>/telemetry`` et utilise les variables
``MQTT_HOST``, ``MQTT_PORT`` et ``MQTT_BASE_TOPIC``. Le scenario ``mixed`` alterne
des mesures normales et des anomalies pour tester la chaine d'alerting :

* intrusion : boitier ouvert pendant une charge ;
* cable retire ;
* surchauffe ;
* surconsommation ;
* etat critique.

Pour envoyer seulement quelques messages et verifier le format sans broker MQTT :

.. code-block:: powershell

   cd backend
   ..\.venv\Scripts\python.exe manage.py simulate_mqtt_telemetry --count 3 --dry-run

Avec Docker, le simulateur est disponible dans un profil dedie pour ne pas le
lancer par defaut :

.. code-block:: bash

   docker compose --profile simulation up -d mqtt-simulator
   docker compose logs -f mqtt-simulator

Si le simulateur ne redemarre pas apres une recreation de la stack et que Docker
signale ``network ... not found``, le conteneur arrete reference probablement un
ancien reseau Compose. Supprimer uniquement ce conteneur suffit :

.. code-block:: bash

   docker compose rm -f mqtt-simulator
   docker compose --profile simulation up -d mqtt-simulator

Pour comparer les reseaux attaches aux conteneurs :

.. code-block:: bash

   docker network ls
   docker inspect mqtt_simulator --format '{{json .NetworkSettings.Networks}}'
   docker inspect mqtt_broker --format '{{json .NetworkSettings.Networks}}'

La chaine locale recommandee pour valider la supervision sans ESP32 est donc :

.. code-block:: text

   simulate_mqtt_telemetry
      -> Mosquitto local
      -> mqtt-bridge backend
      -> Celery
      -> TimescaleDB/PostgreSQL
      -> API admin / Grafana

La chaîne a été vérifiée localement avec le simulateur Docker : le bridge reçoit
les messages, Celery les ingère, ``CapteurData`` reçoit des mesures récentes et
les alertes sont visibles dans l'API de supervision.

Simulation Wokwi
----------------

Le dossier ``esp32/wokwi/`` contient une simulation interactive du slot 1. Elle
publie les mêmes payloads que le firmware MicroPython physique sur
``station/slot1/telemetry``.

La simulation Wokwi utilise par défaut le broker public
``test.mosquitto.org``. Pour faire passer ces messages dans la stack locale et
les afficher dans Grafana, le bridge backend doit temporairement écouter ce même
broker :

.. code-block:: text

   MQTT_HOST=test.mosquitto.org
   MQTT_PORT=1883
   MQTT_BASE_TOPIC=station

La chaîne testée devient alors :

.. code-block:: text

   Wokwi ESP32
      -> test.mosquitto.org
      -> mqtt-bridge backend
      -> Celery
      -> TimescaleDB/PostgreSQL
      -> Grafana

Modèles alimentés
-----------------

L'ingestion MQTT alimente actuellement :

* ``Device`` : état courant et ``last_seen`` du device ESP32 ;
* ``Capteur`` et ``CapteurData`` : valeurs horodatées des capteurs ;
* ``SessionTelemetry`` : courant, tension et énergie si une session active
  existe sur l'emplacement ;
* ``Alerte`` : anomalies telles qu'intrusion, câble retiré, surchauffe ou
  surconsommation.

Les capteurs booleens ``door`` et ``cable`` sont stockes numeriquement dans
``CapteurData`` : ``1`` signifie vrai et ``0`` signifie faux. L'API de
supervision expose en plus un libelle lisible pour l'interface :
``Boitier ferme`` / ``Boitier ouvert`` et ``Cable present`` / ``Cable retire``.

Cycle des alertes
-----------------

Une anomalie detectee par la telemetrie cree une alerte au statut ``nouvelle``.
Si la meme anomalie continue sur une telemetrie suivante, l'alerte existante est
mise a jour au statut ``active`` au lieu de creer un doublon. Quand une
telemetrie normale confirme que la condition a disparu, l'alerte passe
automatiquement au statut ``resolue``.

Les conditions de resolution automatique sont :

* ``intrusion`` : ``door`` repasse a ``true`` ou le slot n'est plus en charge ;
* ``cable_removed`` : ``cable`` repasse a ``true`` ou le slot n'est plus en
  charge ;
* ``overheat`` : la temperature repasse sous ``60 C`` ;
* ``overcurrent`` : le courant repasse sous ``3.0 A`` ;
* ``state_error`` : l'etat n'est plus ``error``, ``emergency`` ou ``fault``.

Grafana
-------

Grafana est provisionné automatiquement avec une datasource PostgreSQL nommée
``Station TimescaleDB`` et un dashboard ``Station - Supervision technique``.
Le dashboard est accessible directement via :

.. code-block:: text

   http://localhost/grafana/d/station-supervision/station-supervision-technique?orgId=1&from=now-6h&to=now&refresh=5s

Le dashboard initial affiche :

* la température par slot ;
* le courant de charge ;
* les alertes récentes ;
* l'état des ESP32.

Cette supervision technique complète l'interface web métier. L'application web
reste destinée aux utilisateurs, administrateurs et techniciens ; Grafana sert à
visualiser rapidement les séries temporelles et les incidents techniques.

Sécurité prévue
---------------

La configuration de développement accepte MQTT sans authentification pour
faciliter la démonstration locale. Pour une version de production, il faudra
activer progressivement :

* identifiants MQTT par équipement ;
* TLS côté broker ;
* segmentation réseau entre utilisateurs, serveur, Raspberry et ESP32 ;
* limitation stricte des commandes acceptées par chaque slot ;
* journalisation des commandes sensibles.
