Installation sur serveur Debian
================================

Cette procédure décrit l'installation de la partie backend sur un serveur
Debian dédié. Elle vise un serveur d'intégration ou une production académique
maîtrisée : API Django, base TimescaleDB/PostgreSQL, Redis, Celery, Grafana,
Mailpit et reverse proxy Nginx. Le broker Mosquitto de terrain est porté par le
Raspberry de la borne.

La procédure utilise ``docker-compose.prod.yml``. Ce profil production sépare le
mode développement du mode serveur : le backend est lancé en ASGI avec Daphne,
le frontend est buildé puis servi par Nginx, les fichiers statiques Django sont
collectés dans un volume dédié, et les ports internes ne sont pas publiés
directement sur le réseau. En architecture terrain, le broker Mosquitto de la
borne tourne sur le Raspberry physique ; le service Docker ``mqtt`` du fichier
production est conservé uniquement pour la simulation ou un banc de test local.

Architecture cible
------------------

Le serveur Debian héberge les services suivants :

.. list-table::
   :header-rows: 1

   * - Service
     - Rôle
     - Exposition attendue
   * - ``reverse-proxy``
     - Entrée HTTPS, routage vers l'API, le frontend et Grafana
     - Ports ``80`` et ``443``
   * - ``backend``
     - API Django, admin, logique métier, endpoints kiosk/mobile
     - Interne, exposé via Nginx
   * - ``db``
     - PostgreSQL avec TimescaleDB pour les données métier et séries temporelles
     - Interne uniquement
   * - ``redis``
     - Cache, broker Celery et Channels
     - Interne uniquement
   * - ``celery`` et ``celery-beat``
     - Tâches asynchrones, alertes, contrôles périodiques
     - Interne uniquement
   * - ``mqtt``
     - Broker Mosquitto de simulation si aucun Raspberry n'est disponible
     - Profil ``simulation`` uniquement
   * - ``mqtt-bridge``
     - Ingestion des télémétries depuis le broker Raspberry vers la base
     - Interne uniquement
   * - ``grafana``
     - Supervision technique
     - Via ``/grafana/`` sur Nginx
   * - ``mailpit``
     - SMTP et boîte de réception de test
     - Local ou tunnel SSH uniquement

Le kiosque Raspberry et le broker Mosquitto de terrain ne sont pas lancés sur le
serveur Debian en production. Ils tournent sur le Raspberry physique raccordé à
l'écran tactile, au lecteur RFID, au réseau de la borne et aux ESP32. Les
services Docker ``raspberry`` et ``mqtt`` de ``docker-compose.prod.yml`` sont
réservés à la simulation avec le profil ``simulation``.

Pour tester ponctuellement le kiosque dans la stack serveur, utiliser :

.. code-block:: bash

   docker compose -f docker-compose.prod.yml --profile simulation up -d mqtt raspberry

Ce mode ne remplace pas le déploiement terrain : en exploitation réelle, le
Raspberry lance ``raspberry/app/main.py`` localement, héberge Mosquitto et joint
l'API serveur via ``BACKEND_API_BASE_URL``.

Pré-requis
----------

Prévoir :

* un serveur Debian 12 ou 13 à jour ;
* un compte utilisateur avec ``sudo`` ;
* une adresse IP fixe ou une réservation DHCP ;
* un nom DNS si le serveur doit être joint par un domaine ;
* les ports ``80`` et ``443`` ouverts vers le serveur ;
* une route réseau entre le serveur Debian et le Raspberry qui héberge Mosquitto ;
* le port ``1883`` ou ``8883`` ouvert sur le Raspberry uniquement depuis le
  réseau local des ESP32 et du serveur selon la configuration MQTT ;
* au moins 4 Go de RAM pour un confort correct avec Grafana, Django, Celery et
  TimescaleDB.

Ne pas exposer directement sur Internet les ports ``5432``, ``6379``, ``8000``,
``3000``, ``5173``, ``8025`` ou ``1025``. Le port MQTT du Raspberry doit rester
sur le réseau terrain.

Installation système
--------------------

Mettre Debian à jour et installer les outils de base :

.. code-block:: bash

   sudo apt update
   sudo apt upgrade -y
   sudo apt install -y ca-certificates curl gnupg git ufw openssl

Installer Docker Engine et le plugin Docker Compose :

.. code-block:: bash

   sudo install -m 0755 -d /etc/apt/keyrings
   curl -fsSL https://download.docker.com/linux/debian/gpg \
     | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
   sudo chmod a+r /etc/apt/keyrings/docker.gpg

   echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
     | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

   sudo apt update
   sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

Autoriser l'utilisateur courant à lancer Docker sans ``sudo`` :

.. code-block:: bash

   sudo usermod -aG docker "$USER"

Se déconnecter puis se reconnecter avant de continuer. Vérifier ensuite :

.. code-block:: bash

   docker --version
   docker compose version

Récupération du projet
----------------------

Installer le projet dans ``/opt/station`` :

.. code-block:: bash

   sudo mkdir -p /opt/station
   sudo chown "$USER":"$USER" /opt/station
   git clone https://github.com/bayhes5/Station_de_recharge.git /opt/station
   cd /opt/station
   git checkout main

Créer le fichier d'environnement :

.. code-block:: bash

   cp .env.example .env
   chmod 600 .env

Génération des secrets
----------------------

Générer au minimum une clé Django, un secret terminal et des mots de passe forts :

.. code-block:: bash

   openssl rand -base64 48
   openssl rand -hex 32

Reporter ces valeurs dans ``.env``. Le fichier ``.env`` ne doit jamais être
commité.

Configuration minimale du fichier .env
--------------------------------------

Adapter les variables suivantes avant le premier démarrage :

.. code-block:: text

   SECRET_KEY=<valeur openssl rand -base64 48>
   DEBUG=False
   BOOTSTRAP_DEMO_DATA=False
   ALLOWED_HOSTS=station.example.com,192.168.1.50

   TIMESCALEDB_IMAGE=timescale/timescaledb@sha256:<digest valide>
   REDIS_IMAGE=redis@sha256:<digest valide>
   MAILPIT_IMAGE=axllent/mailpit@sha256:<digest valide>
   MOSQUITTO_IMAGE=eclipse-mosquitto@sha256:<digest valide>
   GRAFANA_IMAGE=grafana/grafana-oss@sha256:<digest valide>
   NGINX_IMAGE=nginx@sha256:<digest valide>

   FRONTEND_BASE_URL=https://station.example.com
   CORS_ALLOWED_ORIGINS=https://station.example.com

   DB_NAME=station
   DB_USER=station_user
   DB_PASSWORD=<mot de passe fort>
   DB_HOST=db
   DB_PORT=5432

   POSTGRES_DB=station
   POSTGRES_USER=station_user
   POSTGRES_PASSWORD=<même mot de passe que DB_PASSWORD>

   TERMINAL_API_SECRET=<valeur openssl rand -hex 32>

   GRAFANA_ADMIN_USER=admin
   GRAFANA_ADMIN_PASSWORD=<mot de passe fort>
   GRAFANA_ROOT_URL=https://station.example.com/grafana/

   MQTT_HOST=<ip-du-raspberry>
   MQTT_PORT=1883
   MQTT_USERNAME=station_backend
   MQTT_PASSWORD=<mot de passe station_backend>
   MQTT_RASPBERRY_USERNAME=raspberry_kiosk
   MQTT_RASPBERRY_PASSWORD=<mot de passe raspberry_kiosk>
   MQTT_ACK_REQUIRED=True
   MQTT_TLS_ENABLED=False
   MQTT_TLS_CA_CERT=
   MQTT_PUBLISHED_HOST=127.0.0.1

   SECURE_SSL_REDIRECT=True
   SESSION_COOKIE_SECURE=True
   CSRF_COOKIE_SECURE=True
   JWT_REFRESH_COOKIE_SECURE=True
   SECURE_HSTS_SECONDS=31536000
   SECURE_HSTS_INCLUDE_SUBDOMAINS=False
   SECURE_HSTS_PRELOAD=False

   TELEMETRY_RETENTION_DAYS=90
   CELERY_BEAT_TELEMETRY_RETENTION_SECONDS=86400

   ADMIN_EMAIL=<email admin>
   ADMIN_PASSWORD=<mot de passe admin fort>

Si le serveur est utilisé uniquement en réseau local sans domaine, remplacer
``station.example.com`` par l'adresse IP fixe du serveur. La solution retenue
pour le projet est une CA locale Smallstep nommée ``Metropole Verte`` : le
certificat serveur est signé par cette CA et la racine est installée sur les
postes qui doivent faire confiance à l'application.

Les options ``SECURE_HSTS_SECONDS``, ``SECURE_HSTS_INCLUDE_SUBDOMAINS`` et
``SECURE_HSTS_PRELOAD`` ne doivent être activées qu'après validation du
certificat et des sous-domaines de production. Une politique HSTS préchargée
est volontairement difficile à annuler côté navigateurs.
Dans le contexte LAN du projet, ``SECURE_HSTS_SECONDS=31536000`` est activé,
mais ``includeSubDomains`` et ``preload`` restent désactivés : il n'y a pas de
domaine public ni de sous-domaines maîtrisés à précharger dans les navigateurs.
Le profil Nginx production applique donc aussi l'en-tête HSTS sous la forme
``Strict-Transport-Security: max-age=31536000``.

En production terrain, ``MQTT_HOST`` doit pointer vers l'adresse IP du Raspberry
sur le réseau local de la borne, car c'est lui qui héberge Mosquitto. Le backend
et ``mqtt-bridge`` se connectent donc au broker Raspberry pour ingérer les
télémétries et les ACK.

``MQTT_PUBLISHED_HOST`` ne concerne que le broker Docker de simulation. Il vaut
``127.0.0.1`` par défaut afin de ne pas exposer Mosquitto par erreur si le
profil ``simulation`` est utilisé sur le serveur.

Configuration TLS
-----------------

La configuration Nginx actuelle attend deux fichiers :

.. code-block:: text

   nginx/certs/localhost.crt
   nginx/certs/localhost.key

La terminaison HTTPS Nginx est volontairement limitée à ``TLSv1.3`` dans les
configurations du dépôt. TLS 1.2 n'est pas activé pour le point d'entrée web de
production ; les clients trop anciens doivent donc être exclus ou mis à jour.

Pour une démonstration locale ou LAN, générer un certificat autosigné :

.. code-block:: bash

   mkdir -p nginx/certs
   openssl req -x509 -nodes -days 365 -newkey rsa:4096 \
     -keyout nginx/certs/localhost.key \
     -out nginx/certs/localhost.crt \
     -subj "/CN=station.local"

Cette option suffit pour un test ponctuel, mais elle n'est pas idéale dès que
plusieurs machines doivent faire confiance au service : PC, smartphone,
Raspberry, ESP32, backend conteneurisé et outils de supervision.

Option recommandée en LAN : smallstep
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pour une production locale ou académique sans domaine public, la solution la
plus propre est d'utiliser une autorité de certification interne avec
``step-ca`` et le client ``step`` de Smallstep. Le principe est le suivant :

* ``step-ca`` joue le rôle d'autorité de certification privée ;
* ``step`` génère les certificats Nginx et Mosquitto ;
* la racine de confiance est installée sur les postes, téléphones, Raspberry et
  conteneurs qui doivent vérifier TLS ;
* les certificats peuvent être renouvelés automatiquement au lieu de conserver
  un certificat autosigné statique.

Installer ``step`` et ``step-ca`` sur Debian :

.. code-block:: bash

   sudo apt update
   sudo apt install -y --no-install-recommends curl gpg ca-certificates
   sudo install -m 0755 -d /etc/apt/keyrings
   curl -fsSL https://packages.smallstep.com/keys/apt/repo-signing-key.gpg \
     | sudo tee /etc/apt/keyrings/smallstep.asc > /dev/null
   sudo tee /etc/apt/sources.list.d/smallstep.sources > /dev/null <<'EOF'
   Types: deb
   URIs: https://packages.smallstep.com/stable/debian
   Suites: debs
   Components: main
   Signed-By: /etc/apt/keyrings/smallstep.asc
   EOF
   sudo apt update
   sudo apt install -y step-cli step-ca

Initialiser la CA locale sur une machine d'administration protégée :

.. code-block:: bash

   step ca init \
     --name "Metropole Verte" \
     --dns 192.168.10.10 \
     --dns localhost \
     --address ":9000" \
     --provisioner metropole-verte-admin

Lancer ensuite ``step-ca`` via un service ``systemd`` ou un conteneur dédié, et
ne pas exposer le port de la CA à Internet. La racine doit rester protégée ; en
production réelle, l'approche recommandée est de garder la racine hors ligne et
de laisser l'intermédiaire signer les certificats courants.

Configuration appliquée sur le serveur Debian du projet :

.. code-block:: text

   Nom CA      : Metropole Verte
   URL CA      : https://192.168.10.10:9000
   Provisioner : metropole-verte-admin
   Service     : step-ca.service
   Racine      : /etc/step-ca/certs/root_ca.crt
   Fingerprint : e05fa0ebed4ccad08462cb261ef6ce4a0c025d07dbd5d17399832022bbc65325

Le certificat HTTPS Nginx est signé par l'intermédiaire Smallstep et contient
les SAN réellement utilisés dans le prototype :

.. code-block:: text

   DNS:localhost
   DNS:SRV-Station
   IP:192.168.10.10
   IP:127.0.0.1

Cette liste est essentielle : si le navigateur ouvre ``https://192.168.10.10``,
le certificat doit contenir l'IP ``192.168.10.10`` dans ses SAN, sinon la
connexion TLS est rejetée même si la racine CA est installée.

Sur chaque machine qui doit émettre ou renouveler des certificats, établir la
confiance vers la CA :

.. code-block:: bash

   step certificate fingerprint /etc/step-ca/certs/root_ca.crt
   step ca bootstrap \
     --ca-url https://192.168.10.10:9000 \
     --fingerprint e05fa0ebed4ccad08462cb261ef6ce4a0c025d07dbd5d17399832022bbc65325

Générer le certificat Nginx. Les noms et IP utilisés par les navigateurs doivent
être présents dans les SAN du certificat :

.. code-block:: bash

   step ca certificate 192.168.10.10 \
     nginx/certs/localhost.crt \
     nginx/certs/localhost.key \
     --san 192.168.10.10 \
     --san 127.0.0.1 \
     --san localhost \
     --san SRV-Station \
     --not-after 720h
   chmod 600 nginx/certs/localhost.key

La durée ``720h`` correspond à 30 jours. Elle oblige à tester le renouvellement,
limite l'impact d'une fuite de clé, et reste assez longue pour une soutenance ou
une démonstration sans renouvellement quotidien.

Générer les certificats Mosquitto sur le Raspberry, car c'est lui qui héberge le
broker de terrain :

.. code-block:: bash

   sudo mkdir -p /etc/station/mqtt-certs
   sudo chown "$USER":"$USER" /etc/station/mqtt-certs
   step ca certificate raspberry-mqtt.station.local \
     /etc/station/mqtt-certs/mqtt.crt \
     /etc/station/mqtt-certs/mqtt.key \
     --san mqtt.station.local \
     --san <ip-du-raspberry>
   step ca root /etc/station/mqtt-certs/metropole-verte-root-ca.crt
   chmod 600 /etc/station/mqtt-certs/mqtt.key

Pour activer MQTT TLS sur le Raspberry, adapter la configuration Mosquitto avec
un listener ``8883`` :

.. code-block:: text

   listener 8883 0.0.0.0
   protocol mqtt
   allow_anonymous false
   password_file /etc/mosquitto/passwords
   acl_file /etc/mosquitto/aclfile
   cafile /etc/station/mqtt-certs/metropole-verte-root-ca.crt
   certfile /etc/station/mqtt-certs/mqtt.crt
   keyfile /etc/station/mqtt-certs/mqtt.key

Le dépôt fournit un modèle prêt à adapter dans
``raspberry/mosquitto/station.tls.conf``. Il ne doit remplacer la configuration
1883 actuelle qu'après validation du backend, du kiosk Raspberry et des ESP32 en
TLS.

Le serveur Debian doit seulement faire confiance à la racine utilisée par le
broker Raspberry. Copier ``metropole-verte-root-ca.crt`` dans un chemin monté
par le conteneur backend, puis configurer :

.. code-block:: text

   MQTT_PORT=8883
   MQTT_TLS_ENABLED=True
   MQTT_TLS_CA_CERT=/etc/station/mqtt-certs/metropole-verte-root-ca.crt

Les ESP32 doivent aussi vérifier le certificat du broker : embarquer la racine
``metropole-verte-root-ca.crt`` dans le firmware ou la stocker dans le système
de fichiers de l'ESP32 si l'implémentation TLS utilisée le permet.

Distribuer la racine de confiance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

La racine Smallstep doit être installée sur chaque client :

* Windows : importer ``metropole-verte-root-ca.crt`` dans les autorités de
  certification racines de confiance ;
* Android : installer le certificat CA pour les tests de navigation locale ;
* Raspberry/Debian : copier le certificat dans
  ``/usr/local/share/ca-certificates/station-root-ca.crt`` puis lancer
  ``sudo update-ca-certificates`` ;
* conteneurs backend : monter ``metropole-verte-root-ca.crt`` et renseigner
  ``MQTT_TLS_CA_CERT`` ;
* ESP32 : embarquer explicitement la racine dans le code ou dans LittleFS.

Renouvellement
~~~~~~~~~~~~~~

Les certificats Smallstep sont généralement courts. C'est volontaire : en cas de
fuite d'un certificat ou d'une clé, la durée d'exposition est limitée. En
contrepartie, il faut automatiser le renouvellement.

Le client ``step`` fournit ``step ca renew --daemon``. En mode démon, il garde un
processus actif, renouvelle le certificat avant expiration et peut exécuter une
commande après renouvellement avec ``--exec``. D'après le comportement documenté
de Smallstep, le renouvellement est tenté par défaut avant que les deux tiers de
la période de validité soient écoulés ; on peut aussi imposer un seuil avec
``--expires-in`` ou une période fixe avec ``--renew-period``.

Avant d'automatiser, tester un renouvellement manuel :

.. code-block:: bash

   # Sur le serveur Debian
   cd /opt/station
   step ca renew --force nginx/certs/localhost.crt nginx/certs/localhost.key
   docker compose -f docker-compose.prod.yml exec -T reverse-proxy nginx -s reload

   # Sur le Raspberry
   step ca renew --force /etc/station/mqtt-certs/mqtt.crt /etc/station/mqtt-certs/mqtt.key
   sudo systemctl restart mosquitto

Vérifier ensuite :

.. code-block:: bash

   step certificate inspect nginx/certs/localhost.crt --short
   step certificate inspect /etc/station/mqtt-certs/mqtt.crt --short

Créer ensuite un service systemd pour le certificat Nginx. Sur le serveur du
projet, l'utilisateur Linux est ``btsciel`` et possède ``/opt/station`` :

.. code-block:: bash

   sudo tee /etc/systemd/system/metropole-verte-nginx-cert-renew.service > /dev/null <<'EOF'
   [Unit]
   Description=Renouvellement du certificat HTTPS Nginx Metropole Verte
   After=network-online.target docker.service
   Wants=network-online.target

   [Service]
   Type=simple
   User=btsciel
   Group=btsciel
   WorkingDirectory=/opt/station
   ExecStart=/usr/bin/step ca renew --daemon --expires-in 168h --ca-url https://127.0.0.1:9000 --root /etc/step-ca/certs/root_ca.crt --exec "/usr/bin/docker compose -f /opt/station/docker-compose.prod.yml exec -T reverse-proxy nginx -s reload" /opt/station/nginx/certs/localhost.crt /opt/station/nginx/certs/localhost.key
   Restart=always
   RestartSec=30

   [Install]
   WantedBy=multi-user.target
   EOF

Créer un second service sur le Raspberry pour Mosquitto. Le profil Smallstep
doit être initialisé pour ``root`` sur le Raspberry, car le service renouvelle
des certificats dans ``/etc`` et redémarre Mosquitto :

.. code-block:: bash

   sudo STEPPATH=/root/.step step ca bootstrap --ca-url https://station-ca.local:9001 --fingerprint <fingerprint>

   sudo tee /etc/systemd/system/metropole-verte-mqtt-cert-renew.service > /dev/null <<'EOF'
   [Unit]
   Description=Renouvellement du certificat MQTT Mosquitto Metropole Verte
   After=network-online.target mosquitto.service
   Wants=network-online.target

   [Service]
   Type=simple
   User=root
   Group=root
   Environment=STEPPATH=/root/.step
   ExecStart=/bin/sh -lc 'exec step ca renew --daemon --expires-in 168h --exec "systemctl restart mosquitto" /etc/station/mqtt-certs/mqtt.crt /etc/station/mqtt-certs/mqtt.key'
   Restart=always
   RestartSec=30

   [Install]
   WantedBy=multi-user.target
   EOF

Activer les deux services :

.. code-block:: bash

   sudo systemctl daemon-reload
   sudo systemctl enable --now metropole-verte-nginx-cert-renew.service
   sudo systemctl enable --now metropole-verte-mqtt-cert-renew.service

Contrôler leur état :

.. code-block:: bash

   systemctl status metropole-verte-nginx-cert-renew.service
   systemctl status metropole-verte-mqtt-cert-renew.service
   journalctl -u metropole-verte-nginx-cert-renew.service -n 100 --no-pager
   journalctl -u metropole-verte-mqtt-cert-renew.service -n 100 --no-pager

Avec ``--expires-in 168h``, le renouvellement est demandé lorsqu'il reste moins
de sept jours de validité. Ce seuil est lisible pour l'exploitation et laisse le
temps de corriger un problème avant expiration. Après renouvellement :

* Nginx est rechargé sans redémarrer toute la stack serveur ;
* Mosquitto est redémarré sur le Raspberry pour relire le certificat et la clé ;
* ``mqtt-bridge``, le kiosk Raspberry et les ESP32 doivent se reconnecter
  automatiquement au broker. Si ce n'est pas le cas, redémarrer le service
  concerné.

Points de vigilance :

* l'utilisateur systemd doit pouvoir écrire les certificats et lire les clés ;
* ``STEPPATH`` doit pointer vers le profil Smallstep bootstrapé avec
  ``step ca bootstrap`` ;
* la date du serveur doit être correcte, sinon la validation TLS échoue ;
* les journaux systemd doivent être surveillés comme les autres services
  critiques.

Pour un domaine public exposé à Internet, Let's Encrypt reste plus adapté : la
CA locale Smallstep est surtout pertinente pour un réseau de station privé, un
laboratoire ou un déploiement industriel fermé.

Pour un vrai domaine, utiliser un certificat Let's Encrypt ou un certificat
fourni par l'infrastructure, puis placer la clé et le certificat aux chemins
ci-dessus ou adapter ``nginx/conf.d/station.conf``.

Configurer le nom du serveur dans ``nginx/prod.conf.d/station.conf`` si un nom
explicite est souhaité :

.. code-block:: nginx

   server_name station.example.com 192.168.1.50;

Remplacer ``station.example.com`` et ``192.168.1.50`` par les valeurs réelles.

Pare-feu
--------

Configurer UFW pour n'exposer que les ports nécessaires :

.. code-block:: bash

   sudo ufw default deny incoming
   sudo ufw default allow outgoing
   sudo ufw allow OpenSSH
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   sudo ufw status numbered

Le serveur Debian n'a pas besoin d'exposer MQTT si le broker tourne sur le
Raspberry. Ouvrir ``1883`` ou ``8883`` sur le Raspberry uniquement, en limitant
l'accès au réseau local des ESP32 et du serveur. Le port MQTT ne doit pas être
ouvert à tout Internet. En production avec MQTT TLS, préférer ``8883`` et fermer
``1883`` dès que tous les clients utilisent TLS.

Durcissement Linux
------------------

Le durcissement doit être appliqué progressivement afin de ne pas couper l'accès
SSH pendant l'installation. Le projet fournit un script d'installation des
mesures de maintenance :

.. code-block:: bash

   cd /opt/station
   chmod +x scripts/*.sh
   sudo scripts/install-prod-maintenance.sh

Ce premier passage installe et configure :

* ``unattended-upgrades`` pour les mises à jour de sécurité automatiques ;
* ``fail2ban`` pour protéger SSH ;
* ``logrotate`` pour le journal de sauvegarde ;
* une tâche cron quotidienne ``/etc/cron.d/station-backup`` ;
* une rotation ``/etc/logrotate.d/station-backup``.

Les protections pouvant verrouiller l'accès au serveur restent opt-in. Après
avoir confirmé qu'une connexion SSH par clé fonctionne, appliquer le durcissement
SSH :

.. code-block:: bash

   sudo APPLY_SSH_HARDENING=true scripts/install-prod-maintenance.sh

Pour désactiver l'authentification SSH par mot de passe, uniquement après test
d'une deuxième session SSH par clé :

.. code-block:: bash

   sudo APPLY_SSH_HARDENING=true DISABLE_SSH_PASSWORD_AUTH=true scripts/install-prod-maintenance.sh

Pour activer UFW depuis le script :

.. code-block:: bash

   sudo APPLY_UFW=true scripts/install-prod-maintenance.sh

Les commandes manuelles équivalentes restent utiles si l'on préfère appliquer
chaque mesure séparément.

Installer les outils de maintenance de base :

.. code-block:: bash

   sudo apt install -y unattended-upgrades fail2ban logrotate

Activer les mises à jour de sécurité automatiques :

.. code-block:: bash

   sudo dpkg-reconfigure --priority=low unattended-upgrades

Durcir SSH dans ``/etc/ssh/sshd_config`` :

.. code-block:: text

   PermitRootLogin no
   PasswordAuthentication no
   PubkeyAuthentication yes
   MaxAuthTries 3

Redémarrer SSH après validation de l'accès par clé :

.. code-block:: bash

   sudo systemctl restart ssh

Vérifier que ``fail2ban`` protège SSH :

.. code-block:: bash

   sudo systemctl enable --now fail2ban
   sudo fail2ban-client status sshd

Surveiller régulièrement :

.. code-block:: bash

   df -h
   free -h
   docker system df
   journalctl -u station.service --since "1 hour ago"

Pour un serveur réellement exposé, ajouter une supervision système externe
ou au minimum des alertes disque, mémoire, CPU et disponibilité HTTPS.

Démarrage de la stack
---------------------

Le profil production monte ``postgresql/prod/postgresql.conf`` pour appliquer un
réglage PostgreSQL/TimescaleDB conservateur : connexions limitées, buffers
raisonnables, compression WAL et journalisation des requêtes lentes au-delà de
1 seconde. Ces valeurs doivent être revues si le serveur possède beaucoup plus
ou beaucoup moins de mémoire que prévu.

Le fichier active aussi ``pg_stat_statements`` pour l'analyse des requêtes et le
profil production applique une rotation des logs Docker par service avec
``json-file``, ``max-size=10m`` et ``max-file=5``.

Les images publiques du profil production sont référencées par digest
``sha256`` via ``.env``. Lors d'une mise à jour volontaire d'image, changer le
digest, reconstruire, tester, puis commiter le nouveau digest.

Initialisation PostgreSQL et création des tables
------------------------------------------------

Avec le profil Docker production, il n'y a pas de commande SQL manuelle à lancer
pour créer la base au premier démarrage. Le conteneur PostgreSQL/TimescaleDB
utilise les variables suivantes du fichier ``.env`` :

* ``POSTGRES_DB`` : nom de la base créée automatiquement si le volume
  ``postgres_data`` est vide ;
* ``POSTGRES_USER`` : rôle propriétaire créé automatiquement ;
* ``POSTGRES_PASSWORD`` : mot de passe du rôle ;
* ``DB_NAME``, ``DB_USER`` et ``DB_PASSWORD`` : identifiants utilisés par Django
  pour se connecter à cette base.

Au premier ``docker compose up -d --build``, PostgreSQL crée donc la base
``POSTGRES_DB`` si aucun volume existant ne contient déjà un cluster. Ensuite,
le conteneur ``backend`` exécute automatiquement :

.. code-block:: bash

   python manage.py migrate --noinput
   python manage.py collectstatic --noinput
   python manage.py bootstrap_superuser

Les migrations Django créent toutes les tables applicatives, vues SQL, index,
contraintes et extensions optionnelles disponibles, notamment TimescaleDB,
``pg_stat_statements`` et PostgreSQL Anonymizer lorsque l'image les fournit.

Attention : si le volume ``postgres_data`` existe déjà, PostgreSQL ne recrée pas
la base à partir des variables ``POSTGRES_*``. Modifier ``POSTGRES_DB`` ou
``POSTGRES_USER`` après le premier démarrage ne renomme pas une base existante.
Pour une réinstallation complète, il faut sauvegarder puis recréer le volume, ou
créer la nouvelle base manuellement avec un compte administrateur PostgreSQL.

Démarrer tous les services :

.. code-block:: bash

   cd /opt/station
   docker compose -f docker-compose.prod.yml pull
   docker compose -f docker-compose.prod.yml up -d --build
   docker compose -f docker-compose.prod.yml ps

Le conteneur ``backend`` attend la base, lance les migrations, collecte les
fichiers statiques, crée le super utilisateur configuré par les variables
``ADMIN_*`` et démarre Django en ASGI avec Daphne. Les données de démonstration
ne sont chargées que si ``BOOTSTRAP_DEMO_DATA=True``.

Le conteneur ``frontend`` exécute ``npm run build`` pendant la construction de
l'image. Les fichiers HTML, CSS et JavaScript produits par Vite sont ensuite
servis par Nginx interne, derrière le reverse proxy. Les assets versionnés sous
``/assets/`` reçoivent un cache long côté reverse proxy, ce qui évite de servir
le frontend en mode développement sur le serveur Debian.

Suivre les logs du premier démarrage :

.. code-block:: bash

   docker compose -f docker-compose.prod.yml logs -f backend db redis mqtt mqtt-bridge celery celery-beat

Vérifications applicatives
--------------------------

Tester l'API via le reverse proxy :

.. code-block:: bash

   curl -k https://station.example.com/api/health/live/
   curl -k https://station.example.com/api/health/ready/

Tester la chaîne asynchrone :

.. code-block:: bash

   docker compose -f docker-compose.prod.yml exec celery celery -A config inspect ping --timeout=3
   docker compose -f docker-compose.prod.yml exec mqtt-bridge python manage.py check_mqtt_bridge_health

Lancer les contrôles Django :

.. code-block:: bash

   docker compose -f docker-compose.prod.yml exec backend python manage.py check --deploy

Les avertissements doivent être analysés. En production publique, aucun
avertissement de sécurité critique ne doit rester ignoré.

URLs de validation
------------------

Remplacer ``station.example.com`` par le domaine ou l'IP du serveur :

.. code-block:: text

   https://station.example.com/          Interface web
   https://station.example.com/api/      API REST
   https://station.example.com/admin/    Administration Django
   https://station.example.com/grafana/  Supervision Grafana

L'interface borne s'ouvre sur le Raspberry physique, par exemple
``http://localhost:9000`` depuis Chromium en mode kiosque sur l'écran tactile.

Grafana utilise le compte configuré par ``GRAFANA_ADMIN_USER`` et
``GRAFANA_ADMIN_PASSWORD``. Changer le mot de passe après la première connexion
si le compte est conservé.

Mailpit et emails de test
-------------------------

Mailpit est prévu pour un projet académique ou une préproduction. Il capture les
emails sans les envoyer réellement.

Ne pas exposer le port ``8025`` publiquement. Pour consulter Mailpit depuis son
poste :

.. code-block:: bash

   ssh -L 8025:localhost:8025 utilisateur@station.example.com

Puis ouvrir :

.. code-block:: text

   http://localhost:8025

Pour une production réelle, remplacer Mailpit par un SMTP authentifié et mettre
à jour ``EMAIL_HOST``, ``EMAIL_PORT``, ``EMAIL_USE_TLS``, ``EMAIL_HOST_USER`` et
``EMAIL_HOST_PASSWORD``.

Configuration serveur, Raspberry et ESP32
-----------------------------------------

Le serveur Debian doit joindre le broker Mosquitto du Raspberry. Dans ``.env``
côté serveur :

.. code-block:: text

   MQTT_HOST=<ip-du-raspberry>
   MQTT_PORT=1883
   MQTT_USERNAME=station_backend
   MQTT_PASSWORD=<mot de passe station_backend>
   MQTT_TLS_ENABLED=False
   MQTT_TLS_CA_CERT=
   MQTT_ACK_REQUIRED=True

Le Raspberry doit joindre le serveur Debian pour l'API, mais il parle à son
broker Mosquitto local en ``localhost`` :

.. code-block:: text

   BACKEND_API_BASE_URL=https://station.example.com/api
   MQTT_HOST=localhost
   MQTT_PORT=1883
   MQTT_USERNAME=raspberry_kiosk
   MQTT_PASSWORD=<mot de passe raspberry_kiosk>
   MQTT_TLS_ENABLED=False
   MQTT_TLS_CA_CERT=
   MQTT_ACK_REQUIRED=True
   TERMINAL_API_SECRET=<même valeur que côté backend>

Pour l'ESP32 :

.. code-block:: text

   WIFI_SSID=<SSID du réseau>
   WIFI_PASSWORD=<mot de passe Wi-Fi>
   MQTT_HOST=<ip-du-raspberry>
   MQTT_PORT=1883
   MQTT_USER=esp32_station_demo_borne_1_slot1
   MQTT_PASSWORD=<mot de passe de l'emplacement ESP32>

L'ESP32 publie sa télémétrie vers Mosquitto. Le backend ne reçoit pas les mesures
en HTTP direct : ``mqtt-bridge`` consomme les topics MQTT et écrit en base.

Si Mosquitto est passé en TLS avec smallstep, remplacer le port par ``8883``,
mettre ``MQTT_TLS_ENABLED=True`` côté Raspberry/backend et distribuer
``metropole-verte-root-ca.crt`` aux clients. Côté ESP32, le firmware doit charger la racine CA
utilisée pour vérifier le certificat du broker.

Test MQTT
---------

Observer les messages MQTT depuis le serveur Debian, si ``mosquitto-clients`` est
installé :

.. code-block:: bash

   mosquitto_sub -h <ip-du-raspberry> -t 'station/#' -v -C 10 -W 20

Si des identifiants MQTT sont activés :

.. code-block:: bash

   mosquitto_sub -h <ip-du-raspberry> \
     -u station_backend -P '<mot-de-passe>' \
     -t 'station/#' -v -C 10 -W 20

Si MQTT TLS est activé :

.. code-block:: bash

   mosquitto_sub -h <ip-du-raspberry> -p 8883 \
     --cafile /etc/station/mqtt-certs/metropole-verte-root-ca.crt \
     -u station_backend -P '<mot-de-passe>' \
     -t 'station/#' -v -C 10 -W 20

Depuis le Raspberry, le même test peut viser ``localhost`` :

.. code-block:: bash

   mosquitto_sub -h localhost \
     -u raspberry_kiosk -P '<mot-de-passe>' \
     -t 'station/#' -v -C 10 -W 20

Pour un réseau Wi-Fi ESP32, vérifier que :

* l'ESP32 est sur le même réseau que le Raspberry ou qu'une route existe ;
* le serveur Debian peut joindre le Raspberry sur ``1883`` ou ``8883`` ;
* le port ``1883`` ou ``8883`` est autorisé sur le Raspberry depuis ce réseau ;
* le topic publié correspond au préfixe de la borne/emplacement ;
* ``mqtt-bridge`` est ``healthy`` dans ``docker compose -f docker-compose.prod.yml ps``.

Sauvegardes
-----------

Les scripts opérationnels sont versionnés :

* ``scripts/backup-prod.sh`` produit un dump SQL compressé avec checksum SHA-256 ;
* ``scripts/restore-prod.sh`` restaure un dump et exige
  ``RESTORE_CONFIRM=YES`` pour éviter une restauration accidentelle.
* ``scripts/test-prod-restore.sh`` restaure une sauvegarde dans une base
  temporaire puis supprime cette base après vérification.
* ``scripts/install-prod-maintenance.sh`` installe la tâche cron quotidienne de
  sauvegarde et les premiers contrôles de durcissement système.

Créer un dossier de sauvegarde :

.. code-block:: bash

   mkdir -p /opt/station/backups
   chmod 700 /opt/station/backups

Sauvegarder la base PostgreSQL/TimescaleDB :

.. code-block:: bash

   BACKUP_DIR=/opt/station/backups scripts/backup-prod.sh

Sauvegarder aussi Grafana et la configuration non secrète :

.. code-block:: bash

   BACKUP_DIR=/opt/station/backups \
   BACKUP_DOCKER_VOLUMES=true \
   BACKUP_CONFIG=true \
   scripts/backup-prod.sh

Par défaut, l'archive de configuration exclut ``.env``, les clés privées TLS,
les mots de passe Mosquitto et le dossier ``backups``. Si l'on veut conserver
les secrets dans une sauvegarde chiffrée hors ligne, utiliser explicitement :

.. code-block:: bash

   BACKUP_INCLUDE_SECRETS=true scripts/backup-prod.sh

Vérifier les checksums :

.. code-block:: bash

   cd /opt/station/backups
   sha256sum -c *.sha256

Tester une restauration dans une base de préproduction ou un serveur jetable :

.. code-block:: bash

   RESTORE_CONFIRM=YES scripts/restore-prod.sh /opt/station/backups/station_YYYYMMDDTHHMMSSZ.sql.gz

Ne jamais tester une restauration directement sur la production active sans
fenêtre de maintenance, sauvegarde récente et validation manuelle.

Pour vérifier une sauvegarde sans toucher à la base de production, restaurer dans
une base temporaire du même conteneur PostgreSQL :

.. code-block:: bash

   cd /opt/station
   scripts/test-prod-restore.sh /opt/station/backups/station_YYYYMMDDTHHMMSSZ.sql.gz

Sans argument, le script utilise la dernière sauvegarde ``station_*.sql.gz`` du
dossier ``BACKUP_DIR``.

Lister les volumes Docker pour identifier le nom exact des volumes :

.. code-block:: bash

   docker volume ls

Les volumes importants sont :

* ``postgres_data`` pour la base ;
* ``grafana_data`` pour Grafana ;
* ``mqtt_data`` et ``mqtt_log`` uniquement si le broker Docker de simulation est utilisé ;
* ``mailpit_data`` pour les emails capturés.

Planifier au minimum une sauvegarde quotidienne de la base et une sauvegarde
régulière du volume Grafana. Si Mosquitto tourne sur le Raspberry, sa
configuration, ses ACL, son fichier de mots de passe et ses certificats doivent
être sauvegardés côté Raspberry. Exemple de cron quotidien à 02:15 :

.. code-block:: text

   15 2 * * * cd /opt/station && BACKUP_DIR=/opt/station/backups scripts/backup-prod.sh >> /var/log/station-backup.log 2>&1

Rétention télémétrie
--------------------

La télémétrie applicative est purgée par Celery Beat avec
``api.prune_old_telemetry``. Par défaut :

* ``TELEMETRY_RETENTION_DAYS=90`` ;
* ``CELERY_BEAT_TELEMETRY_RETENTION_SECONDS=86400``.

La politique supprime les anciens enregistrements ``CapteurData`` et laisse les
alertes existantes en place grâce au ``SET_NULL`` côté modèle. La migration
``0026_pg_stat_statements_and_timescale_policies`` active ``pg_stat_statements``
et prépare des politiques TimescaleDB conditionnelles. Ces politiques natives ne
s'appliquent que si ``capteur_data`` est convertie plus tard en hypertable, car
le schéma Django actuel conserve une clé primaire UUID simple.

Rétention RGPD applicative
--------------------------

Avant le transfert sur un serveur de production, activer explicitement la
politique de rétention applicative dans ``.env`` :

.. code-block:: text

   PRIVACY_RETENTION_ENABLED=True
   SESSION_TELEMETRY_RETENTION_DAYS=365
   DEVICE_COMMAND_LOG_RETENTION_DAYS=365
   SECURITY_LOG_RETENTION_DAYS=365
   ALERT_RETENTION_DAYS=365
   AUTH_METHOD_RETENTION_DAYS=90
   USER_ANONYMIZATION_RETENTION_DAYS=1095
   CELERY_BEAT_PRIVACY_RETENTION_SECONDS=86400

La tâche planifiée ``api.apply_privacy_retention`` complète
``api.prune_old_telemetry``. Elle supprime les anciennes télémétries de session,
les anciens ACK/commandes ESP32, les journaux de sécurité périmés, les alertes
résolues anciennes et les moyens d’accès inactifs ou expirés.

La suppression de compte côté application est une anonymisation immédiate :

* le compte devient inactif et ``archive`` ;
* le nom, le téléphone et l’email sont retirés ;
* les secrets RFID, QR et SMS sont désactivés ;
* les réservations et sessions restent disponibles pour la traçabilité
  opérationnelle sans identité personnelle.

Exécution manuelle avant sauvegarde ou migration :

.. code-block:: bash

   docker compose -f docker-compose.prod.yml exec backend python manage.py apply_privacy_retention

Vérification de la planification :

.. code-block:: bash

   docker compose -f docker-compose.prod.yml exec backend python manage.py shell -c "from django.conf import settings; print(settings.CELERY_BEAT_SCHEDULE['apply-privacy-retention'])"

TimescaleDB en production
-------------------------

Le service ``db`` utilise une image TimescaleDB. Les migrations activent
``timescaledb`` et ``pg_stat_statements`` lorsque ces extensions sont
disponibles.

Pour ne pas casser les clés primaires UUID du modèle Django, les tables
applicatives ``capteur_data`` et ``session_telemetry`` restent des tables ORM
classiques. La migration ``0033_timescale_timeseries_and_anonymized_views`` crée
des hypertables miroir spécialisées :

* ``capteur_data_timeseries`` ;
* ``session_telemetry_timeseries``.

Ces hypertables sont alimentées par backfill initial puis par triggers. Elles
servent aux usages séries temporelles, supervision et exports sans modifier le
chemin d’écriture applicatif.

Vérifier l’état TimescaleDB :

.. code-block:: bash

   docker compose -f docker-compose.prod.yml exec db \
     psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
     -c "SELECT hypertable_schema, hypertable_name FROM timescaledb_information.hypertables;"

Politiques attendues :

* compression après 7 jours ;
* rétention de ``capteur_data_timeseries`` après 90 jours ;
* rétention de ``session_telemetry_timeseries`` après 365 jours.

Anonymisation PostgreSQL
------------------------

La migration ``0033_timescale_timeseries_and_anonymized_views`` crée aussi des
vues SQL anonymisées exploitables immédiatement :

* ``utilisateur_anonyme`` ;
* ``technicien_anonyme`` ;
* ``journal_securite_anonyme`` ;
* ``supervision_session_anonyme``.

Ces vues masquent les identités par hash ou constantes anonymisées. Elles
permettent de vérifier et d’exporter des statistiques sans exposer email,
téléphone, nom ou adresse IP réelle.

La migration ``0027_optional_postgresql_anonymizer`` active l'extension
``anon`` et ses ``SECURITY LABEL`` uniquement si PostgreSQL Anonymizer est
installé dans l'image de base de données. Cette extension n'est pas garantie par
l'image TimescaleDB standard ; en production, il faut donc choisir explicitement
une image PostgreSQL/TimescaleDB qui contient ``anon`` ou construire une image
interne validée.

Ne pas ajouter ``anon`` dans ``shared_preload_libraries`` tant que la bibliothèque
n'est pas présente dans l'image, sinon PostgreSQL peut refuser de démarrer. Une
fois l'image validée, les règles de masquage versionnées couvrent les colonnes
personnelles des comptes, profils, techniciens et journaux de sécurité.

Vérifier l'état réel de ``anon`` sur le serveur :

.. code-block:: bash

   docker exec station_postgres_db \
     psql -U station_user -d station \
     -Atc "SELECT extname FROM pg_extension ORDER BY extname;"

   docker exec station_postgres_db \
     find /usr/share /usr/local/share -path '*/extension/anon.control' -print

Si ``anon.control`` n'est pas retourné, l'extension n'est pas installable dans
l'image courante. Dans ce cas, ne pas modifier le conteneur à la main : le
changement serait perdu au prochain redéploiement. La solution durable consiste
à créer ou sélectionner une image PostgreSQL qui contient à la fois TimescaleDB
et PostgreSQL Anonymizer, puis à rejouer les migrations Django.

Mise à jour applicative
-----------------------

Mettre à jour le code et reconstruire :

.. code-block:: bash

   cd /opt/station
   git pull --ff-only
   docker compose -f docker-compose.prod.yml pull
   docker compose -f docker-compose.prod.yml up -d --build
   docker compose -f docker-compose.prod.yml ps

Vérifier ensuite :

.. code-block:: bash

   curl -k https://station.example.com/api/health/ready/
   docker compose -f docker-compose.prod.yml exec backend python manage.py check_mqtt_bridge_health
   docker compose -f docker-compose.prod.yml exec backend python manage.py check --deploy

Service systemd
---------------

Créer un service systemd pour relancer la stack au démarrage du serveur :

.. code-block:: bash

   sudo nano /etc/systemd/system/station-prod.service

Contenu :

.. code-block:: ini

   [Unit]
   Description=Station de recharge - stack Docker Compose production
   Requires=docker.service
   After=docker.service network-online.target
   Wants=network-online.target

   [Service]
   Type=oneshot
   WorkingDirectory=/opt/station
   ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d
   ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml stop
   RemainAfterExit=yes
   TimeoutStartSec=120
   TimeoutStopSec=120

   [Install]
   WantedBy=multi-user.target

Activer le service :

.. code-block:: bash

   sudo systemctl daemon-reload
   sudo systemctl enable --now station-prod.service
   sudo systemctl status station-prod.service

Ce service ne remplace pas les politiques ``restart: unless-stopped`` des
conteneurs. Il garantit surtout qu'après un redémarrage complet du serveur,
``docker compose up -d`` est rejoué dans ``/opt/station``. Les conteneurs gardent
ensuite leur propre politique de redémarrage.

Le fichier de santé du bridge MQTT est partagé entre ``mqtt-bridge`` et
``backend`` via le volume Docker ``mqtt_bridge_state``. Cela permet au backend
d'exécuter ``check_mqtt_bridge_health`` même si le bridge tourne dans un autre
conteneur.

Commandes de diagnostic
-----------------------

Afficher l'état des conteneurs :

.. code-block:: bash

   docker compose -f docker-compose.prod.yml ps

Lire les logs principaux :

.. code-block:: bash

   docker compose -f docker-compose.prod.yml logs --tail=100 backend
   docker compose -f docker-compose.prod.yml logs --tail=100 mqtt-bridge
   docker compose -f docker-compose.prod.yml logs --tail=100 celery
   docker compose -f docker-compose.prod.yml logs --tail=100 mqtt
   docker compose -f docker-compose.prod.yml logs --tail=100 reverse-proxy

Contrôler l'espace disque Docker :

.. code-block:: bash

   docker system df
   docker volume ls

Contrôler les ports écoutés :

.. code-block:: bash

   sudo ss -lntup

Checklist avant démonstration
-----------------------------

Avant une démonstration complète :

* ``docker compose -f docker-compose.prod.yml ps`` affiche les services critiques en ``healthy`` ou
  ``running`` ;
* ``/api/health/ready/`` répond ``200`` ;
* l'interface web s'ouvre via HTTPS ;
* l'admin Django est accessible ;
* Grafana s'ouvre via ``/grafana/`` ;
* ``mqtt-bridge`` répond au healthcheck ;
* une télémétrie ESP32 ou simulée arrive en base ;
* le scénario réservation QR, session mobile, validation kiosk, UNLOCK, START,
  télémétrie, STOP et clôture de session fonctionne ;
* le Raspberry et les ESP32 pointent vers l'adresse IP ou le DNS du serveur ;
* le firewall n'expose pas PostgreSQL, Redis, Django direct, Grafana direct ou
  Mailpit direct à Internet.

Points à durcir avant exposition Internet
-----------------------------------------

Avant d'ouvrir le service à des utilisateurs réels :

* remplacer le certificat autosigné par un certificat reconnu ;
* fixer explicitement les images Docker via ``TIMESCALEDB_IMAGE`` et
  ``REDIS_IMAGE`` au lieu de conserver un tag générique ;
* restreindre les ports directs au niveau Docker ou via un firewall strict ;
* activer des identifiants Mosquitto et des ACL par station/borne/emplacement ;
* activer TLS pour MQTT avec une CA locale smallstep ou un certificat public si
  le réseau n'est pas totalement maîtrisé ;
* installer la racine de confiance sur les postes, Raspberry et ESP32 avant
  d'activer HSTS ou MQTT TLS strict ;
* remplacer Mailpit par un SMTP réel ;
* configurer un fournisseur SMS réel si le code SMS doit être envoyé hors mode
  démonstration ;
* définir une stratégie de sauvegarde, restauration et rotation des logs ;
* exécuter régulièrement les tests backend, frontend, Raspberry et le scénario
  de bout en bout automatisé.
