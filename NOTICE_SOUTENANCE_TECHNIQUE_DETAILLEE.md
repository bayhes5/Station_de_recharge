# Notice technique détaillée pour soutenance

Ce document est la notice de révision technique complète du projet. Il est
volontairement plus détaillé que les autres notices : son objectif n'est pas
seulement de dire ce qui existe, mais d'expliquer comment chaque mécanisme est
implémenté dans le code, avec quelle librairie, quelle donnée circule, quelle
donnée est stockée, quelle protection est apportée et quelles limites restent à
assumer.

Cette notice sert à répondre aux questions du type :

```text
Comment l'as-tu fait techniquement ?
Où est-ce dans le code ?
Avec quelle librairie ?
Qu'est-ce qui est stocké ?
Quelle protection cela apporte ?
Quelles sont les limites ?
```

Elle complète :

- [`NOTICE_FONCTIONNEMENT_PROJET.md`](NOTICE_FONCTIONNEMENT_PROJET.md)
- [`NOTICE_TECHNIQUE_IMPLEMENTATION.md`](NOTICE_TECHNIQUE_IMPLEMENTATION.md)

## Mode d'emploi pour l'oral

Pour chaque sujet, la logique de réponse est toujours la même :

```text
1. Où ?
   -> fichier, fonction, modèle ou service concerné.

2. Comment ?
   -> mécanisme exact dans le code.

3. Avec quoi ?
   -> librairie, API Django, protocole ou composant système utilisé.

4. Qu'est-ce qui est stocké ou transmis ?
   -> table, champ, payload, cookie, token, topic MQTT, message WebSocket.

5. Pourquoi ce choix ?
   -> sécurité, robustesse, performance, maintenabilité ou réalisme terrain.

6. Quelles limites ?
   -> ce qui est simulé, ce qui dépend du matériel, ce qui reste à durcir.
```

Exemple de niveau attendu :

```text
Je ne dis pas seulement "les mots de passe sont hashés".
J'explique que create_user() appelle set_password(), que Django produit une
chaîne de type algorithme$itérations$sel$hash, que check_password() relit cette
chaîne pour recalculer la valeur attendue, et que ce choix évite un SHA-256 brut
avec hashlib qui serait trop rapide pour des mots de passe.
```

## 0. Gestion de projet, agile léger et DevOps

### Question possible

Comment avez-vous géré votre projet ?

### Réponse structurée

Le projet a été géré par découpage en trois périmètres :

```text
Partie 1 : application web/backend, API, base, supervision, sécurité
Partie 2 : Raspberry Pi, kiosque, RFID, interface tactile, mode local
Partie 3 : ESP32, capteurs, serrure, télémétrie, alertes physiques
```

L'équipe a utilisé une méthode agile légère. Ce n'était pas un Scrum complet avec tous les rôles formalisés, mais une organisation par itérations :

```text
1. cadrer une fonctionnalité ou un scénario ;
2. définir le contrat entre les parties ;
3. implémenter chacun dans son périmètre ;
4. tester en simulation ou avec le matériel disponible ;
5. corriger selon les retours ;
6. documenter ce qui a été stabilisé.
```

### Outils de coordination

```text
Teams
  -> points de suivi, décisions plus formelles, organisation globale

Discord
  -> échanges rapides, captures d'erreurs, debug réseau, tests matériels en direct

GitHub
  -> dépôt central, commits, branches, pull requests, CI et historique

Documentation
  -> notices, contrats MQTT/API, procédures Raspberry/ESP32, scénarios de test
```

### Contrats d'interface

Le point important est que les parties ne sont pas seulement juxtaposées. Elles communiquent par contrats :

```text
Frontend/PWA -> API REST Django
Raspberry -> API terminal Django
Raspberry/backend/ESP32 -> topics MQTT
Backend/Grafana -> PostgreSQL/TimescaleDB
```

Ces contrats précisent les URL, méthodes HTTP, payloads JSON, topics MQTT, ACK, statuts et champs attendus. Cela évite que le Raspberry dépende directement des tables SQL ou que l'ESP32 dépende directement de Django.

### DevOps : formulation prudente

La formulation à utiliser en soutenance est :

> Nous nous sommes inspirés d'une démarche DevOps, sans prétendre avoir mis en place une chaîne DevOps industrielle complète.

Pratiques réellement mises en place :

- GitHub comme dépôt central ;
- branches, commits, pull requests et merge vers `main` ;
- CI GitHub Actions ;
- tests automatisés backend, frontend et Raspberry ;
- Ruff pour la qualité Python ;
- CodeQL pour l'analyse statique ;
- SBOM/Grype pour l'inventaire et l'analyse de vulnérabilités ;
- Docker Compose pour rendre l'environnement reproductible ;
- documentation de déploiement Debian ;
- scripts de sauvegarde/restauration ;
- supervision Grafana et alertes.

Limites à annoncer honnêtement :

- pas encore de déploiement continu automatique vers un serveur de production ;
- pas d'environnement staging complet ;
- pas de gestionnaire de secrets avancé type Vault ;
- pas de rollback automatisé ;
- pas de tests E2E automatisés sur matériel réel.

### Phrase de soutenance

> Nous avons géré le projet avec une organisation agile légère : découpage par périmètres, points de coordination via Teams, échanges rapides via Discord, GitHub pour le code et la CI, et contrats d'interface pour relier les parties. Côté DevOps, nous avons appliqué plusieurs pratiques adaptées au cadre académique : tests automatisés, Docker Compose, CodeQL, SBOM et documentation de déploiement. Il manquerait encore une CD réelle, un staging et des tests E2E matériels pour parler d'une chaîne DevOps industrielle.

## 1. Mots de passe utilisateur

### Question possible

Comment sont stockés les mots de passe ? Est-ce un hash ? Où ?

### Réponse technique

Les mots de passe sont gérés par le système natif de Django. Le projet ne stocke jamais le mot de passe en clair et ne fait pas un hash manuel avec `hashlib`.

À la création d'un utilisateur, le code appelle :

```python
user.set_password(password)
```

Référence :

- `UtilisateurManager.create_user()` dans [`backend/api/models.py`](backend/api/models.py)

À la connexion, la vérification appelle :

```python
user.check_password(password)
```

Référence :

- `UtilisateurBackend.authenticate()` dans [`backend/api/auth_backends.py`](backend/api/auth_backends.py)

### Mécanisme interne

Django stocke le mot de passe sous une chaîne auto-descriptive :

```text
pbkdf2_sha256$1200000$salt_aleatoire$hash_final
```

Les parties signifient :

```text
pbkdf2_sha256
  -> algorithme de dérivation

1200000
  -> nombre d'itérations PBKDF2 dans la version Django installée

salt_aleatoire
  -> sel unique propre à ce mot de passe

hash_final
  -> résultat final après dérivation
```

Le sel évite que deux utilisateurs ayant le même mot de passe aient la même valeur stockée. Les itérations rendent les attaques par dictionnaire plus coûteuses.

### Ce qui est stocké

La valeur est stockée dans le champ `password` hérité de `AbstractBaseUser`.

Référence :

- `class Utilisateur(AbstractBaseUser, PermissionsMixin)` dans [`backend/api/models.py`](backend/api/models.py)

### Ce qui est volontairement évité

Le projet évite :

```python
hashlib.sha256(password.encode()).hexdigest()
```

Un SHA-256 brut est trop rapide, n'intègre pas automatiquement de sel et n'est pas adapté au stockage de mots de passe.

### Phrase de soutenance

> Les mots de passe sont stockés avec le mécanisme natif de Django. J'appelle `set_password()` à la création et `check_password()` à la connexion. Django stocke une chaîne de type `algorithme$itérations$sel$hash`, ici PBKDF2-SHA256, ce qui évite un hash SHA-256 brut et bénéficie des protections du framework.

### Réinitialisation par l'administrateur

Question possible :

```text
Comment l'administrateur réinitialise-t-il un mot de passe maintenant qu'il y a Mailpit ?
```

Réponse technique :

L'endpoint concerné est :

```text
POST /api/admin/users/<id>/reset-password/
```

Références :

- `admin_reset_user_password()` dans [`backend/api/views.py`](backend/api/views.py)
- `send_temporary_password_email()` dans [`backend/api/services/email_notifications.py`](backend/api/services/email_notifications.py)
- `must_change_password` et `password_reset_at` dans [`backend/api/models.py`](backend/api/models.py)
- migration [`backend/api/migrations/0030_user_forced_password_change.py`](backend/api/migrations/0030_user_forced_password_change.py)

Le backend génère un mot de passe provisoire avec `secrets`, en forçant au moins :

```text
une minuscule
une majuscule
un chiffre
un caractère spécial
```

Il valide ensuite ce mot de passe avec :

```python
validate_django_password(password, user=user)
```

Le mot de passe provisoire est enregistré avec :

```python
user.set_password(temporary_password)
```

Il n'est donc pas stocké en clair dans la base. Le compte est marqué :

```python
user.must_change_password = True
user.password_reset_at = timezone.now()
```

Puis le mot de passe provisoire est envoyé par e-mail avec `EmailMultiAlternatives`.
En développement, l'e-mail arrive dans Mailpit. La réponse API ne contient plus
le mot de passe provisoire ; elle indique seulement que l'e-mail a été envoyé.

Côté frontend :

- `frontend/js/login.js` lit `user.must_change_password` après connexion ;
- si la valeur est vraie, l'utilisateur est redirigé vers `profile.html?force_password_change=1` ;
- `frontend/js/profile.js` affiche le message de changement obligatoire ;
- `POST /api/me/change-password/` met `must_change_password` à `False` quand le nouveau mot de passe est accepté.

Phrase de soutenance possible :

> Quand l'admin réinitialise un compte, je ne renvoie plus le mot de passe provisoire dans l'interface admin. Le backend génère un mot de passe conforme, l'enregistre avec `set_password()`, marque le compte en changement obligatoire, puis l'envoie par e-mail via Mailpit. À la connexion, le frontend voit `must_change_password` et redirige l'utilisateur vers le formulaire de changement de mot de passe.

## 2. Règles de complexité des mots de passe

### Question possible

Quelles règles empêchent un mot de passe trop faible ?

### Réponse technique

Deux niveaux sont utilisés :

1. les validateurs Django configurés dans `AUTH_PASSWORD_VALIDATORS` ;
2. une validation métier dans le serializer d'inscription.

Références :

- `AUTH_PASSWORD_VALIDATORS` dans [`backend/config/settings.py`](backend/config/settings.py)
- `RegisterSerializer.validate_password()` dans [`backend/api/serializers.py`](backend/api/serializers.py)

### Mécanisme interne

Le serializer vérifie notamment :

- longueur minimale de 12 caractères ;
- au moins une minuscule ;
- au moins une majuscule ;
- au moins un chiffre ;
- au moins un caractère spécial ;
- le mot de passe ne doit pas contenir le pseudo ;
- le mot de passe ne doit pas contenir la partie principale de l'email.

Le code utilise des expressions régulières :

```python
re.search(r"[a-z]", value)
re.search(r"[A-Z]", value)
re.search(r"\d", value)
re.search(r"[^A-Za-z0-9]", value)
```

### Ce qui est stocké

Seul le hash Django final est stocké. Les règles de validation ne sont pas stockées utilisateur par utilisateur.

## 3. Connexion par pseudo ou email

### Question possible

Comment l'utilisateur peut-il se connecter avec pseudo ou email ?

### Réponse technique

Le projet définit un backend d'authentification personnalisé.

Référence :

- [`backend/api/auth_backends.py`](backend/api/auth_backends.py)

Configuration :

- `AUTHENTICATION_BACKENDS` dans [`backend/config/settings.py`](backend/config/settings.py)

### Mécanisme interne

Le backend récupère l'identifiant saisi :

```python
lookup = identifiant or username or email
```

Il cherche ensuite :

```python
Q(pseudo__iexact=lookup) | Q(email__iexact=lookup)
```

Puis il vérifie le mot de passe :

```python
user.check_password(password)
```

Le suffixe `__iexact` rend la recherche insensible à la casse.

### Limites

Si deux comptes avaient le même email ou pseudo avec une casse différente, les contraintes d'unicité du modèle empêchent déjà cette situation.

## 4. Tokens JWT

### Question possible

Comment sont gérés les tokens ? Où sont-ils stockés côté navigateur ?

### Réponse technique

Le projet utilise `djangorestframework-simplejwt`.

Références :

- `SIMPLE_JWT` dans [`backend/config/settings.py`](backend/config/settings.py)
- `login()` dans [`backend/api/views.py`](backend/api/views.py)
- `refresh_token()` dans [`backend/api/views.py`](backend/api/views.py)
- Client frontend : [`frontend/js/api.js`](frontend/js/api.js)

### Mécanisme interne

À la connexion :

```python
refresh = RefreshToken.for_user(user)
access = refresh.access_token
```

Le backend renvoie l'access token dans la réponse JSON :

```json
{
  "access": "...",
  "user": {...}
}
```

Le refresh token est stocké dans un cookie HttpOnly :

```python
response.set_cookie(
    settings.JWT_REFRESH_COOKIE_NAME,
    str(refresh_token),
    httponly=True,
    secure=settings.JWT_REFRESH_COOKIE_SECURE,
    samesite=settings.JWT_REFRESH_COOKIE_SAMESITE,
    path=settings.JWT_REFRESH_COOKIE_PATH,
)
```

Référence :

- `_set_refresh_cookie()` dans [`backend/api/views.py`](backend/api/views.py)

### Côté frontend

Dans [`frontend/js/api.js`](frontend/js/api.js), le frontend :

- garde l'access token en mémoire ;
- envoie `Authorization: Bearer <access_token>` ;
- envoie les cookies avec `credentials: "include"` ;
- tente `/api/token/refresh/` si une requête renvoie `401`.

### Ce qui est stocké

```text
Access token
  -> mémoire JavaScript
  -> durée courte

Refresh token
  -> cookie HttpOnly
  -> non lisible directement par JavaScript
```

### Protection apportée

Le refresh token étant HttpOnly, un script JavaScript injecté ne peut pas simplement le lire avec `localStorage` ou `document.cookie`.

### Limites

Le cookie HttpOnly ne supprime pas le risque CSRF à lui seul. Le projet limite ce risque par :

- `SameSite` ;
- CORS contrôlé ;
- HTTPS en production ;
- endpoints API JSON avec authentification Bearer pour l'access token.

## 5. Journalisation de sécurité

### Question possible

Comment tracez-vous les actions sensibles ?

### Réponse technique

Le projet utilise le modèle `JournalSecurite`.

Références :

- `JournalSecurite` dans [`backend/api/models.py`](backend/api/models.py)
- `_log_security_event()` dans [`backend/api/views.py`](backend/api/views.py)

### Mécanisme interne

La fonction écrit :

```python
JournalSecurite.objects.create(
    utilisateur=target_user,
    action=action,
    ip=_client_ip(request),
    statut=statut,
)
```

L'IP est récupérée via :

```python
HTTP_X_FORWARDED_FOR
REMOTE_ADDR
```

Référence :

- `_client_ip()` dans [`backend/api/views.py`](backend/api/views.py)

### Exemples d'actions journalisées

- envoi du QR par email ;
- envoi du code SMS ;
- synchronisation d'événement offline ;
- certaines opérations sensibles d'accès.

### Limite

Le journal de sécurité reste un journal applicatif. En production, il doit être complété par les logs Nginx, Docker et système.

## 6. Rate limiting

### Question possible

Comment empêchez-vous les attaques par brute force sur login ou SMS ?

### Réponse technique

Le projet utilise les throttles de Django REST Framework.

Références :

- [`backend/api/throttles.py`](backend/api/throttles.py)
- `DEFAULT_THROTTLE_RATES` dans [`backend/config/settings.py`](backend/config/settings.py)

### Mécanisme interne

Toutes les classes héritent de :

```python
rest_framework.throttling.SimpleRateThrottle
```

La clé de limitation est :

```text
utilisateur authentifié si disponible
sinon IP cliente
```

Référence :

- `ClientScopedRateThrottle.get_cache_key()` dans [`backend/api/throttles.py`](backend/api/throttles.py)

### Seuils actuels

```text
login           -> 10/minute
register        -> 5/hour
token_refresh   -> 30/minute
auth_factor     -> 20/minute
sms             -> 3/minute
terminal        -> 120/minute
mobile_session  -> 60/minute
```

### Justification des paramètres chiffrés de la slide 22

| Paramètre | Valeur | Justification |
|---|---:|---|
| Connexion | `10/min` | Suffisant pour un humain qui se trompe plusieurs fois, trop bas pour laisser tourner une attaque brute force rapide. |
| Inscription | `5/h` | La création de compte est rare dans un usage normal. Cette limite réduit les comptes abusifs et les tests automatisés. |
| Refresh JWT | `30/min` | Un refresh automatique peut arriver après des `401`, mais il ne doit pas devenir une boucle infinie de renouvellement. |
| Moyens d'accès | `20/min` | QR, RFID, code SMS et association badge peuvent être retentés, mais doivent rester bornés contre les essais automatisés. |
| SMS | `3/min` | Le SMS est coûteux et intrusif. La limite évite le spam d'envoi ou de renvoi de code. |
| Terminal | `120/min` | La borne doit rester fluide : polling, validation, état session et synchronisation. Le seuil est donc plus haut qu'un login, mais pas illimité. |
| Session mobile | `60/min` | Le téléphone peut interroger l'état de la session de borne, mais la fréquence reste bornée pour éviter l'abus. |
| Code SMS | `8` caractères | Le clavier matriciel limite l'alphabet à `0-9/A-D`. La longueur compense cette contrainte matérielle. |
| Alphabet SMS | `14` symboles | Correspond aux touches disponibles : dix chiffres plus `A-D`. |
| Espace SMS | `14^8 = 1 475 789 056` | Rend le code difficile à deviner, surtout avec expiration, rate limiting et verrouillage. |
| Essais SMS | `5 max` | Probabilité brute maximale ≈ `5 / 14^8`, soit environ `1 chance sur 295 millions` par code. |
| Access token JWT | `60 min` par défaut | Compromis prototype : assez court pour limiter la durée d'un jeton volé, assez long pour éviter de gêner la démonstration. |
| Refresh token JWT | `7 jours` par défaut | Permet de garder une session web pratique ; il est placé en cookie `HttpOnly`, donc non lisible par JavaScript. |
| Secret terminal | minimum `24` caractères | Un secret court ou par défaut est refusé par les checks de déploiement. En production, la procédure recommande une valeur aléatoire longue, par exemple `openssl rand -hex 32`. |
| `SECRET_KEY` Django | minimum `32` caractères | La clé signe et protège plusieurs mécanismes Django/JWT/HMAC. Une valeur faible ou par défaut bloque les checks production. |
| HSTS production | `31536000` secondes | Un an : durée classique après validation HTTPS, pour forcer les navigateurs à utiliser HTTPS. |
| HSTS sous-domaines | désactivé | Le prototype utilise une IP LAN et non un domaine public avec sous-domaines maîtrisés. Activer `includeSubDomains` serait artificiel. |
| HSTS preload | désactivé | Le préchargement navigateur n'est pertinent que pour un domaine public stable. Sur une CA privée locale, il pourrait bloquer des essais si la configuration change. |
| Certificat HTTPS | `30 jours` | Durée courte suffisante pour une démonstration, qui force à documenter le renouvellement et limite l'impact d'une fuite de clé. |

Phrase de soutenance :

> Les paramètres ne sont pas arbitraires. Les limites basses protègent les zones
> sensibles comme connexion, inscription ou SMS. Les limites plus hautes, comme
> le terminal, tiennent compte du fonctionnement réel de la borne. Pour le code
> SMS, le clavier limite l'alphabet, donc la sécurité vient de la longueur, de
> l'expiration, du nombre d'essais et du rate limiting.

À l'oral, si on me demande pourquoi je n'active pas `includeSubDomains` et
`preload`, la réponse est : ces options sont faites pour un domaine public
stable. Ici, on travaille sur `https://192.168.10.10` avec une CA privée
`Metropole Verte`. Le bon choix est donc d'activer HSTS pour forcer HTTPS sur
l'origine utilisée, mais de ne pas inscrire une politique globale impossible à
garantir sur des sous-domaines inexistants.

### Où c'est appliqué ?

Exemples :

```python
@throttle_classes([LoginRateThrottle])
@throttle_classes([SmsRateThrottle])
@throttle_classes([TerminalRateThrottle])
```

Référence :

- [`backend/api/views.py`](backend/api/views.py)

### Limite

Le rate limiting dépend du cache configuré. En production, Redis doit être disponible pour que la limitation soit partagée entre workers.

## 7. Secrets temporaires QR et SMS

### Question possible

Comment générez-vous les QR et codes SMS sans stocker le clair ?

### Réponse technique

Le projet dérive les secrets temporaires avec `HMAC-SHA256`, à partir de `SECRET_KEY`, de l'identifiant d'authentification, du code réservation, du mode et d'un nonce.

Références :

- `_generate_access_nonce()` dans [`backend/api/views.py`](backend/api/views.py)
- `_derive_temporary_access_secret()` dans [`backend/api/views.py`](backend/api/views.py)
- `_create_temporary_auth()` dans [`backend/api/views.py`](backend/api/views.py)

### Mécanisme interne

Le nonce est généré par :

```python
secrets.token_urlsafe(18)
```

Le matériau HMAC est :

```text
id_auth | reservation_code | auth_mode | nonce
```

Le digest est calculé avec :

```python
hmac.new(
    settings.SECRET_KEY.encode("utf-8"),
    material,
    hashlib.sha256,
).digest()
```

Le secret clair est ensuite :

- transformé en token QR pour le mode `qr` ;
- transformé en code clavier pour le mode `code`.

Le hash stocké en base est :

```python
hash_secret(clear_value)
```

Référence :

- `hash_secret()` dans [`backend/api/services/auth_methods.py`](backend/api/services/auth_methods.py)

### Ce qui est stocké

Dans `Authentification` :

```text
hash_valeur     -> hash SHA-256 du secret clair
display_value   -> uniquement une indication masquée
metadata        -> nonce, type, date expiration, politique de code
expiration      -> fin de validité
is_active       -> actif/révoqué
```

Référence :

- `Authentification` dans [`backend/api/models.py`](backend/api/models.py)

### Protection apportée

Si la base fuit, le QR ou le code SMS utilisable n'est pas directement lisible. Le backend peut le dériver à nouveau tant qu'il dispose de `SECRET_KEY`, du nonce et des métadonnées.

### Limite

Si `SECRET_KEY` fuit avec la base, les secrets temporaires peuvent être redérivés. D'où l'importance de protéger `SECRET_KEY` en production.

## 8. QR de réservation

### Question possible

Le QR est-il généré à la réservation ou à la borne ?

### Réponse technique

Le QR de réservation est généré à la réservation. Il est lié à une réservation précise.

Le QR affiché par la borne pour le téléphone est un autre QR : c'est un QR de session mobile temporaire.

### Mécanisme QR réservation

Le payload QR est :

```json
{
  "v": 1,
  "type": "reservation_access",
  "reservation": "DEMOQR1",
  "token": "QR-..."
}
```

Référence :

- `_build_qr_payload()` dans [`backend/api/views.py`](backend/api/views.py)

Le QR SVG est généré avec :

```python
import qrcode
from qrcode.image.svg import SvgPathImage
```

Référence :

- `_build_qr_svg()` dans [`backend/api/views.py`](backend/api/views.py)

### Envoi email

L'email est construit avec :

```python
EmailMultiAlternatives(...)
message.attach_alternative(html, "text/html")
```

Référence :

- `send_reservation_qr_email()` dans [`backend/api/services/email_notifications.py`](backend/api/services/email_notifications.py)

En développement, l'email est capturé par Mailpit.

Référence :

- service `mailpit` dans [`docker-compose.yml`](docker-compose.yml)

## 9. Code SMS temporaire

### Question possible

Pourquoi 8 caractères ? Pourquoi seulement 0-9 et A-D ?

### Réponse technique

Le code SMS doit rester compatible avec un clavier matriciel 4x4. L'alphabet choisi est donc :

```text
0123456789ABCD
```

La longueur par défaut est 8.

Références :

- [`backend/api/services/sms_access_policy.py`](backend/api/services/sms_access_policy.py)
- variables `SMS_ACCESS_CODE_*` dans [`backend/config/settings.py`](backend/config/settings.py)

### Mécanisme interne

Le digest HMAC est converti en code par :

```python
_digest_to_keypad_code()
```

Référence :

- [`backend/api/views.py`](backend/api/views.py)

Le code évite un biais modulo trop fort en rejetant les octets hors plage :

```python
max_accepted = (256 // len(KEYPAD_CODE_ALPHABET)) * len(KEYPAD_CODE_ALPHABET)
if byte >= max_accepted:
    continue
```

### Espace de recherche

```text
14^8 = 1 475 789 056 combinaisons
```

Avec 5 essais maximum, la probabilité de réussite brute est très faible.

### Verrouillage

Le nombre d'échecs est stocké dans `Authentification.metadata` :

```text
sms_failed_attempts
sms_last_failed_at
sms_locked_at
sms_locked_reason
```

Références :

- `_record_sms_access_failure()` dans [`backend/api/views.py`](backend/api/views.py)
- `_sms_access_is_locked()` dans [`backend/api/views.py`](backend/api/views.py)

### Envoi

Le service SMS abstrait est :

- [`backend/api/services/sms.py`](backend/api/services/sms.py)

Backends :

- `console`
- `twilio`
- `brevo`
- `disabled`

L'envoi réel utilise `urllib.request.Request` et `urlopen` pour Twilio/Brevo.

## 10. RFID ACR122U

### Question possible

Comment le badge est-il lu ? Est-ce que le web lit le badge ?

### Réponse technique

Le web ne lit jamais le badge. L'UID vient uniquement du lecteur RFID branché au Raspberry.

Références :

- [`raspberry/app/rfid_reader.py`](raspberry/app/rfid_reader.py)
- `terminal_link_rfid()` dans [`backend/api/views.py`](backend/api/views.py)

### Mécanisme côté Raspberry

Le lecteur ACR122U est supporté via PC/SC avec la librairie `pyscard`.

Imports utilisés :

```python
from smartcard.CardRequest import CardRequest
from smartcard.System import readers
from smartcard.util import toHexString
```

La lecture UID utilise l'APDU :

```text
FF CA 00 00 00
```

Dans le code :

```python
data, sw1, sw2 = connection.transmit([0xFF, 0xCA, 0x00, 0x00, 0x00])
```

Si la réponse est `90 00`, l'UID est accepté.

### Normalisation

L'UID est normalisé avec :

```python
"".join(char for char in value.upper() if char.isalnum())
```

Référence :

- `normalize_uid()` dans [`raspberry/app/rfid_reader.py`](raspberry/app/rfid_reader.py)

### Debounce

Pour éviter plusieurs lectures du même badge en quelques millisecondes, le Raspberry conserve le dernier UID lu et ignore les doublons pendant une courte période.

Référence :

- `RfidScanStore` dans [`raspberry/app/rfid_reader.py`](raspberry/app/rfid_reader.py)

### Stockage backend

Le backend stocke le hash de l'UID RFID dans `Authentification.hash_valeur`.

Référence :

- `ensure_rfid_auth()` dans [`backend/api/services/auth_methods.py`](backend/api/services/auth_methods.py)

## 11. Session mobile borne/téléphone

### Question possible

Comment le QR affiché par la borne sait à quelle réservation il correspond ?

### Réponse technique

Il ne correspond pas directement à une réservation. Il correspond à une session temporaire de borne. L'utilisateur choisit ensuite sa réservation depuis son téléphone.

### Mécanisme

Le token est généré par :

```python
secrets.token_urlsafe(MOBILE_SESSION_TOKEN_BYTES)
```

Référence :

- `_generate_mobile_session_token()` dans [`backend/api/views.py`](backend/api/views.py)

Il est stocké dans le cache :

```python
cache.set("mobile-session:<token>", payload, timeout=ttl)
```

Référence :

- `_store_mobile_session()` dans [`backend/api/views.py`](backend/api/views.py)

Le payload contient :

```text
token
status
station_id
borne_id
station_nom
borne_nom
created_at
expires_at
reservation_id si autorisé
session_id si consommé
```

Les statuts possibles sont :

```text
pending    -> QR de borne créé, aucune réservation choisie
authorized -> réservation choisie depuis la PWA mobile
consumed   -> autorisation consommée par le kiosque
```

### Flux exact

```text
Raspberry
  -> POST /api/terminal/mobile-sessions/
  -> reçoit token + URL
  -> affiche QR

Téléphone
  -> ouvre /mobile-session.html?token=...
  -> se connecte si nécessaire
  -> GET /api/mobile-sessions/<token>/
  -> liste réservations compatibles
  -> POST /api/mobile-sessions/<token>/authorize/
  -> affiche "Autorisation confirmée"
  -> interroge GET /api/mobile-sessions/<token>/
  -> affiche "Borne autorisée" quand status=consumed

Raspberry
  -> interroge /terminal/mobile-sessions/status/
  -> consomme /terminal/mobile-sessions/consume/
  -> reçoit session + slot_id + mqtt_prefix
  -> publie UNLOCK vers l'ESP32
  -> affiche l'écran de branchement après ACK unlocked
```

Si la page mobile est rafraîchie après autorisation, `mobile_session_detail()`
renvoie aussi la réservation sélectionnée. La PWA peut donc reconstruire l'écran
avec la bonne station, la bonne borne et le bon emplacement au lieu de perdre le
contexte.

Références :

- [`frontend/js/mobile-session.js`](frontend/js/mobile-session.js)
- [`raspberry/app/app.js`](raspberry/app/app.js)
- vues mobile/terminal dans [`backend/api/views.py`](backend/api/views.py)

## 11 bis. PWA et mode hors ligne mobile

### Question possible

```text
Que se passe-t-il si le téléphone perd le réseau ?
Est-ce que la PWA peut valider une réservation hors ligne ?
```

### Réponse technique

Le mode hors ligne de la PWA est volontairement limité. Il ne remplace pas le
backend et ne valide jamais une réservation sans serveur. Il sert uniquement à
éviter une page blanche ou une erreur navigateur quand le téléphone ne peut plus
joindre l'application.

Références :

- [`frontend/public/manifest.webmanifest`](frontend/public/manifest.webmanifest)
- [`frontend/public/sw.js`](frontend/public/sw.js)
- [`frontend/js/pwa.js`](frontend/js/pwa.js)
- [`frontend/offline.html`](frontend/offline.html)

### Mécanisme

Le fichier `frontend/js/api.js` importe `frontend/js/pwa.js`. Ce script
enregistre le service worker `frontend/public/sw.js` lorsque l'application n'est
pas lancée en développement local.

Le service worker installe un cache applicatif léger :

```javascript
const APP_SHELL = [
  "/",
  "/index.html",
  "/login.html",
  "/register.html",
  "/offline.html",
  "/manifest.webmanifest",
  "/icons/pwa-icon.svg",
  "/icons/pwa-icon-192.png",
  "/icons/pwa-icon-512.png",
  "/icons/pwa-maskable-512.png"
];
```

Les appels API sont explicitement exclus :

```javascript
if (url.pathname.startsWith("/api/")) {
  return;
}
```

Cela signifie que les réservations, sessions, profils, moyens d'accès et
autorisations borne restent toujours demandés au backend.

### Pages privées

Les pages privées ne sont pas servies depuis un ancien cache :

```javascript
const PRIVATE_NAVIGATION_PATHS = new Set([
  "/admin-dashboard.html",
  "/admin-form.html",
  "/admin-station.html",
  "/dashboard.html",
  "/mobile-session.html",
  "/profile.html",
  "/reservation.html",
  "/technician-dashboard.html"
]);
```

Si le réseau tombe sur l'une de ces pages, le service worker renvoie
`offline.html` au lieu d'afficher un écran de compte potentiellement obsolète.
Ce choix évite de présenter de fausses informations après une déconnexion, une
expiration de jeton ou une révocation côté serveur.

### IP Wi-Fi et tests locaux

Pendant les tests sur téléphone via l'adresse IP Wi-Fi du PC, `frontend/js/pwa.js`
désactive le service worker sur les IP privées. Cela évite que le navigateur du
téléphone conserve une ancienne version de l'application pendant les essais.

### Différence avec le mode dégradé Raspberry

La PWA hors ligne est un mécanisme d'ergonomie mobile. Elle affiche un écran
propre quand le réseau tombe, mais ne prend aucune décision métier.

Le mode dégradé Raspberry est un mécanisme terrain. Le Raspberry conserve un
cache SQLite d'autorisations déjà synchronisées et peut valider localement
certains accès si le backend central devient indisponible.

Le cache n'est pas un historique des dernières réservations créées. Il contient
les droits dont le créneau est proche. Par défaut, l'horizon est de 24 heures :
le backend exporte les réservations confirmées ou actives comprises entre la
tolérance de fin et les prochaines 24 heures. Une réservation créée deux jours
avant peut donc être acceptée si son créneau est dans cette fenêtre ; une
réservation passée ou prévue trop loin ne reste pas dans le cache.

Phrase de soutenance possible :

> Le mode dégradé n'est pas un mode autonome complet. Il permet au Raspberry de
> continuer environ 24 heures avec les droits déjà synchronisés, sans créer de
> nouvelles réservations ni de nouveaux secrets. C'est un compromis entre
> continuité de service et limitation du risque local.

Phrase de soutenance possible :

> Le mode hors ligne de la PWA ne sert pas à autoriser une charge. Il sert à
> afficher une page propre quand le téléphone n'a plus accès au serveur. Les
> pages privées et les appels API ne sont pas servis depuis un ancien cache. La
> vraie continuité de service terrain est portée par le Raspberry, qui dispose
> d'un cache SQLite limité pour les accès déjà synchronisés.

## 12. Secret terminal Raspberry

### Question possible

Comment évitez-vous qu'un client quelconque appelle les endpoints terminal ?

### Réponse technique

Les endpoints terminal sont protégés par un secret partagé `X-Terminal-Secret`.

### Mécanisme backend

Le backend récupère :

```python
request.headers.get("X-Terminal-Secret")
```

ou un Bearer token compatible.

La comparaison utilise :

```python
hmac.compare_digest(provided_secret, expected_secret)
```

Référence :

- `_terminal_secret_response()` dans [`backend/api/views.py`](backend/api/views.py)

`compare_digest` évite une comparaison naïve caractère par caractère sensible au timing.

Une comparaison classique peut théoriquement s'arrêter dès qu'un caractère est
différent. Avec suffisamment d'essais et des mesures de temps très précises, un
attaquant pourrait chercher à déduire combien de caractères initiaux sont
corrects. `hmac.compare_digest` limite ce canal auxiliaire temporel : c'est le
bon outil pour comparer des secrets.

Phrase de soutenance possible :

> Je n'utilise pas `==` pour comparer le secret terminal. J'utilise
> `hmac.compare_digest`, car un secret doit être comparé sans fuite d'information
> par le temps de comparaison. Cette protection s'ajoute au secret long, au HTTPS
> et au rate limiting.

### Mécanisme Raspberry

Le Raspberry ajoute :

```python
headers["X-Terminal-Secret"] = TERMINAL_API_SECRET
```

Référence :

- `backend_headers()` dans [`raspberry/app/main.py`](raspberry/app/main.py)

### Limite

C'est un secret partagé. En production, il doit être long, aléatoire, différent par station si possible, et stocké hors code source.

## 13. Réservation et disponibilité

### Question possible

Comment savez-vous qu'un emplacement est libre ?

### Réponse technique

Le backend recherche les emplacements de la station qui n'ont pas de réservation chevauchante.

Référence :

- `_available_emplacements()` dans [`backend/api/views.py`](backend/api/views.py)

### Mécanisme SQL/Django

Une réservation chevauche si :

```text
reservation.date_debut < nouvelle_date_fin
reservation.date_fin > nouvelle_date_debut
```

Et si son statut est :

```text
confirmee, active, en_attente
```

Le code utilise :

```python
Exists(overlapping_reservations)
OuterRef("pk")
```

pour annoter les emplacements avec `has_overlap`, puis filtre :

```python
has_overlap=False
```

### Attribution

Si l'utilisateur ne choisit pas manuellement l'emplacement, le backend choisit un emplacement libre ordonné par :

```text
borne__numero
numero
```

### Limite

L'algorithme actuel est robuste pour un prototype. En production large échelle, on pourrait ajouter un scoring avec distance, charge station, maintenance, historique et équilibrage.

## 14. Création de session de charge

### Question possible

Quelle différence entre réservation et session ?

### Réponse technique

La réservation est le droit planifié. La session est l'utilisation réelle de l'emplacement.

Modèles :

- `Reservation` dans [`backend/api/models.py`](backend/api/models.py)
- `Session` dans [`backend/api/models.py`](backend/api/models.py)

### Mécanisme

Lorsqu'un accès est validé, le backend :

1. retrouve la réservation ;
2. vérifie le moyen d'accès ;
3. vérifie station/borne/créneau ;
4. crée ou retrouve `Session` ;
5. passe la réservation à `active` ;
6. passe la session à `access_validated`.

Référence :

- `terminal_authenticate()` dans [`backend/api/views.py`](backend/api/views.py)

Sur le kiosque, cette validation ne lance pas directement la charge électrique.
Elle autorise l'ouverture du boîtier : le Raspberry publie `UNLOCK` vers l'ESP32.
Quand l'ESP32 répond `status=unlocked`, le backend peut projeter la session en
`waiting_plug`. L'utilisateur branche ensuite le câble ; quand la télémétrie
remonte `cable=true`, le Raspberry publie automatiquement `START`.

### Machine d'état

États :

```text
reserved
access_validated
waiting_plug
charging
stopping
stopped
error
```

Référence :

- [`backend/api/services/charge_session_state.py`](backend/api/services/charge_session_state.py)

Fonctions importantes :

- `ensure_session_can_be_started()`
- `mark_access_validated()`
- `mark_state_from_ack()` pour projeter `UNLOCK`, `START` et `STOP`
- `mark_start_ack()`
- `mark_stop_requested()`
- `mark_stopped()`
- `mark_error()`

### Protection apportée

La machine d'état évite les doubles START, les STOP incohérents et les sessions terminées réutilisées.

## 15. Kiosque Raspberry

### Question possible

Le Raspberry est-il un simple écran ?

### Réponse technique

Non. Le Raspberry est un edge controller léger :

- il sert l'interface tactile ;
- il lit le RFID ;
- il proxy les appels vers le backend ;
- il publie les commandes MQTT ;
- il maintient un cache offline SQLite ;
- il conserve l'état local de charge.

Références :

- [`raspberry/app/main.py`](raspberry/app/main.py)
- [`raspberry/app/app.js`](raspberry/app/app.js)
- [`raspberry/app/style.css`](raspberry/app/style.css)
- [`raspberry/app/offline_store.py`](raspberry/app/offline_store.py)
- [`raspberry/app/charge_state.py`](raspberry/app/charge_state.py)

### Serveur local

Le serveur est basé sur :

```python
ThreadingHTTPServer
SimpleHTTPRequestHandler
```

Référence :

- `KioskHandler` dans [`raspberry/app/main.py`](raspberry/app/main.py)

Il écoute sur :

```text
0.0.0.0:9000
```

### Pourquoi un proxy local ?

Le frontend kiosk appelle `/backend-api/...` localement. Le Raspberry ajoute le secret terminal avant de parler au backend. Cela évite d'exposer le secret dans le JavaScript du navigateur.

## 16. Commandes MQTT Raspberry vers ESP32

### Question possible

Comment la borne démarre physiquement une charge ?

### Réponse technique

Après validation backend, le Raspberry publie d'abord un ordre MQTT `UNLOCK` à
l'ESP32 de l'emplacement. La charge électrique ne démarre pas à ce moment-là :
le Raspberry attend que l'ESP32 remonte `cable=true`, puis publie `START`
automatiquement.

Référence :

- [`raspberry/app/mqtt_client.py`](raspberry/app/mqtt_client.py)

### Librairie

```python
paho.mqtt.client
```

### Topic

```text
station/<mqtt_prefix>/<slot_id>/cmd
```

### Payload

```json
{
  "command_id": "uuid",
  "action": "START",
  "issued_at": "date ISO",
  "session_id": "uuid-session",
  "station": "Station Demo",
  "borne": "Borne 1",
  "emplacement": 1,
  "source": "raspberry"
}
```

### ACK

Si `MQTT_ACK_REQUIRED=True`, le Raspberry attend un message correspondant sur :

```text
station/<mqtt_prefix>/<slot_id>/ack
```

Le code utilise :

```python
threading.Event()
```

pour attendre l'ACK.

### Validation de l'ACK

Le Raspberry vérifie :

- même `command_id` si présent ;
- même action ;
- statut connu ;
- statut confirmant pour l'action.

Références :

- [`raspberry/app/mqtt_contract.py`](raspberry/app/mqtt_contract.py)
- [`raspberry/tests/test_mqtt_contract.py`](raspberry/tests/test_mqtt_contract.py)

## 17. Firmware ESP32

### Question possible

Que fait réellement l'ESP32 ?

### Réponse technique

L'ESP32 est l'exécutant matériel de l'emplacement. Il reçoit les commandes MQTT, pilote les sorties si elles sont câblées, lit les capteurs et publie la télémétrie.

Référence :

- [`esp32/emplacement1/main.py`](esp32/emplacement1/main.py)

### Librairies MicroPython

```python
network
machine.Pin
machine.ADC
machine.I2C
umqtt.simple.MQTTClient
dht.DHT22
ujson
```

### Wi-Fi

Connexion :

```python
network.WLAN(network.STA_IF)
station.connect(WIFI_SSID, WIFI_PASSWORD)
```

Référence :

- `connect_wifi()` dans [`esp32/emplacement1/main.py`](esp32/emplacement1/main.py)

### MQTT

Connexion :

```python
MQTTClient(CLIENT_ID, MQTT_HOST, port=MQTT_PORT, ...)
client.set_callback(handle_command)
client.subscribe(TOPIC_CMD)
```

Référence :

- `connect_mqtt()` dans [`esp32/emplacement1/main.py`](esp32/emplacement1/main.py)

### Identité remontée

L'ESP32 remonte :

- `slot_id`
- `client_id`
- `firmware_version`
- `hardware_mac`
- `ip_address`

Référence :

- `device_identity()` dans [`esp32/emplacement1/main.py`](esp32/emplacement1/main.py)

### Serrure électromagnétique

La serrure validée sur le prototype utilise un relais actif-bas sur `GPIO26`.

```python
LOCK_OUTPUT_ENABLED = True
LOCK_PIN = 26
LOCK_RELAY_ACTIVE_LOW = True
LOCK_AUTO_RELOCK_SECONDS = 15
```

Concrètement :

- `0` sur le GPIO active le relais et ouvre la serrure ;
- `1` remet le relais au repos ;
- l'ouverture lance une fenêtre d'accès de 15 secondes ;
- si aucune charge ne démarre pendant cette fenêtre, l'ESP32 reverrouille
  automatiquement l'emplacement.

Sur `UNLOCK`, l'ESP32 renvoie un ACK `unlocked`, exécute l'impulsion de serrure
et publie ensuite un état d'attente de branchement. `START` est séparé :
il ne sert plus à ouvrir la serrure, mais à démarrer la charge après détection
du câble et fermeture du boîtier quand les capteurs seront câblés. Le kiosque
l'envoie automatiquement lorsque l'ESP32 remonte `cable=true`.

## 18. Capteurs ESP32 et calculs électriques

### Question possible

Comment calculez-vous courant, puissance et énergie ?

### Réponse technique

Le prototype lit :

- température/humidité via DHT22 ;
- courant via SEN0214 sur ADC ;
- tension fixe 12 V tant que le capteur tension réel n'est pas câblé.

Référence :

- [`esp32/emplacement1/main.py`](esp32/emplacement1/main.py)

### DHT22

Initialisation :

```python
DHT22(Pin(DHT_PIN))
```

Lecture :

```python
dht_sensor.measure()
temperature = dht_sensor.temperature()
humidity = dht_sensor.humidity()
```

Référence :

- `read_environment()` dans [`esp32/emplacement1/main.py`](esp32/emplacement1/main.py)

### SEN0214

Le SEN0214 est lu avec :

```python
ADC(Pin(ADC_CURRENT_PIN))
adc.atten(ADC.ATTN_11DB)
adc.width(ADC.WIDTH_12BIT)
```

Le code moyenne plusieurs échantillons :

```python
read_average_adc(samples=120)
```

Conversion :

```python
gpio_voltage = (raw / ADC_RESOLUTION) * ADC_VREF
sensor_voltage = gpio_voltage * ADC_CURRENT_INPUT_SCALE
current = (sensor_voltage - zero_voltage) / SEN0214_SENSITIVITY_V_PER_A
```

Le zéro courant est calibré au démarrage :

```python
calibrate_current_zero()
```

### Puissance

```python
power = voltage * current
```

### Énergie

```python
energy_kwh += (power_watts * elapsed_seconds) / 3_600_000
```

Car :

```text
kWh = W * secondes / 3 600 000
```

Référence :

- `update_energy()` dans [`esp32/emplacement1/main.py`](esp32/emplacement1/main.py)

### Limite prototype

La tension est actuellement :

```python
FIXED_BUS_VOLTAGE = 12.0
```

Donc la puissance et l'énergie sont estimées, pas encore mesurées avec une tension réelle.

## 19. Ingestion MQTT backend

### Question possible

Comment les messages ESP32 arrivent-ils en base ?

### Réponse technique

Le service `mqtt-bridge` écoute Mosquitto, reçoit les messages MQTT, les délègue à Celery, puis le backend les écrit en base.

Références :

- [`backend/api/mqtt.py`](backend/api/mqtt.py)
- [`backend/api/tasks.py`](backend/api/tasks.py)
- [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)

### Librairie

```python
paho.mqtt.client
```

### Abonnement

```python
station/#
```

Référence :

- `_subscription_topic()` dans [`backend/api/mqtt.py`](backend/api/mqtt.py)

### Délégation à Celery

Quand un message arrive :

```python
process_mqtt_message_task.delay(topic, payload_text)
```

Référence :

- `_handle_message()` dans [`backend/api/mqtt.py`](backend/api/mqtt.py)

### Routage

Dans [`backend/api/tasks.py`](backend/api/tasks.py) :

```text
.../ack       -> ingest_slot_ack()
.../status    -> ingest_slot_status()
.../telemetry -> ingest_slot_telemetry()
.../alert     -> ingest_slot_telemetry() avec state=error
```

### Pourquoi Celery ?

Le thread MQTT doit rester rapide. Celery absorbe les traitements plus lourds : parsing, lookup base, création capteurs, alertes, WebSocket.

## 20. Rattachement MQTT à Station/Borne/Emplacement

### Question possible

Comment savez-vous qu'un message MQTT vient de l'emplacement réservé ?

### Réponse technique

Le topic contient le préfixe de borne et le slot.

Exemple :

```text
station/station-demo/borne-1/slot1/telemetry
```

Décodage :

```text
station
  -> base topic

station-demo/borne-1
  -> mqtt_prefix de la borne

slot1
  -> slot ESP32

telemetry
  -> type de message
```

Références :

- `_extract_topic_prefix()` dans [`backend/api/tasks.py`](backend/api/tasks.py)
- `_borne_from_topic_prefix()` dans [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)
- `_get_device()` dans [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)

Le champ base de données est :

```python
Borne.mqtt_prefix
```

Référence :

- `Borne` dans [`backend/api/models.py`](backend/api/models.py)

## 21. Stockage des mesures en base

### Question possible

Quelles tables stockent les mesures ?

### Réponse technique

Deux niveaux existent :

```text
CapteurData
  -> mesure brute par capteur/device

SessionTelemetry
  -> mesure électrique liée à une session active
```

Références :

- `Capteur`, `CapteurData`, `SessionTelemetry` dans [`backend/api/models.py`](backend/api/models.py)
- `ingest_slot_telemetry()` dans [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)

### Mécanisme

Le mapping des champs MQTT vers capteurs est dans :

```python
SENSOR_FIELDS
```

Référence :

- [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)

Pour chaque champ présent :

```python
Capteur.objects.get_or_create(...)
CapteurData.objects.create(...)
```

Si une session active existe et que `current` + `voltage` sont présents :

```python
SessionTelemetry.objects.create(
    session=session,
    courant=current,
    tension=voltage,
    energie_kwh=energy or 0.0,
)
```

### Protection métier

Sans session active, la mesure brute peut être stockée dans `CapteurData`, mais elle ne devient pas une mesure de session. Cela permet de détecter une charge sans session.

## 22. ACK START/STOP

### Question possible

Comment savez-vous que l'ESP32 a bien reçu START ou STOP ?

### Réponse technique

L'ESP32 répond sur un topic `/ack` avec le même `command_id` et l'action concernée.

### Côté ESP32

Référence :

- `publish_ack()` dans [`esp32/emplacement1/main.py`](esp32/emplacement1/main.py)

Payload :

```json
{
  "command_id": "uuid",
  "action": "START",
  "status": "charging",
  "message": "Charge démarrée.",
  "session_id": "uuid-session"
}
```

### Côté backend

Référence :

- `ingest_slot_ack()` dans [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)

Le backend :

- met à jour `Device.last_command_*` ;
- écrit `DeviceCommandLog` ;
- fait évoluer la session via `mark_state_from_ack()`.

Pour une validation RFID réussie, la supervision doit donc montrer au minimum :

- `DeviceCommandLog.action = UNLOCK` ;
- `DeviceCommandLog.status = unlocked` ;
- `Device.last_command_action = UNLOCK` ;
- `charging_session.charge_state = waiting_plug` après ACK ;
- puis `START` et `charging` seulement quand le câble est détecté sur
  l'emplacement autorisé.

Modèle :

- `DeviceCommandLog` dans [`backend/api/models.py`](backend/api/models.py)

## 23. Redis et Celery

### Question possible

À quoi sert Redis ? À quoi sert Celery ?

### Réponse technique

Redis est utilisé pour :

- broker Celery ;
- cache applicatif ;
- channel layer WebSocket ;
- sessions mobiles temporaires ;
- codes RFID temporaires ;
- cache catalogue stations.

Celery sert à :

- traiter l'ingestion MQTT hors du thread MQTT ;
- scanner les sessions sans télémétrie ;
- envoyer les notifications d'alertes ;
- appliquer la rétention de télémétrie.

Références :

- `CACHES`, `CELERY_*`, `CHANNEL_LAYERS` dans [`backend/config/settings.py`](backend/config/settings.py)
- [`backend/config/celery.py`](backend/config/celery.py)
- tâches dans [`backend/api/tasks.py`](backend/api/tasks.py)

### Tâches périodiques

```text
api.scan_session_telemetry_gaps
api.notify_pending_alerts
api.prune_old_telemetry
```

Ces tâches sont planifiées dans `CELERY_BEAT_SCHEDULE`.

## 24. TimescaleDB/PostgreSQL

### Question possible

Pourquoi TimescaleDB ? Et que se passe-t-il si l'extension n'est pas disponible ?

### Réponse technique

Le service base utilise une image TimescaleDB compatible PostgreSQL. Le projet peut fonctionner comme PostgreSQL classique, mais active TimescaleDB si l'extension est disponible.

Références :

- service `db` dans [`docker-compose.yml`](docker-compose.yml)
- migration [`backend/api/migrations/0015_enable_timescaledb_extension.py`](backend/api/migrations/0015_enable_timescaledb_extension.py)

### Mécanisme

La migration vérifie :

```sql
SELECT EXISTS (
  SELECT 1 FROM pg_available_extensions
  WHERE name = 'timescaledb'
);
```

Si disponible :

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;
```

### Performance

Des index sont définis dans les modèles et migrations sur :

- dates de réservation ;
- session/timestamp ;
- capteur/timestamp ;
- device/status/last_seen ;
- alerte/status/timestamp ;
- technicien/station.

Références :

- [`backend/api/models.py`](backend/api/models.py)
- migrations [`backend/api/migrations/`](backend/api/migrations/)

### Rétention

Le projet supprime les anciennes mesures brutes via :

- [`backend/api/services/retention.py`](backend/api/services/retention.py)

Paramètre :

```text
TELEMETRY_RETENTION_DAYS=90
```

## 24 bis. Performance applicative

### Question possible

Comment avez-vous pris en compte la performance ?

### Réponse technique

La performance est traitée par plusieurs couches, pas par un seul outil.

Base de données :

- index sur les fenêtres de réservation ;
- index sur les sessions, timestamps de télémétrie, devices et alertes ;
- contraintes en base pour éviter les incohérences ;
- TimescaleDB disponible pour les séries temporelles ;
- `pg_stat_statements` préparé côté production pour identifier les requêtes
  coûteuses ;
- rétention des mesures brutes pour éviter une croissance illimitée.

Backend Django :

- `select_related()` pour charger les relations simples en une seule requête ;
- `prefetch_related()` pour les collections ;
- pagination des listes d'administration ;
- cache Redis du catalogue station/borne/emplacement ;
- séparation des services métier pour éviter des vues trop lourdes.

Asynchrone :

- Celery traite l'ingestion MQTT, les alertes, les notifications et la rétention ;
- le thread MQTT reste rapide et délègue les traitements lourds ;
- Redis sert de broker Celery, cache et couche Channels.

Frontend et Nginx :

- frontend buildé en fichiers statiques ;
- cache long sur `/assets/` et `/static/` ;
- gzip activé ;
- logs Nginx avec temps de réponse ;
- rate limiting et limites de taille de requête.

Preuves :

- [`backend/api/tests/test_query_performance.py`](backend/api/tests/test_query_performance.py)
- [`nginx/nginx.prod.conf`](nginx/nginx.prod.conf)
- [`nginx/prod.conf.d/station.conf`](nginx/prod.conf.d/station.conf)

Phrase de soutenance :

> J'ai traité la performance à plusieurs niveaux : index SQL pour les recherches
> critiques, optimisation ORM avec `select_related` et `prefetch_related`, cache
> Redis pour les données fréquentes, Celery pour sortir l'ingestion MQTT du
> chemin direct, et Nginx pour servir efficacement les assets. Les tests de
> performance vérifient notamment que certaines vues gardent un nombre de
> requêtes constant.

Limite :

> Le projet n'a pas encore subi de test de charge industriel. Si le nombre
> d'ESP32 augmente fortement, il faudra aller plus loin avec hypertables,
> compression TimescaleDB, tuning PostgreSQL et optimisation des requêtes Grafana.

## 25. Grafana

### Question possible

Grafana reçoit-il directement les messages MQTT ?

### Réponse technique

Non. Grafana lit PostgreSQL/TimescaleDB avec des requêtes SQL.

Flux :

```text
ESP32 -> MQTT -> backend -> base -> Grafana
```

Références :

- datasource [`grafana/provisioning/datasources/datasource.yml`](grafana/provisioning/datasources/datasource.yml)
- dashboards [`grafana/dashboards/`](grafana/dashboards/)

### Dashboards provisionnés

Le projet sépare trois besoins de supervision :

- `station-overview.json` : vue d'accueil avec les indicateurs globaux, les
  sessions en cours et les alertes ouvertes.
- `station-supervision.json` : vue technique filtrée par station, borne et
  emplacement pour analyser l'état d'un ESP32 ou d'un emplacement.
- `session-detail.json` : vue dédiée à une session de charge précise.

Si on me demande si Grafana permet de suivre une session en cours, la réponse
est donc oui : la variable `session` du dashboard `session-detail.json` liste les
sessions ouvertes et les sessions récentes. Une fois la session sélectionnée, le
dashboard affiche le contexte de la réservation, le courant, la tension, la
puissance calculée, l'énergie, les commandes UNLOCK/START/STOP, les ACK ESP32
et les alertes liées à cette session.

Ce choix est important : la vue session ne filtre pas seulement par emplacement.
Elle utilise `id_session` dans `session_telemetry`, ce qui évite de confondre les
mesures de deux charges différentes réalisées sur le même emplacement.

### Tables utilisées

Grafana lit notamment :

- `device`
- `capteur`
- `capteur_data`
- `charging_session`
- `session_telemetry`
- `alerte`
- `device_command_log`
- `station`
- `borne`
- `emplacement`

### Pourquoi ce choix ?

Grafana reste un outil de visualisation. La source de vérité est la base.

## 26. Alertes opérationnelles

### Question possible

Comment les alertes sont-elles levées et résolues ?

### Réponse technique

Les alertes sont créées ou mises à jour depuis la télémétrie. Si l'état redevient normal, certaines alertes sont résolues automatiquement.

Référence :

- [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)

### Création sans doublon

La fonction :

```python
_upsert_active_alert()
```

cherche une alerte ouverte du même type et la met à jour au lieu d'empiler des doublons.

### Résolution automatique

La fonction :

```python
_resolve_alerts_for_device()
```

passe l'alerte en `resolue`.

### Seuils

Dans le code :

```text
temperature >= 60 °C -> overheat
current >= 4.0 A -> overcurrent
cable False en charging -> cable_removed
door False en charging -> intrusion
lock False en charging -> lock_unlocked
energy_kwh >= SESSION_ENERGY_ALERT_KWH -> energy_over_limit
waiting_plug trop long -> session_waiting_plug_too_long
```

Références :

- `_create_alert_if_needed()` dans [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)
- paramètres dans [`backend/config/settings.py`](backend/config/settings.py)

### Session sans télémétrie

Une tâche périodique détecte les sessions actives sans mesure récente.
L'état `waiting_plug` est exclu de cette règle, car l'utilisateur peut être en
train de brancher le câble après ouverture du boîtier. Si cet état dure trop
longtemps, le backend crée une alerte dédiée :
`session_waiting_plug_too_long`.

Référence :

- [`backend/api/services/operational_alerts.py`](backend/api/services/operational_alerts.py)

Paramètre :

```text
SESSION_TELEMETRY_STALE_MINUTES=2
SESSION_WAITING_PLUG_STALE_MINUTES=5
```

## 27. Workflow technicien

### Question possible

Un technicien peut-il voir toutes les stations ?

### Réponse technique

Non. Le périmètre technicien est limité par `TechnicienStation`.

Références :

- `Technicien`, `TechnicienStation` dans [`backend/api/models.py`](backend/api/models.py)
- [`backend/api/services/alert_workflow.py`](backend/api/services/alert_workflow.py)
- `TechnicianSupervisionConsumer` dans [`backend/api/consumers.py`](backend/api/consumers.py)

### Mécanisme

Un technicien est associé à une ou plusieurs stations :

```text
technicien_id
station_id
role
is_active
```

Le WebSocket technicien filtre les snapshots selon ces stations.

Le dashboard technicien applique ensuite un filtre station côté interface. Les
lignes de supervision exposent un `station_id` pour les contrôleurs ESP32, les
alertes, les mesures et les commandes récentes. La page
[`frontend/technician-dashboard.html`](frontend/technician-dashboard.html) permet
donc à un technicien affecté à plusieurs stations de limiter immédiatement la
vue à une seule station sans accéder aux autres périmètres.

### Alerte

Un technicien peut :

- prendre en charge ;
- résoudre avec une note.

Références :

- `acknowledge_alert()` dans [`backend/api/services/alert_workflow.py`](backend/api/services/alert_workflow.py)
- `resolve_alert()` dans [`backend/api/services/alert_workflow.py`](backend/api/services/alert_workflow.py)

## 28. Notifications d'alertes

### Question possible

Quand envoyez-vous une notification ?

### Réponse technique

Le backend envoie une notification seulement si l'alerte :

- est active ;
- a un type notifiable ;
- a persisté assez longtemps ;
- n'a pas été notifiée trop récemment ;
- concerne une station avec technicien assigné.

Référence :

- [`backend/api/services/email_notifications.py`](backend/api/services/email_notifications.py)

### Délais

Paramètres :

```text
ALERT_NOTIFICATION_MIN_AGE_SECONDS=120
ALERT_CRITICAL_NOTIFICATION_MIN_AGE_SECONDS=60
ALERT_RENOTIFY_COOLDOWN_SECONDS=1800
```

La fonction centrale est :

```python
alert_is_ready_for_notification()
```

### Envoi

L'envoi utilise :

```python
django.core.mail.send_mail()
```

Les destinataires sont trouvés avec :

```python
TechnicienStation.objects.filter(station=station, is_active=True)
```

## 29. WebSocket supervision

### Question possible

Comment l'interface de supervision reçoit-elle les changements en temps réel ?

### Réponse technique

Le projet utilise Django Channels.

Références :

- [`backend/config/asgi.py`](backend/config/asgi.py)
- [`backend/api/routing.py`](backend/api/routing.py)
- [`backend/api/consumers.py`](backend/api/consumers.py)
- [`backend/api/realtime.py`](backend/api/realtime.py)

### Mécanisme

Après ingestion MQTT, le backend appelle :

```python
broadcast_supervision_update(reason, summary)
```

Référence :

- [`backend/api/tasks.py`](backend/api/tasks.py)

Channels diffuse ensuite au groupe WebSocket.

Routes :

```text
/ws/admin/supervision/
/ws/technician/supervision/
```

En production, la couche Channels passe par Redis.

## 30. Mode dégradé Raspberry

### Question possible

Que se passe-t-il si le backend tombe ?

### Réponse technique

Le Raspberry garde un cache SQLite des réservations proches et peut valider localement un accès déjà synchronisé.

Références :

- [`raspberry/app/offline_store.py`](raspberry/app/offline_store.py)
- `terminal_offline_cache()` dans [`backend/api/views.py`](backend/api/views.py)
- `terminal_offline_events()` dans [`backend/api/views.py`](backend/api/views.py)

### Tables SQLite

```text
cached_reservations
offline_events
offline_metadata
```

### Ce qui est mis en cache

Le backend exporte :

- id réservation ;
- code référence ;
- station ;
- borne ;
- emplacement ;
- slot ;
- mode d'accès ;
- hash du secret ;
- date début/fin ;
- statut.

Référence :

- `_serialize_offline_cached_reservation()` dans [`backend/api/views.py`](backend/api/views.py)

### Ce qui n'est pas mis en cache

Le clair du QR/code SMS/RFID n'est pas mis en cache.

### Validation locale

Le Raspberry recalcule :

```python
hashlib.sha256(value.encode("utf-8")).hexdigest()
```

et compare avec le hash reçu.

Référence :

- `hash_secret()` dans [`raspberry/app/offline_store.py`](raspberry/app/offline_store.py)

### Rejeu

Si une session est acceptée offline, l'événement est stocké dans `offline_events`, puis rejoué quand le backend revient.

## 31. Placement du broker MQTT

### Question possible

Où doit être Mosquitto ?

### Réponse technique

En développement, Mosquitto est dans Docker sur le PC.

Référence :

- service `mqtt` dans [`docker-compose.yml`](docker-compose.yml)

En production terrain dégradée, le broker doit idéalement être sur le Raspberry.

Pourquoi :

```text
Backend central indisponible
  -> Raspberry continue à parler aux ESP32 via Mosquitto local
  -> les commandes START/STOP locales restent possibles
  -> les événements peuvent être resynchronisés ensuite
```

Configuration :

```text
Raspberry : MQTT_HOST=localhost
ESP32     : MQTT_HOST=<IP du Raspberry>
Backend   : selon architecture, broker local ou broker central
```

## 32. Firmware et conformité OTA

### Question possible

Comment savez-vous qu'un ESP32 est à jour ?

### Réponse technique

L'ESP32 remonte sa version firmware dans les messages `status`, `ack` ou `telemetry`. Le backend la compare à la version attendue.

Références :

- `device_identity()` dans [`esp32/emplacement1/main.py`](esp32/emplacement1/main.py)
- [`backend/api/services/firmware.py`](backend/api/services/firmware.py)
- `_check_firmware_alert()` dans [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)

### Mécanisme

Le backend détermine la version attendue :

```python
device.expected_firmware_version
ou settings.EXPECTED_ESP32_FIRMWARE_VERSION
```

Puis compare :

```python
current != expected
```

Si différent, le statut devient :

```text
update_required
```

et une alerte `firmware_outdated` peut être créée.

### OTA

Un admin peut planifier :

- version cible ;
- URL de mise à jour ;
- statut `update_scheduled`.

Référence :

- `schedule_ota_update()` dans [`backend/api/services/firmware.py`](backend/api/services/firmware.py)
- `admin_device_schedule_ota()` dans [`backend/api/views.py`](backend/api/views.py)

## 33. Anonymisation et privacy by design

### Question possible

Comment protégez-vous les données personnelles ?

### Réponse technique

Le projet applique plusieurs niveaux :

- secrets hashés ;
- refresh token HttpOnly ;
- consentements historisés ;
- export utilisateur ;
- masquage téléphone ;
- suppression de compte par anonymisation applicative ;
- rétention automatisée des données techniques ;
- anonymisation PostgreSQL optionnelle.

### Suppression de compte

La suppression utilisateur ne fait plus un `user.delete()` direct. Elle appelle :

```python
anonymize_user_account(user, reason="account_self_delete")
```

Références :

- `profile()` dans [`backend/api/views.py`](backend/api/views.py)
- `anonymize_user_account()` dans [`backend/api/services/retention.py`](backend/api/services/retention.py)

Effets :

- le compte passe à `archive` et `is_active=False` ;
- le mot de passe devient inutilisable ;
- l'email est remplacé par `user-<uuid>@anonymized.invalid` ;
- le nom et le téléphone du profil sont vidés ;
- les moyens RFID, QR et SMS sont désactivés ;
- les IP des journaux liés au compte sont remplacées par `0.0.0.0` ;
- les réservations et sessions restent disponibles pour la traçabilité technique.

Phrase de soutenance :

> Je ne supprime pas brutalement les lignes liées aux sessions, parce qu'elles servent à la traçabilité opérationnelle. En revanche, je retire l'identité exploitable : email, téléphone, nom, mot de passe, secrets d'accès et IP liée au compte.

### Rétention automatisée

La tâche Celery `api.apply_privacy_retention` applique les durées configurées :

| Donnée | Durée par défaut |
|---|---:|
| Mesures brutes capteurs | 90 jours |
| Télémétrie de session | 365 jours |
| Commandes et ACK ESP32 | 365 jours |
| Journaux de sécurité | 365 jours |
| Alertes résolues | 365 jours |
| Secrets inactifs ou expirés | 90 jours |
| Comptes archivés non anonymisés | 1095 jours |

Commande manuelle :

```bash
python manage.py apply_privacy_retention
```

### Vues anonymisées et Anonymizer

Migration :

- [`backend/api/migrations/0027_optional_postgresql_anonymizer.py`](backend/api/migrations/0027_optional_postgresql_anonymizer.py)
- [`backend/api/migrations/0033_timescale_timeseries_and_anonymized_views.py`](backend/api/migrations/0033_timescale_timeseries_and_anonymized_views.py)

La production actuelle protège déjà les exports SQL avec des vues anonymisées :

- `utilisateur_anonyme`
- `technicien_anonyme`
- `journal_securite_anonyme`
- `supervision_session_anonyme`

Ces vues ne renvoient pas les emails, noms, téléphones ou IP réelles. Elles
renvoient des constantes ou des hashes, ce qui permet de produire des rapports
ou de vérifier les données sans exposer les identités.

PostgreSQL Anonymizer (`anon`) est une couche supplémentaire. Elle sert surtout
au masquage dynamique côté PostgreSQL, par exemple lorsqu’on veut donner un rôle
SQL restreint à un utilisateur ou générer un dump anonymisé directement depuis la
base.

Le code vérifie si l'extension `anon` est disponible :

```sql
SELECT EXISTS (
  SELECT 1
  FROM pg_available_extensions
  WHERE name = 'anon'
);
```

Si oui :

```sql
CREATE EXTENSION IF NOT EXISTS anon CASCADE;
```

Puis applique des `SECURITY LABEL` sur :

- `utilisateur.pseudo`
- `utilisateur.email`
- `profil_utilisateur.nom`
- `profil_utilisateur.telephone`
- `journal_securite.ip`
- `technicien.nom`
- `technicien.email`
- `technicien.telephone`

### État production

Sur le serveur de production actuel, la base tourne avec l’image
`timescale/timescaledb`, qui fournit PostgreSQL avec TimescaleDB mais pas
l’extension système `anon`. Concrètement, `anon` n’apparaît pas dans
`pg_available_extensions` et le fichier `anon.control` n’est pas présent dans le
conteneur.

Ce n’est pas bloquant pour le projet, car l’anonymisation applicative et les vues
SQL anonymisées sont déjà actives. Installer `anon` proprement nécessiterait une
image PostgreSQL personnalisée qui combine à la fois TimescaleDB et PostgreSQL
Anonymizer. Il ne faut pas installer l’extension à la main dans un conteneur en
cours, car ce serait perdu au prochain redéploiement.

Phrase orale possible :

> J’ai distingué deux niveaux. Le niveau déjà actif repose sur l’anonymisation
> applicative et des vues SQL anonymisées. Le niveau PostgreSQL Anonymizer est
> préparé par migration, mais il dépend de l’image serveur. Comme ma production
> utilise une image TimescaleDB pour les séries temporelles, je n’active `anon`
> que si l’image fournit réellement l’extension, sinon la migration passe sans
> casser le déploiement.

## 34. CORS, hosts et IP Wi-Fi

### Question possible

Pourquoi l'application marche avec localhost et l'IP Wi-Fi en développement ?

### Réponse technique

En développement, le projet peut accepter automatiquement les IP privées locales grâce à un middleware spécifique.

Référence :

- [`backend/api/middleware.py`](backend/api/middleware.py)

Activation :

```python
if DEBUG and DEV_AUTO_TRUST_PRIVATE_NETWORK:
    MIDDLEWARE.insert(2, "api.middleware.DevelopmentPrivateNetworkHostMiddleware")
```

Référence :

- [`backend/config/settings.py`](backend/config/settings.py)

Le middleware accepte notamment :

- `localhost`
- `127.0.0.1`
- `10.x.x.x`
- `172.16.x.x` à `172.31.x.x`
- `192.168.x.x`
- `169.254.x.x`
- `.local`

CORS est aussi configuré avec des regex de réseau privé en développement :

- `CORS_ALLOWED_ORIGIN_REGEXES` dans [`backend/config/settings.py`](backend/config/settings.py)

### Limite

Ce mode est uniquement fait pour le développement local. En production, `ALLOWED_HOSTS` doit être explicite.

## 35. Nginx et sécurité HTTP

### Question possible

Quelles protections HTTP sont mises en place ?

### Réponse technique

Nginx sert de reverse proxy unique.

Références :

- [`nginx/conf.d/station.conf`](nginx/conf.d/station.conf)
- [`nginx/prod.conf.d/station.conf`](nginx/prod.conf.d/station.conf)

### Mécanismes

Nginx :

- redirige HTTP vers HTTPS ;
- sert `/api/` vers Django ;
- sert `/grafana/` vers Grafana ;
- sert `/kiosk/` seulement en simulation locale ; en production réelle, le
  kiosque tourne sur le Raspberry physique ;
- route `/ws/` pour les WebSockets ;
- ajoute des headers de sécurité.

Headers :

```text
X-Frame-Options
X-Content-Type-Options
Referrer-Policy
Content-Security-Policy
Strict-Transport-Security
```

Django complète avec :

```text
SECURE_SSL_REDIRECT
SESSION_COOKIE_SECURE
CSRF_COOKIE_SECURE
SECURE_HSTS_SECONDS
SECURE_PROXY_SSL_HEADER
```

Référence :

- [`backend/config/settings.py`](backend/config/settings.py)

### TLS et CA locale

Pour la mise en production académique, le projet utilise une autorité de
certification locale Smallstep nommée `Metropole Verte`.

Concrètement :

- `step-ca` tourne sur le serveur Debian ;
- le certificat HTTPS Nginx est signé par cette CA ;
- le certificat contient les SAN `192.168.10.10`, `127.0.0.1`, `localhost` et
  `SRV-Station` ;
- la racine CA doit être installée sur les postes qui ouvrent l'application ;
- Nginx termine TLS, puis relaie vers les services internes Docker.

Pourquoi ne pas garder un certificat autosigné simple ?

Un certificat autosigné chiffre bien le trafic, mais il ne donne pas une chaîne
de confiance propre à plusieurs machines. Avec Smallstep, on obtient un modèle
plus industriel : une racine de confiance, des certificats serveurs signés, des
SAN contrôlés, et une procédure de renouvellement.

Pourquoi HSTS ?

HSTS force le navigateur à revenir en HTTPS après une première connexion
sécurisée. Dans le projet, l'en-tête est :

```text
Strict-Transport-Security: max-age=31536000
```

Les options `includeSubDomains` et `preload` restent désactivées parce que
l'application tourne sur une IP LAN avec une CA privée. Les activer serait
pertinent uniquement avec un domaine public stable et tous ses sous-domaines
servis en HTTPS.

À expliquer simplement :

> TLS chiffre la communication. Le certificat prouve que je parle au bon
> serveur. HSTS empêche le navigateur de revenir en HTTP. Smallstep me permet de
> gérer cette confiance en local sans acheter de certificat public pour un
> prototype LAN.

## 36. Docker et production-ready

### Question possible

Qu'est-ce qui différencie la production du développement ?

### Réponse technique

Le projet a deux fichiers Compose :

- [`docker-compose.yml`](docker-compose.yml) pour le développement ;
- [`docker-compose.prod.yml`](docker-compose.prod.yml) pour la production.

### Production

La stack production :

- limite l'exposition des ports ;
- utilise `restart: unless-stopped` ;
- borne les logs Docker ;
- utilise des images pinnées par digest pour certains services ;
- exécute le backend et le Raspberry en utilisateur non-root ;
- expose les services internes via Nginx ;
- ajoute des healthchecks.

### Backend Dockerfile

Référence :

- [`backend/Dockerfile`](backend/Dockerfile)

Le Dockerfile :

- installe les dépendances ;
- lance Ruff ;
- lance pytest dans la cible `test` ;
- crée un utilisateur système `station` ;
- utilise cet utilisateur dans la cible runtime.

### Frontend Dockerfile

Référence :

- [`frontend/Dockerfile`](frontend/Dockerfile)

Le frontend est buildé avec Node puis servi statiquement par Nginx.

## 37. Tests et preuve de fonctionnement

### Question possible

Comment prouvez-vous que le scénario complet fonctionne ?

### Réponse technique

Le test principal est :

- [`backend/api/tests/test_end_to_end_charge_flow.py`](backend/api/tests/test_end_to_end_charge_flow.py)

Il couvre :

```text
réservation QR
session mobile
autorisation téléphone
consommation kiosk
création session
ACK START
télémétrie seulement sur l'emplacement réservé
ACK STOP
clôture session
DeviceCommandLog
SessionTelemetry
CapteurData
```

Autres tests importants :

- terminal : [`backend/api/tests/test_terminal_auth.py`](backend/api/tests/test_terminal_auth.py)
- MQTT : [`backend/api/tests/test_mqtt_ingestion.py`](backend/api/tests/test_mqtt_ingestion.py)
- SMS : [`backend/api/tests/test_sms_access_policy.py`](backend/api/tests/test_sms_access_policy.py)
- alertes : [`backend/api/tests/test_operational_alerts.py`](backend/api/tests/test_operational_alerts.py)
- sécurité prod : [`backend/api/tests/test_production_hardening.py`](backend/api/tests/test_production_hardening.py)
- contrat Raspberry MQTT : [`raspberry/tests/test_mqtt_contract.py`](raspberry/tests/test_mqtt_contract.py)

## 38. Résumé technique global

### Phrase de synthèse

Le projet est une architecture Django/PWA/Raspberry/ESP32 où :

```text
Django
  -> décide les droits métier
  -> stocke réservations, sessions, secrets hashés, alertes et télémétrie

Raspberry
  -> exécute localement l'interface tactile
  -> lit le RFID
  -> appelle le backend avec un secret terminal
  -> commande les ESP32 via MQTT
  -> conserve un cache SQLite pour le mode dégradé

ESP32
  -> reçoit START/STOP
  -> publie ACK/status/telemetry/alert
  -> lit DHT22 et SEN0214
  -> calcule puissance et énergie

Redis/Celery
  -> absorbe les traitements asynchrones

PostgreSQL/TimescaleDB
  -> conserve la source de vérité

Grafana/Channels
  -> visualisent et diffusent la supervision
```
