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

Si ``sphinx-build`` n'est pas disponible dans le ``PATH`` mais que
l'environnement virtuel contient bien les dépendances de documentation :

.. code-block:: powershell

   $env:DEBUG="True"
   $env:SECRET_KEY="docs-local-secret-key-not-for-production"
   .\.venv\Scripts\python.exe -m sphinx -b html docs\source docs\build\html

Sous Linux/macOS :

.. code-block:: bash

   make -C docs html

La sortie HTML est générée dans ``docs/build/html/``.

Lancer la stack locale
----------------------

La stack Docker démarre le backend, le frontend, le kiosque Raspberry, le broker
MQTT, Redis, TimescaleDB/PostgreSQL, Celery, Grafana et le reverse proxy Nginx :

.. code-block:: bash

   docker compose up -d --build

Le chemin local recommandé pour une démonstration proche production passe par
Nginx :

.. code-block:: text

   http://localhost/          -> frontend
   http://localhost/api/      -> API Django
   http://localhost/admin/    -> admin Django
   http://localhost/grafana/  -> Grafana
   http://localhost/kiosk/    -> kiosque Raspberry

Les ports directs ``8000``, ``5173``, ``3000`` et ``9000`` restent exposés pour
le diagnostic pendant le développement.

Vérifier Nginx et MQTT
----------------------

Valider la configuration Docker Compose :

.. code-block:: bash

   docker compose config --quiet

Valider la syntaxe du reverse proxy :

.. code-block:: bash

   docker compose run --rm --no-deps reverse-proxy nginx -t

Envoyer une commande MQTT via le Raspberry :

.. code-block:: bash

   curl -X POST http://localhost:9000/mqtt/command \
     -H "Content-Type: application/json" \
     -d '{"slot_id":"slot1","action":"START","session_id":"demo"}'

Le firmware ESP32 publie sa télémétrie sur ``station/<slot_id>/telemetry`` et
écoute les commandes sur ``station/<slot_id>/cmd``.

Ce qui est automatique
----------------------

La référence backend est alimentée par Sphinx autodoc à partir des docstrings
des modules Python, et le schéma OpenAPI est généré par drf-spectacular à partir
des vues DRF et des serializers.

Les pages narratives, comme ``architecture.rst`` ou les notes de flux métier,
ne sont pas réécrites automatiquement : elles doivent être maintenues dans le
dépôt quand le comportement produit change.

Vérifier le schéma API
----------------------

.. code-block:: bash

   docker compose exec backend python manage.py spectacular --validate

Vérifier la configuration de production
---------------------------------------

Avant une mise en production, lancer le contrôle Django avec des variables
réalistes. ``DEBUG`` doit être désactivé, ``SECRET_KEY`` doit être long et
aléatoire, et ``ALLOWED_HOSTS`` doit contenir les domaines réels.

.. code-block:: powershell

   $env:DEBUG="False"
   $env:SECRET_KEY="<secret-long-et-aleatoire>"
   $env:ALLOWED_HOSTS="example.com"
   .\.venv\Scripts\python.exe backend\manage.py check --deploy

Les cookies de session, CSRF et refresh JWT doivent être marqués ``Secure`` en
production. ``SECURE_HSTS_SECONDS`` peut être activé après validation du HTTPS;
``SECURE_HSTS_PRELOAD`` ne doit être activé que si le domaine est prêt pour la
preload list navigateur.

Lancer les tests
----------------

Les tests pytest sont exécutés automatiquement pendant le build de l'image
backend. Si un test échoue, ``docker compose up -d --build`` s'arrête avant de
lancer les services.

Le workflow GitHub Actions ``CI`` relance aussi les tests backend, la qualité
des docstrings backend, la validation frontend avec ``npm run verify`` et la
génération de la documentation HTML sur chaque push et pull request.

Automatisations DevSecOps
-------------------------

Le dépôt contient aussi :

* un workflow ``Documentation Pages`` pour reconstruire la documentation Sphinx
  et la publier sur GitHub Pages après chaque merge dans ``main`` ;
* un workflow ``CodeQL`` pour analyser le code Python et JavaScript sur push,
  pull request, exécution manuelle et planification hebdomadaire ;
* un workflow ``Generate SBOM and VEX`` pour produire les SBOM CycloneDX/SPDX,
  scanner l'image backend avec Grype, publier le SARIF dans GitHub Code
  Scanning et générer un brouillon OpenVEX si des vulnérabilités sont détectées ;
* une configuration Dependabot pour proposer des mises à jour hebdomadaires des
  dépendances GitHub Actions, npm, pip et Docker.

Le workflow CodeQL versionné dans ``.github/workflows/codeql.yml`` est une
configuration avancée. Le ``Default setup`` CodeQL de GitHub doit rester
désactivé, sinon GitHub Code Scanning refuse les résultats SARIF produits par le
workflow avancé.

Protection de la branche principale
-----------------------------------

La branche ``main`` est protégée côté GitHub. Les changements doivent passer par
une pull request dont la branche est à jour et dont les statuts requis sont au
vert :

* ``Backend tests`` ;
* ``Backend quality`` ;
* ``Frontend verify`` ;
* ``Documentation build`` ;
* ``Analyze (python)`` ;
* ``Analyze (javascript-typescript)`` ;
* ``Backend image supply chain reports``.

Les conversations de revue doivent être résolues avant fusion. Les force-pushs
et suppressions de ``main`` sont désactivés, et la règle s'applique aussi aux
administrateurs du dépôt. Dependabot crée une branche et une pull request par
mise à jour proposée ; les montées de versions majeures doivent être relues avant
fusion.

Publication de la documentation HTML
------------------------------------

Le dossier ``docs/build/html`` est un artefact local ignoré par Git. Il peut être
reconstruit sur le poste de développement, mais il ne doit pas être committé.

La publication officielle est assurée par le workflow ``Documentation Pages`` :
il installe les dépendances de documentation, lance Sphinx puis publie
``docs/build/html`` via GitHub Pages à chaque merge dans ``main``. Le workflow
peut aussi être lancé manuellement depuis l'onglet Actions.

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

Vérifier le frontend
--------------------

Installer les dépendances frontend puis lancer les validations :

.. code-block:: powershell

   cd frontend
   npm ci
   npm run check:js
   npm run verify

``check:js`` valide la syntaxe des scripts JavaScript avec Node. ``verify``
enchaîne cette vérification, le build Vite de production et les tests
end-to-end Playwright. Avant le premier lancement local, installer le navigateur
de test avec ``npx playwright install chromium``.

Contrôler les docstrings
------------------------

Le backend configure Ruff et Interrogate dans ``backend/pyproject.toml``.
Ruff contrôle la qualité des docstrings existantes, tandis qu'Interrogate
mesure les docstrings manquantes. Les docstrings utilisent le style Google, qui
est repris par Sphinx grâce à ``sphinx.ext.napoleon``.

Installer les dépendances de développement :

.. code-block:: powershell

   .\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt

Vérifier le style des docstrings :

.. code-block:: powershell

   cd backend
   ..\.venv\Scripts\python.exe -m ruff check .

Mesurer la couverture documentaire :

.. code-block:: powershell

   cd backend
   ..\.venv\Scripts\python.exe -m interrogate api

Le seuil Interrogate est fixé à ``100`` : une nouvelle classe ou fonction suivie
par l'audit doit donc recevoir une docstring. Ruff active aussi les règles ``D``
pour contrôler la présence et le style des docstrings publiques.
