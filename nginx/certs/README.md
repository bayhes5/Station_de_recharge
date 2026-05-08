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
