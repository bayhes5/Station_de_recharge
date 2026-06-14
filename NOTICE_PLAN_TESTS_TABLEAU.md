# Plan de tests sous forme de tableau

Cette notice présente le plan de tests dans un format proche d'un cahier de recette utilisé en entreprise.
Elle complète la notice détaillée `NOTICE_PLAN_TESTS_REALISES.md` avec une vue plus opérationnelle : chaque test possède un identifiant, un périmètre, des préconditions, des étapes, un résultat attendu et une preuve de validation.

## Légende

| Terme | Signification |
|---|---|
| Automatisé | Test exécuté par `pytest`, Playwright, script Node ou CI |
| Manuel | Test réalisé à la main sur l'application, le kiosk, le smartphone ou le matériel |
| Simulation | Test réalisé avec données simulées, Wokwi, simulateur MQTT ou scénario Docker |
| OK | Test validé au moins une fois dans l'environnement de développement ou de démonstration |
| À valider matériel | Test préparé mais dépendant du câblage réel ou du matériel disponible |
| Régression | Test à relancer après chaque modification sensible |

## 1. Matrice globale de couverture

| Domaine | Objectif de test | Type principal | Preuve dans le projet |
|---|---|---|---|
| Authentification | Vérifier inscription, connexion, JWT, refresh token, profil | Automatisé | `backend/api/tests/test_api_auth.py`, `test_auth_profile.py` |
| Réservations | Vérifier création, créneaux, conflits, états, archivage | Automatisé | `backend/api/tests/test_reservations.py` |
| Accès terminal | Vérifier QR, RFID, SMS, session mobile, refus | Automatisé + manuel | `backend/api/tests/test_terminal_auth.py` |
| Session mobile | Vérifier QR borne, choix réservation, consommation par kiosk | Automatisé + manuel | `test_end_to_end_charge_flow.py`, `frontend/js/mobile-session.js` |
| Kiosk Raspberry | Vérifier interface tactile, RFID, cache offline, commandes MQTT | Automatisé + manuel | `raspberry/tests`, `raspberry/app` |
| ESP32 | Vérifier serrure, télémétrie, courant, énergie, alertes locales | Manuel + simulation | `esp32/emplacement1/main.py`, Wokwi, Grafana |
| MQTT | Vérifier topics, commandes, ACK, télémétrie, bridge | Automatisé + simulation | `test_mqtt_ingestion.py`, `test_mqtt_security_config.py` |
| Supervision | Vérifier dashboard admin, Grafana, alertes, exports | Automatisé + manuel | `test_admin_api.py`, `test_grafana_provisioning.py` |
| Sécurité | Vérifier rate limiting, secrets, cookies, Nginx, TLS, déploiement | Automatisé + manuel | `test_deployment_checks.py`, `test_nginx_security_config.py` |
| Production | Vérifier Docker, Nginx, sauvegarde, restauration, checks | Automatisé + manuel | CI, `docker-compose.prod.yml`, scripts `backup/restore` |
| Frontend/PWA | Vérifier pages, navigation, accessibilité, build, E2E | Automatisé + manuel | `npm run verify`, Playwright |

## 2. Tests backend et API

| ID | Fonction testée | Préconditions | Étapes de test | Résultat attendu | Type | Statut | Preuve |
|---|---|---|---|---|---|---|---|
| API-001 | Inscription utilisateur | Backend démarré | Créer un compte avec pseudo, e-mail et mot de passe | Compte créé, mot de passe non stocké en clair | Automatisé | OK | `test_api_auth.py` |
| API-002 | Connexion utilisateur | Compte existant | Envoyer identifiant + mot de passe | Retour JWT access + cookie refresh | Automatisé | OK | `test_api_auth.py` |
| API-003 | Refresh token | Session existante | Appeler `/api/token/refresh/` | Nouveau token access valide | Automatisé | OK | `test_api_auth.py` |
| API-004 | Profil utilisateur | Utilisateur connecté | Lire/modifier profil | Données mises à jour, accès protégé | Automatisé | OK | `test_auth_profile.py` |
| API-005 | Changement mot de passe | Utilisateur connecté | Envoyer ancien et nouveau mot de passe | Mot de passe changé, ancien refusé | Automatisé | OK | `test_auth_profile.py` |
| API-006 | Réinitialisation admin | Admin connecté | Générer mot de passe temporaire | Mail envoyé, changement obligatoire à la prochaine connexion | Manuel + automatisable | OK | `backend/api/views.py`, Mailpit |
| API-007 | Suppression/anonymisation compte | Utilisateur existant | Supprimer le compte | Données personnelles anonymisées, historiques conservés si nécessaires | Automatisé + manuel | OK | `backend/api/views.py` |

## 3. Tests réservations

| ID | Fonction testée | Préconditions | Étapes de test | Résultat attendu | Type | Statut | Preuve |
|---|---|---|---|---|---|---|---|
| RES-001 | Affichage des stations | Stations en base | Ouvrir page réservation | Stations visibles, carte chargée | Manuel + E2E | OK | `frontend/js/reservation.js` |
| RES-002 | Création réservation valide | Utilisateur connecté, emplacement libre | Choisir station, créneau, moyen d'accès | Réservation confirmée | Automatisé | OK | `test_reservations.py` |
| RES-003 | Conflit de réservation | Emplacement déjà réservé | Réserver un créneau chevauchant | Refus avec message métier | Automatisé | OK | `test_reservations.py` |
| RES-004 | Enchaînement de créneaux | Réservation existante | Tester un créneau voisin avec marge morte | Seuls les créneaux autorisés sont proposés | Automatisé + manuel | OK | `reservation_rules.py` |
| RES-005 | Archivage réservation | Réservation passée | Avancer le temps ou relancer état | Réservation archivée uniquement après fin de créneau | Automatisé + manuel | OK | `test_reservations.py` |
| RES-006 | QR réservation | Réservation confirmée | Générer ou régénérer QR | QR lié à la réservation, révocable | Automatisé | OK | `test_terminal_auth.py` |
| RES-007 | QR envoyé par mail | Mailpit disponible | Créer ou régénérer QR | Mail visible dans Mailpit | Manuel | OK | Mailpit |
| RES-008 | SMS sans téléphone | Profil sans numéro | Tenter de choisir code SMS | Option SMS non proposée | Automatisé + manuel | OK | `test_sms_access_policy.py` |
| RES-009 | Code SMS avec téléphone | Profil avec téléphone | Demander code SMS | Code généré, envoyé/loggé selon backend SMS | Automatisé + manuel | OK | `test_sms_service.py` |

## 4. Tests terminal, kiosk et moyens d'accès

| ID | Fonction testée | Préconditions | Étapes de test | Résultat attendu | Type | Statut | Preuve |
|---|---|---|---|---|---|---|---|
| KIO-001 | Démarrage kiosk | Raspberry démarré | Lancer service kiosk sur port 9000 | Interface disponible en local | Manuel | OK | `raspberry/app/main.py` |
| KIO-002 | Interface tactile 1024x600 | Kiosk ouvert sur écran Waveshare | Vérifier écrans principaux | Interface lisible, boutons cohérents | Manuel | OK | `raspberry/app/style.css` |
| KIO-003 | Authentification QR réservation | Réservation QR active | Présenter payload QR au kiosk | Accès autorisé si station/borne/créneau corrects | Automatisé + manuel | OK | `test_terminal_auth.py` |
| KIO-004 | QR invalide ou expiré | QR expiré/révoqué | Présenter QR au kiosk | Accès refusé | Automatisé | OK | `test_terminal_auth.py` |
| KIO-005 | Mauvaise station ou borne | Réservation sur une autre borne | Tenter validation au mauvais terminal | Accès refusé avec motif | Automatisé | OK | `test_terminal_auth.py` |
| KIO-006 | Session mobile QR borne | Smartphone connecté à la PWA | Scanner QR kiosk, choisir réservation | Session `authorized`, puis `consumed` par kiosk | Automatisé + manuel | OK | `test_end_to_end_charge_flow.py` |
| KIO-007 | QR mobile expiré | QR ancien affiché | Scanner après expiration | Session refusée ou renouvelée côté kiosk | Manuel + code | OK | `raspberry/app/app.js` |
| KIO-008 | Association RFID | Code d'association généré | Saisir code au kiosk et badger | UID associé au compte | Manuel | OK | `rfid_reader.py`, backend terminal |
| KIO-009 | Accès RFID valide | Badge associé, réservation active | Présenter badge | Accès validé | Manuel + automatisé côté API | OK | `test_terminal_auth.py` |
| KIO-010 | Accès RFID hors créneau | Badge associé, pas de réservation valide | Présenter badge | Accès refusé | Automatisé + manuel | OK | `test_terminal_auth.py` |
| KIO-011 | Code SMS valide | Code SMS généré | Saisir le code au kiosk | Accès validé | Automatisé + manuel | OK | `test_terminal_auth.py` |
| KIO-012 | Trop d'essais | Plusieurs codes invalides | Répéter la saisie | Rate limiting ou refus temporaire | Automatisé | OK | `throttles.py` |

## 5. Tests charge, serrure et machine d'état

| ID | Fonction testée | Préconditions | Étapes de test | Résultat attendu | Type | Statut | Preuve |
|---|---|---|---|---|---|---|---|
| CHG-001 | Déverrouillage après accès | Accès QR/RFID/SMS/mobile validé | Valider l'accès au kiosk | Commande `UNLOCK` envoyée | Manuel + simulation | OK | `mqtt_commands.py`, ESP32 |
| CHG-002 | Pas de charge au badge seul | Accès validé, pas de courant | Présenter badge sans activer générateur | État `waiting_plug`, pas `charging` | Manuel + logique | OK | `charge_state.py` |
| CHG-003 | Démarrage sur courant détecté | Générateur activé | Détecter courant au-dessus du seuil | Passage en `charging` | Manuel | À valider matériel | `esp32/emplacement1/main.py` |
| CHG-004 | Re-fermeture si aucune charge | Serrure ouverte, pas de courant | Attendre le délai défini | Serrure refermée, session annulée/clôturée | Manuel | À valider matériel | ESP32/kiosk |
| CHG-005 | Arrêt charge | Session en charge | Demander arrêt | Commande `STOP`, session clôturée | Automatisé + manuel | OK | `run-demo-scenario.ps1` |
| CHG-006 | Énergie cumulée | Courant mesuré dans le temps | Laisser télémétrie active | Énergie kWh augmente progressivement | Simulation + manuel | OK | `mqtt_simulator.py`, Grafana |
| CHG-007 | Seuil courant 4 A | Télémétrie courant élevée | Publier courant > seuil | Alerte courant créée | Simulation + manuel | OK | `test_operational_alerts.py` |
| CHG-008 | LED verte pendant charge | ESP32 en charge | Observer LED | LED verte active/clignotante selon firmware | Manuel | À valider matériel | ESP32 |
| CHG-009 | LED jaune/rouge alerte | Température/courant élevé | Simuler alerte modérée/grave | LED et buzzer selon sévérité | Manuel | À valider matériel | ESP32 |

## 6. Tests MQTT et ESP32

| ID | Fonction testée | Préconditions | Étapes de test | Résultat attendu | Type | Statut | Preuve |
|---|---|---|---|---|---|---|---|
| MQTT-001 | Connexion Mosquitto | Broker accessible | Connecter backend/Raspberry/ESP32 | Connexion acceptée avec identifiants valides | Manuel | OK | Mosquitto |
| MQTT-002 | Identifiants invalides | Mauvais mot de passe | Connexion ESP32 | Refus `not authorised` | Manuel | OK | Mosquitto |
| MQTT-003 | Publication télémétrie | ESP32 ou simulateur actif | Publier température/humidité/courant | Message reçu par bridge | Automatisé + manuel | OK | `test_mqtt_ingestion.py` |
| MQTT-004 | ACK commande | Commande avec `command_id` | ESP32 répond ACK | Commande confirmée | Automatisé + manuel | OK | `test_mqtt_client.py` |
| MQTT-005 | Timeout ACK | ESP32 muet | Envoyer commande avec ACK requis | Erreur explicite | Automatisé | OK | `test_mqtt_client.py` |
| MQTT-006 | Topic par emplacement | Station/borne/emplacement configurés | Publier sur topic slot1 | Seul slot1 est mis à jour | Automatisé + simulation | OK | `test_mqtt_ingestion.py` |
| MQTT-007 | État firmware/IP/MAC | ESP32 connecté | Publier status device | Données device enregistrées si réelles | Manuel + automatisé | OK | `test_mqtt_ingestion.py` |
| MQTT-008 | Données non inventées | Bootstrap demo | Charger jeu d'essais | Pas d'IP/MAC fictives si non remontées | Manuel | OK | `bootstrap_demo_data.py` |

## 7. Tests supervision admin et Grafana

| ID | Fonction testée | Préconditions | Étapes de test | Résultat attendu | Type | Statut | Preuve |
|---|---|---|---|---|---|---|---|
| SUP-001 | Dashboard admin global | Admin connecté | Ouvrir tableau de bord admin | Statistiques cohérentes | Automatisé + manuel | OK | `test_admin_api.py` |
| SUP-002 | Supervision sessions | Session active ou simulée | Ouvrir supervision | Session visible avec état correct | Manuel | OK | `admin-dashboard.js` |
| SUP-003 | Alertes | Télémétrie hors seuil | Simuler température/courant élevé | Alerte créée, sévérité visible | Automatisé + manuel | OK | `test_operational_alerts.py` |
| SUP-004 | Sévérité haute rouge | Alerte critique | Afficher dashboard | Couleur rouge utilisée | Manuel | OK | CSS/JS frontend |
| SUP-005 | Grafana global | Grafana démarré | Ouvrir dashboard global | Mesures visibles | Manuel | OK | `station-supervision.json` |
| SUP-006 | Grafana par session | Session active | Filtrer par session/emplacement | Mesures liées à la session | Manuel | OK | Grafana |
| SUP-007 | Export CSV/JSON | Admin connecté | Filtrer et exporter logs | Fichier téléchargé avec données filtrées | Manuel + API | OK | `admin-dashboard.js` |
| SUP-008 | Logs archivés | Données historiques | Afficher journaux archivés | Liste consultable avant export | Manuel | OK | Frontend admin |

## 8. Tests mode dégradé

| ID | Fonction testée | Préconditions | Étapes de test | Résultat attendu | Type | Statut | Preuve |
|---|---|---|---|---|---|---|---|
| OFF-001 | Synchronisation cache | Backend disponible | Lancer kiosk | Réservations compatibles mises en cache | Manuel + code | OK | `offline_store.py` |
| OFF-002 | Backend indisponible | Cache déjà synchronisé | Couper backend puis valider accès connu | Validation locale possible si secret présent | Manuel | À valider démo | `offline_store.py` |
| OFF-003 | Réservation non cachée | Backend indisponible | Tenter accès à réservation absente | Accès refusé | Manuel | À valider démo | `offline_store.py` |
| OFF-004 | MQTT local Raspberry | Broker sur Raspberry | Couper serveur central | Raspberry peut commander ESP32 via broker local | Manuel | À valider matériel | Mosquitto Raspberry |
| OFF-005 | Reprise serveur | Backend rétabli | Relancer synchronisation | Retour au mode nominal | Manuel | À valider démo | Kiosk logs |

## 9. Tests sécurité et production

| ID | Fonction testée | Préconditions | Étapes de test | Résultat attendu | Type | Statut | Preuve |
|---|---|---|---|---|---|---|---|
| SEC-001 | Hash mots de passe | Utilisateur créé | Inspecter/authentifier | Mot de passe jamais stocké en clair | Automatisé + manuel | OK | Django auth |
| SEC-002 | Secret terminal | Terminal configuré | Appeler API terminal sans secret | Requête refusée | Automatisé | OK | `test_terminal_auth.py` |
| SEC-003 | Comparaison secrets | Secret fourni | Comparaison sécurisée | Pas de comparaison naïve sensible | Code review | OK | `backend/api/views.py` |
| SEC-004 | Rate limiting | Appels répétés | Multiplier erreurs login/SMS/session | Limitation appliquée | Automatisé | OK | `throttles.py` |
| SEC-005 | Cookies sécurisés | Mode production | Vérifier config Django | Cookies secure/httponly selon rôle | Automatisé | OK | `test_deployment_checks.py` |
| SEC-006 | CSRF/CORS | Origines configurées | Accès depuis origine non autorisée | Requête refusée | Automatisé + manuel | OK | `settings.py` |
| SEC-007 | Nginx headers | Reverse proxy démarré | Vérifier configuration | Headers de sécurité présents | Automatisé | OK | `test_nginx_security_config.py` |
| SEC-008 | TLS local | CA Smallstep installée | Accéder en HTTPS | Certificat accepté si racine importée | Manuel | OK | `security/README.md` |
| SEC-009 | Docker non-root | Compose prod | Analyser services | Services durcis autant que possible | Automatisé | OK | `test_container_security_config.py` |
| SEC-010 | Sauvegarde/restauration | Serveur prod | Lancer scripts backup/restore test | Scripts valides | Automatisé syntaxe + manuel | OK | `scripts/backup-prod.sh` |

## 10. Tests frontend/PWA

| ID | Fonction testée | Préconditions | Étapes de test | Résultat attendu | Type | Statut | Preuve |
|---|---|---|---|---|---|---|---|
| FE-001 | Syntaxe JS | Node installé | `npm run check:js` | Aucun fichier JS invalide | Automatisé | OK | `check-js.mjs` |
| FE-002 | Sécurité DOM | Code frontend | `npm run check:js` | Pas d'`innerHTML` dangereux, pas de `eval` | Automatisé | OK | `check-js.mjs` |
| FE-003 | Accessibilité de base | Pages HTML | `npm run check:a11y` | Titres, labels, main, viewport présents | Automatisé | OK | `check-accessibility.mjs` |
| FE-004 | Build production | Dépendances installées | `npm run build` | Build Vite généré | Automatisé | OK | CI |
| FE-005 | Navigation utilisateur | API simulée | Playwright | Dashboard/réservation/profil navigables | Automatisé | OK | `app.spec.js` |
| FE-006 | Navigation admin | Admin simulé | Playwright | Dashboard admin accessible | Automatisé | OK | `app.spec.js` |
| FE-007 | Navigation technicien | Technicien simulé | Playwright | Espace technicien accessible | Automatisé | OK | `app.spec.js` |
| FE-008 | PWA mobile | Smartphone | Ouvrir app mobile et session QR | Interface lisible, bottom nav cohérente | Manuel | OK | Recette mobile |
| FE-009 | Carte OpenStreetMap | Accès Internet | Ouvrir réservation sur PC/mobile | Carte visible après chargement | Manuel | OK partiel | `reservation.js` |

## 11. Tests CI/CD et qualité

| ID | Fonction testée | Préconditions | Étapes de test | Résultat attendu | Type | Statut | Preuve |
|---|---|---|---|---|---|---|---|
| CI-001 | Tests backend | Push/PR GitHub | Lancer workflow CI | `pytest` backend OK | Automatisé | OK | `.github/workflows/ci.yml` |
| CI-002 | Qualité backend | Push/PR GitHub | Lancer Ruff | Aucun problème bloquant | Automatisé | OK | CI |
| CI-003 | Schéma OpenAPI | Push/PR GitHub | Générer et valider schema | OpenAPI valide | Automatisé | OK | CI |
| CI-004 | Checks déploiement | Variables prod simulées | `manage.py check --deploy` | Pas d'erreur critique | Automatisé | OK | CI |
| CI-005 | Tests Raspberry | Push/PR GitHub | Compiler modules + pytest | Tests edge OK | Automatisé | OK | CI |
| CI-006 | Frontend verify | Changement frontend | `npm run verify` | JS, a11y, build, e2e OK | Automatisé | OK | CI |
| CI-007 | Docker compose prod | Push/PR GitHub | `docker compose config --quiet` | Compose valide | Automatisé | OK | CI |
| CI-008 | Documentation | Push/PR GitHub | Build Sphinx | Documentation construite | Automatisé | OK | CI |

## 12. Tests de recette démonstration

| ID | Scénario | Préconditions | Étapes résumées | Résultat attendu | Type | Statut |
|---|---|---|---|---|---|---|
| DEMO-001 | Réservation QR complète | Stack lancée, utilisateur demo | Réserver, scanner QR, ouvrir, détecter courant, arrêter | Session complète visible backend/Grafana | Manuel + script | OK |
| DEMO-002 | Session mobile kiosk | Smartphone connecté, QR kiosk | Scanner QR, choisir réservation, autoriser | Kiosk ouvre l'emplacement | Manuel | OK |
| DEMO-003 | RFID | Badge associé | Badger pendant créneau valide | Accès validé, serrure ouverte | Manuel | OK selon matériel |
| DEMO-004 | SMS | Téléphone renseigné ou mode mail/log | Générer code, saisir au kiosk | Accès validé | Manuel | OK |
| DEMO-005 | Télémétrie continue | ESP32 ou simulateur | Publier mesures slot1 | Grafana affiche température/humidité/courant/énergie | Manuel + simulation | OK |
| DEMO-006 | Alerte courant | Courant simulé > 4 A | Publier télémétrie | Alerte visible | Simulation + manuel | OK |
| DEMO-007 | Mauvaise réservation | Réservation hors borne/créneau | Tenter accès | Refus clair | Automatisé + manuel | OK |
| DEMO-008 | Perte backend | Cache offline prêt | Couper backend | Accès cached possible selon données | Manuel | À valider démo |

## 13. Critères d'acceptation principaux

| Critère | Condition d'acceptation |
|---|---|
| Réservation | Une réservation valide est créée uniquement sur un emplacement disponible |
| QR réservation | Le QR donne accès uniquement à la bonne réservation, au bon créneau et à la bonne borne |
| QR borne mobile | Le QR lie temporairement un téléphone à une borne, puis laisse l'utilisateur choisir une réservation compatible |
| RFID | Le badge ne donne accès que si une réservation compatible existe |
| SMS | Le mode SMS est indisponible sans téléphone et limité par durée/essais |
| Serrure | La serrure s'ouvre après validation d'accès, pas avant |
| Charge | La charge passe en cours uniquement après détection de courant dans le prototype |
| MQTT | Les commandes critiques exigent un ACK en production |
| Supervision | Les mesures sont liées à station, borne, emplacement et session quand disponible |
| Sécurité | Les secrets ne sont pas stockés en clair et les accès sensibles sont limités |
| Production | La stack démarre avec Docker, Nginx, PostgreSQL, Redis, backend, frontend et Grafana |

## 14. Tests à rejouer avant démonstration

| Ordre | Test | Commande ou action |
|---:|---|---|
| 1 | Vérifier les services serveur | `docker compose -f docker-compose.prod.yml ps` |
| 2 | Vérifier backend | Ouvrir `/api/health/ready/` |
| 3 | Vérifier frontend | Ouvrir l'application HTTPS |
| 4 | Vérifier login admin | Connexion compte admin |
| 5 | Vérifier réservation | Créer une réservation proche |
| 6 | Vérifier kiosk | Ouvrir interface Raspberry sur écran |
| 7 | Vérifier QR mobile | Scanner QR avec smartphone |
| 8 | Vérifier MQTT | Observer logs bridge/kiosk |
| 9 | Vérifier ESP32 | Connexion Wi-Fi/MQTT et télémétrie |
| 10 | Vérifier Grafana | Voir mesures sur dashboard |
| 11 | Vérifier arrêt | Stopper charge et clôturer session |
| 12 | Vérifier données résiduelles | S'assurer qu'aucune session ne reste bloquée |
