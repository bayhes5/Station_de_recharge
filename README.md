# Station de recharge

Prototype de station de recharge pour vélos électriques.

Le projet rassemble:

- un backend Django avec API REST et pages serveur
- un frontend statique servi par Nginx
- une interface kiosque Raspberry Pi
- une base PostgreSQL pour les données de développement

## Démarrage rapide

1. Copier `.env.example` vers `.env` si besoin, puis vérifier les identifiants locaux.
2. Démarrer la stack:

```bash
docker compose up -d --build
```

3. Ouvrir les interfaces utiles:

- `http://localhost:8000` pour le backend Django et les pages serveur
- `http://localhost:8080` pour le frontend statique
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
- Django sur le port `8000`
- le frontend Nginx sur le port `8080`
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
- `http://localhost:8080` pour le frontend
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

Lancer une commande Django dans le conteneur backend:

```bash
docker compose exec backend python manage.py <commande>
```

Supprimer aussi la base PostgreSQL locale et repartir de zéro:

```bash
docker compose down -v
```

Attention: `docker compose down -v` supprime le volume `postgres_data` et donc les données de la base locale.

## Composants

- `backend/`: application Django, modèle de données, API, templates et commandes de bootstrap
- `frontend/`: pages statiques pour l'inscription, la connexion, le dashboard et les vues métier
- `raspberry/app/`: mini serveur HTTP pour simuler l'interface kiosque locale
- `esp32/`: prototype firmware / logique embarquée pour un emplacement

## Variables d'environnement

Le fichier `.env.example` couvre les variables principales:

- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `FRONTEND_BASE_URL`, `CORS_ALLOWED_ORIGINS`
- `SIMPLE_JWT_ACCESS_MINUTES`, `SIMPLE_JWT_REFRESH_DAYS`
- `ADMIN_PSEUDO`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`
- `DEMO_STATION_*`, `DEMO_TECH_*`

## Données de démo

Au démarrage du backend dans Docker:

- le superuser local est créé ou mis à jour automatiquement
- une station de démo est créée avec ses emplacements
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

Dependances:

- `backend/requirements.in`: dependances directes du backend
- `backend/requirements.txt`: dependances backend verrouillees pour Docker
- `backend/requirements-dev.in`: dependances directes des tests
- `backend/requirements-dev.txt`: dependances de test verrouillees
- `docs/requirements.in`: dependances directes de documentation
- `docs/requirements.txt`: dependances de documentation verrouillees

Les fichiers `.txt` sont ceux installes par Docker et par les commandes locales.
Les fichiers `.in` servent de source lisible quand il faut mettre a jour les
dependances. Apres une mise a jour, reconstruire l'image backend pour verifier
que les tests passent avec les versions verrouillees.

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

## SBOM et securite supply chain

Le projet peut generer un SBOM (Software Bill of Materials) avec Syft, en deux
formats:

- CycloneDX JSON: pratique pour les outils de securite applicative
- SPDX JSON: pratique pour la conformite et les audits de licences

Les fichiers generes localement sont places dans `sbom/`, qui est ignore par Git.
Ils doivent etre regeneres a chaque build ou release plutot que maintenus a la
main dans le depot.

Generation locale depuis les sources:

```powershell
.\scripts\generate-sbom.ps1
```

Si `syft` n'est pas installe localement mais que Docker est disponible:

```powershell
.\scripts\generate-sbom.ps1 -UseDockerSyft
```

Generation locale depuis l'image backend construite, plus representative des
versions reellement installees. Cette commande necessite Docker demarre et Syft
installe localement:

```powershell
.\scripts\generate-sbom.ps1 -Target backend-image
```

Ou avec Syft via Docker:

```powershell
.\scripts\generate-sbom.ps1 -Target backend-image -UseDockerSyft
```

Installer Syft sous Windows:

```powershell
winget install Anchore.Syft
```

Un workflow GitHub Actions genere aussi un SBOM CycloneDX et un SBOM SPDX de
l'image backend a chaque push, pull request ou lancement manuel. Le SBOM est un
inventaire: pour en tirer une valeur securite, il doit etre associe a des scans
de vulnerabilites et a des dependances versionnees.

## Kiosque Raspberry

Le kiosque est un simple serveur HTTP local lancé sur le port `9000`.

En dehors de Docker, il peut être démarré avec:

```bash
python raspberry/app/main.py
```

## Notes techniques

- Le backend utilise PostgreSQL par défaut.
- Les jetons JWT sont exposés via `SimpleJWT`.
- Les origines CORS locales incluent `localhost:8080` et `localhost:9000`.
- Le backend bootstrape les données de démo à chaque démarrage de la stack Docker.
