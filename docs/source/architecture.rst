Architecture
============

Le projet est composé de quatre parties principales.

Backend Django
--------------

Le dossier ``backend/`` contient la configuration Django, les modèles, les
serializers, les vues API et les commandes de bootstrap. L'API REST est exposée
sous ``/api/`` et utilise des jetons JWT.

Frontend statique
-----------------

Le dossier ``frontend/`` contient les pages HTML, CSS et JavaScript servies par
Nginx. Ces pages consomment l'API Django.

Kiosque Raspberry
-----------------

Le dossier ``raspberry/app/`` contient une interface locale simple exposée sur le
port ``9000`` dans la stack Docker.

ESP32
-----

Le dossier ``esp32/`` contient le prototype de logique embarquée pour un
emplacement de recharge. En configuration de démonstration, le backend crée
trois emplacements et associe un device ``ESP32`` à chacun d'eux.
