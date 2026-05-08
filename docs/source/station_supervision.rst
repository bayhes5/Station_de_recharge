Supervision technique des stations
==================================

Cette page documente la supervision technique attendue pour exploiter les
stations : remontée des mesures, commandes vers les emplacements, suivi des
devices, alertes et visualisation Grafana. MQTT reste le protocole de transport
retenu, mais le besoin couvert est la surveillance opérationnelle des bornes.

Flux opérationnel
-----------------

Le flux normal de remontée capteurs est le suivant :

.. code-block:: text

   ESP32
      -> broker de messagerie Mosquitto
      -> bridge d'ingestion backend
      -> tâche Celery
      -> base TimescaleDB/PostgreSQL
      -> API Django / Grafana

Le flux de commande vers les emplacements passe dans l'autre sens :

.. code-block:: text

   API Django ou Raspberry
      -> broker de messagerie Mosquitto
      -> ESP32
      -> serrure / module de charge

Dans la version actuelle, le kiosque Raspberry expose aussi un endpoint local
``POST /mqtt/command``. Après une authentification réussie auprès de l'API, le
navigateur du kiosque appelle cet endpoint pour publier une commande ``START``
vers l'emplacement concerné.

Le serveur Django reste la source de vérité pour les utilisateurs, les
réservations et les droits d'accès. Les ESP32 exécutent les commandes validées et
gardent seulement les réflexes de sécurité locale : arrêt en cas d'ouverture du
boîtier, retrait du câble, surchauffe ou surconsommation.

Continuité en mode dégradé
--------------------------

Le fonctionnement nominal passe par le backend : validation de l'identité,
vérification de la réservation, contrôle de la station, création de la session,
journalisation et supervision. Ce chemin centralisé garantit la cohérence des
données et évite qu'un équipement local devienne seul responsable des décisions
d'accès.

La station doit néanmoins rester exploitable de façon limitée si le serveur ou
la liaison applicative tombe. Le mode dégradé repose sur deux mécanismes locaux :

* le Raspberry conserve un cache local des autorisations récemment synchronisées
  et encore valides, par station et par emplacement ;
* chaque ESP32 conserve localement les événements et mesures non transmis, par
  exemple dans LittleFS, afin de les republier après rétablissement de la
  communication.

Le cache Raspberry ne doit pas créer de nouveaux droits. Il ne sert qu'à
réutiliser des autorisations déjà émises par le backend, avec une durée de vie
courte, une portée limitée à la station et une liste d'actions autorisées. En
cas de doute, le comportement attendu est le refus d'accès plutôt que l'ouverture
non vérifiée.

Le journal local ESP32 protège la traçabilité : une coupure réseau ne doit pas
faire disparaître les mesures de charge, les arrêts de sécurité ou les alertes.
Au retour du réseau, les événements sont rejoués vers le backend, qui redevient
la source consolidée pour l'historique et Grafana.

Cette architecture est plus robuste qu'une communication directe Raspberry ->
ESP32 utilisée comme chemin principal. Une communication directe nominale
dupliquerait les règles métier dans le kiosque, rendrait la révocation des accès
plus difficile, réduirait l'audit centralisé et augmenterait le risque de
divergence entre stations. Le lien local reste donc un mécanisme de continuité,
pas une source d'autorité.

Services Docker
---------------

La stack locale contient les services de supervision suivants :

* ``mqtt`` : broker Mosquitto local, exposé sur le port ``1883`` ;
* ``redis`` : cache, broker Celery et support futur de Django Channels ;
* ``celery`` : worker de traitement asynchrone ;
* ``mqtt-bridge`` : consommateur backend abonné aux télémétries ESP32 ;
* ``grafana`` : supervision technique exposée sur ``http://localhost:3000`` ;
* ``db`` : TimescaleDB/PostgreSQL, compatible avec les modèles Django existants.

Canaux de télémétrie et de commande
-----------------------------------

Les ESP32 publient leur télémétrie sur :

.. code-block:: text

   station/<slot_id>/telemetry

Exemple de message :

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

Le message de commande est un JSON simple :

.. code-block:: json

   {
     "action": "START",
     "session_id": "<uuid-session>"
   }

Le Raspberry publie ce message via son client de messagerie local. Le backend
dispose du même mécanisme côté serveur avec la commande ``send_slot_command``.

Commandes utiles
----------------

Afficher l'etat des services de supervision :

.. code-block:: bash

   docker compose ps mqtt mqtt-bridge celery grafana db
   docker compose logs --tail=100 mqtt
   docker compose logs --tail=100 mqtt-bridge
   docker compose logs --tail=100 celery
   docker compose logs --tail=100 grafana

Lancer le bridge d'ingestion backend hors Docker :

.. code-block:: bash

   python manage.py run_mqtt_bridge

Relancer le bridge d'ingestion dans Docker :

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

Ecouter les messages publies sur les canaux de la station :

.. code-block:: bash

   docker compose exec mqtt mosquitto_sub -h localhost -t 'station/#' -v -C 5 -W 10

Publier une telemetrie de test sans ESP32 :

.. code-block:: bash

   docker compose exec mqtt mosquitto_pub -h localhost -t 'station/slot1/telemetry' -m '{"state":"charging","current":1.2,"voltage":12.0,"temperature":32.5,"humidity":45,"door":true,"cable":true}'

Verifier que Django et la base repondent :

.. code-block:: bash

   docker compose exec backend python manage.py check
   docker compose exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select now();"'

Simulateur local de télémétrie
------------------------------

Wokwi peut rester de cote pendant le developpement de la supervision. Le projet
contient une commande Django capable de publier des donnees capteurs realistes
sur les memes canaux que les ESP32 :

.. code-block:: powershell

   cd backend
   ..\.venv\Scripts\python.exe manage.py simulate_mqtt_telemetry --slots slot1 slot2 slot3 --scenario mixed --interval 2

La commande publie sur ``station/<slot_id>/telemetry`` et utilise les variables
``MQTT_HOST``, ``MQTT_PORT`` et ``MQTT_BASE_TOPIC``. Le scenario ``mixed`` alterne
des mesures normales et des anomalies pour tester la chaîne d'alertes :

* intrusion : boitier ouvert pendant une charge ;
* cable retire ;
* surchauffe ;
* surconsommation ;
* etat critique.

Pour envoyer seulement quelques messages et verifier le format sans broker :

.. code-block:: powershell

   cd backend
   ..\.venv\Scripts\python.exe manage.py simulate_mqtt_telemetry --count 3 --dry-run

Avec Docker, le simulateur est disponible dans un profil dedie pour ne pas le
lancer par defaut :

.. code-block:: bash

   docker compose up -d mqtt
   docker compose --profile simulation run --rm mqtt-simulator

Le simulateur tourne en conteneur ephemere. A l'arret, Docker le supprime
automatiquement ; il ne garde donc pas de reference vers un reseau Compose
supprime apres un rebuild.

Si Docker signale encore ``network ... not found`` pour un ancien conteneur
arrete, supprimer uniquement le simulateur puis relancer la commande ephemere :

.. code-block:: bash

   docker compose rm -sf mqtt-simulator
   docker compose up -d mqtt
   docker compose --profile simulation run --rm mqtt-simulator

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

Le dossier ``esp32/wokwi/`` contient une simulation interactive de l'emplacement
1. Elle publie les mêmes messages que le firmware MicroPython physique sur
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

L'ingestion des télémétries alimente actuellement :

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

* ``intrusion`` : ``door`` repasse a ``true`` ou l'emplacement n'est plus en charge ;
* ``cable_removed`` : ``cable`` repasse a ``true`` ou l'emplacement n'est plus en
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

* la température par emplacement ;
* le courant de charge ;
* les alertes récentes ;
* l'état des ESP32.

Cette supervision technique complète l'interface web métier. L'application web
reste destinée aux utilisateurs, administrateurs et techniciens ; Grafana sert à
visualiser rapidement les séries temporelles et les incidents techniques.

Sécurité prévue
---------------

La configuration de développement accepte la messagerie IoT sans authentification
pour faciliter les essais locaux. Pour une version de production, il faudra
activer progressivement :

* identifiants MQTT par équipement ;
* TLS côté broker ;
* segmentation réseau entre utilisateurs, serveur, Raspberry et ESP32 ;
* limitation stricte des commandes acceptées par chaque emplacement ;
* journalisation des commandes sensibles.
