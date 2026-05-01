# Station de recharge

Prototype de station de recharge pour vélos électriques.

Le projet rassemble:

- un backend Django avec API REST et pages serveur
- un frontend Vite servi en développement par le serveur Vite
- une interface kiosque Raspberry Pi
- une base PostgreSQL pour les données de développement
- un cache Redis pour les caches applicatifs ciblés

## Démarrage rapide

1. Copier `.env.example` vers `.env` si besoin, puis vérifier les identifiants locaux.
2. Démarrer la stack:

```bash
docker compose up -d --build
```

3. Ouvrir les interfaces utiles:

- `http://localhost:8000` pour le backend Django et les pages serveur
- `http://localhost:5173` pour le frontend Vite
- `http://localhost:9000` pour le kiosque Raspberry

## Déploiement depuis un clone Git

Cette procédure permet de repartir d'une machine vierge après un `git clone`.

### Prérequis

- Git
- Docker et Docker Compose
- Un terminal placé dans le dossier du projet

Vérifier que Docker est disponible:

```bash
docker --version
docker compose version
```

### 1. Cloner le projet

```bash
git clone https://github.com/bayhes5/Station_de_recharge
cd Station_de_recharge
```

### 2. Créer le fichier d'environnement

Copier le modèle fourni:

```bash
cp .env.example .env
```

Sous Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Ouvrir ensuite `.env` et adapter au minimum:

- `SECRET_KEY`: mettre une valeur unique et secrète
- `DEBUG`: mettre `False` hors développement local
- `ALLOWED_HOSTS`: ajouter le domaine ou l'adresse IP de la machine cible
- `ADMIN_PSEUDO`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`: définir le compte administrateur
- `DEMO_TECH_*`: définir ou modifier le compte technicien de démo si besoin

Pour un lancement local de test, les valeurs de `.env.example` suffisent.

### 3. Construire et démarrer les services

```bash
docker compose up -d --build
```

Cette commande démarre:

- PostgreSQL sur le port `5432`
- Redis sur le port `6379`
- Django sur le port `8000`
- le frontend Vite sur le port `5173`
- le kiosque Raspberry sur le port `9000`

Au démarrage, le backend applique les migrations Django, crée ou met à jour le superuser, puis initialise les données de démo.

### 4. Vérifier le déploiement

Afficher l'état des conteneurs:

```bash
docker compose ps
```

Consulter les logs si un service ne démarre pas:

```bash
docker compose logs -f backend
docker compose logs -f db
```

Ouvrir ensuite:

- `http://localhost:8000` pour le backend Django
- `http://localhost:5173` pour le frontend
- `http://localhost:9000` pour le kiosque Raspberry

Sur une autre machine du réseau, remplacer `localhost` par l'adresse IP ou le nom de domaine du serveur.

### Commandes utiles

Arrêter les services sans supprimer les données:

```bash
docker compose down
```

Redémarrer après une modification:

```bash
docker compose up -d --build
```

Reconstruire rapidement l'image backend de développement:

```bash
docker compose build backend
```

Reconstruire le backend sans cache Docker. Cette commande reste plus lente car
elle force la réexécution des étapes Docker, mais le cache pip BuildKit limite
les retéléchargements après un premier passage:

```bash
docker compose build --no-cache backend
```

Construire l'image backend de vérification, avec installation des dépendances de
test et exécution de pytest pendant le build:

```bash
docker compose --profile test build backend-test
```

Lancer une commande Django dans le conteneur backend:

```bash
docker compose exec backend python manage.py <commande>
```

Suivre le serveur Vite:

```bash
docker compose logs -f frontend
```

Lancer le frontend sans Docker, si Node.js est installe:

```bash
cd frontend
npm ci
npm run dev
```

Construire les assets frontend de production:

```bash
cd frontend
npm ci
npm run build
```

Supprimer aussi la base PostgreSQL locale et repartir de zéro:

```bash
docker compose down -v
```

Attention: `docker compose down -v` supprime le volume `postgres_data` et donc les données de la base locale.

## Composants

- `backend/`: application Django, modèle de données, API, templates et commandes de bootstrap
- `frontend/`: application Vite multi-pages pour l'inscription, la connexion, le dashboard et les vues métier
- `raspberry/app/`: mini serveur HTTP pour simuler l'interface kiosque locale
- `esp32/`: prototype firmware / logique embarquée pour les ESP32 affectés aux emplacements

## Variables d'environnement

Le fichier `.env.example` couvre les variables principales:

- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `FRONTEND_BASE_URL`, `CORS_ALLOWED_ORIGINS`
- `CACHE_URL`, `API_DEFAULT_PAGE_SIZE`, `API_MAX_PAGE_SIZE`
- `STATIONS_CATALOG_CACHE_SECONDS`
- `SIMPLE_JWT_ACCESS_MINUTES`, `SIMPLE_JWT_REFRESH_DAYS`
- `ADMIN_PSEUDO`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`
- `DEMO_STATION_*`, `DEMO_EMPLACEMENTS_COUNT`, `DEMO_ESP32_FIRMWARE_VERSION`, `DEMO_TECH_*`

## Données de démo

Au démarrage du backend dans Docker:

- le superuser local est créé ou mis à jour automatiquement
- une station de démo est créée avec 3 emplacements par défaut
- un device `ESP32` est associé à chaque emplacement de démo
- un technicien de démo est créé automatiquement
- une maintenance de démonstration est ajoutée

Comptes de démo actuels dans le fichier `.env` fourni:

- admin: `admin / Admin123!`
- technicien: `tech / Tech123!`

Ces valeurs peuvent être modifiées via `.env`.

## Points d'entrée utiles

Backend Django:

- `/` page d'accueil
- `/inscription/`
- `/connexion/`
- `/contact/`
- `/politique-confidentialite/`

API principale:

- `/api/register/`
- `/api/login/`
- `/api/token/refresh/`
- `/api/me/`
- `/api/me/profile/`
- `/api/dashboard/`
- `/api/stations/`
- `/api/reservations/`
- `/api/reservations/availability/`
- `/api/terminal/authenticate/`
- `/api/technician/maintenances/`
- `/api/admin/overview/`

Documentation:

- `/api/schema/` schéma OpenAPI généré par drf-spectacular
- `/api/docs/` documentation interactive Swagger UI
- `/api/redoc/` documentation interactive Redoc
- `docs/` documentation technique Sphinx
- `docs/source/technical_choices.rst`: justification des choix techniques du projet

Dépendances:

- `backend/requirements.in`: dépendances directes du backend
- `backend/requirements.txt`: dépendances backend verrouillées pour Docker
- `backend/requirements-dev.in`: dépendances directes des tests
- `backend/requirements-dev.txt`: dépendances de test verrouillées
- `frontend/package.json`: scripts et dépendances Vite du frontend
- `docs/requirements.in`: dépendances directes de documentation
- `docs/requirements.txt`: dépendances de documentation verrouillées

Les fichiers `.txt` sont ceux installés par Docker et par les commandes locales.
Les fichiers `.in` servent de source lisible quand il faut mettre à jour les
dépendances. Après une mise à jour, reconstruire l'image backend pour vérifier
que les tests passent avec les versions verrouillées.

Tests:

Les tests pytest sont exécutés automatiquement pendant le build de l'image
backend. Si un test échoue, `docker compose up -d --build` s'arrête avant de
lancer les services.

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest
```

Relancer uniquement le build backend et donc les tests :

```bash
docker compose build backend
```

Avec couverture:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest --cov=api --cov-report=term-missing
```

Les tests utilisent `config.test_settings` et une base SQLite locale pour rester
indépendants de PostgreSQL.

Qualité des docstrings:

Le backend contient une configuration `backend/pyproject.toml` pour contrôler
la qualité des docstrings existantes avec Ruff et mesurer les docstrings
manquantes avec Interrogate. Le format retenu est le style Google, compatible
avec Sphinx via Napoleon.

Installer les dépendances de développement:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
```

Vérifier les docstrings:

```powershell
cd backend
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m interrogate api
```

Le seuil Interrogate est fixé à `100`: une nouvelle classe ou fonction suivie
par l'audit doit donc recevoir une docstring. Ruff active aussi les règles `D`
pour contrôler la présence et le style des docstrings publiques.

## SBOM et sécurité supply chain

Le projet peut générer un SBOM (Software Bill of Materials) avec Syft, en deux
formats:

- CycloneDX JSON: pratique pour les outils de sécurité applicative
- SPDX JSON: pratique pour la conformité et les audits de licences

Les fichiers générés localement sont placés dans `sbom/`, qui est ignoré par Git.
Ils doivent être régénérés à chaque build ou release plutôt que maintenus à la
main dans le dépôt.

Génération locale depuis les sources:

```powershell
.\scripts\generate-sbom.ps1
```

Si `syft` n'est pas installé localement mais que Docker est disponible:

```powershell
.\scripts\generate-sbom.ps1 -UseDockerSyft
```

Génération locale depuis l'image backend construite, plus représentative des
versions réellement installées. Cette commande nécessite Docker démarré et Syft
installé localement:

```powershell
.\scripts\generate-sbom.ps1 -Target backend-image
```

Ou avec Syft via Docker:

```powershell
.\scripts\generate-sbom.ps1 -Target backend-image -UseDockerSyft
```

Génération locale du SBOM, du rapport de vulnérabilités Grype et d'un brouillon
OpenVEX:

```powershell
.\scripts\generate-sbom.ps1 -Target backend-image -UseDockerSyft -AnalyzeVulnerabilities -UseDockerGrype
```

Les rapports Grype sont générés dans `sbom/`:

- `station-de-recharge.vulnerabilities.json`: rapport machine lisible
- `station-de-recharge.vulnerabilities.sarif`: rapport compatible GitHub Code
  Scanning
- `station-de-recharge.openvex.json`: brouillon OpenVEX, généré seulement si des
  vulnérabilités sont trouvées

Le brouillon OpenVEX utilise le statut `under_investigation`. Une déclaration VEX
officielle doit être revue avant d'être placée dans `security/vex.openvex.json`.
Si ce fichier existe, le scan Grype l'applique automatiquement.

Pour visualiser les résultats plus clairement dans l'IDE, générer un rapport
Markdown synthétique:

```powershell
.\scripts\summarize-vulnerabilities.ps1
```

Le rapport est écrit dans `sbom/station-de-recharge.vulnerability-report.md`.

Installer Syft sous Windows:

```powershell
winget install Anchore.Syft
```

Installer Grype sous Windows:

```powershell
winget install Anchore.Grype
```

Un workflow GitHub Actions génère aussi un SBOM CycloneDX, un SBOM SPDX, des
rapports de vulnérabilités Grype et un brouillon OpenVEX de l'image backend à
chaque push, pull request ou lancement manuel. Le SARIF est envoyé à GitHub Code
Scanning quand les permissions du dépôt le permettent.

## Kiosque Raspberry

Le kiosque est un simple serveur HTTP local lancé sur le port `9000`.

En dehors de Docker, il peut être démarré avec:

```bash
python raspberry/app/main.py
```

## Notes techniques

- Le backend utilise PostgreSQL par défaut.
- Les jetons JWT sont exposés via `SimpleJWT`.
- Les origines CORS locales incluent `localhost:5173`, `localhost:8080` et `localhost:9000`.
- Le backend bootstrape les données de démo à chaque démarrage de la stack Docker.
