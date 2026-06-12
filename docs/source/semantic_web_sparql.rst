Web sémantique et SPARQL
========================

Cette page décrit la couche web sémantique ajoutée au projet en phase de
développement. Elle ne remplace pas Django, PostgreSQL, TimescaleDB, MQTT ou
Grafana. Elle fournit une vue RDF/SPARQL de lecture, filtrée et contrôlée, pour
relier les objets métier dans un graphe de connaissances.

Positionnement
--------------

Le cœur du système reste :

* Django et Django REST Framework pour la logique métier ;
* PostgreSQL et TimescaleDB pour la persistance, les transactions et les séries
  temporelles ;
* MQTT pour les échanges backend, Raspberry et ESP32 ;
* Celery pour les traitements asynchrones ;
* Grafana pour la supervision opérationnelle.

SPARQL ne doit pas valider une authentification, ouvrir une serrure, démarrer
une charge, arrêter une session ou envoyer une commande ESP32. Ces actions
restent dans le backend et dans le contrat MQTT.

Le rôle de SPARQL est différent : il sert à interroger des relations métier
transversales, par exemple :

* quelles stations ont des alertes critiques ouvertes ;
* quels ESP32 ont un firmware obsolète ;
* quels emplacements sont en charge sans télémétrie récente ;
* quels techniciens sont responsables des stations concernées.

Architecture mise en place
--------------------------

::

   PostgreSQL / TimescaleDB
       -> modèles Django
       -> export RDF filtré
       -> endpoint SPARQL de développement
       -> requêtes d'analyse / démonstration

Le graphe RDF est généré à partir des modèles Django dans
``backend/api/services/semantic_graph.py``.

Deux usages sont disponibles :

* export fichier avec la commande ``export_semantic_graph`` ;
* interrogation HTTP en développement avec ``/api/semantic/graph/`` et
  ``/api/semantic/sparql/``.
* visualisation graphique avec ``/semantic-graph.html`` côté frontend.

Endpoints de développement
--------------------------

Les endpoints sont désactivés par défaut. Ils doivent être activés uniquement en
développement ou en démonstration :

.. code-block:: text

   SEMANTIC_DEV_ENDPOINTS_ENABLED=True

Routes disponibles :

.. list-table::
   :header-rows: 1

   * - Route
     - Usage
   * - ``GET /api/semantic/graph/?format=turtle``
     - Exporte le graphe en Turtle
   * - ``GET /api/semantic/graph/?format=json-ld``
     - Exporte le graphe en JSON-LD
   * - ``POST /api/semantic/sparql/``
     - Exécute une requête SPARQL de lecture
   * - ``GET /api/semantic/network/``
     - Expose un graphe JSON simplifié pour l'interface graphique

Ces routes sont réservées aux comptes administrateurs Django. Les requêtes
SPARQL de modification, comme ``INSERT`` ou ``DELETE``, sont refusées.

Visualisation graphique
-----------------------

Une page de développement est disponible côté frontend :

::

   /semantic-graph.html

Elle affiche le graphe métier sous forme de nœuds et de relations :

* station ;
* borne ;
* emplacement ;
* contrôleur ESP32 ;
* capteur ;
* session active ;
* alerte ;
* technicien.

La page ne consomme pas directement le Turtle RDF. Elle utilise
``GET /api/semantic/network/``, qui transforme le graphe métier en une structure
plus lisible pour l'interface :

.. code-block:: json

   {
     "nodes": [
       {"id": "station:...", "label": "Station Demo", "type": "station"},
       {"id": "borne:...", "label": "Borne 1", "type": "borne"}
     ],
     "edges": [
       {"from": "station:...", "to": "borne:...", "label": "contient"}
     ]
   }

Cette séparation est volontaire :

* RDF/SPARQL reste la couche standardisée et interopérable ;
* la page graphique reste une vue humaine, plus adaptée à la soutenance et à
  l'exploration rapide du système.

Commande d'export
-----------------

La commande suivante génère un fichier RDF Turtle :

.. code-block:: console

   python manage.py export_semantic_graph

Export dans un format précis :

.. code-block:: console

   python manage.py export_semantic_graph --format json-ld --output semantic/exports/station-recharge.jsonld

L'export par défaut est écrit dans :

::

   semantic/exports/station-recharge.ttl

Modèle RDF
----------

Hiérarchie physique retenue :

::

   Station
     -> Borne
       -> Emplacement
         -> ESP32
           -> Capteurs

Classes principales :

.. list-table::
   :header-rows: 1

   * - Classe RDF
     - Description
   * - ``station:ChargingStation``
     - Station de recharge
   * - ``station:ChargingCabinet``
     - Borne ou armoire rattachée à une station
   * - ``station:ChargingSlot``
     - Emplacement de charge
   * - ``station:EmbeddedDevice``
     - ESP32 ou équipement embarqué
   * - ``sosa:Sensor``
     - Capteur physique
   * - ``sosa:Observation``
     - Dernière mesure connue d'un capteur
   * - ``station:ChargingSession``
     - Session effective de charge
   * - ``station:OperationalAlert``
     - Alerte de supervision
   * - ``station:Technician``
     - Technicien affecté à une station

Fichiers ajoutés :

* ``semantic/ontology/station-recharge.ttl`` : ontologie locale minimale ;
* ``semantic/queries/firmware_temperature_technician.rq`` : exemple firmware,
  température et technicien ;
* ``semantic/queries/active_sessions_without_recent_telemetry.rq`` : sessions
  actives sans télémétrie ;
* ``semantic/queries/open_alerts_by_technician.rq`` : alertes critiques par
  technicien.

Protection des données
----------------------

Le graphe RDF est volontairement filtré. Il exporte des données techniques et
opérationnelles, mais pas les secrets ni les données personnelles inutiles.

Données exportées :

* stations, bornes et emplacements ;
* statut des emplacements et état de serrure ;
* ESP32, adresse IP, MAC matérielle, firmware, dernier état connu ;
* capteurs et dernière mesure connue ;
* sessions actives avec identifiant pseudonymisé ;
* alertes ouvertes ;
* affectations technicien/station.

Données exclues :

* mots de passe et hash de mots de passe ;
* tokens JWT ;
* secrets QR ;
* codes SMS ;
* UID RFID ;
* emails et téléphones des utilisateurs finaux ;
* coordonnées personnelles non nécessaires.

Les sessions sont référencées avec un identifiant pseudonymisé par HMAC côté
backend. Cela permet de lier une session technique à ses relations RDF sans
publier directement l'identifiant interne de session.

Comparaison avec SQL
--------------------

Une base relationnelle peut déjà répondre à beaucoup de questions complexes.
Dans ce projet, PostgreSQL reste même le bon choix pour les usages critiques :
réservations, transactions, permissions, sessions, intégrité et performances.

Exemple de question :

::

   Donne-moi les emplacements en charge, dont l'ESP32 a un firmware obsolète,
   avec une température supérieure au seuil, et le technicien responsable.

Cette question est possible en SQL avec des jointures entre stations, bornes,
emplacements, devices, capteurs, mesures et techniciens. La limite n'est donc
pas la capacité de SQL. La limite apparaît quand on veut intégrer des sources
hétérogènes ou exprimer les relations métier dans un vocabulaire commun :
référentiel bâtiment, ville connectée, météo, autre modèle de station ou autre
plateforme IoT.

La bonne séparation est donc :

.. list-table::
   :header-rows: 1

   * - Besoin
     - Technologie adaptée
   * - Réservation et validation d'accès
     - Django, API REST et PostgreSQL
   * - Télémétrie temporelle
     - PostgreSQL, TimescaleDB et Grafana
   * - Commandes ESP32
     - MQTT et backend Django
   * - Interopérabilité, graphe de connaissances et analyse transversale
     - RDF et SPARQL

Exemple SPARQL
--------------

Requête de démonstration :

.. code-block:: sparql

   PREFIX station: <https://station-recharge.local/ontology#>
   PREFIX sosa: <http://www.w3.org/ns/sosa/>

   SELECT ?stationName ?cabinetName ?slotNumber ?device ?firmware ?expected ?temperature ?technician
   WHERE {
     ?station a station:ChargingStation ;
              station:name ?stationName ;
              station:hasCabinet ?cabinet ;
              station:hasTechnician ?technicianResource .

     ?technicianResource station:name ?technician .

     ?cabinet station:name ?cabinetName ;
              station:hasSlot ?slot .

     ?slot station:number ?slotNumber ;
           station:status "occupe" ;
           station:hostsDevice ?device .

     ?device station:firmwareVersion ?firmware ;
             station:expectedFirmwareVersion ?expected ;
             station:firmwareStatus "update_required" ;
             station:hasSensor ?sensor .

     ?sensor station:sensorType "temperature" ;
             station:latestObservation ?observation .

     ?observation sosa:hasSimpleResult ?temperature .

    FILTER (?temperature >= 28)
   }
   ORDER BY DESC(?temperature)

Réponse courte pour la soutenance
---------------------------------

PostgreSQL sait répondre à ces questions avec des jointures SQL, et c'est la
bonne solution pour le cœur opérationnel. Le web sémantique n'est pas là pour
remplacer PostgreSQL. Il ajoute une couche d'interopérabilité et de connaissance
au-dessus du système, utile pour relier les stations, capteurs, sessions,
alertes et techniciens avec des vocabulaires standards.
