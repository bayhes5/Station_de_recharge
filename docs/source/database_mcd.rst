Référence du MCD et du schéma PostgreSQL
========================================

Cette page ouvre la partie modèle de données. Elle présente d’abord la cible
fonctionnelle : schéma relationnel, champs, valeurs attendues, relations et
script PostgreSQL représentatif. La page :doc:`data_model` vient ensuite pour
expliquer les arbitrages entre cette cible et l’implémentation Django réellement
utilisée par l’application.

Le schéma est aligné avec le modèle Django actuel. Les tables techniques ajoutées
par Django pour les groupes et permissions ne sont pas détaillées ici : elles
font partie du socle d’administration Django, pas du domaine métier de la
station.

Principes de modélisation
-------------------------

La base est organisée autour de cinq ensembles fonctionnels :

* **comptes et sécurité** : utilisateurs, profils, rôles, moyens
  d’authentification, consentements et journal de sécurité ;
* **infrastructure terrain** : stations, emplacements de charge, devices ESP32
  et capteurs ;
* **réservation et session** : réservation utilisateur, authentification choisie
  et session de charge effective ;
* **télémétrie et alertes** : mesures capteurs, mesures électriques et alertes
  opérationnelles ;
* **maintenance** : techniciens et interventions planifiées.

Les valeurs textuelles comme ``statut``, ``status`` ou ``type`` restent des
chaînes dans la base. Cela garde de la souplesse pour l’API et les simulations.
Les valeurs indiquées ci-dessous sont donc les valeurs fonctionnelles attendues,
pas toujours des contraintes SQL strictes.

Diagramme Mermaid
-----------------

Le bloc suivant est rendu par Sphinx avec l’extension Mermaid. Il contient les
tables, les champs structurants, les clés et les relations. Il peut aussi être
copié dans un visualiseur Mermaid ou dans un outil compatible pour obtenir le
diagramme ER.

.. mermaid::

   erDiagram
       utilisateur {
           UUID id_user PK
           VARCHAR pseudo UK
           VARCHAR email UK
           VARCHAR password
           VARCHAR statut
           TIMESTAMP created_at
           TIMESTAMP last_login
           INTEGER failed_attempts
           BOOLEAN is_active
           BOOLEAN is_staff
           BOOLEAN is_superuser
           TIMESTAMP date_joined
       }

       profil_utilisateur {
           UUID id_profil PK
           UUID id_user FK
           VARCHAR nom
           VARCHAR telephone
       }

       role {
           UUID id_role PK
           VARCHAR nom UK
           TEXT description
       }

       utilisateur_role {
           UUID id_user PK,FK
           UUID id_role PK,FK
           TIMESTAMP assigned_at
       }

       consentement {
           UUID id_consentement PK
           UUID id_user FK
           VARCHAR type
           VARCHAR statut
           TIMESTAMP date_consentement
       }

       journal_securite {
           UUID id_log PK
           UUID id_user FK
           INET ip
           VARCHAR action
           VARCHAR statut
           TIMESTAMP date_action
       }

       type_auth {
           UUID id_type PK
           VARCHAR libelle UK
           SMALLINT factor_level
       }

       auth_method {
           UUID id_auth PK
           UUID id_user FK
           UUID id_type FK
           TEXT secret_hash
           VARCHAR display_value
           JSONB metadata
           TIMESTAMP expiration
           BOOLEAN is_active
           TIMESTAMP created_at
       }

       station {
           UUID id_station PK
           VARCHAR nom
           VARCHAR localisation
           DOUBLE latitude
           DOUBLE longitude
           VARCHAR statut
           TIMESTAMP created_at
       }

       emplacement {
           UUID id_emplacement PK
           UUID id_station FK
           INTEGER numero
           VARCHAR etat
           VARCHAR statut_cadenas
       }

       device {
           UUID id_device PK
           UUID id_emplacement FK
           VARCHAR type_device
           VARCHAR firmware_version
           INET ip_address
           VARCHAR mac_address
           TIMESTAMP last_seen
           VARCHAR status
       }

       capteur {
           UUID id_capteur PK
           UUID id_device FK
           VARCHAR type
           VARCHAR unite
       }

       capteur_data {
           UUID id_data PK
           UUID id_capteur FK
           DOUBLE valeur
           TIMESTAMP timestamp
       }

       reservation {
           UUID id_reservation PK
           VARCHAR reference_code UK
           UUID id_user FK
           UUID id_emplacement FK
           UUID id_auth FK
           VARCHAR auth_choice
           TIMESTAMP date_debut
           TIMESTAMP date_fin
           VARCHAR statut
       }

       charging_session {
           UUID id_session PK
           UUID id_reservation FK,UK
           UUID id_emplacement FK
           TIMESTAMP start_time
           TIMESTAMP end_time
       }

       session_telemetry {
           UUID id_telemetry PK
           UUID id_session FK
           DOUBLE courant
           DOUBLE tension
           DOUBLE energie_kwh
           TIMESTAMP timestamp
       }

       alerte {
           UUID id_alerte PK
           UUID id_data FK
           UUID id_session FK
           VARCHAR type
           TEXT message
           VARCHAR niveau_severite
           VARCHAR status
           TIMESTAMP date
       }

       technicien {
           UUID id_tech PK
           UUID id_user FK,UK
           VARCHAR nom
           VARCHAR email UK
           VARCHAR telephone
       }

       maintenance {
           UUID id_maintenance PK
           UUID id_station FK
           UUID id_technicien FK
           VARCHAR type
           TEXT description
           VARCHAR status
           TIMESTAMP date_planifiee
           TIMESTAMP date_realisee
       }

       utilisateur ||--o| profil_utilisateur : possède
       utilisateur ||--o{ utilisateur_role : reçoit
       role ||--o{ utilisateur_role : définit
       utilisateur ||--o{ consentement : donne
       utilisateur ||--o{ journal_securite : déclenche
       utilisateur ||--o{ auth_method : possède
       type_auth ||--o{ auth_method : classe
       utilisateur ||--o{ reservation : réserve
       auth_method ||--o{ reservation : sécurise
       station ||--o{ emplacement : contient
       emplacement ||--o| device : équipe
       device ||--o{ capteur : mesure
       capteur ||--o{ capteur_data : produit
       emplacement ||--o{ reservation : concerne
       reservation ||--o| charging_session : ouvre
       emplacement ||--o{ charging_session : accueille
       charging_session ||--o{ session_telemetry : mesure
       charging_session ||--o{ alerte : génère
       capteur_data ||--o{ alerte : explique
       utilisateur ||--o| technicien : peut_être
       station ||--o{ maintenance : nécessite
       technicien ||--o{ maintenance : réalise

Script de création PostgreSQL
-----------------------------

Ce script de création représente le schéma métier attendu sur PostgreSQL. Dans
le projet, les migrations Django restent la source opérationnelle pour créer et
faire évoluer la base.

.. code-block:: sql

   CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

   CREATE TABLE utilisateur (
       id_user UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
       pseudo VARCHAR(100) UNIQUE NOT NULL,
       email VARCHAR(254) UNIQUE NOT NULL,
       password VARCHAR(128) NOT NULL,
       statut VARCHAR(50) DEFAULT 'actif',
       created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
       last_login TIMESTAMP,
       failed_attempts INTEGER NOT NULL DEFAULT 0,
       is_active BOOLEAN NOT NULL DEFAULT TRUE,
       is_staff BOOLEAN NOT NULL DEFAULT FALSE,
       is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
       date_joined TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
   );

   CREATE TABLE profil_utilisateur (
       id_profil UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
       id_user UUID UNIQUE NOT NULL REFERENCES utilisateur(id_user) ON DELETE CASCADE,
       nom VARCHAR(100) NOT NULL DEFAULT '',
       telephone VARCHAR(20) NOT NULL DEFAULT ''
   );

   CREATE TABLE role (
       id_role UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
       nom VARCHAR(50) UNIQUE NOT NULL,
       description TEXT NOT NULL DEFAULT ''
   );

   CREATE TABLE utilisateur_role (
       id_user UUID NOT NULL REFERENCES utilisateur(id_user) ON DELETE CASCADE,
       id_role UUID NOT NULL REFERENCES role(id_role) ON DELETE CASCADE,
       assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
       PRIMARY KEY (id_user, id_role)
   );

   CREATE TABLE consentement (
       id_consentement UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
       id_user UUID NOT NULL REFERENCES utilisateur(id_user) ON DELETE CASCADE,
       type VARCHAR(100) NOT NULL,
       statut VARCHAR(50) NOT NULL,
       date_consentement TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
   );

   CREATE TABLE journal_securite (
       id_log UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
       id_user UUID REFERENCES utilisateur(id_user) ON DELETE SET NULL,
       action VARCHAR(255) NOT NULL,
       ip INET NOT NULL,
       statut VARCHAR(50) NOT NULL,
       date_action TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
   );

   CREATE TABLE type_auth (
       id_type UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
       libelle VARCHAR(50) UNIQUE NOT NULL,
       factor_level SMALLINT NOT NULL
   );

   CREATE TABLE auth_method (
       id_auth UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
       id_user UUID NOT NULL REFERENCES utilisateur(id_user) ON DELETE CASCADE,
       id_type UUID NOT NULL REFERENCES type_auth(id_type) ON DELETE RESTRICT,
       secret_hash TEXT NOT NULL,
       display_value VARCHAR(255) NOT NULL DEFAULT '',
       metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
       expiration TIMESTAMP,
       is_active BOOLEAN NOT NULL DEFAULT TRUE,
       created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
   );

   CREATE TABLE station (
       id_station UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
       nom VARCHAR(100) NOT NULL,
       localisation VARCHAR(255) NOT NULL,
       latitude DOUBLE PRECISION,
       longitude DOUBLE PRECISION,
       statut VARCHAR(50) NOT NULL,
       created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
   );

   CREATE TABLE emplacement (
       id_emplacement UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
       id_station UUID NOT NULL REFERENCES station(id_station) ON DELETE CASCADE,
       numero INTEGER NOT NULL,
       etat VARCHAR(50) NOT NULL,
       statut_cadenas VARCHAR(50) NOT NULL,
       UNIQUE (id_station, numero)
   );

   CREATE TABLE device (
       id_device UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
       id_emplacement UUID UNIQUE NOT NULL REFERENCES emplacement(id_emplacement) ON DELETE CASCADE,
       type_device VARCHAR(50) NOT NULL,
       firmware_version VARCHAR(50) NOT NULL,
       ip_address INET,
       mac_address VARCHAR(50) NOT NULL DEFAULT '',
       last_seen TIMESTAMP,
       status VARCHAR(50) NOT NULL
   );

   CREATE TABLE capteur (
       id_capteur UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
       id_device UUID REFERENCES device(id_device) ON DELETE CASCADE,
       type VARCHAR(50) NOT NULL,
       unite VARCHAR(20) NOT NULL
   );

   CREATE TABLE capteur_data (
       id_data UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
       id_capteur UUID NOT NULL REFERENCES capteur(id_capteur) ON DELETE CASCADE,
       valeur DOUBLE PRECISION NOT NULL,
       timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
   );

   CREATE TABLE reservation (
       id_reservation UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
       reference_code VARCHAR(12) UNIQUE,
       id_user UUID REFERENCES utilisateur(id_user) ON DELETE SET NULL,
       id_emplacement UUID NOT NULL REFERENCES emplacement(id_emplacement) ON DELETE CASCADE,
       id_auth UUID REFERENCES auth_method(id_auth) ON DELETE SET NULL,
       auth_choice VARCHAR(20) NOT NULL DEFAULT 'qr',
       date_debut TIMESTAMP NOT NULL,
       date_fin TIMESTAMP NOT NULL,
       statut VARCHAR(50) NOT NULL,
       CONSTRAINT reservation_date_fin_gt_debut CHECK (date_fin > date_debut)
   );

   CREATE TABLE charging_session (
       id_session UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
       id_reservation UUID UNIQUE NOT NULL REFERENCES reservation(id_reservation) ON DELETE CASCADE,
       id_emplacement UUID NOT NULL REFERENCES emplacement(id_emplacement) ON DELETE CASCADE,
       start_time TIMESTAMP NOT NULL,
       end_time TIMESTAMP,
       CONSTRAINT session_end_gt_start CHECK (end_time IS NULL OR end_time > start_time)
   );

   CREATE TABLE session_telemetry (
       id_telemetry UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
       id_session UUID NOT NULL REFERENCES charging_session(id_session) ON DELETE CASCADE,
       courant DOUBLE PRECISION NOT NULL,
       tension DOUBLE PRECISION NOT NULL,
       energie_kwh DOUBLE PRECISION NOT NULL,
       timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
   );

   CREATE TABLE alerte (
       id_alerte UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
       id_data UUID REFERENCES capteur_data(id_data) ON DELETE SET NULL,
       id_session UUID REFERENCES charging_session(id_session) ON DELETE SET NULL,
       type VARCHAR(50) NOT NULL,
       message TEXT NOT NULL,
       niveau_severite VARCHAR(50) NOT NULL,
       status VARCHAR(50) NOT NULL,
       date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
   );

   CREATE TABLE technicien (
       id_tech UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
       id_user UUID UNIQUE REFERENCES utilisateur(id_user) ON DELETE SET NULL,
       nom VARCHAR(100) NOT NULL,
       email VARCHAR(254) UNIQUE NOT NULL,
       telephone VARCHAR(20) NOT NULL DEFAULT ''
   );

   CREATE TABLE maintenance (
       id_maintenance UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
       id_station UUID NOT NULL REFERENCES station(id_station) ON DELETE CASCADE,
       id_technicien UUID NOT NULL REFERENCES technicien(id_tech) ON DELETE CASCADE,
       type VARCHAR(100) NOT NULL,
       description TEXT NOT NULL,
       status VARCHAR(50) NOT NULL,
       date_planifiee TIMESTAMP NOT NULL,
       date_realisee TIMESTAMP
   );

   CREATE INDEX idx_user_is_active ON utilisateur(is_active);
   CREATE INDEX idx_user_date_joined ON utilisateur(date_joined);
   CREATE INDEX idx_consent_user_date ON consentement(id_user, date_consentement);
   CREATE INDEX idx_log_user_date ON journal_securite(id_user, date_action);
   CREATE INDEX idx_auth_user_type ON auth_method(id_user, id_type, is_active);
   CREATE INDEX idx_auth_expiration ON auth_method(expiration);
   CREATE INDEX idx_station_nom ON station(nom);
   CREATE INDEX idx_station_statut ON station(statut);
   CREATE INDEX idx_emp_station_statut ON emplacement(id_station, etat);
   CREATE INDEX idx_emp_lock_state ON emplacement(statut_cadenas, etat);
   CREATE INDEX idx_reservation_emp_dates ON reservation(id_emplacement, date_debut, date_fin);
   CREATE INDEX idx_res_user_date ON reservation(id_user, date_debut);
   CREATE INDEX idx_res_statut_date ON reservation(statut, date_debut);
   CREATE INDEX idx_res_dates ON reservation(date_debut, date_fin);
   CREATE INDEX idx_session_emplacement ON charging_session(id_emplacement);
   CREATE INDEX idx_session_start ON charging_session(start_time);
   CREATE INDEX idx_session_end ON charging_session(end_time);
   CREATE INDEX idx_session_window ON charging_session(start_time, end_time);
   CREATE INDEX idx_telemetry_time ON session_telemetry(id_session, timestamp);
   CREATE INDEX idx_session_tel_ts ON session_telemetry(timestamp DESC);
   CREATE INDEX idx_device_last_seen ON device(last_seen);
   CREATE INDEX idx_device_status_seen ON device(status, last_seen);
   CREATE INDEX idx_capteur_type_dev ON capteur(type, id_device);
   CREATE INDEX idx_capteur_data_time ON capteur_data(id_capteur, timestamp);
   CREATE INDEX idx_capteur_data_ts ON capteur_data(timestamp DESC);
   CREATE INDEX idx_alert_status_time ON alerte(status, date);
   CREATE INDEX idx_alert_session_time ON alerte(id_session, date);
   CREATE INDEX idx_alert_ts ON alerte(date DESC);
   CREATE INDEX idx_alert_sev_time ON alerte(niveau_severite, date);
   CREATE INDEX idx_alert_type_time ON alerte(type, date);
   CREATE INDEX idx_maint_tech_date ON maintenance(id_technicien, date_planifiee);
   CREATE INDEX idx_maint_station_date ON maintenance(id_station, date_planifiee);
   CREATE INDEX idx_maint_status_date ON maintenance(status, date_planifiee);

   CREATE OR REPLACE VIEW session_anonyme AS
   SELECT
       cs.id_session,
       cs.start_time AS date_debut,
       cs.end_time AS date_fin,
       COALESCE(MAX(st.energie_kwh), 0)::double precision AS consommation_kwh,
       md5(COALESCE(r.id_user::text, cs.id_session::text)) AS user_hash
   FROM charging_session cs
   JOIN reservation r ON r.id_reservation = cs.id_reservation
   LEFT JOIN session_telemetry st ON st.id_session = cs.id_session
   GROUP BY cs.id_session, cs.start_time, cs.end_time, r.id_user;

Dictionnaire de données
-----------------------

``utilisateur``
~~~~~~~~~~~~~~~

Compte applicatif utilisé pour l’authentification, le portail utilisateur,
l’administration et le lien éventuel avec un technicien.

* ``id_user`` : UUID primaire. Exemple : ``7df7f18e-7b75-4c2f-93bc-4f6d2f4eab15``.
* ``pseudo`` : identifiant de connexion unique. Exemple : ``sarah.martin``.
* ``email`` : adresse email unique. Exemple : ``sarah.martin@example.com``.
* ``password`` : mot de passe haché par Django, jamais stocké en clair.
* ``statut`` : état fonctionnel du compte. Valeurs attendues :
  ``actif``, ``suspendu``, ``archive``.
* ``created_at`` : date de création métier du compte.
* ``last_login`` : dernière connexion connue, optionnelle.
* ``failed_attempts`` : compteur d’échecs d’authentification.
* ``is_active`` : booléen Django autorisant ou bloquant la connexion.
* ``is_staff`` : accès à l’administration Django.
* ``is_superuser`` : droits administrateur complets.
* ``date_joined`` : date d’inscription Django.

``profil_utilisateur``
~~~~~~~~~~~~~~~~~~~~~~

Extension personnelle du compte. La séparation avec ``utilisateur`` facilite les
traitements RGPD et les évolutions du profil.

* ``id_profil`` : UUID primaire.
* ``id_user`` : lien unique vers ``utilisateur``.
* ``nom`` : nom affiché dans l’interface. Exemple : ``Sarah Martin``.
* ``telephone`` : numéro de contact. Exemple : ``+33601020304``.

``role``
~~~~~~~~

Catalogue des rôles fonctionnels attribuables aux utilisateurs.

* ``id_role`` : UUID primaire.
* ``nom`` : rôle unique. Valeurs attendues : ``client``, ``technicien``,
  ``administrateur``.
* ``description`` : finalité du rôle. Exemple : ``Accès aux interventions``.

``utilisateur_role``
~~~~~~~~~~~~~~~~~~~~

Table d’association entre comptes et rôles.

* ``id_user`` : utilisateur concerné.
* ``id_role`` : rôle attribué.
* ``assigned_at`` : date d’attribution.

``consentement``
~~~~~~~~~~~~~~~~

Historise les décisions utilisateur sur les traitements de données.

* ``id_consentement`` : UUID primaire.
* ``id_user`` : utilisateur concerné.
* ``type`` : nature du consentement. Valeurs attendues : ``cgu``,
  ``politique_confidentialite``, ``notifications``, ``mesure_audience``.
* ``statut`` : décision. Valeurs attendues : ``accepte``, ``refuse``,
  ``retire``.
* ``date_consentement`` : date de décision.

Cette table est utile si elle est exploitée comme preuve de choix utilisateur.
Elle ne remplace pas les autres bases légales RGPD : la création de compte, la
réservation, la facturation ou la sécurité peuvent relever du contrat, de
l’intérêt légitime ou d’une obligation légale. Le consentement doit être réservé
aux traitements optionnels, par exemple les notifications non indispensables ou
les mesures d’audience.

Dans l’application actuelle, ``consentement`` est modélisée, visible dans
l’administration Django, exportée dans les données personnelles du compte et
alimentée automatiquement à l’inscription. Le formulaire collecte les choix
RGPD explicites et l’API crée une ligne historisée par décision :

* ``cgu/accepte`` pour les conditions générales d’utilisation ;
* ``politique_confidentialite/accepte`` pour la prise de connaissance de
  l’information RGPD ;
* ``notifications/accepte`` ou ``notifications/refuse`` pour les communications
  optionnelles liées au service.

Le profil utilisateur permet ensuite de modifier le choix lié aux notifications.
Chaque changement ajoute une nouvelle ligne datée, par exemple
``notifications/refuse`` après une acceptation initiale. Cette approche conserve
la preuve datée de chaque décision.

``journal_securite``
~~~~~~~~~~~~~~~~~~~~

Journal d’audit des actions sensibles.

* ``id_log`` : UUID primaire.
* ``id_user`` : utilisateur associé, conservé à ``NULL`` si le compte disparaît.
* ``action`` : action tracée. Exemple : ``login:success`` ou
  ``rfid:revoked``.
* ``ip`` : adresse IP source. Exemple : ``192.168.1.25``.
* ``statut`` : résultat. Valeurs attendues : ``success``, ``failure``.
* ``date_action`` : horodatage de l’événement.

``type_auth``
~~~~~~~~~~~~~

Catalogue des moyens d’authentification.

* ``id_type`` : UUID primaire.
* ``libelle`` : libellé unique. Valeurs attendues : ``RFID``, ``qr``,
  ``code``.
* ``factor_level`` : niveau d’assurance. Exemple : ``1`` pour RFID,
  ``2`` pour code temporaire.

``auth_method``
~~~~~~~~~~~~~~~

Moyen d’authentification lié à un utilisateur. Les secrets sont hachés.

* ``id_auth`` : UUID primaire.
* ``id_user`` : propriétaire du moyen d’accès.
* ``id_type`` : type d’authentification.
* ``secret_hash`` : secret haché. Exemple : hash du badge RFID ou du token QR.
* ``display_value`` : valeur affichable lorsque le parcours l’autorise, par
  exemple un code temporaire.
* ``metadata`` : métadonnées JSON. Exemple : ``{"reservation_code": "A1B2C3"}``.
* ``expiration`` : date de fin de validité, surtout pour QR/code temporaire.
* ``is_active`` : moyen actif ou révoqué.
* ``created_at`` : date de création.

``station``
~~~~~~~~~~~

Site physique de recharge.

* ``id_station`` : UUID primaire.
* ``nom`` : nom public. Exemple : ``Station Centre Ville``.
* ``localisation`` : adresse ou description. Exemple : ``12 rue de Paris``.
* ``latitude`` : coordonnée GPS optionnelle. Exemple : ``48.8566``.
* ``longitude`` : coordonnée GPS optionnelle. Exemple : ``2.3522``.
* ``statut`` : état du site. Valeurs attendues : ``active``,
  ``maintenance``, ``hors_service``.
* ``created_at`` : date d’enregistrement.

``emplacement``
~~~~~~~~~~~~~~~

Point de charge numéroté dans une station.

* ``id_emplacement`` : UUID primaire.
* ``id_station`` : station parente.
* ``numero`` : numéro visible sur site. Exemple : ``1``.
* ``etat`` : disponibilité opérationnelle. Valeurs attendues :
  ``disponible``, ``reserve``, ``occupe``, ``maintenance``, ``hors_service``.
* ``statut_cadenas`` : état du verrou. Valeurs attendues : ``verrouille``,
  ``deverrouille``, ``inconnu``.

``device``
~~~~~~~~~~

Équipement embarqué associé à un emplacement, typiquement un ESP32.

* ``id_device`` : UUID primaire.
* ``id_emplacement`` : emplacement équipé, unique.
* ``type_device`` : type matériel. Exemple : ``ESP32``.
* ``firmware_version`` : version embarquée. Exemple : ``1.2.0``.
* ``ip_address`` : adresse IP locale si disponible. Exemple : ``192.168.1.42``.
* ``mac_address`` : adresse MAC ou identifiant matériel. Exemple :
  ``AA:BB:CC:DD:EE:FF``.
* ``last_seen`` : dernière télémétrie reçue.
* ``status`` : état remonté. Valeurs observées : ``online``, ``offline``,
  ``charging``.

``capteur``
~~~~~~~~~~~

Capteur logique exposé par un device.

* ``id_capteur`` : UUID primaire.
* ``id_device`` : device porteur.
* ``type`` : type de mesure. Valeurs attendues : ``temperature``,
  ``door``, ``cable``, ``current``, ``voltage``.
* ``unite`` : unité de mesure. Exemples : ``C``, ``bool``, ``A``, ``V``.

``capteur_data``
~~~~~~~~~~~~~~~~

Mesure brute produite par un capteur.

* ``id_data`` : UUID primaire.
* ``id_capteur`` : capteur source.
* ``valeur`` : valeur numérique. Exemple : ``1`` pour ``door`` ouvert,
  ``0`` pour fermé, ``31.7`` pour une température.
* ``timestamp`` : date de réception de la mesure.

``reservation``
~~~~~~~~~~~~~~~

Réservation d’un emplacement sur un créneau donné.

* ``id_reservation`` : UUID primaire.
* ``reference_code`` : code court unique affiché à l’utilisateur. Exemple :
  ``R7K2Q9``.
* ``id_user`` : utilisateur demandeur, nullable pour conserver l'historique
  après suppression ou anonymisation.
* ``id_emplacement`` : emplacement réservé.
* ``id_auth`` : moyen d’accès associé, nullable si le moyen est révoqué.
* ``auth_choice`` : mode choisi. Valeurs fermées côté API : ``rfid``, ``qr``,
  ``code``.
* ``date_debut`` : début du créneau.
* ``date_fin`` : fin du créneau, strictement après ``date_debut``.
* ``statut`` : cycle de vie. Valeurs observées : ``confirmee``, ``active``,
  ``annulee``, ``terminee``, ``expiree``.

``charging_session``
~~~~~~~~~~~~~~~~~~~~

Session de charge effective ouverte à partir d’une réservation.

* ``id_session`` : UUID primaire.
* ``id_reservation`` : réservation source, unique.
* ``id_emplacement`` : emplacement utilisé.
* ``start_time`` : début réel de charge.
* ``end_time`` : fin réelle de charge, ``NULL`` tant que la session est active.

``session_telemetry``
~~~~~~~~~~~~~~~~~~~~~

Télémétrie électrique associée à une session.

* ``id_telemetry`` : UUID primaire.
* ``id_session`` : session concernée.
* ``courant`` : intensité en ampères. Exemple : ``12.4``.
* ``tension`` : tension en volts. Exemple : ``230.0``.
* ``energie_kwh`` : énergie cumulée. Exemple : ``4.72``.
* ``timestamp`` : date de mesure.

``alerte``
~~~~~~~~~~

Incident opérationnel issu d’une mesure capteur ou d’une session.

* ``id_alerte`` : UUID primaire.
* ``id_data`` : mesure source si l’alerte vient d’un capteur.
* ``id_session`` : session concernée si l’alerte est liée à une charge.
* ``type`` : famille d’alerte. Valeurs observées : ``intrusion``,
  ``cable_removed``.
* ``message`` : message lisible. Exemple : ``Cable retire pendant une charge active.``.
* ``niveau_severite`` : priorité. Valeurs observées : ``critique``,
  ``haute``, ``critical``.
* ``status`` : cycle de vie. Valeurs observées : ``nouvelle``, ``active``,
  ``resolue``, ``closed``, ``fermee``.
* ``date`` : date de création ou de dernière mise à jour.

``technicien``
~~~~~~~~~~~~~~

Profil opérationnel d’un intervenant de maintenance.

* ``id_tech`` : UUID primaire.
* ``id_user`` : compte applicatif associé, optionnel.
* ``nom`` : nom de l’intervenant. Exemple : ``Nadia Leroy``.
* ``email`` : email professionnel unique.
* ``telephone`` : numéro de contact.

``maintenance``
~~~~~~~~~~~~~~~

Intervention planifiée ou réalisée sur une station.

* ``id_maintenance`` : UUID primaire.
* ``id_station`` : station concernée.
* ``id_technicien`` : technicien assigné.
* ``type`` : nature de l’intervention. Valeurs attendues : ``preventive``,
  ``corrective``, ``diagnostic``.
* ``description`` : détail de l’intervention.
* ``status`` : avancement. Valeurs attendues : ``planifiee``, ``en_cours``,
  ``realisee``, ``annulee``.
* ``date_planifiee`` : date prévue.
* ``date_realisee`` : date effective, optionnelle tant que l'intervention n'est
  pas terminée.

Vue ``session_anonyme``
~~~~~~~~~~~~~~~~~~~~~~~

Vue d’exploitation statistique sans identifiant utilisateur direct.

* ``id_session`` : session analysée.
* ``date_debut`` : début réel de session.
* ``date_fin`` : fin réelle, optionnelle.
* ``consommation_kwh`` : consommation estimée depuis la télémétrie.
* ``user_hash`` : hachage stable de l’utilisateur, ou valeur de repli si le lien
  utilisateur n’existe plus.

Lecture fonctionnelle
---------------------

Le MCD privilégie une séparation nette entre la réservation et la session. Une
réservation représente un droit d’accès planifié ; une session représente
l’usage réel du point de charge. Cette distinction permet de gérer les
annulations, les absences, les démarrages tardifs et les sessions encore
ouvertes.

Les mesures capteurs sont conservées indépendamment des alertes. Une alerte peut
donc pointer vers la mesure qui l’a déclenchée, tout en portant son propre cycle
de vie. Cela évite de transformer chaque mesure anormale en incident distinct :
une anomalie persistante peut faire évoluer une alerte existante de ``nouvelle``
vers ``active``, puis ``resolue`` lorsque la télémétrie revient à la normale.

Les moyens d’authentification sont séparés des réservations afin de prendre en
charge plusieurs modes d’accès : RFID durable, QR code temporaire et code court.
Le secret reste haché ; la valeur affichable est limitée aux parcours où elle est
nécessaire à l’utilisateur.
