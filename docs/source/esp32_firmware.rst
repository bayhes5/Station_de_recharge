Firmware ESP32
==============

Chaque emplacement de recharge est piloté par un ESP32 connecté au réseau Wi-Fi
local. L'ESP32 ne connaît pas les règles métier de réservation : il reçoit des
commandes déjà validées, applique les sécurités physiques et publie la
télémétrie.

Périmètre matériel
------------------

Le firmware de référence se trouve dans ``esp32/emplacement1/main.py``. Il sert
de base pour les trois emplacements en changeant uniquement :

* ``SLOT_ID`` ;
* ``CLIENT_ID`` ;
* les identifiants Wi-Fi ;
* l'adresse du broker MQTT local du Raspberry ;
* les pins réels des capteurs, relais et serrure.

Le code cible actuellement :

* un DHT22 pour température et humidité ;
* un capteur de courant analogique SEN0214 ;
* une tension fixe de prototype pour estimer puissance et énergie ;
* une sortie de serrure via relais actif-bas ;
* un relais de charge, un contact de boîtier et un détecteur de présence câble
  encore optionnels tant qu'ils ne sont pas câblés.

Configuration minimale
----------------------

Extrait de configuration :

.. code-block:: python

   WIFI_SSID = "WIFI_SSID"
   WIFI_PASSWORD = "WIFI_PASSWORD"
   MQTT_HOST = "192.168.1.10"  # IP du serveur Mosquitto
   MQTT_PORT = 1883
   MQTT_USER = "esp32_slot1"
   MQTT_PASSWORD = "mot-de-passe-mqtt"
   MQTT_BASE_TOPIC = "station"
   MQTT_TLS_ENABLED = False
   MQTT_TLS_CA_CERT_FILE = "certs/metropole-verte-root-ca.der"
   MQTT_TLS_SERVER_HOSTNAME = ""
   SLOT_ID = "slot1"
   CLIENT_ID = "esp32-slot1"

   DHT_PIN = 15
   CURRENT_SENSOR_MODE = "sen0214"
   ADC_CURRENT_PIN = 34
   VOLTAGE_SENSOR_MODE = "fixed"
   FIXED_BUS_VOLTAGE = 12.0
   LOCK_OUTPUT_ENABLED = True
   LOCK_PIN = 26
   LOCK_RELAY_ACTIVE_LOW = True
   LOCK_AUTO_RELOCK_SECONDS = 30
   CHARGE_RELAY_OUTPUT_ENABLED = False
   CHARGE_RELAY_PIN = 22

L'emplacement démarre verrouillé. La serrure testée physiquement utilise
``GPIO26`` avec un relais actif-bas : ``0`` alimente la serrure et ouvre, ``1``
remet le relais au repos. Le firmware ouvre donc la serrure lors de ``UNLOCK``
après authentification, puis programme un reverrouillage automatique non
bloquant au bout de ``30`` secondes si la charge n'est pas passée à l'état
``charging``. Cette fenêtre laisse le temps de brancher le câble sans alimenter
la serrure en continu et sans bloquer la boucle MQTT.

Le ``START`` est volontairement séparé de l'ouverture. Il ne démarre la charge
qu'après branchement du câble et vérification des capteurs disponibles. En
fonctionnement cible, le Raspberry envoie ``START`` automatiquement lorsque la
télémétrie ESP32 remonte ``cable=true`` pour l'emplacement autorisé.

Pour le prototype actuel, le capteur câble n'est pas encore câblé. Le kiosk peut
donc utiliser une mesure SEN0214 récente, ``current >= 0.1 A`` depuis moins de
15 secondes, comme équivalent provisoire d'un branchement détecté. Cette règle
est côté Raspberry/kiosk : l'ESP32 continue de publier ``current`` et garde la
vérification physique ``cable`` prioritaire dès que le capteur sera installé.
Le statut réel de l'emplacement est ensuite publié sur ``status`` et
``telemetry``.

Les voyants locaux donnent une lecture simple de l'état terrain :

* vert fixe : accès validé et attente de branchement ;
* vert clignotant : charge réellement en cours, état ``charging`` ;
* jaune : seuil d'alerte modérée, entre ``5 A`` et ``6 A`` ;
* rouge et buzzer : seuil critique, à partir de ``6 A``.

Pour la démonstration, la plage ``5 A <= current < 6 A`` sert à visualiser
l'avertissement jaune. À partir de ``6 A``, le seuil critique publie une alerte
``overcurrent``, active le rouge et le buzzer, puis arrête la charge localement.
Les états d'alerte jaune et rouge restent prioritaires sur le clignotement vert.

Déploiement avec Thonny
-----------------------

Cette méthode est adaptée au banc de test et au travail de ton collègue. Elle
reste manuelle mais permet de valider rapidement le câblage.

Procédure de test sur carte physique :

1. installer MicroPython sur l'ESP32 ;
2. ouvrir Thonny avec l'interpréteur MicroPython ESP32 ;
3. adapter ``WIFI_SSID``, ``WIFI_PASSWORD`` et ``MQTT_HOST`` ;
4. renseigner ``MQTT_USER`` et ``MQTT_PASSWORD`` si le broker sécurisé est actif ;
5. adapter ``SLOT_ID`` et ``CLIENT_ID`` pour l'emplacement ;
6. enregistrer ``esp32/emplacement1/main.py`` sur la carte sous le nom
   ``main.py`` ;
7. optionnel : enregistrer un fichier ``version.txt`` contenant uniquement la
   version à publier, par exemple ``1.2.0-lock-relay`` ;
8. redémarrer la carte ;
9. vérifier les topics MQTT depuis le PC ou le Raspberry.

Le point important est l'étape 6 : le fichier doit être enregistré **sur
l'ESP32** sous le nom exact ``main.py``. Si le fichier est seulement exécuté
depuis Thonny, il disparaît au redémarrage et ne se lance pas automatiquement.

Démarrage persistant MicroPython
--------------------------------

Au démarrage, MicroPython monte le système de fichiers interne de l'ESP32, puis
exécute les fichiers standards s'ils existent :

.. code-block:: text

   alimentation ESP32
   -> démarrage MicroPython
   -> montage du système de fichiers interne
   -> exécution optionnelle de boot.py
   -> exécution de main.py

``boot.py`` est optionnel. Pour ce projet, il est préférable de le garder absent
ou minimal, car un ``boot.py`` bloquant peut rendre la carte difficile à
récupérer. Le firmware métier doit rester dans ``main.py``. C'est ce fichier qui
contient la connexion Wi-Fi, la connexion MQTT, les lectures capteurs, la
serrure et la boucle de télémétrie.

Si ``main.py`` plante ou sort, MicroPython revient au REPL. Pour récupérer une
carte bloquée, ouvrir la console série, envoyer ``Ctrl-C`` puis supprimer ou
remplacer le fichier problématique :

.. code-block:: python

   import os
   os.remove("main.py")

Déploiement reproductible avec mpremote
---------------------------------------

Pour éviter les manipulations manuelles dans Thonny, utiliser ``mpremote``. Il
permet de copier les fichiers dans LittleFS, redémarrer l'ESP32 et ouvrir une
console série depuis un terminal.

Installer les outils sur le PC :

.. code-block:: powershell

   python -m pip install esptool mpremote

Identifier le port série :

.. code-block:: powershell

   mpremote connect list

Sous Windows, le port ressemble à ``COM5``. Sous Linux, il ressemble plutôt à
``/dev/ttyUSB0`` ou ``/dev/ttyACM0``.

Flasher MicroPython sur une carte neuve ou réinitialisée :

.. code-block:: powershell

   python -m esptool --chip esp32 --port COM5 erase_flash
   python -m esptool --chip esp32 --port COM5 --baud 460800 write_flash -z 0x1000 ESP32_GENERIC-<version>.bin

Le fichier ``ESP32_GENERIC-<version>.bin`` doit être téléchargé depuis la page
officielle MicroPython correspondant à la carte utilisée. Cette étape n'est pas
nécessaire à chaque mise à jour applicative : une fois MicroPython installé, on
copie seulement les fichiers Python.

Déployer le firmware applicatif :

.. code-block:: powershell

   mpremote connect COM5 fs cp esp32\emplacement1\main.py :main.py
   mpremote connect COM5 reset
   mpremote connect COM5 repl

Déployer aussi la version firmware affichée dans la supervision :

.. code-block:: powershell

   Set-Content -Path version.txt -Value "1.3.0-access-before-charge" -Encoding ASCII -NoNewline
   mpremote connect COM5 fs cp version.txt :version.txt
   mpremote connect COM5 reset

Le dépôt fournit un script PowerShell pour automatiser les copies courantes :

.. code-block:: powershell

   .\scripts\deploy-esp32-micropython.ps1 `
     -Port COM5 `
     -SourceDir esp32\emplacement1 `
     -FirmwareVersion "1.3.0-access-before-charge" `
     -OpenRepl

Avec MQTT TLS, ajouter le certificat racine converti en DER :

.. code-block:: powershell

   .\scripts\deploy-esp32-micropython.ps1 `
     -Port COM5 `
     -SourceDir esp32\emplacement1 `
     -FirmwareVersion "1.3.0-access-before-charge" `
     -RootCaPath certs\metropole-verte-root-ca.der `
     -OpenRepl

LittleFS sur l'ESP32
--------------------

LittleFS est le système de fichiers persistant monté par MicroPython dans la
flash de l'ESP32. Il sert à stocker les fichiers qui doivent survivre aux
redémarrages :

.. code-block:: text

   /
   ├── main.py
   ├── version.txt
   ├── certs/
   │   └── metropole-verte-root-ca.der
   └── spool/
       └── pending_telemetry.jsonl

Accéder au contenu avec ``mpremote`` :

.. code-block:: powershell

   mpremote connect COM5 fs ls :
   mpremote connect COM5 fs ls :certs
   mpremote connect COM5 fs cat :version.txt
   mpremote connect COM5 fs cp :main.py main-backup.py

Créer des dossiers :

.. code-block:: powershell

   mpremote connect COM5 fs mkdir :certs
   mpremote connect COM5 fs mkdir :spool

Dans le code MicroPython, l'accès se fait comme sur un petit système de fichiers
classique :

.. code-block:: python

   with open("spool/pending_telemetry.jsonl", "a") as spool:
       spool.write(payload + "\n")

Le journal LittleFS doit rester court. Il sert uniquement à éviter une perte de
traces pendant une coupure MQTT temporaire. La source durable de l'historique
reste la base PostgreSQL/TimescaleDB côté backend.

Sécurisation MQTT TLS
---------------------

Le mode de test actuel utilise MQTT sur ``1883`` avec identifiants et ACL. Pour
une installation plus robuste, Mosquitto peut être exposé en TLS sur ``8883``
avec la CA locale ``Metropole Verte`` décrite dans la procédure Debian.

Chaîne cible :

.. code-block:: text

   ESP32
   -> Wi-Fi WPA2/WPA3
   -> MQTT TLS 8883
   -> Mosquitto
   -> mqtt-bridge backend
   -> TimescaleDB / Grafana

L'ESP32 ne doit jamais contenir la clé privée de la CA. Il embarque uniquement le
certificat racine public ``root_ca.crt`` converti en DER, car MicroPython avec le
port mbedTLS attend ``cadata`` sous forme de certificat DER.

Conversion du certificat racine :

.. code-block:: powershell

   openssl x509 -in mosquitto\certs\root_ca.crt -outform DER -out certs\metropole-verte-root-ca.der

Copie dans LittleFS :

.. code-block:: powershell

   mpremote connect COM5 fs mkdir :certs
   mpremote connect COM5 fs cp certs\metropole-verte-root-ca.der :certs\metropole-verte-root-ca.der

Configuration firmware :

.. code-block:: python

   MQTT_HOST = "mqtt.station.local"
   MQTT_PORT = 8883
   MQTT_TLS_ENABLED = True
   MQTT_TLS_CA_CERT_FILE = "certs/metropole-verte-root-ca.der"
   MQTT_TLS_SERVER_HOSTNAME = "mqtt.station.local"

Le nom ``MQTT_TLS_SERVER_HOSTNAME`` doit correspondre à un SAN du certificat
Mosquitto. Si l'ESP32 se connecte à une IP, cette IP doit également être
présente dans le certificat. Sans cela, la validation TLS échoue, ce qui est le
comportement attendu.

Sous MicroPython, le module ``ssl`` expose une interface simplifiée. Sur ESP32,
la pile TLS sous-jacente repose sur l'intégration ESP-IDF, généralement basée
sur mbedTLS. Dans le firmware du projet, ``MQTT_TLS_ENABLED=True`` force :

* l'utilisation de ``ssl=True`` dans le client MQTT ;
* la lecture du certificat CA depuis LittleFS ;
* ``cert_reqs=ssl.CERT_REQUIRED`` ;
* l'utilisation de ``server_hostname`` pour vérifier le nom du broker.

Si la version de ``umqtt.simple`` installée ne supporte pas ``ssl_params``, le
firmware refuse de démarrer en TLS plutôt que d'établir une connexion chiffrée
sans validation correcte du certificat.

Commande d'écoute :

.. code-block:: bash

   docker compose exec mqtt mosquitto_sub -h localhost -t 'station/#' -v

En production, ``MQTT_HOST`` doit être l'adresse IP du Raspberry sur le réseau
Wi-Fi local de la borne. En développement, si l'ESP32 utilise le broker Docker
du PC, ``MQTT_HOST`` doit être l'adresse IP du PC sur le même réseau Wi-Fi, pas
``localhost``. Depuis un ESP32, ``localhost`` désigne l'ESP32 lui-même.

Topics MQTT
-----------

Topics publiés par l'ESP32 :

.. code-block:: text

   station/<slot_id>/ack
   station/<slot_id>/telemetry
   station/<slot_id>/status
   station/<slot_id>/alert

Topic écouté par l'ESP32 :

.. code-block:: text

   station/<slot_id>/cmd

Pour une borne de production, ``MQTT_BASE_TOPIC`` peut être configuré avec un
préfixe plus précis, par exemple ``station/<station_id>/<borne_id>``. Les topics
deviennent alors ``station/<station_id>/<borne_id>/<slot_id>/telemetry`` et
``station/<station_id>/<borne_id>/<slot_id>/cmd``. Le firmware n'a pas besoin de
logique métier supplémentaire : il concatène toujours ``MQTT_BASE_TOPIC``,
``SLOT_ID`` et le suffixe.

Le backend retire le préfixe global ``station`` et compare la partie
``<station_id>/<borne_id>`` au champ ``mqtt_prefix`` de la borne. En production,
chaque borne doit donc avoir un ``mqtt_prefix`` stable, par exemple
``station-centre/borne-1``. Cela évite qu'un ``slot1`` publié par deux bornes
différentes soit rattaché au mauvais emplacement.

Commandes acceptées
-------------------

Payload de commande :

.. code-block:: json

   {
     "command_id": "uuid-ou-token-court",
     "action": "START",
     "session_id": "<uuid-session>"
   }

Actions :

``START``
   Démarre uniquement la charge électrique. L'ouverture du boîtier est gérée
   avant par ``UNLOCK``. Le ``START`` est envoyé automatiquement par le Raspberry
   lorsque la télémétrie de l'emplacement remonte ``cable=true`` ou, en mode
   prototype sans capteur câble, lorsqu'un courant SEN0214 récent dépasse
   ``0.1 A``. L'ESP32 doit encore vérifier localement le câble et le boîtier
   avant d'activer le relais de charge quand ces capteurs seront câblés.

``STOP``
   Arrête la charge, déverrouille et publie un statut d'arrêt.

``LOCK``
   Verrouille l'emplacement.

``UNLOCK``
   Déverrouille l'emplacement.

ACK de commande
---------------

Chaque commande doit produire un acquittement :

.. code-block:: json

   {
     "command_id": "même-valeur-que-la-commande",
     "action": "START",
     "status": "accepted",
     "message": "Emplacement réservé.",
     "state": "reserved",
     "slot_id": "slot1",
     "client_id": "esp32-slot1",
     "firmware_version": "1.0.0",
     "hardware_mac": "AA:BB:CC:DD:EE:FF",
     "ip_address": "192.168.1.42",
     "session_id": "<uuid-session>"
   }

Le Raspberry utilise cet ACK pour confirmer que l'ESP32 a bien reçu et appliqué
la commande. En production, une commande sans ACK doit être traitée comme un
échec opérationnel.

Un ACK doit reprendre le ``command_id`` et, si le champ ``action`` est présent,
il doit correspondre à l'action demandée. Côté Raspberry, un ACK reçu n'est
accepté comme confirmation que si son ``status`` est cohérent avec la commande :

* ``START`` : ``accepted``, ``reserved``, ``ready``, ``charging`` ou
  ``charging_started`` ;
* ``STOP`` : ``accepted``, ``stopped`` ou ``idle`` ;
* ``LOCK`` : ``accepted`` ou ``locked`` ;
* ``UNLOCK`` : ``accepted`` ou ``unlocked``.

Les statuts ``error``, ``rejected``, ``denied``, ``failed`` et ``fault`` doivent
être réservés aux refus explicites. Ils bloquent le parcours kiosk même en mode
développement.

Le backend ingère également les ACK via le bridge MQTT. Le dernier
acquittement connu est conservé sur le ``Device`` pour la supervision :
identifiant de commande, action, statut, message lisible et horodatage. Cette
trace ne remplace pas les statuts ``reserved`` ou ``charging_started`` ; elle
sert à prouver que l'ordre ``START``, ``STOP``, ``LOCK`` ou ``UNLOCK`` a été reçu
par l'ESP32.

Machine d'état
--------------

Les états embarqués restent volontairement simples. Ils décrivent uniquement
l'état physique de l'emplacement, pas la décision métier de réservation :

.. code-block:: text

   idle      : emplacement au repos
   reserved  : accès autorisé, attente câble + boîtier fermé
   charging  : relais de charge actif

Transitions principales :

* ``UNLOCK`` fait passer l'emplacement en attente de branchement ;
* ``START`` est reçu automatiquement après détection câble ;
* câble présent et boîtier fermé font passer l'emplacement à ``charging`` ;
* ``STOP`` ou une anomalie font revenir à ``idle``.

Pour les essais sans capteur Hall câblé, le firmware conserve
``SIMULATE_CABLE_PRESENT_FOR_AUTO_START = False`` par défaut. Tant que cette
valeur reste à ``False`` et que ``PHYSICAL_INPUTS_ENABLED = False``, la
télémétrie publie ``cable=null``. Le kiosk utilise alors la mesure ``current`` du
SEN0214 comme fallback prototype : ``START`` part si la mesure est récente et
supérieure ou égale à ``0.1 A``. Mettre ``SIMULATE_CABLE_PRESENT_FOR_AUTO_START``
à ``True`` reste possible pour un essai de banc, mais ce n'est plus nécessaire
si le générateur produit déjà un courant mesurable.

Le Raspberry maintient en parallèle une machine d'état locale plus explicite
(``reserved``, ``access_validated``, ``waiting_plug``, ``charging``,
``stopping``, ``stopped``, ``error``). Elle évite les doubles commandes et
signale les états douteux côté kiosk. L'ESP32 reste responsable des sécurités
immédiates : relais, serrure, câble, boîtier, courant et température.

Sécurités locales
-----------------

Pendant ``charging``, l'ESP32 arrête la charge si :

* le boîtier est ouvert ;
* le câble est retiré ;
* le courant dépasse ``MAX_CURRENT_A`` ;
* la température dépasse ``MAX_TEMPERATURE_C``.

Ces règles doivent rester locales. Elles ne doivent pas attendre une réponse du
backend, car elles protègent l'utilisateur, le matériel et la traçabilité en cas
de coupure réseau.

Télémétrie capteurs
-------------------

Payload publié sur ``station/<slot_id>/telemetry`` :

.. code-block:: json

   {
     "slot_id": "slot1",
     "session_id": "<uuid-session>",
     "state": "charging",
     "client_id": "esp32-slot1",
     "firmware_version": "1.0.0",
     "hardware_mac": "AA:BB:CC:DD:EE:FF",
     "ip_address": "192.168.1.42",
     "current": 1.42,
     "voltage": 42.1,
     "power": 59.78,
     "energy_kwh": 0.0,
     "temperature": 31.5,
     "humidity": 45.0,
     "door": true,
     "cable": true,
     "lock": true
   }

Le firmware lit actuellement le DHT22, le SEN0214 et l'état logique de serrure.
La tension est une valeur fixe de prototype tant qu'un capteur de tension réel
n'est pas câblé. Les champs porte et câble restent absents ou ``null`` tant que
les contacts physiques ne sont pas branchés.

Les champs d'inventaire sont publiés automatiquement par le firmware :

* ``slot_id`` identifie l'emplacement logique et le topic MQTT ;
* ``hardware_mac`` identifie la carte ESP32 physique ;
* ``ip_address`` décrit l'adresse Wi-Fi courante ;
* ``firmware_version`` permet au backend de détecter une version non conforme
  avec ``EXPECTED_ESP32_FIRMWARE_VERSION``.

Le backend ne demande pas une saisie manuelle de ces informations : elles sont
remontées automatiquement par le firmware dans les messages ``status``, ``ack``
et ``telemetry``. L'administrateur peut ensuite définir une version attendue
par équipement ou planifier une cible OTA depuis l'API admin. Les champs
``firmware_update_status``, ``ota_target_version``, ``ota_update_url``,
``ota_requested_at``, ``ota_completed_at`` et ``ota_last_error`` servent à
tracer la décision et l'état de conformité sans donner d'accès global à Grafana
aux techniciens terrain.

La MAC et l'adresse IP sont de vraies données lues au runtime par
``network.WLAN``. La version firmware ne peut pas être devinée automatiquement
par l'ESP32 : elle doit être embarquée au moment du flash. Le firmware lit
d'abord ``version.txt`` sur LittleFS s'il existe, puis retombe sur la constante
``FIRMWARE_VERSION`` de ``main.py``. Cette approche évite de modifier toute la
logique du firmware pour une démonstration : on peut livrer le même ``main.py``
et changer seulement le petit fichier de version lors du flash.

Chaîne de supervision
---------------------

La télémétrie ESP32 suit ce chemin :

1. publication MQTT par l'ESP32 ;
2. réception par Mosquitto ;
3. consommation par ``mqtt-bridge`` ;
4. tâche Celery ``api.process_mqtt_message`` ;
5. stockage dans ``Device``, ``CapteurData`` et éventuellement
   ``SessionTelemetry`` ;
6. lecture par l'API admin et Grafana.

Pour tester sans ESP32 physique :

.. code-block:: bash

   docker compose up -d backend mqtt mqtt-bridge celery grafana
   docker compose run --rm mqtt-simulator python manage.py simulate_mqtt_telemetry --slots slot1 --scenario normal --interval 1 --count 5

Vérifier le stockage :

.. code-block:: bash

   docker compose exec backend python manage.py shell -c "from api.models import CapteurData; print(CapteurData.objects.count())"

Simulation Wokwi
----------------

Le dossier ``esp32/wokwi/`` permet de tester la logique sans matériel. Il publie
les mêmes champs que le firmware physique et accepte les mêmes commandes MQTT.

En local, privilégier le broker Docker du projet pour valider toute la chaîne
avec Grafana. Le broker public ``test.mosquitto.org`` reste utile pour une
démonstration isolée, mais il ne doit pas être utilisé comme dépendance de
production.

Limites actuelles
-----------------

Le firmware est prêt pour les tests d'intégration, mais certains points doivent
être validés sur le matériel final :

* sens électrique réel des contacts ``door`` et ``cable`` ;
* comportement mécanique réel de la serrure sur plusieurs cycles ;
* calibration SEN0214 et, plus tard, capteur tension ou INA219 selon le shunt ;
* seuils réels de courant et température ;
* stratégie de reconnexion Wi-Fi/MQTT longue durée ;
* journal local LittleFS pour événements non transmis.
