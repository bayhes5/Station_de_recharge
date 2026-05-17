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
  et encore valides, par station, borne et emplacement ;
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

Cette architecture est plus robuste qu'un lien ESP32 dépendant directement du
backend central. Le Raspberry reste le contrôleur terrain : il publie les
commandes locales vers les ESP32 après validation backend, ou depuis un cache
offline déjà synchronisé en mode dégradé. Les règles métier ne sont pas
dupliquées dans les ESP32 ; elles restent côté backend, puis le Raspberry exécute
la décision au plus près du matériel.

Services Docker
---------------

La stack locale contient les services de supervision suivants :

* ``mqtt`` : broker Mosquitto local, exposé sur le port ``1883`` ;
* ``redis`` : cache, broker Celery et bus temps réel de Django Channels ;
* ``celery`` : worker de traitement asynchrone ;
* ``mqtt-bridge`` : consommateur backend abonné aux télémétries, statuts, ACK et alertes ESP32 ;
* ``grafana`` : supervision technique exposée sur ``http://localhost:3000`` ;
* ``db`` : TimescaleDB/PostgreSQL, compatible avec les modèles Django existants.

Le worker ``celery`` et le ``mqtt-bridge`` disposent de healthchecks Docker. Le
worker doit répondre à ``celery inspect ping``. Le bridge écrit un heartbeat
local tant que la connexion MQTT est active ; si le heartbeat devient trop
ancien, Docker marque le service comme non sain.

Supervision web temps réel
--------------------------

L'onglet administrateur ``Supervision`` reste disponible en HTTP avec :

.. code-block:: text

   GET /api/admin/supervision/

Cet endpoint retourne une photographie complète de l'état terrain : compteurs,
devices ESP32, alertes récentes et dernières mesures capteurs.

Le dashboard technicien utilise une vue séparée :

.. code-block:: text

   GET /api/technician/supervision/

Cette vue reprend les mêmes données, mais les filtre sur les stations affectées
au technicien connecté via ``TechnicienStation``. C'est le point d'entrée prévu
pour les intervenants terrain : ils voient leurs stations, les ESP32 associés,
les alertes récentes, les dernières mesures et les commandes acquittées, sans
accès global au parc.

Grafana reste la supervision technique des séries temporelles. En production, un
technicien ne devrait pas recevoir un accès Grafana large par défaut. Si Grafana
est ouvert aux techniciens plus tard, l'accès devra être en lecture seule et
limité par organisation, dossier, datasource ou proxy applicatif ; de simples
variables de dashboard ne constituent pas une barrière de sécurité suffisante.

Pour éviter d'attendre le rafraîchissement périodique, le backend expose aussi
un canal WebSocket réservé aux administrateurs :

.. code-block:: text

   /ws/admin/supervision/

Le navigateur ouvre ce canal avec le jeton d'accès JWT en paramètre. Le backend
vérifie que l'utilisateur est actif et administrateur avant d'accepter la
connexion. À chaque télémétrie MQTT, statut ESP32 ou alerte, le worker publie un
événement Channels dans le groupe ``admin_supervision``. Les dashboards connectés
reçoivent alors une nouvelle photographie de supervision.

Le polling toutes les 30 secondes reste volontairement conservé côté frontend :
il sert de filet de sécurité si le WebSocket n'est pas disponible, si le jeton
expire ou si le reverse proxy n'est pas encore configuré pour ``/ws/``.

Canaux de télémétrie et de commande
-----------------------------------

Les ESP32 publient leur télémétrie sur :

.. code-block:: text

   station/<slot_id>/telemetry

Ce format compact reste celui du développement local et du simulateur. En
production, le broker peut utiliser un chemin plus explicite par station et par
borne :

.. code-block:: text

   station/<station_id>/<borne_id>/<slot_id>/telemetry

Le couple ``<station_id>/<borne_id>`` doit correspondre au ``mqtt_prefix`` de la
borne en base, sans le préfixe global ``station``. Cette forme est recommandée
en production, car elle permet au backend de rattacher correctement deux
emplacements qui auraient le même ``slot_id`` sur deux bornes différentes. Le
format compact ``station/slot1/telemetry`` reste accepté pour le simulateur et
les tests locaux, mais il suppose des ``slot_id`` uniques dans l'environnement.

Le bridge backend s'abonne à ``station/#`` puis ne traite que les suffixes
supervisés ``telemetry``, ``status``, ``ack`` et ``alert``. Les messages de
diagnostic comme ``station/health`` sont donc ignorés par l'ingestion métier et
ne créent pas de faux ``Device``.

Ils publient aussi leurs événements d'état sur :

.. code-block:: text

   station/<slot_id>/status

Ils publient enfin leurs alertes locales immédiates sur :

.. code-block:: text

   station/<slot_id>/alert

Ils publient aussi les accusés de réception de commandes sur :

.. code-block:: text

   station/<slot_id>/ack

Ces événements servent de heartbeat opérationnel. Un ESP32 qui vient d'accepter
une commande ``START`` peut donc être vu comme connecté dès le message
``reserved`` ou ``charging_started``, même si la mesure DHT22/INA219 suivante
n'est pas encore arrivée.

Exemple de message :

.. code-block:: json

   {
     "state": "charging",
     "current": 1.2,
     "voltage": 12.0,
     "power": 14.4,
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

Le même principe de préfixe s'applique aux commandes terrain :

.. code-block:: text

   station/<station_id>/<borne_id>/<slot_id>/cmd

Le backend renvoie le ``mqtt_prefix`` de la borne dans les réponses de session
terminal. L'interface kiosk le transmet ensuite au Raspberry, qui publie la
commande et écoute l'ACK sur le même préfixe. La lecture télémétrie et l'écriture
commande utilisent donc le même routage par borne.

Le message de commande est un JSON simple :

.. code-block:: json

   {
     "command_id": "<uuid-commande>",
     "action": "START",
     "session_id": "<uuid-session>"
   }

Le Raspberry publie ce message via son client de messagerie local. Le backend
dispose du même mécanisme côté serveur avec la commande ``send_slot_command``.
En production, le chemin privilégié reste la publication depuis le Raspberry,
car il est connecté au broker Mosquitto local de la borne et peut fonctionner
même si le backend est temporairement indisponible.

Le Raspberry attend aussi une confirmation ESP32 sur :

.. code-block:: text

   station/<slot_id>/ack

L'accusé de réception attendu reprend le ``command_id`` :

.. code-block:: json

   {
     "command_id": "<uuid-commande>",
     "action": "START",
     "status": "accepted",
     "message": "Emplacement reserve.",
     "state": "reserved",
     "slot_id": "slot1",
     "session_id": "<uuid-session>"
   }

En développement, ``MQTT_ACK_REQUIRED=False`` laisse la commande réussir sans
ESP32 branché. En production, ``MQTT_ACK_REQUIRED=True`` permet de refuser le
démarrage si le relais ne confirme pas.

Le Raspberry ne considère pas tout ACK comme une validation. Le champ
``ack_received`` indique seulement qu'une réponse est arrivée. Le champ
``command_confirmed`` vaut ``true`` uniquement si le statut reçu correspond à
l'action envoyée : ``accepted``, ``reserved``, ``ready``, ``charging`` ou
``charging_started`` pour ``START``, ``stopped`` ou ``idle`` pour ``STOP``,
``locked`` pour ``LOCK`` et ``unlocked`` pour ``UNLOCK``. Les statuts ``error``,
``rejected``, ``denied``, ``failed`` et ``fault`` provoquent un refus immédiat,
même si les ACK ne sont pas obligatoires en développement.

Le bridge backend consomme aussi ces ACK. Il met à jour le device avec
``last_command_id``, ``last_command_action``, ``last_command_status``,
``last_command_message`` et ``last_command_at``. L'onglet administrateur
``Supervision`` affiche ainsi le dernier acquittement reçu pour chaque ESP32 et
l'historique récent des commandes acquittées. Cela permet de distinguer une
commande publiée, une commande confirmée et une charge réellement active
remontée ensuite par le statut ou la télémétrie.

Le Raspberry conserve en parallèle un état local par emplacement. Cet état
protège la borne contre les doubles ``START`` / ``STOP`` pendant qu'une session
est en cours. Il ne remplace pas Grafana : Grafana observe la télémétrie et les
états publiés par les ESP32, tandis que l'état local du Raspberry décrit la
dernière décision opérationnelle prise par le kiosk.

Commandes utiles
----------------

Afficher l'état des services de supervision :

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

Écouter les messages publiés sur les canaux de la station :

.. code-block:: bash

   docker compose exec mqtt mosquitto_sub -h localhost -t 'station/#' -v -C 5 -W 10

Publier une télémétrie de test sans ESP32 :

.. code-block:: bash

   docker compose exec mqtt mosquitto_pub -h localhost -t 'station/slot1/telemetry' -m '{"state":"charging","current":1.2,"voltage":12.0,"temperature":32.5,"humidity":45,"door":true,"cable":true}'

Sécurisation du broker MQTT
---------------------------

La configuration active ``mosquitto/config/mosquitto.conf`` reste ouverte pour
les tests locaux, Wokwi et les premiers essais ESP32 sur le réseau Wi-Fi. Pour
une borne réelle, utiliser ``mosquitto/config/mosquitto.secure.conf`` :

* ``allow_anonymous false`` bloque les connexions anonymes ;
* ``password_file`` impose un compte MQTT ;
* ``acl_file`` limite les topics accessibles à chaque rôle ;
* le healthcheck Docker publie sur ``station/health`` avec les identifiants
  ``MQTT_USERNAME`` / ``MQTT_PASSWORD`` si ces variables sont renseignées.

Préparer le fichier de mots de passe :

.. code-block:: powershell

   .\scripts\init-mqtt-auth.ps1

Puis copier le contenu de ``mosquitto.secure.conf`` vers ``mosquitto.conf`` ou
adapter le montage Docker pour pointer vers la configuration sécurisée. En
développement, un seul compte ``station_backend`` peut suffire pour le backend,
le simulateur et le Raspberry. En installation réelle, utiliser des comptes
séparés : ``station_backend``, ``raspberry_kiosk`` et un compte par ESP32
(``esp32_slot1``, ``esp32_slot2``, ``esp32_slot3``).

Vérifier que Django et la base répondent :

.. code-block:: bash

   docker compose exec backend python manage.py check
   docker compose exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select now();"'

Simulateur local de télémétrie
------------------------------

Wokwi peut rester de côté pendant le développement de la supervision. Le projet
contient une commande Django capable de publier des données capteurs réalistes
sur les mêmes canaux que les ESP32 :

.. code-block:: powershell

   cd backend
   ..\.venv\Scripts\python.exe manage.py simulate_mqtt_telemetry --slots slot1 slot2 slot3 --scenario mixed --interval 2

La commande publie par défaut sur ``station/<slot_id>/telemetry`` et utilise les
variables ``MQTT_HOST``, ``MQTT_PORT`` et ``MQTT_BASE_TOPIC``. Avec
``--topic-prefix station-centre/borne-1``, elle publie sur
``station/station-centre/borne-1/<slot_id>/telemetry`` pour reproduire le routage
de production station/borne/emplacement. Le scénario ``mixed`` alterne
des mesures normales et des anomalies pour tester la chaîne d'alertes :

* intrusion : boîtier ouvert pendant une charge ;
* câble retiré ;
* surchauffe ;
* surconsommation ;
* état critique.

Pour un test de bout en bout depuis le kiosk, préférer le mode lié à la session
active. Après validation QR et ouverture de la session de charge, cette commande
retrouve l'emplacement réellement attribué à la réservation, reprend le
``session_id`` backend, reprend le ``mqtt_prefix`` de la borne si celui-ci est
renseigné et ne publie que sur le ``slot_id`` de cet emplacement :

.. code-block:: powershell

   cd backend
   ..\.venv\Scripts\python.exe manage.py simulate_mqtt_telemetry --active-session --scenario normal --interval 2

Il est aussi possible de cibler explicitement une réservation :

.. code-block:: powershell

   cd backend
   ..\.venv\Scripts\python.exe manage.py simulate_mqtt_telemetry --reservation-code QR-SIM-1 --scenario normal --interval 2

Ce mode évite de marquer plusieurs ESP32 en ``charging`` alors qu'une seule
réservation a été validée.

Pour envoyer seulement quelques messages et vérifier le format sans broker :

.. code-block:: powershell

   cd backend
   ..\.venv\Scripts\python.exe manage.py simulate_mqtt_telemetry --count 3 --dry-run

Avec Docker, le simulateur est disponible dans un profil dédié pour ne pas le
lancer par défaut :

.. code-block:: bash

   docker compose up -d mqtt
   docker compose --profile simulation run --rm mqtt-simulator

Le simulateur tourne en conteneur éphémère. À l'arrêt, Docker le supprime
automatiquement ; il ne garde donc pas de référence vers un réseau Compose
supprimé après un rebuild.

Si Docker signale encore ``network ... not found`` pour un ancien conteneur
arrêté, supprimer uniquement le simulateur puis relancer la commande éphémère :

.. code-block:: bash

   docker compose rm -sf mqtt-simulator
   docker compose up -d mqtt
   docker compose --profile simulation run --rm mqtt-simulator

Pour comparer les réseaux attachés aux conteneurs :

.. code-block:: bash

   docker network ls
   docker inspect mqtt_simulator --format '{{json .NetworkSettings.Networks}}'
   docker inspect mqtt_broker --format '{{json .NetworkSettings.Networks}}'

La chaîne locale recommandée pour valider la supervision sans ESP32 est donc :

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

* ``Device`` : dernier état reçu et ``last_seen`` du device ESP32 ;
* ``Capteur`` et ``CapteurData`` : valeurs horodatées des capteurs ;
* ``SessionTelemetry`` : courant, tension et énergie si une session active
  existe sur l'emplacement ;
* ``Alerte`` : anomalies telles qu'intrusion, câble retiré, surchauffe ou
  surconsommation.

Les capteurs booléens ``door`` et ``cable`` sont stockés numériquement dans
``CapteurData`` : ``1`` signifie vrai et ``0`` signifie faux. L'API de
supervision expose en plus un libellé lisible pour l'interface :
``Boîtier fermé`` / ``Boîtier ouvert`` et ``Câble présent`` / ``Câble retiré``.

Dans l'interface administrateur, la colonne ``Connexion`` indique si l'ESP32 a
émis récemment une télémétrie ou un statut MQTT. Elle est calculée à partir de
``Device.last_seen`` et non à partir du champ ``status``. La colonne
``Dernier état reçu`` affiche la
dernière valeur métier transmise par l'équipement, par exemple ``charging`` pour
une charge en cours. Un ESP32 provisionné mais jamais vu reste donc hors ligne et
affiche ``Aucune télémétrie reçue`` tant qu'aucun message réel n'a été ingéré.

Cycle des alertes
-----------------

Une anomalie détectée par la télémétrie crée une alerte au statut ``nouvelle``.
Si la même anomalie continue sur une télémétrie suivante, l'alerte existante est
mise à jour au statut ``active`` au lieu de créer un doublon. Quand une
télémétrie normale confirme que la condition a disparu, l'alerte passe
automatiquement au statut ``resolue``.

L'email technicien n'est pas envoyé au premier signal. La notification part
uniquement si l'alerte est ``active``, si son type fait partie de
``ALERT_TECHNICIAN_EMAIL_TYPES`` et si elle persiste au-delà du délai configuré :

* ``ALERT_CRITICAL_NOTIFICATION_MIN_AGE_SECONDS`` pour les alertes critiques,
  ``60`` secondes par défaut ;
* ``ALERT_NOTIFICATION_MIN_AGE_SECONDS`` pour les autres alertes terrain,
  ``120`` secondes par défaut ;
* ``ALERT_RENOTIFY_COOLDOWN_SECONDS`` pour éviter les répétitions, ``1800``
  secondes par défaut.

La commande suivante permet d'envoyer les notifications en attente, par exemple
depuis une tâche planifiée :

.. code-block:: bash

   python manage.py send_alert_notifications

En environnement académique, ces emails sont capturés par Mailpit et
consultables sur ``http://localhost:8025``. Ce mécanisme complète l'API de
supervision : le technicien reçoit un signal, puis consulte son tableau de bord
restreint pour traiter l'incident.

Les conditions de résolution automatique sont :

* ``intrusion`` : ``door`` repasse à ``true`` ou l'emplacement n'est plus en charge ;
* ``cable_removed`` : ``cable`` repasse à ``true`` ou l'emplacement n'est plus en
  charge ;
* ``overheat`` : la température repasse sous ``60 C`` ;
* ``overcurrent`` : le courant repasse sous ``3.0 A`` ;
* ``state_error`` : l'état n'est plus ``error``, ``emergency`` ou ``fault``.

Le firmware est traité séparément. Si ``EXPECTED_ESP32_FIRMWARE_VERSION`` est
défini et que l'ESP32 remonte une version différente, le backend crée une alerte
``firmware_outdated`` de sévérité moyenne. Elle est levée automatiquement lorsque
l'équipement remonte la version attendue. Par défaut, cette alerte n'est pas
envoyée aux techniciens terrain : elle relève plutôt de l'administrateur ou du
responsable qui prépare les mises à jour firmware.

Accès technicien
----------------

Les techniciens n'ont pas besoin d'un accès Grafana global pour intervenir sur
le terrain. L'accès recommandé passe par le tableau de bord technicien de
l'application web :

* l'administrateur associe un technicien à une ou plusieurs stations ;
* l'endpoint ``/api/technician/supervision/`` retourne uniquement les stations
  affectées ;
* le WebSocket ``/ws/technician/supervision/`` diffuse les mêmes snapshots en
  temps réel avec le même périmètre restreint ;
* si le WebSocket est indisponible, l'interface repasse en polling HTTP.

Grafana reste réservé aux profils d'exploitation ayant besoin d'une vue globale
ou d'une analyse détaillée des séries temporelles. Ce découpage applique le
principe du moindre privilège : un technicien terrain voit ses stations, pas
tout le réseau.

Grafana
-------

Grafana est provisionné automatiquement avec une datasource PostgreSQL nommée
``Station TimescaleDB`` et deux dashboards complémentaires.

Le point d'entrée recommandé est ``Station - Vue globale supervision`` :

.. code-block:: text

   https://localhost/grafana/d/station-overview/station-vue-globale-supervision?orgId=1&from=now-6h&to=now&refresh=10s

Ce dashboard affiche les indicateurs globaux, les sessions en cours, les
stations à surveiller, les dernières alertes et les derniers acquittements ESP32.
Il expose aussi des variables de recherche ``station``, ``borne`` et
``emplacement``. Ces variables permettent de partir d'une vue globale puis de
zoomer progressivement sur un point de charge.

Le dashboard ``Station - Supervision technique`` reste dédié aux séries
temporelles détaillées :

.. code-block:: text

   https://localhost/grafana/d/station-supervision/station-supervision-technique?orgId=1&from=now-6h&to=now&refresh=5s

Il affiche :

* la température par emplacement ;
* l'humidité ;
* le courant de charge ;
* la tension ;
* la puissance ;
* les alertes récentes ;
* l'état des ESP32.

Il reprend les mêmes variables ``station``, ``borne`` et ``emplacement`` que le
dashboard d'accueil afin de conserver le même périmètre d'analyse.

Cette supervision technique complète l'interface web métier. L'application web
reste destinée aux utilisateurs, administrateurs et techniciens ; Grafana sert à
visualiser rapidement les séries temporelles et les incidents techniques.

Alertes provisionnées
---------------------

Le fichier ``grafana/provisioning/alerting/station-alerts.yml`` provisionne les
alertes Grafana de production. Elles sont évaluées toutes les minutes sur la
datasource ``station-timescaledb`` :

* ``ESP32 offline`` : un ESP32 ne publie plus de status ou de télémétrie récente ;
* ``Température ESP32 élevée`` : une mesure DHT22 dépasse le seuil critique ;
* ``Courant anormal`` : une mesure INA219 dépasse le seuil de courant attendu ;
* ``Charge sans session active`` : un device remonte ``charging`` sans session
  backend ouverte ;
* ``Session active sans télémétrie`` : une session ouverte ne reçoit plus de
  télémétrie récente.

Ces alertes ne remplacent pas les sécurités locales ESP32 : elles servent à la
supervision et à l'escalade opérateur.

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

Le choix MQTT reste pertinent pour cette chaîne IoT : les messages sont courts,
fréquents et naturellement organisés par topics. Les ESP32 n'ont pas besoin de
connaître les endpoints HTTP du backend ; ils publient leurs états sur
``station/<slot_id>/telemetry`` et écoutent les commandes sur
``station/<slot_id>/cmd``. Le broker local sert ainsi de point de découplage
entre l'embarqué, le Raspberry, la simulation et l'ingestion Django.
