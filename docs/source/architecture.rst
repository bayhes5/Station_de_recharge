Architecture
============

Le projet est composé de quatre parties applicatives principales, complétées par
PostgreSQL et Redis dans la stack Docker locale.

Backend Django
--------------

Le dossier ``backend/`` contient la configuration Django, les modèles, les
serializers, les vues API et les commandes de bootstrap. L'API REST est exposée
sous ``/api/`` et utilise des jetons JWT.

Frontend Vite
-------------

Le dossier ``frontend/`` contient une application Vite multi-pages. Chaque page
HTML charge un module d'entrée sous ``frontend/src/pages/`` qui regroupe le
client API commun et le script métier de la page.

En développement, le service Docker ``frontend`` expose le serveur Vite sur le
port ``5173``. Les pages consomment l'API Django exposée sur ``8000``.

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

Les QR codes et codes temporaires sont rattachés à une réservation. Ils peuvent
être régénérés ou révoqués depuis l'administration des réservations, tandis que
le terminal refuse les moyens d'accès expirés ou révoqués. Les actions sensibles
sont journalisées dans ``JournalSecurite``.

Kiosque Raspberry
-----------------

Le dossier ``raspberry/app/`` contient une interface locale simple exposée sur le
port ``9000`` dans la stack Docker.

ESP32
-----

Le dossier ``esp32/`` contient le prototype de logique embarquée pour un
emplacement de recharge. En configuration de démonstration, le backend crée
trois emplacements et associe un device ``ESP32`` à chacun d'eux.

Cache Redis
-----------

Le service Docker ``redis`` expose un cache partagé sur le port ``6379``. Django
l'utilise quand ``CACHE_URL`` est défini, notamment pour le catalogue des
stations. Sans ``CACHE_URL``, le backend revient à un cache local en mémoire.
