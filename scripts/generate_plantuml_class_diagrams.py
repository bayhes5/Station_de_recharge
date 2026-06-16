from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DBML_PATH = ROOT / "docs" / "source" / "_static" / "dbdiagram" / "station_recharge.dbml"
OUTPUT_DIR = ROOT / "docs" / "source" / "_static" / "uml"

TABLE_RE = re.compile(r"^Table\s+(\w+)\s+\{")
FIELD_RE = re.compile(r"^\s*([A-Za-z_][\w]*)\s+([A-Za-z0-9_()]+)(?:\s+(\[.*\]))?")


@dataclass(frozen=True)
class Field:
    name: str
    type_: str
    attrs: str


@dataclass(frozen=True)
class Table:
    name: str
    fields: list[Field]


@dataclass(frozen=True)
class Relation:
    source: str
    source_multiplicity: str
    target: str
    target_multiplicity: str
    label: str = ""
    color: str = "#2563eb"


@dataclass(frozen=True)
class Diagram:
    title: str
    file_stem: str
    tables: list[str]
    relations: list[Relation]
    left_to_right: bool = True


DIAGRAMS = [
    Diagram(
        title="Identités et accès",
        file_stem="uml_identites_acces",
        tables=[
            "utilisateur",
            "profil_utilisateur",
            "role",
            "utilisateur_role",
            "consentement",
            "journal_securite",
            "type_auth",
            "auth_method",
        ],
        relations=[
            Relation("utilisateur", "1", "profil_utilisateur", "0..1", "profil", "#047857"),
            Relation("utilisateur", "1", "utilisateur_role", "0..*", "rôles", "#047857"),
            Relation("role", "1", "utilisateur_role", "0..*", "attribution", "#047857"),
            Relation("utilisateur", "1", "consentement", "0..*", "consentements", "#047857"),
            Relation("utilisateur", "1", "journal_securite", "0..*", "audit", "#047857"),
            Relation("utilisateur", "1", "auth_method", "0..*", "moyens d'accès", "#047857"),
            Relation("type_auth", "1", "auth_method", "0..*", "classement", "#047857"),
        ],
    ),
    Diagram(
        title="Infrastructure, réservation et supervision",
        file_stem="uml_infrastructure_charge",
        tables=[
            "station",
            "borne",
            "emplacement",
            "device",
            "capteur",
            "capteur_data",
            "device_command_log",
            "reservation",
            "charging_session",
            "session_telemetry",
            "alerte",
        ],
        relations=[
            Relation("station", "1", "borne", "0..*", "contient", "#1d4ed8"),
            Relation("borne", "1", "emplacement", "0..*", "contient", "#1d4ed8"),
            Relation("emplacement", "1", "device", "0..1", "piloté par", "#1d4ed8"),
            Relation("device", "1", "capteur", "0..*", "expose", "#1d4ed8"),
            Relation("capteur", "1", "capteur_data", "0..*", "mesure", "#1d4ed8"),
            Relation("device", "1", "device_command_log", "0..*", "ACK MQTT", "#1d4ed8"),
            Relation("emplacement", "1", "reservation", "0..*", "réservé", "#b45309"),
            Relation("reservation", "1", "charging_session", "0..1", "ouvre", "#b45309"),
            Relation("emplacement", "1", "charging_session", "0..*", "utilisé", "#b45309"),
            Relation("charging_session", "1", "session_telemetry", "0..*", "télémétrie", "#b45309"),
            Relation("charging_session", "0..1", "alerte", "0..*", "incident", "#b45309"),
            Relation("capteur_data", "0..1", "alerte", "0..*", "déclenche", "#b45309"),
        ],
    ),
    Diagram(
        title="Maintenance et exploitation",
        file_stem="uml_maintenance_exploitation",
        tables=[
            "utilisateur",
            "technicien",
            "station",
            "technicien_station",
            "maintenance",
            "alerte",
        ],
        relations=[
            Relation("utilisateur", "0..1", "technicien", "0..1", "compte", "#7c3aed"),
            Relation("technicien", "1", "technicien_station", "0..*", "périmètre", "#7c3aed"),
            Relation("station", "1", "technicien_station", "0..*", "affectation", "#7c3aed"),
            Relation("technicien", "1", "maintenance", "0..*", "réalise", "#7c3aed"),
            Relation("station", "1", "maintenance", "0..*", "intervention", "#7c3aed"),
            Relation("technicien", "0..1", "alerte", "0..*", "prise en charge", "#b45309"),
        ],
    ),
]


def parse_dbml(path: Path) -> dict[str, Table]:
    tables: dict[str, Table] = {}
    current_name: str | None = None
    current_fields: list[Field] = []
    in_indexes = False

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        match = TABLE_RE.match(line)
        if match:
            current_name = match.group(1)
            current_fields = []
            in_indexes = False
            continue
        if current_name is None:
            continue
        stripped = line.strip()
        if stripped == "}":
            if in_indexes:
                in_indexes = False
                continue
            tables[current_name] = Table(current_name, current_fields)
            current_name = None
            continue
        if stripped.startswith("indexes"):
            in_indexes = True
            continue
        if in_indexes or not stripped:
            continue
        field = FIELD_RE.match(line)
        if field:
            current_fields.append(Field(field.group(1), field.group(2), field.group(3) or ""))

    return tables


def field_marker(field: Field) -> str:
    if "pk" in field.attrs:
        return "<<PK>>"
    if "ref:" in field.attrs:
        return "<<FK>>"
    return ""


def class_block(table: Table) -> list[str]:
    lines = [f"class {table.name} {{"]
    pk_fields = [field for field in table.fields if "pk" in field.attrs]
    fk_fields = [field for field in table.fields if "ref:" in field.attrs and "pk" not in field.attrs]
    other_fields = [field for field in table.fields if field not in pk_fields and field not in fk_fields]

    for group_index, group in enumerate((pk_fields, fk_fields, other_fields)):
        if group_index and group:
            lines.append("  --")
        for field in group:
            marker = field_marker(field)
            suffix = f" {marker}" if marker else ""
            lines.append(f"  {field.name} : {field.type_}{suffix}")
    lines.append("}")
    return lines


def puml_for(diagram: Diagram, tables: dict[str, Table]) -> str:
    lines = [
        "@startuml",
        "' Generated from docs/source/_static/dbdiagram/station_recharge.dbml",
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
        "hide methods",
    ]
    if diagram.left_to_right:
        lines.append("left to right direction")
    lines.extend(["", f"' {diagram.title}", ""])

    for table_name in diagram.tables:
        table = tables.get(table_name)
        if not table:
            continue
        lines.extend(class_block(table))
        lines.append("")

    for relation in diagram.relations:
        label = f" : {relation.label}" if relation.label else ""
        lines.append(
            f"{relation.source} \"{relation.source_multiplicity}\" "
            f"-[{relation.color}]- \"{relation.target_multiplicity}\" {relation.target}{label}"
        )

    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def write_puml_files(tables: dict[str, Table]) -> list[Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for diagram in DIAGRAMS:
        path = OUTPUT_DIR / f"{diagram.file_stem}.puml"
        path.write_text(puml_for(diagram, tables), encoding="utf-8")
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
    parser = argparse.ArgumentParser(description="Generate PlantUML class diagrams from the DBML schema.")
    parser.add_argument("--plantuml-jar", help="Path to plantuml.jar. Overrides PLANTUML_JAR.")
    args = parser.parse_args()

    tables = parse_dbml(DBML_PATH)
    puml_files = write_puml_files(tables)
    render_png(puml_files, resolve_plantuml_runner(args.plantuml_jar))


if __name__ == "__main__":
    main()
