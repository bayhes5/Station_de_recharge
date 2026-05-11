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
un créneau de début. L'utilisateur ne choisit pas directement l'emplacement :
le backend vérifie les disponibilités de la station sur la fenêtre de 30 minutes
et attribue automatiquement un emplacement libre au moment de la création.

Les emplacements restent des objets métier côté backend. Ils portent la
réservation effective, les sessions de charge et le rattachement aux devices
ESP32.

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
port ``9000`` dans la stack Docker.

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
sur les emplacements de la station. Les ESP32 conservent de leur côté les
événements et télémétries non transmis dans un journal local, par exemple via
LittleFS, puis les republient lorsque la communication revient.

Ce choix évite de faire de la communication directe Raspberry -> ESP32 le mode
principal. Le backend reste la source de vérité pour la sécurité, l'audit et la
cohérence des réservations ; le mode local sert uniquement de continuité
opérationnelle.

Reverse proxy local
-------------------

Le dossier ``nginx/`` contient une configuration de reverse proxy locale qui
centralise les routes d'accès :

* ``/`` vers le frontend Vite ;
* ``/api/`` et ``/admin/`` vers Django ;
* ``/grafana/`` vers Grafana ;
* ``/kiosk/`` vers le kiosque Raspberry.

Cette configuration prépare la mise en production en isolant progressivement les
services internes derrière un point d'entrée unique. En développement, Nginx
écoute ``80`` et ``443`` : le trafic HTTP est redirigé vers HTTPS et le
certificat auto-signé local permet de valider les cookies sécurisés, les routes
proxy et les en-têtes ``X-Forwarded-Proto`` dans des conditions proches d'un
déploiement réel. Les ports directs restent disponibles pour le diagnostic.

ESP32
-----

Le dossier ``esp32/`` contient la logique embarquée de référence pour un
emplacement de recharge. En configuration locale, le backend crée
trois emplacements et associe un device ``ESP32`` à chacun d'eux.

Les ESP32, la simulation Wokwi ou le service Docker ``mqtt-simulator`` publient
les mesures sur le canal ``station/<slot_id>/telemetry``. Le service
``mqtt-bridge`` écoute ces canaux, délègue le traitement à Celery, puis le backend stocke les
échantillons dans ``CapteurData`` et met à jour ``Device.last_seen``. Cette
chaîne alimente l'interface de supervision et le dashboard Grafana en quasi temps
réel.

La supervision distingue la connexion de l'équipement et son dernier état métier
reçu. La connexion est calculée avec ``Device.last_seen`` : un ESP32 sans
télémétrie récente est considéré hors ligne, même si son dernier ``status``
stocké vaut ``online``. Le champ ``status`` reste une information métier
historisée, par exemple ``charging`` ou ``error``.

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
