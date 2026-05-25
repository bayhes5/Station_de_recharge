# Notice technique d'implémentation

Cette notice répond à la question : **comment le projet fonctionne concrètement dans le code ?**

Pour une version encore plus détaillée, pensée comme support de réponse aux
questions de jury, voir aussi :
[`NOTICE_SOUTENANCE_TECHNIQUE_DETAILLEE.md`](NOTICE_SOUTENANCE_TECHNIQUE_DETAILLEE.md).

L'objectif est de pouvoir expliquer en soutenance :

- où se trouve le mécanisme ;
- quelle librairie ou API est utilisée ;
- quelle donnée est stockée ;
- ce qui est volontairement évité pour des raisons de sécurité ou de robustesse.

## 1. Comment les mots de passe sont-ils gérés ?

### Réponse courte

Les mots de passe utilisateur sont gérés par Django. Ils ne sont jamais stockés en clair. Le projet utilise `set_password()` pour hasher le mot de passe et `check_password()` pour vérifier une connexion.

### Comment dans le code ?

À la création d'un utilisateur, le manager appelle :

```python
user.set_password(password)
```

Référence :

- `UtilisateurManager.create_user()` dans [`backend/api/models.py`](backend/api/models.py)

À la connexion, le backend personnalisé récupère l'utilisateur par pseudo ou email, puis vérifie :

```python
user.check_password(password)
```

Référence :

- `UtilisateurBackend.authenticate()` dans [`backend/api/auth_backends.py`](backend/api/auth_backends.py)

Les règles de complexité sont appliquées à deux niveaux :

- validateurs Django configurés dans `AUTH_PASSWORD_VALIDATORS` ;
- contrôles métier supplémentaires dans `RegisterSerializer.validate_password()`.

Références :

- `AUTH_PASSWORD_VALIDATORS` dans [`backend/config/settings.py`](backend/config/settings.py)
- `RegisterSerializer.validate_password()` dans [`backend/api/serializers.py`](backend/api/serializers.py)

### Avec quoi ?

Django utilise son système de hash de mot de passe. Dans ce projet, aucun `PASSWORD_HASHERS` spécifique n'est défini en production, donc Django utilise ses hashers par défaut, notamment PBKDF2 avec SHA-256.

Concrètement, cela signifie que le projet ne calcule pas lui-même un simple :

```python
hashlib.sha256(password.encode()).hexdigest()
```

Ce serait insuffisant pour un mot de passe, car un SHA-256 brut :

- n'ajoute pas automatiquement de sel ;
- est trop rapide face à une attaque par dictionnaire ;
- ne stocke pas clairement l'algorithme utilisé ;
- rend les migrations d'algorithme plus difficiles.

Django stocke le mot de passe sous une forme encodée qui ressemble à :

```text
pbkdf2_sha256$1200000$salt_aleatoire$hash_final
```

Les parties sont :

```text
pbkdf2_sha256
  -> nom de l'algorithme utilisé

1200000
  -> nombre d'itérations PBKDF2

salt_aleatoire
  -> sel unique généré pour ce mot de passe

hash_final
  -> résultat dérivé du mot de passe + sel + itérations
```

Le sel sert à éviter que deux utilisateurs ayant le même mot de passe aient la même valeur stockée en base. Il protège aussi contre l'utilisation directe de tables précalculées.

Le nombre d'itérations rend le calcul volontairement coûteux. Un attaquant qui essaie des millions de mots de passe doit payer ce coût à chaque tentative.

Dans le projet, la base ne stocke donc pas :

```text
motdepasse123
```

ni :

```text
sha256(motdepasse123)
```

mais une chaîne Django complète :

```text
algorithme$iterations$sel$hash
```

Cette chaîne est stockée dans le champ `password` hérité de `AbstractBaseUser`.

Référence :

- `Utilisateur(AbstractBaseUser, PermissionsMixin)` dans [`backend/api/models.py`](backend/api/models.py)

Lors d'une connexion, `check_password()` :

1. lit la chaîne stockée en base ;
2. extrait l'algorithme, le nombre d'itérations, le sel et le hash ;
3. recalcule le hash avec le mot de passe fourni ;
4. compare le résultat avec la valeur stockée ;
5. renvoie `True` ou `False`.

Le projet n'a donc pas besoin de connaître le sel ni de gérer manuellement l'encodage. Django les intègre dans la chaîne stockée.

Point important à dire :

```text
On n'utilise pas hashlib directement pour les mots de passe utilisateur.
On laisse Django gérer le sel, l'algorithme, l'encodage et la vérification.
```

`hashlib.sha256` est utilisé ailleurs dans le projet, mais pour les secrets temporaires RFID/QR/SMS, pas pour les mots de passe de compte.

Phrase de soutenance possible :

```text
Pour les mots de passe, je n'ai pas implémenté un hash manuel. J'utilise le mécanisme natif de Django via set_password() et check_password(). Django stocke une chaîne auto-descriptive contenant l'algorithme, les itérations PBKDF2, le sel unique et le hash final. Cela évite les hashes SHA-256 bruts et permet de bénéficier des bonnes pratiques du framework.
```

## 2. Comment les tokens JWT sont-ils gérés ?

### Réponse courte

Le backend utilise `djangorestframework-simplejwt`. Le token d'accès est renvoyé au frontend et gardé en mémoire JavaScript. Le refresh token est stocké dans un cookie HttpOnly.

### Comment dans le code ?

La configuration JWT est dans :

- `SIMPLE_JWT` dans [`backend/config/settings.py`](backend/config/settings.py)

Paramètres principaux :

```python
ACCESS_TOKEN_LIFETIME = 60 minutes par défaut
REFRESH_TOKEN_LIFETIME = 7 jours par défaut
AUTH_HEADER_TYPES = ("Bearer",)
USER_ID_FIELD = "id_user"
USER_ID_CLAIM = "user_id"
```

La connexion crée les tokens avec :

```python
refresh = RefreshToken.for_user(user)
access = refresh.access_token
```

Référence :

- `login()` dans [`backend/api/views.py`](backend/api/views.py)

Le refresh token est placé dans un cookie avec :

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

Références :

- `_set_refresh_cookie()` dans [`backend/api/views.py`](backend/api/views.py)
- `_refresh_cookie_kwargs()` dans [`backend/api/views.py`](backend/api/views.py)

Le renouvellement se fait par :

```text
POST /api/token/refresh/
```

La vue récupère le refresh token :

- soit depuis le body ;
- soit depuis le cookie HttpOnly.

Référence :

- `refresh_token()` dans [`backend/api/views.py`](backend/api/views.py)

Côté frontend, les appels passent par :

- [`frontend/js/api.js`](frontend/js/api.js)

Le frontend :

- met l'access token en mémoire ;
- envoie les requêtes avec `Authorization: Bearer <access>`;
- utilise `credentials: "include"` pour inclure le cookie refresh ;
- tente un refresh automatique si une requête authentifiée renvoie `401`.

### Pourquoi ce choix ?

Le refresh token est le token le plus sensible. En le mettant en cookie HttpOnly, on évite qu'il soit lisible directement par JavaScript en cas de XSS.

## 3. Comment les comptes sont-ils authentifiés ?

### Réponse courte

L'utilisateur peut se connecter avec son pseudo ou son email. Le backend personnalisé cherche les deux champs puis délègue la vérification du mot de passe à Django.

### Comment dans le code ?

Backend d'authentification :

- [`backend/api/auth_backends.py`](backend/api/auth_backends.py)

Configuration :

- `AUTHENTICATION_BACKENDS` dans [`backend/config/settings.py`](backend/config/settings.py)

La recherche se fait avec :

```python
Q(pseudo__iexact=lookup) | Q(email__iexact=lookup)
```

Puis :

```python
user.check_password(password)
```

L'utilisateur est refusé si :

- identifiant absent ;
- mot de passe absent ;
- aucun compte correspondant ;
- mot de passe invalide ;
- compte désactivé selon `user_can_authenticate()`.

## 4. Comment les rôles et permissions sont-ils gérés ?

### Réponse courte

Le projet utilise les permissions Django/DRF pour les accès API, et des modèles métier pour distinguer utilisateurs, administrateurs et techniciens.

### Comment dans le code ?

Les endpoints utilisateur exigent souvent :

```python
@permission_classes([IsAuthenticated])
```

Les endpoints d'administration utilisent :

```python
@permission_classes([IsStaffUser])
```

Références :

- Permission staff : [`backend/api/permissions.py`](backend/api/permissions.py)
- Routes API : [`backend/api/api_urls.py`](backend/api/api_urls.py)
- Vues API : [`backend/api/views.py`](backend/api/views.py)

Le périmètre technicien est géré par :

- `Technicien`
- `TechnicienStation`

Références :

- Modèles : [`backend/api/models.py`](backend/api/models.py)
- Serializer `TechnicianSerializer` : [`backend/api/serializers.py`](backend/api/serializers.py)
- WebSocket technicien : `TechnicianSupervisionConsumer` dans [`backend/api/consumers.py`](backend/api/consumers.py)

Un technicien ne doit pas recevoir toute la supervision globale : il est filtré par les stations qui lui sont affectées.

## 5. Comment le rate limiting est-il fait ?

### Réponse courte

Le projet utilise les throttles DRF avec des classes dédiées par usage sensible : connexion, inscription, SMS, terminal, session mobile.

### Comment dans le code ?

Classes :

- [`backend/api/throttles.py`](backend/api/throttles.py)

Elles héritent de :

```python
rest_framework.throttling.SimpleRateThrottle
```

Le cache key est construit par :

- utilisateur authentifié si disponible ;
- IP client sinon.

Configuration des seuils :

- `DEFAULT_THROTTLE_RATES` dans [`backend/config/settings.py`](backend/config/settings.py)
- `.env.example`

Exemples de valeurs :

```text
login: 10/minute
register: 5/hour
token_refresh: 30/minute
sms: 3/minute
terminal: 120/minute
mobile_session: 60/minute
```

Utilisation :

```python
@throttle_classes([LoginRateThrottle])
@throttle_classes([SmsRateThrottle])
@throttle_classes([TerminalRateThrottle])
```

Référence :

- [`backend/api/views.py`](backend/api/views.py)

## 6. Comment les secrets RFID, QR et SMS sont-ils stockés ?

### Réponse courte

Les secrets d'accès ne sont pas stockés en clair. Le projet stocke un hash SHA-256 dans `Authentification.hash_valeur`.

### Comment dans le code ?

Fonction commune :

```python
hashlib.sha256(secret.encode("utf-8")).hexdigest()
```

Référence :

- `hash_secret()` dans [`backend/api/services/auth_methods.py`](backend/api/services/auth_methods.py)

Le modèle concerné est :

- `Authentification` dans [`backend/api/models.py`](backend/api/models.py)

Champ important :

```python
hash_valeur = models.TextField(db_column="secret_hash")
```

Point important :

```text
hashlib.sha256 est utilisé pour les secrets temporaires et RFID.
Les mots de passe utilisateur, eux, restent gérés par Django avec set_password().
```

## 7. Comment le QR de réservation est-il généré ?

### Réponse courte

Le backend génère un secret temporaire dérivé par HMAC-SHA256, construit un payload JSON, puis produit un SVG QR avec la librairie `qrcode`.

### Comment dans le code ?

Le nonce est généré avec :

```python
secrets.token_urlsafe(18)
```

Référence :

- `_generate_access_nonce()` dans [`backend/api/views.py`](backend/api/views.py)

Le secret temporaire est dérivé avec :

```python
hmac.new(settings.SECRET_KEY.encode("utf-8"), material, hashlib.sha256).digest()
```

Référence :

- `_derive_temporary_access_secret()` dans [`backend/api/views.py`](backend/api/views.py)

Le matériau signé contient :

```text
id_auth | reservation_code | auth_mode | nonce
```

Pour le QR, le digest HMAC est converti en token base64 URL-safe :

```python
base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")[:24]
```

Puis le payload QR est :

```json
{
  "v": 1,
  "type": "reservation_access",
  "reservation": "CODE",
  "token": "QR-..."
}
```

Références :

- `_build_qr_payload()` dans [`backend/api/views.py`](backend/api/views.py)
- `_build_qr_svg()` dans [`backend/api/views.py`](backend/api/views.py)

La génération SVG utilise :

```python
import qrcode
from qrcode.image.svg import SvgPathImage
```

Le QR clair est affichable/envoyable, mais en base on stocke seulement :

```python
hash_secret(clear_value)
```

## 8. Comment le code SMS est-il généré ?

### Réponse courte

Le code SMS est dérivé du même HMAC que le QR, mais converti dans un alphabet compatible clavier matriciel.

### Comment dans le code ?

Alphabet :

```text
0123456789ABCD
```

Longueur par défaut :

```text
8 caractères
```

Fonction de conversion :

- `_digest_to_keypad_code()` dans [`backend/api/views.py`](backend/api/views.py)

Politique :

- [`backend/api/services/sms_access_policy.py`](backend/api/services/sms_access_policy.py)

La fonction convertit les octets du digest vers l'alphabet autorisé, avec rejet des octets qui biaiseraient la distribution.

Justification :

```text
14 caractères possibles ^ 8 positions = 14^8 combinaisons.
Le code reste compatible avec un clavier 4x4 limité à 0-9 et A-D.
Le nombre d'essais est limité à 5.
```

Le nombre d'échecs est stocké dans `Authentification.metadata` :

- `sms_failed_attempts`
- `sms_last_failed_at`
- `sms_locked_at`
- `sms_locked_reason`

Références :

- `_record_sms_access_failure()` dans [`backend/api/views.py`](backend/api/views.py)
- `_sms_access_is_locked()` dans [`backend/api/views.py`](backend/api/views.py)
- Tests : [`backend/api/tests/test_sms_access_policy.py`](backend/api/tests/test_sms_access_policy.py)

## 9. Comment l'envoi SMS est-il fait ?

### Réponse courte

Le projet a un service SMS abstrait. En développement, le backend `console` journalise l'envoi. Pour la production, des adaptateurs Twilio et Brevo existent.

### Comment dans le code ?

Service :

- [`backend/api/services/sms.py`](backend/api/services/sms.py)

Fonction principale :

```python
send_sms(phone_number, message)
```

Backends supportés :

- `console`
- `twilio`
- `brevo`
- `disabled`
- `ovh` volontairement refusé dans le profil durci actuel

Twilio et Brevo utilisent `urllib.request.Request` et `urlopen`.

Références :

- `_send_twilio_sms()` dans [`backend/api/services/sms.py`](backend/api/services/sms.py)
- `_send_brevo_sms()` dans [`backend/api/services/sms.py`](backend/api/services/sms.py)

Le numéro affiché est masqué avec :

```python
******1234
```

Référence :

- `mask_phone_number()` dans [`backend/api/services/sms.py`](backend/api/services/sms.py)

L'envoi est refusé si :

- aucun téléphone n'est renseigné ;
- le téléphone doit être vérifié et ne l'est pas ;
- le cooldown de renvoi n'est pas terminé ;
- le provider SMS échoue.

Référence :

- `_send_reservation_sms_code()` dans [`backend/api/views.py`](backend/api/views.py)

## 10. Comment l'association RFID fonctionne-t-elle ?

### Réponse courte

L'utilisateur génère un code court depuis son profil. La borne lit l'UID RFID avec le lecteur ACR122U, puis appelle le backend avec le code et l'UID. Le backend hash l'UID et l'associe au compte.

### Comment dans le code ?

Le code d'association est généré avec :

```python
secrets.choice(KEYPAD_CODE_ALPHABET)
```

Il est stocké temporairement dans le cache :

```python
cache.set("rfid-link:<code>", payload, timeout=600)
```

Références :

- `_generate_rfid_link_code()` dans [`backend/api/views.py`](backend/api/views.py)
- `create_rfid_link_code()` dans [`backend/api/views.py`](backend/api/views.py)

Côté Raspberry, l'UID est normalisé :

```python
"".join(char for char in value.upper() if char.isalnum())
```

Référence :

- `normalize_uid()` dans [`raspberry/app/rfid_reader.py`](raspberry/app/rfid_reader.py)

Le lecteur ACR122U est lu via PC/SC avec l'APDU :

```text
FF CA 00 00 00
```

Référence :

- `_pcsc_loop()` dans [`raspberry/app/rfid_reader.py`](raspberry/app/rfid_reader.py)

Le backend associe le badge via :

- `terminal_link_rfid()` dans [`backend/api/views.py`](backend/api/views.py)
- `ensure_rfid_auth()` dans [`backend/api/services/auth_methods.py`](backend/api/services/auth_methods.py)

L'UID n'est pas stocké en clair comme secret de validation : son hash est stocké dans `Authentification.hash_valeur`.

## 11. Comment le QR de session mobile fonctionne-t-il ?

### Réponse courte

La borne crée une session mobile temporaire dans le cache backend. Le QR affiché par la borne contient seulement une URL avec un token. L'utilisateur scanne, se connecte, choisit une réservation compatible, puis autorise la borne.

### Comment dans le code ?

Token :

```python
secrets.token_urlsafe(MOBILE_SESSION_TOKEN_BYTES)
```

Référence :

- `_generate_mobile_session_token()` dans [`backend/api/views.py`](backend/api/views.py)

Stockage :

```python
cache.set("mobile-session:<token>", payload, timeout=ttl)
```

Références :

- `_store_mobile_session()` dans [`backend/api/views.py`](backend/api/views.py)
- `_get_mobile_session_payload()` dans [`backend/api/views.py`](backend/api/views.py)

Durée :

```python
MOBILE_SESSION_TTL_SECONDS = 10 * 60
```

Référence :

- [`backend/config/settings.py`](backend/config/settings.py)

Endpoints :

```text
POST /api/terminal/mobile-sessions/
GET  /api/mobile-sessions/<token>/
POST /api/mobile-sessions/<token>/authorize/
POST /api/terminal/mobile-sessions/consume/
```

Références :

- `terminal_create_mobile_session()` dans [`backend/api/views.py`](backend/api/views.py)
- `mobile_session_detail()` dans [`backend/api/views.py`](backend/api/views.py)
- `mobile_session_authorize()` dans [`backend/api/views.py`](backend/api/views.py)
- `terminal_consume_mobile_session()` dans [`backend/api/views.py`](backend/api/views.py)
- [`frontend/js/mobile-session.js`](frontend/js/mobile-session.js)
- [`raspberry/app/app.js`](raspberry/app/app.js)

Le backend vérifie que la réservation choisie appartient au compte connecté et correspond à la station/borne de la session mobile.

## 12. Comment le terminal Raspberry est-il authentifié auprès du backend ?

### Réponse courte

Les endpoints terminal sont publics côté authentification utilisateur, mais protégés par un secret partagé `X-Terminal-Secret`.

### Comment dans le code ?

La vérification utilise :

```python
hmac.compare_digest(provided_secret, expected_secret)
```

Référence :

- `_terminal_secret_response()` dans [`backend/api/views.py`](backend/api/views.py)

Le Raspberry ajoute ce header dans :

```python
headers["X-Terminal-Secret"] = TERMINAL_API_SECRET
```

Référence :

- `backend_headers()` dans [`raspberry/app/main.py`](raspberry/app/main.py)

Le secret est configuré par :

```text
TERMINAL_API_SECRET
```

Références :

- [`backend/config/settings.py`](backend/config/settings.py)
- [`.env.example`](.env.example)

## 13. Comment la disponibilité des emplacements est-elle calculée ?

### Réponse courte

Le backend cherche les emplacements d'une station qui n'ont pas de réservation chevauchante sur la fenêtre payée.

### Comment dans le code ?

Fonction :

- `_available_emplacements()` dans [`backend/api/views.py`](backend/api/views.py)

Elle utilise une sous-requête avec :

```python
Exists(overlapping_reservations)
```

Une réservation chevauche si :

```python
date_debut < nouvelle_date_fin
date_fin > nouvelle_date_debut
statut in ["confirmee", "active", "en_attente"]
```

Références :

- `_reservation_overlaps()` dans [`backend/api/views.py`](backend/api/views.py)
- `_available_emplacements()` dans [`backend/api/views.py`](backend/api/views.py)
- Tests de réservation : [`backend/api/tests/test_reservations.py`](backend/api/tests/test_reservations.py)

Les créneaux doivent être alignés selon :

- `RESERVATION_STEP_MINUTES`
- `RESERVATION_DURATION_MINUTES`

Référence :

- [`backend/api/reservation_rules.py`](backend/api/reservation_rules.py)

## 14. Comment une session de charge est-elle ouverte ?

### Réponse courte

Après validation de l'accès, le backend crée ou retrouve une `Session`, passe la réservation à `active`, puis renvoie au Raspberry les informations nécessaires pour commander l'ESP32.

### Comment dans le code ?

Endpoint :

```text
POST /api/terminal/authenticate/
```

Référence :

- `terminal_authenticate()` dans [`backend/api/views.py`](backend/api/views.py)

La session est le modèle :

- `Session` dans [`backend/api/models.py`](backend/api/models.py)

La machine d'état est dans :

- [`backend/api/services/charge_session_state.py`](backend/api/services/charge_session_state.py)

Transition après authentification réussie :

```python
mark_access_validated(session)
```

Le backend refuse les doubles démarrages incohérents avec :

```python
ensure_session_can_be_started(session)
```

Référence :

- [`backend/api/services/charge_session_state.py`](backend/api/services/charge_session_state.py)

## 15. Comment le Raspberry envoie une commande à l'ESP32 ?

### Réponse courte

Le Raspberry publie un message MQTT sur le topic de commande de l'emplacement, avec un `command_id`, une action et le `session_id`.

### Comment dans le code ?

Endpoint local :

```text
POST /mqtt/command
```

Référence :

- `KioskHandler.do_POST()` dans [`raspberry/app/main.py`](raspberry/app/main.py)

Publication MQTT :

- [`raspberry/app/mqtt_client.py`](raspberry/app/mqtt_client.py)

La librairie utilisée est :

```python
paho.mqtt.client
```

Le `command_id` est généré par :

```python
uuid.uuid4()
```

Le topic est construit par :

```python
slot_topic(slot_id, suffix="cmd")
```

Format :

```text
station/<mqtt_prefix>/<slot_id>/cmd
```

Si `MQTT_ACK_REQUIRED=True`, le Raspberry attend un ACK sur :

```text
station/<mqtt_prefix>/<slot_id>/ack
```

Le code utilise :

```python
threading.Event()
```

pour attendre l'ACK pendant `MQTT_ACK_TIMEOUT_SECONDS`.

## 16. Comment l'ESP32 reçoit et exécute START/STOP ?

### Réponse courte

L'ESP32 écoute son topic `/cmd`, parse le JSON reçu, exécute l'action, publie un ACK et publie immédiatement une télémétrie.

### Comment dans le code ?

Firmware :

- [`esp32/emplacement1/main.py`](esp32/emplacement1/main.py)

Librairie MQTT MicroPython :

```python
from umqtt.simple import MQTTClient
```

Callback :

```python
client.set_callback(handle_command)
```

Commandes supportées :

- `START`
- `STOP`
- `LOCK`
- `UNLOCK`

Fonctions :

- `handle_command()`
- `accept_start()`
- `accept_stop()`
- `publish_ack()`
- `publish_status()`
- `publish_telemetry_now()`

Tant que les sorties physiques ne sont pas câblées :

```python
OUTPUTS_ENABLED = False
PHYSICAL_INPUTS_ENABLED = False
```

Le firmware simule donc l'état logique sans activer de relais réel.

## 17. Comment les données électriques sont-elles calculées ?

### Réponse courte

Le courant est lu via le capteur analogique SEN0214. La tension est actuellement fixe à 12 V pour le prototype. La puissance est calculée par `P = U * I`. L'énergie est intégrée dans le temps en kWh.

### Comment dans le code ?

Référence :

- [`esp32/emplacement1/main.py`](esp32/emplacement1/main.py)

Courant :

```python
ADC(Pin(34))
```

Le firmware moyenne plusieurs lectures ADC :

```python
read_average_adc()
```

Puis convertit :

```python
gpio_voltage = (raw / ADC_RESOLUTION) * ADC_VREF
sensor_voltage = gpio_voltage * ADC_CURRENT_INPUT_SCALE
current = (sensor_voltage - zero_voltage) / SEN0214_SENSITIVITY_V_PER_A
```

Le zéro courant est calibré au démarrage :

```python
calibrate_current_zero()
```

Tension prototype :

```python
VOLTAGE_SENSOR_MODE = "fixed"
FIXED_BUS_VOLTAGE = 12.0
```

Puissance :

```python
power = voltage * current
```

Énergie :

```python
energy_kwh += (power_watts * elapsed_seconds) / 3_600_000
```

Référence :

- `update_energy()` dans [`esp32/emplacement1/main.py`](esp32/emplacement1/main.py)

Cette formule vient de :

```text
Wh = W * h
kWh = Wh / 1000
elapsed_hours = elapsed_seconds / 3600
donc kWh = W * elapsed_seconds / 3 600 000
```

## 18. Comment l'ingestion MQTT backend fonctionne-t-elle ?

### Réponse courte

Le service `mqtt-bridge` s'abonne à `station/#`, reçoit les messages, les délègue à Celery, puis le service de télémétrie écrit en base.

### Comment dans le code ?

Bridge :

- [`backend/api/mqtt.py`](backend/api/mqtt.py)

Commande :

- [`backend/api/management/commands/run_mqtt_bridge.py`](backend/api/management/commands/run_mqtt_bridge.py)

Librairie :

```python
paho.mqtt.client
```

Abonnement :

```python
station/#
```

À chaque message :

```python
process_mqtt_message_task.delay(topic, payload_text)
```

Référence :

- `_handle_message()` dans [`backend/api/mqtt.py`](backend/api/mqtt.py)

Le worker Celery exécute :

```python
process_mqtt_message(topic, payload)
```

Référence :

- [`backend/api/tasks.py`](backend/api/tasks.py)

Types reconnus :

```text
ack
status
telemetry
alert
```

Routage :

```text
ack       -> ingest_slot_ack()
status    -> ingest_slot_status()
telemetry -> ingest_slot_telemetry()
alert     -> ingest_slot_telemetry() avec state=error
```

Référence :

- [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)

## 19. Comment le backend retrouve le bon emplacement depuis MQTT ?

### Réponse courte

Le backend utilise le `topic_prefix` MQTT pour retrouver la borne, puis le `slot_id` pour retrouver l'emplacement et le device.

### Comment dans le code ?

Extraction du préfixe :

- `_extract_topic_prefix()` dans [`backend/api/tasks.py`](backend/api/tasks.py)

Recherche de la borne :

- `_borne_from_topic_prefix()` dans [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)

Recherche ou création du device :

- `_get_device()` dans [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)
- `_device_for_emplacement()` dans [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)

Le champ clé côté borne est :

```python
Borne.mqtt_prefix
```

Référence :

- Modèle `Borne` dans [`backend/api/models.py`](backend/api/models.py)

Exemple :

```text
station/station-demo/borne-1/slot1/telemetry
```

Ici :

- base topic : `station`
- préfixe borne : `station-demo/borne-1`
- slot : `slot1`
- message : `telemetry`

## 20. Comment les mesures sont-elles écrites en base ?

### Réponse courte

Chaque champ reçu est converti en capteur typé puis stocké dans `CapteurData`. Si une session active existe et que courant+tension sont présents, une ligne `SessionTelemetry` est aussi créée.

### Comment dans le code ?

Mapping des champs :

- `SENSOR_FIELDS` dans [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)

Exemples :

```text
temperature -> Capteur type temperature, unité C
humidity    -> Capteur type humidity, unité %
current     -> Capteur type current, unité A
voltage     -> Capteur type voltage, unité V
power       -> Capteur type power, unité W
energy_kwh  -> Capteur type energy_kwh, unité kWh
```

Stockage capteur :

- `_store_sensor()` dans [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)

La fonction fait :

```python
Capteur.objects.get_or_create(device=device, type=sensor_type)
CapteurData.objects.create(...)
```

Stockage session :

```python
SessionTelemetry.objects.create(
    session=session,
    courant=current,
    tension=voltage,
    energie_kwh=energy or 0.0,
    timestamp=timestamp,
)
```

Référence :

- `ingest_slot_telemetry()` dans [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)

Une `SessionTelemetry` n'est créée que si :

- une session active existe ;
- le courant est présent ;
- la tension est présente.

## 21. Comment les ACK START/STOP sont-ils tracés ?

### Réponse courte

Chaque ACK ESP32 est écrit dans `DeviceCommandLog`, met à jour le device et peut faire évoluer l'état de session.

### Comment dans le code ?

Référence :

- `ingest_slot_ack()` dans [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)

Le backend extrait :

- `command_id`
- `action`
- `status`
- `message`
- `source`
- `session_id`

Puis il écrit :

```python
DeviceCommandLog.objects.create(...)
```

Modèle :

- `DeviceCommandLog` dans [`backend/api/models.py`](backend/api/models.py)

La session évolue avec :

```python
mark_state_from_ack(session, action=action, ack_status=ack_status)
```

Référence :

- [`backend/api/services/charge_session_state.py`](backend/api/services/charge_session_state.py)

## 22. Comment les alertes sont-elles créées et levées ?

### Réponse courte

Les alertes sont créées depuis la télémétrie ou depuis des tâches périodiques. Si l'anomalie persiste, l'alerte est mise à jour. Si la télémétrie redevient normale, certaines alertes sont résolues automatiquement.

### Comment dans le code ?

Création depuis télémétrie :

- `_create_alert_if_needed()` dans [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)

Création ou mise à jour sans doublon :

- `_upsert_active_alert()` dans [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)

Résolution automatique :

- `_resolve_alerts_for_device()` dans [`backend/api/services/telemetry.py`](backend/api/services/telemetry.py)

Seuils actuels :

```text
temperature >= 60 °C -> overheat critique
current >= 3.0 A    -> overcurrent haute
energy_kwh >= SESSION_ENERGY_ALERT_KWH -> energy_over_limit
session active sans télémétrie récente -> session_without_telemetry
```

Paramètres :

- `SESSION_TELEMETRY_STALE_MINUTES`
- `ENERGY_ACTIVITY_MIN_KWH`
- `SESSION_ENERGY_ALERT_KWH`
- `ALERT_NOTIFICATION_MIN_AGE_SECONDS`
- `ALERT_CRITICAL_NOTIFICATION_MIN_AGE_SECONDS`
- `ALERT_RENOTIFY_COOLDOWN_SECONDS`

Références :

- [`backend/config/settings.py`](backend/config/settings.py)
- [`.env.example`](.env.example)

Le scan des sessions sans télémétrie est exécuté par Celery Beat :

- `scan_session_telemetry_gaps()` dans [`backend/api/services/operational_alerts.py`](backend/api/services/operational_alerts.py)
- tâche `api.scan_session_telemetry_gaps` dans [`backend/api/tasks.py`](backend/api/tasks.py)

## 23. Comment les notifications technicien sont-elles envoyées ?

### Réponse courte

Le backend notifie les techniciens affectés à la station concernée, après un délai de persistance de l'alerte.

### Comment dans le code ?

Service :

- [`backend/api/services/email_notifications.py`](backend/api/services/email_notifications.py)

Fonction :

```python
notify_technicians_for_alert(alert_id)
```

Le service cherche les destinataires avec :

```python
TechnicienStation.objects.filter(station=station, is_active=True)
```

Puis envoie avec :

```python
django.core.mail.send_mail()
```

Les alertes notifiables sont filtrées par :

- type ;
- statut ;
- sévérité ;
- délai de persistance ;
- cooldown de renotification.

Références :

- `alert_is_ready_for_notification()` dans [`backend/api/services/email_notifications.py`](backend/api/services/email_notifications.py)
- `notify_pending_alerts()` dans [`backend/api/services/email_notifications.py`](backend/api/services/email_notifications.py)

La tâche périodique est :

- `api.notify_pending_alerts` dans [`backend/api/tasks.py`](backend/api/tasks.py)

## 24. Comment Grafana récupère les données ?

### Réponse courte

Grafana ne lit pas MQTT. Grafana interroge PostgreSQL/TimescaleDB avec des requêtes SQL.

### Comment dans le code ?

Datasource :

- [`grafana/provisioning/datasources/datasource.yml`](grafana/provisioning/datasources/datasource.yml)

Dashboards :

- [`grafana/dashboards/station-overview.json`](grafana/dashboards/station-overview.json)
- [`grafana/dashboards/station-supervision.json`](grafana/dashboards/station-supervision.json)

Tables lues :

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

Flux exact :

```text
ESP32 -> MQTT -> backend -> PostgreSQL/TimescaleDB -> Grafana
```

Pas :

```text
ESP32 -> Grafana
```

## 25. Comment Redis est-il utilisé ?

### Réponse courte

Redis sert de cache, de broker Celery et de couche WebSocket Channels.

### Comment dans le code ?

Configuration cache :

- `CACHES` dans [`backend/config/settings.py`](backend/config/settings.py)

Configuration Celery :

- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`

Référence :

- [`backend/config/settings.py`](backend/config/settings.py)
- [`backend/config/celery.py`](backend/config/celery.py)

Configuration Channels :

- `CHANNEL_LAYERS` dans [`backend/config/settings.py`](backend/config/settings.py)

Usages concrets :

- cache des sessions mobiles ;
- cache des codes RFID d'association ;
- cache catalogue stations ;
- queue Celery pour ingestion MQTT ;
- diffusion WebSocket admin/technicien.

## 26. Comment le mode dégradé fonctionne techniquement ?

### Réponse courte

Le Raspberry synchronise une copie limitée des réservations proches dans SQLite. Si le backend tombe, il vérifie localement les secrets hashés et stocke les événements à rejouer.

### Comment dans le code ?

Stockage local :

- [`raspberry/app/offline_store.py`](raspberry/app/offline_store.py)

Tables SQLite :

- `cached_reservations`
- `offline_events`
- `offline_metadata`

Synchronisation depuis backend :

- `sync_offline_cache()` dans [`raspberry/app/main.py`](raspberry/app/main.py)
- endpoint `terminal_offline_cache()` dans [`backend/api/views.py`](backend/api/views.py)

Rejeu des événements :

- `sync_offline_events()` dans [`raspberry/app/main.py`](raspberry/app/main.py)
- endpoint `terminal_offline_events()` dans [`backend/api/views.py`](backend/api/views.py)

La vérification locale utilise les mêmes hashes que le backend :

```python
hashlib.sha256(value.encode("utf-8")).hexdigest()
```

Référence :

- `hash_secret()` dans [`raspberry/app/offline_store.py`](raspberry/app/offline_store.py)

Le cache ne contient pas de secrets en clair.

## 27. Comment le backend est-il protégé côté réseau HTTP ?

### Réponse courte

Nginx est le point d'entrée. Il force HTTPS, ajoute des headers de sécurité, route les WebSockets et limite l'exposition directe des services.

### Comment dans le code ?

Nginx local :

- [`nginx/conf.d/station.conf`](nginx/conf.d/station.conf)

Nginx production :

- [`nginx/prod.conf.d/station.conf`](nginx/prod.conf.d/station.conf)

Mesures présentes :

- redirection HTTP vers HTTPS ;
- TLS ;
- `X-Frame-Options` ;
- `X-Content-Type-Options` ;
- `Referrer-Policy` ;
- `Content-Security-Policy` ;
- `client_max_body_size` ;
- proxy WebSocket pour `/ws/` ;
- routage séparé `/api/`, `/admin/`, `/grafana/`, `/kiosk/`.

Configuration Django associée :

- `SECURE_SSL_REDIRECT`
- `SESSION_COOKIE_SECURE`
- `CSRF_COOKIE_SECURE`
- `SECURE_HSTS_SECONDS`
- `SECURE_PROXY_SSL_HEADER`
- `CORS_ALLOWED_ORIGINS`
- `CORS_ALLOWED_ORIGIN_REGEXES`

Référence :

- [`backend/config/settings.py`](backend/config/settings.py)

## 28. Comment les IP locales variables sont-elles acceptées en développement ?

### Réponse courte

En mode développement uniquement, un middleware autorise automatiquement les IP privées locales pour faciliter les tests smartphone/Raspberry sur Wi-Fi.

### Comment dans le code ?

Middleware :

- [`backend/api/middleware.py`](backend/api/middleware.py)

Activation :

```python
if DEBUG and DEV_AUTO_TRUST_PRIVATE_NETWORK:
    MIDDLEWARE.insert(2, "api.middleware.DevelopmentPrivateNetworkHostMiddleware")
```

Référence :

- [`backend/config/settings.py`](backend/config/settings.py)

Ce middleware accepte notamment :

- `localhost`
- `127.0.0.1`
- `10.x.x.x`
- `172.16.x.x` à `172.31.x.x`
- `192.168.x.x`
- `.local`

En production, ce mécanisme ne doit pas remplacer une configuration explicite de `ALLOWED_HOSTS`.

## 29. Comment le WebSocket de supervision fonctionne ?

### Réponse courte

Django Channels expose des WebSockets admin et technicien. Les événements d'ingestion MQTT déclenchent un broadcast via Redis.

### Comment dans le code ?

ASGI :

- [`backend/config/asgi.py`](backend/config/asgi.py)

Routes :

- [`backend/api/routing.py`](backend/api/routing.py)

Consumers :

- [`backend/api/consumers.py`](backend/api/consumers.py)

Broadcast :

- [`backend/api/realtime.py`](backend/api/realtime.py)

À chaque ingestion MQTT, `process_mqtt_message()` appelle :

```python
broadcast_supervision_update(...)
```

Référence :

- [`backend/api/tasks.py`](backend/api/tasks.py)

Le payload envoyé au frontend est construit par :

- [`backend/api/services/supervision.py`](backend/api/services/supervision.py)

## 30. Comment la production est durcie ?

### Réponse courte

Le projet sépare la stack de développement et la stack production. La production utilise des images pinnées, des services non exposés directement, des healthchecks, des logs bornés, un backend ASGI et un reverse proxy Nginx.

### Comment dans le code ?

Compose développement :

- [`docker-compose.yml`](docker-compose.yml)

Compose production :

- [`docker-compose.prod.yml`](docker-compose.prod.yml)

Backend Docker :

- [`backend/Dockerfile`](backend/Dockerfile)

Le `Dockerfile` backend :

- installe les dépendances ;
- lance Ruff et pytest dans la cible `test` ;
- copie la preuve `/tmp/pytest-passed` dans la cible runtime ;
- crée un utilisateur système `station` ;
- exécute le runtime en non-root.

Raspberry Docker :

- [`raspberry/Dockerfile`](raspberry/Dockerfile)

Il crée aussi un utilisateur `station` et isole les fichiers d'état.

Frontend Docker :

- [`frontend/Dockerfile`](frontend/Dockerfile)

Il construit les assets avec Node puis sert le build statique avec Nginx.

Tests de durcissement :

- [`backend/api/tests/test_production_hardening.py`](backend/api/tests/test_production_hardening.py)
- [`backend/api/tests/test_container_security_config.py`](backend/api/tests/test_container_security_config.py)
- [`backend/api/tests/test_nginx_security_config.py`](backend/api/tests/test_nginx_security_config.py)

## 31. Comment les données personnelles peuvent-elles être anonymisées ?

### Réponse courte

Le projet prépare PostgreSQL Anonymizer de façon optionnelle : si l'extension `anon` est disponible, une migration pose des règles de masquage sur les colonnes sensibles.

### Comment dans le code ?

Migration :

- [`backend/api/migrations/0027_optional_postgresql_anonymizer.py`](backend/api/migrations/0027_optional_postgresql_anonymizer.py)

Colonnes masquées :

- `utilisateur.pseudo`
- `utilisateur.email`
- `profil_utilisateur.nom`
- `profil_utilisateur.telephone`
- `journal_securite.ip`
- `technicien.nom`
- `technicien.email`
- `technicien.telephone`

La migration vérifie d'abord :

```sql
SELECT EXISTS FROM pg_available_extensions WHERE name = 'anon'
```

Si l'extension n'est pas disponible, elle ne casse pas le déploiement.

## 32. Comment expliquer le projet en une phrase technique ?

Le projet est une architecture Django/PWA/Raspberry/ESP32 où le backend central décide les droits d'accès, le Raspberry exécute localement les commandes de borne, les ESP32 remontent leur télémétrie par MQTT, Redis/Celery absorbe l'ingestion asynchrone, PostgreSQL/TimescaleDB conserve l'historique, et Grafana/Channels exposent la supervision.
