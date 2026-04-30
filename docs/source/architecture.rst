Architecture
============

Le projet est composé de quatre parties principales.

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

Kiosque Raspberry
-----------------

Le dossier ``raspberry/app/`` contient une interface locale simple exposée sur le
port ``9000`` dans la stack Docker.

ESP32
-----

Le dossier ``esp32/`` contient le prototype de logique embarquée pour un
emplacement de recharge. En configuration de démonstration, le backend crée
trois emplacements et associe un device ``ESP32`` à chacun d'eux.
