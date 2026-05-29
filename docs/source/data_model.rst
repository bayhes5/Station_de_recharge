Modèle de données applicatif
============================

Cette page explique comment le MCD de référence décrit dans
:doc:`database_mcd` est implémenté dans le modèle Django. Le MCD donne la vision
fonctionnelle de la base ; l’implémentation Django l’adapte aux besoins concrets
de l’application, aux migrations ORM, à l’authentification Django et aux tests.

Positionnement du MCD
---------------------

Le MCD fourni est une bonne base de conception. Il décrit les grands domaines du
projet :

* utilisateurs, profils, rôles et moyens d’authentification ;
* consentements et journal de sécurité ;
* stations, bornes, emplacements, devices ESP32 et capteurs ;
* réservations, sessions de charge et télémétrie ;
* alertes, techniciens et maintenances ;
* pistes RGPD et performance avec vues, anonymisation, TimescaleDB et index.

Il ne doit cependant pas être appliqué tel quel comme script SQL dans le projet.
La source opérationnelle de la base est le modèle Django situé dans
``backend/api/models.py`` et ses migrations dans ``backend/api/migrations/``. La
référence MCD/PostgreSQL reste placée avant cette page dans le sommaire afin de
présenter d’abord la cible fonctionnelle, puis les choix d’implémentation.

Cette décision évite de maintenir deux schémas concurrents : un schéma SQL
manuel et un schéma généré par Django. Toute évolution structurelle doit passer
par une migration Django afin de rester versionnée, testable et reproductible
dans Docker, en CI et sur les postes de développement.

Choix d’implémentation
----------------------

Valeurs métier fermées
~~~~~~~~~~~~~~~~~~~~~~

Les cycles de vie structurants sont déclarés dans ``backend/api/models.py`` avec
des classes ``TextChoices``. Cette couche ferme les valeurs acceptées par les
serializers Django REST Framework et par les formulaires d'administration, tout
en conservant un stockage simple en ``VARCHAR``.

Les migrations ajoutent aussi des contraintes ``CHECK`` sur ces champs. La
base refuse donc une valeur hors catalogue même si elle arrive par un script ou
une écriture directe. Une migration de normalisation précède ces contraintes
pour ramener les anciennes valeurs libres vers les valeurs métier retenues.

Les champs concernés sont notamment :

* ``Utilisateur.statut`` : ``actif``, ``suspendu``, ``archive`` ;
* ``Station.statut`` : ``active``, ``maintenance``, ``inactive`` ;
* ``Emplacement.statut`` : ``disponible``, ``reserve``, ``occupe``,
  ``maintenance`` ;
* ``Emplacement.lock_state`` : ``verrouille``, ``deverrouille``, ``bloque`` ;
* ``Reservation.auth_choice`` : ``rfid``, ``qr``, ``code`` ;
* ``Reservation.statut`` : ``en_attente``, ``confirmee``, ``active``,
  ``annulee``, ``terminee`` ;
* ``Session.charge_state`` : ``reserved``, ``access_validated``,
  ``waiting_plug``, ``charging``, ``stopping``, ``stopped``, ``error`` ;
* ``Device.status`` : ``provisioned``, ``online``, ``idle``, ``offline``,
  ``charging``, ``error`` ;
* ``Alerte.status`` : ``nouvelle``, ``active``, ``prise_en_charge``,
  ``resolue``, ``closed``, ``fermee`` ;
* ``Maintenance.status`` : ``planifiee``, ``en_cours``, ``realisee``,
  ``annulee``.

Les types de capteurs, types d'alertes et types d'intervention restent plus
ouverts. Ils dépendent du matériel, du firmware et de l'exploitation terrain ;
les figer trop tôt rendrait l'intégration ESP32 moins souple.

Les champs ``Device.last_command_*`` conservent le dernier ACK MQTT reçu pour un
ESP32 : identifiant de commande, action, statut, message et horodatage. Ils
servent à l'exploitation et à la supervision, sans remplacer ``Device.status``
ni ``Device.last_seen``.

Le modèle ``DeviceCommandLog`` conserve l'historique récent des ACK de
commandes ESP32. Il rattache l'action au device, à la session de charge lorsque
le firmware renvoie ``session_id``, au ``command_id`` et au payload brut reçu.
Ce journal sert à auditer les ordres ``START``, ``STOP``, ``LOCK`` et
``UNLOCK`` sans dépendre uniquement du dernier état écrasé sur ``Device``.

UUID
~~~~

Le MCD prévoit ``CREATE EXTENSION "uuid-ossp"`` et des valeurs par défaut
``uuid_generate_v4()``. Dans le projet, les UUID sont générés côté Django avec
``uuid.uuid4`` sur les champs ``UUIDField``.

Ce choix garde l'application compatible avec l'ORM et les tests SQLite. Il rend
l'extension ``uuid-ossp`` non indispensable pour la version actuelle.

Utilisateur Django
~~~~~~~~~~~~~~~~~~

Le MCD décrit une table ``utilisateur`` autonome avec ``email``,
``password_hash``, ``statut``, ``created_at``, ``last_login`` et
``failed_attempts``.

Le projet utilise un modèle ``Utilisateur`` personnalisé qui hérite de
``AbstractBaseUser`` et ``PermissionsMixin``. Cela ajoute les conventions Django
nécessaires : mot de passe géré par Django, permissions, groupes, ``is_staff``,
``is_active`` et ``date_joined``.

Le pseudo est l'identifiant principal de connexion, et l'email reste unique.
Cette structure permet d'utiliser l'administration Django, les permissions DRF,
les jetons JWT et les tests d'authentification sans recréer toute la mécanique
de sécurité.

Profil utilisateur
~~~~~~~~~~~~~~~~~~

Le modèle ``ProfilUtilisateur`` reprend bien l’idée du MCD : les données
personnelles comme le nom et le téléphone sont séparées du compte
d'authentification.

La relation est un ``OneToOneField`` vers ``Utilisateur`` avec suppression en
cascade. Si le compte est supprimé, le profil associé disparaît aussi.

Rôles
~~~~~

Les tables ``role`` et ``utilisateur_role`` existent dans Django. Elles
permettent de conserver une représentation métier simple des rôles, en plus des
permissions Django natives.

La table de liaison garde la date d'affectation avec ``assigned_at`` et impose
l’unicité du couple utilisateur-rôle.

Authentification multi-moyens
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Le MCD prévoit ``auth_type`` et ``auth_method``. Le projet implémente ces
concepts avec ``TypeAuth`` et ``Authentification``.

``Authentification`` stocke le secret sous la colonne SQL ``secret_hash`` via le
champ Django ``hash_valeur``. Le modèle ajoute aussi :

* ``display_value`` pour afficher une valeur masquee ou lisible quand c'est
  acceptable ;
* ``metadata`` pour stocker les informations nécessaires aux QR codes, codes
  temporaires et associations RFID ;
* ``expiration`` et ``is_active`` pour gérer révocation et durée de validité.

Cette structure est plus adaptée au projet que le MCD minimal, car elle couvre
les QR codes, les codes temporaires et les badges RFID persistants.

RGPD et journalisation
~~~~~~~~~~~~~~~~~~~~~~

Les tables ``consentement`` et ``journal_securite`` sont implémentées.

``JournalSecurite`` utilise ``ON DELETE SET NULL`` plutôt qu’une cascade stricte
sur l’utilisateur. Ce choix permet de conserver une trace d’événements sensibles
même si le compte utilisateur est supprimé ou anonymisé.

La table ``consentement`` sert à tracer les choix explicites de l’utilisateur
lorsqu’un traitement repose réellement sur le consentement. Elle est pertinente
pour les traitements optionnels : acceptation des CGU, prise de connaissance de
la politique de confidentialité, notifications non indispensables ou mesure
d’audience.

Elle ne doit pas être utilisée comme justification générique pour tous les
traitements. Les données nécessaires à la création du compte, à la réservation,
à la sécurité ou à la maintenance du service relèvent plutôt du contrat, de
l’intérêt légitime ou d’une obligation légale. Cette distinction renforce la
crédibilité RGPD du projet : le consentement reste libre, spécifique et
révocable.

La table est utilisée dès l’inscription. Le formulaire demande explicitement
l’acceptation des CGU, la prise de connaissance de la politique de
confidentialité et le choix relatif aux notifications optionnelles. L’API crée
ensuite trois lignes historisées :

* ``cgu/accepte`` ;
* ``politique_confidentialite/accepte`` ;
* ``notifications/accepte`` ou ``notifications/refuse`` selon le choix de
  l’utilisateur.

Ce choix donne une preuve datée des décisions prises à la création du compte,
tout en séparant clairement les consentements optionnels des traitements
nécessaires au service. Le profil utilisateur expose ensuite les consentements
courants et permet de modifier les notifications optionnelles. Lorsqu’un choix
change, l’API ajoute une nouvelle ligne datée dans ``consentement`` au lieu
d’écraser l’historique existant.

Les mécanismes PostgreSQL avancés du MCD, comme l’extension ``anon``, les
``SECURITY LABEL`` et les vues SQL d'export, ne sont pas encore actives. Le
projet gère pour l’instant l’export et la suppression côté API Django.

Stations, bornes et emplacements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``Station``, ``Borne`` et ``Emplacement`` décrivent l'infrastructure physique.

Le modèle Django ajoute ``latitude`` et ``longitude`` sur ``Station`` afin de
supporter la carte de réservation. ``Borne`` représente une armoire ou un
kiosque physique rattaché à une station. ``Emplacement`` garde le numéro, l’état
métier et l’état de cadenas.

La hiérarchie métier est donc : station, borne, emplacement. Une contrainte
d’unicité empêche deux emplacements d’une même borne de porter le même numéro.
Le champ ``station`` reste aussi présent sur ``Emplacement`` pour conserver des
requêtes simples et une compatibilité avec les flux existants ; il est aligné
automatiquement avec la station de la borne.

Devices ESP32
~~~~~~~~~~~~~

``Device`` correspond au MCD et représente le contrôleur embarqué d’un
emplacement. La relation avec ``Emplacement`` est un ``OneToOneField`` : un
emplacement ne doit avoir qu’un device principal dans la version actuelle.

Le modèle distingue l'identité logique et l'identité physique :

* ``slot_id`` : identifiant MQTT de l'emplacement, par exemple ``slot1`` ;
* ``hardware_mac`` : adresse MAC Wi-Fi réelle de la carte ESP32 ;
* ``ip_address`` : adresse IP courante, informative car elle peut changer ;
* ``firmware_version`` : version publiée par le firmware ;
* ``mac_address`` : ancien champ conservé temporairement pour compatibilité avec
  les données et tests déjà existants.

Le backend utilise ``slot_id`` pour router et afficher l'emplacement. Les
payloads ``status``, ``ack`` et ``telemetry`` peuvent mettre à jour
automatiquement ``firmware_version``, ``hardware_mac`` et ``ip_address``.

Capteurs et données capteurs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``Capteur`` et ``CapteurData`` reprennent le principe du MCD : un device porte
plusieurs capteurs, et chaque mesure horodatée est stockée dans ``capteur_data``.

Les valeurs booléennes issues de l'ESP32, comme ``door`` et ``cable``, sont
converties en ``1.0`` ou ``0.0`` pour rester compatibles avec ``valeur`` de type
flottant. L'API ajoute ensuite une valeur d'affichage lisible dans la supervision
administrateur.

Le MCD cible propose des hypertables TimescaleDB pour ``capteur_data``. Elles ne
sont pas encore activées : la table reste une table Django standard afin de
garder la solution simple et portable.

Réservations
~~~~~~~~~~~~

``Reservation`` relie un utilisateur, un emplacement, un moyen
d’authentification et une fenêtre de temps.

Le projet ajoute ``reference_code`` et ``auth_choice`` afin de gérer le parcours
terminal : code de réservation, QR code, code SMS temporaire ou RFID.

La relation vers ``Utilisateur`` est en ``SET_NULL`` et non en cascade. Ce choix
évite d’effacer tout l’historique technique d’une réservation si le compte est
supprimé. La donnée personnelle peut disparaître, tandis que l’événement métier
reste exploitable.

Sessions de charge
~~~~~~~~~~~~~~~~~~

Le MCD prévoit une table ``session`` avec ``id_user``, ``date_debut``,
``date_fin``, ``consommation_kwh`` et ``etat_batterie``.

Le projet implémente ce concept dans la table SQL ``charging_session``. Le
modèle Django s’appelle ``Session`` mais sa table n’est pas nommée ``session``,
ce qui évite aussi la confusion avec la notion de session applicative.

La session réelle est rattachée à une réservation et à un emplacement. Elle
stocke ``start_time`` et ``end_time``. L’utilisateur se retrouve via
``session.reservation.utilisateur``.

``charge_state`` formalise le cycle technique de la charge côté backend :
``reserved`` lorsque la session existe sans commande validée, ``access_validated``
après authentification, ``waiting_plug`` après ACK ``UNLOCK`` ou attente de
branchement, ``charging`` dès que l'ESP32 confirme la charge ou publie de la
télémétrie active, ``stopping`` après ACK ``STOP`` ou retour ``idle`` avant
clôture backend, ``stopped`` lorsque ``end_time`` est renseigné, et ``error`` si
l'ESP32 remonte un état de défaut.
Ce champ complète ``end_time`` : il évite les doubles ``START`` et rend visibles
les sessions arrêtées physiquement mais pas encore clôturées côté backend.

La consommation instantanee ou cumulee n'est pas stockee directement dans
``charging_session``. Elle est portee par ``session_telemetry`` avec
``energie_kwh``. Cette séparation garde la session comme un objet métier et la
télémétrie comme une série temporelle.

Télémétrie de session
~~~~~~~~~~~~~~~~~~~~~

``SessionTelemetry`` correspond au MCD : il stocke courant, tension, energie et
timestamp pour une session active.

La table est indexée par session et timestamp. Elle pourra devenir une
hypertable TimescaleDB si la fréquence de mesures augmente fortement.

Alertes
~~~~~~~

``Alerte`` correspond au MCD mais adapte les suppressions : les liens vers
``CapteurData`` et ``Session`` sont en ``SET_NULL``. Cela permet de garder une
alerte historique même si la mesure ou la session associée n’est plus disponible.

Le champ ``timestamp`` est stocké dans la colonne SQL ``date`` pour rester proche
du MCD tout en gardant un nom Django plus explicite.

Les champs ``first_seen`` et ``last_seen`` encadrent la durée de l'anomalie. Les
champs ``notified_at`` et ``notification_count`` permettent de tracer les emails
envoyés et d'appliquer un délai de relance sans dupliquer les alertes.

Le workflow technicien est porté directement par l'alerte. ``assigned_technician``
identifie l'intervenant responsable, ``acknowledged_by`` et ``acknowledged_at``
tracent la prise en charge, puis ``resolved_by``, ``resolved_at`` et
``resolution_note`` documentent la clôture opérationnelle. Les alertes restent
filtrées par station via ``TechnicienStation`` afin de respecter le principe du
moindre privilège.

Le cycle actuel est géré côté application :

* ``nouvelle`` à la création ;
* ``active`` si la même anomalie continue ;
* ``prise_en_charge`` lorsqu'un technicien accepte l'incident ;
* ``resolue`` quand la télémétrie revient à la normale.

Maintenance
~~~~~~~~~~~

``Technicien`` et ``Maintenance`` reprennent le MCD. Le projet ajoute la
possibilité de lier un technicien à un compte ``Utilisateur``. Cela permet à un
technicien de se connecter et de consulter ses interventions.

``TechnicienStation`` applique le principe du moindre privilège côté métier :
un administrateur affecte explicitement un technicien à une ou plusieurs
stations. La supervision technicien ne lit ensuite que les devices, alertes,
mesures et commandes des stations actives dans ce périmètre. Grafana reste un
outil de supervision technique global ou administrateur ; l'accès terrain
quotidien des techniciens passe par l'application, où le filtrage est porté par
l'API Django. Dans l'interface d'administration, ce périmètre est intégré à la
fiche du technicien afin que l'identité, le compte lié et les stations
autorisées soient contrôlés dans un seul écran.

Performance et TimescaleDB
--------------------------

Le conteneur ``db`` utilise l’image ``timescale/timescaledb:latest-pg15``. Une
migration active l'extension ``timescaledb`` quand elle est disponible sur le
serveur PostgreSQL. Sur SQLite ou sur un PostgreSQL sans extension installée, la
migration reste sans effet pour préserver la portabilité du projet.

Dans l’état actuel, le projet utilise TimescaleDB comme un PostgreSQL compatible.
Les tables ``capteur_data`` et ``session_telemetry`` ne sont pas encore des
hypertables. Ce choix est volontaire : elles possèdent aujourd'hui une clé
primaire UUID simple, alors qu'une hypertable TimescaleDB impose que les
contraintes uniques incluent la colonne temporelle de partitionnement. Le passage
en hypertables doit donc être traité comme une refonte de schéma ciblée, pas
comme une simple commande SQL ajoutée en fin de migration.

Les index déjà présents couvrent les requêtes les plus importantes :

* emplacements par borne, station et statut opérationnel ;
* réservations par utilisateur, statut, emplacement et dates ;
* sessions par emplacement et dates ;
* devices par dernière activité ;
* télémétrie par session et timestamp ;
* données capteurs par capteur et timestamp ;
* alertes par statut, session et timestamp ;
* alertes par technicien assigné et statut ;
* affectations technicien-station par technicien, station et statut actif ;
* maintenances par technicien, station, statut et date planifiée.

Une migration complémentaire ajoute aussi des index orientés exploitation :

* ``capteur(type, id_device)`` pour retrouver rapidement les séries par type de
  capteur et par device ;
* ``capteur_data(timestamp DESC)`` pour les dernières mesures et les fenêtres
  temporelles Grafana ;
* ``session_telemetry(timestamp DESC)`` pour les analyses temporelles de session ;
* ``alerte(date DESC)`` pour les alertes récentes affichées en supervision.

Une seconde migration complète cette logique avec des index métier plus proches
des écrans d’exploitation et des filtres API :

* ``emplacement(statut_cadenas, etat)`` pour identifier rapidement les points de
  charge selon l’état du cadenas et l’état opérationnel ;
* ``reservation(date_debut, date_fin)`` pour les recherches de disponibilité sur
  une fenêtre de temps ;
* ``charging_session(start_time, end_time)`` pour les sessions ouvertes, fermées
  ou analysées par période ;
* ``charging_session(charge_state, end_time)`` pour identifier les sessions en
  charge, en arrêt ou en erreur ;
* ``device(status, last_seen)`` pour détecter les équipements indisponibles ou
  silencieux ;
* ``alerte(niveau_severite, date)`` pour prioriser les incidents ;
* ``alerte(type, date)`` pour suivre les familles d’anomalies dans le temps ;
* ``alerte(assigned_technician_id, status)`` pour afficher rapidement les
  incidents ouverts par technicien.

Ces index ne changent pas le modèle fonctionnel. Ils rendent les parcours
critiques plus prévisibles lorsque le volume augmente : supervision temps réel,
historique d'exploitation, diagnostic terrain et tableaux de bord.

Les optimisations du MCD cible, comme ``create_hypertable``, compression,
retention et vues matérialisées, restent pertinentes pour une phase production
ou une simulation à volume élevé. Elles nécessitent toutefois de revoir la clé
primaire des tables de télémétrie ou d'introduire des tables spécialisées pour
les séries temporelles.

Sécurité base de données
------------------------

Le MCD propose Row Level Security sur ``session`` et ``reservation``.

Dans le projet actuel, l’isolation est portée par l’API Django : les endpoints
utilisateur filtrent toujours avec ``request.user`` et les endpoints
administrateur exigent les droits staff.

Activer la RLS dans PostgreSQL serait possible, mais il faut alors garantir que
``app.current_user_id`` est défini et nettoyé correctement pour chaque requête.
Comme Django réutilise ses connexions, une mauvaise gestion de ce contexte peut
créer des erreurs difficiles à diagnostiquer. La RLS est donc considérée comme
une évolution de durcissement, pas comme un prérequis de la version actuelle.

RGPD cible
----------

Le MCD propose plusieurs mécanismes SQL :

* vue ``session_anonyme`` ;
* vue ``export_user_data`` ;
* fonction ``delete_user_rgpd`` ;
* extension ``anon`` et masquage dynamique ;
* hachage de l’identifiant utilisateur dans les exports statistiques.

Le projet implémente déjà une partie de ce besoin côté API :

* profil séparé du compte ;
* export de compte via endpoint authentifié ;
* suppression depuis le profil ;
* journalisation des actions sensibles ;
* conservation possible d’événements techniques sans lien personnel direct.

Les vues SQL et l’anonymisation PostgreSQL sont traitées progressivement. La vue
``session_anonyme`` est toujours disponible sur PostgreSQL. La migration
``0027_optional_postgresql_anonymizer`` active aussi l’extension ``anon`` et ses
``SECURITY LABEL`` quand le serveur PostgreSQL fournit PostgreSQL Anonymizer.
Cette migration est volontairement optionnelle : elle ne casse pas SQLite, ni une
image TimescaleDB qui ne contient pas encore l’extension système.

Vue ``session_anonyme``
------------------------

La première vue SQL ajoutée côté PostgreSQL est ``session_anonyme``. Elle expose
un jeu de données dédié aux statistiques de sessions sans publier directement
l’identifiant utilisateur.

La vue s'appuie sur les tables reelles de l'application :

* ``charging_session`` pour les dates de début et de fin ;
* ``reservation`` pour retrouver l’utilisateur lié à la session ;
* ``session_telemetry`` pour calculer la consommation observée.

Le champ ``user_hash`` est produit avec ``md5(id_user::text)`` lorsque la session
est encore rattachée à un utilisateur. Si le lien utilisateur a disparu, la vue
utilise l'identifiant de session comme valeur de repli afin de conserver une
ligne statistique sans recréer de donnée personnelle.

Cette vue ne remplace pas les contrôles d’accès applicatifs. Elle sert de base à
des rapports d’usage anonymisés ou pseudonymisés, par exemple pour analyser le
nombre de sessions, les plages horaires et les consommations sans exposer email,
pseudo, nom ou téléphone.

La migration est volontairement limitee a PostgreSQL. Les tests unitaires du
projet utilisent SQLite ; la migration devient donc un no-op sur SQLite afin de
garder la suite rapide et portable.

Extension PostgreSQL Anonymizer
-------------------------------

Quand l’extension ``anon`` est disponible dans PostgreSQL, la migration
``0027_optional_postgresql_anonymizer`` pose des règles de masquage sur les
colonnes personnelles suivantes :

* ``utilisateur.pseudo`` et ``utilisateur.email`` ;
* ``profil_utilisateur.nom`` et ``profil_utilisateur.telephone`` ;
* ``journal_securite.ip`` ;
* ``technicien.nom``, ``technicien.email`` et ``technicien.telephone``.

L’objectif n’est pas de masquer les données dans l’application de production,
mais de permettre des exports, jeux de tests ou accès SQL restreints sans
exposer directement les données personnelles. L’installation de l’extension
reste une décision d’infrastructure : l’image TimescaleDB standard du projet ne
garantit pas sa présence.

Synthèse
--------

Le MCD ne doit pas être appliqué tel quel dans le projet. Il doit rester une
référence de conception et une cible d’évolution.

L’implémentation Django est le modèle opérationnel actuel parce qu’elle :

* respecte les besoins fonctionnels réels de l’application ;
* intègre l’authentification et les permissions Django ;
* garde les migrations versionnées ;
* reste testable avec pytest et SQLite ;
* évite un double schéma SQL/ORM ;
* prépare les évolutions PostgreSQL et TimescaleDB sans les imposer trop tôt.

La trajectoire reste progressive :

1. conserver le modèle Django comme source de vérité applicative ;
2. ajouter les optimisations SQL lorsqu’elles répondent à un usage mesuré ou
   clairement identifié ;
3. enrichir les vues SQL pour les exports ou statistiques ;
4. activer les hypertables TimescaleDB quand le volume de télémétrie augmente ;
5. activer l’image PostgreSQL/TimescaleDB incluant ``anon`` lorsque des dumps
   anonymisés ou des rôles SQL masqués deviennent nécessaires ;
6. envisager RLS, compression et rétention native pour une version durcie.
