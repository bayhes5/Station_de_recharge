from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
OUTPUT_DIR = ROOT / "docs" / "source" / "_static" / "uml"

sys.path.insert(0, str(BACKEND_DIR))
os.environ["DEBUG"] = "True"
os.environ.setdefault("SECRET_KEY", "docs-local-secret-key-not-for-production")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402
from django.db import models  # noqa: E402


django.setup()

from api.models import (  # noqa: E402
    Alerte,
    AlertSeverity,
    AlertStatus,
    Authentification,
    Borne,
    BorneStatus,
    Capteur,
    CapteurData,
    ChargeSessionState,
    Consentement,
    ConsentStatus,
    ConsentType,
    Device,
    DeviceCommandLog,
    DeviceStatus,
    DeviceType,
    Emplacement,
    EmplacementStatus,
    FirmwareUpdateStatus,
    JournalSecurite,
    LockState,
    Maintenance,
    MaintenanceStatus,
    ProfilUtilisateur,
    Reservation,
    ReservationAuthChoice,
    ReservationStatus,
    Role,
    SecurityLogStatus,
    Session,
    SessionTelemetry,
    Station,
    StationStatus,
    Technicien,
    TechnicienStation,
    TechnicianStationRole,
    TypeAuth,
    Utilisateur,
    UtilisateurRole,
    UserStatus,
)


@dataclass(frozen=True)
class Diagram:
    file_stem: str
    title: str
    models: list[type[models.Model]]
    enums: list[type[models.TextChoices]]
    direction: str = "left to right direction"


DIAGRAMS = [
    Diagram(
        file_stem="uml_identites_acces",
        title="Identités et accès",
        models=[
            Utilisateur,
            ProfilUtilisateur,
            Role,
            UtilisateurRole,
            Consentement,
            JournalSecurite,
            TypeAuth,
            Authentification,
        ],
        enums=[UserStatus, ConsentType, ConsentStatus, SecurityLogStatus],
    ),
    Diagram(
        file_stem="uml_infrastructure_charge",
        title="Infrastructure, réservation et supervision",
        models=[
            Station,
            Borne,
            Emplacement,
            Reservation,
            Session,
            SessionTelemetry,
            Device,
            DeviceCommandLog,
            Capteur,
            CapteurData,
            Alerte,
        ],
        enums=[
            StationStatus,
            BorneStatus,
            EmplacementStatus,
            LockState,
            ReservationAuthChoice,
            ReservationStatus,
            ChargeSessionState,
            DeviceType,
            DeviceStatus,
            FirmwareUpdateStatus,
            AlertSeverity,
            AlertStatus,
        ],
    ),
    Diagram(
        file_stem="uml_maintenance_exploitation",
        title="Maintenance et exploitation",
        models=[
            Utilisateur,
            Technicien,
            Station,
            TechnicienStation,
            Maintenance,
            Alerte,
        ],
        enums=[
            UserStatus,
            StationStatus,
            TechnicianStationRole,
            MaintenanceStatus,
            AlertSeverity,
            AlertStatus,
        ],
    ),
]

CHOICE_TYPES = {
    ("Utilisateur", "statut"): "UserStatus",
    ("Consentement", "type"): "ConsentType",
    ("Consentement", "statut"): "ConsentStatus",
    ("JournalSecurite", "statut"): "SecurityLogStatus",
    ("Station", "statut"): "StationStatus",
    ("Borne", "statut"): "BorneStatus",
    ("Emplacement", "statut"): "EmplacementStatus",
    ("Emplacement", "lock_state"): "LockState",
    ("Reservation", "auth_choice"): "ReservationAuthChoice",
    ("Reservation", "statut"): "ReservationStatus",
    ("Session", "charge_state"): "ChargeSessionState",
    ("Device", "type_device"): "DeviceType",
    ("Device", "status"): "DeviceStatus",
    ("Device", "firmware_update_status"): "FirmwareUpdateStatus",
    ("Alerte", "niveau_severite"): "AlertSeverity",
    ("Alerte", "status"): "AlertStatus",
    ("TechnicienStation", "role"): "TechnicianStationRole",
    ("Maintenance", "status"): "MaintenanceStatus",
}

COMPOSITIONS = {
    ("Utilisateur", "ProfilUtilisateur", "utilisateur"),
    ("Station", "Borne", "station"),
    ("Borne", "Emplacement", "borne"),
    ("Emplacement", "Device", "emplacement"),
    ("Device", "Capteur", "device"),
    ("Capteur", "CapteurData", "capteur"),
    ("Reservation", "Session", "reservation"),
    ("Session", "SessionTelemetry", "session"),
}

DISPLAY_FIELDS = {
    "Utilisateur": [
        "pseudo",
        "email",
        "password",
        "statut",
        "failed_attempts",
        "must_change_password",
        "password_reset_at",
        "is_active",
        "is_staff",
        "date_joined",
    ],
    "ProfilUtilisateur": ["nom", "telephone", "telephone_verifie"],
    "Role": ["nom", "description"],
    "UtilisateurRole": ["assigned_at"],
    "Consentement": ["type", "statut", "date_consentement"],
    "JournalSecurite": ["action", "ip", "statut", "date_action"],
    "TypeAuth": ["libelle", "factor_level"],
    "Authentification": [
        "hash_valeur",
        "display_value",
        "metadata",
        "expiration",
        "is_active",
        "created_at",
    ],
    "Station": ["nom", "localisation_text", "latitude", "longitude", "statut"],
    "Borne": ["numero", "nom", "terminal_code", "mqtt_prefix", "statut"],
    "Emplacement": ["numero", "statut", "lock_state"],
    "Reservation": [
        "reference_code",
        "auth_choice",
        "date_debut",
        "date_fin",
        "statut",
    ],
    "Session": [
        "start_time",
        "end_time",
        "charge_state",
        "charge_state_updated_at",
    ],
    "SessionTelemetry": ["courant", "tension", "energie_kwh", "timestamp"],
    "Device": [
        "type_device",
        "firmware_version",
        "expected_firmware_version",
        "firmware_update_status",
        "ip_address",
        "slot_id",
        "hardware_mac",
        "last_seen",
        "status",
    ],
    "DeviceCommandLog": [
        "command_id",
        "action",
        "status",
        "message",
        "source",
        "timestamp",
    ],
    "Capteur": ["type", "unite"],
    "CapteurData": ["valeur", "timestamp"],
    "Alerte": [
        "type",
        "message",
        "niveau_severite",
        "status",
        "timestamp",
        "first_seen",
        "last_seen",
        "notification_count",
        "acknowledged_at",
        "resolved_at",
    ],
    "Technicien": ["nom", "email", "telephone"],
    "TechnicienStation": ["role", "is_active", "assigned_at"],
    "Maintenance": ["type", "description", "status", "date_planifiee", "date_realisee"],
}

MODEL_OPERATIONS = {
    "Utilisateur": ["+__str__() : String"],
    "UtilisateurManager": [
        "+create_user(pseudo, email, password) : Utilisateur",
        "+create_superuser(pseudo, email, password) : Utilisateur",
    ],
    "ProfilUtilisateur": ["+__str__() : String"],
    "Role": ["+__str__() : String"],
    "UtilisateurRole": ["+__str__() : String"],
    "Station": ["+__str__() : String"],
    "Borne": [
        "+__str__() : String",
        "+{static} default_for_station(station) : Borne",
    ],
    "Emplacement": [
        "+__str__() : String",
        "+save() : void",
    ],
    "Technicien": ["+__str__() : String"],
    "TechnicienStation": ["+__str__() : String"],
}

FIELD_TYPE_MAP = {
    models.UUIDField: "UUID",
    models.CharField: "String",
    models.EmailField: "Email",
    models.TextField: "Text",
    models.DateTimeField: "DateTime",
    models.BooleanField: "Boolean",
    models.PositiveIntegerField: "Integer",
    models.PositiveSmallIntegerField: "Integer",
    models.IntegerField: "Integer",
    models.FloatField: "Float",
    models.JSONField: "JSON",
    models.GenericIPAddressField: "IPAddress",
    models.URLField: "URL",
}


def model_name(model: type[models.Model]) -> str:
    return model.__name__


def field_type(model: type[models.Model], field: models.Field) -> str:
    choice_type = CHOICE_TYPES.get((model_name(model), field.name))
    if choice_type:
        return choice_type
    for django_type, uml_type in FIELD_TYPE_MAP.items():
        if isinstance(field, django_type):
            return uml_type
    return field.__class__.__name__.removesuffix("Field")


def scalar_fields(model: type[models.Model]) -> list[models.Field]:
    wanted = DISPLAY_FIELDS.get(model_name(model))
    fields = [
        field
        for field in model._meta.fields
        if not isinstance(field, (models.ForeignKey, models.OneToOneField))
        and not field.primary_key
        and not field.name.startswith("id_")
    ]
    if wanted is None:
        return fields
    by_name = {field.name: field for field in fields}
    return [by_name[name] for name in wanted if name in by_name]


def relation_fields(model: type[models.Model]) -> list[models.Field]:
    return [
        field
        for field in model._meta.fields
        if isinstance(field, (models.ForeignKey, models.OneToOneField))
    ]


def class_block(model: type[models.Model]) -> list[str]:
    lines = [f"class {model_name(model)} <<Django model>> {{"]
    for field in scalar_fields(model):
        nullable = "?" if getattr(field, "null", False) or getattr(field, "blank", False) else ""
        name = "password_hash" if field.name == "password" else field.name
        lines.append(f"  +{name} : {field_type(model, field)}{nullable}")
    operations = MODEL_OPERATIONS.get(model_name(model), [])
    if operations:
        lines.append("  --")
        lines.extend(f"  {operation}" for operation in operations)
    lines.append("}")
    return lines


def enum_block(enum_cls: type[models.TextChoices]) -> list[str]:
    lines = [f"enum {enum_cls.__name__} {{"]
    for member_name in enum_cls.__members__:
        lines.append(f"  {member_name}")
    lines.append("}")
    return lines


def relation_line(
    target: type[models.Model],
    source: type[models.Model],
    field: models.Field,
) -> str:
    target_name = model_name(target)
    source_name = model_name(source)
    source_multiplicity = "0..1" if isinstance(field, models.OneToOneField) else "0..*"
    target_multiplicity = "0..1" if getattr(field, "null", False) else "1"
    operator = "*--" if (target_name, source_name, field.name) in COMPOSITIONS else "--"
    label = field.remote_field.related_name or field.name
    return (
        f'{target_name} "{target_multiplicity}" '
        f'{operator} "{source_multiplicity}" {source_name} : {label}'
    )


def puml_for(diagram: Diagram) -> str:
    included = {model_name(model): model for model in diagram.models}
    lines = [
        "@startuml",
        "' Generated from backend/api/models.py",
        "!pragma layout smetana",
        "skinparam backgroundColor #F8FAFC",
        "skinparam dpi 160",
        "skinparam shadowing false",
        "skinparam roundcorner 10",
        "skinparam linetype ortho",
        "skinparam classAttributeIconSize 0",
        "skinparam class {",
        "  BackgroundColor #FFFFFF",
        "  BorderColor #CBD5E1",
        "  FontColor #0F172A",
        "  HeaderBackgroundColor #0F766E",
        "  HeaderFontColor #FFFFFF",
        "}",
        "hide circle",
        diagram.direction,
        "",
        f"' {diagram.title}",
        "",
    ]

    for model in diagram.models:
        lines.extend(class_block(model))
        lines.append("")

    for enum_cls in diagram.enums:
        lines.extend(enum_block(enum_cls))
        lines.append("")

    rendered_relations: set[str] = set()
    for source in diagram.models:
        for field in relation_fields(source):
            target = field.remote_field.model
            if not isinstance(target, type) or target.__name__ not in included:
                continue
            line = relation_line(target, source, field)
            if line not in rendered_relations:
                lines.append(line)
                rendered_relations.add(line)

    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def write_puml_files() -> list[Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for diagram in DIAGRAMS:
        path = OUTPUT_DIR / f"{diagram.file_stem}.puml"
        path.write_text(puml_for(diagram), encoding="utf-8")
        generated.append(path)
        print(f"Generated {path}")
    return generated


def resolve_plantuml_runner(plantuml_jar: str | None) -> list[str] | None:
    if plantuml_jar:
        return ["java", "-jar", plantuml_jar]
    env_jar = os.environ.get("PLANTUML_JAR")
    if env_jar:
        return ["java", "-jar", env_jar]
    command = shutil.which("plantuml")
    if command:
        return [command]
    return None


def render_png(puml_files: list[Path], runner: list[str] | None) -> None:
    if runner is None:
        print("PlantUML not found. PUML files were generated, PNG rendering was skipped.")
        print("Set PLANTUML_JAR or install the plantuml command to render images.")
        return
    command = [*runner, "-tpng", *[str(path) for path in puml_files]]
    subprocess.run(command, cwd=ROOT, check=True)
    for path in puml_files:
        print(f"Rendered {path.with_suffix('.png')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate PlantUML class diagrams from Django models.")
    parser.add_argument("--plantuml-jar", help="Path to plantuml.jar. Overrides PLANTUML_JAR.")
    args = parser.parse_args()

    puml_files = write_puml_files()
    render_png(puml_files, resolve_plantuml_runner(args.plantuml_jar))


if __name__ == "__main__":
    main()
