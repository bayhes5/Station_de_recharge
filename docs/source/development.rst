Developpement
=============

Installer les dependances de documentation
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

La sortie HTML est generee dans ``docs/build/html/``.

Verifier le schema API
----------------------

.. code-block:: bash

   docker compose exec backend python manage.py spectacular --validate

Lancer les tests
----------------

Installer les dependances de developpement :

.. code-block:: powershell

   .\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt

Executer la suite pytest :

.. code-block:: powershell

   cd backend
   ..\.venv\Scripts\python.exe -m pytest

Executer les tests avec couverture :

.. code-block:: powershell

   cd backend
   ..\.venv\Scripts\python.exe -m pytest --cov=api --cov-report=term-missing

La configuration pytest utilise ``config.test_settings`` et une base SQLite de
test, afin de ne pas dependre de PostgreSQL pendant les tests unitaires.
