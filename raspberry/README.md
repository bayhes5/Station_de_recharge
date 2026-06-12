# Intégration Raspberry Pi

Ce dossier contient la version à utiliser sur la borne Raspberry Pi. Il remplace
le prototype Flask autonome reçu dans `borne.7z` : le Raspberry reste un terminal
local, tandis que Django conserve la décision métier, les réservations, les
sessions et les droits d'accès.

## Choix d'intégration

La base à conserver est `raspberry/app` de ce dépôt.

Le prototype du collègue est utile comme référence pour le matériel, mais il ne
doit pas être repris tel quel en production car il possède sa propre base SQLite,
ses propres utilisateurs et ses propres réservations. Cela créerait deux sources
de vérité différentes entre la borne et le backend.

À reprendre du prototype :

- l'idée d'un lecteur QR USB qui se comporte comme un clavier ;
- les retours visuels simples pendant une lecture RFID ou QR ;
- le principe d'une interface tactile plein écran.

À ne pas reprendre tel quel :

- la base locale `instance/borne.db` ;
- les modèles locaux `Utilisateur` et `code_reservation` ;
- les routes Flask de validation locale ;
- le module RFID qui lit l'ATR de la carte au lieu de l'UID ;
- le dossier `venv` envoyé dans l'archive.

## Interface tactile

L'interface actuelle `index.html`, `style.css` et `app.js` est la base
recommandée.

Elle est plus adaptée au projet final parce qu'elle :

- respecte la cible 1024 x 600 de l'écran Waveshare ;
- garde un enchaînement cohérent : identification, validation, écran
  "Recharger à l'emplacement X", puis démarrage de la charge ;
- ne permet pas de démarrer tant que l'authentification n'est pas validée ;
- gère RFID, QR de réservation, session mobile, code SMS, association de badge,
  mode dégradé et arrêt de charge ;
- parle au backend Django et publie les commandes MQTT vers les ESP32 ;
- revient automatiquement à l'accueil hors écran de charge après inactivité.

Les idées visuelles du prototype peuvent être ajoutées plus tard sous forme
d'amélioration : thème nuit, animation de scan plus marquée, compte à rebours de
lecture et retour sonore local. Elles ne justifient pas de remplacer
l'interface actuelle.

## Configuration minimale sur Raspberry

Exemple de variables pour un Raspberry connecté au même réseau que le backend :

```bash
export BACKEND_API_BASE_URL=http://<ip-backend>:8000/api
export TERMINAL_API_SECRET=dev-terminal-secret
export TERMINAL_CODE=station-demo-borne-1

export MQTT_HOST=<ip-broker>
export MQTT_PORT=1883
export MQTT_BASE_TOPIC=station
export MQTT_ACK_REQUIRED=false

export RFID_READER_BACKEND=acr122u
export RFID_DEBOUNCE_SECONDS=2
```

En développement historique, si Mosquitto tourne sur le PC dans Docker,
`MQTT_HOST` est l'adresse Wi-Fi du PC. Pour le mode dégradé réel, Mosquitto doit
tourner sur le Raspberry et `MQTT_HOST=localhost` côté kiosk.

Au démarrage, le Raspberry appelle `/api/terminal/config/` avec `TERMINAL_CODE`
et `TERMINAL_API_SECRET`. Le backend renvoie les UUID actuels de station et de
borne, ainsi que le préfixe MQTT. Le kiosk les conserve dans
`terminal_config.json` pour pouvoir redémarrer en mode dégradé si le backend est
temporairement indisponible.

## Broker MQTT local sur le Raspberry

Architecture cible :

```text
ESP32 -> Mosquitto Raspberry -> bridge MQTT backend -> base -> Grafana
Raspberry kiosk -> Mosquitto Raspberry -> ESP32
```

Le Raspberry devient le point local de commande. Si le backend tombe, le kiosk
peut encore publier `UNLOCK`, `LOCK`, `START` ou `STOP` vers les ESP32 déjà
connus et synchronisés.

### Installation rapide

Depuis le Raspberry :

```bash
cd ~/Station_de_recharge/raspberry
chmod +x scripts/install-mosquitto-broker.sh
./scripts/install-mosquitto-broker.sh
```

Le script :

- installe `mosquitto` et `mosquitto-clients` ;
- copie `raspberry/mosquitto/station.conf` dans `/etc/mosquitto/conf.d/` ;
- copie `raspberry/mosquitto/aclfile` dans `/etc/mosquitto/` ;
- crée `/etc/mosquitto/passwd` ;
- demande les mots de passe MQTT ;
- redémarre et active le service `mosquitto`.

Le fichier actif utilise MQTT authentifié sur `1883`. Le fichier
`raspberry/mosquitto/station.tls.conf` prépare la migration TLS sur `8883` avec
un certificat signé par la CA locale `Metropole Verte`. Il ne doit remplacer
`station.conf` qu'après distribution de la racine CA au backend, au kiosk et aux
ESP32.

Comptes créés :

| Compte | Usage |
|---|---|
| `station_backend` | bridge MQTT backend, ingestion télémétrie |
| `raspberry_kiosk` | kiosk local, commandes et lecture ACK/status |
| `esp32_station_demo_borne_1_slot1` | ESP32 emplacement 1 |
| `esp32_station_demo_borne_1_slot2` | ESP32 emplacement 2 optionnel |
| `esp32_station_demo_borne_1_slot3` | ESP32 emplacement 3 optionnel |

### Variables à utiliser après migration

Sur le Raspberry kiosk :

```bash
export MQTT_HOST=localhost
export MQTT_PORT=1883
export MQTT_BASE_TOPIC=station
export MQTT_USERNAME=raspberry_kiosk
export MQTT_PASSWORD=<mot-de-passe-raspberry>
export MQTT_ACK_REQUIRED=true
```

Sur le backend ou le bridge MQTT, dans `.env` :

```env
MQTT_HOST=<ip-wifi-raspberry>
MQTT_PORT=1883
MQTT_BASE_TOPIC=station
MQTT_USERNAME=station_backend
MQTT_PASSWORD=<mot-de-passe-backend>
MQTT_ACK_REQUIRED=True
```

Sur l'ESP32 `slot1` :

```python
MQTT_HOST = "<ip-wifi-raspberry>"
MQTT_USER = "esp32_station_demo_borne_1_slot1"
MQTT_PASSWORD = "<mot-de-passe-esp32-slot1>"
MQTT_TOPIC_PREFIX = "station-demo/borne-1"
SLOT_ID = "slot1"
```

Ne jamais mettre `localhost` dans l'ESP32 : pour lui, `localhost` désigne
l'ESP32 lui-même.

### Tests utiles

Depuis le Raspberry :

```bash
systemctl status mosquitto
mosquitto_sub -h localhost -u raspberry_kiosk -P '<mot-de-passe>' -t 'station/#' -v
```

Depuis le PC backend :

```bash
mosquitto_pub -h <ip-wifi-raspberry> -u station_backend -P '<mot-de-passe>' \
  -t 'station/health' -m 'ok'
```

## Installation

```bash
cd raspberry/app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

La borne est ensuite disponible sur :

```text
http://localhost:9000
```

Depuis l'écran tactile du Raspberry, ouvrir cette URL en plein écran dans le
navigateur.

## Procédure complète testée sur Raspberry physique

Cette procédure correspond au montage testé avec :

- Raspberry Pi sur le même Wi-Fi que le PC backend ;
- écran tactile Waveshare ;
- lecteur RFID ACR122U ;
- backend et Mosquitto lancés sur le PC avec Docker.

### 1. Côté PC backend

Relever l'adresse IPv4 Wi-Fi du PC :

```powershell
ipconfig
```

Mettre à jour `.env` manuellement ou lancer :

```powershell
.\scripts\update-local-ip.ps1
docker compose up -d --force-recreate backend frontend
```

Vérifier que `.env` contient au minimum :

```text
ALLOWED_HOSTS=localhost,127.0.0.1,<ip-pc>,backend,django_app
FRONTEND_BASE_URL=http://<ip-pc>:5173
CORS_ALLOWED_ORIGINS=http://<ip-pc>:5173,http://<ip-pc>:9000,...
TERMINAL_API_SECRET=dev-terminal-secret
```

Depuis le Raspberry, le backend doit répondre :

```bash
curl -i http://<ip-pc>:8000/api/health/ready/
```

Une erreur `DisallowedHost` signifie que l'IP Wi-Fi du PC manque dans
`ALLOWED_HOSTS`.

### 2. Côté Raspberry

Installer les paquets système :

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev swig pcscd pcsc-tools chromium
sudo systemctl enable --now pcscd
```

Vérifier que l'ACR122U est détecté :

```bash
lsusb | grep -i '072f\|acr122'
```

Si `pcsc_scan` affiche `SCardEstablishContext: Access denied`, ajouter la règle
Polkit suivante en remplaçant `btsciel` par l'utilisateur qui lance le kiosque :

```bash
sudo tee /etc/polkit-1/rules.d/49-pcscd-btsciel.rules >/dev/null <<'EOF'
polkit.addRule(function(action, subject) {
    if ((action.id == "org.debian.pcsc-lite.access_pcsc" ||
         action.id == "org.debian.pcsc-lite.access_card") &&
        subject.user == "btsciel") {
        return polkit.Result.YES;
    }
});
EOF

sudo chmod 0644 /etc/polkit-1/rules.d/49-pcscd-btsciel.rules
sudo systemctl restart polkit pcscd
```

Vérifier ensuite :

```bash
timeout 10 pcsc_scan
```

La sortie doit contenir `ACS ACR122U PICC Interface`.

Installer les dépendances Python :

```bash
cd /home/btsciel/raspberry/app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pyscard==2.3.1
```

Lancer le serveur kiosque :

```bash
cd /home/btsciel/raspberry/app
source .venv/bin/activate

export BACKEND_API_BASE_URL=http://<ip-pc>:8000/api
export TERMINAL_API_SECRET=dev-terminal-secret
export TERMINAL_STATION_ID=
export TERMINAL_BORNE_ID=

export MQTT_HOST=<ip-pc>
export MQTT_PORT=1883
export MQTT_BASE_TOPIC=station
export MQTT_ACK_REQUIRED=false

export RFID_READER_BACKEND=acr122u
export RFID_DEBOUNCE_SECONDS=2

python main.py
```

Contrôler dans un deuxième terminal SSH :

```bash
curl http://localhost:9000/offline/status
curl http://localhost:9000/rfid/status
```

Résultat RFID attendu :

```json
{
  "backend": "acr122u",
  "status": "running",
  "detail": "Lecteur PC/SC prêt: ACS ACR122U PICC Interface 00 00."
}
```

Lancer l'interface tactile :

```bash
DISPLAY=:0 chromium --kiosk http://localhost:9000
```

Si l'écran est en veille :

```bash
DISPLAY=:0 xset s reset
DISPLAY=:0 xset dpms force on
DISPLAY=:0 xset s off -dpms
```

### 3. Tests fonctionnels

Association RFID :

1. générer un code d'association depuis le profil web ;
2. saisir ce code dans le menu d'association du kiosque ;
3. présenter le badge sur l'ACR122U ;
4. vérifier côté backend un `POST /api/terminal/link-rfid/` en `201`.

Accès RFID :

1. créer une réservation sur le compte lié au badge ;
2. attendre le début du créneau autorisé ;
3. présenter le badge directement sur l'accueil du kiosque ;
4. vérifier un `POST /api/terminal/authenticate/` en `200` ;
5. démarrer puis arrêter la charge depuis le kiosque.

Commandes de diagnostic :

```bash
curl http://localhost:9000/rfid/status
curl http://localhost:9000/rfid/scan
curl http://localhost:9000/offline/status
curl http://localhost:9000/charge/state
tail -f /home/btsciel/raspberry/app/kiosk.log
journalctl -u pcscd -f
```

## Lecteur RFID ACR122U

Installer les dépendances système :

```bash
sudo apt update
sudo apt install pcscd pcsc-tools python3-dev swig
sudo systemctl enable --now pcscd
```

Activer la dépendance Python `pyscard` dans `raspberry/app/requirements.txt`,
puis installer les dépendances.

Vérifier le lecteur :

```bash
pcsc_scan
curl http://localhost:9000/rfid/status
```

Le code `raspberry/app/rfid_reader.py` utilise la commande ACR122U
`FF CA 00 00 00` pour lire l'UID réel du badge. C'est cet UID qui doit être
envoyé au backend.

Pour tester sans lecteur :

```bash
curl -X POST http://localhost:9000/rfid/scan \
  -H "Content-Type: application/json" \
  -d '{"uid":"04A3BC89F2"}'
```

## Lecteur QR USB

La solution la plus simple est de configurer le lecteur QR comme clavier USB.
Sur l'écran "Scanner QR", le champ de saisie est automatiquement focalisé :
le lecteur écrit le contenu du QR et envoie `Entrée`, ce qui déclenche la
validation.

Un module Linux basé sur `evdev`, comme celui du prototype, peut être ajouté
plus tard si le lecteur ne fonctionne pas correctement en mode clavier. Il
faudra alors gérer les droits d'accès à `/dev/input` et éviter de capturer le
clavier tactile ou un autre périphérique par erreur.

## Parcours attendu

RFID :

1. L'utilisateur présente son badge.
2. Le Raspberry lit l'UID.
3. Le Raspberry appelle le backend terminal.
4. Le backend valide la réservation et renvoie la session de charge.
5. Le Raspberry publie `UNLOCK` vers l'ESP32 pour ouvrir le boîtier.
6. La borne affiche "Recharger à l'emplacement X".
7. L'utilisateur branche le câble ou active le générateur du prototype.
8. Le Raspberry publie `START` vers l'ESP32 dès que `cable=true` est reçu, ou provisoirement dès qu'une mesure SEN0214 récente `current >= 0.1 A` est détectée sans capteur câble câblé.
9. L'écran passe à "Chargement en cours".

QR de réservation :

1. L'utilisateur affiche son QR de réservation.
2. Le lecteur QR USB l'envoie comme saisie clavier.
3. Le backend valide la réservation.
4. Le même enchaînement de charge démarre.

Session mobile :

1. La borne affiche un QR temporaire de session.
2. L'utilisateur le scanne avec son téléphone.
3. Il se connecte à la PWA.
4. Il choisit sa réservation.
5. Le backend autorise la borne.
6. La borne affiche l'emplacement attribué.

Mode dégradé :

1. Le Raspberry synchronise à l'avance les réservations proches.
2. Si le backend tombe, il vérifie uniquement les droits déjà synchronisés.
3. Les événements locaux sont rejoués au backend lorsque la connexion revient.

## Fichiers à transmettre au collègue

Pour repartir proprement, transmettre au minimum :

- `raspberry/app/main.py`
- `raspberry/app/app.js`
- `raspberry/app/index.html`
- `raspberry/app/style.css`
- `raspberry/app/rfid_reader.py`
- `raspberry/app/mqtt_client.py`
- `raspberry/app/mqtt_contract.py`
- `raspberry/app/offline_store.py`
- `raspberry/app/charge_state.py`
- `raspberry/app/requirements.txt`
- `raspberry/Dockerfile`
- ce fichier `raspberry/README.md`

Ne pas transmettre `__pycache__`, les bases SQLite locales de test, les dossiers
`venv` ni les fichiers `.env` contenant des secrets.
