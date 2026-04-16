# Station de recharge

Prototype de station de recharge de velos electriques avec backend Django, ossature Raspberry Pi et firmware ESP32.

## Demarrage rapide

1. Ouvrir le projet dans le DevContainer.
2. Lancer les migrations :

```bash
python manage.py migrate
```

3. Demarrer le serveur :

```bash
python manage.py runserver 0.0.0.0:8000
```

4. Ouvrir `http://localhost:8000`
