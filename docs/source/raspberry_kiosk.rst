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

Parcours écran de l'interface tactile
-------------------------------------

L'interface du kiosque est pensée pour un écran tactile Waveshare en résolution
``1024x600``. L'objectif est de limiter les actions devant la borne et de ne pas
afficher de vocabulaire technique à l'utilisateur final.

Le parcours nominal est le suivant :

1. l'écran d'accueil affiche uniquement l'action principale : présenter le badge
   RFID ;
2. les moyens secondaires restent disponibles en bas de l'écran : téléphone,
   code SMS, QR de réservation et association de badge ;
3. aucune action de charge n'est visible avant la validation de l'accès ;
4. après validation, l'écran ``Recharger à l'emplacement X`` affiche
   l'emplacement attribué et demande de brancher le câble ;
5. dès que le câble est détecté par l'ESP32, le Raspberry publie
   automatiquement ``START`` ;
6. pendant la charge, l'écran ``Chargement en cours`` affiche l'emplacement actif
   et le bouton ``Arrêter la charge`` ;
7. l'arrêt publie ``STOP`` vers l'ESP32, clôture la session côté backend, puis
   revient au parcours d'accueil.

Les écrans secondaires ont un rôle strict :

* ``Téléphone`` affiche un QR de session mobile temporaire. Ce QR ne correspond
  pas à une réservation : il relie le téléphone à cette borne, puis l'utilisateur
  choisit sa réservation depuis la PWA.
* ``Code SMS`` demande deux valeurs : la référence de réservation et le code SMS
  temporaire. Le clavier virtuel reprend volontairement l'alphabet limité
  ``0-9`` et ``A-D`` pour rester cohérent avec un clavier matriciel physique.
* ``QR réservation`` attend le QR généré lors de la réservation et reçu par
  e-mail ou affiché dans l'application.
* ``Associer badge`` demande le code d'association généré depuis le profil web,
  puis attend le passage du badge RFID.

L'interface revient automatiquement à l'accueil après une période d'inactivité
sur les écrans d'accès. La durée par défaut est ``120`` secondes et peut être
modifiée avec le paramètre ``idle_timeout`` dans l'URL ou avec
``terminalIdleTimeoutSeconds`` dans le stockage local du navigateur. L'écran de
charge active ne revient pas automatiquement à l'accueil afin de laisser
l'utilisateur arrêter explicitement la charge.

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

Procédure complète d'installation locale
----------------------------------------

Cette procédure correspond au scénario testé avec un Raspberry physique, un
écran tactile Waveshare, un lecteur RFID ACR122U et le backend lancé sur le PC
dans Docker. Le Raspberry, le PC et les ESP32 doivent être connectés au même
réseau Wi-Fi.

1. Préparer le PC backend
~~~~~~~~~~~~~~~~~~~~~~~~~

Sur le PC qui exécute Docker, relever l'adresse IPv4 Wi-Fi. Sous Windows :

.. code-block:: powershell

   ipconfig

Dans le projet, mettre à jour ``.env`` avec cette adresse, ou lancer :

.. code-block:: powershell

   .\scripts\update-local-ip.ps1
   docker compose up -d --force-recreate backend frontend

Pour une mise à jour manuelle, vérifier au minimum :

.. code-block:: text

   ALLOWED_HOSTS=localhost,127.0.0.1,<ip-pc>,backend,django_app
   FRONTEND_BASE_URL=http://<ip-pc>:5173
   CORS_ALLOWED_ORIGINS=http://<ip-pc>:5173,http://<ip-pc>:9000,...
   TERMINAL_API_SECRET=dev-terminal-secret

Le Raspberry doit pouvoir joindre le backend :

.. code-block:: bash

   curl -i http://<ip-pc>:8000/api/health/ready/

Une réponse ``200 OK`` confirme que le réseau, ``ALLOWED_HOSTS`` et le backend
sont corrects. En développement, ``DEV_AUTO_TRUST_PRIVATE_NETWORK=True`` accepte
automatiquement les IP privées du Wi-Fi. En production, une erreur
``DisallowedHost`` signifie que le domaine ou l'IP doit être déclaré
explicitement dans ``ALLOWED_HOSTS`` côté backend.

2. Copier le code sur le Raspberry
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Copier le contenu de ``raspberry/app`` sur le Raspberry, par exemple dans
``/home/btsciel/raspberry/app``. Ne pas copier les dossiers ``__pycache__``, les
bases SQLite de test, les environnements virtuels ni les secrets.

Exemple d'arborescence attendue :

.. code-block:: text

   /home/btsciel/raspberry/app/
     app.js
     charge_state.py
     index.html
     main.py
     mqtt_client.py
     mqtt_contract.py
     offline_store.py
     requirements.txt
     rfid_reader.py
     style.css

3. Installer les paquets système
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sur le Raspberry :

.. code-block:: bash

   sudo apt update
   sudo apt install -y python3-venv python3-dev swig pcscd pcsc-tools chromium
   sudo systemctl enable --now pcscd

Vérifier que le lecteur ACR122U est vu en USB :

.. code-block:: bash

   lsusb | grep -i '072f\|acr122'

La sortie attendue ressemble à :

.. code-block:: text

   Advanced Card Systems, Ltd ACR122U

4. Autoriser l'accès PC/SC à l'utilisateur du kiosque
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sur certaines versions récentes de Debian/Raspberry Pi OS, ``pcsc_scan`` peut
renvoyer :

.. code-block:: text

   SCardEstablishContext: Access denied.

Dans ce cas, créer une règle Polkit limitée à l'utilisateur qui lance le kiosque,
ici ``btsciel`` :

.. code-block:: bash

   sudo tee /etc/polkit-1/rules.d/49-pcscd-btsciel.rules >/dev/null <<'EOF'
   polkit.addRule(function(action, subject) {
       if ((action.id == "org.debian.pcsc-lite.access_pcsc" ||
            action.id == "org.debian.pcsc-lite.access_card") &&
           subject.user == "btsciel") {
           return polkit.Result.YES;
       }
   });
   EOF

   sudo chmod 0644 /etc/polkit-1/rules.d/49-pcscd-btsciel.rules
   sudo systemctl restart polkit pcscd

Tester ensuite :

.. code-block:: bash

   timeout 10 pcsc_scan

La sortie doit afficher :

.. code-block:: text

   ACS ACR122U PICC Interface

5. Installer les dépendances Python
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   cd /home/btsciel/raspberry/app
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   pip install pyscard==2.3.1

``pyscard`` est indispensable pour ``RFID_READER_BACKEND=acr122u``. Il est gardé
hors installation Docker par défaut, car le conteneur de développement ne pilote
pas le lecteur USB physique.

6. Lancer le serveur kiosque
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

En développement local avec le backend et Mosquitto sur le PC :

.. code-block:: bash

   cd /home/btsciel/raspberry/app
   source .venv/bin/activate

   export BACKEND_API_BASE_URL=http://<ip-pc>:8000/api
   export TERMINAL_API_SECRET=dev-terminal-secret
   export TERMINAL_STATION_ID=
   export TERMINAL_BORNE_ID=

   export MQTT_HOST=<ip-pc>
   export MQTT_PORT=1883
   export MQTT_BASE_TOPIC=station
   export MQTT_ACK_REQUIRED=false

   export RFID_READER_BACKEND=acr122u
   export RFID_DEBOUNCE_SECONDS=2

   python main.py

Le serveur doit afficher :

.. code-block:: text

   Kiosk server running on http://localhost:9000

Dans un second terminal SSH, vérifier :

.. code-block:: bash

   curl http://localhost:9000/offline/status
   curl http://localhost:9000/rfid/status

Résultat RFID attendu :

.. code-block:: json

   {
     "backend": "acr122u",
     "status": "running",
     "detail": "Lecteur PC/SC prêt: ACS ACR122U PICC Interface 00 00."
   }

7. Lancer l'interface sur l'écran tactile
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Depuis la session graphique du Raspberry :

.. code-block:: bash

   DISPLAY=:0 chromium --kiosk http://localhost:9000

Si l'écran reste noir ou en veille :

.. code-block:: bash

   DISPLAY=:0 xset s reset
   DISPLAY=:0 xset dpms force on
   DISPLAY=:0 xset s off -dpms

8. Tester l'association RFID
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Depuis l'application web, générer un code d'association RFID pour l'utilisateur.
Sur le kiosque :

1. ouvrir le menu d'association RFID ;
2. saisir le code d'association ;
3. présenter le badge sur l'ACR122U.

Vérifications attendues :

* côté Raspberry, ``/rfid/scan`` retourne un UID, par exemple ``A8A288EF`` ;
* côté backend, ``POST /api/terminal/link-rfid/`` répond ``201`` ;
* en base, un moyen d'accès ``RFID`` actif apparaît pour l'utilisateur ;
* le journal sécurité contient ``rfid_linked``.

9. Tester l'accès par badge
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Créer une réservation sur le même compte que le badge. Au début du créneau
autorisé, présenter le badge directement sur l'écran d'accueil du kiosque.

Vérifications attendues :

* le Raspberry lit l'UID du badge ;
* le backend reçoit ``POST /api/terminal/authenticate/`` ;
* une réponse ``200`` valide l'accès ;
* le kiosque affiche ``Recharger à l'emplacement X`` ;
* ``UNLOCK`` est publié sur MQTT pour ouvrir le boîtier ;
* la supervision admin reçoit un ACK ``UNLOCK`` et passe la session en
  ``waiting_plug`` ;
* ``START`` est publié automatiquement sur MQTT lorsque l'utilisateur a branché
  le câble et que le capteur remonte ``cable=true`` ;
* ``STOP`` clôture la session lorsque l'utilisateur arrête.

Si un autre badge est présenté, le backend peut répondre ``401``. Ce comportement
est normal si l'UID n'est pas associé au compte de la réservation.

10. Commandes de diagnostic utiles
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sur le Raspberry :

.. code-block:: bash

   curl http://localhost:9000/rfid/status
   curl http://localhost:9000/rfid/scan
   curl http://localhost:9000/offline/status
   curl http://localhost:9000/charge/state
   tail -f /home/btsciel/raspberry/app/kiosk.log
   journalctl -u pcscd -f

Sur le PC :

.. code-block:: powershell

   docker compose logs -f backend
   docker compose logs -f mqtt mqtt-bridge

Erreurs fréquentes :

* ``DisallowedHost`` : en développement, vérifier
  ``DEV_AUTO_TRUST_PRIVATE_NETWORK=True`` ; en production, ajouter le domaine ou
  l'IP dans ``ALLOWED_HOSTS`` ;
* ``Backend indisponible`` : vérifier ``BACKEND_API_BASE_URL`` sur le Raspberry ;
* ``Access denied`` avec PC/SC : appliquer la règle Polkit ;
* ``Lecteur ACR122U introuvable`` : vérifier ``lsusb``, ``pcscd`` et le câble USB ;
* aucun ``POST /api/terminal/authenticate/`` : le badge est lu mais l'interface
  n'a pas envoyé la validation, ou l'écran n'est pas sur le bon parcours ;
* ``401`` sur l'authentification : badge inconnu, badge différent ou réservation
  non active pour ce compte.

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
5. le Raspberry publie ``UNLOCK`` sur ``station/<slot_id>/cmd`` ;
6. l'ESP32 acquitte la commande et ouvre le boîtier par impulsion ;
7. le backend ingère l'ACK ``UNLOCK`` et la supervision affiche le dernier ordre
   ``UNLOCK`` / ``unlocked`` ;
8. l'utilisateur branche le câble ;
9. le Raspberry détecte ``cable=true`` dans la télémétrie de l'emplacement et
   publie ``START`` automatiquement ;
10. l'ESP32 vérifie le câble et le boîtier, puis démarre le relais de charge.

Si le capteur câble n'est pas encore câblé, l'ESP32 doit soit publier une vraie
télémétrie ``cable=true`` depuis le capteur, soit activer explicitement
``SIMULATE_CABLE_PRESENT_FOR_AUTO_START`` pour un essai de banc. Sans ce signal,
le kiosk reste volontairement sur l'écran de branchement et ne démarre pas la
charge.

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
     "message": "Emplacement réservé.",
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
   access_validated : accès validé côté kiosk, commande UNLOCK prête à partir
   waiting_plug  : boîtier ouvert, attente câble + boîtier fermé avant START
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
