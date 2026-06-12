import hashlib
import hmac
from datetime import timezone as datetime_timezone
from urllib.parse import quote

from django.conf import settings
from django.utils import timezone

try:
    from rdflib import Graph, Literal, Namespace, RDF, URIRef
    from rdflib.namespace import XSD
except ImportError:  # pragma: no cover - handled by endpoints and command.
    Graph = Literal = Namespace = RDF = URIRef = XSD = None

from api.models import (
    AlertStatus,
    Alerte,
    Borne,
    Capteur,
    CapteurData,
    Device,
    Emplacement,
    Session,
    Station,
    Technicien,
    TechnicienStation,
)


BASE_URI = "https://station-recharge.local/"
STATION = Namespace(f"{BASE_URI}ontology#") if Namespace else None
RESOURCE = Namespace(f"{BASE_URI}resource/") if Namespace else None
SOSA = Namespace("http://www.w3.org/ns/sosa/") if Namespace else None
GEO = Namespace("http://www.opengis.net/ont/geosparql#") if Namespace else None


class SemanticGraphUnavailable(RuntimeError):
    """Raised when the optional RDF dependency is not installed."""


def ensure_rdflib_available():
    """Fail explicitly when the semantic development dependency is missing."""
    if Graph is None:
        raise SemanticGraphUnavailable(
            "rdflib is required for semantic graph export. Install backend requirements first."
        )


def build_semantic_graph():
    """Build a privacy-filtered RDF graph from operational Django models."""
    ensure_rdflib_available()

    graph = Graph()
    _bind_prefixes(graph)
    _declare_local_ontology(graph)

    latest_measure_by_sensor = _latest_measure_by_sensor()

    for station in Station.objects.prefetch_related("bornes__emplacements").all():
        _add_station(graph, station)

    for borne in Borne.objects.select_related("station").all():
        _add_borne(graph, borne)

    for emplacement in Emplacement.objects.select_related("station", "borne").all():
        _add_emplacement(graph, emplacement)

    for device in Device.objects.select_related("emplacement", "emplacement__borne").all():
        _add_device(graph, device)

    for capteur in Capteur.objects.select_related("device", "device__emplacement").all():
        _add_sensor(graph, capteur, latest_measure_by_sensor.get(capteur.id_capteur))

    for session in Session.objects.select_related("emplacement", "reservation").filter(
        end_time__isnull=True
    ):
        _add_session(graph, session)

    for alerte in Alerte.objects.select_related(
        "session",
        "session__emplacement",
        "data",
        "data__capteur",
        "data__capteur__device",
        "data__capteur__device__emplacement",
        "assigned_technician",
    ).exclude(status__in=[AlertStatus.RESOLVED, AlertStatus.CLOSED, AlertStatus.FERMEE]):
        _add_alert(graph, alerte)

    for technicien in Technicien.objects.all():
        _add_technician(graph, technicien)

    for assignment in TechnicienStation.objects.select_related("technicien", "station").filter(
        is_active=True
    ):
        _add_technician_assignment(graph, assignment)

    return graph


def serialize_semantic_graph(graph, output_format="turtle"):
    """Serialize an RDF graph with a controlled set of output formats."""
    format_map = {
        "json-ld": "json-ld",
        "nt": "nt",
        "turtle": "turtle",
        "ttl": "turtle",
        "xml": "xml",
    }
    rdf_format = format_map.get(output_format, "turtle")
    return graph.serialize(format=rdf_format)


def build_semantic_network():
    """Build a frontend-friendly graph without exposing private data."""
    nodes = {}
    edges = []

    def node(node_id, label, node_type, **metadata):
        nodes[node_id] = {
            "id": node_id,
            "label": label,
            "type": node_type,
            **metadata,
        }

    def edge(source, target, label):
        edges.append({"from": source, "to": target, "label": label})

    latest_measure_by_sensor = _latest_measure_by_sensor()

    for station in Station.objects.all():
        station_id = f"station:{station.id_station}"
        node(
            station_id,
            station.nom,
            "station",
            status=station.statut,
            subtitle=station.localisation_text,
            station_id=str(station.id_station),
            level=0,
        )

    for borne in Borne.objects.select_related("station").all():
        station_id = f"station:{borne.station_id}"
        borne_id = f"borne:{borne.id_borne}"
        node(
            borne_id,
            borne.nom,
            "borne",
            status=borne.statut,
            subtitle=f"Borne {borne.numero}",
            station_id=str(borne.station_id),
            level=1,
        )
        edge(station_id, borne_id, "contient")

    for emplacement in Emplacement.objects.select_related("station", "borne").all():
        borne_id = f"borne:{emplacement.borne_id}"
        slot_id = f"emplacement:{emplacement.id_emplacement}"
        node(
            slot_id,
            f"Emplacement {emplacement.numero}",
            "emplacement",
            status=emplacement.statut,
            subtitle=f"Serrure {emplacement.lock_state}",
            station_id=str(emplacement.station_id),
            level=2,
        )
        edge(borne_id, slot_id, "contient")

    for device in Device.objects.select_related("emplacement", "emplacement__station").all():
        slot_id = f"emplacement:{device.emplacement_id}"
        device_id = f"device:{device.id_device}"
        firmware_label = device.firmware_version
        if device.expected_firmware_version:
            firmware_label = f"{device.firmware_version} / attendu {device.expected_firmware_version}"
        node(
            device_id,
            device.type_device,
            "device",
            status=device.status,
            subtitle=f"Firmware {firmware_label}",
            station_id=str(device.emplacement.station_id),
            level=3,
            firmware_status=device.firmware_update_status,
            ip_address=str(device.ip_address or ""),
            hardware_mac=device.hardware_mac or device.mac_address,
            last_seen=device.last_seen.isoformat() if device.last_seen else "",
        )
        edge(slot_id, device_id, "héberge")

    for capteur in Capteur.objects.select_related("device", "device__emplacement").all():
        sensor_id = f"sensor:{capteur.id_capteur}"
        latest = latest_measure_by_sensor.get(capteur.id_capteur)
        subtitle = capteur.unite
        status = "configured"
        if latest:
            subtitle = f"{latest.valeur:g} {capteur.unite}"
            status = "measured"
        node(
            sensor_id,
            capteur.type,
            "sensor",
            status=status,
            subtitle=subtitle,
            station_id=str(capteur.device.emplacement.station_id) if capteur.device_id else "",
            level=4,
            latest_value=latest.valeur if latest else None,
            latest_at=latest.timestamp.isoformat() if latest else "",
        )
        if capteur.device_id:
            edge(f"device:{capteur.device_id}", sensor_id, "mesure")

    for session in Session.objects.select_related("emplacement").filter(end_time__isnull=True):
        session_id = f"session:{_session_public_id(session.id_session)}"
        node(
            session_id,
            "Session active",
            "session",
            status=session.charge_state,
            subtitle=session.start_time.isoformat(),
            station_id=str(session.emplacement.station_id),
            level=4,
        )
        edge(f"emplacement:{session.emplacement_id}", session_id, "session")

    for alerte in Alerte.objects.select_related(
        "session",
        "session__emplacement",
        "data",
        "data__capteur",
        "data__capteur__device",
        "data__capteur__device__emplacement",
        "assigned_technician",
    ).exclude(status__in=[AlertStatus.RESOLVED, AlertStatus.CLOSED, AlertStatus.FERMEE]):
        slot = _alert_slot(alerte)
        alert_id = f"alert:{alerte.id_alerte}"
        node(
            alert_id,
            alerte.type,
            "alert",
            status=alerte.niveau_severite,
            subtitle=alerte.message,
            station_id=str(slot.station_id) if slot else "",
            level=5,
        )
        if slot:
            edge(f"emplacement:{slot.id_emplacement}", alert_id, "alerte")
        if alerte.assigned_technician_id:
            edge(alert_id, f"technician:{alerte.assigned_technician_id}", "assignée à")

    for technicien in Technicien.objects.all():
        technician_id = f"technician:{technicien.id_technicien}"
        node(
            technician_id,
            technicien.nom,
            "technician",
            status="assigned",
            subtitle="Technicien",
            level=5,
        )

    for assignment in TechnicienStation.objects.select_related("technicien", "station").filter(
        is_active=True
    ):
        station_id = f"station:{assignment.station_id}"
        technician_id = f"technician:{assignment.technicien_id}"
        if technician_id in nodes:
            stations = nodes[technician_id].setdefault("station_ids", [])
            stations.append(str(assignment.station_id))
        edge(station_id, technician_id, assignment.role)

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "generated_at": timezone.now().isoformat(),
    }


def _bind_prefixes(graph):
    """Register namespace prefixes used by serialized RDF outputs."""
    graph.bind("station", STATION)
    graph.bind("res", RESOURCE)
    graph.bind("sosa", SOSA)
    graph.bind("geo", GEO)
    graph.bind("xsd", XSD)


def _declare_local_ontology(graph):
    """Declare the minimal local ontology classes used by the export."""
    for class_name in (
        "ChargingStation",
        "ChargingCabinet",
        "ChargingSlot",
        "EmbeddedDevice",
        "ChargingSession",
        "OperationalAlert",
        "Technician",
    ):
        graph.add((STATION[class_name], RDF.type, STATION.Class))


def _latest_measure_by_sensor():
    """Return the latest telemetry row indexed by sensor identifier."""
    latest = {}
    for measure in CapteurData.objects.select_related("capteur").order_by(
        "-timestamp", "capteur_id"
    ):
        latest.setdefault(measure.capteur_id, measure)
    return latest


def _add_station(graph, station):
    """Add one station resource and its public properties."""
    subject = _resource("station", station.id_station)
    graph.add((subject, RDF.type, STATION.ChargingStation))
    _literal(graph, subject, STATION.name, station.nom)
    _literal(graph, subject, STATION.locationLabel, station.localisation_text)
    _literal(graph, subject, STATION.status, station.statut)
    _literal(graph, subject, STATION.createdAt, station.created_at, XSD.dateTime)
    _literal(graph, subject, GEO.lat, station.latitude, XSD.decimal)
    _literal(graph, subject, GEO.long, station.longitude, XSD.decimal)


def _add_borne(graph, borne):
    """Add one physical cabinet and its station relation."""
    subject = _resource("borne", borne.id_borne)
    station = _resource("station", borne.station_id)
    graph.add((subject, RDF.type, STATION.ChargingCabinet))
    graph.add((station, STATION.hasCabinet, subject))
    graph.add((subject, STATION.belongsToStation, station))
    _literal(graph, subject, STATION.name, borne.nom)
    _literal(graph, subject, STATION.number, borne.numero, XSD.integer)
    _literal(graph, subject, STATION.status, borne.statut)
    _literal(graph, subject, STATION.mqttPrefix, borne.mqtt_prefix)


def _add_emplacement(graph, emplacement):
    """Add one charging slot and its station/cabinet relations."""
    subject = _resource("emplacement", emplacement.id_emplacement)
    station = _resource("station", emplacement.station_id)
    borne = _resource("borne", emplacement.borne_id)
    graph.add((subject, RDF.type, STATION.ChargingSlot))
    graph.add((station, STATION.hasSlot, subject))
    graph.add((borne, STATION.hasSlot, subject))
    graph.add((subject, STATION.belongsToCabinet, borne))
    _literal(graph, subject, STATION.number, emplacement.numero, XSD.integer)
    _literal(graph, subject, STATION.status, emplacement.statut)
    _literal(graph, subject, STATION.lockState, emplacement.lock_state)


def _add_device(graph, device):
    """Add one ESP32 device and its firmware/network metadata."""
    subject = _resource("device", device.id_device)
    slot = _resource("emplacement", device.emplacement_id)
    graph.add((subject, RDF.type, STATION.EmbeddedDevice))
    graph.add((slot, STATION.hostsDevice, subject))
    graph.add((subject, STATION.installedOnSlot, slot))
    _literal(graph, subject, STATION.deviceType, device.type_device)
    _literal(graph, subject, STATION.status, device.status)
    _literal(graph, subject, STATION.firmwareVersion, device.firmware_version)
    _literal(graph, subject, STATION.expectedFirmwareVersion, device.expected_firmware_version)
    _literal(graph, subject, STATION.firmwareStatus, device.firmware_update_status)
    _literal(graph, subject, STATION.ipAddress, device.ip_address)
    _literal(graph, subject, STATION.hardwareMac, device.hardware_mac or device.mac_address)
    _literal(graph, subject, STATION.slotId, device.slot_id)
    _literal(graph, subject, STATION.lastSeen, device.last_seen, XSD.dateTime)


def _add_sensor(graph, capteur, latest_measure):
    """Add one sensor and optionally its latest observation."""
    subject = _resource("sensor", capteur.id_capteur)
    graph.add((subject, RDF.type, SOSA.Sensor))
    _literal(graph, subject, STATION.sensorType, capteur.type)
    _literal(graph, subject, STATION.unit, capteur.unite)

    if capteur.device_id:
        device = _resource("device", capteur.device_id)
        graph.add((device, STATION.hasSensor, subject))
        graph.add((subject, STATION.attachedToDevice, device))

    if latest_measure:
        observation = _resource("observation", latest_measure.id_data)
        graph.add((observation, RDF.type, SOSA.Observation))
        graph.add((observation, SOSA.madeBySensor, subject))
        graph.add((subject, STATION.latestObservation, observation))
        _literal(graph, observation, SOSA.resultTime, latest_measure.timestamp, XSD.dateTime)
        _literal(graph, observation, SOSA.hasSimpleResult, latest_measure.valeur, XSD.decimal)
        _literal(graph, subject, STATION.latestValue, latest_measure.valeur, XSD.decimal)
        _literal(graph, subject, STATION.latestTelemetryAt, latest_measure.timestamp, XSD.dateTime)


def _add_session(graph, session):
    """Add one active charging session using a pseudonymized identifier."""
    subject = _resource("session", _session_public_id(session.id_session))
    slot = _resource("emplacement", session.emplacement_id)
    graph.add((subject, RDF.type, STATION.ChargingSession))
    graph.add((slot, STATION.hasChargingSession, subject))
    graph.add((subject, STATION.sessionOnSlot, slot))
    _literal(graph, subject, STATION.chargeState, session.charge_state)
    _literal(graph, subject, STATION.startedAt, session.start_time, XSD.dateTime)
    _literal(graph, subject, STATION.endedAt, session.end_time, XSD.dateTime)


def _add_alert(graph, alerte):
    """Add one unresolved operational alert and its slot/technician links."""
    subject = _resource("alert", alerte.id_alerte)
    graph.add((subject, RDF.type, STATION.OperationalAlert))
    _literal(graph, subject, STATION.alertType, alerte.type)
    _literal(graph, subject, STATION.message, alerte.message)
    _literal(graph, subject, STATION.severity, alerte.niveau_severite)
    _literal(graph, subject, STATION.status, alerte.status)
    _literal(graph, subject, STATION.firstSeen, alerte.first_seen, XSD.dateTime)
    _literal(graph, subject, STATION.lastSeen, alerte.last_seen, XSD.dateTime)

    slot = _alert_slot(alerte)
    if slot:
        slot_subject = _resource("emplacement", slot.id_emplacement)
        graph.add((slot_subject, STATION.raisedAlert, subject))

    if alerte.assigned_technician_id:
        tech = _resource("technician", alerte.assigned_technician_id)
        graph.add((subject, STATION.assignedTo, tech))


def _add_technician(graph, technicien):
    """Add one technician without exposing private contact data."""
    subject = _resource("technician", technicien.id_technicien)
    graph.add((subject, RDF.type, STATION.Technician))
    _literal(graph, subject, STATION.name, technicien.nom)


def _add_technician_assignment(graph, assignment):
    """Link one technician to an assigned station and role."""
    station = _resource("station", assignment.station_id)
    technician = _resource("technician", assignment.technicien_id)
    graph.add((station, STATION.hasTechnician, technician))
    graph.add((technician, STATION.assignedToStation, station))
    graph.add((technician, STATION.stationRole, Literal(assignment.role)))


def _alert_slot(alerte):
    """Resolve the charging slot affected by an alert."""
    if alerte.session_id:
        return alerte.session.emplacement
    if alerte.data_id and alerte.data.capteur.device_id:
        return alerte.data.capteur.device.emplacement
    return None


def _literal(graph, subject, predicate, value, datatype=None):
    """Add a literal triple when the value is present."""
    if value is None or value == "":
        return
    if hasattr(value, "isoformat"):
        if timezone.is_aware(value):
            value = value.astimezone(datetime_timezone.utc)
        value = value.isoformat()
    graph.add((subject, predicate, Literal(value, datatype=datatype)))


def _resource(kind, identifier):
    """Build a stable resource URI for an internal identifier."""
    return URIRef(f"{RESOURCE}{kind}/{quote(str(identifier), safe='')}")


def _session_public_id(session_id):
    """Pseudonymize a session identifier with HMAC-SHA256."""
    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        str(session_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:32]
