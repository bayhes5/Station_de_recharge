Documentation API
=================

La documentation API interactive est fournie par drf-spectacular.

Endpoints locaux
----------------

Une fois le backend demarre :

* Schema OpenAPI brut : ``http://localhost:8000/api/schema/``
* Swagger UI : ``http://localhost:8000/api/docs/``
* Redoc : ``http://localhost:8000/api/redoc/``

Generer un fichier OpenAPI
--------------------------

Depuis le conteneur backend :

.. code-block:: bash

   docker compose exec backend python manage.py spectacular --file schema.yml

Depuis un environnement Python local place dans ``backend/`` :

.. code-block:: bash

   python manage.py spectacular --file schema.yml

Les vues fonctionnelles DRF peuvent ensuite etre enrichies avec
``@extend_schema`` pour preciser les requetes, reponses, exemples et tags quand
l'inference automatique ne suffit pas.
