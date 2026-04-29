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
git clone <url-du-depot>
cd Station_de_recharge
```

Remplacer `<url-du-depot>` par l'URL du dépôt Git.

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
