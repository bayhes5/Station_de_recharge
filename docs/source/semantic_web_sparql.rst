Web sémantique et SPARQL
========================

Cette page décrit une évolution possible du projet vers le web sémantique.
Elle est volontairement présentée comme une extension future : le fonctionnement
critique de la station ne dépend pas de SPARQL.

Objectif
--------

SPARQL peut apporter une valeur ajoutée comme couche d'interopérabilité et
d'analyse. Il permettrait de relier dans un graphe RDF les stations, bornes,
emplacements, ESP32, capteurs, sessions de charge, alertes, techniciens et
interventions.

Le cœur du système reste :

* Django et Django REST Framework pour la logique métier ;
* PostgreSQL et TimescaleDB pour la persistance ;
* MQTT pour les échanges Raspberry / ESP32 / backend ;
* Grafana pour les tableaux de bord opérationnels ;
* Celery pour les traitements asynchrones.

SPARQL ne doit pas être utilisé pour valider une authentification, ouvrir une
serrure, démarrer une charge ou envoyer une commande ESP32. Ces actions restent
dans le backend et dans le contrat MQTT.

Architecture recommandée
------------------------

::

   ESP32
     -> MQTT
     -> backend Django
     -> PostgreSQL / TimescaleDB
     -> export RDF contrôlé
     -> triplestore RDF
     -> requêtes SPARQL

PostgreSQL et TimescaleDB restent la source de vérité. Le triplestore reçoit une
copie filtrée et contrôlée des données utiles à l'analyse.

Références code :

* ``backend/api/models.py`` : modèles Station, Borne, Emplacement, Device,
  Capteur, CapteurData, Session, SessionTelemetry, Alerte, Technicien ;
* ``backend/api/mqtt.py`` : bridge MQTT backend ;
* ``backend/api/tasks.py`` : traitement asynchrone des messages MQTT ;
* ``backend/api/services/telemetry.py`` : normalisation et stockage de la
  télémétrie ;
* ``grafana/dashboards/`` : supervision opérationnelle.

Vocabulaires possibles
----------------------

Les vocabulaires suivants sont adaptés au domaine :

.. list-table::
   :header-rows: 1

   * - Vocabulaire
     - Utilisation
   * - SOSA / SSN
     - Capteurs et observations
   * - SAREF
     - Appareils connectés, énergie et services
   * - QUDT
     - Unités physiques comme °C, %, A, V, W et kWh
   * - GeoSPARQL
     - Localisation des stations
   * - Ontologie locale ``station:``
     - Concepts propres au projet

Modèle RDF cible
----------------

Hiérarchie physique :

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
     - Mesure horodatée
   * - ``station:ChargingSession``
     - Session effective de charge
   * - ``station:OperationalAlert``
     - Alerte de supervision
   * - ``station:Technician``
     - Technicien affecté à une station

Données à exporter
------------------

La couche RDF doit se concentrer sur les données techniques :

* stations, bornes et emplacements ;
* ESP32, adresse IP, MAC matérielle, version firmware ;
* capteurs et dernières mesures ;
* sessions actives ou récentes ;
* alertes ouvertes ou récentes ;
* affectations technicien/station ;
* maintenances.

Données à exclure
-----------------

Pour respecter le principe de privacy by design, le graphe RDF ne doit pas
exposer :

* mots de passe ou hash de mots de passe ;
* tokens JWT ;
* secrets QR ;
* codes SMS ;
* UID RFID ;
* emails et téléphones des utilisateurs finaux ;
* données personnelles non nécessaires.

Si une session doit être référencée, l'identifiant peut être pseudonymisé, par
exemple avec un HMAC côté backend.

Comparaison avec SQL relationnel
--------------------------------

Une base relationnelle peut déjà répondre à beaucoup de questions complexes.
Dans ce projet, PostgreSQL reste même le bon choix pour le fonctionnement
opérationnel : réservations, transactions, contraintes, permissions, sessions et
supervision.

Par exemple, la question suivante peut être traitée en SQL :

::

   Donne-moi les emplacements en charge, dont l'ESP32 a un firmware obsolète,
   avec une température supérieure au seuil, et le technicien responsable.

Exemple SQL simplifié :

.. code-block:: sql

   SELECT
     s.nom AS station,
     b.nom AS borne,
     e.numero AS emplacement,
     d.firmware_version,
     d.expected_firmware_version,
     cd.valeur AS temperature,
     t.nom AS technicien
   FROM station s
   JOIN borne b ON b.id_station = s.id_station
   JOIN emplacement e ON e.id_borne = b.id_borne
   JOIN device d ON d.id_emplacement = e.id_emplacement
   JOIN capteur c ON c.id_device = d.id_device
   JOIN capteur_data cd ON cd.id_capteur = c.id_capteur
   JOIN technicien_station ts ON ts.id_station = s.id_station
   JOIN technicien t ON t.id_technicien = ts.id_technicien
   WHERE d.firmware_update_status = 'update_required'
     AND c.type = 'temperature'
     AND cd.valeur > 60
     AND e.etat = 'charging';

Cette requête est possible, mais elle est fortement dépendante du schéma
interne : noms des tables, clés de jointure, noms des colonnes et valeurs métier.
Si le projet doit intégrer demain une source externe, comme un système de ville
connectée, une météo, un référentiel bâtiment ou un autre modèle de borne, il
faut ajouter des mappings spécifiques.

SPARQL n'est donc pas proposé parce qu'il serait meilleur que SQL pour les
transactions ou les performances. Il est proposé comme couche sémantique de
lecture, capable d'exprimer les relations métier dans un graphe :

::

   Station
     -> contient -> Borne
     -> contient -> Emplacement
     -> héberge -> ESP32
     -> possède -> Capteur
     -> observe -> Température
     -> est suivie par -> Technicien

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

Réponse courte pour la soutenance :

   Oui, PostgreSQL peut répondre à cette question avec des jointures SQL, et
   c'est la bonne solution pour le cœur opérationnel. SPARQL n'est pas destiné à
   remplacer PostgreSQL. Il devient intéressant comme couche sémantique au-dessus
   du système, pour relier des objets hétérogènes avec des vocabulaires standards
   et faciliter l'interopérabilité avec d'autres plateformes.

Exemples de requêtes
--------------------

Stations avec alertes critiques ouvertes :

.. code-block:: sparql

   PREFIX station: <https://station-recharge.local/ontology#>

   SELECT ?station ?stationName ?alert ?message
   WHERE {
     ?station a station:ChargingStation ;
              station:name ?stationName ;
              station:hasCabinet ?borne .

     ?borne station:hasSlot ?slot .
     ?slot station:raisedAlert ?alert .

     ?alert station:severity "critical" ;
            station:status "open" ;
            station:message ?message .
   }
   ORDER BY ?stationName

ESP32 avec firmware obsolète :

.. code-block:: sparql

   PREFIX station: <https://station-recharge.local/ontology#>

   SELECT ?device ?firmware ?expected ?slot
   WHERE {
     ?slot station:hostsDevice ?device .
     ?device station:firmwareVersion ?firmware ;
             station:expectedFirmwareVersion ?expected ;
             station:firmwareStatus "update_required" .
   }

Charge détectée sans session active :

.. code-block:: sparql

   PREFIX station: <https://station-recharge.local/ontology#>

   SELECT ?slot ?device ?current ?time
   WHERE {
     ?slot station:hostsDevice ?device .
     ?device station:lastCurrent ?current ;
             station:lastTelemetryAt ?time .

     FILTER (?current > 0.5)

     FILTER NOT EXISTS {
       ?slot station:hasChargingSession ?session .
       ?session station:chargeState "charging" .
     }
   }
   ORDER BY DESC(?time)

Mise en place future
--------------------

La mise en place peut se faire par étapes :

1. créer ``semantic/ontology/station-recharge.ttl`` ;
2. créer des requêtes exemples dans ``semantic/queries/`` ;
3. ajouter ``rdflib`` côté Python ;
4. créer une commande Django ``export_semantic_graph`` ;
5. exporter un fichier Turtle filtré ;
6. charger ce fichier dans Apache Jena Fuseki ;
7. automatiser l'export toutes les 5 ou 15 minutes ;
8. documenter les accès et les limites de confidentialité.

Choix recommandé
----------------

Pour ce projet, la bonne stratégie est de garder SPARQL optionnel. Il apporte une
valeur académique et une ouverture vers l'interopérabilité, mais il ne doit pas
devenir une dépendance des parcours critiques : réservation, authentification,
mode dégradé, commande serrure et démarrage de charge.

La notice détaillée à la racine du dépôt est disponible dans
``NOTICE_WEB_SEMANTIQUE_SPARQL.md``.
