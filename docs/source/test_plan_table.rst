Plan de tests en tableau
========================

Cette page présente le plan de tests sous forme de tableau de recette. Elle
complète la :doc:`testing_strategy` en donnant une vue exploitable avant une
démonstration, une soutenance ou une évolution sensible du projet.

Légende
-------

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Terme
     - Signification
   * - Automatisé
     - Test exécuté par ``pytest``, Playwright, script Node ou CI.
   * - Manuel
     - Test réalisé à la main sur l'application, le kiosque, le smartphone ou le matériel.
   * - Simulation
     - Test réalisé avec données simulées, simulateur MQTT ou scénario Docker.
   * - OK
     - Test validé au moins une fois dans l'environnement de développement ou de démonstration.
   * - À valider matériel
     - Test préparé mais dépendant du câblage réel ou du matériel disponible.
   * - Régression
     - Test à relancer après chaque modification sensible.

Matrice globale de couverture
-----------------------------

.. list-table::
   :header-rows: 1
   :widths: 18 38 20 24

   * - Domaine
     - Objectif de test
     - Type principal
     - Preuve dans le projet
   * - Authentification
     - Vérifier inscription, connexion, JWT, refresh token et profil.
     - Automatisé
     - ``backend/api/tests/test_api_auth.py``, ``test_auth_profile.py``
   * - Réservations
     - Vérifier création, créneaux, conflits, états et archivage.
     - Automatisé
     - ``backend/api/tests/test_reservations.py``
   * - Accès terminal
     - Vérifier QR, RFID, SMS, session mobile et refus.
     - Automatisé + manuel
     - ``backend/api/tests/test_terminal_auth.py``
   * - Session mobile
     - Vérifier QR borne, choix réservation et consommation par le kiosque.
     - Automatisé + manuel
     - ``test_end_to_end_charge_flow.py``, ``frontend/js/mobile-session.js``
   * - Kiosque Raspberry
     - Vérifier interface tactile, RFID, cache offline et commandes MQTT.
     - Automatisé + manuel
     - ``raspberry/tests``, ``raspberry/app``
   * - ESP32
     - Vérifier serrure, télémétrie, courant, énergie et alertes locales.
     - Manuel + simulation
     - ``esp32/emplacement1/main.py``, Grafana
   * - MQTT
     - Vérifier topics, commandes, ACK, télémétrie et bridge.
     - Automatisé + simulation
     - ``test_mqtt_ingestion.py``, ``test_mqtt_security_config.py``
   * - Supervision
     - Vérifier dashboard admin, Grafana, alertes et exports.
     - Automatisé + manuel
     - ``test_admin_api.py``, ``test_grafana_provisioning.py``
   * - Sécurité
     - Vérifier rate limiting, secrets, cookies, Nginx, TLS et déploiement.
     - Automatisé + manuel
     - ``test_deployment_checks.py``, ``test_nginx_security_config.py``
   * - Production
     - Vérifier Docker, Nginx, sauvegarde, restauration et checks.
     - Automatisé + manuel
     - CI, ``docker-compose.prod.yml``, scripts backup/restore
   * - Frontend/PWA
     - Vérifier pages, navigation, accessibilité, build et E2E.
     - Automatisé + manuel
     - ``npm run verify``, Playwright

Tests fonctionnels principaux
-----------------------------

.. list-table::
   :header-rows: 1
   :widths: 12 22 24 26 30 16 12 22

   * - ID
     - Fonction testée
     - Préconditions
     - Étapes
     - Résultat attendu
     - Type
     - Statut
     - Preuve
   * - API-001
     - Inscription utilisateur
     - Backend démarré
     - Créer un compte avec pseudo, e-mail et mot de passe.
     - Compte créé, mot de passe non stocké en clair.
     - Automatisé
     - OK
     - ``test_api_auth.py``
   * - API-002
     - Connexion utilisateur
     - Compte existant
     - Envoyer identifiant et mot de passe.
     - Retour JWT access et cookie refresh.
     - Automatisé
     - OK
     - ``test_api_auth.py``
   * - RES-001
     - Création réservation valide
     - Utilisateur connecté, emplacement libre
     - Choisir station, créneau et moyen d'accès.
     - Réservation confirmée.
     - Automatisé
     - OK
     - ``test_reservations.py``
   * - RES-002
     - Conflit de réservation
     - Emplacement déjà réservé
     - Réserver un créneau chevauchant.
     - Refus avec message métier.
     - Automatisé
     - OK
     - ``test_reservations.py``
   * - RES-003
     - QR réservation
     - Réservation confirmée
     - Générer ou régénérer le QR.
     - QR lié à la réservation, révocable et testable.
     - Automatisé + manuel
     - OK
     - ``test_terminal_auth.py``
   * - KIO-001
     - Authentification QR
     - Réservation QR active
     - Présenter le payload QR au kiosque.
     - Accès autorisé si station, borne et créneau sont corrects.
     - Automatisé + manuel
     - OK
     - ``test_terminal_auth.py``
   * - KIO-002
     - Association RFID
     - Code d'association généré
     - Saisir le code au kiosque et badger.
     - UID associé au compte.
     - Manuel
     - OK
     - ``rfid_reader.py``, API terminal
   * - KIO-003
     - Session mobile QR borne
     - Smartphone connecté à la PWA
     - Scanner QR kiosque, choisir réservation.
     - Session autorisée puis consommée par le kiosque.
     - Automatisé + manuel
     - OK
     - ``test_end_to_end_charge_flow.py``

Tests charge, MQTT et supervision
---------------------------------

.. list-table::
   :header-rows: 1
   :widths: 12 22 24 26 30 16 14 22

   * - ID
     - Fonction testée
     - Préconditions
     - Étapes
     - Résultat attendu
     - Type
     - Statut
     - Preuve
   * - CHG-001
     - Déverrouillage après accès
     - Accès QR/RFID/SMS/mobile validé
     - Valider l'accès au kiosque.
     - Commande ``UNLOCK`` envoyée.
     - Manuel + simulation
     - OK
     - ``mqtt_commands.py``, ESP32
   * - CHG-002
     - Pas de charge au badge seul
     - Accès validé, pas de courant
     - Présenter badge sans activer générateur.
     - État ``waiting_plug``, pas ``charging``.
     - Manuel + logique
     - OK
     - ``charge_state.py``
   * - CHG-003
     - Démarrage sur courant détecté
     - Générateur activé
     - Détecter un courant suffisant.
     - Passage en ``charging``.
     - Manuel
     - À valider matériel
     - ``esp32/emplacement1/main.py``
   * - CHG-004
     - Re-fermeture si aucune charge
     - Serrure ouverte, pas de courant
     - Attendre le délai défini.
     - Serrure refermée et retour à l'état sûr.
     - Manuel
     - À valider matériel
     - Firmware ESP32/kiosque
   * - MQTT-001
     - ACK commande
     - Commande avec ``command_id``
     - ESP32 répond avec ACK.
     - Commande confirmée.
     - Automatisé + manuel
     - OK
     - ``test_mqtt_client.py``
   * - MQTT-002
     - Publication télémétrie
     - ESP32 ou simulateur actif
     - Publier température, humidité et courant.
     - Message reçu et stocké par le backend.
     - Automatisé + manuel
     - OK
     - ``test_mqtt_ingestion.py``
   * - SUP-001
     - Grafana par session
     - Session active ou simulée
     - Filtrer par station, borne, emplacement ou session.
     - Mesures liées à la session visibles.
     - Manuel
     - OK
     - ``station-supervision.json``
   * - SUP-002
     - Alertes courant/température
     - Télémétrie hors seuil
     - Publier une mesure anormale.
     - Alerte créée, sévérité visible.
     - Automatisé + manuel
     - OK
     - ``test_operational_alerts.py``

Tests sécurité, production et frontend
--------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 12 22 24 26 30 16 12 22

   * - ID
     - Fonction testée
     - Préconditions
     - Étapes
     - Résultat attendu
     - Type
     - Statut
     - Preuve
   * - SEC-001
     - Hash mots de passe
     - Utilisateur créé
     - Inspecter/authentifier.
     - Mot de passe jamais stocké en clair.
     - Automatisé + manuel
     - OK
     - Django auth
   * - SEC-002
     - Secret terminal
     - Terminal configuré
     - Appeler l'API terminal sans secret.
     - Requête refusée.
     - Automatisé
     - OK
     - ``test_terminal_auth.py``
   * - SEC-003
     - Rate limiting
     - Appels répétés
     - Multiplier erreurs login, SMS ou session.
     - Limitation appliquée.
     - Automatisé
     - OK
     - ``throttles.py``
   * - SEC-004
     - Nginx et TLS
     - Reverse proxy démarré
     - Vérifier la configuration.
     - En-têtes de sécurité et TLS configurés.
     - Automatisé + manuel
     - OK
     - ``test_nginx_security_config.py``, ``security/README.md``
   * - FE-001
     - Syntaxe JavaScript
     - Node installé
     - Lancer ``npm run check:js``.
     - Aucun fichier JavaScript invalide.
     - Automatisé
     - OK
     - ``check-js.mjs``
   * - FE-002
     - Accessibilité de base
     - Pages HTML présentes
     - Lancer ``npm run check:a11y``.
     - Titres, labels, ``main`` et viewport présents.
     - Automatisé
     - OK
     - ``check-accessibility.mjs``
   * - FE-003
     - Navigation utilisateur/admin/technicien
     - API simulée
     - Exécuter Playwright.
     - Parcours principaux navigables.
     - Automatisé
     - OK
     - ``frontend/tests/e2e/app.spec.js``

Recette démonstration
---------------------

.. list-table::
   :header-rows: 1
   :widths: 12 24 30 42 28 18 14

   * - ID
     - Scénario
     - Préconditions
     - Étapes résumées
     - Résultat attendu
     - Type
     - Statut
   * - DEMO-001
     - Réservation QR complète
     - Stack lancée, utilisateur démo
     - Réserver, scanner QR, ouvrir, détecter courant, arrêter.
     - Session complète visible backend/Grafana.
     - Manuel + script
     - OK
   * - DEMO-002
     - Session mobile kiosque
     - Smartphone connecté, QR kiosque
     - Scanner QR, choisir réservation, autoriser.
     - Kiosque ouvre l'emplacement.
     - Manuel
     - OK
   * - DEMO-003
     - RFID
     - Badge associé
     - Badger pendant un créneau valide.
     - Accès validé, serrure ouverte.
     - Manuel
     - OK selon matériel
   * - DEMO-004
     - SMS
     - Téléphone renseigné ou mode mail/log
     - Générer code, saisir au kiosque.
     - Accès validé.
     - Manuel
     - OK
   * - DEMO-005
     - Télémétrie continue
     - ESP32 ou simulateur
     - Publier mesures slot1.
     - Grafana affiche température, humidité, courant et énergie.
     - Manuel + simulation
     - OK
   * - DEMO-006
     - Alerte courant
     - Courant simulé supérieur au seuil
     - Publier télémétrie.
     - Alerte visible dans l'administration et Grafana.
     - Simulation + manuel
     - OK

Critères d'acceptation principaux
---------------------------------

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Critère
     - Condition d'acceptation
   * - Réservation
     - Une réservation valide est créée uniquement sur un emplacement disponible.
   * - QR réservation
     - Le QR donne accès uniquement à la bonne réservation, au bon créneau et à la bonne borne.
   * - QR borne mobile
     - Le QR lie temporairement un téléphone à une borne, puis laisse l'utilisateur choisir une réservation compatible.
   * - RFID
     - Le badge ne donne accès que si une réservation compatible existe.
   * - SMS
     - Le mode SMS est indisponible sans téléphone et limité par durée, essais et rate limiting.
   * - Serrure
     - La serrure s'ouvre après validation d'accès, jamais avant.
   * - Charge
     - La charge passe en cours uniquement après détection de courant dans le prototype.
   * - MQTT
     - Les commandes critiques exigent un ACK en production.
   * - Supervision
     - Les mesures sont liées à station, borne, emplacement et session quand disponible.
   * - Sécurité
     - Les secrets ne sont pas stockés en clair et les accès sensibles sont limités.
   * - Production
     - La stack démarre avec Docker, Nginx, PostgreSQL, Redis, backend, frontend et Grafana.

Tests à rejouer avant démonstration
-----------------------------------

.. list-table::
   :header-rows: 1
   :widths: 8 40 52

   * - Ordre
     - Test
     - Commande ou action
   * - 1
     - Vérifier les services serveur
     - ``docker compose -f docker-compose.prod.yml ps``
   * - 2
     - Vérifier backend
     - Ouvrir ``/api/health/ready/``.
   * - 3
     - Vérifier frontend
     - Ouvrir l'application HTTPS.
   * - 4
     - Vérifier login admin
     - Connexion compte administrateur.
   * - 5
     - Vérifier réservation
     - Créer une réservation proche.
   * - 6
     - Vérifier kiosque
     - Ouvrir l'interface Raspberry sur l'écran.
   * - 7
     - Vérifier QR mobile
     - Scanner le QR avec le smartphone.
   * - 8
     - Vérifier MQTT
     - Observer logs bridge et kiosque.
   * - 9
     - Vérifier ESP32
     - Contrôler connexion Wi-Fi/MQTT et télémétrie.
   * - 10
     - Vérifier Grafana
     - Voir les mesures sur le dashboard.
   * - 11
     - Vérifier arrêt
     - Stopper la charge et clôturer la session.
   * - 12
     - Vérifier données résiduelles
     - S'assurer qu'aucune session ne reste bloquée.
