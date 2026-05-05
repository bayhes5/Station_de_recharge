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

Commandes utiles
----------------

Lancer le bridge MQTT backend hors Docker :

.. code-block:: bash

   python manage.py run_mqtt_bridge

Envoyer une commande manuelle à un emplacement :

.. code-block:: bash

   python manage.py send_slot_command slot1 START --session-id <uuid-session>

Modèles alimentés
-----------------

L'ingestion MQTT alimente actuellement :

* ``Device`` : état courant et ``last_seen`` du device ESP32 ;
* ``Capteur`` et ``CapteurData`` : valeurs horodatées des capteurs ;
* ``SessionTelemetry`` : courant, tension et énergie si une session active
  existe sur l'emplacement ;
* ``Alerte`` : anomalies telles qu'intrusion, câble retiré, surchauffe ou
  surconsommation.

Grafana
-------

Grafana est provisionné automatiquement avec une datasource PostgreSQL nommée
``Station TimescaleDB`` et un dashboard ``Station - Supervision technique``.

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
