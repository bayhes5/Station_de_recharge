Kiosque Raspberry Pi
====================

Cette page documente le rôle du Raspberry Pi dans la station. Le Raspberry ne
remplace pas le backend : il représente le terminal local de la borne, lit les
moyens d'accès, affiche l'interface tactile et relaie les commandes vers les
ESP32.

Responsabilités
---------------

Le kiosque Raspberry assure cinq responsabilités limitées et vérifiables :

* servir l'interface locale de borne sur le port ``9000`` ;
* lire ou recevoir les scans RFID ;
* appeler les endpoints terminal du backend ;
* conserver un cache local d'autorisations déjà synchronisées pour le mode
  dégradé ;
* publier les commandes MQTT vers les ESP32 et attendre leur acquittement.

La décision métier reste côté Django. Le Raspberry ne crée pas une réservation,
ne modifie pas les droits d'accès et ne décide pas seul d'ouvrir un emplacement
en mode nominal.

Fichiers principaux
-------------------

``raspberry/app/main.py``
   Petit serveur HTTP local. Il sert l'interface, expose les endpoints RFID,
   proxyfie les appels terminal autorisés vers Django et publie les commandes
   locales vers MQTT.

``raspberry/app/app.js``
   Logique de l'interface kiosque. Elle gère les parcours RFID, QR borne,
   session mobile, code de réservation et mode dégradé.

``raspberry/app/rfid_reader.py``
   Couche de lecture RFID. Le backend ``acr122u`` utilise PC/SC pour lire l'UID
   du badge ACR122U avec la commande ``FF CA 00 00 00``.

``raspberry/app/mqtt_client.py``
   Client MQTT local. Il publie les commandes sur ``station/<slot_id>/cmd`` et
   attend un ACK sur ``station/<slot_id>/ack``.

``raspberry/app/charge_state.py``
   Machine d'état locale persistée en SQLite. Elle empêche les doubles
   commandes ``START`` / ``STOP`` sur un même emplacement et rend visible l'état
   opérationnel courant côté Raspberry.

``raspberry/app/offline_store.py``
   Cache SQLite local utilisé uniquement lorsque le backend est indisponible.

Variables d'environnement
-------------------------

Les variables minimales pour tester sur un Raspberry physique sont :

.. code-block:: bash

   export BACKEND_API_BASE_URL=http://<ip-backend>:8000/api
   export MQTT_HOST=localhost
   export MQTT_PORT=1883
   export MQTT_BASE_TOPIC=station
   export MQTT_ACK_REQUIRED=true
   export TERMINAL_API_SECRET=<même-secret-que-le-backend>
   export TERMINAL_STATION_ID=<id-station>
   export TERMINAL_BORNE_ID=<id-borne>
   export CHARGE_STATE_DB_PATH=charge_state.sqlite3
   export RFID_READER_BACKEND=acr122u

Pour un réseau de production, ``MQTT_BASE_TOPIC`` peut intégrer la station et la
borne, par exemple ``station/<station_id>/<borne_id>``. Le Raspberry publiera
alors les commandes sur ``station/<station_id>/<borne_id>/<slot_id>/cmd`` et
attendra les ACK sur ``station/<station_id>/<borne_id>/<slot_id>/ack``.

En production, Mosquitto tourne sur le Raspberry : ``MQTT_HOST=localhost`` pour
le kiosque, tandis que les ESP32 utilisent l'adresse IP Wi-Fi du Raspberry. En
développement, si le backend et Mosquitto tournent sur le PC dans Docker,
``<ip-backend>`` correspond à l'adresse du PC sur le réseau Wi-Fi local et
``MQTT_HOST`` peut pointer vers cette même adresse.

Lecture RFID ACR122U
--------------------

Paquets système recommandés sur Raspberry Pi OS :

.. code-block:: bash

   sudo apt update
   sudo apt install pcscd pcsc-tools python3-dev swig
   sudo systemctl enable --now pcscd

Vérifier que le lecteur est détecté :

.. code-block:: bash

   pcsc_scan

Installer les dépendances Python :

.. code-block:: bash

   cd raspberry/app
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt

Lancer le kiosque :

.. code-block:: bash

   python main.py

Tester la lecture :

.. code-block:: bash

   curl http://localhost:9000/rfid/status
   curl http://localhost:9000/rfid/scan

Pour un test sans lecteur, laisser ``RFID_READER_BACKEND=manual`` et injecter un
UID :

.. code-block:: bash

   curl -X POST http://localhost:9000/rfid/scan \
     -H "Content-Type: application/json" \
     -d '{"uid":"04A3BC89F2"}'

Parcours d'accès nominal
------------------------

Le parcours nominal avec badge RFID est le suivant :

1. l'utilisateur présente son badge à la borne ;
2. le Raspberry lit l'UID et déclenche l'authentification terminal ;
3. Django vérifie le badge, la réservation active, la station attendue et le
   créneau ;
4. Django crée ou retrouve la session de charge ;
5. le Raspberry publie ``START`` sur ``station/<slot_id>/cmd`` ;
6. l'ESP32 acquitte la commande sur ``station/<slot_id>/ack`` ;
7. l'ESP32 déverrouille, attend câble et boîtier fermé, puis démarre le relais.

Le même principe s'applique aux accès par QR ou code : la validation précède
toujours la commande physique.

Cas couverts par le kiosque
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Le kiosque doit couvrir les situations suivantes :

* badge RFID connu, réservation active sur cette station, démarrage autorisé ;
* badge inconnu, badge révoqué ou réservation absente, accès refusé ;
* QR de réservation scanné par un lecteur physique, puis validation par Django ;
* téléphone utilisateur scannant le QR de session affiché par la borne ;
* code SMS temporaire de 8 caractères ``0-9/A-D`` saisi avec le code de
  réservation ;
* association d'un badge avec un code court généré depuis le profil web ;
* mauvaise station, mauvaise borne ou mauvais emplacement, avec message explicite ;
* backend indisponible, avec bascule limitée vers le cache local si le droit a
  déjà été synchronisé.

Session mobile et QR de borne
-----------------------------

Le QR affiché par la borne ne correspond pas directement à une réservation. Il
ouvre une session de borne temporaire. L'utilisateur scanne ce QR avec son
téléphone, se connecte à la PWA, choisit ou confirme sa réservation, puis le
backend autorise cette session de borne.

Ce choix évite de demander un code de réservation au départ. L'identité et la
réservation sont apportées par la session mobile authentifiée, tandis que le QR
de borne sert seulement à dire : "je suis devant cette borne".

Le QR de borne expire rapidement. S'il expire, le kiosque doit en générer un
nouveau. Il ne doit jamais être confondu avec le QR de réservation affiché dans
l'espace utilisateur : le QR de réservation identifie une réservation, alors que
le QR de borne identifie une session temporaire entre un téléphone et une borne.

Les scénarios détaillés, y compris les refus et les bascules, sont décrits dans
:doc:`user_scenarios`.

Mode dégradé
------------

Le mode dégradé s'appuie sur ``offline_store.py``. Le Raspberry synchronise à
l'avance les autorisations proches du créneau via le backend, puis peut les
vérifier localement si l'API devient indisponible.

Le backend transmet aussi les marges de validation temporelle :
``start_grace_minutes`` et ``end_grace_minutes``. Le cache local les applique
pour garder le même comportement qu'en ligne : arrivée légèrement anticipée et
courte tolérance après la fin du créneau. Par défaut, l'arrivée anticipée est
limitée à 5 minutes et la tolérance de fin à 10 minutes. En mode dégradé, le
cache refuse aussi une ouverture anticipée si l'emplacement est encore couvert
par le créneau précédent.

Règles de sécurité :

* le cache ne crée aucun nouveau droit ;
* les secrets restent stockés sous forme de hash ;
* la portée est limitée à la station déclarée par ``TERMINAL_STATION_ID`` et,
  sur une installation réelle, à la borne déclarée par ``TERMINAL_BORNE_ID`` ;
* les événements offline sont rejoués au backend dès que la communication
  revient ;
* en cas d'ambiguïté ou de cache expiré, l'accès doit être refusé.

Commandes MQTT vers ESP32
-------------------------

Commande publiée par le Raspberry :

.. code-block:: json

   {
     "command_id": "uuid-ou-token-court",
     "action": "START",
     "session_id": "<uuid-session>"
   }

Topic :

.. code-block:: text

   station/<slot_id>/cmd

Si la session backend contient un ``mqtt_prefix`` de borne, le kiosk publie sur
le topic structuré correspondant :

.. code-block:: text

   station/<mqtt_prefix>/<slot_id>/cmd

Le même préfixe est utilisé pour attendre l'ACK :

.. code-block:: text

   station/<mqtt_prefix>/<slot_id>/ack

Cela permet à deux bornes différentes d'utiliser chacune ``slot1`` sans risque
de commander le mauvais ESP32. Si ``MQTT_BASE_TOPIC`` est déjà configuré avec le
préfixe complet de la borne, le Raspberry ne le duplique pas.

ACK attendu :

.. code-block:: json

   {
     "command_id": "même-valeur",
     "action": "START",
     "status": "accepted",
     "message": "Emplacement reserve.",
     "state": "reserved",
     "slot_id": "slot1",
     "session_id": "<uuid-session>"
   }

En développement, ``MQTT_ACK_REQUIRED=False`` permet de tester l'interface sans
ESP32. Sur une borne réelle, ``MQTT_ACK_REQUIRED=True`` doit être utilisé afin
de refuser le démarrage si l'emplacement ne confirme pas la commande.

Le kiosk distingue deux notions :

* ``ack_received`` : un message a bien été reçu sur le canal ``ack`` ;
* ``command_confirmed`` : cet ACK confirme réellement l'action demandée.

Un ACK ``error``, ``rejected``, ``denied``, ``failed`` ou ``fault`` est toujours
traité comme un échec. En production, un ACK reçu mais non confirmant, par
exemple ``status=stopped`` pour une commande ``START``, bloque aussi la suite du
parcours quand ``MQTT_ACK_REQUIRED=True``.

Machine d'état locale
---------------------

Le Raspberry conserve aussi un état local par emplacement dans
``CHARGE_STATE_DB_PATH``. Cette couche ne remplace pas le backend et ne crée
aucun droit d'accès ; elle sert uniquement à protéger l'exécution physique
locale.

États utilisés :

.. code-block:: text

   idle          : aucun ordre local en cours
   reserved      : réservation connue localement, avant validation d'accès
   access_validated : accès validé côté kiosk, commande START prête à partir
   waiting_plug  : START confirmé par l'ESP32, attente câble + boîtier fermé
   charging      : charge confirmée active
   stopping      : STOP demandé, attente confirmation ou clôture
   stopped       : session arrêtée localement
   error         : état incohérent ou commande non confirmée

Règles principales :

* un ``START`` est refusé si l'emplacement est déjà ``reserved``,
  ``access_validated``, ``waiting_plug``, ``charging`` ou ``stopping`` ;
* un ``STOP`` doit porter le même ``session_id`` que la session locale active ;
* un ACK ESP32 non confirmant fait passer l'emplacement en ``error`` ;
* l'état ``error`` impose une vérification technicien avant de relancer une
  charge, car l'état physique réel peut être incertain ;
* ``GET /charge/state`` permet de consulter les états locaux depuis le
  Raspberry ;
* ``POST /charge/state/reset`` réinitialise un emplacement après intervention
  technicien. Si ``TERMINAL_API_SECRET`` est configuré, l'appel doit fournir le
  même secret dans l'en-tête ``X-Terminal-Secret``.

Contrôles avant démonstration
-----------------------------

Avant une démonstration locale, vérifier :

.. code-block:: bash

   curl http://localhost:9000/offline/status
   curl http://localhost:9000/rfid/status
   docker compose ps backend mqtt mqtt-bridge celery grafana
   docker compose exec mqtt mosquitto_sub -h localhost -t 'station/#' -v -C 5 -W 10

Le kiosque doit pouvoir afficher son état, lire ou recevoir un UID RFID, joindre
le backend en mode nominal et publier une commande MQTT vers le slot attendu.
