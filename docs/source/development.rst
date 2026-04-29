Développement
=============

Installer les dépendances de documentation
------------------------------------------

Depuis la racine du projet :

.. code-block:: bash

   pip install -r backend/requirements.txt
   pip install -r docs/requirements.txt

Construire la documentation HTML
--------------------------------

Sous Windows :

.. code-block:: powershell

   .\docs\make.bat html

Sous Linux/macOS :

.. code-block:: bash

   make -C docs html

La sortie HTML est générée dans ``docs/build/html/``.

Vérifier le schéma API
----------------------

.. code-block:: bash

   docker compose exec backend python manage.py spectacular --validate

Lancer les tests
----------------

Les tests pytest sont exécutés automatiquement pendant le build de l'image
backend. Si un test échoue, ``docker compose up -d --build`` s'arrête avant de
lancer les services.

Installer les dépendances de développement :

.. code-block:: powershell

   .\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt

Exécuter la suite pytest :

.. code-block:: powershell

   cd backend
   ..\.venv\Scripts\python.exe -m pytest

Relancer uniquement le build backend et donc les tests :

.. code-block:: bash

   docker compose build backend

Exécuter les tests avec couverture :

.. code-block:: powershell

   cd backend
   ..\.venv\Scripts\python.exe -m pytest --cov=api --cov-report=term-missing

La configuration pytest utilise ``config.test_settings`` et une base SQLite de
test, afin de ne pas dépendre de PostgreSQL pendant les tests unitaires.
