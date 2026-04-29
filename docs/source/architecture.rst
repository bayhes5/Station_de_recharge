Architecture
============

Le projet est compose de quatre parties principales.

Backend Django
--------------

Le dossier ``backend/`` contient la configuration Django, les modeles, les
serializers, les vues API et les commandes de bootstrap. L'API REST est exposee
sous ``/api/`` et utilise des jetons JWT.

Frontend statique
-----------------

Le dossier ``frontend/`` contient les pages HTML, CSS et JavaScript servies par
Nginx. Ces pages consomment l'API Django.

Kiosque Raspberry
-----------------

Le dossier ``raspberry/app/`` contient une interface locale simple exposee sur le
port ``9000`` dans la stack Docker.

ESP32
-----

Le dossier ``esp32/`` contient le prototype de logique embarquee pour un
emplacement de recharge.
