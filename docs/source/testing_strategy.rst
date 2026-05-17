Stratégie de tests
==================

Cette page décrit les tests à lancer pendant le développement, les tests
automatisés existants et les scénarios manuels de recette.

Objectifs
---------

Les tests doivent vérifier :

* la cohérence des réservations et des accès ;
* la sécurité de l'authentification ;
* la robustesse du terminal Raspberry ;
* l'ingestion des télémétries et la création d'alertes ;
* la validité du frontend ;
* la documentation et la configuration Docker/Nginx ;
* les scénarios matériels simulés avant intégration physique.

Tests automatisés backend
-------------------------

Le backend utilise ``pytest`` et ``pytest-django`` avec ``config.test_settings``.
La base de test est SQLite pour rester rapide et indépendante de PostgreSQL.

Commande complète :

.. code-block:: powershell

   cd backend
   ..\.venv\Scripts\python.exe -m pytest

Tests ciblés utiles :

.. code-block:: powershell

   cd backend
   ..\.venv\Scripts\python.exe -m pytest api\tests\test_terminal_auth.py
   ..\.venv\Scripts\python.exe -m pytest api\tests\test_mqtt_ingestion.py

Couverture :

.. code-block:: powershell

   cd backend
   ..\.venv\Scripts\python.exe -m pytest --cov=api --cov-report=term-missing

Tests couverts actuellement :

* inscription, connexion et profil ;
* création et validation de réservations ;
* administration utilisateurs/réservations ;
* génération et révocation QR/code SMS/RFID ;
* authentification terminal QR/code SMS/RFID ;
* ingestion des télémétries vers capteurs/alertes ;
* performance de requêtes ciblées.

Qualité backend
---------------

Ruff vérifie les docstrings suivies par le projet, les erreurs Python probables,
les imports inutilisés et quelques pièges courants signalés par Bugbear :

.. code-block:: powershell

   cd backend
   ..\.venv\Scripts\python.exe -m ruff check .

Interrogate mesure la couverture documentaire :

.. code-block:: powershell

   cd backend
   ..\.venv\Scripts\python.exe -m interrogate api

Tests frontend
--------------

Le frontend utilise Vite, un script de vérification syntaxique et Playwright.

.. code-block:: powershell

   cd frontend
   npm ci
   npm run check:js
   npm run verify

``npm run verify`` enchaîne :

* vérification syntaxique JavaScript ;
* build Vite de production ;
* tests end-to-end Playwright.

Pour la couche PWA, le build doit aussi contenir ``manifest.webmanifest``,
``sw.js`` et l'icône installable. Les tests E2E peuvent ensuite vérifier que le
manifeste est référencé sur les pages principales et que l'application reste
utilisable même si l'enregistrement du service worker échoue.

Avant le premier lancement Playwright :

.. code-block:: powershell

   cd frontend
   npx playwright install chromium

Tests configuration
-------------------

Docker Compose :

.. code-block:: bash

   docker compose config --quiet

Nginx reverse proxy :

.. code-block:: bash

   docker compose run --rm --no-deps reverse-proxy nginx -t

Django :

.. code-block:: powershell

   .\.venv\Scripts\python.exe backend\manage.py check --settings=config.test_settings

Documentation Sphinx
--------------------

Construction locale :

.. code-block:: powershell

   .\docs\make.bat html

Variante fiable si ``sphinx-build`` n'est pas dans le ``PATH`` :

.. code-block:: powershell

   $env:DEBUG="True"
   $env:SECRET_KEY="docs-local-secret-key-not-for-production"
   .\.venv\Scripts\python.exe -m sphinx -b html docs\source docs\build\html

La sortie est générée dans ``docs/build/html``. Ce dossier est un artefact local
et ne doit pas être committé.

Tests télémétrie, commandes et supervision
------------------------------------------

Test d'ingestion backend :

.. code-block:: powershell

   cd backend
   ..\.venv\Scripts\python.exe -m pytest api\tests\test_mqtt_ingestion.py
   ..\.venv\Scripts\python.exe -m pytest api\tests\test_admin_api.py

Test manuel d'une commande via Raspberry :

.. code-block:: bash

   curl -X POST http://localhost:9000/mqtt/command \
     -H "Content-Type: application/json" \
     -d '{"slot_id":"slot1","action":"START","session_id":"demo"}'

Test unitaire du comportement ACK côté Raspberry :

.. code-block:: powershell

   .\.venv\Scripts\python.exe -m pytest raspberry\tests -q

Ce test vérifie trois cas sans ESP32 physique : commande acceptée sans ACK en
développement, refus en mode ``MQTT_ACK_REQUIRED=true`` et acceptation lorsqu'un
ACK correspondant au ``command_id`` est reçu.
Le workflow CI exécute aussi ``Raspberry edge tests`` : compilation des modules
Python du kiosque et exécution de ``raspberry/tests``.

Test local de télémétrie temps réel sans ESP32 :

.. code-block:: bash

   docker compose up -d mqtt
   docker compose --profile simulation run --rm mqtt-simulator
   docker compose logs -f mqtt-bridge
   docker compose logs -f celery

Test complet QR -> kiosk -> télémétrie -> Grafana sans ESP32 :

.. code-block:: powershell

   .\scripts\run-demo-scenario.ps1 -Reference DEMOQR1 -Emplacement 1 -TelemetryCount 5

Le script vérifie que la télémétrie simulée se limite à l'emplacement autorisé
par la réservation et que la session est clôturée proprement après ``STOP``.

Contrôle rapide des mesures en base :

.. code-block:: bash

   docker compose exec backend python manage.py shell -c "from django.utils import timezone; from datetime import timedelta; from api.models import CapteurData; now=timezone.now(); print(CapteurData.objects.filter(timestamp__gte=now-timedelta(minutes=1)).count())"

Test Wokwi vers Grafana :

1. Configurer temporairement ``MQTT_HOST=test.mosquitto.org`` pour le bridge.
2. Démarrer la stack Docker.
3. Lancer ``esp32/wokwi/`` dans Wokwi.
4. Vérifier les logs d'ingestion côté ``mqtt-bridge``.
5. Ouvrir ``https://localhost/grafana/d/station-overview/station-vue-globale-supervision?orgId=1&from=now-6h&to=now&refresh=10s``.
6. Filtrer par station, borne ou emplacement, puis ouvrir le détail technique si
   nécessaire.

Scénarios manuels de recette
----------------------------

Réservation utilisateur :

* créer un compte ;
* réserver un créneau ;
* afficher le QR ou envoyer le code SMS ;
* vérifier l'historique utilisateur.

RFID :

* générer un code d'association depuis le profil ;
* saisir le code sur le kiosque ;
* scanner/simuler le badge ;
* réserver en mode RFID ;
* s'authentifier directement au kiosque.

Kiosque Raspberry :

* tester l'accueil en ``1024x600`` ;
* tester QR, code et RFID ;
* vérifier mauvais code, mauvais moyen d'accès et mauvaise station ;
* vérifier l'envoi de ``START`` à l'emplacement.

ESP32 / Wokwi :

* passer de ``idle`` à ``reserved`` puis ``charging`` ;
* ouvrir le boîtier pendant la charge ;
* retirer le câble pendant la charge ;
* augmenter le courant au-dessus du seuil ;
* augmenter la température au-dessus du seuil ;
* vérifier que les alertes passent de ``nouvelle`` à ``active`` puis
  ``resolue`` quand la télémétrie revient à la normale ;
* vérifier les alertes dans la base, l'interface admin et Grafana.

Sécurité :

* tester mot de passe faible ;
* tester refresh/logout ;
* vérifier qu'un utilisateur non admin ne peut pas accéder aux endpoints admin ;
* vérifier qu'un moyen d'accès révoqué ou expiré est refusé ;
* vérifier la journalisation des actions sensibles.

Critères de validation
----------------------

Un changement est considéré prêt lorsqu'il respecte les points suivants :

* tests backend ciblés ou complets au vert ;
* vérification frontend si une page web est modifiée ;
* ``docker compose config --quiet`` au vert si Docker change ;
* ``nginx -t`` au vert si Nginx change ;
* documentation mise à jour pour tout nouveau flux ;
* PR GitHub avec les checks requis au vert avant merge dans ``main``.
