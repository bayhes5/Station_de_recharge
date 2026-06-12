# Plan de tests sous forme de tableau

Cette notice prÃ©sente le plan de tests dans un format proche d'un cahier de recette utilisÃ© en entreprise.
Elle complÃ¨te la notice dÃ©taillÃ©e `NOTICE_PLAN_TESTS_REALISES.md` avec une vue plus opÃ©rationnelle : chaque test possÃ¨de un identifiant, un pÃ©rimÃ¨tre, des prÃ©conditions, des Ã©tapes, un rÃ©sultat attendu et une preuve de validation.

## LÃ©gende

| Terme | Signification |
|---|---|
| AutomatisÃ© | Test exÃ©cutÃ© par `pytest`, Playwright, script Node ou CI |
| Manuel | Test rÃ©alisÃ© Ã  la main sur l'application, le kiosk, le smartphone ou le matÃ©riel |
| Simulation | Test rÃ©alisÃ© avec donnÃ©es simulÃ©es, Wokwi, simulateur MQTT ou scÃ©nario Docker |
| OK | Test validÃ© au moins une fois dans l'environnement de dÃ©veloppement ou de dÃ©monstration |
| Ã€ valider matÃ©riel | Test prÃ©parÃ© mais dÃ©pendant du cÃ¢blage rÃ©el ou du matÃ©riel disponible |
| RÃ©gression | Test Ã  relancer aprÃ¨s chaque modification sensible |

## 1. Matrice globale de couverture

| Domaine | Objectif de test | Type principal | Preuve dans le projet |
|---|---|---|---|
| Authentification | VÃ©rifier inscription, connexion, JWT, refresh token, profil | AutomatisÃ© | `backend/api/tests/test_api_auth.py`, `test_auth_profile.py` |
| RÃ©servations | VÃ©rifier crÃ©ation, crÃ©neaux, conflits, Ã©tats, archivage | AutomatisÃ© | `backend/api/tests/test_reservations.py` |
| AccÃ¨s terminal | VÃ©rifier QR, RFID, SMS, session mobile, refus | AutomatisÃ© + manuel | `backend/api/tests/test_terminal_auth.py` |
| Session mobile | VÃ©rifier QR borne, choix rÃ©servation, consommation par kiosk | AutomatisÃ© + manuel | `test_end_to_end_charge_flow.py`, `frontend/js/mobile-session.js` |
| Kiosk Raspberry | VÃ©rifier interface tactile, RFID, cache offline, commandes MQTT | AutomatisÃ© + manuel | `raspberry/tests`, `raspberry/app` |
| ESP32 | VÃ©rifier serrure, tÃ©lÃ©mÃ©trie, courant, Ã©nergie, alertes locales | Manuel + simulation | `esp32/emplacement1/main.py`, Wokwi, Grafana |
| MQTT | VÃ©rifier topics, commandes, ACK, tÃ©lÃ©mÃ©trie, bridge | AutomatisÃ© + simulation | `test_mqtt_ingestion.py`, `test_mqtt_security_config.py` |
| Supervision | VÃ©rifier dashboard admin, Grafana, alertes, exports | AutomatisÃ© + manuel | `test_admin_api.py`, `test_grafana_provisioning.py` |
| SÃ©curitÃ© | VÃ©rifier rate limiting, secrets, cookies, Nginx, TLS, dÃ©ploiement | AutomatisÃ© + manuel | `test_deployment_checks.py`, `test_nginx_security_config.py` |
| Production | VÃ©rifier Docker, Nginx, sauvegarde, restauration, checks | AutomatisÃ© + manuel | CI, `docker-compose.prod.yml`, scripts `backup/restore` |
| Frontend/PWA | VÃ©rifier pages, navigation, accessibilitÃ©, build, E2E | AutomatisÃ© + manuel | `npm run verify`, Playwright |

## 2. Tests backend et API

| ID | Fonction testÃ©e | PrÃ©conditions | Ã‰tapes de test | RÃ©sultat attendu | Type | Statut | Preuve |
|---|---|---|---|---|---|---|---|
| API-001 | Inscription utilisateur | Backend dÃ©marrÃ© | CrÃ©er un compte avec pseudo, e-mail et mot de passe | Compte crÃ©Ã©, mot de passe non stockÃ© en clair | AutomatisÃ© | OK | `test_api_auth.py` |
| API-002 | Connexion utilisateur | Compte existant | Envoyer identifiant + mot de passe | Retour JWT access + cookie refresh | AutomatisÃ© | OK | `test_api_auth.py` |
| API-003 | Refresh token | Session existante | Appeler `/api/token/refresh/` | Nouveau token access valide | AutomatisÃ© | OK | `test_api_auth.py` |
| API-004 | Profil utilisateur | Utilisateur connectÃ© | Lire/modifier profil | DonnÃ©es mises Ã  jour, accÃ¨s protÃ©gÃ© | AutomatisÃ© | OK | `test_auth_profile.py` |
| API-005 | Changement mot de passe | Utilisateur connectÃ© | Envoyer ancien et nouveau mot de passe | Mot de passe changÃ©, ancien refusÃ© | AutomatisÃ© | OK | `test_auth_profile.py` |
| API-006 | RÃ©initialisation admin | Admin connectÃ© | GÃ©nÃ©rer mot de passe temporaire | Mail envoyÃ©, changement obligatoire Ã  la prochaine connexion | Manuel + automatisable | OK | `backend/api/views.py`, Mailpit |
| API-007 | Suppression/anonymisation compte | Utilisateur existant | Supprimer le compte | DonnÃ©es personnelles anonymisÃ©es, historiques conservÃ©s si nÃ©cessaires | AutomatisÃ© + manuel | OK | `backend/api/views.py` |

## 3. Tests rÃ©servations

| ID | Fonction testÃ©e | PrÃ©conditions | Ã‰tapes de test | RÃ©sultat attendu | Type | Statut | Preuve |
|---|---|---|---|---|---|---|---|
| RES-001 | Affichage des stations | Stations en base | Ouvrir page rÃ©servation | Stations visibles, carte chargÃ©e | Manuel + E2E | OK | `frontend/js/reservation.js` |
| RES-002 | CrÃ©ation rÃ©servation valide | Utilisateur connectÃ©, emplacement libre | Choisir station, crÃ©neau, moyen d'accÃ¨s | RÃ©servation confirmÃ©e | AutomatisÃ© | OK | `test_reservations.py` |
| RES-003 | Conflit de rÃ©servation | Emplacement dÃ©jÃ  rÃ©servÃ© | RÃ©server un crÃ©neau chevauchant | Refus avec message mÃ©tier | AutomatisÃ© | OK | `test_reservations.py` |
| RES-004 | EnchaÃ®nement de crÃ©neaux | RÃ©servation existante | Tester un crÃ©neau voisin avec marge morte | Seuls les crÃ©neaux autorisÃ©s sont proposÃ©s | AutomatisÃ© + manuel | OK | `reservation_rules.py` |
| RES-005 | Archivage rÃ©servation | RÃ©servation passÃ©e | Avancer le temps ou relancer Ã©tat | RÃ©servation archivÃ©e uniquement aprÃ¨s fin de crÃ©neau | AutomatisÃ© + manuel | OK | `test_reservations.py` |
| RES-006 | QR rÃ©servation | RÃ©servation confirmÃ©e | GÃ©nÃ©rer ou rÃ©gÃ©nÃ©rer QR | QR liÃ© Ã  la rÃ©servation, rÃ©vocable | AutomatisÃ© | OK | `test_terminal_auth.py` |
| RES-007 | QR envoyÃ© par mail | Mailpit disponible | CrÃ©er ou rÃ©gÃ©nÃ©rer QR | Mail visible dans Mailpit | Manuel | OK | Mailpit |
| RES-008 | SMS sans tÃ©lÃ©phone | Profil sans numÃ©ro | Tenter de choisir code SMS | Option SMS non proposÃ©e | AutomatisÃ© + manuel | OK | `test_sms_access_policy.py` |
| RES-009 | Code SMS avec tÃ©lÃ©phone | Profil avec tÃ©lÃ©phone | Demander code SMS | Code gÃ©nÃ©rÃ©, envoyÃ©/loggÃ© selon backend SMS | AutomatisÃ© + manuel | OK | `test_sms_service.py` |

## 4. Tests terminal, kiosk et moyens d'accÃ¨s

| ID | Fonction testÃ©e | PrÃ©conditions | Ã‰tapes de test | RÃ©sultat attendu | Type | Statut | Preuve |
|---|---|---|---|---|---|---|---|
| KIO-001 | DÃ©marrage kiosk | Raspberry dÃ©marrÃ© | Lancer service kiosk sur port 9000 | Interface disponible en local | Manuel | OK | `raspberry/app/main.py` |
| KIO-002 | Interface tactile 1024x600 | Kiosk ouvert sur Ã©cran Waveshare | VÃ©rifier Ã©crans principaux | Interface lisible, boutons cohÃ©rents | Manuel | OK | `raspberry/app/style.css` |
| KIO-003 | Authentification QR rÃ©servation | RÃ©servation QR active | PrÃ©senter payload QR au kiosk | AccÃ¨s autorisÃ© si station/borne/crÃ©neau corrects | AutomatisÃ© + manuel | OK | `test_terminal_auth.py` |
| KIO-004 | QR invalide ou expirÃ© | QR expirÃ©/rÃ©voquÃ© | PrÃ©senter QR au kiosk | AccÃ¨s refusÃ© | AutomatisÃ© | OK | `test_terminal_auth.py` |
| KIO-005 | Mauvaise station ou borne | RÃ©servation sur une autre borne | Tenter validation au mauvais terminal | AccÃ¨s refusÃ© avec motif | AutomatisÃ© | OK | `test_terminal_auth.py` |
| KIO-006 | Session mobile QR borne | Smartphone connectÃ© Ã  la PWA | Scanner QR kiosk, choisir rÃ©servation | Session `authorized`, puis `consumed` par kiosk | AutomatisÃ© + manuel | OK | `test_end_to_end_charge_flow.py` |
| KIO-007 | QR mobile expirÃ© | QR ancien affichÃ© | Scanner aprÃ¨s expiration | Session refusÃ©e ou renouvelÃ©e cÃ´tÃ© kiosk | Manuel + code | OK | `raspberry/app/app.js` |
| KIO-008 | Association RFID | Code d'association gÃ©nÃ©rÃ© | Saisir code au kiosk et badger | UID associÃ© au compte | Manuel | OK | `rfid_reader.py`, backend terminal |
| KIO-009 | AccÃ¨s RFID valide | Badge associÃ©, rÃ©servation active | PrÃ©senter badge | AccÃ¨s validÃ© | Manuel + automatisÃ© cÃ´tÃ© API | OK | `test_terminal_auth.py` |
| KIO-010 | AccÃ¨s RFID hors crÃ©neau | Badge associÃ©, pas de rÃ©servation valide | PrÃ©senter badge | AccÃ¨s refusÃ© | AutomatisÃ© + manuel | OK | `test_terminal_auth.py` |
| KIO-011 | Code SMS valide | Code SMS gÃ©nÃ©rÃ© | Saisir le code au kiosk | AccÃ¨s validÃ© | AutomatisÃ© + manuel | OK | `test_terminal_auth.py` |
| KIO-012 | Trop d'essais | Plusieurs codes invalides | RÃ©pÃ©ter la saisie | Rate limiting ou refus temporaire | AutomatisÃ© | OK | `throttles.py` |

## 5. Tests charge, serrure et machine d'Ã©tat

| ID | Fonction testÃ©e | PrÃ©conditions | Ã‰tapes de test | RÃ©sultat attendu | Type | Statut | Preuve |
|---|---|---|---|---|---|---|---|
| CHG-001 | DÃ©verrouillage aprÃ¨s accÃ¨s | AccÃ¨s QR/RFID/SMS/mobile validÃ© | Valider l'accÃ¨s au kiosk | Commande `UNLOCK` envoyÃ©e | Manuel + simulation | OK | `mqtt_commands.py`, ESP32 |
| CHG-002 | Pas de charge au badge seul | AccÃ¨s validÃ©, pas de courant | PrÃ©senter badge sans activer gÃ©nÃ©rateur | Ã‰tat `waiting_plug`, pas `charging` | Manuel + logique | OK | `charge_state.py` |
| CHG-003 | DÃ©marrage sur courant dÃ©tectÃ© | GÃ©nÃ©rateur activÃ© | DÃ©tecter courant au-dessus du seuil | Passage en `charging` | Manuel | Ã€ valider matÃ©riel | `esp32/emplacement1/main.py` |
| CHG-004 | Re-fermeture si aucune charge | Serrure ouverte, pas de courant | Attendre le dÃ©lai dÃ©fini | Serrure refermÃ©e, session annulÃ©e/clÃ´turÃ©e | Manuel | Ã€ valider matÃ©riel | ESP32/kiosk |
| CHG-005 | ArrÃªt charge | Session en charge | Demander arrÃªt | Commande `STOP`, session clÃ´turÃ©e | AutomatisÃ© + manuel | OK | `run-demo-scenario.ps1` |
| CHG-006 | Ã‰nergie cumulÃ©e | Courant mesurÃ© dans le temps | Laisser tÃ©lÃ©mÃ©trie active | Ã‰nergie kWh augmente progressivement | Simulation + manuel | OK | `mqtt_simulator.py`, Grafana |
| CHG-007 | Seuil courant 4 A | TÃ©lÃ©mÃ©trie courant Ã©levÃ©e | Publier courant > seuil | Alerte courant crÃ©Ã©e | Simulation + manuel | OK | `test_operational_alerts.py` |
| CHG-008 | LED verte pendant charge | ESP32 en charge | Observer LED | LED verte active/clignotante selon firmware | Manuel | Ã€ valider matÃ©riel | ESP32 |
| CHG-009 | LED jaune/rouge alerte | TempÃ©rature/courant Ã©levÃ© | Simuler alerte modÃ©rÃ©e/grave | LED et buzzer selon sÃ©vÃ©ritÃ© | Manuel | Ã€ valider matÃ©riel | ESP32 |

## 6. Tests MQTT et ESP32

| ID | Fonction testÃ©e | PrÃ©conditions | Ã‰tapes de test | RÃ©sultat attendu | Type | Statut | Preuve |
|---|---|---|---|---|---|---|---|
| MQTT-001 | Connexion Mosquitto | Broker accessible | Connecter backend/Raspberry/ESP32 | Connexion acceptÃ©e avec identifiants valides | Manuel | OK | Mosquitto |
| MQTT-002 | Identifiants invalides | Mauvais mot de passe | Connexion ESP32 | Refus `not authorised` | Manuel | OK | Mosquitto |
| MQTT-003 | Publication tÃ©lÃ©mÃ©trie | ESP32 ou simulateur actif | Publier tempÃ©rature/humiditÃ©/courant | Message reÃ§u par bridge | AutomatisÃ© + manuel | OK | `test_mqtt_ingestion.py` |
| MQTT-004 | ACK commande | Commande avec `command_id` | ESP32 rÃ©pond ACK | Commande confirmÃ©e | AutomatisÃ© + manuel | OK | `test_mqtt_client.py` |
| MQTT-005 | Timeout ACK | ESP32 muet | Envoyer commande avec ACK requis | Erreur explicite | AutomatisÃ© | OK | `test_mqtt_client.py` |
| MQTT-006 | Topic par emplacement | Station/borne/emplacement configurÃ©s | Publier sur topic slot1 | Seul slot1 est mis Ã  jour | AutomatisÃ© + simulation | OK | `test_mqtt_ingestion.py` |
| MQTT-007 | Ã‰tat firmware/IP/MAC | ESP32 connectÃ© | Publier status device | DonnÃ©es device enregistrÃ©es si rÃ©elles | Manuel + automatisÃ© | OK | `test_mqtt_ingestion.py` |
| MQTT-008 | DonnÃ©es non inventÃ©es | Bootstrap demo | Charger jeu d'essais | Pas d'IP/MAC fictives si non remontÃ©es | Manuel | OK | `bootstrap_demo_data.py` |

## 7. Tests supervision admin et Grafana

| ID | Fonction testÃ©e | PrÃ©conditions | Ã‰tapes de test | RÃ©sultat attendu | Type | Statut | Preuve |
|---|---|---|---|---|---|---|---|
| SUP-001 | Dashboard admin global | Admin connectÃ© | Ouvrir tableau de bord admin | Statistiques cohÃ©rentes | AutomatisÃ© + manuel | OK | `test_admin_api.py` |
| SUP-002 | Supervision sessions | Session active ou simulÃ©e | Ouvrir supervision | Session visible avec Ã©tat correct | Manuel | OK | `admin-dashboard.js` |
| SUP-003 | Alertes | TÃ©lÃ©mÃ©trie hors seuil | Simuler tempÃ©rature/courant Ã©levÃ© | Alerte crÃ©Ã©e, sÃ©vÃ©ritÃ© visible | AutomatisÃ© + manuel | OK | `test_operational_alerts.py` |
| SUP-004 | SÃ©vÃ©ritÃ© haute rouge | Alerte critique | Afficher dashboard | Couleur rouge utilisÃ©e | Manuel | OK | CSS/JS frontend |
| SUP-005 | Grafana global | Grafana dÃ©marrÃ© | Ouvrir dashboard global | Mesures visibles | Manuel | OK | `station-supervision.json` |
| SUP-006 | Grafana par session | Session active | Filtrer par session/emplacement | Mesures liÃ©es Ã  la session | Manuel | OK | Grafana |
| SUP-007 | Export CSV/JSON | Admin connectÃ© | Filtrer et exporter logs | Fichier tÃ©lÃ©chargÃ© avec donnÃ©es filtrÃ©es | Manuel + API | OK | `admin-dashboard.js` |
| SUP-008 | Logs archivÃ©s | DonnÃ©es historiques | Afficher journaux archivÃ©s | Liste consultable avant export | Manuel | OK | Frontend admin |

## 8. Tests mode dÃ©gradÃ©

| ID | Fonction testÃ©e | PrÃ©conditions | Ã‰tapes de test | RÃ©sultat attendu | Type | Statut | Preuve |
|---|---|---|---|---|---|---|---|
| OFF-001 | Synchronisation cache | Backend disponible | Lancer kiosk | RÃ©servations compatibles mises en cache | Manuel + code | OK | `offline_store.py` |
| OFF-002 | Backend indisponible | Cache dÃ©jÃ  synchronisÃ© | Couper backend puis valider accÃ¨s connu | Validation locale possible si secret prÃ©sent | Manuel | Ã€ valider dÃ©mo | `offline_store.py` |
| OFF-003 | RÃ©servation non cachÃ©e | Backend indisponible | Tenter accÃ¨s Ã  rÃ©servation absente | AccÃ¨s refusÃ© | Manuel | Ã€ valider dÃ©mo | `offline_store.py` |
| OFF-004 | MQTT local Raspberry | Broker sur Raspberry | Couper serveur central | Raspberry peut commander ESP32 via broker local | Manuel | Ã€ valider matÃ©riel | Mosquitto Raspberry |
| OFF-005 | Reprise serveur | Backend rÃ©tabli | Relancer synchronisation | Retour au mode nominal | Manuel | Ã€ valider dÃ©mo | Kiosk logs |

## 9. Tests sÃ©curitÃ© et production

| ID | Fonction testÃ©e | PrÃ©conditions | Ã‰tapes de test | RÃ©sultat attendu | Type | Statut | Preuve |
|---|---|---|---|---|---|---|---|
| SEC-001 | Hash mots de passe | Utilisateur crÃ©Ã© | Inspecter/authentifier | Mot de passe jamais stockÃ© en clair | AutomatisÃ© + manuel | OK | Django auth |
| SEC-002 | Secret terminal | Terminal configurÃ© | Appeler API terminal sans secret | RequÃªte refusÃ©e | AutomatisÃ© | OK | `test_terminal_auth.py` |
| SEC-003 | Comparaison secrets | Secret fourni | Comparaison sÃ©curisÃ©e | Pas de comparaison naÃ¯ve sensible | Code review | OK | `backend/api/views.py` |
| SEC-004 | Rate limiting | Appels rÃ©pÃ©tÃ©s | Multiplier erreurs login/SMS/session | Limitation appliquÃ©e | AutomatisÃ© | OK | `throttles.py` |
| SEC-005 | Cookies sÃ©curisÃ©s | Mode production | VÃ©rifier config Django | Cookies secure/httponly selon rÃ´le | AutomatisÃ© | OK | `test_deployment_checks.py` |
| SEC-006 | CSRF/CORS | Origines configurÃ©es | AccÃ¨s depuis origine non autorisÃ©e | RequÃªte refusÃ©e | AutomatisÃ© + manuel | OK | `settings.py` |
| SEC-007 | Nginx headers | Reverse proxy dÃ©marrÃ© | VÃ©rifier configuration | Headers de sÃ©curitÃ© prÃ©sents | AutomatisÃ© | OK | `test_nginx_security_config.py` |
| SEC-008 | TLS local | CA Smallstep installÃ©e | AccÃ©der en HTTPS | Certificat acceptÃ© si racine importÃ©e | Manuel | OK | `security/README.md` |
| SEC-009 | Docker non-root | Compose prod | Analyser services | Services durcis autant que possible | AutomatisÃ© | OK | `test_container_security_config.py` |
| SEC-010 | Sauvegarde/restauration | Serveur prod | Lancer scripts backup/restore test | Scripts valides | AutomatisÃ© syntaxe + manuel | OK | `scripts/backup-prod.sh` |

## 10. Tests frontend/PWA

| ID | Fonction testÃ©e | PrÃ©conditions | Ã‰tapes de test | RÃ©sultat attendu | Type | Statut | Preuve |
|---|---|---|---|---|---|---|---|
| FE-001 | Syntaxe JS | Node installÃ© | `npm run check:js` | Aucun fichier JS invalide | AutomatisÃ© | OK | `check-js.mjs` |
| FE-002 | SÃ©curitÃ© DOM | Code frontend | `npm run check:js` | Pas d'`innerHTML` dangereux, pas de `eval` | AutomatisÃ© | OK | `check-js.mjs` |
| FE-003 | AccessibilitÃ© de base | Pages HTML | `npm run check:a11y` | Titres, labels, main, viewport prÃ©sents | AutomatisÃ© | OK | `check-accessibility.mjs` |
| FE-004 | Build production | DÃ©pendances installÃ©es | `npm run build` | Build Vite gÃ©nÃ©rÃ© | AutomatisÃ© | OK | CI |
| FE-005 | Navigation utilisateur | API simulÃ©e | Playwright | Dashboard/rÃ©servation/profil navigables | AutomatisÃ© | OK | `app.spec.js` |
| FE-006 | Navigation admin | Admin simulÃ© | Playwright | Dashboard admin accessible | AutomatisÃ© | OK | `app.spec.js` |
| FE-007 | Navigation technicien | Technicien simulÃ© | Playwright | Espace technicien accessible | AutomatisÃ© | OK | `app.spec.js` |
| FE-008 | PWA mobile | Smartphone | Ouvrir app mobile et session QR | Interface lisible, bottom nav cohÃ©rente | Manuel | OK | Recette mobile |
| FE-009 | Carte OpenStreetMap | AccÃ¨s Internet | Ouvrir rÃ©servation sur PC/mobile | Carte visible aprÃ¨s chargement | Manuel | OK partiel | `reservation.js` |

## 11. Tests CI/CD et qualitÃ©

| ID | Fonction testÃ©e | PrÃ©conditions | Ã‰tapes de test | RÃ©sultat attendu | Type | Statut | Preuve |
|---|---|---|---|---|---|---|---|
| CI-001 | Tests backend | Push/PR GitHub | Lancer workflow CI | `pytest` backend OK | AutomatisÃ© | OK | `.github/workflows/ci.yml` |
| CI-002 | QualitÃ© backend | Push/PR GitHub | Lancer Ruff | Aucun problÃ¨me bloquant | AutomatisÃ© | OK | CI |
| CI-003 | SchÃ©ma OpenAPI | Push/PR GitHub | GÃ©nÃ©rer et valider schema | OpenAPI valide | AutomatisÃ© | OK | CI |
| CI-004 | Checks dÃ©ploiement | Variables prod simulÃ©es | `manage.py check --deploy` | Pas d'erreur critique | AutomatisÃ© | OK | CI |
| CI-005 | Tests Raspberry | Push/PR GitHub | Compiler modules + pytest | Tests edge OK | AutomatisÃ© | OK | CI |
| CI-006 | Frontend verify | Changement frontend | `npm run verify` | JS, a11y, build, e2e OK | AutomatisÃ© | OK | CI |
| CI-007 | Docker compose prod | Push/PR GitHub | `docker compose config --quiet` | Compose valide | AutomatisÃ© | OK | CI |
| CI-008 | Documentation | Push/PR GitHub | Build Sphinx | Documentation construite | AutomatisÃ© | OK | CI |

## 12. Tests de recette dÃ©monstration

| ID | ScÃ©nario | PrÃ©conditions | Ã‰tapes rÃ©sumÃ©es | RÃ©sultat attendu | Type | Statut |
|---|---|---|---|---|---|---|
| DEMO-001 | RÃ©servation QR complÃ¨te | Stack lancÃ©e, utilisateur demo | RÃ©server, scanner QR, ouvrir, dÃ©tecter courant, arrÃªter | Session complÃ¨te visible backend/Grafana | Manuel + script | OK |
| DEMO-002 | Session mobile kiosk | Smartphone connectÃ©, QR kiosk | Scanner QR, choisir rÃ©servation, autoriser | Kiosk ouvre l'emplacement | Manuel | OK |
| DEMO-003 | RFID | Badge associÃ© | Badger pendant crÃ©neau valide | AccÃ¨s validÃ©, serrure ouverte | Manuel | OK selon matÃ©riel |
| DEMO-004 | SMS | TÃ©lÃ©phone renseignÃ© ou mode mail/log | GÃ©nÃ©rer code, saisir au kiosk | AccÃ¨s validÃ© | Manuel | OK |
| DEMO-005 | TÃ©lÃ©mÃ©trie continue | ESP32 ou simulateur | Publier mesures slot1 | Grafana affiche tempÃ©rature/humiditÃ©/courant/Ã©nergie | Manuel + simulation | OK |
| DEMO-006 | Alerte courant | Courant simulÃ© > 4 A | Publier tÃ©lÃ©mÃ©trie | Alerte visible | Simulation + manuel | OK |
| DEMO-007 | Mauvaise rÃ©servation | RÃ©servation hors borne/crÃ©neau | Tenter accÃ¨s | Refus clair | AutomatisÃ© + manuel | OK |
| DEMO-008 | Perte backend | Cache offline prÃªt | Couper backend | AccÃ¨s cached possible selon donnÃ©es | Manuel | Ã€ valider dÃ©mo |

## 13. CritÃ¨res d'acceptation principaux

| CritÃ¨re | Condition d'acceptation |
|---|---|
| RÃ©servation | Une rÃ©servation valide est crÃ©Ã©e uniquement sur un emplacement disponible |
| QR rÃ©servation | Le QR donne accÃ¨s uniquement Ã  la bonne rÃ©servation, au bon crÃ©neau et Ã  la bonne borne |
| QR borne mobile | Le QR lie temporairement un tÃ©lÃ©phone Ã  une borne, puis laisse l'utilisateur choisir une rÃ©servation compatible |
| RFID | Le badge ne donne accÃ¨s que si une rÃ©servation compatible existe |
| SMS | Le mode SMS est indisponible sans tÃ©lÃ©phone et limitÃ© par durÃ©e/essais |
| Serrure | La serrure s'ouvre aprÃ¨s validation d'accÃ¨s, pas avant |
| Charge | La charge passe en cours uniquement aprÃ¨s dÃ©tection de courant dans le prototype |
| MQTT | Les commandes critiques exigent un ACK en production |
| Supervision | Les mesures sont liÃ©es Ã  station, borne, emplacement et session quand disponible |
| SÃ©curitÃ© | Les secrets ne sont pas stockÃ©s en clair et les accÃ¨s sensibles sont limitÃ©s |
| Production | La stack dÃ©marre avec Docker, Nginx, PostgreSQL, Redis, backend, frontend et Grafana |

## 14. Tests Ã  rejouer avant dÃ©monstration

| Ordre | Test | Commande ou action |
|---:|---|---|
| 1 | VÃ©rifier les services serveur | `docker compose -f docker-compose.prod.yml ps` |
| 2 | VÃ©rifier backend | Ouvrir `/api/health/ready/` |
| 3 | VÃ©rifier frontend | Ouvrir l'application HTTPS |
| 4 | VÃ©rifier login admin | Connexion compte admin |
| 5 | VÃ©rifier rÃ©servation | CrÃ©er une rÃ©servation proche |
| 6 | VÃ©rifier kiosk | Ouvrir interface Raspberry sur Ã©cran |
| 7 | VÃ©rifier QR mobile | Scanner QR avec smartphone |
| 8 | VÃ©rifier MQTT | Observer logs bridge/kiosk |
| 9 | VÃ©rifier ESP32 | Connexion Wi-Fi/MQTT et tÃ©lÃ©mÃ©trie |
| 10 | VÃ©rifier Grafana | Voir mesures sur dashboard |
| 11 | VÃ©rifier arrÃªt | Stopper charge et clÃ´turer session |
| 12 | VÃ©rifier donnÃ©es rÃ©siduelles | S'assurer qu'aucune session ne reste bloquÃ©e |
