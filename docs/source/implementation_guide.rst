Fonctionnalités et implantation
===============================

Cette page sert de guide d'explication du projet. Elle relie chaque
fonctionnalité visible à son implantation dans le code, aux modèles concernés et
aux choix techniques qui ont été faits. L'objectif est de pouvoir expliquer le
prototype sans devoir relire tout le dépôt pendant une présentation.

Vue d'ensemble
--------------

Le projet est organisé autour de quatre surfaces applicatives :

* le backend Django, qui porte les règles métier, les modèles, l'API REST,
  l'authentification, les réservations et l'ingestion MQTT ;
* le frontend Vite multi-pages, qui fournit les écrans utilisateur,
  administrateur et technicien ;
* le kiosque Raspberry, qui représente l'interface locale de la borne ;
* l'ESP32, réel ou simulé, qui représente le contrôleur d'un emplacement.

La stack Docker ajoute les services techniques nécessaires : TimescaleDB/
PostgreSQL pour la base, Redis pour Celery et le cache, Mosquitto pour MQTT,
Grafana pour la supervision et Nginx comme point d'entrée local.

Le flux le plus complet est le suivant :

.. code-block:: text

   utilisateur réserve
      -> backend attribue un emplacement
      -> utilisateur s'identifie au kiosque
      -> Raspberry publie START en MQTT
      -> ESP32 démarre la charge
      -> ESP32 publie la télémétrie
      -> mqtt-bridge transmet à Celery
      -> Django stocke capteurs, devices, alertes
      -> interface admin et Grafana affichent l'état

Modèle de données
-----------------

Les modèles métier sont dans ``backend/api/models.py``.

``Utilisateur`` remplace le modèle utilisateur standard Django afin d'utiliser le
pseudo comme identifiant principal, tout en gardant les permissions Django grâce
à ``AbstractBaseUser`` et ``PermissionsMixin``. ``ProfilUtilisateur`` sépare les
données personnelles du compte d'authentification.

``Station`` et ``Emplacement`` décrivent la structure physique. Une station
contient plusieurs emplacements ; chaque emplacement porte son état métier et
son état de serrure.

``Reservation`` relie un utilisateur, un emplacement, un moyen
d'authentification et une fenêtre de temps. La durée choisie dans le prototype
est de 30 minutes pour simplifier l'expérience, le calcul de disponibilité et
l'expiration des accès temporaires.

``Session`` représente la charge réellement ouverte à la borne. Elle est créée
quand le kiosque valide l'accès. ``SessionTelemetry`` stocke les mesures
électriques associées si une session active existe.

``Authentification`` centralise les moyens d'accès : RFID persistant, QR code et
code temporaire. Les secrets ne sont pas stockés en clair : ils sont hachés ou
dérivés depuis un nonce et ``SECRET_KEY``.

``Device``, ``Capteur`` et ``CapteurData`` relient un ESP32 à son emplacement et
stockent les mesures horodatées. ``Alerte`` stocke les anomalies opérationnelles
créées depuis la télémétrie.

Authentification applicative
----------------------------

Les endpoints d'authentification sont déclarés dans ``backend/api/api_urls.py``
et implémentés dans ``backend/api/views.py`` :

* ``POST /api/register/`` crée un utilisateur via ``RegisterSerializer`` ;
* ``POST /api/login/`` accepte pseudo ou email ;
* ``POST /api/token/refresh/`` renouvelle le jeton d'accès ;
* ``POST /api/logout/`` efface le refresh token ;
* ``GET /api/me/`` expose la session courante.

Le choix JWT vient du besoin d'une API consommée par plusieurs clients :
frontend, kiosque et outils de test. Le refresh token est placé dans un cookie
``HttpOnly`` pour réduire l'exposition côté JavaScript. Le frontend garde
l'access token en mémoire et sait le renouveler depuis ``frontend/js/api.js``.

Les écrans concernés sont :

* ``frontend/login.html`` et ``frontend/js/login.js`` ;
* ``frontend/register.html`` et ``frontend/js/register.js`` ;
* ``frontend/profile.html`` et ``frontend/js/profile.js``.

Profil, export et sécurité utilisateur
--------------------------------------

Le profil utilisateur est modifiable via ``GET/PATCH/DELETE /api/me/profile/``.
Le changement de mot de passe passe par ``/api/me/change-password/`` afin de
vérifier le mot de passe courant. L'export de compte est disponible via
``/api/me/export/``.

Les actions sensibles côté administration et accès sont journalisées dans
``JournalSecurite`` par ``_log_security_event``. Cela permet d'expliquer qu'un
prototype académique peut déjà préparer une traçabilité minimale.

Réservation en ligne
--------------------

La réservation utilise trois endpoints principaux :

* ``GET /api/stations/`` pour le catalogue des stations ;
* ``GET /api/reservations/availability/`` pour vérifier les disponibilités ;
* ``POST /api/reservations/`` pour créer une réservation.

Le frontend correspondant se trouve dans ``frontend/reservation.html`` et
``frontend/js/reservation.js``. La carte utilise Leaflet afin de rester simple,
lisible et suffisante pour localiser les stations.

L'utilisateur choisit une station et un créneau, mais pas forcément un
emplacement précis. Le backend centralise la règle de disponibilité dans
``_available_emplacements`` et ``_reservation_overlaps``. Ce choix évite que deux
navigateurs prennent des décisions concurrentes côté client.

La fenêtre de réservation est forcée à 30 minutes avec
``_duration_is_valid``. Les tests associés sont dans
``backend/api/tests/test_reservations.py``.

QR code et code temporaire
--------------------------

Les QR codes et codes temporaires sont rattachés à une réservation, pas au
profil utilisateur. Cela permet de créer un secret valable seulement pour la
fenêtre réservée.

L'implantation principale est dans ``backend/api/views.py`` :

* ``_create_temporary_auth`` crée le moyen d'accès ;
* ``_derive_temporary_access_secret`` reconstruit la valeur temporaire depuis un
  nonce, le code de réservation et ``SECRET_KEY`` ;
* ``_build_qr_payload`` prépare le contenu QR ;
* ``_build_qr_svg`` génère le SVG QR ;
* ``reservation_access_payload`` expose le QR ou le code à l'utilisateur.

Le choix important est de ne pas stocker le secret clair. L'administration peut
régénérer ou révoquer l'accès, mais elle ne devient pas le canal de transmission
du secret.

RFID
----

Le RFID est traité comme un moyen d'accès persistant lié au compte. Un
utilisateur peut créer un code d'association depuis son profil avec
``/api/me/auth-methods/link-code/``. Le kiosque consomme ensuite ce code via
``POST /api/terminal/link-rfid/`` pour rattacher le badge au compte.

Ce fonctionnement sépare deux moments :

* côté web, l'utilisateur demande une autorisation d'association ;
* côté borne, le badge physique est réellement présenté.

Les tests sont dans ``backend/api/tests/test_terminal_auth.py``. Cette séparation
évite qu'un badge puisse être associé sans passage par la borne.

Kiosque Raspberry
-----------------

Le kiosque se trouve dans ``raspberry/app/``.

``main.py`` sert l'interface statique et expose ``POST /mqtt/command``. Ce point
d'entrée local publie une commande MQTT vers l'ESP32 après validation par l'API.
``mqtt_client.py`` construit le topic ``station/<slot_id>/cmd`` et publie le
payload ``START``, ``STOP``, ``LOCK`` ou ``UNLOCK``.

Le choix d'un petit serveur local est volontaire : le Raspberry reste simple et
joue le rôle d'un client edge. La décision métier reste dans Django ; le kiosque
ne fait que transmettre une commande validée.

Validation terminal
-------------------

L'endpoint central est ``POST /api/terminal/authenticate/``. Il vérifie :

* le code de réservation ou la réservation retrouvée par RFID ;
* le mode d'authentification attendu ;
* le secret fourni ;
* l'expiration et la révocation ;
* la station attendue ;
* l'existence ou la création d'une ``Session`` active.

Si la validation réussit, l'API renvoie l'emplacement et les informations utiles
au kiosque. Celui-ci peut alors publier ``START`` vers l'ESP32. Le comportement
est volontairement idempotent : si une session active existe déjà, le terminal
peut retrouver le même état sans créer de session doublon.

ESP32 et simulation Wokwi
-------------------------

Le prototype ESP32 est dans ``esp32/``. La simulation Wokwi est dans
``esp32/wokwi/``. Elle se connecte au WiFi Wokwi, s'abonne à
``station/slot1/cmd`` et publie sur :

.. code-block:: text

   station/<slot_id>/telemetry
   station/<slot_id>/status
   station/<slot_id>/alert

La machine d'état embarquée est volontairement simple :

.. code-block:: text

   idle -> reserved -> charging -> idle

En charge, l'ESP32 arrête la session simulée si le boîtier s'ouvre, si le câble
est retiré, si le courant dépasse le seuil ou si la température dépasse le
seuil. Ces règles locales représentent les réflexes de sécurité qui doivent
rester possibles même si le backend est indisponible.

MQTT et ingestion temps réel
----------------------------

Le broker local est Mosquitto. Les services concernés sont :

* ``mqtt`` : broker ;
* ``mqtt-bridge`` : client abonné aux télémétries ;
* ``celery`` : traitement asynchrone ;
* ``redis`` : broker Celery ;
* ``db`` : stockage final.

``backend/api/mqtt.py`` s'abonne aux topics de télémétrie et délègue à
``api.process_mqtt_message``. Cette tâche est définie dans
``backend/api/tasks.py``. Elle extrait le slot depuis le topic ou le payload,
puis appelle ``ingest_slot_telemetry`` dans
``backend/api/services/telemetry.py``.

Le choix Celery évite de bloquer le client MQTT pendant les écritures en base.
Même si le volume du prototype est faible, cette architecture prépare le
filtrage, l'agrégation et les notifications.

Stockage des capteurs
---------------------

``ingest_slot_telemetry`` crée ou met à jour le ``Device`` associé au slot,
met à jour ``last_seen`` et stocke les mesures numériques dans ``CapteurData``.

Les champs booléens ``door`` et ``cable`` sont convertis en ``1.0`` ou ``0.0``
pour rester compatibles avec ``CapteurData.valeur`` qui est numérique. L'API de
supervision ajoute ensuite un ``display_value`` lisible :

* ``Boitier ferme`` / ``Boitier ouvert`` ;
* ``Cable present`` / ``Cable retire``.

Ce choix permet à Grafana de lire une série numérique, tout en gardant une
interface admin compréhensible.

Alertes
-------

Les alertes sont créées depuis ``backend/api/services/telemetry.py``. Les règles
actuelles sont :

* ``intrusion`` si ``door`` vaut ``false`` pendant ``charging`` ;
* ``cable_removed`` si ``cable`` vaut ``false`` pendant ``charging`` ;
* ``overheat`` si la température est supérieure ou égale à ``60`` ;
* ``overcurrent`` si le courant est supérieur ou égal à ``3.0`` ;
* ``state_error`` si l'état vaut ``error``, ``emergency`` ou ``fault``.

Le cycle est automatique :

* ``nouvelle`` à la création ;
* ``active`` si la même anomalie continue sur une télémétrie suivante ;
* ``resolue`` quand une télémétrie normale confirme la disparition de la
  condition.

Le choix d'éviter les doublons rend la supervision plus lisible pendant une
simulation continue. Les alertes historiques restent en base pour conserver le
contexte.

Supervision administrateur
--------------------------

L'endpoint ``GET /api/admin/supervision/`` agrège :

* l'état des devices ;
* les alertes récentes ;
* les dernières mesures capteurs ;
* les compteurs de supervision.

Le frontend est dans ``frontend/admin-dashboard.html`` et
``frontend/js/admin-dashboard.js``. L'onglet supervision rafraîchit les données
en arrière-plan et fournit un lien direct vers le dashboard Grafana :

.. code-block:: text

   /grafana/d/station-supervision/station-supervision-technique

L'interface admin reste orientée exploitation métier : elle présente les alertes
et les états récents sous forme de tableaux lisibles. Grafana est réservé aux
courbes et séries temporelles.

Grafana
-------

Grafana est provisionné depuis ``grafana/provisioning/``. La datasource
PostgreSQL est dans ``grafana/provisioning/datasources/datasource.yml`` et le
dashboard dans ``grafana/dashboards/station-supervision.json``.

Le dashboard lit directement les tables Django : ``capteur_data``, ``capteur``,
``device``, ``emplacement``, ``station`` et ``alerte``. Ce choix évite de créer
une API dédiée pour Grafana et exploite les capacités SQL de PostgreSQL.

Administration métier
---------------------

L'administration applicative se trouve dans l'onglet admin du frontend. Les
endpoints commencent par ``/api/admin/`` et sont protégés par ``IsStaffUser``.

Les principales fonctions sont :

* vue globale des compteurs ;
* supervision technique ;
* gestion des utilisateurs ;
* gestion des RFID utilisateur ;
* régénération et révocation des accès de réservation ;
* gestion des stations et emplacements ;
* gestion des techniciens ;
* gestion des maintenances ;
* consultation des réservations et sessions.

Les formulaires de création/modification réutilisent ``frontend/admin-form.html``
et ``frontend/js/admin-form.js`` avec un paramètre ``resource``. Ce choix évite de
multiplier les pages tout en gardant des formulaires spécialisés par type de
ressource.

Techniciens et maintenance
--------------------------

``Technicien`` représente un intervenant de maintenance, éventuellement lié à un
compte utilisateur. ``Maintenance`` rattache une intervention à une station, un
technicien, un statut et des dates.

L'endpoint ``GET /api/technician/maintenances/`` permet à un technicien connecté
de consulter ses interventions. L'administration peut créer, modifier et
supprimer les techniciens et maintenances.

Frontend
--------

Le frontend est volontairement multi-pages. Chaque page HTML charge un module
sous ``frontend/src/pages/`` qui importe ensuite le script métier sous
``frontend/js/``. Le client API commun est ``frontend/js/api.js``.

Ce choix garde la structure facile à expliquer : une page correspond à un
parcours. Vite apporte le serveur de développement, le build de production et
les tests Playwright sans imposer un framework SPA complet.

Les pages principales sont :

* ``index.html`` : accueil ;
* ``login.html`` / ``register.html`` : authentification ;
* ``dashboard.html`` : espace utilisateur ;
* ``reservation.html`` : réservation ;
* ``profile.html`` : profil et moyens d'accès ;
* ``admin-dashboard.html`` : administration et supervision ;
* ``admin-form.html`` : formulaires admin ;
* ``technician-dashboard.html`` : vue technicien.

Docker et démarrage local
-------------------------

``docker-compose.yml`` orchestre toute la stack. Les healthchecks de ``db``,
``redis`` et ``mqtt`` permettent d'attendre les services critiques avant de
démarrer les consommateurs.

Les volumes montent le code local dans les conteneurs de développement. Après
une modification Python qui touche un processus long comme Celery ou
``mqtt-bridge``, il faut redémarrer les services concernés :

.. code-block:: bash

   docker compose restart backend celery mqtt-bridge

Le profil ``simulation`` démarre ``mqtt-simulator`` seulement quand on en a
besoin. Cela évite de polluer la base avec de la télémétrie continue lors d'un
démarrage standard.

Qualité, tests et CI
--------------------

Les tests backend sont dans ``backend/api/tests/``. Les tests les plus
importants pour expliquer les règles métier sont :

* ``test_reservations.py`` pour disponibilité et réservation ;
* ``test_terminal_auth.py`` pour QR/code/RFID et ouverture de session ;
* ``test_mqtt_ingestion.py`` pour télémétrie et alertes ;
* ``test_admin_api.py`` pour supervision et administration ;
* ``test_query_performance.py`` pour pagination/cache.

Le frontend est vérifié par ``npm run check:js``, ``npm run build`` et Playwright
via ``npm run verify``.

GitHub Actions lance la CI, CodeQL, la génération de SBOM/VEX et le build de
documentation. La documentation publique est générée par le workflow
``Documentation Pages`` depuis ``docs/source`` et publiée sur :

.. code-block:: text

   https://bayhes5.github.io/Station_de_recharge/

DevSecOps
---------

Le projet contient une chaîne DevSecOps adaptée à un prototype académique :

* CodeQL analyse Python et JavaScript ;
* Dependabot propose les mises à jour ;
* Syft génère les SBOM ;
* Grype analyse les vulnérabilités ;
* OpenVEX peut documenter les vulnérabilités non exploitables ;
* GitHub Pages publie la documentation.

Ces outils servent surtout à montrer que le projet est explicable et auditable :
on sait quelles dépendances sont utilisées, quels checks protègent ``main`` et
où se trouve la documentation publiée.

Limites actuelles à expliquer
-----------------------------

Le prototype est fonctionnel pour démontrer le flux complet, mais certains
éléments restent simulés ou volontairement simplifiés :

* les relais, serrures et capteurs physiques ne remplacent pas encore toutes les
  simulations ;
* MQTT n'est pas authentifié en développement local ;
* Grafana n'est pas encore protégé par SSO ;
* les notifications technicien email/SMS ne sont pas encore implémentées ;
* TimescaleDB est utilisé comme PostgreSQL compatible, sans hypertables dédiées
  pour l'instant ;
* la gestion de conservation des historiques reste à définir.

Ces limites ne sont pas des défauts cachés : elles marquent la frontière entre le
prototype démontrable et une version de production.

Comment expliquer le projet rapidement
--------------------------------------

Une explication courte peut suivre cet ordre :

1. Le backend Django porte les règles métier et la base relationnelle.
2. Le frontend Vite fournit les parcours utilisateur, admin et technicien.
3. Le Raspberry représente la borne locale et publie les commandes MQTT.
4. Les ESP32 exécutent les commandes et publient la télémétrie.
5. Mosquitto, Celery et Redis rendent l'ingestion asynchrone.
6. PostgreSQL/TimescaleDB conserve les mesures et alertes.
7. L'interface admin donne une vue opérationnelle lisible.
8. Grafana donne les graphes techniques.
9. Les tests, CI, SBOM, CodeQL et Pages rendent le projet vérifiable.

Cette lecture permet de relier chaque fonctionnalité à un fichier, un modèle et
un choix technique clair.
