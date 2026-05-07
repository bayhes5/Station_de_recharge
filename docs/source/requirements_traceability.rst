Traçabilité du cahier des charges
=================================

Cette page relie les exigences du sujet aux composants du prototype. Elle sert à
montrer que les choix techniques couvrent bien les besoins demandés, et à
identifier les points encore à finaliser.

Contexte fonctionnel
--------------------

Le prototype doit permettre :

* la réservation en ligne d'un emplacement de recharge ;
* l'identification sécurisée par QR code, badge RFID ou code alphanumérique ;
* la gestion en temps réel des ports de charge et des disponibilités ;
* le suivi énergétique et la remontée d'alertes ;
* l'archivage des usages et statistiques ;
* la supervision distante ;
* la sécurisation physique par serrure électromagnétique pilotée.

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
       export de compte, séparation des rôles.
     - Compléter la suppression définitive/anonymisation selon le scénario RGPD
       retenu.
   * - Réservation en ligne
     - API de réservation, sélection station/créneau, attribution automatique
       d'un emplacement disponible.
     - Ajouter rapports statistiques plus complets.
   * - QR/code/RFID
     - QR et code temporaires liés à une réservation, badge RFID persistant lié
       au compte, association via code court et borne.
     - Brancher les vrais lecteurs QR/RFID sur le Raspberry.
   * - Interface locale Raspberry
     - Kiosque web local, parcours QR/code/RFID, écran tactile cible
       ``1024x600``.
     - Test physique sur l'écran 7 pouces et intégration lecteur réel.
   * - Validation station/emplacement
     - Le terminal vérifie réservation active, moyen d'accès et station attendue.
     - Ajouter retours utilisateur détaillés pour mauvais emplacement.
   * - Serrure et charge
     - Commande MQTT ``START`` envoyée au slot après authentification réussie.
       Firmware ESP32 simule verrouillage et charge.
     - Remplacer les sorties LED/simulation par relais et câblage physique.
   * - Télémétrie
     - ESP32 publie température, humidité, courant, tension, énergie, porte,
       câble et état du slot.
     - Brancher INA219 et capteurs réels dans le firmware.
   * - Alertes
     - Détection intrusion, câble retiré, surconsommation et surchauffe.
       Stockage dans ``Alerte`` avec cycle ``nouvelle`` -> ``active`` ->
       ``resolue`` selon le retour à la normale.
     - Ajouter notification email/SMS technicien et acquittement manuel si
       besoin métier.
   * - Supervision
     - Grafana provisionné, datasource TimescaleDB/PostgreSQL, dashboard
       technique initial, interface admin de supervision et simulateur MQTT
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
      -> reçoit ou consulte QR/code/badge
      -> s'identifie au kiosque Raspberry
      -> API valide réservation + moyen d'accès + station
      -> Raspberry publie START sur MQTT
      -> ESP32 ouvre/verrouille le boîtier et démarre la charge
      -> télémétrie envoyée au backend puis à Grafana

Supervision et alertes
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   ESP32
      -> publie température/courant/intrusion/câble
      -> mqtt-bridge ingère le message
      -> Celery stocke les capteurs et crée/met à jour/résout les alertes
      -> Grafana affiche les mesures
      -> interface métier expose les alertes administrateur/technicien

Contraintes projet
------------------

* **Budget limité** : composants open source et matériel déjà disponible.
* **Modularité** : séparation frontend, backend, Raspberry, ESP32, broker MQTT
  et supervision.
* **Sécurité** : mots de passe hashés, JWT, cookies ``HttpOnly``, journalisation
  des actions sensibles, préparation TLS/reverse proxy.
* **Qualité** : tests backend/frontend, documentation Sphinx, CI GitHub Actions,
  CodeQL et rapports supply chain.
* **Matériel imposé** : Raspberry Pi 4, écran 7 pouces ``1024x600``, ESP32,
  serrures électromagnétiques, capteurs DHT/Hall/contact/INA219.

État de maturité
----------------

Le prototype logiciel est structuré pour démontrer le parcours complet. Les
éléments actuellement simulés sont clairement identifiés : capteurs, charge,
serrure et lecteurs physiques. La simulation Wokwi permet de tester le flux de
télémétrie avant le câblage définitif.
