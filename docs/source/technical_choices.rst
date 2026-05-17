Choix techniques
================

Cette page explique les principaux choix du projet. L'objectif est de garder une
trace des raisons, des bénéfices, des limites assumées et des alternatives
écartées quand elles ont été discutées.

Pour une lecture orientée fonctionnalité par fonctionnalité, voir aussi
``implementation_guide.rst``. Pour le détail du schéma relationnel et de son
adaptation dans Django, voir ``data_model.rst``.

Backend Django
--------------

Le backend est construit avec Django.

Ce choix est adapté au projet parce que l'application manipule beaucoup de
données relationnelles : utilisateurs, profils, stations, bornes, emplacements,
réservations, sessions, devices, capteurs et maintenances. Django fournit une
base robuste pour les modèles, les migrations, l'administration, la validation
des mots de passe, les permissions et les commandes de gestion.

Le compromis assumé est que Django impose une structure assez complète. Pour ce
la version actuelle, ce cadre est un avantage : il évite de réinventer l'authentification,
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
comptes, rattachement des bornes aux stations, rattachement des emplacements aux
bornes, réservations par fenêtre de temps, sessions de charge et historiques.
PostgreSQL est plus proche d'un
environnement de production qu'une base fichier et gère bien les index, les
contraintes et les données structurées.

SQLite reste utilisé pour les tests unitaires via ``config.test_settings``. Ce
choix rend les tests plus rapides et plus faciles à lancer localement, tout en
gardant PostgreSQL pour la stack applicative normale.

TimescaleDB pour la télémétrie
------------------------------

La stack Docker utilise l'image TimescaleDB compatible PostgreSQL.

Ce choix garde le confort de PostgreSQL pour les modèles relationnels Django,
tout en préparant le stockage des séries temporelles issues des ESP32 :
température, courant, tension, énergie, câble, porte et état des emplacements.
L'application peut continuer à utiliser l'ORM Django, et Grafana peut lire les
tables horodatées sans couche supplémentaire.

Une migration active l'extension ``timescaledb`` lorsque le serveur PostgreSQL la
propose. Les tables restent toutefois des modèles Django standards. Le passage en
hypertables est gardé pour une étape dédiée, car les tables de télémétrie
utilisent aujourd'hui des clés primaires UUID simples ; TimescaleDB exige que les
contraintes uniques incluent la colonne temporelle de partitionnement.

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
pour chaque client.

La session navigateur suit une approche plus défensive que le stockage complet
en ``localStorage`` : le jeton d'accès reste uniquement en mémoire JavaScript et
le jeton de rafraîchissement est porté par un cookie ``HttpOnly``. Le frontend
ne peut donc plus lire le refresh token directement; il appelle
``/api/token/refresh/`` avec les cookies inclus pour obtenir un nouveau jeton
d'accès. ``/api/logout/`` efface ce cookie.

Cette solution réduit l'impact d'une XSS qui lirait le stockage local. Elle ne
remplace pas une politique anti-XSS complète : les rendus frontend évitent les
insertions HTML pour les champs issus de l'API, et les rares usages restants de
``innerHTML`` sont réservés au nettoyage de conteneurs ou au SVG QR généré côté
serveur.

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

PWA plutôt qu'application mobile native
---------------------------------------

Le projet retient une web app responsive et installable en PWA plutôt qu'une
application mobile native. Ce choix évite de maintenir deux clients séparés tout
en couvrant le besoin mobile : consulter ses réservations, afficher le QR,
déclencher l'envoi du code SMS et gérer le badge RFID depuis le profil.

Le frontend fournit donc un manifeste ``manifest.webmanifest``, une icône
installable et un service worker léger. Le cache PWA reste volontairement
limité à l'enveloppe applicative et aux assets statiques : les données métier,
les réservations et les secrets d'accès continuent de venir de l'API afin de ne
pas figer des droits sensibles côté navigateur.

Cette base porte aussi le parcours "téléphone -> borne". La borne affiche un QR
de session mobile, l'utilisateur ouvre la PWA, se connecte si nécessaire,
choisit une réservation compatible, puis le backend autorise la borne. Ce QR de
session mobile ne remplace pas le QR de réservation : il sert uniquement à lier
temporairement le téléphone à la borne devant laquelle se trouve l'utilisateur.

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

Infrastructure station, borne et emplacement
--------------------------------------------

Le modèle terrain suit une hiérarchie explicite : une station représente un lieu,
une borne représente l'équipement physique installé sur ce lieu, et un
emplacement représente le point de charge réservé et piloté.

Ce découpage évite de confondre la station publique avec le matériel local. Il
prépare aussi la supervision et MQTT : une station peut contenir plusieurs
bornes, et chaque borne peut piloter plusieurs emplacements.

Le champ station reste maintenu sur ``Emplacement`` pour les filtres rapides et
la compatibilité avec les flux existants. Il est aligné automatiquement depuis la
borne par le modèle backend.

Allocation des emplacements par le backend
------------------------------------------

L'utilisateur choisit une station, un début de réservation et une durée de
recharge, mais pas directement l'emplacement.

Le backend attribue automatiquement un emplacement libre sur la fenêtre de
réservation. Ce choix garde la règle de disponibilité au même endroit que les
données, ce qui réduit les incohérences entre utilisateurs et évite que deux
clients prennent une décision concurrente côté navigateur.

Le compromis est que l'utilisateur a moins de contrôle fin. Pour la version actuelle,
la simplicité et la cohérence métier sont plus importantes.

Durées de réservation
---------------------

La durée minimale est de 30 minutes et la durée par défaut est de 1 heure. Les
durées proposées sont 30 minutes, 1 heure, 2 heures et 4 heures.

Cette règle garde un calcul de disponibilité simple tout en restant réaliste
pour une recharge de vélo électrique. Les accès temporaires restent valables sur
la fenêtre réellement réservée.

La borne applique aussi une tolérance d'accès : l'utilisateur peut démarrer un
peu avant le début du créneau et conserve une courte marge après la fin. Les
valeurs par défaut sont 5 minutes avant le début et 10 minutes après la fin.
Elles sont exposées par le cache offline pour que le Raspberry applique les
mêmes règles en mode dégradé.

Ces marges ne font pas partie du calcul de disponibilité. Une réservation
affichée 14h00-15h00 bloque l'emplacement sur cette fenêtre payée uniquement :
un autre utilisateur peut donc réserver 13h00-14h00 ou 15h00-16h00 sur le même
emplacement. La tolérance sert seulement au contrôle d'accès à la borne, sans
créer un trou invisible dans le planning. Si le créneau précédent est encore en
cours ou si une session de charge est active sur l'emplacement, la borne refuse
l'ouverture anticipée.

Si le projet évolue vers une tarification, ces durées pourront être déplacées
dans une configuration métier ou dans un modèle de prix.

Modes d'accès RFID, QR code et code SMS temporaire
--------------------------------------------------

Le projet prévoit plusieurs modes d'authentification d'accès.

Le RFID correspond au cas physique naturel pour une station. Le QR code et le
code SMS temporaire servent de solutions simples pour les utilisateurs sans
badge ou pour un parcours sans badge physique. Cette combinaison permet de tester
le parcours complet avant que tout le matériel soit disponible.

Les secrets ne doivent pas être stockés en clair. Le modèle
``Authentification`` porte donc une valeur hachée, des métadonnées, une
expiration et un état actif.

Le badge RFID est traité comme un moyen d'accès persistant. L'utilisateur peut
l'enregistrer depuis son profil, et l'administrateur peut l'associer, le
remplacer ou le révoquer depuis l'écran de modification de l'utilisateur. Côté
administration, la valeur affichée est toujours masquée afin de ne pas exposer
le secret physique du badge.

Le QR code et le code SMS temporaire sont volontairement rattachés à une
réservation, pas au profil utilisateur. Ils peuvent donc être régénérés ou
révoqués depuis l'administration des réservations. L'utilisateur peut afficher
ou masquer le QR courant sans provoquer de rotation. La valeur temporaire est
dérivée côté serveur à partir d'un nonce et de ``SECRET_KEY`` : le secret clair
n'est pas stocké, mais le même accès peut être reconstruit tant qu'il est actif.

Le QR est le support applicatif immédiat : il est généré dès la réservation et
consultable dans le dashboard. Le code SMS répond au cas sans application au
moment de la charge : le secret est créé dès la réservation pour pouvoir être
synchronisé côté station, mais il n'est envoyé à l'utilisateur que peu avant le
créneau ou lorsqu'il clique sur ``Recevoir le code SMS``.

Le transport SMS est isolé derrière un service backend. En local, le fournisseur
``console`` évite tout coût et tout envoi réel. En production, le fournisseur
doit être choisi explicitement parmi ``twilio`` ou ``brevo`` avec ses
identifiants dédiés. ``ovh`` n'est pas activé dans le profil durci, car la
signature REST OVH repose sur SHA-1. Le mode production recommande aussi
``SMS_REQUIRE_VERIFIED_PHONE=True`` et un délai de renvoi afin de limiter les
erreurs de numéro, les abus et les boucles de clic sur l'interface mobile.

Pour les emails, le projet retient Mailpit en environnement académique. Django
envoie via SMTP vers le service ``mailpit`` du ``docker-compose`` et les messages
sont consultables dans l'interface web locale. Ce choix reste gratuit, open
source et démontrable sans fournisseur externe. Les emails servent d'abord aux
notifications technicien sur nouvelle alerte ; les parcours de vérification de
compte ou de réinitialisation de mot de passe pourront réutiliser la même
configuration.

La régénération par l'administration remplace la valeur active et ne présente
plus le QR/code SMS dans une modale de copie. Cette décision évite de transformer
l'admin en canal de transmission du secret : si l'utilisateur affiche déjà son
accès, l'interface rafraîchit la valeur courante automatiquement.

La révocation est douce : l'enregistrement reste en base avec
``is_active=False`` et une expiration ramenée à l'instant courant. Le terminal
refuse explicitement tout moyen d'accès révoqué, ce qui conserve une trace tout
en empêchant la réutilisation.

Les actions sensibles d'administration, comme la réinitialisation du mot de
passe, l'association ou la révocation RFID et la régénération ou révocation
QR/code SMS, alimentent ``JournalSecurite``.

Kiosque Raspberry séparé
------------------------

Le dossier ``raspberry/app/`` contient une interface de kiosque indépendante.

Ce choix isole l'interface locale de la station du frontend utilisateur. Le
kiosque peut simuler un terminal physique, appeler l'API et évoluer vers un
déploiement embarqué sans coupler son cycle de vie au dashboard web.

Le serveur actuel est volontairement minimal. Il est suffisant pour la version
actuelle, mais un déploiement réel devra traiter le démarrage automatique, la
supervision, le mode hors ligne et la sécurité réseau locale.

Continuité locale et mode dégradé
---------------------------------

Le choix d'architecture retient le backend comme source de vérité et non une
communication directe Raspberry -> ESP32 comme chemin principal.

Ce choix répond à trois enjeux du cahier des charges :

* **sécurité** : l'API centralise la validation des réservations, des moyens
  d'accès, des expirations et des révocations ;
* **audit** : les décisions sensibles sont journalisées côté serveur et restent
  corrélées aux utilisateurs, réservations et sessions ;
* **performance d'exploitation** : le backend et Celery absorbent les écritures,
  la supervision et les agrégations, tandis que le Raspberry reste concentré sur
  l'interaction locale avec l'usager.

Le Raspberry conserve toutefois un rôle de continuité. En cas de perte du
serveur, il peut utiliser un cache local d'autorisations déjà obtenues auprès du
backend. Ce cache doit être court, borné à la station, invalidable et limité aux
actions nécessaires au service. Il ne doit pas permettre de créer une nouvelle
réservation ni d'accorder un accès inconnu du système central.

Les ESP32 doivent aussi conserver une autonomie de sécurité : arrêt de charge en
cas d'ouverture du boîtier, retrait du câble, surchauffe ou surconsommation.
Pour éviter la perte de traces pendant une coupure, les événements et mesures
non transmis peuvent être stockés localement dans LittleFS, puis resynchronisés
quand la messagerie redevient disponible.

La communication Raspberry -> ESP32 est donc justifiée en mode dégradé ou pour
relayer une commande déjà validée. Elle n'est pas le mode nominal, car elle
court-circuiterait la source de vérité, compliquerait les révocations et
multiplierait les règles de sécurité à maintenir.

Parcours tactile du kiosque Raspberry
-------------------------------------

L'interface Raspberry cible un écran tactile Waveshare en résolution
``1024x600``. Le kiosque doit donc être pensé comme une interface embarquée :
peu d'informations simultanées, boutons larges, états visibles à distance et
enchaînement clair des écrans.

Le parcours est découpé en écrans courts plutôt qu'en formulaire unique :

* un accueil centré sur l'action immédiate : badge RFID, téléphone, QR de
  réservation, code SMS temporaire et aide ;
* un écran RFID direct, sans code préalable, car le badge est le geste naturel
  sur une borne ;
* un écran téléphone qui génère un QR de session mobile temporaire ;
* un écran QR de réservation utilisé seulement si la borne dispose d'un lecteur
  QR physique ;
* un écran code SMS qui demande le code de réservation puis le code reçu par SMS ;
* un écran d'association badge qui consomme un code court créé depuis le profil
  web ;
* un écran de résultat plein écran, vert ou rouge, qui confirme l'emplacement ou
  explique le refus.

Le bouton ``Démarrer la charge`` n'est jamais affiché avant validation de
l'authentification. Le kiosque ne propose le démarrage qu'après une réponse
positive du backend, ou du cache local en mode dégradé, puis relaie seulement à
ce moment-là la commande ``START`` à l'ESP32.

Le clavier tactile remplace le clavier matriciel si celui-ci n'est pas installé.
Il sert uniquement aux codes courts : code de réservation, code SMS ou code
d'association RFID. Les secrets restent générés dans un alphabet compatible avec
la saisie tactile et les contraintes matérielles de la borne.

ESP32 et modèles devices
------------------------

Les ESP32 sont représentés dans le backend par les modèles ``Device``,
``Capteur`` et ``CapteurData``.

Ce choix garde une trace explicite du lien entre un emplacement physique, son
contrôleur embarqué et ses mesures. Il prépare la supervision technique :
version de firmware, dernière présence, statut, capteurs et alertes.

Le code embarqué reste une base d'intégration. La priorité actuelle est de stabiliser le
contrat métier et les données attendues par le backend.

Docker Compose
--------------

La stack locale est orchestrée avec Docker Compose.

Compose permet de lancer PostgreSQL, Django, Vite et le kiosque avec une
commande unique. Cela réduit les écarts entre machines de développement et
facilite la reprise du projet après un clone Git.

Ce choix ne remplace pas à lui seul une architecture de production complète. Le
reverse proxy Nginx local prépare déjà un point d'entrée unique, mais il faudra
encore ajouter TLS, sauvegardes, supervision système et gestion stricte des
secrets pour un déploiement public.

Commandes de bootstrap
----------------------

Le backend initialise les données locales au démarrage Docker.

Ce choix rend la solution immédiatement testable : compte administrateur,
technicien, station, borne, emplacements, devices et maintenance de référence sont prêts
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

Le cache est invalidé lors des modifications de stations, bornes ou emplacements. Les
réservations et les accès temporaires restent hors cache, car ils sont dynamiques
et sensibles à l'utilisateur connecté.

Messagerie IoT avec Mosquitto
-----------------------------

MQTT est utilisé comme protocole de messagerie pour la télémétrie IoT et les
commandes vers les ESP32. Ce choix est cohérent avec le cahier des charges :
les équipements embarqués disposent de ressources limitées, publient de petits
messages fréquents et doivent continuer à fonctionner même lorsque le réseau est
moins stable qu'un réseau serveur classique.

Le broker Mosquitto est léger, open source et adapté à une architecture de
station locale. Les ESP32 publient leurs mesures sur
``station/<slot_id>/telemetry`` et reçoivent les commandes sur
``station/<slot_id>/cmd``. Cette séparation permet de découpler l'embarqué du
backend : l'ESP32 reste un exécutant local, tandis que Django et le Raspberry
gardent les décisions métier.

MQTT apporte plusieurs avantages par rapport à des appels HTTP directs entre
chaque composant :

* **découplage** : les ESP32 publient un événement sans connaître les détails de
  l'API Django ;
* **sobriété réseau** : les messages sont compacts et adaptés à des échanges
  fréquents de capteurs ;
* **communication bidirectionnelle** : le même broker transporte les mesures
  montantes et les commandes descendantes ;
* **résilience locale** : le Raspberry et le broker local peuvent maintenir une
  continuité opérationnelle même si le backend central est temporairement
  indisponible ;
* **observabilité** : les topics ``station/#`` facilitent le diagnostic avec
  ``mosquitto_sub`` et la simulation locale.

Le développement local accepte MQTT sans authentification pour faciliter la
simulation. En production, le broker devra être protégé par identifiants, TLS et
segmentation réseau.

Celery pour l'ingestion asynchrone
----------------------------------

Le bridge d'ingestion backend délègue le traitement des messages à Celery.

Ce choix évite de bloquer le consommateur de messages pendant l'écriture en base ou la
création d'alertes. Redis sert de broker Celery, ce qui reste cohérent avec le
cache Django et le canal temps réel de Django Channels.

L'ingestion est idempotente pour les anomalies ouvertes : une même anomalie sur
un même emplacement met à jour l'alerte existante au lieu d'empiler des doublons.
La télémétrie normale résout automatiquement les alertes connues, ce qui garde
la supervision exploitable pendant une simulation continue.

Pour trois ESP32, le volume reste faible, mais cette architecture donne déjà une
base robuste pour filtrer, agréger ou notifier sans modifier le firmware.

Django Channels pour l'administration temps réel
------------------------------------------------

Django Channels est utilisé pour pousser les mises à jour de supervision vers
l'interface administrateur. Le backend expose ``/ws/admin/supervision/`` en ASGI,
protégé par le jeton JWT d'accès et limité aux comptes administrateurs.

À chaque message MQTT ingéré, le backend publie une notification dans le groupe
Channels ``admin_supervision``. Les navigateurs connectés récupèrent alors une
nouvelle photographie de supervision sans attendre le polling HTTP. Le polling
reste activé en secours, ce qui évite de bloquer l'interface si le WebSocket est
filtré, si le jeton expire ou si un environnement de développement ne route pas
encore ``/ws/``.

Grafana pour la supervision technique
-------------------------------------

Grafana est utilisé pour les courbes et tableaux techniques.

Le tableau de bord métier de l'application reste destiné aux administrateurs et
techniciens : réservations, utilisateurs, maintenances et alertes lisibles.
Grafana complète cette vue avec des séries temporelles : température, courant,
état des ESP32 et incidents récents.

Ce choix évite de recréer un outil de graphes temps réel de zéro et s'appuie sur
une solution open source connue. Dans la version actuelle, Grafana est accessible sur
``/grafana/`` via le reverse proxy local, avec un lien direct vers le dashboard
``/grafana/d/station-overview/station-vue-globale-supervision``. Ce dashboard
d'accueil porte les statistiques globales, les sessions en cours et les filtres
station/borne/emplacement ; il renvoie ensuite vers le dashboard technique
``/grafana/d/station-supervision/station-supervision-technique`` pour les séries
capteurs détaillées.

Reverse proxy Nginx
-------------------

Un reverse proxy Nginx local centralise les routes d'accès.

Il expose ``/`` pour le frontend, ``/api/`` et ``/admin/`` pour Django,
``/grafana/`` pour Grafana et ``/kiosk/`` pour le kiosque Raspberry. Les ports
directs restent disponibles en développement, mais Nginx prépare la mise en
production : un seul point d'entrée, terminaison TLS, ajout de headers de
sécurité et future protection de Grafana derrière l'authentification
admin/technicien.

La configuration locale active HTTPS par défaut avec un certificat auto-signé
pour ``localhost``. Ce certificat n'a pas vocation à être utilisé en production,
mais il permet de tester dès maintenant les comportements dépendants du contexte
sécurisé : cookies de session, redirection HTTP vers HTTPS, génération des liens
applicatifs et en-têtes ``X-Forwarded-Proto`` transmis aux services internes.

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
Il est utile pour maîtriser le contenu logiciel livré et suivre les
vulnérabilités.

CodeQL complète ce contrôle avec une analyse statique Python et JavaScript. Il
sert à détecter automatiquement des vulnérabilités de code ou des usages risqués
qui ne sont pas visibles dans un simple inventaire de dépendances.

Le projet conserve une configuration CodeQL avancée dans le dépôt plutôt que le
``Default setup`` GitHub. Ce choix garde les requêtes, la planification et les
permissions visibles en revue de code. Le ``Default setup`` doit rester
désactivé pour éviter un conflit de traitement des résultats SARIF.

Dependabot surveille les dépendances GitHub Actions, npm, pip et Docker. Les
mises à jour arrivent sous forme de pull requests, ce qui permet de les faire
passer par la même CI que les changements applicatifs.

La protection de ``main`` transforme ces automatisations en garde-fous
opérationnels : une mise à jour Dependabot ou applicative ne doit pas être
fusionnée tant que les tests, CodeQL, le build documentaire et le rapport SBOM ne
sont pas validés.

La documentation HTML n'est pas versionnée : ``docs/build/html`` reste un
artefact généré. GitHub Pages est alimenté par un workflow dédié qui reconstruit
Sphinx depuis les sources versionnées, ce qui évite les divergences entre la
documentation source et le HTML publié.

La publication est disponible sur
``https://bayhes5.github.io/Station_de_recharge/`` après merge dans ``main``.

Les rapports ne remplacent pas une analyse humaine. Une entrée VEX ne doit être
validée qu'après avoir vérifié si le chemin vulnérable est réellement
atteignable.

Après une modification des dépendances, de l'image backend ou des surfaces de
sécurité exposées, les artefacts ``sbom/`` et, si nécessaire, le brouillon
OpenVEX doivent être régénérés avec ``scripts/generate-sbom.ps1`` puis résumés
avec ``scripts/summarize-vulnerabilities.ps1``.

Limites assumées
----------------

Le périmètre actuel privilégie les composants réellement utilisés dans la
solution :
Django, Vite, PostgreSQL/TimescaleDB, Redis, Celery, Mosquitto, Grafana, Nginx,
Raspberry Pi et ESP32.

Les sujets suivants restent volontairement hors périmètre immédiat :

* paiement ou facturation réelle ;
* application mobile native ;
* déploiement multi-site ;
* haute disponibilité ;
* authentification unique avancée pour Grafana ;
* TLS MQTT et certificats X.509 en développement local ;
* remplacement complet des simulations par le câblage définitif.

Ce périmètre maintient une trajectoire de livraison réaliste, tout en préservant
une architecture extensible vers une exploitation de production.
