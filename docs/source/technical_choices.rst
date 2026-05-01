Choix techniques
================

Cette page explique les principaux choix du projet. L'objectif est de garder une
trace des raisons, des bénéfices, des limites assumées et des alternatives
écartées quand elles ont été discutées.

Backend Django
--------------

Le backend est construit avec Django.

Ce choix est adapté au projet parce que l'application manipule beaucoup de
données relationnelles : utilisateurs, profils, stations, emplacements,
réservations, sessions, devices, capteurs et maintenances. Django fournit une
base robuste pour les modèles, les migrations, l'administration, la validation
des mots de passe, les permissions et les commandes de gestion.

Le compromis assumé est que Django impose une structure assez complète. Pour ce
prototype, ce cadre est un avantage : il évite de réinventer l'authentification,
les migrations et les conventions d'administration.

API REST avec Django REST Framework
-----------------------------------

L'API métier est exposée avec Django REST Framework.

DRF est cohérent avec Django et apporte des serializers, des permissions, des
vues API et une gestion standard des erreurs. Il permet au frontend Vite, au
kiosque Raspberry et aux futurs composants embarqués de consommer le même
contrat HTTP.

Ce choix est plus simple à maintenir qu'une API ad hoc écrite directement avec
des vues Django classiques. Il prépare aussi mieux la documentation OpenAPI et
les tests d'API.

Base PostgreSQL
---------------

La base de données de développement principale est PostgreSQL.

Le projet porte des contraintes relationnelles importantes : unicité des
comptes, rattachement des emplacements aux stations, réservations par fenêtre de
temps, sessions de charge et historiques. PostgreSQL est plus proche d'un
environnement de production qu'une base fichier et gère bien les index, les
contraintes et les données structurées.

SQLite reste utilisé pour les tests unitaires via ``config.test_settings``. Ce
choix rend les tests plus rapides et plus faciles à lancer localement, tout en
gardant PostgreSQL pour la stack applicative normale.

Modèle utilisateur personnalisé
-------------------------------

Le projet utilise un modèle ``Utilisateur`` personnalisé avec un identifiant UUID
et une connexion par pseudo.

Ce choix correspond au domaine fonctionnel : l'utilisateur se connecte avec un
pseudo ou une adresse e-mail, et les objets métier référencent des identifiants
stables qui ne révèlent pas un ordre de création. Le profil personnel est placé
dans ``ProfilUtilisateur`` afin de séparer le compte d'authentification des
données de profil.

La limite est qu'un modèle utilisateur personnalisé doit être conservé avec
discipline dans les migrations et les formulaires d'administration. Il vaut
mieux l'assumer tôt, comme ici, que migrer plus tard depuis le modèle Django
standard.

Authentification JWT
--------------------

L'API utilise ``djangorestframework-simplejwt``.

Les jetons JWT conviennent à une API consommée par un frontend séparé et par un
kiosque. Le backend n'a pas besoin de maintenir une session serveur classique
pour chaque client, et le frontend peut renouveler un jeton d'accès à partir
d'un jeton de rafraîchissement.

La limite principale est la gestion côté navigateur : les jetons doivent être
protégés avec soin. Dans ce prototype, la solution reste pragmatique. Pour un
déploiement plus exposé, il faudra réexaminer le stockage des jetons, leur durée
de vie, la rotation et les politiques de déconnexion.

CORS explicite
--------------

Le backend utilise ``django-cors-headers`` avec une liste d'origines locales.

Ce choix permet de développer le frontend Vite sur ``5173``, le backend Django
sur ``8000`` et le kiosque sur ``9000`` sans ouvrir l'API à toutes les origines.
La configuration reste lisible dans ``.env`` et peut être durcie hors
développement.

Frontend Vite multi-pages
-------------------------

Le frontend est une application Vite multi-pages.

Vite remplace le simple service Nginx de développement par un vrai outil
frontend : serveur rapide, modules JavaScript natifs, rechargement à chaud et
build de production avec assets optimisés et hashés. La structure multi-pages
conserve le fonctionnement actuel de l'application : chaque écran reste une page
HTML claire, avec un script d'entrée dédié.

Ce choix améliore la maintenabilité et prépare une future industrialisation du
frontend. Il n'optimise pas directement les requêtes backend : les gains de
performance API viendront plutôt des index, de la pagination, du cache ciblé et
de l'optimisation des serializers.

Carte de réservation
--------------------

La page de réservation utilise Leaflet pour afficher les stations.

Leaflet est léger, largement utilisé et suffisant pour un besoin de carte simple
: afficher les stations disponibles, aider l'utilisateur à choisir un lieu et
garder l'interface compréhensible. Le projet évite ainsi d'introduire un service
SIG complexe avant d'en avoir besoin.

Pour un déploiement de production, il faudra valider les conditions
d'utilisation des tuiles cartographiques et éventuellement héberger ou
contractualiser un fournisseur de tuiles.

Allocation des emplacements par le backend
------------------------------------------

L'utilisateur choisit une station et un créneau, mais pas directement
l'emplacement.

Le backend attribue automatiquement un emplacement libre sur la fenêtre de
réservation. Ce choix garde la règle de disponibilité au même endroit que les
données, ce qui réduit les incohérences entre utilisateurs et évite que deux
clients prennent une décision concurrente côté navigateur.

Le compromis est que l'utilisateur a moins de contrôle fin. Pour le prototype,
la simplicité et la cohérence métier sont plus importantes.

Fenêtre de réservation de 30 minutes
------------------------------------

La durée de réservation est fixée à 30 minutes.

Cette règle simplifie le calcul de disponibilité, l'expiration des accès
temporaires et l'expérience utilisateur. Elle donne aussi une base claire pour
les tests automatisés.

Si le projet évolue vers des durées configurables, la règle devra passer dans
une configuration métier ou dans un modèle de tarification.

Modes d'accès RFID, QR code et code temporaire
----------------------------------------------

Le projet prévoit plusieurs modes d'authentification d'accès.

Le RFID correspond au cas physique naturel pour une station. Le QR code et le
code temporaire servent de solutions simples pour les utilisateurs sans badge ou
pour une démonstration. Cette combinaison permet de tester le parcours complet
avant que tout le matériel soit disponible.

Les secrets ne doivent pas être stockés en clair. Le modèle
``Authentification`` porte donc une valeur hachée, des métadonnées, une
expiration et un état actif.

Kiosque Raspberry séparé
------------------------

Le dossier ``raspberry/app/`` contient une interface de kiosque indépendante.

Ce choix isole l'interface locale de la station du frontend utilisateur. Le
kiosque peut simuler un terminal physique, appeler l'API et évoluer vers un
déploiement embarqué sans coupler son cycle de vie au dashboard web.

Le serveur actuel est volontairement minimal. Il est suffisant pour un
prototype, mais un déploiement réel devra traiter le démarrage automatique, la
supervision, le mode hors ligne et la sécurité réseau locale.

ESP32 et modèles devices
------------------------

Les ESP32 sont représentés dans le backend par les modèles ``Device``,
``Capteur`` et ``CapteurData``.

Ce choix garde une trace explicite du lien entre un emplacement physique, son
contrôleur embarqué et ses mesures. Il prépare la supervision technique :
version de firmware, dernière présence, statut, capteurs et alertes.

Le code embarqué reste un prototype. La priorité actuelle est de stabiliser le
contrat métier et les données attendues par le backend.

Docker Compose
--------------

La stack locale est orchestrée avec Docker Compose.

Compose permet de lancer PostgreSQL, Django, Vite et le kiosque avec une
commande unique. Cela réduit les écarts entre machines de développement et
facilite la reprise du projet après un clone Git.

Ce choix ne remplace pas une architecture de production. Pour un déploiement
public, il faudra ajouter un reverse proxy, une stratégie TLS, des volumes et
sauvegardes contrôlés, et une façon propre de servir le build Vite.

Commandes de bootstrap
----------------------

Le backend initialise les données de démonstration au démarrage Docker.

Ce choix rend le prototype immédiatement testable : compte administrateur,
technicien, station, emplacements, devices et maintenance de démo sont prêts
sans manipulation manuelle. Il améliore aussi la reproductibilité des tests
fonctionnels.

En production, ces commandes devront être remplacées ou encadrées par une
procédure d'installation explicite.

Documentation OpenAPI
---------------------

Le projet utilise ``drf-spectacular`` pour produire le schéma OpenAPI et les vues
Swagger UI / Redoc.

Ce choix documente le contrat API directement à partir du code DRF. Il réduit le
risque de documentation obsolète et facilite les tests manuels par les
développeurs.

La documentation OpenAPI doit tout de même être enrichie progressivement avec
des descriptions explicites quand les endpoints deviennent ambigus.

Documentation Sphinx
--------------------

La documentation technique est construite avec Sphinx.

Sphinx permet de combiner des pages narratives, comme cette page, avec une
référence backend générée par autodoc. Le style Google des docstrings est repris
par ``sphinx.ext.napoleon``, ce qui évite de maintenir deux formats
documentaires différents.

Ce choix demande une discipline : les pages narratives doivent être mises à jour
quand les choix produit ou architecture changent.

Tests pytest
------------

Les tests backend sont écrits avec pytest et pytest-django.

Pytest donne une syntaxe concise pour tester les serializers,
l'authentification, les réservations, l'administration et le terminal. Le build
Docker backend lance les tests, ce qui empêche de construire une image
applicative quand la suite échoue.

La base de test SQLite rend la suite rapide. Les comportements spécifiques à
PostgreSQL devront être couverts s'ils deviennent critiques.

Qualité documentaire avec Ruff et Interrogate
---------------------------------------------

Le projet configure Ruff et Interrogate pour suivre les docstrings backend.

Ce choix rend la documentation du code vérifiable. Ruff contrôle le style des
docstrings existantes, tandis qu'Interrogate mesure les docstrings manquantes.
Le seuil élevé force les nouvelles fonctions publiques à être expliquées.

La limite est que la présence d'une docstring ne garantit pas sa qualité. Les
revues de code restent nécessaires.

Dépendances verrouillées
------------------------

Les dépendances Python installées par Docker sont verrouillées dans des fichiers
``requirements.txt``. Le frontend dispose d'un ``package-lock.json``.

Ce choix améliore la reproductibilité : une nouvelle installation récupère les
mêmes versions que celles testées. Les fichiers ``.in`` restent la source
lisible pour les dépendances Python directes.

Quand une dépendance est mise à jour, il faut reconstruire l'environnement et
relancer les tests.

Pagination API
--------------

Les endpoints de liste acceptent progressivement ``page`` et ``page_size``.

Ce choix permet d'éviter de charger des volumes trop importants quand les données
grandissent, tout en gardant la forme historique ``results`` pour les écrans qui
ne demandent pas encore explicitement une page. Les paramètres
``API_DEFAULT_PAGE_SIZE`` et ``API_MAX_PAGE_SIZE`` encadrent la taille des pages.

La pagination reste volontairement progressive : les écrans existants peuvent
continuer à fonctionner sans changement, et les interfaces pourront ajouter des
contrôles de pagination là où le volume le justifie.

Cache Redis ciblé
-----------------

Le projet configure le cache Django avec Redis quand ``CACHE_URL`` est défini,
et bascule sur un cache local en mémoire quand Redis n'est pas disponible.

Ce choix garde le développement local simple tout en préparant un cache partagé
dans Docker. Le premier usage ciblé est le catalogue des stations, car il est lu
souvent par le frontend et change moins fréquemment que les réservations ou les
données de profil.

Le cache est invalidé lors des modifications de stations ou d'emplacements. Les
réservations et les accès temporaires restent hors cache, car ils sont dynamiques
et sensibles à l'utilisateur connecté.

Headers cache des assets Vite
-----------------------------

Le frontend fournit une configuration Nginx de production pour servir le build
Vite.

Les fichiers hashés sous ``/assets/`` reçoivent un header
``Cache-Control: public, max-age=31536000, immutable``. Les pages HTML restent en
``no-cache`` afin que le navigateur récupère rapidement les nouveaux liens vers
les assets après un déploiement.

Ce choix optimise les assets sans risquer de servir une ancienne page HTML qui
pointe vers des fichiers retirés du build.

SBOM et analyse de vulnérabilités
---------------------------------

Le projet fournit des scripts pour générer un SBOM avec Syft et analyser les
vulnérabilités avec Grype.

Ce choix donne de la visibilité sur la chaîne d'approvisionnement logicielle :
dépendances installées, image backend, rapports JSON/SARIF et brouillon OpenVEX.
Il est utile pour expliquer ce qui est présent dans l'application et suivre les
vulnérabilités.

Les rapports ne remplacent pas une analyse humaine. Une entrée VEX ne doit être
validée qu'après avoir vérifié si le chemin vulnérable est réellement
atteignable.

Cache HTTP et Varnish
---------------------

Le projet n'intègre pas encore Varnish Cache.

La majorité des endpoints actuels restent dynamiques et authentifiés par JWT :
profil, réservations, administration, maintenances et accès temporaires. Les
mettre en cache au niveau reverse proxy serait risqué sans politique fine sur les
en-têtes ``Authorization``, ``Cookie`` et ``Set-Cookie``.

La priorité actuelle est donc l'optimisation interne Django/DRF : requêtes,
index, pagination, cache Redis ciblé et headers cache pour les assets buildés.
Varnish Cache pourra devenir pertinent pour des pages publiques ou endpoints
anonymes stables.

Varnish Orca n'est pas retenu pour l'accélération applicative : son rôle est
plutôt de mettre en cache des registres et artifacts de build, comme Docker, npm
ou Python packages. Il pourrait être étudié plus tard pour accélérer la CI, mais
pas pour servir les réponses de l'API.
