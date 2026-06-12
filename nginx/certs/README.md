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

## Option production locale avec Smallstep

Pour une installation LAN plus propre, utiliser une CA locale Smallstep au lieu
du certificat autosigné fourni. Dans le projet, la CA s'appelle `Metropole
Verte` et le serveur Debian est exposé sur `192.168.10.10`.

```bash
step ca certificate 192.168.10.10 \
  nginx/certs/localhost.crt \
  nginx/certs/localhost.key \
  --san 192.168.10.10 \
  --san 127.0.0.1 \
  --san localhost \
  --san SRV-Station \
  --not-after 720h
chmod 600 nginx/certs/localhost.key
```

La racine Smallstep doit ensuite être installée sur les postes, téléphones et
Raspberry qui accèdent à l'application. La racine publique peut être distribuée
aux clients ; les clés privées `*.key` ne doivent jamais être versionnées ni
copiées hors de la machine concernée. Pour un domaine public, préférer un
certificat Let's Encrypt ou un certificat fourni par l'infrastructure.
