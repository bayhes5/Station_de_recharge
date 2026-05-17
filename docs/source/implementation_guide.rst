Fonctionnalités et implantation
===============================

Cette page constitue le dossier d'implantation fonctionnelle et technique. Elle
relie chaque fonctionnalité livrée à son implantation dans le code, aux modèles
concernés et aux choix d'architecture retenus pour répondre au besoin client.

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
      -> Raspberry publie START vers l'emplacement
      -> ESP32 démarre la charge
      -> ESP32 publie la télémétrie
      -> le bridge d'ingestion transmet à Celery
      -> Django stocke capteurs, devices, alertes
      -> interface admin et Grafana affichent l'état

Modèle de données
-----------------

Les modèles métier sont dans ``backend/api/models.py``.

``Utilisateur`` remplace le modèle utilisateur standard Django afin d'utiliser le
pseudo comme identifiant principal, tout en gardant les permissions Django grâce
à ``AbstractBaseUser`` et ``PermissionsMixin``. ``ProfilUtilisateur`` sépare les
données personnelles du compte d'authentification.

``Station``, ``Borne`` et ``Emplacement`` décrivent la structure physique. Une
station contient plusieurs bornes, et chaque borne contient plusieurs
emplacements. L'emplacement reste l'objet réservé et piloté électriquement ; il
porte son état métier et son état de serrure.

``Reservation`` relie un utilisateur, un emplacement, un moyen
d'authentification et une fenêtre de temps. Les durées proposées sont 30 minutes,
1 heure, 2 heures et 4 heures, avec 1 heure par défaut. Cette règle garde une
expérience simple tout en restant réaliste pour une recharge de vélo électrique.

``Session`` représente la charge réellement ouverte à la borne. Elle est créée
quand le kiosque valide l'accès. ``SessionTelemetry`` stocke les mesures
électriques associées si une session active existe.

``Authentification`` centralise les moyens d'accès : RFID persistant, QR code et
code SMS temporaire. Les secrets ne sont pas stockés en clair : ils sont hachés
ou dérivés depuis un nonce et ``SECRET_KEY``.

``Device``, ``Capteur`` et ``CapteurData`` relient un ESP32 à son emplacement.
La supervision remonte donc la station, la borne et l'emplacement associés à
chaque mesure. ``Alerte`` stocke les anomalies opérationnelles créées depuis la
télémétrie.

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

Les consentements sont consultables et pilotables via
``GET/PATCH /api/me/consentements/``. Les CGU et la politique de confidentialité
sont affichées comme décisions obligatoires prises à l'inscription. Les
notifications restent optionnelles : le profil permet de les accepter ou de les
refuser, et chaque changement ajoute une nouvelle ligne historisée dans
``consentement``.

Les actions sensibles côté administration et accès sont journalisées dans
``JournalSecurite`` par ``_log_security_event``. Cette traçabilité prépare les
besoins d'audit, de support et d'exploitation d'une solution multi-utilisateurs.

Réservation en ligne
--------------------

La réservation utilise trois endpoints principaux :

* ``GET /api/stations/`` pour le catalogue des stations ;
* ``GET /api/reservations/availability/`` pour vérifier les disponibilités ;
* ``POST /api/reservations/`` pour créer une réservation.

Le frontend correspondant se trouve dans ``frontend/reservation.html`` et
``frontend/js/reservation.js``. La carte utilise Leaflet afin de rester simple,
lisible et suffisante pour localiser les stations.

L'utilisateur choisit une station, un début de réservation et une durée de
recharge, mais pas forcément un emplacement précis. Le backend centralise la règle de disponibilité dans
``_available_emplacements`` et ``_reservation_overlaps``. Ce choix évite que deux
navigateurs prennent des décisions concurrentes côté client.

La durée est validée côté backend avec ``_duration_is_valid``. Les durées
acceptées sont centralisées dans ``backend/api/reservation_rules.py``. Les tests
associés sont dans ``backend/api/tests/test_reservations.py`` et
``backend/api/tests/test_serializers.py``.

La validation à la borne utilise deux marges métier : ``RESERVATION_START_GRACE_MINUTES``
autorise l'arrivée un peu avant le début du créneau et
``RESERVATION_END_GRACE_MINUTES`` autorise un léger retard après la fin. Par
défaut, ces valeurs sont de 5 minutes et 10 minutes. Elles sont utilisées par
les endpoints terminal, les sessions mobiles et le cache offline.

Ces marges ne sont pas prises en compte par ``_available_emplacements`` ni par
``_reservation_overlaps``. Le backend réserve uniquement la fenêtre payée par
l'utilisateur afin de maximiser l'utilisation de la station. Deux réservations
adjacentes, par exemple 13h00-14h00 puis 14h00-15h00, peuvent donc être affectées
au même emplacement. Au moment de l'ouverture, ``_session_start_conflict_response``
empêche toutefois de démarrer en avance si l'emplacement est encore couvert par
le créneau précédent ou par une session de charge active.

QR code et code SMS temporaire
------------------------------

Les QR codes et codes SMS temporaires sont rattachés à une réservation, pas au
profil utilisateur. Cela permet de créer un secret valable seulement pour la
fenêtre réservée.

Le QR code est généré dès la réservation et consultable dans l'application. Il
sert d'accès applicatif immédiat, mais il n'est accepté à la borne que sur le bon
créneau, la bonne station et tant qu'il n'est pas révoqué.

Le code SMS est aussi généré techniquement dès la réservation afin que le secret
puisse être synchronisé ou caché côté station avant le passage de l'utilisateur.
Il n'est toutefois pas affiché dans l'interface : il est envoyé via
``POST /api/reservations/<reservation_id>/send-access-code/`` peu avant le
créneau, ou à la demande avec le bouton d'envoi. Une réservation en mode
``code`` est refusée si aucun numéro de téléphone n'est renseigné. En mode
production, ``SMS_REQUIRE_VERIFIED_PHONE`` doit être activé : le numéro doit
alors être marqué comme vérifié sur le profil avant de pouvoir choisir ou
recevoir un code SMS.

Le service d'envoi est abstrait dans ``backend/api/services/sms.py``. Le backend
``console`` sert au développement local et journalise seulement l'envoi. Les
backends ``twilio``, ``brevo`` et ``ovh`` utilisent des variables
d'environnement dédiées et échouent immédiatement si leurs identifiants sont
absents. ``SMS_RESEND_COOLDOWN_SECONDS`` limite le renvoi manuel du même code
pour éviter le spam et les boucles côté interface mobile.

L'implantation principale est dans ``backend/api/views.py`` :

* ``_create_temporary_auth`` crée le moyen d'accès ;
* ``_derive_temporary_access_secret`` reconstruit la valeur temporaire depuis un
  nonce, le code de réservation et ``SECRET_KEY`` ;
* ``_build_qr_payload`` prépare le contenu QR ;
* ``_build_qr_svg`` génère le SVG QR ;
* ``reservation_access_payload`` expose le QR ou les métadonnées du code SMS ;
* ``send_reservation_access_code`` envoie le code SMS et journalise l'action.
  Les métadonnées d'authentification conservent notamment le dernier envoi et
  l'identifiant retourné par le fournisseur SMS, sans stocker le code clair.

Le choix important est de ne pas stocker le secret clair. L'administration peut
régénérer ou révoquer l'accès, mais elle ne devient pas le canal de transmission
du secret. Cette génération préalable est aussi ce qui rend le mode dégradé
possible : si le backend est indisponible au moment où l'utilisateur arrive à la
borne, la station peut vérifier un secret déjà connu du système plutôt que de
devoir le créer à la volée.

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

Session mobile de borne
-----------------------

La session mobile de borne couvre le cas où l'utilisateur utilise son téléphone
pour autoriser le kiosque. Elle ne remplace pas le QR de réservation.

Le kiosque crée une session temporaire avec
``POST /api/terminal/mobile-sessions/``. Le backend renvoie un token et une URL
mobile. Le kiosque transforme cette URL en QR. L'utilisateur scanne le QR avec
son téléphone, se connecte à la PWA si nécessaire, consulte les réservations
compatibles avec la station, puis en choisit une. Le backend marque alors la
session comme autorisée.

Le kiosque interroge la session jusqu'à obtenir un statut autorisé, consomme
l'autorisation, puis publie seulement ensuite la commande ``START`` vers
l'ESP32. Si la session expire, il faut générer un nouveau QR de borne.

Le point important est la séparation des rôles :

* le QR de réservation identifie une réservation et peut être scanné par un
  lecteur QR de borne ;
* le QR de borne identifie une session temporaire entre le téléphone et le
  kiosque ;
* la réservation choisie vient de la session utilisateur authentifiée sur la
  PWA.

Kiosque Raspberry
-----------------

Le kiosque se trouve dans ``raspberry/app/``.

``main.py`` sert l'interface statique et expose ``POST /mqtt/command``. Ce point
d'entrée local publie une commande MQTT vers l'ESP32 après validation par l'API.
``mqtt_client.py`` construit le canal ``station/<slot_id>/cmd`` et publie la
commande ``START``, ``STOP``, ``LOCK`` ou ``UNLOCK``.

Le choix d'un petit serveur local est volontaire : le Raspberry reste simple et
joue le rôle d'un client local de borne. La décision métier reste dans Django ; le kiosque
ne fait que transmettre une commande validée.

Le kiosque expose aussi un flux RFID local. ``POST /rfid/scan`` reçoit un UID
lu par un lecteur ou injecté en test, applique un debounce court contre les
doubles lectures, puis ``GET /rfid/scan?since=<id>`` permet au frontend de
récupérer le dernier scan. Sur l'écran d'accueil, un badge lu déclenche
directement l'authentification RFID. Sur l'écran d'association, le même scan
remplit l'UID du badge avant l'appel à ``POST /api/terminal/link-rfid/``.

Le backend lecteur se choisit avec ``RFID_READER_BACKEND`` : ``manual`` pour les
tests via HTTP, ``acr122u`` pour le lecteur ACR122U via PC/SC et ``pyscard``,
``stdin`` pour un lecteur qui émule un clavier ou une liaison série, et
``nfcpy`` pour un autre lecteur NFC compatible si la dépendance optionnelle est
installée sur le Raspberry. Le backend ACR122U lit l'UID avec la commande PC/SC
``FF CA 00 00 00`` puis le transmet au flux local avec le même debounce que les
autres sources.

En mode nominal, le Raspberry ne décide pas seul d'ouvrir un emplacement. Il
appelle d'abord l'API terminal, qui valide la réservation, le moyen d'accès, la
station attendue et crée ou retrouve la session de charge. Après cette réponse,
le Raspberry relaie la commande ``START`` vers l'ESP32 concerné.

Le mode dégradé doit rester limité : si le backend devient indisponible, le
Raspberry peut s'appuyer sur un cache local d'autorisations déjà synchronisées,
avec une durée de vie courte et une portée limitée à la station. Ce cache permet
de maintenir une continuité de service contrôlée sans transformer le kiosque en
source de vérité.

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

La logique ESP32 de référence est dans ``esp32/``. La simulation Wokwi est dans
``esp32/wokwi/``. Elle se connecte au WiFi Wokwi, s'abonne à
``station/slot1/cmd`` et publie sur :

.. code-block:: text

   station/<slot_id>/ack
   station/<slot_id>/telemetry
   station/<slot_id>/status
   station/<slot_id>/alert

Chaque commande contient un ``command_id`` et l'ESP32 doit répondre sur
``station/<slot_id>/ack`` avec le même identifiant. Le Raspberry utilise cet
accusé de réception pour confirmer que le relais ou le verrou a bien reçu la
commande.

La machine d'état embarquée est volontairement simple :

.. code-block:: text

   idle -> reserved -> charging -> idle

En charge, l'ESP32 arrête la session simulée si le boîtier s'ouvre, si le câble
est retiré, si le courant dépasse le seuil ou si la température dépasse le
seuil. Ces règles locales représentent les réflexes de sécurité qui doivent
rester possibles même si le backend est indisponible.

Le stockage local ESP32, par exemple avec LittleFS, est prévu pour conserver les
événements et mesures qui ne peuvent pas être transmis pendant une coupure. Au
retour de la communication, ces traces sont rejouées vers le backend pour
conserver l'historique central et la supervision.

Télémétrie temps réel et ingestion
----------------------------------

Le broker local est Mosquitto. Les services concernés sont :

* ``mqtt`` : broker de messagerie ;
* ``mqtt-bridge`` : consommateur abonné aux télémétries ;
* ``celery`` : traitement asynchrone ;
* ``redis`` : broker Celery ;
* ``db`` : stockage final.

``backend/api/mqtt.py`` s'abonne aux canaux de télémétrie et délègue à
``api.process_mqtt_message``. Cette tâche est définie dans
``backend/api/tasks.py``. Elle extrait l'emplacement depuis le canal ou le message,
puis appelle ``ingest_slot_telemetry`` dans
``backend/api/services/telemetry.py``.

Le choix Celery évite de bloquer le consommateur de messages pendant les
écritures en base.
Même si le volume actuel reste limité, cette architecture prépare le
filtrage, l'agrégation et les notifications.

Stockage des capteurs
---------------------

``ingest_slot_telemetry`` crée ou met à jour le ``Device`` associé à l'emplacement,
met à jour ``last_seen`` et stocke les mesures numériques dans ``CapteurData``.
Quand le topic MQTT contient un préfixe structuré
``station/<station>/<borne>/<slot_id>/telemetry``, le backend utilise la partie
``<station>/<borne>`` pour retrouver la borne via ``Borne.mqtt_prefix`` avant de
choisir l'emplacement. Cette règle protège les environnements multi-bornes où
plusieurs ESP32 peuvent publier un ``slot1``.

Les champs booléens ``door`` et ``cable`` sont convertis en ``1.0`` ou ``0.0``
pour rester compatibles avec ``CapteurData.valeur`` qui est numérique. L'API de
supervision ajoute ensuite un ``display_value`` lisible :

* ``Boîtier fermé`` / ``Boîtier ouvert`` ;
* ``Câble présent`` / ``Câble retiré``.

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

L'endpoint ``GET /api/technician/supervision/`` réutilise le même moteur
d'agrégation, mais avec un périmètre de stations. Pour un technicien non
administrateur, seules les stations affectées via ``TechnicienStation`` sont
visibles. Les administrateurs gardent la supervision globale.

Le frontend est dans ``frontend/admin-dashboard.html`` et
``frontend/js/admin-dashboard.js``. L'onglet supervision reçoit les mises à jour
via ``/ws/admin/supervision/`` quand Django Channels est disponible, puis garde un
rafraîchissement HTTP périodique en secours. Il fournit aussi un lien direct vers
le dashboard Grafana :

.. code-block:: text

   /grafana/d/station-overview/station-vue-globale-supervision

L'interface admin reste orientée exploitation métier : elle présente les alertes
et les états récents sous forme de tableaux lisibles. Grafana est réservé aux
courbes et séries temporelles.

Grafana
-------

Grafana est provisionné depuis ``grafana/provisioning/``. La datasource
PostgreSQL est dans ``grafana/provisioning/datasources/datasource.yml`` et le
dashboard d'accueil dans ``grafana/dashboards/station-overview.json``. Le
dashboard détaillé des séries capteurs reste dans
``grafana/dashboards/station-supervision.json``.

Les dashboards lisent directement les tables Django : ``charging_session``,
``session_telemetry``, ``capteur_data``, ``capteur``, ``device``,
``device_command_log``, ``emplacement``, ``borne``, ``station`` et ``alerte``.
Ce choix évite de créer une API dédiée pour Grafana et exploite les capacités SQL
de PostgreSQL.

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
* gestion des stations, bornes et emplacements ;
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

``TechnicienStation`` rattache un technicien à une station avec un rôle
opérationnel : ``intervenant``, ``referent`` ou ``observateur``. Cette table sert
à limiter la supervision visible dans le dashboard technicien et évite de donner
un accès Grafana large à un intervenant terrain. L'admin peut gérer ces
affectations depuis l'onglet opérations avec la ressource
``technician-station``.

L'endpoint ``GET /api/technician/maintenances/`` permet à un technicien connecté
de consulter ses interventions. L'administration peut créer, modifier et
supprimer les techniciens et maintenances.

Frontend
--------

Le frontend est volontairement multi-pages. Chaque page HTML charge un module
sous ``frontend/src/pages/`` qui importe ensuite le script métier sous
``frontend/js/``. Le client API commun est ``frontend/js/api.js``.

La couche PWA se compose de :

* ``frontend/public/manifest.webmanifest`` pour l'installation mobile ;
* ``frontend/public/sw.js`` pour le cache léger de l'enveloppe applicative ;
* ``frontend/js/pwa.js``, importé par le client commun, pour enregistrer le
  service worker sur toutes les pages.

Ce cache ne remplace pas l'API : les réservations, statuts de session et moyens
d'accès restent récupérés en ligne afin de conserver une source de vérité côté
backend.

Ce choix garde une structure lisible et maintenable : une page correspond à un
parcours métier. Vite apporte le serveur de développement, le build de
production et les tests Playwright sans imposer un framework SPA complet.

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

Le reverse proxy Nginx est le point d'entrée recommandé. Il expose HTTPS sur
``https://localhost`` avec un certificat auto-signé de développement et redirige
le trafic HTTP vers HTTPS. Le frontend Docker utilise ``/api`` comme URL d'API
afin de rester sur le même domaine et d'éviter les appels mixtes HTTP/HTTPS.

Qualité, tests et CI
--------------------

Les tests backend sont dans ``backend/api/tests/``. Les tests couvrant les
règles métier principales sont :

* ``test_reservations.py`` pour disponibilité et réservation ;
* ``test_terminal_auth.py`` pour QR/code SMS/RFID et ouverture de session ;
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

Le projet contient une chaîne DevSecOps adaptée à un livrable applicatif
professionnel :

* CodeQL analyse Python et JavaScript ;
* Dependabot propose les mises à jour ;
* Syft génère les SBOM ;
* Grype analyse les vulnérabilités ;
* OpenVEX peut documenter les vulnérabilités non exploitables ;
* GitHub Pages publie la documentation.

Ces outils rendent le projet auditable : les dépendances utilisées sont
inventoriées, les contrôles qui protègent ``main`` sont visibles et la
documentation publiée reste reconstruite depuis les sources versionnées.

Limites et périmètre actuel
---------------------------

La solution couvre le flux fonctionnel principal. Certains éléments restent
volontairement hors périmètre de livraison ou simulés dans l'environnement
local :

* les relais, serrures et capteurs physiques ne remplacent pas encore toutes les
  simulations ;
* MQTT n'est pas authentifié en développement local ;
* Grafana n'est pas encore protégé par SSO ;
* les notifications technicien par email ou SMS restent à définir séparément du
  code SMS temporaire d'accès ;
* TimescaleDB est utilisé comme PostgreSQL compatible, sans hypertables dédiées
  pour l'instant ;
* la gestion de conservation des historiques reste à définir.

Ces limites définissent le périmètre actuel et les chantiers nécessaires avant
un déploiement de production complet.

Synthèse opérationnelle
-----------------------

La solution peut être présentée selon la chaîne opérationnelle suivante :

1. Le backend Django porte les règles métier et la base relationnelle.
2. Le frontend Vite fournit les parcours utilisateur, admin et technicien.
3. Le Raspberry représente la borne locale et publie les commandes MQTT.
4. Les ESP32 exécutent les commandes et publient la télémétrie.
5. Mosquitto, Celery et Redis rendent l'ingestion asynchrone.
6. PostgreSQL/TimescaleDB conserve les mesures et alertes.
7. L'interface admin donne une vue opérationnelle lisible.
8. Grafana donne les graphes techniques.
9. Les tests, CI, SBOM, CodeQL et Pages rendent le projet vérifiable.

Cette lecture relie chaque capacité métier à un composant applicatif, un modèle
de données et un choix technique vérifiable.
