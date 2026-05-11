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

``raspberry/app/offline_store.py``
   Cache SQLite local utilisé uniquement lorsque le backend est indisponible.

Variables d'environnement
-------------------------

Les variables minimales pour tester sur un Raspberry physique sont :

.. code-block:: bash

   export BACKEND_API_BASE_URL=http://<ip-backend>:8000/api
   export MQTT_HOST=<ip-broker-mqtt>
   export MQTT_PORT=1883
   export MQTT_BASE_TOPIC=station
   export TERMINAL_API_SECRET=<meme-secret-que-le-backend>
   export TERMINAL_STATION_ID=<id-station>
   export RFID_READER_BACKEND=acr122u

En développement, si le backend et Mosquitto tournent sur le PC dans Docker,
``<ip-backend>`` et ``<ip-broker-mqtt>`` correspondent à l'adresse du PC sur le
réseau Wi-Fi local.

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

Session mobile et QR de borne
-----------------------------

Le QR affiché par la borne ne correspond pas directement à une réservation. Il
ouvre une session de borne temporaire. L'utilisateur scanne ce QR avec son
téléphone, se connecte à la PWA, choisit ou confirme sa réservation, puis le
backend autorise cette session de borne.

Ce choix évite de demander un code de réservation au départ. L'identité et la
réservation sont apportées par la session mobile authentifiée, tandis que le QR
de borne sert seulement à dire : "je suis devant cette borne".

Mode dégradé
------------

Le mode dégradé s'appuie sur ``offline_store.py``. Le Raspberry synchronise à
l'avance les autorisations proches du créneau via le backend, puis peut les
vérifier localement si l'API devient indisponible.

Règles de sécurité :

* le cache ne crée aucun nouveau droit ;
* les secrets restent stockés sous forme de hash ;
* la portée est limitée à la station déclarée par ``TERMINAL_STATION_ID`` ;
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

ACK attendu :

.. code-block:: json

   {
     "command_id": "meme-valeur",
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
