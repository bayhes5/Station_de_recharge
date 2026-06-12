# Plan de tests rÃ©alisÃ©s sur le projet

Cette notice prÃ©sente les tests mis en place et rÃ©alisÃ©s pendant le dÃ©veloppement de la station de recharge intelligente.
Elle distingue les tests automatisÃ©s, les tests de configuration, les tests frontend, les tests Raspberry, les tests MQTT/ESP32, les tests de supervision et les recettes manuelles de dÃ©monstration.

Le but n'est pas seulement de prouver que l'application dÃ©marre. Le plan de tests vÃ©rifie que le systÃ¨me reste cohÃ©rent de bout en bout :

- crÃ©ation de compte ;
- rÃ©servation ;
- validation d'accÃ¨s par QR, RFID, SMS ou session mobile ;
- dÃ©verrouillage de l'emplacement ;
- communication MQTT ;
- remontÃ©e de tÃ©lÃ©mÃ©trie ;
- supervision ;
- sÃ©curitÃ© ;
- mode dÃ©gradÃ© ;
- configuration de production.

## 1. PÃ©rimÃ¨tre testÃ©

### Composants concernÃ©s

| Composant | RÃ´le dans le projet | Type de test rÃ©alisÃ© |
|---|---|---|
| Backend Django | API, rÃ©servations, sÃ©curitÃ©, sessions, supervision | Tests unitaires, tests d'intÃ©gration, tests de configuration |
| Base PostgreSQL/TimescaleDB | DonnÃ©es mÃ©tier et tÃ©lÃ©mÃ©trie | Tests d'ingestion, vÃ©rifications SQL, tests de rÃ©tention/configuration |
| Redis | Cache, sessions mobiles, Channels, tÃ¢ches asynchrones | Tests indirects via API, session mobile et WebSocket |
| Frontend/PWA | Interface utilisateur, rÃ©servation, profil, session mobile | Tests JS, accessibilitÃ©, build, Playwright |
| Kiosk Raspberry | Interface tactile, RFID, cache offline, commandes MQTT | Tests unitaires Raspberry, tests manuels, tests d'intÃ©gration |
| ESP32 | Serrure, tÃ©lÃ©mÃ©trie, Ã©tat de charge | Tests matÃ©riel, simulation MQTT, Wokwi, adaptation firmware |
| Mosquitto/MQTT | Commandes START/STOP/UNLOCK et tÃ©lÃ©mÃ©trie | Tests d'ACK, ACL, topics, ingestion |
| Grafana | Supervision et visualisation | Tests de provisioning, vÃ©rification dashboard |
| Nginx/TLS | Reverse proxy, HTTPS, durcissement | Tests de configuration et sÃ©curitÃ© |
| Docker | Orchestration dev/prod | Validation Compose, tests de durcissement |

### Ce qui a Ã©tÃ© testÃ© automatiquement

Les tests automatisÃ©s couvrent principalement :

- l'authentification ;
- les rÃ©servations ;
- les accÃ¨s QR/SMS/RFID/session mobile ;
- l'administration ;
- l'ingestion MQTT ;
- les alertes ;
- la sÃ©curitÃ© de configuration ;
- les dashboards Grafana ;
- le contrat Raspberry/MQTT ;
- les performances de requÃªtes ciblÃ©es ;
- le frontend et l'accessibilitÃ© de base.

### Ce qui reste testÃ© manuellement

Certains points dÃ©pendent du matÃ©riel physique et ne peuvent pas Ãªtre entiÃ¨rement automatisÃ©s :

- lecture rÃ©elle du badge ACR122U ;
- action rÃ©elle du relais de serrure ;
- courant mesurÃ© sur le capteur SEN0214 ;
- comportement rÃ©el des LED et du buzzer ;
- comportement rÃ©seau du Raspberry, de l'ESP32 et du smartphone dans le rÃ©seau de dÃ©monstration.

Ces points sont nÃ©anmoins prÃ©parÃ©s par des tests de simulation et par des contrats techniques documentÃ©s.

## 2. Tests automatisÃ©s backend

### Objectif

VÃ©rifier que l'API Django respecte les rÃ¨gles mÃ©tier, les rÃ¨gles de sÃ©curitÃ© et les scÃ©narios d'intÃ©gration principaux.

### Commande utilisÃ©e

Depuis le poste de dÃ©veloppement :

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

| Fichier | Nombre indicatif de tests | PÃ©rimÃ¨tre |
|---|---:|---|
| `backend/api/tests/test_admin_api.py` | 45 | Administration, utilisateurs, stations, rÃ©servations, supervision |
| `backend/api/tests/test_api_auth.py` | 9 | Connexion, refresh token, authentification API |
| `backend/api/tests/test_auth_profile.py` | 9 | Profil, consentements, changement de mot de passe |
| `backend/api/tests/test_channels_supervision.py` | 4 | WebSocket/Channels et supervision temps rÃ©el |
| `backend/api/tests/test_container_security_config.py` | 3 | Configuration sÃ©curitÃ© des conteneurs |
| `backend/api/tests/test_deployment_checks.py` | 5 | ContrÃ´les de dÃ©ploiement Django |
| `backend/api/tests/test_end_to_end_charge_flow.py` | 2 | Parcours complet rÃ©servation -> kiosk -> MQTT -> tÃ©lÃ©mÃ©trie -> clÃ´ture |
| `backend/api/tests/test_grafana_provisioning.py` | 2 | Provisioning Grafana |
| `backend/api/tests/test_health_api.py` | 3 | Endpoints de santÃ© |
| `backend/api/tests/test_mqtt_bridge_health.py` | 3 | SantÃ© du bridge MQTT |
| `backend/api/tests/test_mqtt_ingestion.py` | 32 | Ingestion tÃ©lÃ©mÃ©trie, commandes, Ã©tats ESP32 |
| `backend/api/tests/test_mqtt_security_config.py` | 3 | SÃ©curitÃ© MQTT |
| `backend/api/tests/test_mqtt_simulator.py` | 5 | Simulation tÃ©lÃ©mÃ©trie rÃ©aliste |
| `backend/api/tests/test_nginx_security_config.py` | 4 | Durcissement Nginx |
| `backend/api/tests/test_operational_alerts.py` | 12 | Politique d'alertes |
| `backend/api/tests/test_production_hardening.py` | 10 | Durcissement production |
| `backend/api/tests/test_public_pages.py` | 2 | Pages publiques |
| `backend/api/tests/test_query_performance.py` | 5 | Nombre de requÃªtes et performance ciblÃ©e |
| `backend/api/tests/test_reservations.py` | 26 | CrÃ©ation, disponibilitÃ©, crÃ©neaux, conflits |
| `backend/api/tests/test_semantic_graph.py` | 4 | Graphe mÃ©tier sÃ©mantique en dÃ©veloppement |
| `backend/api/tests/test_serializers.py` | 6 | SÃ©rialisation API |
| `backend/api/tests/test_sms_access_policy.py` | 4 | Politique code SMS |
| `backend/api/tests/test_sms_service.py` | 6 | Service SMS abstrait |
| `backend/api/tests/test_terminal_auth.py` | 42 | Authentification terminal QR/SMS/RFID/session mobile |

Total indicatif : environ 246 tests backend dÃ©clarÃ©s.

### Exemples de scÃ©narios couverts

#### CrÃ©ation et validation de rÃ©servation

Objectif :

- vÃ©rifier qu'un utilisateur peut crÃ©er une rÃ©servation ;
- vÃ©rifier qu'un emplacement est disponible ;
- empÃªcher les rÃ©servations concurrentes ;
- respecter les crÃ©neaux et les marges mÃ©tier.

Fichiers concernÃ©s :

- `backend/api/tests/test_reservations.py` ;
- `backend/api/reservation_rules.py` ;
- `backend/api/views.py`.

RÃ©sultat attendu :

- une rÃ©servation valide est acceptÃ©e ;
- une rÃ©servation en conflit est refusÃ©e ;
- les dates, statuts et moyens d'accÃ¨s restent cohÃ©rents.

#### Authentification terminal

Objectif :

- vÃ©rifier l'accÃ¨s par QR de rÃ©servation ;
- vÃ©rifier l'accÃ¨s par code SMS ;
- vÃ©rifier l'accÃ¨s par badge RFID ;
- vÃ©rifier la session mobile QR borne -> tÃ©lÃ©phone -> rÃ©servation ;
- refuser une rÃ©servation sur la mauvaise station ou la mauvaise borne.

Fichiers concernÃ©s :

- `backend/api/tests/test_terminal_auth.py` ;
- `backend/api/tests/test_end_to_end_charge_flow.py`.

RÃ©sultat attendu :

- le terminal obtient une autorisation uniquement si la rÃ©servation correspond Ã  la bonne station, Ã  la bonne borne et au bon crÃ©neau ;
- une session mobile autorisÃ©e peut Ãªtre consommÃ©e par le kiosk ;
- une session incohÃ©rente ou expirÃ©e est refusÃ©e.

#### Ingestion MQTT

Objectif :

- vÃ©rifier que le backend reÃ§oit les tÃ©lÃ©mÃ©tries ;
- rattacher les mesures Ã  la station, Ã  la borne, Ã  l'emplacement et Ã  la session ;
- crÃ©er les alertes lorsque les seuils sont dÃ©passÃ©s ;
- mettre Ã  jour les Ã©tats des ESP32.

Fichiers concernÃ©s :

- `backend/api/tests/test_mqtt_ingestion.py` ;
- `backend/api/mqtt.py` ;
- `backend/api/models.py`.

RÃ©sultat attendu :

- les mesures sont enregistrÃ©es ;
- les alertes sont crÃ©Ã©es ou levÃ©es selon la politique dÃ©finie ;
- les dashboards peuvent exploiter les donnÃ©es.

#### Politique SMS

Objectif :

- vÃ©rifier que le code SMS n'est disponible que si l'utilisateur possÃ¨de un tÃ©lÃ©phone ;
- vÃ©rifier le service SMS abstrait ;
- vÃ©rifier le mode dÃ©veloppement en log/console ;
- vÃ©rifier la politique d'envoi et de renvoi.

Fichiers concernÃ©s :

- `backend/api/tests/test_sms_access_policy.py` ;
- `backend/api/tests/test_sms_service.py` ;
- `backend/api/services/sms.py`.

RÃ©sultat attendu :

- l'accÃ¨s SMS est dÃ©sactivÃ© sans tÃ©lÃ©phone ;
- aucun secret n'est stockÃ© en clair ;
- le service peut Ãªtre remplacÃ© par Twilio, Brevo ou un autre fournisseur.

## 3. Tests Raspberry / kiosk

### Objectif

Tester la logique locale du Raspberry sans dÃ©pendre systÃ©matiquement du matÃ©riel rÃ©el.

### Commande utilisÃ©e

```powershell
.\.venv\Scripts\python.exe -m pytest raspberry\tests -q
```

Dans la CI :

```bash
python -m pytest raspberry/tests -q
```

### Fichiers de tests

| Fichier | Nombre indicatif de tests | PÃ©rimÃ¨tre |
|---|---:|---|
| `raspberry/tests/test_charge_state.py` | 7 | Machine d'Ã©tat de charge |
| `raspberry/tests/test_mqtt_client.py` | 10 | Client MQTT, ACK, timeouts |
| `raspberry/tests/test_mqtt_contract.py` | 6 | Contrat payload MQTT |

Total indicatif : 23 tests Raspberry.

### Compilation des modules Raspberry

La CI vÃ©rifie aussi que les modules Python du kiosk compilent :

```bash
python -m py_compile \
  raspberry/app/charge_state.py \
  raspberry/app/main.py \
  raspberry/app/mqtt_contract.py \
  raspberry/app/mqtt_client.py \
  raspberry/app/offline_store.py \
  raspberry/app/rfid_reader.py
```

### ScÃ©narios couverts

#### Commande acceptÃ©e avec ACK

Objectif :

- envoyer une commande MQTT ;
- attendre un ACK avec le bon `command_id` ;
- valider que la commande est confirmÃ©e.

RÃ©sultat attendu :

- si l'ACK est reÃ§u, la commande est considÃ©rÃ©e comme confirmÃ©e.

#### Commande refusÃ©e sans ACK en production

Objectif :

- vÃ©rifier le comportement lorsque `MQTT_ACK_REQUIRED=true` ;
- empÃªcher une validation silencieuse si l'ESP32 ne confirme pas.

RÃ©sultat attendu :

- l'interface signale que la commande n'a pas Ã©tÃ© confirmÃ©e.

#### Mode dÃ©veloppement sans ACK obligatoire

Objectif :

- permettre les essais lorsque l'ESP32 n'est pas encore connectÃ© ;
- ne pas bloquer toute la dÃ©monstration pendant l'intÃ©gration.

RÃ©sultat attendu :

- la commande peut Ãªtre acceptÃ©e en mode dÃ©gradÃ© de dÃ©veloppement, mais la configuration production impose l'ACK.

## 4. Tests frontend et PWA

### Objectif

VÃ©rifier que les pages HTML, CSS et JavaScript restent cohÃ©rentes, accessibles et compatibles avec un usage web/mobile.

### Commandes utilisÃ©es

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

### Scripts utilisÃ©s

| Script | RÃ´le |
|---|---|
| `frontend/scripts/check-js.mjs` | VÃ©rifie la syntaxe JS et bloque certaines pratiques dangereuses |
| `frontend/scripts/check-accessibility.mjs` | VÃ©rifie les bases d'accessibilitÃ© HTML |
| `frontend/tests/e2e/app.spec.js` | Tests Playwright avec API simulÃ©e |
| `frontend/vite.config.js` | Build et preview frontend |

### VÃ©rifications JavaScript

Le script `check-js.mjs` vÃ©rifie notamment :

- absence de `eval()` ;
- absence de `console.log()` dans les fichiers contrÃ´lÃ©s ;
- absence de `outerHTML` ;
- absence de `insertAdjacentHTML()` ;
- interdiction de `innerHTML` non contrÃ´lÃ© ;
- syntaxe JavaScript valide.

Objectif sÃ©curitÃ© :

- rÃ©duire les risques XSS ;
- Ã©viter les traces de debug ;
- maintenir un code frontend plus propre.

### VÃ©rifications accessibilitÃ©

Le script `check-accessibility.mjs` vÃ©rifie notamment :

- prÃ©sence de `lang="fr"` ;
- prÃ©sence d'une meta viewport ;
- prÃ©sence d'un titre ;
- prÃ©sence d'un `main` ;
- prÃ©sence d'un `h1` ;
- labels accessibles sur boutons, liens et champs ;
- absence de gestionnaires inline `on*` ;
- absence de `tabindex` positif.

Objectif :

- Ã©viter les oublis simples qui dÃ©gradent l'expÃ©rience utilisateur ;
- rendre l'application plus prÃ©sentable et plus proche d'un niveau production.

### Tests Playwright

Les tests Playwright utilisent une API simulÃ©e pour vÃ©rifier les parcours frontend sans dÃ©pendre du backend rÃ©el.

ScÃ©narios vÃ©rifiÃ©s :

- connexion utilisateur ;
- navigation tableau de bord ;
- rÃ©servation ;
- affichage des stations ;
- session mobile ;
- vues administrateur ;
- vues technicien.

Limite :

- ces tests valident l'interface et les appels attendus ;
- ils ne remplacent pas un test complet avec l'API rÃ©elle, le Raspberry et l'ESP32.

## 5. Tests de bout en bout

### Objectif

Valider le parcours rÃ©el :

```text
RÃ©servation -> session mobile -> kiosk -> MQTT -> tÃ©lÃ©mÃ©trie -> supervision -> arrÃªt
```

### Test automatisÃ© backend

Fichier principal :

```text
backend/api/tests/test_end_to_end_charge_flow.py
```

ScÃ©nario couvert :

1. crÃ©ation d'une rÃ©servation QR ;
2. crÃ©ation d'une session mobile par le terminal ;
3. connexion utilisateur ;
4. sÃ©lection d'une rÃ©servation compatible ;
5. autorisation mobile ;
6. consommation par le kiosk ;
7. commande MQTT ;
8. tÃ©lÃ©mÃ©trie sur l'emplacement rÃ©servÃ© ;
9. arrÃªt et clÃ´ture de session.

### Script de recette dÃ©monstration

Fichier :

```text
scripts/run-demo-scenario.ps1
```

Commande :

```powershell
.\scripts\run-demo-scenario.ps1 -Reference DEMOQR1 -Emplacement 1 -TelemetryCount 5
```

Ã‰tapes exÃ©cutÃ©es par le script :

- dÃ©marrage des services Docker si demandÃ© ;
- prÃ©paration d'une rÃ©servation QR de dÃ©monstration ;
- crÃ©ation d'une session mobile cÃ´tÃ© kiosk ;
- connexion mobile utilisateur ;
- rÃ©cupÃ©ration des rÃ©servations compatibles ;
- autorisation de la rÃ©servation ;
- consommation par le kiosk ;
- commande `START` MQTT ;
- simulation de tÃ©lÃ©mÃ©trie limitÃ©e Ã  l'emplacement rÃ©servÃ© ;
- commande `STOP` MQTT ;
- clÃ´ture de session ;
- affichage de l'Ã©tat final backend.

RÃ©sultat attendu :

- une seule rÃ©servation est utilisÃ©e ;
- un seul emplacement reÃ§oit la tÃ©lÃ©mÃ©trie ;
- la session est clÃ´turÃ©e proprement ;
- Grafana peut afficher les mesures.

## 6. Tests MQTT, tÃ©lÃ©mÃ©trie et supervision

### Objectif

VÃ©rifier que les messages envoyÃ©s par les ESP32 ou par le simulateur sont correctement ingÃ©rÃ©s, stockÃ©s et affichÃ©s.

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

- simuler une tÃ©lÃ©mÃ©trie rÃ©aliste sans ESP32 ;
- tester Grafana ;
- tester l'ingestion backend ;
- tester les seuils d'alerte.

### VÃ©rification des logs

```bash
docker compose logs -f mqtt-bridge
docker compose logs -f celery
docker compose logs -f backend
```

RÃ©sultat attendu :

- les messages MQTT sont reÃ§us ;
- l'ingestion ne produit pas d'erreur ;
- les mesures apparaissent en base ;
- les dashboards Grafana affichent les sÃ©ries temporelles.

### VÃ©rification en base

Exemple de contrÃ´le rapide :

```bash
docker compose exec backend python manage.py shell -c "from django.utils import timezone; from datetime import timedelta; from api.models import CapteurData; now=timezone.now(); print(CapteurData.objects.filter(timestamp__gte=now-timedelta(minutes=1)).count())"
```

RÃ©sultat attendu :

- le nombre de mesures rÃ©centes augmente lorsque la simulation ou l'ESP32 publie.

### Grafana

Tests rÃ©alisÃ©s :

- vÃ©rification du provisioning des dashboards ;
- vÃ©rification des filtres station/borne/emplacement ;
- vÃ©rification des panels de tempÃ©rature, humiditÃ©, courant, tension, puissance et Ã©nergie ;
- vÃ©rification des Ã©tats d'Ã©quipement ;
- vÃ©rification de la sÃ©paration entre supervision applicative et supervision Grafana.

Fichiers concernÃ©s :

- `backend/api/tests/test_grafana_provisioning.py` ;
- `grafana/dashboards/station-supervision.json`.

## 7. Tests sÃ©curitÃ©

### Objectif

VÃ©rifier que le projet respecte les principaux choix `security by design`.

### Tests automatisÃ©s

| Fichier | PÃ©rimÃ¨tre |
|---|---|
| `backend/api/tests/test_deployment_checks.py` | SÃ©curitÃ© Django en production |
| `backend/api/tests/test_nginx_security_config.py` | Headers, TLS, durcissement Nginx |
| `backend/api/tests/test_mqtt_security_config.py` | MQTT ACK, identifiants, configuration |
| `backend/api/tests/test_container_security_config.py` | Exposition et sÃ©curitÃ© des conteneurs |
| `backend/api/tests/test_production_hardening.py` | Durcissement global |
| `backend/api/tests/test_sms_access_policy.py` | Politique SMS et tÃ©lÃ©phone requis |

### Commandes utilisÃ©es

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest api\tests\test_deployment_checks.py
..\.venv\Scripts\python.exe -m pytest api\tests\test_nginx_security_config.py
..\.venv\Scripts\python.exe -m pytest api\tests\test_mqtt_security_config.py
```

### ContrÃ´le Django production

Dans la CI :

```bash
python manage.py check --deploy
```

Variables testÃ©es en CI :

- `DEBUG=False` ;
- `SESSION_COOKIE_SECURE=True` ;
- `CSRF_COOKIE_SECURE=True` ;
- `JWT_REFRESH_COOKIE_SECURE=True` ;
- `MQTT_ACK_REQUIRED=True` ;
- `MQTT_TLS_ENABLED=True` ;
- `SECURE_HSTS_SECONDS=31536000` ;
- `SECURE_HSTS_INCLUDE_SUBDOMAINS=True` ;
- `SECURE_HSTS_PRELOAD=True`.

### ContrÃ´les frontend sÃ©curitÃ©

Le script `check-js.mjs` limite les pratiques dangereuses cÃ´tÃ© navigateur :

- pas de `eval()` ;
- pas d'injection HTML non contrÃ´lÃ©e ;
- pas de logs console ;
- pas de gestion DOM trop risquÃ©e.

RÃ©sultat attendu :

- rÃ©duire les risques XSS ;
- Ã©viter les traces de dÃ©veloppement ;
- fiabiliser les pages avant dÃ©monstration.

## 8. Tests de configuration production

### Docker Compose

Commande :

```bash
docker compose --env-file .env.example -f docker-compose.prod.yml config --quiet
```

Objectif :

- vÃ©rifier que le fichier de production est syntaxiquement valide ;
- vÃ©rifier que les variables attendues sont bien interprÃ©tÃ©es.

### Scripts de sauvegarde/restauration

Commandes CI :

```bash
bash -n scripts/backup-prod.sh
bash -n scripts/restore-prod.sh
```

Objectif :

- vÃ©rifier la syntaxe des scripts ;
- Ã©viter une erreur bloquante le jour oÃ¹ une sauvegarde ou restauration est nÃ©cessaire.

### Nginx

Tests rÃ©alisÃ©s :

- validation de configuration ;
- vÃ©rification des headers ;
- vÃ©rification des limites de requÃªte ;
- vÃ©rification du TLS/HSTS cÃ´tÃ© configuration.

Fichiers concernÃ©s :

- `nginx/nginx.conf` ;
- `nginx/conf.d/station.conf` ;
- `backend/api/tests/test_nginx_security_config.py`.

## 9. Tests de documentation et qualitÃ©

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

- vÃ©rifier que la documentation technique se construit ;
- Ã©viter les rÃ©fÃ©rences cassÃ©es ;
- maintenir une documentation exploitable.

### QualitÃ© Python

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

- dÃ©tecter les imports inutilisÃ©s ;
- dÃ©tecter des erreurs Python probables ;
- homogÃ©nÃ©iser le style ;
- Ã©viter certains piÃ¨ges courants.

### Couverture documentaire

Commande CI :

```bash
python -m interrogate api
```

Objectif :

- vÃ©rifier que les modules importants restent documentÃ©s ;
- amÃ©liorer la maintenabilitÃ© du backend.

## 10. Tests manuels matÃ©riel

### Badge RFID

ProcÃ©dure testÃ©e :

1. associer un badge RFID Ã  un compte utilisateur ;
2. crÃ©er une rÃ©servation avec accÃ¨s RFID ;
3. attendre le crÃ©neau de rÃ©servation ;
4. prÃ©senter le badge sur le lecteur ACR122U ;
5. vÃ©rifier que le kiosk valide l'accÃ¨s ;
6. vÃ©rifier que la serrure reÃ§oit la commande de dÃ©verrouillage.

RÃ©sultat attendu :

- le badge est reconnu ;
- l'utilisateur est retrouvÃ© ;
- une rÃ©servation compatible est trouvÃ©e ;
- l'emplacement est autorisÃ©.

### Serrure

ProcÃ©dure testÃ©e avec prototype :

1. accÃ¨s validÃ© par QR, RFID ou session mobile ;
2. publication d'une commande de dÃ©verrouillage ;
3. activation du relais cÃ´tÃ© ESP32 ;
4. retour d'Ã©tat ou ACK MQTT.

RÃ©sultat attendu :

- la serrure s'ouvre aprÃ¨s validation d'accÃ¨s ;
- la session reste en attente de branchement ;
- la charge ne doit pas Ãªtre considÃ©rÃ©e comme active tant qu'aucun courant n'est dÃ©tectÃ©.

### DÃ©tection de courant

ProcÃ©dure testÃ©e :

1. dÃ©marrer le firmware ESP32 ;
2. calibrer le zÃ©ro courant ;
3. activer le gÃ©nÃ©rateur pour simuler la charge ;
4. vÃ©rifier la remontÃ©e du courant ;
5. vÃ©rifier le calcul de puissance ;
6. vÃ©rifier l'Ã©nergie cumulÃ©e.

RÃ©sultat attendu :

- courant dÃ©tectÃ© lorsque le gÃ©nÃ©rateur est actif ;
- puissance calculÃ©e avec `P = U x I` ;
- Ã©nergie cumulÃ©e en kWh ;
- passage de l'Ã©tat `waiting_plug` Ã  `charging`.

### LED et buzzer

ProcÃ©dure testÃ©e ou prÃ©vue :

- LED verte : Ã©tat normal ou charge ;
- LED jaune : alerte modÃ©rÃ©e ;
- LED rouge : alerte grave ;
- buzzer : anomalie critique.

RÃ©sultat attendu :

- l'Ã©tat physique est lisible localement sans ouvrir Grafana.

## 11. Tests de dÃ©monstration avant soutenance

### Checklist courte

Avant une dÃ©monstration, lancer :

```bash
docker compose -f docker-compose.prod.yml ps
```

VÃ©rifier :

- backend actif ;
- frontend actif ;
- reverse proxy actif ;
- PostgreSQL actif ;
- Redis actif ;
- Celery actif ;
- MQTT bridge actif ;
- Grafana actif ;
- Mailpit actif si test mail.

### VÃ©rifier l'application

Depuis le PC :

- ouvrir l'application HTTPS ;
- se connecter avec le compte admin ;
- crÃ©er une rÃ©servation ;
- vÃ©rifier la carte ;
- vÃ©rifier le dashboard admin ;
- vÃ©rifier Grafana.

Depuis le smartphone :

- ouvrir la mÃªme origine publique que celle du QR mobile ;
- se connecter ;
- scanner un QR de session mobile ;
- sÃ©lectionner la rÃ©servation compatible.

Depuis le Raspberry :

- vÃ©rifier que Chromium est lancÃ© sur `localhost:9000` ;
- vÃ©rifier que le QR mobile pointe vers l'adresse accessible au smartphone ;
- vÃ©rifier que le lecteur RFID est dÃ©tectÃ© si branchÃ©.

Depuis l'ESP32 :

- vÃ©rifier la connexion Wi-Fi ;
- vÃ©rifier la connexion MQTT ;
- vÃ©rifier les publications de tÃ©lÃ©mÃ©trie ;
- vÃ©rifier les ACK de commandes.

## 12. ScÃ©narios de recette fonctionnelle

### ScÃ©nario 1 : rÃ©servation QR

| Ã‰tape | Action | RÃ©sultat attendu |
|---|---|---|
| 1 | L'utilisateur crÃ©e une rÃ©servation | RÃ©servation confirmÃ©e |
| 2 | Le QR de rÃ©servation est gÃ©nÃ©rÃ© | QR disponible dans l'application et envoyable par mail |
| 3 | Le QR est prÃ©sentÃ© au kiosk | AccÃ¨s validÃ© si crÃ©neau et borne corrects |
| 4 | La serrure s'ouvre | Session en attente de branchement |
| 5 | Un courant est dÃ©tectÃ© | Session en charge |
| 6 | La charge est arrÃªtÃ©e | Session clÃ´turÃ©e |

### ScÃ©nario 2 : session mobile QR borne

| Ã‰tape | Action | RÃ©sultat attendu |
|---|---|---|
| 1 | La borne affiche un QR temporaire | Session mobile `pending` |
| 2 | Le tÃ©lÃ©phone scanne le QR | Page mobile ouverte |
| 3 | L'utilisateur se connecte | RÃ©servations compatibles affichÃ©es |
| 4 | L'utilisateur choisit une rÃ©servation | Session mobile `authorized` |
| 5 | La borne consomme l'autorisation | Session mobile `consumed` |
| 6 | L'emplacement est ouvert | Attente branchement |

### ScÃ©nario 3 : accÃ¨s RFID

| Ã‰tape | Action | RÃ©sultat attendu |
|---|---|---|
| 1 | L'utilisateur associe un badge | UID liÃ© au compte |
| 2 | Une rÃ©servation compatible existe | AccÃ¨s possible |
| 3 | L'utilisateur prÃ©sente le badge | Backend ou cache offline valide |
| 4 | La serrure s'ouvre | Session en attente branchement |

### ScÃ©nario 4 : code SMS

| Ã‰tape | Action | RÃ©sultat attendu |
|---|---|---|
| 1 | L'utilisateur possÃ¨de un tÃ©lÃ©phone | Option SMS disponible |
| 2 | Le code est gÃ©nÃ©rÃ© | Secret stockÃ© sans clair |
| 3 | Le code est envoyÃ© ou loggÃ© en dev | Utilisateur peut tester |
| 4 | Le code est saisi au kiosk | AccÃ¨s validÃ© si correct |
| 5 | Trop d'essais sont rÃ©alisÃ©s | Rate limiting ou refus |

### ScÃ©nario 5 : mode dÃ©gradÃ©

| Ã‰tape | Action | RÃ©sultat attendu |
|---|---|---|
| 1 | Le Raspberry a synchronisÃ© le cache | RÃ©servations rÃ©centes disponibles localement |
| 2 | Le backend devient indisponible | Le kiosk bascule sur le cache |
| 3 | L'utilisateur utilise un accÃ¨s connu | Validation locale possible |
| 4 | L'ESP32 reste joignable via MQTT local | Commande possible |
| 5 | Le backend revient | Synchronisation et reprise normale |

## 13. Limites et risques restants

### MatÃ©riel incomplet

Certains capteurs prÃ©vus dans le cahier des charges ne sont pas encore entiÃ¨rement cÃ¢blÃ©s :

- capteur d'ouverture du boÃ®tier ;
- capteur de prÃ©sence cÃ¢ble dÃ©diÃ© ;
- tension rÃ©elle si elle reste fixe dans le prototype ;
- intrusion physique complÃ¨te.

ConsÃ©quence :

- certains Ã©tats sont simulÃ©s ou dÃ©duits Ã  partir du courant ;
- le scÃ©nario physique reste cohÃ©rent pour un prototype, mais doit Ãªtre complÃ©tÃ© pour une industrialisation.

### Tests mobiles rÃ©els

Les tests Playwright valident l'interface en navigateur, mais une vraie recette mobile reste nÃ©cessaire :

- Firefox/Chrome Android ;
- certificat local installÃ© ;
- hotspot ou rÃ©seau commun ;
- QR session mobile ;
- PWA installÃ©e ou utilisÃ©e en navigateur.

### RÃ©seau de dÃ©monstration

La dÃ©monstration dÃ©pend fortement de l'adressage rÃ©seau :

- serveur Debian ;
- Raspberry ;
- ESP32 ;
- smartphone ;
- PC de prÃ©sentation.

Un changement de hotspot ou d'IP peut nÃ©cessiter d'aligner :

- `FRONTEND_BASE_URL` ;
- `MOBILE_FRONTEND_BASE_URL` ;
- `BACKEND_API_BASE_URL` ;
- `MQTT_HOST` ;
- certificats HTTPS.

## 14. Conclusion

Le projet dispose d'un plan de tests structurÃ© couvrant :

- les rÃ¨gles mÃ©tier ;
- les accÃ¨s utilisateur ;
- le terminal Raspberry ;
- les Ã©changes MQTT ;
- la tÃ©lÃ©mÃ©trie ;
- la supervision ;
- la sÃ©curitÃ© ;
- la configuration de production ;
- l'expÃ©rience frontend/PWA.

Les tests automatisÃ©s sÃ©curisent les rÃ©gressions logicielles.
Les tests manuels et les simulations complÃ¨tent la validation pour les parties dÃ©pendantes du matÃ©riel physique.

Pour la soutenance, les points les plus valorisants sont :

- le scÃ©nario de bout en bout ;
- la sÃ©paration entre tests automatisÃ©s et tests matÃ©riels ;
- la prÃ©sence de tests sÃ©curitÃ©/production ;
- l'utilisation d'une simulation rÃ©aliste pour compenser l'absence temporaire de matÃ©riel ;
- la traÃ§abilitÃ© entre code, tests, documentation et dÃ©monstration.
