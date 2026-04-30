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
