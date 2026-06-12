Architecture
============

Le projet est composé de quatre parties applicatives principales, complétées par
TimescaleDB/PostgreSQL, Redis, Mosquitto, Grafana et Nginx dans la stack Docker
locale.

Backend Django
--------------

Le dossier ``backend/`` contient la configuration Django, les modèles, les
serializers, les vues API et les commandes de bootstrap. L'API REST est exposée
sous ``/api/`` et utilise des jetons JWT. Le refresh token navigateur est placé
dans un cookie ``HttpOnly``; le frontend garde seulement le jeton d'accès en
mémoire et le renouvelle via ``/api/token/refresh/``.

Frontend Vite
-------------

Le dossier ``frontend/`` contient une application Vite multi-pages. Chaque page
HTML charge un module d'entrée sous ``frontend/src/pages/`` qui regroupe le
client API commun et le script métier de la page.

En développement, le service Docker ``frontend`` expose le serveur Vite sur le
port ``5173``. Les pages consomment l'API Django exposée sur ``8000``.

Le frontend est aussi installable comme PWA. Le manifeste et le service worker
sont servis depuis ``frontend/public/``. Ils donnent une expérience mobile proche
d'une application native sans créer un client séparé : l'utilisateur peut garder
le dashboard sur l'écran d'accueil de son téléphone, tandis que les données
métier restent récupérées en ligne depuis l'API.

Réservation
-----------

Le flux utilisateur de réservation sélectionne une station sur une carte, puis
un début et une durée de recharge. L'utilisateur ne choisit pas directement
l'emplacement : le backend vérifie les bornes et emplacements disponibles sur la
fenêtre demandée, puis attribue automatiquement un emplacement libre au moment de
la création. Les durées proposées sont 30 minutes, 1 heure, 2 heures et 4 heures,
avec 1 heure par défaut. Le début et la fin du créneau sont alignés sur un pas de
5 minutes, puis un buffer technique de 5 minutes est ajouté après le créneau pour
préparer l'emplacement suivant.

Les emplacements restent des objets métier côté backend. Ils portent la
réservation effective, les sessions de charge et le rattachement aux devices
ESP32.

L'infrastructure est structurée en trois niveaux : ``Station`` pour le lieu,
``Borne`` pour l'armoire ou le kiosque physique, puis ``Emplacement`` pour le
point de charge réellement réservé. Le champ station reste disponible sur
l'emplacement pour les filtres rapides, mais il est dérivé de la borne afin de
conserver la hiérarchie terrain.

Moyens d'accès
--------------

Le backend distingue les badges RFID persistants des accès temporaires. Les
badges RFID sont rattachés au compte utilisateur et peuvent être gérés depuis le
profil ou depuis l'écran administrateur de modification d'un utilisateur. La
valeur complète du badge n'est pas exposée dans l'administration.

Les QR codes et codes SMS temporaires sont rattachés à une réservation. Ils peuvent
être régénérés ou révoqués depuis l'administration des réservations, tandis que
le terminal refuse les moyens d'accès expirés ou révoqués. La régénération admin
remplace la valeur côté serveur sans afficher le secret dans une fenêtre de copie;
l'endpoint admin ne renvoie pas la valeur régénérée. L'interface utilisateur
peut ensuite rafraîchir le QR courant ou l'état d'envoi du code SMS, sans exposer
le secret SMS en clair. Les
actions sensibles sont journalisées dans ``JournalSecurite``.

Kiosque Raspberry
-----------------

Le dossier ``raspberry/app/`` contient une interface locale simple exposée sur le
port ``9000``. En développement, elle peut être lancée dans Docker pour simuler
la borne. En production, elle tourne sur le Raspberry physique connecté à
l'écran tactile, au lecteur RFID et au broker local de la borne.

L'écran tactile cible une résolution de ``1024x600``. Les parcours critiques du
kiosque doivent être validés sur cette taille, notamment l'accueil, la lecture
RFID, la saisie code et l'association badge.

Le serveur Django reste le chemin nominal : il valide les réservations, les
moyens d'accès et la station attendue avant toute ouverture de charge. Le
Raspberry intervient comme interface de borne et comme relais local de commande
vers les ESP32.

Un mode dégradé est prévu pour maintenir une continuité minimale si le serveur
central ou la liaison applicative devient indisponible. Dans ce cas, le
Raspberry peut s'appuyer sur un cache local de droits déjà synchronisés,
strictement limité dans le temps, pour autoriser uniquement les actions prévues
sur les emplacements de la station et de la borne concernées. Les ESP32
conservent de leur côté les événements et télémétries non transmis dans un
journal local, par exemple via LittleFS, puis les republient lorsque la
communication revient.

Ce choix sépare clairement l'autorité métier et l'exécution terrain. Le backend
reste la source de vérité pour les réservations, les révocations, l'audit et la
cohérence globale. Le Raspberry, lui, exécute localement les commandes déjà
validées et conserve une continuité limitée grâce à son cache offline. Les ESP32
ne prennent jamais de décision d'accès : ils reçoivent des ordres locaux via
MQTT, appliquent les sécurités physiques et publient leurs états.

Reverse proxy local
-------------------

Le dossier ``nginx/`` contient une configuration de reverse proxy locale qui
centralise les routes d'accès :

* ``/`` vers le frontend Vite ;
* ``/api/`` et ``/admin/`` vers Django ;
* ``/grafana/`` vers Grafana.

Cette configuration prépare la mise en production en isolant progressivement les
services internes derrière un point d'entrée unique. En développement, Nginx
écoute ``80`` et ``443`` : le trafic HTTP est redirigé vers HTTPS et le
certificat auto-signé local permet de valider les cookies sécurisés, les routes
proxy et les en-têtes ``X-Forwarded-Proto`` dans des conditions proches d'un
déploiement réel. Les ports directs restent disponibles pour le diagnostic.
La route ``/kiosk/`` est uniquement une commodité de simulation en local ; en
production, l'interface tactile est servie par le Raspberry lui-même.

ESP32
-----

Le dossier ``esp32/`` contient la logique embarquée de référence pour un
emplacement de recharge. En configuration locale, le backend crée
trois emplacements et associe un device ``ESP32`` à chacun d'eux.

En production, le broker Mosquitto est installé localement sur le Raspberry de
la borne. Les ESP32, la simulation Wokwi ou le service Docker
``mqtt-simulator`` publient les mesures sur le canal
``station/<slot_id>/telemetry``. Les ESP32 publient également leurs événements
d'état sur ``station/<slot_id>/status`` et leurs alertes explicites sur
``station/<slot_id>/alert``. Le service ``mqtt-bridge`` écoute ces canaux quand
la liaison serveur est disponible, délègue le traitement à Celery, puis le
backend stocke les échantillons dans ``CapteurData`` et met à jour
``Device.last_seen``. Cette chaîne alimente l'interface de supervision et le
dashboard Grafana en quasi temps réel.

La supervision distingue la connexion de l'équipement et son dernier état métier
reçu. La connexion est calculée avec ``Device.last_seen`` : un ESP32 sans
télémétrie ni statut MQTT récent est considéré hors ligne, même si son dernier
``status`` stocké vaut ``online``. Le champ ``status`` reste une information
métier historisée, par exemple ``charging`` ou ``error``.

Les alertes opérationnelles sont créées depuis la télémétrie : intrusion,
câble retiré, surchauffe, surconsommation et état critique. Une alerte démarre
au statut ``nouvelle``, passe à ``active`` si l'anomalie continue, puis à
``resolue`` quand une télémétrie normale confirme le retour à l'état attendu.

Les ESP32 doivent aussi pouvoir réagir localement sans attendre le serveur pour
les sécurités physiques : arrêt de charge, déverrouillage contrôlé, émission
d'un événement d'alerte et journalisation locale. Le stockage embarqué ne
remplace pas la base centrale ; il évite la perte de traces pendant une coupure
temporaire.

Cache Redis
-----------

Le service Docker ``redis`` expose un cache partagé sur le port ``6379``. Django
l'utilise quand ``CACHE_URL`` est défini, notamment pour le catalogue des
stations. Sans ``CACHE_URL``, le backend revient à un cache local en mémoire.
