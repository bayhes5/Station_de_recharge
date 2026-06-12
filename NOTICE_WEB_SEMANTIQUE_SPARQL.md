# Notice d'évolution : web sémantique, SPARQL et Semantic Web of Things

Cette notice explique comment le projet de station de recharge pourrait évoluer vers une couche de **web sémantique** et de **Semantic Web of Things (SWoT)**.

L'objectif n'est pas de remplacer l'architecture existante. Le système opérationnel doit rester basé sur :

- Django et Django REST Framework pour les règles métier ;
- PostgreSQL et TimescaleDB pour la persistance et les séries temporelles ;
- MQTT pour les échanges backend, Raspberry Pi et ESP32 ;
- Redis et Celery pour l'asynchronisme ;
- Grafana pour la supervision temporelle ;
- le kiosk Raspberry Pi pour l'interface borne ;
- les ESP32 pour les capteurs et actionneurs.

Le web sémantique serait une **couche complémentaire de lecture, d'analyse, d'interopérabilité et d'aide à la décision**. Elle permettrait de représenter les stations, bornes, emplacements, ESP32, capteurs, sessions, alertes et techniciens sous forme de graphe RDF, puis de les interroger avec SPARQL.

## 1. Avis honnête sur l'intérêt pour le projet

Pour ce projet, le web sémantique n'est pas indispensable au fonctionnement de base. La réservation, l'authentification, le démarrage de charge, la supervision Grafana et les alertes peuvent fonctionner sans SPARQL.

En revanche, c'est une perspective d'évolution pertinente si l'on veut aller vers :

- une supervision multi-stations plus intelligente ;
- une maintenance plus structurée ;
- une interopérabilité avec d'autres systèmes IoT ;
- une intégration dans un contexte smart city ou bâtiment intelligent ;
- une meilleure explicabilité des liens entre équipements, capteurs, alertes et interventions ;
- une base de connaissances exploitable par des outils d'aide à la décision ou par une IA.

La bonne position est donc :

```text
Django/PostgreSQL/MQTT/Grafana = fonctionnement opérationnel
RDF/SPARQL = couche de connaissance, d'interopérabilité et d'analyse
```

En soutenance, il faut éviter de présenter SPARQL comme une technologie magique ou meilleure que SQL en toutes circonstances. Ce n'est pas le cas. L'intérêt est ailleurs : donner un sens explicite aux relations métier et rendre les données plus réutilisables par d'autres systèmes.

## 2. Pourquoi en parler à l'époque de l'IA ?

Le sujet devient intéressant avec l'IA, car un modèle d'IA peut produire du texte, mais il ne connaît pas toujours avec certitude la structure réelle du système.

Un graphe sémantique apporte :

- des relations explicites ;
- un vocabulaire métier formel ;
- des liens vérifiables entre les objets ;
- une structure interrogeable ;
- une base factuelle que l'IA peut consulter au lieu d'inventer.

Exemple :

```text
Question utilisateur :
"Quelles stations ont une charge en cours, un firmware ESP32 obsolète
et une température supérieure au seuil ?"
```

Sans couche sémantique, une IA doit connaître le schéma SQL interne ou deviner comment les tables sont reliées.

Avec une couche RDF, l'IA peut être utilisée comme interface en langage naturel :

```text
Question en français
  -> génération d'une requête SPARQL contrôlée
  -> exécution sur le graphe RDF
  -> réponse factuelle
  -> reformulation claire par l'IA
```

L'IA reste utile pour l'interface, l'explication et la synthèse. Le graphe RDF reste utile pour la vérité métier structurée.

## 3. IA et web sémantique : différence et complémentarité

| Sujet | IA générative | Web sémantique / SPARQL |
|---|---|---|
| Nature | Modèle probabiliste | Graphe structuré |
| Force | Compréhension du langage, synthèse, aide à la décision | Relations explicites, interopérabilité, requêtes fiables |
| Risque | Hallucination, approximation | Modélisation initiale plus coûteuse |
| Exemple | Expliquer une alerte à un technicien | Trouver les équipements réellement concernés |
| Rôle dans le projet | Assistant, aide à l'exploitation | Base de connaissances technique |

Les deux approches sont donc complémentaires.

Exemple concret :

```text
SPARQL répond :
"L'emplacement 1 de la Borne 1 à Station Demo est en charge,
son ESP32 a un firmware 1.0.0 alors que la version attendue est 1.1.0,
la température est supérieure au seuil et le technicien affecté est T-02."

L'IA reformule :
"Une intervention est recommandée sur l'emplacement 1 de la Station Demo.
La charge est active, la température dépasse le seuil et le firmware de l'ESP32
n'est pas à jour. Le technicien T-02 est responsable de cette station."
```

Dans ce modèle, l'IA n'invente pas les faits. Elle explique des faits issus du graphe.

## 4. Semantic Web of Things (SWoT)

Le **Semantic Web of Things** consiste à appliquer les principes du web sémantique aux objets connectés.

Dans le projet, cela revient à décrire les ESP32 et leurs capteurs comme des objets IoT compréhensibles par d'autres systèmes.

Au lieu de dire seulement :

```json
{
  "temperature_c": 28.4,
  "current_a": 1.2,
  "lock_state": "locked"
}
```

on peut décrire :

```text
ESP32 slot1
  -> est installé sur -> Emplacement 1
  -> observe -> Température
  -> observe -> Courant
  -> commande -> Serrure
  -> publie sa télémétrie via -> MQTT
  -> appartient à -> Borne 1
  -> appartient à -> Station Demo
```

Cette description est plus riche, car elle donne du sens aux données.

### 4.1. Standards utiles

Pour éviter d'inventer un vocabulaire fermé au projet, il est possible de s'appuyer sur des vocabulaires existants :

| Standard | Utilisation possible |
|---|---|
| SOSA / SSN | Décrire les capteurs et les observations |
| SAREF | Décrire les appareils, l'énergie et les services IoT |
| QUDT | Décrire les unités physiques : °C, %, A, V, W, kWh |
| GeoSPARQL | Décrire la localisation des stations |
| W3C Web of Things Thing Description | Décrire les propriétés, actions et événements d'un objet connecté |

Dans ce projet, un ESP32 pourrait être décrit comme un objet connecté qui expose :

- des propriétés : température, humidité, courant, tension, puissance, énergie, état serrure ;
- des actions : unlock, lock, start, stop ;
- des événements : surchauffe, surintensité, ESP32 offline, firmware obsolète.

## 5. Positionnement par rapport à PostgreSQL

PostgreSQL reste la source de vérité du projet.

Le web sémantique ne doit pas remplacer :

- les transactions de réservation ;
- les contraintes d'intégrité ;
- les permissions ;
- la validation RFID, QR ou SMS ;
- les commandes MQTT ;
- le stockage temporel de la télémétrie ;
- les dashboards Grafana.

SPARQL doit être une couche de lecture.

```text
PostgreSQL / TimescaleDB
  -> données fiables, transactionnelles et temporelles
  -> source de vérité

RDF / SPARQL
  -> représentation métier et interopérable
  -> couche de connaissance
```

## 6. Pourquoi SQL peut répondre, mais pas avec le même objectif

Une base relationnelle peut déjà répondre à beaucoup de questions complexes.

Exemple :

```text
Donne-moi les emplacements en charge, dont l'ESP32 a un firmware obsolète,
avec une température supérieure au seuil, et le technicien responsable.
```

Exemple SQL simplifié :

```sql
SELECT
  s.nom AS station,
  b.nom AS borne,
  e.numero AS emplacement,
  d.firmware_version,
  d.expected_firmware_version,
  cd.valeur AS temperature,
  t.nom AS technicien
FROM station s
JOIN borne b ON b.id_station = s.id_station
JOIN emplacement e ON e.id_borne = b.id_borne
JOIN device d ON d.id_emplacement = e.id_emplacement
JOIN capteur c ON c.id_device = d.id_device
JOIN capteur_data cd ON cd.id_capteur = c.id_capteur
JOIN technicien_station ts ON ts.id_station = s.id_station
JOIN technicien t ON t.id_technicien = ts.id_technicien
WHERE d.firmware_update_status = 'update_required'
  AND c.type = 'temperature'
  AND cd.valeur > 60
  AND e.etat = 'charging';
```

Cette requête fonctionne, mais elle dépend fortement :

- des noms de tables ;
- des noms de colonnes ;
- des clés étrangères ;
- des valeurs internes comme `charging` ou `update_required` ;
- du schéma exact de l'application Django.

Si demain on ajoute :

- une autre marque de borne ;
- une API externe de supervision ;
- une base de données de maintenance ;
- une météo locale ;
- un référentiel de ville connectée ;
- une autre forme de capteur ;

il faut ajouter de nouvelles jointures, de nouveaux mappings et parfois de nouveaux modèles.

Dans un graphe RDF, la question est exprimée en relations métier :

```text
Station
  -> contient -> Borne
  -> contient -> Emplacement
  -> héberge -> ESP32
  -> possède -> Capteur
  -> observe -> Température
  -> a pour technicien -> Technicien
```

La différence n'est donc pas :

```text
SQL = mauvais
SPARQL = bon
```

La différence est :

```text
SQL = excellent pour le système opérationnel
SPARQL = utile pour l'interopérabilité, la connaissance et l'analyse transversale
```

## 7. Architecture cible recommandée

Le fonctionnement recommandé est :

```text
ESP32
  -> MQTT
  -> backend Django
  -> PostgreSQL / TimescaleDB
  -> export RDF filtré
  -> triplestore RDF
  -> requêtes SPARQL
  -> exploitation par admin, supervision ou outil d'aide à la décision
```

Références code existantes :

- ingestion MQTT : `backend/api/mqtt.py`
- traitement asynchrone : `backend/api/tasks.py`
- normalisation télémétrie : `backend/api/services/telemetry.py`
- modèles métier : `backend/api/models.py`
- commandes MQTT : `backend/api/services/mqtt_commands.py`
- dashboards Grafana : `grafana/dashboards/`

Le triplestore ne doit jamais décider seul d'ouvrir une serrure ou de démarrer une charge. Les actions restent dans le backend.

## 8. Modèle métier à représenter

La hiérarchie physique retenue dans le projet est :

```text
Station
  -> Borne
    -> Emplacement
      -> ESP32
        -> Capteurs
```

Cette structure est cohérente avec le prototype :

- une station est un site physique ;
- une station contient une ou plusieurs bornes ;
- une borne contient un ou plusieurs emplacements ;
- un emplacement est réservé et supervisé ;
- un ESP32 pilote l'emplacement ;
- les capteurs mesurent l'état physique de l'emplacement.

Objets Django concernés :

| Modèle | Rôle | Usage sémantique |
|---|---|---|
| `Station` | Site physique | Ressource géographique |
| `Borne` | Borne ou armoire | Sous-ensemble d'une station |
| `Emplacement` | Point de recharge | Ressource réservée |
| `Device` | ESP32 | Objet connecté |
| `Capteur` | Capteur physique | Capteur SOSA |
| `CapteurData` | Mesure brute | Observation |
| `Session` | Charge effective | Session opérationnelle |
| `SessionTelemetry` | Mesures liées à une session | Observation contextualisée |
| `Alerte` | Incident ou anomalie | Événement de supervision |
| `Technicien` | Intervenant | Acteur de maintenance |
| `TechnicienStation` | Périmètre d'intervention | Droit métier |
| `Maintenance` | Intervention | Action corrective |

## 9. Exemple de modèle RDF

Préfixes recommandés :

```turtle
@prefix station: <https://station-recharge.local/ontology#> .
@prefix resource: <https://station-recharge.local/resource/> .
@prefix sosa: <http://www.w3.org/ns/sosa/> .
@prefix ssn: <http://www.w3.org/ns/ssn/> .
@prefix saref: <https://saref.etsi.org/core/> .
@prefix geo: <http://www.opengis.net/ont/geosparql#> .
@prefix qudt: <http://qudt.org/schema/qudt/> .
@prefix unit: <http://qudt.org/vocab/unit/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
```

Exemple simplifié :

```turtle
resource:station/demo
    a station:ChargingStation ;
    station:name "Station Demo" ;
    station:hasCabinet resource:borne/demo-1 .

resource:borne/demo-1
    a station:ChargingCabinet ;
    station:number 1 ;
    station:hasSlot resource:emplacement/slot1 .

resource:emplacement/slot1
    a station:ChargingSlot ;
    station:number 1 ;
    station:chargeState "charging" ;
    station:hostsDevice resource:device/esp32-slot1 .

resource:device/esp32-slot1
    a station:EmbeddedDevice ;
    station:firmwareVersion "1.0.0" ;
    station:expectedFirmwareVersion "1.1.0" ;
    station:firmwareStatus "update_required" ;
    station:ipAddress "172.20.10.42" ;
    station:hardwareMac "AA:BB:CC:DD:EE:FF" ;
    station:hasSensor resource:sensor/temperature-slot1 ;
    station:hasSensor resource:sensor/current-slot1 ;
    station:canExecuteAction station:Unlock ;
    station:canExecuteAction station:StopCharge .

resource:sensor/temperature-slot1
    a sosa:Sensor ;
    sosa:observes station:Temperature .

resource:observation/temp-2026-05-29T10-00-00
    a sosa:Observation ;
    sosa:madeBySensor resource:sensor/temperature-slot1 ;
    sosa:observedProperty station:Temperature ;
    sosa:hasSimpleResult "52.4"^^xsd:decimal ;
    qudt:unit unit:DEG_C ;
    sosa:resultTime "2026-05-29T10:00:00+02:00"^^xsd:dateTime .
```

## 10. Exemple orienté Web of Things

Un ESP32 peut être décrit comme une "Thing" avec propriétés, actions et événements.

Exemple conceptuel :

```json
{
  "id": "esp32-slot1",
  "title": "ESP32 Emplacement 1",
  "properties": {
    "temperature": {
      "type": "number",
      "unit": "degree Celsius"
    },
    "humidity": {
      "type": "number",
      "unit": "percent"
    },
    "current": {
      "type": "number",
      "unit": "ampere"
    },
    "lockState": {
      "type": "string",
      "enum": ["locked", "unlocked"]
    }
  },
  "actions": {
    "unlock": {},
    "stopCharge": {}
  },
  "events": {
    "overTemperature": {},
    "overCurrent": {},
    "offline": {}
  }
}
```

Dans le projet, cette description serait documentaire ou exportée vers une couche sémantique. Elle ne remplacerait pas le code MicroPython de l'ESP32.

## 11. Requêtes SPARQL améliorées

### 11.1. Emplacements en charge avec firmware obsolète et température élevée

```sparql
PREFIX station: <https://station-recharge.local/ontology#>
PREFIX sosa: <http://www.w3.org/ns/sosa/>

SELECT ?stationName ?borneNumber ?slotNumber ?device ?firmware ?expected ?temperature ?technicianName
WHERE {
  ?station a station:ChargingStation ;
           station:name ?stationName ;
           station:assignedTechnician ?technician ;
           station:hasCabinet ?borne .

  ?technician station:name ?technicianName .

  ?borne station:number ?borneNumber ;
         station:hasSlot ?slot .

  ?slot station:number ?slotNumber ;
        station:chargeState "charging" ;
        station:hostsDevice ?device .

  ?device station:firmwareVersion ?firmware ;
          station:expectedFirmwareVersion ?expected ;
          station:firmwareStatus "update_required" ;
          station:hasSensor ?sensor .

  ?sensor sosa:observes station:Temperature .

  ?observation sosa:madeBySensor ?sensor ;
               sosa:hasSimpleResult ?temperature .

  FILTER (?temperature > 50)
}
ORDER BY DESC(?temperature)
```

### 11.2. Sessions actives sans télémétrie récente

```sparql
PREFIX station: <https://station-recharge.local/ontology#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?session ?slot ?lastTelemetry
WHERE {
  ?slot station:hasChargingSession ?session .
  ?session station:chargeState "charging" ;
           station:lastTelemetryAt ?lastTelemetry .

  FILTER (?lastTelemetry < "2026-05-29T09:55:00+02:00"^^xsd:dateTime)
}
ORDER BY ?lastTelemetry
```

Utilité :

- détecter un ESP32 qui ne publie plus ;
- détecter un bridge MQTT arrêté ;
- détecter une session backend encore ouverte mais sans données terrain.

### 11.3. Charge détectée sans session active

```sparql
PREFIX station: <https://station-recharge.local/ontology#>

SELECT ?stationName ?slot ?device ?current ?time
WHERE {
  ?station station:name ?stationName ;
           station:hasCabinet ?borne .

  ?borne station:hasSlot ?slot .
  ?slot station:hostsDevice ?device .

  ?device station:lastCurrent ?current ;
          station:lastTelemetryAt ?time .

  FILTER (?current > 0.5)

  FILTER NOT EXISTS {
    ?slot station:hasChargingSession ?session .
    ?session station:chargeState "charging" .
  }
}
ORDER BY DESC(?current)
```

Utilité :

- détecter une charge non autorisée ;
- détecter une session backend non créée ;
- détecter une incohérence entre terrain et logiciel.

### 11.4. Quels capteurs observent une grandeur physique donnée ?

```sparql
PREFIX station: <https://station-recharge.local/ontology#>
PREFIX sosa: <http://www.w3.org/ns/sosa/>

SELECT ?slot ?device ?sensor
WHERE {
  ?slot station:hostsDevice ?device .
  ?device station:hasSensor ?sensor .
  ?sensor sosa:observes station:Current .
}
ORDER BY ?slot
```

Utilité :

- retrouver les ESP32 capables de mesurer le courant ;
- vérifier la cohérence du câblage logique ;
- préparer une intervention technique.

### 11.5. Actions disponibles sur un ESP32

```sparql
PREFIX station: <https://station-recharge.local/ontology#>

SELECT ?device ?action
WHERE {
  ?device a station:EmbeddedDevice ;
          station:canExecuteAction ?action .
}
ORDER BY ?device ?action
```

Utilité :

- savoir si un équipement sait ouvrir une serrure ;
- distinguer un emplacement simple capteur d'un emplacement pilotable ;
- documenter les capacités sans lire le code embarqué.

### 11.6. Alertes critiques et technicien responsable

```sparql
PREFIX station: <https://station-recharge.local/ontology#>

SELECT ?stationName ?slot ?alert ?message ?technicianName
WHERE {
  ?station a station:ChargingStation ;
           station:name ?stationName ;
           station:assignedTechnician ?technician ;
           station:hasCabinet ?borne .

  ?technician station:name ?technicianName .

  ?borne station:hasSlot ?slot .
  ?slot station:raisedAlert ?alert .

  ?alert station:severity "critical" ;
         station:status "open" ;
         station:message ?message .
}
ORDER BY ?stationName ?slot
```

### 11.7. Candidats à la maintenance préventive

```sparql
PREFIX station: <https://station-recharge.local/ontology#>

SELECT ?slot ?device ?alertCount ?firmwareStatus
WHERE {
  ?slot station:hostsDevice ?device ;
        station:alertCountLast7Days ?alertCount .

  ?device station:firmwareStatus ?firmwareStatus .

  FILTER (?alertCount >= 3 || ?firmwareStatus = "update_required")
}
ORDER BY DESC(?alertCount)
```

Utilité :

- prioriser les interventions ;
- croiser alertes et firmware ;
- préparer une vue technicien.

## 12. Scénario avec IA et SPARQL

### 12.1. Question en langage naturel

```text
Quelles bornes doivent être vérifiées en priorité aujourd'hui ?
```

### 12.2. Transformation en requête contrôlée

L'application peut utiliser une liste de requêtes SPARQL prévalidées plutôt que laisser l'IA générer librement n'importe quelle requête.

Exemple de stratégie :

```text
1. L'utilisateur pose une question.
2. L'application classe l'intention : maintenance_prioritaire.
3. L'application sélectionne une requête SPARQL prévalidée.
4. Le triplestore retourne les résultats.
5. L'IA reformule les résultats en langage clair.
```

Cette stratégie réduit le risque de requête dangereuse ou incohérente.

### 12.3. Réponse possible

```text
Trois emplacements sont à vérifier en priorité :
- Station Demo, Borne 1, Emplacement 1 : température élevée et firmware obsolète.
- Station Gare, Borne 2, Emplacement 3 : session active sans télémétrie récente.
- Station Campus, Borne 1, Emplacement 2 : courant détecté sans session active.
```

## 13. Données à exporter et données à exclure

### 13.1. Données techniques exportables

La couche RDF peut exporter :

- stations ;
- bornes ;
- emplacements ;
- ESP32 ;
- adresse IP ESP32 ;
- adresse MAC ESP32 ;
- version firmware ;
- capteurs ;
- dernières mesures ;
- sessions actives ou récentes ;
- alertes ouvertes ;
- états techniques ;
- maintenances ;
- techniciens affectés à des stations.

### 13.2. Données à exclure

Pour respecter le privacy by design, il ne faut pas exporter :

- mot de passe ;
- hash de mot de passe ;
- token JWT ;
- refresh token ;
- secret QR ;
- code SMS ;
- UID RFID ;
- email utilisateur ;
- téléphone utilisateur ;
- nom complet d'un utilisateur final ;
- adresse personnelle.

### 13.3. Pseudonymisation des sessions

Si une session doit être référencée, on peut utiliser un identifiant pseudonymisé :

```text
session_public_id = HMAC(secret_export, session_id)
```

Ainsi, le graphe peut relier une session, une télémétrie et une alerte sans exposer directement l'utilisateur.

## 14. Sécurité recommandée

La couche SPARQL doit respecter les règles suivantes :

- endpoint en lecture seule ;
- authentification obligatoire ;
- accès réseau limité ;
- aucune commande matériel depuis SPARQL ;
- aucune donnée personnelle en clair ;
- pas de secrets dans le graphe ;
- export généré par le backend, pas par accès direct à la base ;
- logs d'accès au triplestore ;
- requêtes lourdes limitées ou réservées à l'administration.

SPARQL ne doit jamais être utilisé pour :

- valider une authentification ;
- ouvrir une serrure ;
- lancer une charge ;
- arrêter une charge ;
- modifier une réservation ;
- envoyer une commande MQTT.

## 15. Performance et volumétrie

Il ne faut pas exporter toute la télémétrie brute dans RDF.

TimescaleDB reste plus adapté pour :

- les mesures toutes les 5 ou 10 secondes ;
- les courbes temporelles ;
- les agrégations par minute, heure ou jour ;
- l'historique de puissance et d'énergie ;
- les dashboards Grafana.

Le graphe RDF peut se limiter à :

- la dernière mesure connue par capteur ;
- les sessions actives ;
- les sessions récentes ;
- les alertes ouvertes ;
- les agrégats utiles ;
- les états firmware ;
- les relations infrastructure / technicien.

Cette approche évite de transformer le triplestore en base de séries temporelles.

## 16. Mise en place future

### 16.1. Structure de dossiers

```text
semantic/
  ontology/
    station-recharge.ttl
  queries/
    alerts.rq
    firmware.rq
    sessions.rq
    maintenance.rq
  exports/
    station-recharge.ttl
```

### 16.2. Commande Django d'export

Commande proposée :

```text
backend/api/management/commands/export_semantic_graph.py
```

Commande d'utilisation :

```bash
python backend/manage.py export_semantic_graph --output semantic/exports/station-recharge.ttl
```

La commande doit :

- lire les stations, bornes et emplacements ;
- lire les ESP32 ;
- lire les capteurs ;
- lire les dernières mesures ;
- lire les sessions actives ;
- lire les alertes ouvertes ;
- lire les techniciens affectés ;
- exclure les données personnelles ;
- générer un fichier Turtle.

### 16.3. Exemple RDFLib

```python
from rdflib import Graph, Literal, Namespace, RDF

STATION = Namespace("https://station-recharge.local/ontology#")
RESOURCE = Namespace("https://station-recharge.local/resource/")

graph = Graph()

station_uri = RESOURCE[f"station/{station.id_station}"]
graph.add((station_uri, RDF.type, STATION.ChargingStation))
graph.add((station_uri, STATION.name, Literal(station.nom)))

borne_uri = RESOURCE[f"borne/{borne.id_borne}"]
graph.add((borne_uri, RDF.type, STATION.ChargingCabinet))
graph.add((station_uri, STATION.hasCabinet, borne_uri))
```

### 16.4. Triplestore possible

Pour un environnement libre et académique, Apache Jena Fuseki est adapté.

Exemple de service Docker futur :

```yaml
fuseki:
  image: stain/jena-fuseki:latest
  ports:
    - "3030:3030"
  volumes:
    - fuseki-data:/fuseki
  environment:
    ADMIN_PASSWORD: change-me
```

En production, il faudrait :

- pinner l'image Docker ;
- mettre le mot de passe dans une variable d'environnement ;
- limiter l'accès réseau ;
- désactiver l'update public ;
- sauvegarder le volume si le graphe devient important.

### 16.5. Chargement du graphe

Exemple :

```bash
curl -u admin:change-me \
  -X POST \
  -H "Content-Type: text/turtle" \
  --data-binary @semantic/exports/station-recharge.ttl \
  http://localhost:3030/station/data
```

## 17. Roadmap recommandée

### Phase 1 : documentation

Objectif :

- définir les classes RDF ;
- définir les relations ;
- choisir les vocabulaires standards ;
- écrire les requêtes SPARQL exemples ;
- documenter les données interdites à l'export.

### Phase 2 : export statique

Objectif :

- créer une commande Django d'export Turtle ;
- exporter uniquement les données techniques ;
- tester les requêtes sur un fichier local.

### Phase 3 : triplestore local

Objectif :

- ajouter Fuseki en option Docker ;
- charger le fichier Turtle ;
- tester les requêtes depuis une interface SPARQL.

### Phase 4 : intégration supervision

Objectif :

- ajouter des vues transversales non critiques ;
- croiser alertes, firmware, session et technicien ;
- garder Grafana pour les courbes ;
- garder Django pour les actions.

### Phase 5 : assistant IA contrôlé

Objectif :

- permettre une question en langage naturel ;
- mapper la question vers une requête prévalidée ;
- retourner une réponse explicable ;
- ne jamais laisser l'IA déclencher directement une commande matériel.

## 18. Ce qu'il ne faut pas faire

Il ne faut pas :

- remplacer PostgreSQL par un triplestore ;
- stocker tous les points de télémétrie dans RDF ;
- exposer un endpoint SPARQL public ;
- exporter les secrets QR, SMS, RFID ou JWT ;
- laisser SPARQL commander le matériel ;
- laisser une IA écrire librement des commandes critiques ;
- utiliser le graphe comme source de vérité opérationnelle ;
- complexifier le prototype avant d'avoir stabilisé MQTT, Grafana et les scénarios terrain.

## 19. Réponse courte pour la soutenance

> Le web sémantique est une perspective intéressante pour ce projet, surtout dans un contexte IoT et smart city. Je ne l'utiliserais pas pour le cœur opérationnel, car les réservations, les sessions, les commandes MQTT et la télémétrie temporelle sont mieux gérées par Django, PostgreSQL, TimescaleDB et Grafana. En revanche, RDF et SPARQL peuvent créer une couche de connaissance au-dessus du système. Cette couche permettrait de relier les stations, bornes, emplacements, ESP32, capteurs, alertes, sessions et techniciens avec des vocabulaires standards comme SOSA/SSN, SAREF, QUDT, GeoSPARQL ou W3C Web of Things. À l'époque de l'IA, c'est intéressant parce qu'une IA peut interroger ce graphe pour répondre à des questions métier sans inventer les relations. Le graphe devient une base factuelle et explicable, tandis que l'IA sert à formuler et expliquer les résultats. Pour des raisons de sécurité et de confidentialité, cette couche resterait en lecture seule, sans données personnelles ni secrets, et ne commanderait jamais directement le matériel.

## 20. Réponse si le jury demande pourquoi ne pas tout faire en IA

> L'IA est utile pour dialoguer, expliquer et aider à analyser. Mais elle n'est pas une source de vérité fiable pour savoir quel capteur appartient à quel emplacement, quel technicien est responsable d'une station ou quel ESP32 a un firmware obsolète. Ces informations doivent venir d'une base structurée. Le web sémantique apporte cette structure : les relations sont explicites, vérifiables et interrogeables. L'approche la plus robuste est donc de combiner les deux : un graphe RDF pour les faits et une IA pour l'interface et la synthèse.

## 21. Réponse si le jury demande pourquoi ne pas rester en SQL

> On peut rester en SQL pour le fonctionnement opérationnel, et c'est ce que fait le projet. PostgreSQL est adapté aux transactions, aux contraintes, aux permissions et aux performances. SPARQL devient intéressant si l'on veut ouvrir le système à d'autres domaines : ville connectée, maintenance, énergie, bâtiment intelligent, autres fabricants de bornes. SQL interroge un schéma interne ; SPARQL interroge un graphe de connaissances où les relations métier ont un sens explicite et peuvent utiliser des vocabulaires standards.
