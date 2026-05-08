Modele de donnees
=================

Cette page explique le lien entre le MCD de reference et le modele Django
effectivement implemente dans le projet. Le MCD donne la vision fonctionnelle de
la base ; l'implementation Django l'adapte aux besoins concrets de
l'application, aux migrations ORM, a l'authentification Django et aux tests.

Positionnement du MCD
---------------------

Le MCD fourni est une bonne base de conception. Il decrit les grands domaines du
projet :

* utilisateurs, profils, roles et moyens d'authentification ;
* consentements et journal de securite ;
* stations, emplacements, devices ESP32 et capteurs ;
* reservations, sessions de charge et telemetrie ;
* alertes, techniciens et maintenances ;
* pistes RGPD et performance avec vues, anonymisation, TimescaleDB et index.

Il ne doit cependant pas etre applique tel quel comme script SQL dans le projet.
La source de verite de la base est le modele Django situe dans
``backend/api/models.py`` et ses migrations dans ``backend/api/migrations/``.
Le detail table par table, le script PostgreSQL de creation et le diagramme
Mermaid sont disponibles dans :doc:`database_mcd`.

Cette decision evite de maintenir deux schemas concurrents : un schema SQL
manuel et un schema genere par Django. Toute evolution structurelle doit passer
par une migration Django afin de rester versionnee, testable et reproductible
dans Docker, en CI et sur les postes de developpement.

Choix d'implementation
----------------------

UUID
~~~~

Le MCD prevoit ``CREATE EXTENSION "uuid-ossp"`` et des valeurs par defaut
``uuid_generate_v4()``. Dans le projet, les UUID sont generes cote Django avec
``uuid.uuid4`` sur les champs ``UUIDField``.

Ce choix garde l'application compatible avec l'ORM et les tests SQLite. Il rend
l'extension ``uuid-ossp`` non indispensable pour la version actuelle.

Utilisateur Django
~~~~~~~~~~~~~~~~~~

Le MCD decrit une table ``utilisateur`` autonome avec ``email``,
``password_hash``, ``statut``, ``created_at``, ``last_login`` et
``failed_attempts``.

Le projet utilise un modele ``Utilisateur`` personnalise qui herite de
``AbstractBaseUser`` et ``PermissionsMixin``. Cela ajoute les conventions Django
necessaires : mot de passe gere par Django, permissions, groupes, ``is_staff``,
``is_active`` et ``date_joined``.

Le pseudo est l'identifiant principal de connexion, et l'email reste unique.
Cette structure permet d'utiliser l'administration Django, les permissions DRF,
les jetons JWT et les tests d'authentification sans recreer toute la mecanique
de securite.

Profil utilisateur
~~~~~~~~~~~~~~~~~~

Le modele ``ProfilUtilisateur`` reprend bien l'idee du MCD : les donnees
personnelles comme le nom et le telephone sont separees du compte
d'authentification.

La relation est un ``OneToOneField`` vers ``Utilisateur`` avec suppression en
cascade. Si le compte est supprime, le profil associe disparait aussi.

Roles
~~~~~

Les tables ``role`` et ``utilisateur_role`` existent dans Django. Elles
permettent de conserver une representation metier simple des roles, en plus des
permissions Django natives.

La table de liaison garde la date d'affectation avec ``assigned_at`` et impose
l'unicite du couple utilisateur-role.

Authentification multi-moyens
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Le MCD prevoit ``auth_type`` et ``auth_method``. Le projet implemente ces
concepts avec ``TypeAuth`` et ``Authentification``.

``Authentification`` stocke le secret sous la colonne SQL ``secret_hash`` via le
champ Django ``hash_valeur``. Le modele ajoute aussi :

* ``display_value`` pour afficher une valeur masquee ou lisible quand c'est
  acceptable ;
* ``metadata`` pour stocker les informations necessaires aux QR codes, codes
  temporaires et associations RFID ;
* ``expiration`` et ``is_active`` pour gerer revocation et duree de validite.

Cette structure est plus adaptee au projet que le MCD minimal, car elle couvre
les QR codes, les codes temporaires et les badges RFID persistants.

RGPD et journalisation
~~~~~~~~~~~~~~~~~~~~~~

Les tables ``consentement`` et ``journal_securite`` sont implementees.

``JournalSecurite`` utilise ``ON DELETE SET NULL`` plutot qu'une cascade stricte
sur l'utilisateur. Ce choix permet de conserver une trace d'evenements sensibles
meme si le compte utilisateur est supprime ou anonymise.

Les mecanismes PostgreSQL avances du MCD, comme l'extension ``anon``, les
``SECURITY LABEL`` et les vues SQL d'export, ne sont pas encore actives. Le
projet gere pour l'instant l'export et la suppression cote API Django.

Stations et emplacements
~~~~~~~~~~~~~~~~~~~~~~~~

``Station`` et ``Emplacement`` correspondent directement au MCD.

Le modele Django ajoute ``latitude`` et ``longitude`` sur ``Station`` afin de
supporter la carte de reservation. ``Emplacement`` garde le numero, l'etat
metier et l'etat de cadenas.

Une contrainte d'unicite empeche deux emplacements d'une meme station de porter
le meme numero.

Devices ESP32
~~~~~~~~~~~~~

``Device`` correspond au MCD et represente le controleur embarque d'un
emplacement. La relation avec ``Emplacement`` est un ``OneToOneField`` : un
emplacement ne doit avoir qu'un device principal dans la version actuelle.

Le modele garde le type de device, la version de firmware, l'adresse IP,
l'adresse MAC, la derniere presence et le statut courant.

Capteurs et donnees capteurs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``Capteur`` et ``CapteurData`` reprennent le principe du MCD : un device porte
plusieurs capteurs, et chaque mesure horodatee est stockee dans ``capteur_data``.

Les valeurs booleennes issues de l'ESP32, comme ``door`` et ``cable``, sont
converties en ``1.0`` ou ``0.0`` pour rester compatibles avec ``valeur`` de type
flottant. L'API ajoute ensuite une valeur d'affichage lisible dans la supervision
administrateur.

Le MCD cible propose des hypertables TimescaleDB pour ``capteur_data``. Elles ne
sont pas encore activees : la table reste une table Django standard afin de
garder la solution simple et portable.

Reservations
~~~~~~~~~~~~

``Reservation`` relie un utilisateur, un emplacement, un moyen
d'authentification et une fenetre de temps.

Le projet ajoute ``reference_code`` et ``auth_choice`` afin de gerer le parcours
terminal : code de reservation, QR code, code temporaire ou RFID.

La relation vers ``Utilisateur`` est en ``SET_NULL`` et non en cascade. Ce choix
evite d'effacer tout l'historique technique d'une reservation si le compte est
supprime. La donnee personnelle peut disparaitre, tandis que l'evenement metier
reste exploitable.

Sessions de charge
~~~~~~~~~~~~~~~~~~

Le MCD prevoit une table ``session`` avec ``id_user``, ``date_debut``,
``date_fin``, ``consommation_kwh`` et ``etat_batterie``.

Le projet implemente ce concept dans la table SQL ``charging_session``. Le
modele Django s'appelle ``Session`` mais sa table n'est pas nommee ``session``,
ce qui evite aussi la confusion avec la notion de session applicative.

La session reelle est rattachee a une reservation et a un emplacement. Elle
stocke ``start_time`` et ``end_time``. L'utilisateur se retrouve via
``session.reservation.utilisateur``.

La consommation instantanee ou cumulee n'est pas stockee directement dans
``charging_session``. Elle est portee par ``session_telemetry`` avec
``energie_kwh``. Cette separation garde la session comme un objet metier et la
telemetrie comme une serie temporelle.

Telemetrie de session
~~~~~~~~~~~~~~~~~~~~~

``SessionTelemetry`` correspond au MCD : il stocke courant, tension, energie et
timestamp pour une session active.

La table est indexee par session et timestamp. Elle pourra devenir une
hypertable TimescaleDB si la frequence de mesures augmente fortement.

Alertes
~~~~~~~

``Alerte`` correspond au MCD mais adapte les suppressions : les liens vers
``CapteurData`` et ``Session`` sont en ``SET_NULL``. Cela permet de garder une
alerte historique meme si la mesure ou la session associee n'est plus disponible.

Le champ ``timestamp`` est stocke dans la colonne SQL ``date`` pour rester proche
du MCD tout en gardant un nom Django plus explicite.

Le cycle actuel est gere cote application :

* ``nouvelle`` a la creation ;
* ``active`` si la meme anomalie continue ;
* ``resolue`` quand la telemetrie revient a la normale.

Maintenance
~~~~~~~~~~~

``Technicien`` et ``Maintenance`` reprennent le MCD. Le projet ajoute la
possibilite de lier un technicien a un compte ``Utilisateur``. Cela permet a un
technicien de se connecter et de consulter ses interventions.

Performance et TimescaleDB
--------------------------

Le conteneur ``db`` utilise l'image ``timescale/timescaledb:latest-pg15``. Cela
prevoit l'evolution vers les series temporelles sans modifier le moteur de base.

Dans l'etat actuel, le projet utilise TimescaleDB comme un PostgreSQL compatible.
Les tables ``capteur_data`` et ``session_telemetry`` ne sont pas encore des
hypertables.

Les index deja presents couvrent les requetes les plus importantes :

* emplacements par station et statut operationnel ;
* reservations par utilisateur, statut, emplacement et dates ;
* sessions par emplacement et dates ;
* devices par derniere activite ;
* telemetrie par session et timestamp ;
* donnees capteurs par capteur et timestamp ;
* alertes par statut, session et timestamp ;
* maintenances par technicien, station, statut et date planifiee.

Une migration complementaire ajoute aussi des index orientes exploitation :

* ``capteur(type, id_device)`` pour retrouver rapidement les series par type de
  capteur et par device ;
* ``capteur_data(timestamp DESC)`` pour les dernieres mesures et les fenetres
  temporelles Grafana ;
* ``session_telemetry(timestamp DESC)`` pour les analyses temporelles de session ;
* ``alerte(date DESC)`` pour les alertes recentes affichees en supervision.

Une seconde migration complete cette logique avec des index metier plus proches
des ecrans d'exploitation et des filtres API :

* ``emplacement(statut_cadenas, etat)`` pour identifier rapidement les points de
  charge selon l'etat du cadenas et l'etat operationnel ;
* ``reservation(date_debut, date_fin)`` pour les recherches de disponibilite sur
  une fenetre de temps ;
* ``charging_session(start_time, end_time)`` pour les sessions ouvertes, fermees
  ou analysees par periode ;
* ``device(status, last_seen)`` pour detecter les equipements indisponibles ou
  silencieux ;
* ``alerte(niveau_severite, date)`` pour prioriser les incidents ;
* ``alerte(type, date)`` pour suivre les familles d'anomalies dans le temps.

Ces index ne changent pas le modele fonctionnel. Ils rendent les parcours
critiques plus previsibles lorsque le volume augmente : supervision temps reel,
historique d'exploitation, diagnostic terrain et tableaux de bord.

Les optimisations du MCD cible, comme ``create_hypertable``, compression,
retention et vues materialisees, sont pertinentes pour une phase production ou
une simulation a volume eleve.

Securite base de donnees
------------------------

Le MCD propose Row Level Security sur ``session`` et ``reservation``.

Dans le projet actuel, l'isolation est portee par l'API Django : les endpoints
utilisateur filtrent toujours avec ``request.user`` et les endpoints
administrateur exigent les droits staff.

Activer la RLS dans PostgreSQL serait possible, mais il faut alors garantir que
``app.current_user_id`` est defini et nettoye correctement pour chaque requete.
Comme Django reutilise ses connexions, une mauvaise gestion de ce contexte peut
creer des erreurs difficiles a diagnostiquer. La RLS est donc consideree comme
une evolution de durcissement, pas comme un prerequis de la version actuelle.

RGPD cible
----------

Le MCD propose plusieurs mecanismes SQL :

* vue ``session_anonyme`` ;
* vue ``export_user_data`` ;
* fonction ``delete_user_rgpd`` ;
* extension ``anon`` et masquage dynamique ;
* hachage de l'identifiant utilisateur dans les exports statistiques.

Le projet implemente deja une partie de ce besoin cote API :

* profil separe du compte ;
* export de compte via endpoint authentifie ;
* suppression depuis le profil ;
* journalisation des actions sensibles ;
* conservation possible d'evenements techniques sans lien personnel direct.

Les vues SQL et l'anonymisation PostgreSQL pourront etre ajoutees plus tard si le
projet doit fournir des exports directs depuis la base ou une separation stricte
entre roles SQL.

Vue ``session_anonyme``
------------------------

La premiere vue SQL ajoutee cote PostgreSQL est ``session_anonyme``. Elle expose
un jeu de donnees dedie aux statistiques de sessions sans publier directement
l'identifiant utilisateur.

La vue s'appuie sur les tables reelles de l'application :

* ``charging_session`` pour les dates de debut et de fin ;
* ``reservation`` pour retrouver l'utilisateur lie a la session ;
* ``session_telemetry`` pour calculer la consommation observee.

Le champ ``user_hash`` est produit avec ``md5(id_user::text)`` lorsque la session
est encore rattachee a un utilisateur. Si le lien utilisateur a disparu, la vue
utilise l'identifiant de session comme valeur de repli afin de conserver une
ligne statistique sans recreer de donnee personnelle.

Cette vue ne remplace pas les controles d'acces applicatifs. Elle sert de base a
des rapports d'usage anonymises ou pseudonymises, par exemple pour analyser le
nombre de sessions, les plages horaires et les consommations sans exposer email,
pseudo, nom ou telephone.

La migration est volontairement limitee a PostgreSQL. Les tests unitaires du
projet utilisent SQLite ; la migration devient donc un no-op sur SQLite afin de
garder la suite rapide et portable.

Synthese
--------

Le MCD ne doit pas etre applique tel quel dans le projet. Il doit rester une
reference de conception et une cible d'evolution.

L'implementation Django est le modele operationnel actuel parce qu'elle :

* respecte les besoins fonctionnels reels de l'application ;
* integre l'authentification et les permissions Django ;
* garde les migrations versionnees ;
* reste testable avec pytest et SQLite ;
* evite un double schema SQL/ORM ;
* prepare les evolutions PostgreSQL et TimescaleDB sans les imposer trop tot.

La trajectoire reste progressive :

1. conserver le modele Django comme source de verite applicative ;
2. ajouter les optimisations SQL lorsqu'elles repondent a un usage mesure ou
   clairement identifie ;
3. enrichir les vues SQL pour les exports ou statistiques ;
4. activer les hypertables TimescaleDB quand le volume de telemetrie augmente ;
5. envisager RLS, anonymizer, compression et retention pour une version durcie.
