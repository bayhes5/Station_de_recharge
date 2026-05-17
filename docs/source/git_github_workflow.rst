Workflow Git et GitHub
======================

Cette page décrit le flux Git/GitHub utilisé pour le projet. L'objectif est de
garder ``main`` stable, traçable et toujours validée par les tests.

Principes
---------

* ``main`` est la branche stable du projet.
* Les changements passent par une branche dédiée et une pull request.
* Les fichiers générés, comme ``docs/build/html`` ou ``frontend/dist`` local, ne
  doivent pas être ajoutés manuellement sauf décision explicite du projet.
* Un commit doit contenir un changement cohérent : documentation, correction,
  fonctionnalité ou test.
* Une pull request n'est fusionnée que lorsque les checks requis sont au vert.

Premier clone
-------------

.. code-block:: powershell

   git clone https://github.com/bayhes5/Station_de_recharge.git
   cd Station_de_recharge
   git status -sb

Récupérer les dernières modifications
-------------------------------------

Avant de commencer une tâche :

.. code-block:: powershell

   git switch main
   git pull --ff-only origin main

Créer une branche de travail
----------------------------

Utiliser un nom court, descriptif et neutre :

.. code-block:: powershell

   git switch -c docs-supervision-tests

Exemples de noms :

* ``feature-admin-supervision`` ;
* ``fix-terminal-auth`` ;
* ``docs-github-workflow`` ;
* ``mqtt-alerts-api``.

Vérifier les changements
------------------------

Voir l'état du dépôt :

.. code-block:: powershell

   git status -sb

Voir les fichiers modifiés :

.. code-block:: powershell

   git diff --stat

Voir le contenu exact d'une modification :

.. code-block:: powershell

   git diff

Ajouter les fichiers au commit
------------------------------

Préférer un staging explicite :

.. code-block:: powershell

   git add README.md docs/source/development.rst

Pour vérifier ce qui sera committé :

.. code-block:: powershell

   git diff --cached --stat
   git diff --cached

Créer le commit
---------------

.. code-block:: powershell

   git commit -m "Document supervision tests and simulation"

Le message doit être court et expliquer le résultat, pas seulement l'action.

Pousser la branche
------------------

.. code-block:: powershell

   git push -u origin docs-supervision-tests

Créer une pull request
----------------------

Avec GitHub CLI :

.. code-block:: powershell

   gh pr create --base main --head docs-supervision-tests --title "Document supervision tests and simulation"

La description doit contenir :

* ce qui change ;
* pourquoi cela change ;
* les impacts utilisateur ou technique ;
* les vérifications effectuées.

Surveiller les checks
---------------------

.. code-block:: powershell

   gh pr checks --watch --interval 10

Checks attendus
---------------

Les checks principaux du projet sont :

* ``Backend tests`` ;
* ``Backend quality`` ;
* ``Raspberry edge tests`` ;
* ``Frontend verify`` ;
* ``Documentation build`` ;
* ``Analyze (python)`` ;
* ``Analyze (javascript-typescript)`` ;
* ``Backend image supply chain reports``.

Documentation publiée
---------------------

Le workflow ``Documentation Pages`` reconstruit Sphinx à chaque merge dans
``main`` puis publie le résultat sur GitHub Pages :

.. code-block:: text

   https://bayhes5.github.io/Station_de_recharge/

Le dossier ``docs/build/html`` reste un artefact local ignoré par Git. Les pages
publiées doivent donc toujours provenir des sources ``docs/source``.

Fusionner la pull request
-------------------------

Quand les checks sont au vert :

.. code-block:: powershell

   gh pr merge --merge --delete-branch

Puis revenir à jour localement :

.. code-block:: powershell

   git switch main
   git pull --ff-only origin main

Résoudre un conflit simple
--------------------------

Si Git indique un conflit pendant un rebase ou un merge :

.. code-block:: powershell

   git status -sb

Ouvrir les fichiers en conflit, conserver la bonne version, puis :

.. code-block:: powershell

   git add <fichier>
   git rebase --continue

Si le rebase devient trop risqué, il vaut mieux demander de l'aide plutôt que de
forcer une résolution approximative.

Commandes utiles
----------------

Voir les branches locales :

.. code-block:: powershell

   git branch

Voir les commits récents :

.. code-block:: powershell

   git log --oneline --decorate -10

Voir la branche distante suivie :

.. code-block:: powershell

   git status -sb

Supprimer une branche locale déjà fusionnée :

.. code-block:: powershell

   git branch -d docs-supervision-tests

Règles de prudence
------------------

* Ne pas utiliser ``git reset --hard`` sans sauvegarde ou validation explicite.
* Ne pas faire de force-push sur une branche partagée sans accord.
* Ne pas committer les secrets, tokens, mots de passe ou fichiers ``.env`` réels.
* Ne pas ajouter automatiquement tout le dépôt avec ``git add -A`` si des
  changements ne font pas partie de la tâche.
* Relancer les tests adaptés avant de pousser.
