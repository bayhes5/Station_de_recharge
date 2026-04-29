# Station de recharge

Prototype de station de recharge pour velos electriques.

Le projet rassemble:

- un backend Django avec API REST et pages serveur
- un frontend statique servi par Nginx
- une interface kiosque Raspberry Pi
- une base PostgreSQL pour les donnees de developpement

## Demarrage rapide

1. Copier `.env.example` vers `.env` si besoin, puis verifier les identifiants locaux.
2. Demarrer la stack:

```bash
docker compose up -d --build
```

3. Ouvrir les interfaces utiles:

- `http://localhost:8000` pour le backend Django et les pages serveur
- `http://localhost:8080` pour le frontend statique
- `http://localhost:9000` pour le kiosque Raspberry

## Deploiement depuis un clone Git

Cette procedure permet de repartir d'une machine vierge apres un `git clone`.

### Prerequis

- Git
- Docker et Docker Compose
- Un terminal place dans le dossier du projet

Verifier que Docker est disponible:

```bash
docker --version
docker compose version
```

### 1. Cloner le projet

```bash
git clone <url-du-depot>
cd Station_de_recharge
```

Remplacer `<url-du-depot>` par l'URL du depot Git.

### 2. Creer le fichier d'environnement

Copier le modele fourni:

```bash
cp .env.example .env
```

Sous Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Ouvrir ensuite `.env` et adapter au minimum:

- `SECRET_KEY`: mettre une valeur unique et secrete
- `DEBUG`: mettre `False` hors developpement local
- `ALLOWED_HOSTS`: ajouter le domaine ou l'adresse IP de la machine cible
- `ADMIN_PSEUDO`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`: definir le compte administrateur
- `DEMO_TECH_*`: definir ou modifier le compte technicien de demo si besoin

Pour un lancement local de test, les valeurs de `.env.example` suffisent.

### 3. Construire et demarrer les services

```bash
docker compose up -d --build
```

Cette commande demarre:

- PostgreSQL sur le port `5432`
- Django sur le port `8000`
- le frontend Nginx sur le port `8080`
- le kiosque Raspberry sur le port `9000`

Au demarrage, le backend applique les migrations Django, cree ou met a jour le superuser, puis initialise les donnees de demo.

### 4. Verifier le deploiement

Afficher l'etat des conteneurs:

```bash
docker compose ps
```

Consulter les logs si un service ne demarre pas:

```bash
docker compose logs -f backend
docker compose logs -f db
```

Ouvrir ensuite:

- `http://localhost:8000` pour le backend Django
- `http://localhost:8080` pour le frontend
- `http://localhost:9000` pour le kiosque Raspberry

Sur une autre machine du reseau, remplacer `localhost` par l'adresse IP ou le nom de domaine du serveur.

### Commandes utiles

Arreter les services sans supprimer les donnees:

```bash
docker compose down
```

Redemarrer apres une modification:

```bash
docker compose up -d --build
```

Lancer une commande Django dans le conteneur backend:

```bash
docker compose exec backend python manage.py <commande>
```

Supprimer aussi la base PostgreSQL locale et repartir de zero:

```bash
docker compose down -v
```

Attention: `docker compose down -v` supprime le volume `postgres_data` et donc les donnees de la base locale.

## Composants

- `backend/`: application Django, modele de donnees, API, templates et commandes de bootstrap
- `frontend/`: pages statiques pour l'inscription, la connexion, le dashboard et les vues metier
- `raspberry/app/`: mini serveur HTTP pour simuler l'interface kiosque locale
- `esp32/`: prototype firmware / logique embarquee pour un emplacement

## Variables d'environnement

Le fichier `.env.example` couvre les variables principales:

- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `FRONTEND_BASE_URL`, `CORS_ALLOWED_ORIGINS`
- `SIMPLE_JWT_ACCESS_MINUTES`, `SIMPLE_JWT_REFRESH_DAYS`
- `ADMIN_PSEUDO`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`
- `DEMO_STATION_*`, `DEMO_TECH_*`

## Donnees de demo

Au demarrage du backend dans Docker:

- le superuser local est cree ou mis a jour automatiquement
- une station de demo est creee avec ses emplacements
- un technicien de demo est cree automatiquement
- une maintenance de demonstration est ajoutee

Comptes de demo actuels dans le fichier `.env` fourni:

- admin: `admin / Admin123!`
- technicien: `tech / Tech123!`

Ces valeurs peuvent etre modifiees via `.env`.

## Points d'entree utiles

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

- `/api/schema/` schema OpenAPI genere par drf-spectacular
- `/api/docs/` documentation interactive Swagger UI
- `/api/redoc/` documentation interactive Redoc
- `docs/` documentation technique Sphinx

Tests:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest
```

Avec couverture:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest --cov=api --cov-report=term-missing
```

Les tests utilisent `config.test_settings` et une base SQLite locale pour rester
independants de PostgreSQL.

## Kiosque Raspberry

Le kiosque est un simple serveur HTTP local lance sur le port `9000`.

En dehors de Docker, il peut etre demarre avec:

```bash
python raspberry/app/main.py
```

## Notes techniques

- Le backend utilise PostgreSQL par defaut.
- Les jetons JWT sont exposes via `SimpleJWT`.
- Les origines CORS locales incluent `localhost:8080` et `localhost:9000`.
- Le backend bootstrape les donnees de demo a chaque demarrage de la stack Docker.
