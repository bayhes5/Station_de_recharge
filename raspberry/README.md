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
export TERMINAL_STATION_ID=station-demo
export TERMINAL_BORNE_ID=borne-1

export MQTT_HOST=<ip-broker>
export MQTT_PORT=1883
export MQTT_BASE_TOPIC=station
export MQTT_ACK_REQUIRED=false

export RFID_READER_BACKEND=acr122u
export RFID_DEBOUNCE_SECONDS=2
```

En développement, si Mosquitto tourne sur le PC dans Docker, `MQTT_HOST` est
l'adresse Wi-Fi du PC. En production, Mosquitto doit idéalement tourner sur le
Raspberry et `MQTT_HOST=localhost`.

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
5. La borne affiche "Recharger à l'emplacement X".
6. L'utilisateur démarre.
7. Le Raspberry publie `START` vers l'ESP32.
8. L'écran passe à "Chargement en cours".

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
- `raspberry/app/offline_store.py`
- `raspberry/app/charge_state.py`
- `raspberry/app/requirements.txt`
- `raspberry/Dockerfile`
- ce fichier `raspberry/README.md`

Ne pas transmettre `__pycache__`, les bases SQLite locales de test, les dossiers
`venv` ni les fichiers `.env` contenant des secrets.
