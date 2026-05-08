MCD PostgreSQL
===============

Cette page presente le modele conceptuel et relationnel cible de la base de
donnees. Elle sert de reference pour expliquer les tables, leurs responsabilites,
les champs stockes et les valeurs attendues dans le cadre de l'exploitation
d'une station de recharge securisee.

Le schema est aligne avec le modele Django actuel. Les tables techniques ajoutees
par Django pour les groupes et permissions ne sont pas detaillees ici : elles
font partie du socle d'administration Django, pas du domaine metier de la
station.

Principes de modelisation
-------------------------

La base est organisee autour de cinq ensembles fonctionnels :

* **comptes et securite** : utilisateurs, profils, roles, moyens
  d'authentification, consentements et journal de securite ;
* **infrastructure terrain** : stations, emplacements de charge, devices ESP32
  et capteurs ;
* **reservation et session** : reservation utilisateur, authentification choisie
  et session de charge effective ;
* **telemetrie et alertes** : mesures capteurs, mesures electriques et alertes
  operationnelles ;
* **maintenance** : techniciens et interventions planifiees.

Les valeurs textuelles comme ``statut``, ``status`` ou ``type`` restent des
chaines dans la base. Cela garde de la souplesse pour l'API et les simulations.
Les valeurs indiquees ci-dessous sont donc les valeurs fonctionnelles attendues,
pas toujours des contraintes SQL strictes.

Diagramme Mermaid
-----------------

Le bloc suivant est un diagramme Mermaid. Il peut etre colle tel quel dans un
visualiseur Mermaid ou dans un outil compatible pour obtenir le diagramme ER.

.. mermaid::

   erDiagram
       utilisateur ||--o| profil_utilisateur : possede
       utilisateur ||--o{ utilisateur_role : recoit
       role ||--o{ utilisateur_role : definit
       utilisateur ||--o{ consentement : donne
       utilisateur ||--o{ journal_securite : declenche
       utilisateur ||--o{ auth_method : possede
       type_auth ||--o{ auth_method : classe
       utilisateur ||--o{ reservation : reserve
       auth_method ||--o{ reservation : securise
       station ||--o{ emplacement : contient
       emplacement ||--o| device : equipe
       device ||--o{ capteur : mesure
       capteur ||--o{ capteur_data : produit
       emplacement ||--o{ reservation : concerne
       reservation ||--o| charging_session : ouvre
       emplacement ||--o{ charging_session : accueille
       charging_session ||--o{ session_telemetry : mesure
       charging_session ||--o{ alerte : genere
       capteur_data ||--o{ alerte : explique
       utilisateur ||--o| technicien : peut_etre
       station ||--o{ maintenance : necessite
       technicien ||--o{ maintenance : realise

Script de creation PostgreSQL
-----------------------------

Ce script de creation represente le schema metier attendu sur PostgreSQL. Dans
le projet, les migrations Django restent la source operationnelle pour creer et
faire evoluer la base.

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

Dictionnaire de donnees
-----------------------

``utilisateur``
~~~~~~~~~~~~~~~

Compte applicatif utilise pour l'authentification, le portail utilisateur,
l'administration et le lien eventuel avec un technicien.

* ``id_user`` : UUID primaire. Exemple : ``7df7f18e-7b75-4c2f-93bc-4f6d2f4eab15``.
* ``pseudo`` : identifiant de connexion unique. Exemple : ``sarah.martin``.
* ``email`` : adresse email unique. Exemple : ``sarah.martin@example.com``.
* ``password`` : mot de passe hache par Django, jamais stocke en clair.
* ``statut`` : etat fonctionnel du compte. Valeurs attendues :
  ``actif``, ``suspendu``, ``archive``.
* ``created_at`` : date de creation metier du compte.
* ``last_login`` : derniere connexion connue, optionnelle.
* ``failed_attempts`` : compteur d'echecs d'authentification.
* ``is_active`` : booleen Django autorisant ou bloquant la connexion.
* ``is_staff`` : acces a l'administration Django.
* ``is_superuser`` : droits administrateur complets.
* ``date_joined`` : date d'inscription Django.

``profil_utilisateur``
~~~~~~~~~~~~~~~~~~~~~~

Extension personnelle du compte. La separation avec ``utilisateur`` facilite les
traitements RGPD et les evolutions du profil.

* ``id_profil`` : UUID primaire.
* ``id_user`` : lien unique vers ``utilisateur``.
* ``nom`` : nom affiche dans l'interface. Exemple : ``Sarah Martin``.
* ``telephone`` : numero de contact. Exemple : ``+33601020304``.

``role``
~~~~~~~~

Catalogue des roles fonctionnels attribuables aux utilisateurs.

* ``id_role`` : UUID primaire.
* ``nom`` : role unique. Valeurs attendues : ``client``, ``technicien``,
  ``administrateur``.
* ``description`` : finalite du role. Exemple : ``Acces aux interventions``.

``utilisateur_role``
~~~~~~~~~~~~~~~~~~~~

Table d'association entre comptes et roles.

* ``id_user`` : utilisateur concerne.
* ``id_role`` : role attribue.
* ``assigned_at`` : date d'attribution.

``consentement``
~~~~~~~~~~~~~~~~

Historise les decisions utilisateur sur les traitements de donnees.

* ``id_consentement`` : UUID primaire.
* ``id_user`` : utilisateur concerne.
* ``type`` : nature du consentement. Valeurs attendues : ``cgu``,
  ``donnees_personnelles``, ``notifications``.
* ``statut`` : decision. Valeurs attendues : ``accepte``, ``refuse``,
  ``retire``.
* ``date_consentement`` : date de decision.

``journal_securite``
~~~~~~~~~~~~~~~~~~~~

Journal d'audit des actions sensibles.

* ``id_log`` : UUID primaire.
* ``id_user`` : utilisateur associe, conserve a ``NULL`` si le compte disparait.
* ``action`` : action tracee. Exemple : ``login:success`` ou
  ``rfid:revoked``.
* ``ip`` : adresse IP source. Exemple : ``192.168.1.25``.
* ``statut`` : resultat. Valeurs attendues : ``success``, ``failure``.
* ``date_action`` : horodatage de l'evenement.

``type_auth``
~~~~~~~~~~~~~

Catalogue des moyens d'authentification.

* ``id_type`` : UUID primaire.
* ``libelle`` : libelle unique. Valeurs attendues : ``RFID``, ``qr``,
  ``code``.
* ``factor_level`` : niveau d'assurance. Exemple : ``1`` pour RFID,
  ``2`` pour code temporaire.

``auth_method``
~~~~~~~~~~~~~~~

Moyen d'authentification lie a un utilisateur. Les secrets sont haches.

* ``id_auth`` : UUID primaire.
* ``id_user`` : proprietaire du moyen d'acces.
* ``id_type`` : type d'authentification.
* ``secret_hash`` : secret hache. Exemple : hash du badge RFID ou du token QR.
* ``display_value`` : valeur affichable lorsque le parcours l'autorise, par
  exemple un code temporaire.
* ``metadata`` : metadonnees JSON. Exemple : ``{"reservation_code": "A1B2C3"}``.
* ``expiration`` : date de fin de validite, surtout pour QR/code temporaire.
* ``is_active`` : moyen actif ou revoque.
* ``created_at`` : date de creation.

``station``
~~~~~~~~~~~

Site physique de recharge.

* ``id_station`` : UUID primaire.
* ``nom`` : nom public. Exemple : ``Station Centre Ville``.
* ``localisation`` : adresse ou description. Exemple : ``12 rue de Paris``.
* ``latitude`` : coordonnee GPS optionnelle. Exemple : ``48.8566``.
* ``longitude`` : coordonnee GPS optionnelle. Exemple : ``2.3522``.
* ``statut`` : etat du site. Valeurs attendues : ``active``,
  ``maintenance``, ``hors_service``.
* ``created_at`` : date d'enregistrement.

``emplacement``
~~~~~~~~~~~~~~~

Point de charge numerote dans une station.

* ``id_emplacement`` : UUID primaire.
* ``id_station`` : station parente.
* ``numero`` : numero visible sur site. Exemple : ``1``.
* ``etat`` : disponibilite operationnelle. Valeurs attendues :
  ``disponible``, ``reserve``, ``occupe``, ``maintenance``, ``hors_service``.
* ``statut_cadenas`` : etat du verrou. Valeurs attendues : ``verrouille``,
  ``deverrouille``, ``inconnu``.

``device``
~~~~~~~~~~

Equipement embarque associe a un emplacement, typiquement un ESP32.

* ``id_device`` : UUID primaire.
* ``id_emplacement`` : emplacement equipe, unique.
* ``type_device`` : type materiel. Exemple : ``ESP32``.
* ``firmware_version`` : version embarquee. Exemple : ``1.2.0``.
* ``ip_address`` : adresse IP locale si disponible. Exemple : ``192.168.1.42``.
* ``mac_address`` : adresse MAC ou identifiant materiel. Exemple :
  ``AA:BB:CC:DD:EE:FF``.
* ``last_seen`` : derniere telemetrie recue.
* ``status`` : etat remonte. Valeurs observees : ``online``, ``offline``,
  ``charging``.

``capteur``
~~~~~~~~~~~

Capteur logique expose par un device.

* ``id_capteur`` : UUID primaire.
* ``id_device`` : device porteur.
* ``type`` : type de mesure. Valeurs attendues : ``temperature``,
  ``door``, ``cable``, ``current``, ``voltage``.
* ``unite`` : unite de mesure. Exemples : ``C``, ``bool``, ``A``, ``V``.

``capteur_data``
~~~~~~~~~~~~~~~~

Mesure brute produite par un capteur.

* ``id_data`` : UUID primaire.
* ``id_capteur`` : capteur source.
* ``valeur`` : valeur numerique. Exemple : ``1`` pour ``door`` ouvert,
  ``0`` pour ferme, ``31.7`` pour une temperature.
* ``timestamp`` : date de reception de la mesure.

``reservation``
~~~~~~~~~~~~~~~

Reservation d'un emplacement sur un creneau donne.

* ``id_reservation`` : UUID primaire.
* ``reference_code`` : code court unique affiche a l'utilisateur. Exemple :
  ``R7K2Q9``.
* ``id_user`` : utilisateur demandeur, nullable pour conserver l'historique
  apres suppression ou anonymisation.
* ``id_emplacement`` : emplacement reserve.
* ``id_auth`` : moyen d'acces associe, nullable si le moyen est revoque.
* ``auth_choice`` : mode choisi. Valeurs fermees cote API : ``rfid``, ``qr``,
  ``code``.
* ``date_debut`` : debut du creneau.
* ``date_fin`` : fin du creneau, strictement apres ``date_debut``.
* ``statut`` : cycle de vie. Valeurs observees : ``confirmee``, ``active``,
  ``annulee``, ``terminee``, ``expiree``.

``charging_session``
~~~~~~~~~~~~~~~~~~~~

Session de charge effective ouverte a partir d'une reservation.

* ``id_session`` : UUID primaire.
* ``id_reservation`` : reservation source, unique.
* ``id_emplacement`` : emplacement utilise.
* ``start_time`` : debut reel de charge.
* ``end_time`` : fin reelle de charge, ``NULL`` tant que la session est active.

``session_telemetry``
~~~~~~~~~~~~~~~~~~~~~

Telemetrie electrique associee a une session.

* ``id_telemetry`` : UUID primaire.
* ``id_session`` : session concernee.
* ``courant`` : intensite en amperes. Exemple : ``12.4``.
* ``tension`` : tension en volts. Exemple : ``230.0``.
* ``energie_kwh`` : energie cumulee. Exemple : ``4.72``.
* ``timestamp`` : date de mesure.

``alerte``
~~~~~~~~~~

Incident operationnel issu d'une mesure capteur ou d'une session.

* ``id_alerte`` : UUID primaire.
* ``id_data`` : mesure source si l'alerte vient d'un capteur.
* ``id_session`` : session concernee si l'alerte est liee a une charge.
* ``type`` : famille d'alerte. Valeurs observees : ``intrusion``,
  ``cable_removed``.
* ``message`` : message lisible. Exemple : ``Cable retire pendant une charge active.``.
* ``niveau_severite`` : priorite. Valeurs observees : ``critique``,
  ``haute``, ``critical``.
* ``status`` : cycle de vie. Valeurs observees : ``nouvelle``, ``active``,
  ``resolue``, ``closed``, ``fermee``.
* ``date`` : date de creation ou de derniere mise a jour.

``technicien``
~~~~~~~~~~~~~~

Profil operationnel d'un intervenant de maintenance.

* ``id_tech`` : UUID primaire.
* ``id_user`` : compte applicatif associe, optionnel.
* ``nom`` : nom de l'intervenant. Exemple : ``Nadia Leroy``.
* ``email`` : email professionnel unique.
* ``telephone`` : numero de contact.

``maintenance``
~~~~~~~~~~~~~~~

Intervention planifiee ou realisee sur une station.

* ``id_maintenance`` : UUID primaire.
* ``id_station`` : station concernee.
* ``id_technicien`` : technicien assigne.
* ``type`` : nature de l'intervention. Valeurs attendues : ``preventive``,
  ``corrective``, ``diagnostic``.
* ``description`` : detail de l'intervention.
* ``status`` : avancement. Valeurs attendues : ``planifiee``, ``en_cours``,
  ``realisee``, ``annulee``.
* ``date_planifiee`` : date prevue.
* ``date_realisee`` : date effective, optionnelle tant que l'intervention n'est
  pas terminee.

Vue ``session_anonyme``
~~~~~~~~~~~~~~~~~~~~~~~

Vue d'exploitation statistique sans identifiant utilisateur direct.

* ``id_session`` : session analysee.
* ``date_debut`` : debut reel de session.
* ``date_fin`` : fin reelle, optionnelle.
* ``consommation_kwh`` : consommation estimee depuis la telemetrie.
* ``user_hash`` : hachage stable de l'utilisateur, ou valeur de repli si le lien
  utilisateur n'existe plus.

Lecture fonctionnelle
---------------------

Le MCD privilegie une separation nette entre la reservation et la session. Une
reservation represente un droit d'acces planifie ; une session represente
l'usage reel du point de charge. Cette distinction permet de gerer les annulations,
les absences, les demarrages tardifs et les sessions encore ouvertes.

Les mesures capteurs sont conservees independamment des alertes. Une alerte peut
donc pointer vers la mesure qui l'a declenchee, tout en portant son propre cycle
de vie. Cela evite de transformer chaque mesure anormale en incident distinct :
une anomalie persistante peut faire evoluer une alerte existante de ``nouvelle``
vers ``active``, puis ``resolue`` lorsque la telemetrie revient a la normale.

Les moyens d'authentification sont separes des reservations afin de prendre en
charge plusieurs modes d'acces : RFID durable, QR code temporaire et code court.
Le secret reste hache ; la valeur affichable est limitee aux parcours ou elle est
necessaire a l'utilisateur.
