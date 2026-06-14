# Plan de tests réalisés sur le projet

Cette notice présente les tests mis en place et réalisés pendant le développement de la station de recharge intelligente.
Elle distingue les tests automatisés, les tests de configuration, les tests frontend, les tests Raspberry, les tests MQTT/ESP32, les tests de supervision et les recettes manuelles de démonstration.

Le but n'est pas seulement de prouver que l'application démarre. Le plan de tests vérifie que le système reste cohérent de bout en bout :

- création de compte ;
- réservation ;
- validation d'accès par QR, RFID, SMS ou session mobile ;
- déverrouillage de l'emplacement ;
- communication MQTT ;
- remontée de télémétrie ;
- supervision ;
- sécurité ;
- mode dégradé ;
- configuration de production.

## 1. Périmètre testé

### Composants concernés

| Composant | Rôle dans le projet | Type de test réalisé |
|---|---|---|
| Backend Django | API, réservations, sécurité, sessions, supervision | Tests unitaires, tests d'intégration, tests de configuration |
| Base PostgreSQL/TimescaleDB | Données métier et télémétrie | Tests d'ingestion, vérifications SQL, tests de rétention/configuration |
| Redis | Cache, sessions mobiles, Channels, tâches asynchrones | Tests indirects via API, session mobile et WebSocket |
| Frontend/PWA | Interface utilisateur, réservation, profil, session mobile | Tests JS, accessibilité, build, Playwright |
| Kiosk Raspberry | Interface tactile, RFID, cache offline, commandes MQTT | Tests unitaires Raspberry, tests manuels, tests d'intégration |
| ESP32 | Serrure, télémétrie, état de charge | Tests matériel, simulation MQTT, Wokwi, adaptation firmware |
| Mosquitto/MQTT | Commandes START/STOP/UNLOCK et télémétrie | Tests d'ACK, ACL, topics, ingestion |
| Grafana | Supervision et visualisation | Tests de provisioning, vérification dashboard |
| Nginx/TLS | Reverse proxy, HTTPS, durcissement | Tests de configuration et sécurité |
| Docker | Orchestration dev/prod | Validation Compose, tests de durcissement |

### Ce qui a été testé automatiquement

Les tests automatisés couvrent principalement :

- l'authentification ;
- les réservations ;
- les accès QR/SMS/RFID/session mobile ;
- l'administration ;
- l'ingestion MQTT ;
- les alertes ;
- la sécurité de configuration ;
- les dashboards Grafana ;
- le contrat Raspberry/MQTT ;
- les performances de requêtes ciblées ;
- le frontend et l'accessibilité de base.

### Ce qui reste testé manuellement

Certains points dépendent du matériel physique et ne peuvent pas être entièrement automatisés :

- lecture réelle du badge ACR122U ;
- action réelle du relais de serrure ;
- courant mesuré sur le capteur SEN0214 ;
- comportement réel des LED et du buzzer ;
- comportement réseau du Raspberry, de l'ESP32 et du smartphone dans le réseau de démonstration.

Ces points sont néanmoins préparés par des tests de simulation et par des contrats techniques documentés.

## 2. Tests automatisés backend

### Objectif

Vérifier que l'API Django respecte les règles métier, les règles de sécurité et les scénarios d'intégration principaux.

### Commande utilisée

Depuis le poste de développement :

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest
```

Dans la CI GitHub Actions :

```bash
cd backend
python -m pytest
```

### Fichiers de tests backend

| Fichier | Nombre indicatif de tests | Périmètre |
|---|---:|---|
| `backend/api/tests/test_admin_api.py` | 45 | Administration, utilisateurs, stations, réservations, supervision |
| `backend/api/tests/test_api_auth.py` | 9 | Connexion, refresh token, authentification API |
| `backend/api/tests/test_auth_profile.py` | 9 | Profil, consentements, changement de mot de passe |
| `backend/api/tests/test_channels_supervision.py` | 4 | WebSocket/Channels et supervision temps réel |
| `backend/api/tests/test_container_security_config.py` | 3 | Configuration sécurité des conteneurs |
| `backend/api/tests/test_deployment_checks.py` | 5 | Contrôles de déploiement Django |
| `backend/api/tests/test_end_to_end_charge_flow.py` | 2 | Parcours complet réservation -> kiosk -> MQTT -> télémétrie -> clôture |
| `backend/api/tests/test_grafana_provisioning.py` | 2 | Provisioning Grafana |
| `backend/api/tests/test_health_api.py` | 3 | Endpoints de santé |
| `backend/api/tests/test_mqtt_bridge_health.py` | 3 | Santé du bridge MQTT |
| `backend/api/tests/test_mqtt_ingestion.py` | 32 | Ingestion télémétrie, commandes, états ESP32 |
| `backend/api/tests/test_mqtt_security_config.py` | 3 | Sécurité MQTT |
| `backend/api/tests/test_mqtt_simulator.py` | 5 | Simulation télémétrie réaliste |
| `backend/api/tests/test_nginx_security_config.py` | 4 | Durcissement Nginx |
| `backend/api/tests/test_operational_alerts.py` | 12 | Politique d'alertes |
| `backend/api/tests/test_production_hardening.py` | 10 | Durcissement production |
| `backend/api/tests/test_public_pages.py` | 2 | Pages publiques |
| `backend/api/tests/test_query_performance.py` | 5 | Nombre de requêtes et performance ciblée |
| `backend/api/tests/test_reservations.py` | 26 | Création, disponibilité, créneaux, conflits |
| `backend/api/tests/test_semantic_graph.py` | 4 | Graphe métier sémantique en développement |
| `backend/api/tests/test_serializers.py` | 6 | Sérialisation API |
| `backend/api/tests/test_sms_access_policy.py` | 4 | Politique code SMS |
| `backend/api/tests/test_sms_service.py` | 6 | Service SMS abstrait |
| `backend/api/tests/test_terminal_auth.py` | 42 | Authentification terminal QR/SMS/RFID/session mobile |

Total indicatif : environ 246 tests backend déclarés.

### Exemples de scénarios couverts

#### Création et validation de réservation

Objectif :

- vérifier qu'un utilisateur peut créer une réservation ;
- vérifier qu'un emplacement est disponible ;
- empêcher les réservations concurrentes ;
- respecter les créneaux et les marges métier.

Fichiers concernés :

- `backend/api/tests/test_reservations.py` ;
- `backend/api/reservation_rules.py` ;
- `backend/api/views.py`.

Résultat attendu :

- une réservation valide est acceptée ;
- une réservation en conflit est refusée ;
- les dates, statuts et moyens d'accès restent cohérents.

#### Authentification terminal

Objectif :

- vérifier l'accès par QR de réservation ;
- vérifier l'accès par code SMS ;
- vérifier l'accès par badge RFID ;
- vérifier la session mobile QR borne -> téléphone -> réservation ;
- refuser une réservation sur la mauvaise station ou la mauvaise borne.

Fichiers concernés :

- `backend/api/tests/test_terminal_auth.py` ;
- `backend/api/tests/test_end_to_end_charge_flow.py`.

Résultat attendu :

- le terminal obtient une autorisation uniquement si la réservation correspond à la bonne station, à la bonne borne et au bon créneau ;
- une session mobile autorisée peut être consommée par le kiosk ;
- une session incohérente ou expirée est refusée.

#### Ingestion MQTT

Objectif :

- vérifier que le backend reçoit les télémétries ;
- rattacher les mesures à la station, à la borne, à l'emplacement et à la session ;
- créer les alertes lorsque les seuils sont dépassés ;
- mettre à jour les états des ESP32.

Fichiers concernés :

- `backend/api/tests/test_mqtt_ingestion.py` ;
- `backend/api/mqtt.py` ;
- `backend/api/models.py`.

Résultat attendu :

- les mesures sont enregistrées ;
- les alertes sont créées ou levées selon la politique définie ;
- les dashboards peuvent exploiter les données.

#### Politique SMS

Objectif :

- vérifier que le code SMS n'est disponible que si l'utilisateur possède un téléphone ;
- vérifier le service SMS abstrait ;
- vérifier le mode développement en log/console ;
- vérifier la politique d'envoi et de renvoi.

Fichiers concernés :

- `backend/api/tests/test_sms_access_policy.py` ;
- `backend/api/tests/test_sms_service.py` ;
- `backend/api/services/sms.py`.

Résultat attendu :

- l'accès SMS est désactivé sans téléphone ;
- aucun secret n'est stocké en clair ;
- le service peut être remplacé par Twilio, Brevo ou un autre fournisseur.

## 3. Tests Raspberry / kiosk

### Objectif

Tester la logique locale du Raspberry sans dépendre systématiquement du matériel réel.

### Commande utilisée

```powershell
.\.venv\Scripts\python.exe -m pytest raspberry\tests -q
```

Dans la CI :

```bash
python -m pytest raspberry/tests -q
```

### Fichiers de tests

| Fichier | Nombre indicatif de tests | Périmètre |
|---|---:|---|
| `raspberry/tests/test_charge_state.py` | 7 | Machine d'état de charge |
| `raspberry/tests/test_mqtt_client.py` | 10 | Client MQTT, ACK, timeouts |
| `raspberry/tests/test_mqtt_contract.py` | 6 | Contrat payload MQTT |

Total indicatif : 23 tests Raspberry.

### Compilation des modules Raspberry

La CI vérifie aussi que les modules Python du kiosk compilent :

```bash
python -m py_compile \
  raspberry/app/charge_state.py \
  raspberry/app/main.py \
  raspberry/app/mqtt_contract.py \
  raspberry/app/mqtt_client.py \
  raspberry/app/offline_store.py \
  raspberry/app/rfid_reader.py
```

### Scénarios couverts

#### Commande acceptée avec ACK

Objectif :

- envoyer une commande MQTT ;
- attendre un ACK avec le bon `command_id` ;
- valider que la commande est confirmée.

Résultat attendu :

- si l'ACK est reçu, la commande est considérée comme confirmée.

#### Commande refusée sans ACK en production

Objectif :

- vérifier le comportement lorsque `MQTT_ACK_REQUIRED=true` ;
- empêcher une validation silencieuse si l'ESP32 ne confirme pas.

Résultat attendu :

- l'interface signale que la commande n'a pas été confirmée.

#### Mode développement sans ACK obligatoire

Objectif :

- permettre les essais lorsque l'ESP32 n'est pas encore connecté ;
- ne pas bloquer toute la démonstration pendant l'intégration.

Résultat attendu :

- la commande peut être acceptée en mode dégradé de développement, mais la configuration production impose l'ACK.

## 4. Tests frontend et PWA

### Objectif

Vérifier que les pages HTML, CSS et JavaScript restent cohérentes, accessibles et compatibles avec un usage web/mobile.

### Commandes utilisées

```powershell
cd frontend
npm ci
npm run check:js
npm run check:a11y
npm run build
npm run e2e
```

Commande globale :

```powershell
cd frontend
npm run verify
```

### Scripts utilisés

| Script | Rôle |
|---|---|
| `frontend/scripts/check-js.mjs` | Vérifie la syntaxe JS et bloque certaines pratiques dangereuses |
| `frontend/scripts/check-accessibility.mjs` | Vérifie les bases d'accessibilité HTML |
| `frontend/tests/e2e/app.spec.js` | Tests Playwright avec API simulée |
| `frontend/vite.config.js` | Build et preview frontend |

### Vérifications JavaScript

Le script `check-js.mjs` vérifie notamment :

- absence de `eval()` ;
- absence de `console.log()` dans les fichiers contrôlés ;
- absence de `outerHTML` ;
- absence de `insertAdjacentHTML()` ;
- interdiction de `innerHTML` non contrôlé ;
- syntaxe JavaScript valide.

Objectif sécurité :

- réduire les risques XSS ;
- éviter les traces de debug ;
- maintenir un code frontend plus propre.

### Vérifications accessibilité

Le script `check-accessibility.mjs` vérifie notamment :

- présence de `lang="fr"` ;
- présence d'une meta viewport ;
- présence d'un titre ;
- présence d'un `main` ;
- présence d'un `h1` ;
- labels accessibles sur boutons, liens et champs ;
- absence de gestionnaires inline `on*` ;
- absence de `tabindex` positif.

Objectif :

- éviter les oublis simples qui dégradent l'expérience utilisateur ;
- rendre l'application plus présentable et plus proche d'un niveau production.

### Tests Playwright

Les tests Playwright utilisent une API simulée pour vérifier les parcours frontend sans dépendre du backend réel.

Scénarios vérifiés :

- connexion utilisateur ;
- navigation tableau de bord ;
- réservation ;
- affichage des stations ;
- session mobile ;
- vues administrateur ;
- vues technicien.

Limite :

- ces tests valident l'interface et les appels attendus ;
- ils ne remplacent pas un test complet avec l'API réelle, le Raspberry et l'ESP32.

## 5. Tests de bout en bout

### Objectif

Valider le parcours réel :

```text
Réservation -> session mobile -> kiosk -> MQTT -> télémétrie -> supervision -> arrêt
```

### Test automatisé backend

Fichier principal :

```text
backend/api/tests/test_end_to_end_charge_flow.py
```

Scénario couvert :

1. création d'une réservation QR ;
2. création d'une session mobile par le terminal ;
3. connexion utilisateur ;
4. sélection d'une réservation compatible ;
5. autorisation mobile ;
6. consommation par le kiosk ;
7. commande MQTT ;
8. télémétrie sur l'emplacement réservé ;
9. arrêt et clôture de session.

### Script de recette démonstration

Fichier :

```text
scripts/run-demo-scenario.ps1
```

Commande :

```powershell
.\scripts\run-demo-scenario.ps1 -Reference DEMOQR1 -Emplacement 1 -TelemetryCount 5
```

Étapes exécutées par le script :

- démarrage des services Docker si demandé ;
- préparation d'une réservation QR de démonstration ;
- création d'une session mobile côté kiosk ;
- connexion mobile utilisateur ;
- récupération des réservations compatibles ;
- autorisation de la réservation ;
- consommation par le kiosk ;
- commande `START` MQTT ;
- simulation de télémétrie limitée à l'emplacement réservé ;
- commande `STOP` MQTT ;
- clôture de session ;
- affichage de l'état final backend.

Résultat attendu :

- une seule réservation est utilisée ;
- un seul emplacement reçoit la télémétrie ;
- la session est clôturée proprement ;
- Grafana peut afficher les mesures.

## 6. Tests MQTT, télémétrie et supervision

### Objectif

Vérifier que les messages envoyés par les ESP32 ou par le simulateur sont correctement ingérés, stockés et affichés.

### Simulation MQTT locale

Commande :

```bash
docker compose --profile simulation run --rm mqtt-simulator
```

Autre commande utile :

```bash
docker compose exec -d backend python manage.py simulate_mqtt_telemetry --slots slot1 --scenario normal --interval 2 --count 0
```

Objectif :

- simuler une télémétrie réaliste sans ESP32 ;
- tester Grafana ;
- tester l'ingestion backend ;
- tester les seuils d'alerte.

### Vérification des logs

```bash
docker compose logs -f mqtt-bridge
docker compose logs -f celery
docker compose logs -f backend
```

Résultat attendu :

- les messages MQTT sont reçus ;
- l'ingestion ne produit pas d'erreur ;
- les mesures apparaissent en base ;
- les dashboards Grafana affichent les séries temporelles.

### Vérification en base

Exemple de contrôle rapide :

```bash
docker compose exec backend python manage.py shell -c "from django.utils import timezone; from datetime import timedelta; from api.models import CapteurData; now=timezone.now(); print(CapteurData.objects.filter(timestamp__gte=now-timedelta(minutes=1)).count())"
```

Résultat attendu :

- le nombre de mesures récentes augmente lorsque la simulation ou l'ESP32 publie.

### Grafana

Tests réalisés :

- vérification du provisioning des dashboards ;
- vérification des filtres station/borne/emplacement ;
- vérification des panels de température, humidité, courant, tension, puissance et énergie ;
- vérification des états d'équipement ;
- vérification de la séparation entre supervision applicative et supervision Grafana.

Fichiers concernés :

- `backend/api/tests/test_grafana_provisioning.py` ;
- `grafana/dashboards/station-supervision.json`.

## 7. Tests sécurité

### Objectif

Vérifier que le projet respecte les principaux choix `security by design`.

### Tests automatisés

| Fichier | Périmètre |
|---|---|
| `backend/api/tests/test_deployment_checks.py` | Sécurité Django en production |
| `backend/api/tests/test_nginx_security_config.py` | Headers, TLS, durcissement Nginx |
| `backend/api/tests/test_mqtt_security_config.py` | MQTT ACK, identifiants, configuration |
| `backend/api/tests/test_container_security_config.py` | Exposition et sécurité des conteneurs |
| `backend/api/tests/test_production_hardening.py` | Durcissement global |
| `backend/api/tests/test_sms_access_policy.py` | Politique SMS et téléphone requis |

### Commandes utilisées

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest api\tests\test_deployment_checks.py
..\.venv\Scripts\python.exe -m pytest api\tests\test_nginx_security_config.py
..\.venv\Scripts\python.exe -m pytest api\tests\test_mqtt_security_config.py
```

### Contrôle Django production

Dans la CI :

```bash
python manage.py check --deploy
```

Variables testées en CI :

- `DEBUG=False` ;
- `SESSION_COOKIE_SECURE=True` ;
- `CSRF_COOKIE_SECURE=True` ;
- `JWT_REFRESH_COOKIE_SECURE=True` ;
- `MQTT_ACK_REQUIRED=True` ;
- `MQTT_TLS_ENABLED=True` ;
- `SECURE_HSTS_SECONDS=31536000` ;
- `SECURE_HSTS_INCLUDE_SUBDOMAINS=True` ;
- `SECURE_HSTS_PRELOAD=True`.

### Contrôles frontend sécurité

Le script `check-js.mjs` limite les pratiques dangereuses côté navigateur :

- pas de `eval()` ;
- pas d'injection HTML non contrôlée ;
- pas de logs console ;
- pas de gestion DOM trop risquée.

Résultat attendu :

- réduire les risques XSS ;
- éviter les traces de développement ;
- fiabiliser les pages avant démonstration.

## 8. Tests de configuration production

### Docker Compose

Commande :

```bash
docker compose --env-file .env.example -f docker-compose.prod.yml config --quiet
```

Objectif :

- vérifier que le fichier de production est syntaxiquement valide ;
- vérifier que les variables attendues sont bien interprétées.

### Scripts de sauvegarde/restauration

Commandes CI :

```bash
bash -n scripts/backup-prod.sh
bash -n scripts/restore-prod.sh
```

Objectif :

- vérifier la syntaxe des scripts ;
- éviter une erreur bloquante le jour où une sauvegarde ou restauration est nécessaire.

### Nginx

Tests réalisés :

- validation de configuration ;
- vérification des headers ;
- vérification des limites de requête ;
- vérification du TLS/HSTS côté configuration.

Fichiers concernés :

- `nginx/nginx.conf` ;
- `nginx/conf.d/station.conf` ;
- `backend/api/tests/test_nginx_security_config.py`.

## 9. Tests de documentation et qualité

### Documentation Sphinx

Commande :

```powershell
$env:DEBUG="True"
$env:SECRET_KEY="docs-local-secret-key-not-for-production"
.\.venv\Scripts\python.exe -m sphinx -b html docs\source docs\build\html
```

Dans la CI :

```bash
python -m sphinx -b html docs/source docs/build/html
```

Objectif :

- vérifier que la documentation technique se construit ;
- éviter les références cassées ;
- maintenir une documentation exploitable.

### Qualité Python

Commande :

```powershell
cd backend
..\.venv\Scripts\python.exe -m ruff check .
```

Dans la CI :

```bash
python -m ruff check .
```

Objectif :

- détecter les imports inutilisés ;
- détecter des erreurs Python probables ;
- homogénéiser le style ;
- éviter certains pièges courants.

### Couverture documentaire

Commande CI :

```bash
python -m interrogate api
```

Objectif :

- vérifier que les modules importants restent documentés ;
- améliorer la maintenabilité du backend.

## 10. Tests manuels matériel

### Badge RFID

Procédure testée :

1. associer un badge RFID à un compte utilisateur ;
2. créer une réservation avec accès RFID ;
3. attendre le créneau de réservation ;
4. présenter le badge sur le lecteur ACR122U ;
5. vérifier que le kiosk valide l'accès ;
6. vérifier que la serrure reçoit la commande de déverrouillage.

Résultat attendu :

- le badge est reconnu ;
- l'utilisateur est retrouvé ;
- une réservation compatible est trouvée ;
- l'emplacement est autorisé.

### Serrure

Procédure testée avec prototype :

1. accès validé par QR, RFID ou session mobile ;
2. publication d'une commande de déverrouillage ;
3. activation du relais côté ESP32 ;
4. retour d'état ou ACK MQTT.

Résultat attendu :

- la serrure s'ouvre après validation d'accès ;
- la session reste en attente de branchement ;
- la charge ne doit pas être considérée comme active tant qu'aucun courant n'est détecté.

### Détection de courant

Procédure testée :

1. démarrer le firmware ESP32 ;
2. calibrer le zéro courant ;
3. activer le générateur pour simuler la charge ;
4. vérifier la remontée du courant ;
5. vérifier le calcul de puissance ;
6. vérifier l'énergie cumulée.

Résultat attendu :

- courant détecté lorsque le générateur est actif ;
- puissance calculée avec `P = U x I` ;
- énergie cumulée en kWh ;
- passage de l'état `waiting_plug` à `charging`.

### LED et buzzer

Procédure testée ou prévue :

- LED verte : état normal ou charge ;
- LED jaune : alerte modérée ;
- LED rouge : alerte grave ;
- buzzer : anomalie critique.

Résultat attendu :

- l'état physique est lisible localement sans ouvrir Grafana.

## 11. Tests de démonstration avant soutenance

### Checklist courte

Avant une démonstration, lancer :

```bash
docker compose -f docker-compose.prod.yml ps
```

Vérifier :

- backend actif ;
- frontend actif ;
- reverse proxy actif ;
- PostgreSQL actif ;
- Redis actif ;
- Celery actif ;
- MQTT bridge actif ;
- Grafana actif ;
- Mailpit actif si test mail.

### Vérifier l'application

Depuis le PC :

- ouvrir l'application HTTPS ;
- se connecter avec le compte admin ;
- créer une réservation ;
- vérifier la carte ;
- vérifier le dashboard admin ;
- vérifier Grafana.

Depuis le smartphone :

- ouvrir la même origine publique que celle du QR mobile ;
- se connecter ;
- scanner un QR de session mobile ;
- sélectionner la réservation compatible.

Depuis le Raspberry :

- vérifier que Chromium est lancé sur `localhost:9000` ;
- vérifier que le QR mobile pointe vers l'adresse accessible au smartphone ;
- vérifier que le lecteur RFID est détecté si branché.

Depuis l'ESP32 :

- vérifier la connexion Wi-Fi ;
- vérifier la connexion MQTT ;
- vérifier les publications de télémétrie ;
- vérifier les ACK de commandes.

## 12. Scénarios de recette fonctionnelle

### Scénario 1 : réservation QR

| Étape | Action | Résultat attendu |
|---|---|---|
| 1 | L'utilisateur crée une réservation | Réservation confirmée |
| 2 | Le QR de réservation est généré | QR disponible dans l'application et envoyable par mail |
| 3 | Le QR est présenté au kiosk | Accès validé si créneau et borne corrects |
| 4 | La serrure s'ouvre | Session en attente de branchement |
| 5 | Un courant est détecté | Session en charge |
| 6 | La charge est arrêtée | Session clôturée |

### Scénario 2 : session mobile QR borne

| Étape | Action | Résultat attendu |
|---|---|---|
| 1 | La borne affiche un QR temporaire | Session mobile `pending` |
| 2 | Le téléphone scanne le QR | Page mobile ouverte |
| 3 | L'utilisateur se connecte | Réservations compatibles affichées |
| 4 | L'utilisateur choisit une réservation | Session mobile `authorized` |
| 5 | La borne consomme l'autorisation | Session mobile `consumed` |
| 6 | L'emplacement est ouvert | Attente branchement |

### Scénario 3 : accès RFID

| Étape | Action | Résultat attendu |
|---|---|---|
| 1 | L'utilisateur associe un badge | UID lié au compte |
| 2 | Une réservation compatible existe | Accès possible |
| 3 | L'utilisateur présente le badge | Backend ou cache offline valide |
| 4 | La serrure s'ouvre | Session en attente branchement |

### Scénario 4 : code SMS

| Étape | Action | Résultat attendu |
|---|---|---|
| 1 | L'utilisateur possède un téléphone | Option SMS disponible |
| 2 | Le code est généré | Secret stocké sans clair |
| 3 | Le code est envoyé ou loggé en dev | Utilisateur peut tester |
| 4 | Le code est saisi au kiosk | Accès validé si correct |
| 5 | Trop d'essais sont réalisés | Rate limiting ou refus |

### Scénario 5 : mode dégradé

| Étape | Action | Résultat attendu |
|---|---|---|
| 1 | Le Raspberry a synchronisé le cache | Réservations récentes disponibles localement |
| 2 | Le backend devient indisponible | Le kiosk bascule sur le cache |
| 3 | L'utilisateur utilise un accès connu | Validation locale possible |
| 4 | L'ESP32 reste joignable via MQTT local | Commande possible |
| 5 | Le backend revient | Synchronisation et reprise normale |

## 13. Limites et risques restants

### Matériel incomplet

Certains capteurs prévus dans le cahier des charges ne sont pas encore entièrement câblés :

- capteur d'ouverture du boîtier ;
- capteur de présence câble dédié ;
- tension réelle si elle reste fixe dans le prototype ;
- intrusion physique complète.

Conséquence :

- certains états sont simulés ou déduits à partir du courant ;
- le scénario physique reste cohérent pour un prototype, mais doit être complété pour une industrialisation.

### Tests mobiles réels

Les tests Playwright valident l'interface en navigateur, mais une vraie recette mobile reste nécessaire :

- Firefox/Chrome Android ;
- certificat local installé ;
- hotspot ou réseau commun ;
- QR session mobile ;
- PWA installée ou utilisée en navigateur.

### Réseau de démonstration

La démonstration dépend fortement de l'adressage réseau :

- serveur Debian ;
- Raspberry ;
- ESP32 ;
- smartphone ;
- PC de présentation.

Un changement de hotspot ou d'IP peut nécessiter d'aligner :

- `FRONTEND_BASE_URL` ;
- `MOBILE_FRONTEND_BASE_URL` ;
- `BACKEND_API_BASE_URL` ;
- `MQTT_HOST` ;
- certificats HTTPS.

## 14. Conclusion

Le projet dispose d'un plan de tests structuré couvrant :

- les règles métier ;
- les accès utilisateur ;
- le terminal Raspberry ;
- les échanges MQTT ;
- la télémétrie ;
- la supervision ;
- la sécurité ;
- la configuration de production ;
- l'expérience frontend/PWA.

Les tests automatisés sécurisent les régressions logicielles.
Les tests manuels et les simulations complètent la validation pour les parties dépendantes du matériel physique.

Pour la soutenance, les points les plus valorisants sont :

- le scénario de bout en bout ;
- la séparation entre tests automatisés et tests matériels ;
- la présence de tests sécurité/production ;
- l'utilisation d'une simulation réaliste pour compenser l'absence temporaire de matériel ;
- la traçabilité entre code, tests, documentation et démonstration.
