# Station de recharge intelligente

Solution de station de recharge sécurisée pour vélos électriques, conçue pour
couvrir la réservation, le contrôle d'accès, la supervision technique et
l'exploitation des équipements connectés.

Documentation publiée : https://bayhes5.github.io/Station_de_recharge/

Le projet couvre trois blocs :

- plateforme web de réservation et d'administration ;
- interface locale Raspberry Pi pour l'identification à la borne ;
- ESP32 par emplacement pour la serrure, les capteurs, la charge et la télémétrie.

## Objectifs

La solution doit permettre :

- la réservation en ligne d'un emplacement de recharge ;
- l'identification par QR code, badge RFID ou code alphanumérique ;
- la validation de la réservation sur une borne locale ;
- le pilotage d'une serrure électromagnétique et du démarrage de charge ;
- la remontée de télémétrie : température, courant, tension, câble, boîtier ;
- la détection d'alertes : intrusion, surchauffe, surconsommation, câble retiré ;
- la supervision technique avec Grafana ;
- l'archivage des sessions et statistiques d'utilisation.

## Architecture

```text
Utilisateur
  -> Frontend Vite
  -> API Django
  -> TimescaleDB/PostgreSQL

Kiosque Raspberry
  -> API Django pour valider l'accès
  -> messagerie locale pour commander les ESP32
  -> cache local limite en mode degrade

ESP32
  -> MQTT telemetry/status/alert
  -> mqtt-bridge backend
  -> Celery
  -> Base de données
  -> Grafana
  -> journal local embarque en cas de coupure
```

Services principaux :

- `backend/` : Django, API REST, modèles, Celery, ingestion des télémétries ;
- `frontend/` : application Vite multi-pages ;
- `raspberry/app/` : interface kiosque locale et client de commande des emplacements ;
- `esp32/` : firmware MicroPython et simulation Wokwi ;
- `nginx/` : reverse proxy local ;
- `grafana/` : datasource et dashboard provisionnés ;
- `mosquitto/config/` : configuration du broker MQTT.

## Démarrage rapide

Copier le modèle d'environnement :

```powershell
Copy-Item .env.example .env
```

Démarrer la stack :

```bash
docker compose up -d --build
```

Routes recommandées via Nginx :

```text
http://localhost/          -> frontend
http://localhost/api/      -> API Django
http://localhost/admin/    -> administration Django
http://localhost/grafana/d/station-supervision/station-supervision-technique?orgId=1&from=now-6h&to=now&refresh=5s
                         -> dashboard Grafana de supervision
http://localhost/kiosk/    -> kiosque Raspberry
```

Ports directs de développement :

```text
5432  -> TimescaleDB/PostgreSQL
6379  -> Redis
1883  -> Mosquitto MQTT
8000  -> Django
5173  -> Vite
9000  -> kiosque Raspberry
3000  -> Grafana
```

## Comptes locaux préconfigurés

Les comptes sont créés au démarrage Docker depuis `.env` :

```text
admin       -> ADMIN_PSEUDO / ADMIN_PASSWORD
technicien  -> DEMO_TECH_PSEUDO / DEMO_TECH_PASSWORD
```

Les valeurs de `.env.example` sont suffisantes en local, mais doivent être
changées hors développement.

## Télémétrie et commandes des emplacements

Télémétrie ESP32 :

```text
station/<slot_id>/telemetry
```

Commandes vers ESP32 :

```text
station/<slot_id>/cmd
```

Payload type :

```json
{
  "slot_id": "slot1",
  "session_id": "demo",
  "state": "charging",
  "current": 1.2,
  "voltage": 12.0,
  "energy_kwh": 0.04,
  "temperature": 32.5,
  "humidity": 45,
  "door": true,
  "cable": true
}
```

Dans l'interface de supervision, `door` et `cable` sont affiches sous forme
lisible : boitier ferme/ouvert et cable present/retire. Les alertes suivent le
cycle automatique `nouvelle` -> `active` -> `resolue` : une anomalie continue ne
cree pas de doublon, et une telemetrie revenue a la normale resout l'alerte.

Envoyer une commande manuelle depuis Django :

```bash
python manage.py send_slot_command slot1 START --session-id demo
```

Envoyer une commande via le Raspberry :

```bash
curl -X POST http://localhost:9000/mqtt/command \
  -H "Content-Type: application/json" \
  -d '{"slot_id":"slot1","action":"START","session_id":"demo"}'
```

Le backend reste le chemin nominal : il valide la réservation et le moyen
d'accès avant qu'une commande soit envoyée à l'ESP32. Le Raspberry est prévu pour
assurer une continuité locale limitée si le serveur est indisponible, à partir
d'autorisations déjà synchronisées. Les ESP32 doivent conserver les mesures et
événements non transmis dans un journal local, par exemple via LittleFS, puis les
resynchroniser au retour de la communication.

## Simulation locale de télémétrie

Wokwi peut rester de cote pendant que la supervision avance. Le backend fournit
une commande qui publie des donnees capteurs simulees sur les memes canaux que
les ESP32 :

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py simulate_mqtt_telemetry --slots slot1 slot2 slot3 --scenario mixed --interval 2
```

Tester uniquement le format sans broker :

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py simulate_mqtt_telemetry --count 3 --dry-run
```

Avec Docker :

```bash
docker compose --profile simulation up -d mqtt-simulator
docker compose logs -f mqtt-simulator
```

## Commandes utiles et diagnostic

Etat de la stack :

```bash
docker compose ps
docker compose ps -a
docker compose logs --tail=100 backend
docker compose logs --tail=100 mqtt-bridge
docker compose logs --tail=100 mqtt
docker compose logs --tail=100 grafana
```

Relancer un service sans toucher aux volumes :

```bash
docker compose restart backend
docker compose restart mqtt-bridge
docker compose up -d --force-recreate mqtt-bridge
```

Diagnostiquer la messagerie IoT :

```bash
docker compose exec mqtt mosquitto_sub -h localhost -t 'station/#' -v -C 5 -W 10
docker compose exec mqtt mosquitto_pub -h localhost -t 'station/slot1/telemetry' -m '{"state":"charging","current":1.2,"voltage":12.0,"temperature":32.5,"humidity":45,"door":true,"cable":true}'
```

Diagnostiquer PostgreSQL et Django :

```bash
docker compose exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select now();"'
docker compose exec backend python manage.py check
docker compose exec backend python manage.py spectacular --validate
```

Si Docker signale un reseau introuvable pour un conteneur arrete, supprimer
uniquement ce conteneur puis le recreer :

```bash
docker compose rm -f mqtt-simulator
docker compose --profile simulation up -d mqtt-simulator
```

Verifier les reseaux Docker :

```bash
docker network ls
docker inspect mqtt_simulator --format '{{json .NetworkSettings.Networks}}'
docker inspect mqtt_broker --format '{{json .NetworkSettings.Networks}}'
```

Arreter la stack sans supprimer les donnees :

```bash
docker compose down
```

## Simulation Wokwi

Le dossier `esp32/wokwi/` contient une simulation interactive :

- switch câble ;
- switch boîtier ;
- potentiomètre courant ;
- potentiomètre température ;
- LED serrure ;
- LED charge.

Par défaut, Wokwi publie vers :

```text
test.mosquitto.org
```

Pour afficher ces données dans Grafana via le backend local, configurer
temporairement :

```env
MQTT_HOST=test.mosquitto.org
MQTT_PORT=1883
MQTT_BASE_TOPIC=station
```

## Tests et vérifications

Backend :

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest
```

Tests ciblés télémétrie et terminal :

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest api\tests\test_mqtt_ingestion.py api\tests\test_terminal_auth.py
```

Frontend :

```powershell
cd frontend
npm ci
npm run check:js
npm run verify
```

Docker et Nginx :

```bash
docker compose config --quiet
docker compose run --rm --no-deps reverse-proxy nginx -t
```

Django :

```powershell
.\.venv\Scripts\python.exe backend\manage.py check --settings=config.test_settings
```

## Documentation

La documentation technique Sphinx est dans `docs/source/`.

Pages principales :

- `architecture.rst` : architecture globale ;
- `implementation_guide.rst` : fonctionnalités, implantation et choix d'architecture ;
- `data_model.rst` : modèle de données, correspondance MCD et implémentation Django ;
- `requirements_traceability.rst` : correspondance avec le cahier des charges ;
- `station_supervision.rst` : supervision technique, télémétrie, alertes, Grafana ;
- `testing_strategy.rst` : stratégie de tests ;
- `technical_choices.rst` : justification des choix techniques ;
- `api_openapi.rst` : documentation API ;
- `development.rst` : commandes de développement.

Construire la documentation :

```powershell
.\docs\make.bat html
```

Variante si `sphinx-build` n'est pas dans le `PATH` :

```powershell
$env:DEBUG="True"
$env:SECRET_KEY="docs-local-secret-key-not-for-production"
.\.venv\Scripts\python.exe -m sphinx -b html docs\source docs\build\html
```

La sortie HTML est générée dans `docs/build/html/` et ne doit pas être committée.

## Sécurité

Mesures déjà présentes :

- mots de passe hashés par Django ;
- JWT avec refresh token en cookie `HttpOnly` ;
- rôles utilisateur, technicien et administrateur ;
- journalisation d'actions sensibles ;
- reverse proxy Nginx local ;
- protection de branche GitHub avec CI obligatoire ;
- CodeQL et rapports supply chain.

À durcir pour une production :

- HTTPS/TLS ;
- identifiants MQTT et TLS broker ;
- segmentation réseau ;
- secrets forts ;
- sauvegardes ;
- protection Grafana par SSO ou reverse proxy authentifié.

## CI et branche main

La branche `main` est protégée. Les changements doivent passer par une pull
request avec les checks suivants au vert :

- Backend tests ;
- Backend quality ;
- Frontend verify ;
- Documentation build ;
- Analyze Python ;
- Analyze JavaScript/TypeScript ;
- Backend image supply chain reports.
