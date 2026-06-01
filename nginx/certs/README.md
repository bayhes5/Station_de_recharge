# Certificat local de développement

Ce dossier contient le certificat auto-signé utilisé par le reverse proxy Nginx
pour exposer `https://localhost` en développement.

Les fichiers `localhost.crt` et `localhost.key` sont fournis uniquement pour la
stack locale Docker. Ils ne doivent jamais être réutilisés en production.

Pour régénérer le certificat local :

```powershell
openssl req -x509 -nodes -newkey rsa:2048 -days 3650 `
  -keyout nginx\certs\localhost.key `
  -out nginx\certs\localhost.crt `
  -config nginx\certs\localhost.conf
```

## Option production locale avec smallstep

Pour une installation LAN plus propre, utiliser une CA locale smallstep au lieu
du certificat autosigné fourni :

```bash
step ca certificate station.local \
  nginx/certs/localhost.crt \
  nginx/certs/localhost.key \
  --san station.local \
  --san 192.168.1.50
chmod 600 nginx/certs/localhost.key
```

La racine smallstep doit ensuite être installée sur les postes, téléphones et
Raspberry qui accèdent à l'application. Pour un domaine public, préférer un
certificat Let's Encrypt ou un certificat fourni par l'infrastructure.
