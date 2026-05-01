Documentation API
=================

La documentation API interactive est fournie par drf-spectacular.

Endpoints locaux
----------------

Une fois le backend démarré :

* Schéma OpenAPI brut : ``http://localhost:8000/api/schema/``
* Swagger UI : ``http://localhost:8000/api/docs/``
* Redoc : ``http://localhost:8000/api/redoc/``

Générer un fichier OpenAPI
--------------------------

Depuis le conteneur backend :

.. code-block:: bash

   docker compose exec backend python manage.py spectacular --file schema.yml

Depuis un environnement Python local placé dans ``backend/`` :

.. code-block:: bash

   python manage.py spectacular --file schema.yml

Les vues fonctionnelles DRF peuvent ensuite être enrichies avec
``@extend_schema`` pour préciser les requêtes, réponses, exemples et tags quand
l'inférence automatique ne suffit pas.

Note sur la réservation
-----------------------

La création d'une réservation utilisateur attend une station, un créneau et un
mode d'authentification. Le champ ``emplacement`` est optionnel pour ce flux :
si aucun emplacement n'est fourni, l'API attribue automatiquement un emplacement
disponible dans la station demandée.

L'endpoint de disponibilité expose notamment ``available_count`` et
``total_count`` pour permettre au frontend d'afficher une disponibilité globale
de station plutôt qu'une sélection manuelle de place.

Endpoints d'administration des accès
------------------------------------

Les moyens d'accès sont séparés selon leur durée de vie :

* les badges RFID persistants sont gérés sur l'utilisateur avec
  ``/api/admin/users/<user_id>/auth-methods/``;
* la révocation d'un badge RFID passe par
  ``/api/admin/users/<user_id>/auth-methods/<auth_id>/revoke/``;
* l'utilisateur affiche le QR/code courant de sa réservation avec
  ``/api/reservations/<reservation_id>/access-payload/`` sans rotation du secret;
* les QR codes et codes temporaires sont gérés sur la réservation avec
  ``/api/admin/reservations/<reservation_id>/access-payload/`` pour régénérer
  une valeur temporaire sans l'afficher dans une fenêtre de copie côté admin;
* la révocation d'un QR/code temporaire passe par
  ``/api/admin/reservations/<reservation_id>/revoke-access/``.

Ces endpoints exigent un utilisateur authentifié avec les droits staff. Ils ne
renvoient jamais la valeur complète d'un badge RFID. Les QR codes et codes
temporaires sont dérivés côté serveur : l'utilisateur peut afficher ou masquer
le même accès, tandis que l'administration dispose d'une action explicite de
régénération qui invalide l'ancienne valeur. Si l'accès est déjà visible côté
utilisateur, l'interface récupère automatiquement la valeur courante après la
régénération.
