Installation sur serveur Debian
================================

Cette procédure décrit l'installation de la partie backend sur un serveur
Debian dédié. Elle vise un serveur d'intégration ou une production académique
maîtrisée : API Django, base TimescaleDB/PostgreSQL, Redis, Celery, Mosquitto,
Grafana, Mailpit et reverse proxy Nginx.

La procédure utilise ``docker-compose.prod.yml``. Ce profil production sépare le
mode développement du mode serveur : le backend est lancé en ASGI avec Daphne,
le frontend est buildé puis servi par Nginx, les fichiers statiques Django sont
collectés dans un volume dédié, et les ports internes ne sont pas publiés
directement sur le réseau.

Architecture cible
------------------

Le serveur Debian héberge les services suivants :

.. list-table::
   :header-rows: 1

   * - Service
     - Rôle
     - Exposition attendue
   * - ``reverse-proxy``
     - Entrée HTTPS, routage vers l'API, le frontend, Grafana et le kiosque
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
     - Broker Mosquitto pour ESP32, Raspberry et bridge backend
     - LAN uniquement, port ``1883`` si MQTT non TLS
   * - ``mqtt-bridge``
     - Ingestion des télémétries MQTT vers la base
     - Interne uniquement
   * - ``grafana``
     - Supervision technique
     - Via ``/grafana/`` sur Nginx
   * - ``mailpit``
     - SMTP et boîte de réception de test
     - Local ou tunnel SSH uniquement

Pré-requis
----------

Prévoir :

* un serveur Debian 12 ou 13 à jour ;
* un compte utilisateur avec ``sudo`` ;
* une adresse IP fixe ou une réservation DHCP ;
* un nom DNS si le serveur doit être joint par un domaine ;
* les ports ``80`` et ``443`` ouverts vers le serveur ;
* le port ``1883`` ouvert uniquement depuis le réseau local des ESP32/Raspberry ;
* au moins 4 Go de RAM pour un confort correct avec Grafana, Django, Celery et
  TimescaleDB.

Ne pas exposer directement sur Internet les ports ``5432``, ``6379``, ``8000``,
``3000``, ``5173``, ``8025`` ou ``1025``.

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

   MQTT_HOST=mqtt
   MQTT_PORT=1883
   MQTT_USERNAME=station_backend
   MQTT_PASSWORD=<mot de passe station_backend>
   MQTT_RASPBERRY_USERNAME=raspberry_kiosk
   MQTT_RASPBERRY_PASSWORD=<mot de passe raspberry_kiosk>
   MQTT_ACK_REQUIRED=True
   MQTT_TLS_ENABLED=False
   MQTT_PUBLISHED_HOST=127.0.0.1

   SECURE_SSL_REDIRECT=True
   SESSION_COOKIE_SECURE=True
   CSRF_COOKIE_SECURE=True
   JWT_REFRESH_COOKIE_SECURE=True
   SECURE_HSTS_SECONDS=31536000
   SECURE_HSTS_INCLUDE_SUBDOMAINS=True
   SECURE_HSTS_PRELOAD=True

   TELEMETRY_RETENTION_DAYS=90
   CELERY_BEAT_TELEMETRY_RETENTION_SECONDS=86400

   ADMIN_EMAIL=<email admin>
   ADMIN_PASSWORD=<mot de passe admin fort>

Si le serveur est utilisé uniquement en réseau local sans domaine, remplacer
``station.example.com`` par l'adresse IP fixe du serveur. Dans ce cas, HTTPS
fonctionnera avec un certificat autosigné, mais les navigateurs afficheront un
avertissement tant que le certificat n'est pas approuvé.

Les options ``SECURE_HSTS_SECONDS``, ``SECURE_HSTS_INCLUDE_SUBDOMAINS`` et
``SECURE_HSTS_PRELOAD`` ne doivent être activées qu'après validation du
certificat et des sous-domaines de production. Une politique HSTS préchargée
est volontairement difficile à annuler côté navigateurs.
Le profil Nginx production contient également l'en-tête HSTS ; pour une
démonstration LAN avec certificat autosigné, utilisez plutôt le profil de
développement ou retirez temporairement cet en-tête.

``MQTT_PUBLISHED_HOST`` vaut ``127.0.0.1`` par défaut dans le profil production :
Mosquitto n'est donc pas joignable depuis les ESP32 tant que cette variable n'est
pas changée. Pour une station sur le LAN, utiliser l'adresse IP du serveur ou
``0.0.0.0``, puis limiter l'accès avec UFW.

Configuration TLS
-----------------

La configuration Nginx actuelle attend deux fichiers :

.. code-block:: text

   nginx/certs/localhost.crt
   nginx/certs/localhost.key

Pour une démonstration locale ou LAN, générer un certificat autosigné :

.. code-block:: bash

   mkdir -p nginx/certs
   openssl req -x509 -nodes -days 365 -newkey rsa:4096 \
     -keyout nginx/certs/localhost.key \
     -out nginx/certs/localhost.crt \
     -subj "/CN=station.local"

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
   sudo ufw allow from 192.168.1.0/24 to any port 1883 proto tcp
   sudo ufw enable
   sudo ufw status numbered

Adapter ``192.168.1.0/24`` au réseau réel des ESP32 et du Raspberry. Le port
MQTT ne doit pas être ouvert à tout Internet.

Durcissement Linux
------------------

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
   https://station.example.com/kiosk/    Interface borne
   https://station.example.com/grafana/  Supervision Grafana

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

Configuration Raspberry et ESP32
--------------------------------

Les Raspberry et ESP32 doivent joindre le serveur Debian par son IP fixe ou son
nom DNS.

Pour le Raspberry :

.. code-block:: text

   BACKEND_API_BASE_URL=https://station.example.com/api
   MQTT_HOST=192.168.1.50
   MQTT_PORT=1883
   MQTT_USERNAME=raspberry_kiosk
   MQTT_PASSWORD=<mot de passe raspberry_kiosk>
   MQTT_ACK_REQUIRED=True
   TERMINAL_API_SECRET=<même valeur que côté backend>

Pour l'ESP32 :

.. code-block:: text

   WIFI_SSID=<SSID du réseau>
   WIFI_PASSWORD=<mot de passe Wi-Fi>
   MQTT_HOST=192.168.1.50
   MQTT_PORT=1883
   MQTT_USER=esp32_station_demo_borne_1_slot1
   MQTT_PASSWORD=<mot de passe de l'emplacement ESP32>

L'ESP32 publie sa télémétrie vers Mosquitto. Le backend ne reçoit pas les mesures
en HTTP direct : ``mqtt-bridge`` consomme les topics MQTT et écrit en base.

Test MQTT
---------

Observer les messages MQTT depuis le serveur :

.. code-block:: bash

   docker compose -f docker-compose.prod.yml exec mqtt mosquitto_sub -h localhost -t 'station/#' -v -C 10 -W 20

Si des identifiants MQTT sont activés :

.. code-block:: bash

   docker compose -f docker-compose.prod.yml exec mqtt sh -c 'mosquitto_sub -h localhost \
     -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" \
     -t "station/#" -v -C 10 -W 20'

Pour un réseau Wi-Fi ESP32, vérifier que :

* l'ESP32 est sur le même réseau que le serveur ou qu'une route existe ;
* le port ``1883`` est autorisé depuis ce réseau ;
* le topic publié correspond au préfixe de la borne/emplacement ;
* ``mqtt-bridge`` est ``healthy`` dans ``docker compose -f docker-compose.prod.yml ps``.

Sauvegardes
-----------

Les scripts opérationnels sont versionnés :

* ``scripts/backup-prod.sh`` produit un dump SQL compressé avec checksum SHA-256 ;
* ``scripts/restore-prod.sh`` restaure un dump et exige
  ``RESTORE_CONFIRM=YES`` pour éviter une restauration accidentelle.

Créer un dossier de sauvegarde :

.. code-block:: bash

   mkdir -p /opt/station/backups
   chmod 700 /opt/station/backups

Sauvegarder la base PostgreSQL/TimescaleDB :

.. code-block:: bash

   BACKUP_DIR=/opt/station/backups scripts/backup-prod.sh

Tester une restauration dans une base de préproduction ou un serveur jetable :

.. code-block:: bash

   RESTORE_CONFIRM=YES scripts/restore-prod.sh /opt/station/backups/station_YYYYMMDDTHHMMSSZ.sql.gz

Ne jamais tester une restauration directement sur la production active sans
fenêtre de maintenance, sauvegarde récente et validation manuelle.

Lister les volumes Docker pour identifier le nom exact des volumes :

.. code-block:: bash

   docker volume ls

Les volumes importants sont :

* ``postgres_data`` pour la base ;
* ``grafana_data`` pour Grafana ;
* ``mqtt_data`` et ``mqtt_log`` pour Mosquitto ;
* ``mailpit_data`` pour les emails capturés.

Planifier au minimum une sauvegarde quotidienne de la base et une sauvegarde
régulière des volumes Grafana/Mosquitto. Exemple de cron quotidien à 02:15 :

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

Anonymisation PostgreSQL
------------------------

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
   docker compose -f docker-compose.prod.yml exec mqtt-bridge python manage.py check_mqtt_bridge_health
   docker compose -f docker-compose.prod.yml exec backend python manage.py check --deploy

Service systemd
---------------

Créer un service systemd pour relancer la stack au démarrage du serveur :

.. code-block:: bash

   sudo nano /etc/systemd/system/station.service

Contenu :

.. code-block:: ini

   [Unit]
   Description=Station de recharge - Docker Compose
   Requires=docker.service
   After=docker.service network-online.target
   Wants=network-online.target

   [Service]
   Type=oneshot
   RemainAfterExit=yes
   WorkingDirectory=/opt/station
   ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d --build
   ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down
   TimeoutStartSec=0

   [Install]
   WantedBy=multi-user.target

Activer le service :

.. code-block:: bash

   sudo systemctl daemon-reload
   sudo systemctl enable --now station.service
   sudo systemctl status station.service

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
* activer TLS pour MQTT si le réseau n'est pas totalement maîtrisé ;
* remplacer Mailpit par un SMTP réel ;
* configurer un fournisseur SMS réel si le code SMS doit être envoyé hors mode
  démonstration ;
* définir une stratégie de sauvegarde, restauration et rotation des logs ;
* exécuter régulièrement les tests backend, frontend, Raspberry et le scénario
  de bout en bout automatisé.
