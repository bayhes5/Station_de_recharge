from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DBML_PATH = ROOT / "docs" / "source" / "_static" / "dbdiagram" / "station_recharge.dbml"
OUTPUT_DIR = ROOT / "docs" / "source" / "_static" / "uml"


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
class Association:
    source: str
    target: str
    source_multiplicity: str
    target_multiplicity: str
    color: str = "#334155"


@dataclass(frozen=True)
class Diagram:
    name: str
    output: str
    canvas: tuple[int, int]
    positions: dict[str, tuple[int, int]]
    associations: list[Association]


TABLE_RE = re.compile(r"^Table\s+(\w+)\s+\{")
FIELD_RE = re.compile(r"^\s*([A-Za-z_][\w]*)\s+([A-Za-z0-9_()]+)(?:\s+(\[.*\]))?")

FONT_DIR = Path("C:/Windows/Fonts")
CLASS_FONT = ImageFont.truetype(str(FONT_DIR / "segoeuib.ttf"), 24)
FIELD_FONT = ImageFont.truetype(str(FONT_DIR / "segoeui.ttf"), 17)
FIELD_BOLD_FONT = ImageFont.truetype(str(FONT_DIR / "segoeuib.ttf"), 17)
MULTIPLICITY_FONT = ImageFont.truetype(str(FONT_DIR / "segoeuib.ttf"), 18)

CARD_WIDTH = 520
HEADER_HEIGHT = 54
ROW_HEIGHT = 28
PADDING_Y = 18


DIAGRAMS = [
    Diagram(
        name="Identités et moyens d'accès",
        output="uml_identites_acces.png",
        canvas=(2400, 1650),
        positions={
            "utilisateur": (90, 90),
            "profil_utilisateur": (720, 90),
            "role": (90, 700),
            "utilisateur_role": (720, 700),
            "consentement": (1350, 90),
            "journal_securite": (1350, 470),
            "type_auth": (1350, 860),
            "auth_method": (720, 1080),
        },
        associations=[
            Association("utilisateur", "profil_utilisateur", "1", "0..1", "#047857"),
            Association("utilisateur", "utilisateur_role", "1", "0..*", "#047857"),
            Association("role", "utilisateur_role", "1", "0..*", "#047857"),
            Association("utilisateur", "consentement", "1", "0..*", "#047857"),
            Association("utilisateur", "journal_securite", "1", "0..*", "#047857"),
            Association("utilisateur", "auth_method", "1", "0..*", "#047857"),
            Association("type_auth", "auth_method", "1", "0..*", "#047857"),
        ],
    ),
    Diagram(
        name="Infrastructure, réservation et supervision",
        output="uml_infrastructure_charge.png",
        canvas=(3150, 2350),
        positions={
            "station": (90, 90),
            "borne": (730, 90),
            "emplacement": (1370, 90),
            "device": (2010, 90),
            "capteur": (730, 850),
            "capteur_data": (1370, 850),
            "device_command_log": (2010, 1020),
            "reservation": (90, 1540),
            "charging_session": (730, 1540),
            "session_telemetry": (1370, 1540),
            "alerte": (2010, 1540),
        },
        associations=[
            Association("station", "borne", "1", "0..*", "#1d4ed8"),
            Association("borne", "emplacement", "1", "0..*", "#1d4ed8"),
            Association("emplacement", "device", "1", "0..1", "#1d4ed8"),
            Association("device", "capteur", "1", "0..*", "#1d4ed8"),
            Association("capteur", "capteur_data", "1", "0..*", "#1d4ed8"),
            Association("device", "device_command_log", "1", "0..*", "#1d4ed8"),
            Association("emplacement", "reservation", "1", "0..*", "#b45309"),
            Association("reservation", "charging_session", "1", "0..1", "#b45309"),
            Association("emplacement", "charging_session", "1", "0..*", "#b45309"),
            Association("charging_session", "session_telemetry", "1", "0..*", "#b45309"),
            Association("charging_session", "alerte", "0..1", "0..*", "#b45309"),
            Association("capteur_data", "alerte", "0..1", "0..*", "#b45309"),
        ],
    ),
    Diagram(
        name="Maintenance et exploitation",
        output="uml_maintenance_exploitation.png",
        canvas=(2400, 1500),
        positions={
            "utilisateur": (90, 90),
            "technicien": (720, 90),
            "station": (1350, 90),
            "technicien_station": (720, 720),
            "maintenance": (1350, 720),
            "alerte": (90, 720),
        },
        associations=[
            Association("utilisateur", "technicien", "0..1", "0..1", "#7c3aed"),
            Association("technicien", "technicien_station", "1", "0..*", "#7c3aed"),
            Association("station", "technicien_station", "1", "0..*", "#7c3aed"),
            Association("technicien", "maintenance", "1", "0..*", "#7c3aed"),
            Association("station", "maintenance", "1", "0..*", "#7c3aed"),
            Association("technicien", "alerte", "0..1", "0..*", "#b45309"),
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


def is_pk(field: Field) -> bool:
    return "pk" in field.attrs


def is_fk(field: Field) -> bool:
    return "ref:" in field.attrs


def card_size(table: Table) -> tuple[int, int]:
    return CARD_WIDTH, HEADER_HEIGHT + PADDING_Y + len(table.fields) * ROW_HEIGHT + PADDING_Y


def box_for(diagram: Diagram, table_name: str, tables: dict[str, Table]) -> tuple[int, int, int, int]:
    x, y = diagram.positions[table_name]
    w, h = card_size(tables[table_name])
    return x, y, x + w, y + h


def anchor(box: tuple[int, int, int, int], other: tuple[int, int, int, int]) -> tuple[int, int]:
    x1, y1, x2, y2 = box
    ox1, oy1, ox2, oy2 = other
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    ocx, ocy = (ox1 + ox2) // 2, (oy1 + oy2) // 2
    if abs(ocx - cx) >= abs(ocy - cy):
        return (x2, cy) if ocx > cx else (x1, cy)
    return (cx, y2) if ocy > cy else (cx, y1)


def route(source: tuple[int, int, int, int], target: tuple[int, int, int, int]) -> list[tuple[int, int]]:
    start = anchor(source, target)
    end = anchor(target, source)
    if abs(start[0] - end[0]) >= abs(start[1] - end[1]):
        mid_x = (start[0] + end[0]) // 2
        return [start, (mid_x, start[1]), (mid_x, end[1]), end]
    mid_y = (start[1] + end[1]) // 2
    return [start, (start[0], mid_y), (end[0], mid_y), end]


def draw_multiplicity(draw: ImageDraw.ImageDraw, point: tuple[int, int], neighbor: tuple[int, int], text: str, color: str) -> None:
    dx = neighbor[0] - point[0]
    dy = neighbor[1] - point[1]
    length = max((dx * dx + dy * dy) ** 0.5, 1)
    label_x = int(point[0] + dx / length * 34)
    label_y = int(point[1] + dy / length * 34)
    box = draw.textbbox((label_x, label_y), text, font=MULTIPLICITY_FONT)
    draw.rounded_rectangle((box[0] - 5, box[1] - 3, box[2] + 5, box[3] + 3), radius=7, fill="#ffffff", outline="#cbd5e1")
    draw.text((label_x, label_y), text, font=MULTIPLICITY_FONT, fill=color)


def draw_association(draw: ImageDraw.ImageDraw, source: tuple[int, int, int, int], target: tuple[int, int, int, int], association: Association) -> None:
    points = route(source, target)
    draw.line(points, fill=association.color, width=3, joint="curve")
    draw_multiplicity(draw, points[0], points[1], association.source_multiplicity, association.color)
    draw_multiplicity(draw, points[-1], points[-2], association.target_multiplicity, association.color)


def draw_class(draw: ImageDraw.ImageDraw, table: Table, box: tuple[int, int, int, int]) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle((x1 + 8, y1 + 10, x2 + 8, y2 + 10), radius=18, fill="#d4dbe6")
    draw.rounded_rectangle((x1, y1, x2, y2), radius=18, fill="#ffffff", outline="#cbd5e1", width=2)
    draw.rounded_rectangle((x1, y1, x2, y1 + HEADER_HEIGHT), radius=18, fill="#0f766e")
    draw.rectangle((x1, y1 + 34, x2, y1 + HEADER_HEIGHT), fill="#0f766e")
    draw.text((x1 + 18, y1 + 15), table.name, font=CLASS_FONT, fill="#ffffff")
    draw.line((x1, y1 + HEADER_HEIGHT, x2, y1 + HEADER_HEIGHT), fill="#cbd5e1", width=2)

    y = y1 + HEADER_HEIGHT + PADDING_Y
    for field in table.fields:
        marker = "PK" if is_pk(field) else "FK" if is_fk(field) else "  "
        marker_color = "#0f766e" if marker == "PK" else "#2563eb" if marker == "FK" else "#94a3b8"
        draw.text((x1 + 18, y), marker, font=FIELD_BOLD_FONT, fill=marker_color)
        font = FIELD_BOLD_FONT if marker.strip() else FIELD_FONT
        text = f"{field.name}: {field.type_}"
        draw.text((x1 + 72, y), text, font=font, fill="#0f172a" if marker == "PK" else "#1e3a8a" if marker == "FK" else "#334155")
        y += ROW_HEIGHT


def render_diagram(diagram: Diagram, tables: dict[str, Table]) -> None:
    image = Image.new("RGB", diagram.canvas, "#f8fafc")
    draw = ImageDraw.Draw(image)
    boxes = {name: box_for(diagram, name, tables) for name in diagram.positions if name in tables}

    for association in diagram.associations:
        if association.source in boxes and association.target in boxes:
            draw_association(draw, boxes[association.source], boxes[association.target], association)

    for table_name in diagram.positions:
        if table_name in tables:
            draw_class(draw, tables[table_name], boxes[table_name])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / diagram.output
    image.save(output_path, quality=96)
    print(f"Generated {output_path}")


def main() -> None:
    tables = parse_dbml(DBML_PATH)
    for diagram in DIAGRAMS:
        render_diagram(diagram, tables)


if __name__ == "__main__":
    main()
