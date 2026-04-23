# Station de recharge

Prototype de station de recharge de velos electriques avec backend Django, ossature Raspberry Pi et firmware ESP32.

## Demarrage rapide

1. Copier `.env.example` vers `.env` si besoin et ajuster les variables.
2. Demarrer la stack Docker :

```bash
docker compose up -d --build
```

3. Ouvrir :
- `http://localhost:8000` pour le backend Django
- `http://localhost:8080` pour le frontend statique

4. Le superuser local est bootstrap automatiquement au demarrage du backend.
