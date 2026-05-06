# Station de recharge intelligente

Prototype académique de station de recharge sécurisée pour vélos électriques.

Le projet couvre trois blocs :

- plateforme web de réservation et d'administration ;
- interface locale Raspberry Pi pour l'identification à la borne ;
- ESP32 par emplacement pour la serrure, les capteurs, la charge et la télémétrie.

## Objectifs

Le prototype doit permettre :

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
  -> MQTT pour commander les ESP32

ESP32
  -> MQTT telemetry/status/alert
  -> mqtt-bridge backend
  -> Celery
  -> Base de données
  -> Grafana
```

Services principaux :

- `backend/` : Django, API REST, modèles, Celery, bridge MQTT ;
- `frontend/` : application Vite multi-pages ;
- `raspberry/app/` : interface kiosque locale et client MQTT edge ;
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
http://localhost/grafana/  -> Grafana
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

## Comptes de démonstration

Les comptes sont créés au démarrage Docker depuis `.env` :

```text
admin       -> ADMIN_PSEUDO / ADMIN_PASSWORD
technicien  -> DEMO_TECH_PSEUDO / DEMO_TECH_PASSWORD
```

Les valeurs de `.env.example` sont suffisantes en local, mais doivent être
changées hors développement.

## Flux MQTT

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

Tests ciblés MQTT et terminal :

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
- `requirements_traceability.rst` : correspondance avec le cahier des charges ;
- `supervision_mqtt.rst` : flux MQTT, Grafana, Wokwi ;
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
