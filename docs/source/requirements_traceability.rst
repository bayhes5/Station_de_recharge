Traçabilité du cahier des charges
=================================

Cette page relie les exigences fonctionnelles aux composants de la solution. Elle
formalise la couverture actuelle, les choix techniques retenus et les points à
finaliser avant une exploitation complète.

Sources contractuelles analysées
--------------------------------

La traçabilité ci-dessous s'appuie sur les documents de cadrage fournis au début
du projet :

* ``Fiche présentation Station de recharge intelligente.pdf`` ;
* ``Station de recharge intelligente_BAYOU_Said.pdf`` ;
* ``Station de recharge intelligente_ROTA Celian.pdf`` ;
* ``Station de recharge intelligente_CANDIDAT03.pdf`` ;
* ``UML_Diagrammes_Cas_Utilisation.pdf``.

Ces documents fixent une station de recharge intelligente pour vélos
électriques, automatisée, connectée et sécurisée. Le système cible associe un
site web de réservation, une borne tactile Raspberry Pi, des emplacements
pilotés par ESP32 et une supervision locale.

Le diagramme de cas d'utilisation est utilisé comme support de validation des
parcours principaux. Il n'est pas repris en détail ici afin de garder cette page
centrée sur la conformité fonctionnelle.

Contexte fonctionnel
--------------------

La solution doit permettre :

* la réservation en ligne d'un emplacement de recharge ;
* l'identification sécurisée par QR code, badge RFID ou code SMS temporaire ;
* la gestion en temps réel des ports de charge et des disponibilités ;
* le suivi énergétique et la remontée d'alertes ;
* l'archivage des usages et statistiques ;
* la supervision distante ;
* la sécurisation physique par serrure électromagnétique pilotée.

Répartition initiale par partie
-------------------------------

.. list-table::
   :header-rows: 1
   :widths: 24 38 38

   * - Partie
     - Responsabilités demandées
     - Critères de réussite attendus
   * - Partie 1 : web, base de données et supervision
     - Site web responsive, gestion des utilisateurs, réservations, base de
       données sécurisée, statistiques, historique et supervision locale.
     - Base cohérente, accès aux données fonctionnel, historique visible,
       destinataires d'alertes présents et sécurité web/base de données assurée.
   * - Partie 2 : Raspberry et interface de borne
     - IHM tactile locale, identification sur site, vérification par code SMS,
       QR code et badge RFID, puis validation de l'ordre d'ouverture.
     - IHM opérationnelle, communication avec la base, concordance
       code/réservation et QR/réservation, ordre serrure validé après contrôle.
   * - Partie 3 : ESP32 et emplacements
     - Pilotage serrure et port de charge, mesure température/courant/tension,
       détection intrusion, câble branché et état du boîtier.
     - Boîtier opérationnel, mesures remontées au superviseur et alarmes
       correctement transmises.

Couverture par partie
---------------------

.. list-table::
   :header-rows: 1
   :widths: 24 38 38

   * - Exigence
     - Couverture actuelle
     - Éléments à finaliser
   * - Site web responsive
     - Frontend Vite multi-pages, pages inscription, connexion, réservation,
       dashboard utilisateur et vues administrateur.
     - Améliorer progressivement l'ergonomie et tester les parcours sur mobile.
   * - Gestion utilisateurs et RGPD
     - Modèle utilisateur Django, profil, JWT, refresh token ``HttpOnly``,
       export de compte, anonymisation de compte, politique de rétention et
       séparation des rôles.
     - Valider juridiquement les durées de conservation définitives avec le
       contexte réel d'exploitation.
   * - Réservation en ligne
     - API de réservation, sélection station/créneau, attribution automatique
       d'un emplacement disponible.
     - Ajouter rapports statistiques plus complets.
   * - QR/code SMS/RFID
     - QR et codes SMS temporaires liés à une réservation, badge RFID persistant lié
       au compte, association via code court et borne.
     - Brancher les vrais lecteurs QR/RFID sur le Raspberry.
   * - Interface locale Raspberry
     - Kiosque web local, parcours QR/code SMS/RFID, écran tactile cible
       ``1024x600``, relais local des commandes validées.
     - Test physique sur l'écran 7 pouces, intégration lecteur réel et cache
       local des autorisations en mode dégradé.
   * - Validation station/emplacement
     - Le terminal vérifie réservation active, moyen d'accès et station attendue.
     - Ajouter retours utilisateur détaillés pour mauvais emplacement.
   * - Serrure et charge
     - Commande ``UNLOCK`` envoyée après authentification réussie, puis
       ``START`` automatique après détection du câble. Firmware ESP32 pilote la
       serrure par relais GPIO26 ; le relais de charge reste à câbler.
     - Câbler le relais de charge réel et valider le cycle complet sous charge.
   * - Télémétrie
     - ESP32 publie température, humidité, courant, tension, énergie, porte,
       câble et état de l'emplacement. Le test matériel actuel couvre
       température/humidité DHT22, courant SEN0214, identité ESP32
       (firmware, adresse IP, adresse MAC) et état logique de serrure.
     - Brancher capteur de tension ou INA219, porte, câble et relais de charge,
       puis décider si un journal local ESP32 est nécessaire en complément du
       cache Raspberry.
   * - Alertes
     - Détection intrusion, câble retiré, surconsommation et surchauffe.
       Stockage dans ``Alerte`` avec cycle ``nouvelle`` -> ``active`` ->
       ``prise_en_charge`` -> ``resolue`` selon le retour à la normale ou
       l'intervention terrain.
     - Ajouter éventuellement un canal SMS technicien réel si le projet dépasse
       le périmètre académique gratuit.
   * - Supervision
     - Grafana provisionné, datasource TimescaleDB/PostgreSQL, dashboard
       technique initial, interface admin de supervision et simulateur de télémétrie
       local pour valider le flux sans ESP32 physique.
     - Ajouter des vues métier plus détaillées pour techniciens.
   * - Archivage
     - Sessions de charge, télémétrie de session, données capteurs et alertes
       stockées en base.
     - Ajouter politique de conservation et exports CSV métier.

Cas d'utilisation principaux
----------------------------

Réserver et démarrer une charge
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   Utilisateur
      -> réserve sur le site
      -> reçoit ou consulte QR/code SMS/badge
      -> s'identifie au kiosque Raspberry
      -> API valide réservation + moyen d'accès + station
      -> Raspberry publie UNLOCK vers l'emplacement
      -> ESP32 ouvre le boîtier
      -> utilisateur branche le câble
      -> ESP32 publie cable=true
      -> Raspberry publie START automatiquement vers l'emplacement
      -> ESP32 verrouille le boîtier et démarre la charge
      -> télémétrie envoyée au backend puis à Grafana

Supervision et alertes
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   ESP32
      -> publie température/humidité et identité du contrôleur
      -> le bridge d'ingestion traite le message
      -> Celery stocke les capteurs et crée/met à jour/résout les alertes
      -> Grafana affiche les mesures
      -> interface métier expose les alertes administrateur/technicien

Choix et écarts assumés
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Sujet
     - Demande initiale
     - Choix actuel
   * - QR code
     - QR code envoyé par mail et lu par un lecteur USB à la borne.
     - QR de réservation généré dès la réservation, visible dans l'espace
       utilisateur et envoyé par email via Mailpit en environnement académique.
       Ajout d'un QR de session mobile affiché par la borne pour permettre à la
       PWA de confirmer une réservation sans clavier physique.
   * - Code alphanumérique
     - Code envoyé par SMS et saisi au clavier.
     - Code SMS temporaire généré côté backend, stocké sans clair et saisi sur
       clavier tactile. La politique retient 8 caractères ``0-9/A-D`` pour
       rester compatible avec un clavier matriciel 4x4, avec verrouillage après
       5 mauvaises saisies.
   * - RFID
     - Badge RFID avec lecteur MFRC522 ou équivalent.
     - Lecteur ACR122U retenu. Le badge identifie l'utilisateur, puis le backend
       vérifie la réservation active et l'emplacement attendu.
   * - Topologie matérielle
     - Le contrat parle surtout de borne et d'emplacements.
     - Le modèle distingue ``Station > Borne > Emplacement`` pour représenter le
       matériel réel et préparer plusieurs bornes par station.
   * - Supervision
     - Interface web de supervision locale.
     - Deux niveaux : supervision métier dans l'application et supervision
       technique dans Grafana.
   * - Notifications
     - Email/SMS au technicien en cas d'alerte.
     - Politique d'alertes documentée ; Mailpit capture les emails QR et
       technicien, tandis que le mode SMS console/log permet une démonstration
       gratuite et open source.

Contraintes projet
------------------

* **Budget limité** : composants open source et matériel déjà disponible.
* **Modularité** : séparation frontend, backend, Raspberry, ESP32, messagerie IoT
  et supervision.
* **Sécurité** : mots de passe hashés, JWT, cookies ``HttpOnly``, journalisation
  des actions sensibles, source de vérité backend, préparation TLS/reverse proxy.
* **Continuité de service** : cache local limité côté Raspberry pour résister
  aux coupures temporaires sans déplacer l'autorité métier.
* **Qualité** : tests backend/frontend, documentation Sphinx, CI GitHub Actions,
  CodeQL et rapports supply chain.
* **Matériel imposé** : Raspberry Pi 4, écran 7 pouces ``1024x600``, ESP32,
  serrure électromagnétique, DHT22, capteur de courant SEN0214 et capteurs
  complémentaires à câbler.

État de maturité
----------------

La version logicielle couvre le parcours complet de réservation, validation
d'accès, commande MQTT, télémétrie et supervision. Les éléments actuellement
partiels ou non câblés sont clairement identifiés : relais de charge, porte,
câble, tension réelle et certains lecteurs physiques. Le test matériel actuel
couvre déjà la remontée DHT22, le courant SEN0214, l'identité ESP32 et la
commande de serrure par relais GPIO26. Le relais de charge, le contact de porte
et la détection câble restent à câbler.
