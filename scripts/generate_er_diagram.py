from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DBML_PATH = ROOT / "docs" / "source" / "_static" / "dbdiagram" / "station_recharge.dbml"
OUTPUT_PATH = ROOT / "docs" / "source" / "_static" / "dbdiagram" / "station_recharge_er.png"


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
class RelationSpec:
    source: str
    target: str
    label: str
    color: str
    lane: str = "auto"


TABLE_RE = re.compile(r"^Table\s+(\w+)\s+\{")
FIELD_RE = re.compile(r"^\s*([A-Za-z_][\w]*)\s+([A-Za-z0-9_()]+)(?:\s+(\[.*\]))?")


CANVAS_WIDTH = 4700
CANVAS_HEIGHT = 3000
SCALE = 1
CARD_WIDTH = 640
HEADER_HEIGHT = 62
ROW_HEIGHT = 31


FONT_DIR = Path("C:/Windows/Fonts")
TITLE_FONT = ImageFont.truetype(str(FONT_DIR / "segoeuib.ttf"), 58)
SUBTITLE_FONT = ImageFont.truetype(str(FONT_DIR / "segoeui.ttf"), 26)
DOMAIN_FONT = ImageFont.truetype(str(FONT_DIR / "segoeuib.ttf"), 29)
HEADER_FONT = ImageFont.truetype(str(FONT_DIR / "segoeuib.ttf"), 26)
FIELD_FONT = ImageFont.truetype(str(FONT_DIR / "segoeui.ttf"), 18)
FIELD_BOLD_FONT = ImageFont.truetype(str(FONT_DIR / "segoeuib.ttf"), 18)
SMALL_FONT = ImageFont.truetype(str(FONT_DIR / "segoeui.ttf"), 15)
SMALL_BOLD_FONT = ImageFont.truetype(str(FONT_DIR / "segoeuib.ttf"), 15)
FOOTER_FONT = ImageFont.truetype(str(FONT_DIR / "segoeui.ttf"), 18)


DOMAINS = {
    "Identités et accès": {
        "tables": [
            "utilisateur",
            "profil_utilisateur",
            "role",
            "utilisateur_role",
            "consentement",
            "journal_securite",
            "type_auth",
            "auth_method",
        ],
        "color": "#047857",
        "fill": "#eaf8f1",
    },
    "Infrastructure IoT": {
        "tables": [
            "station",
            "borne",
            "emplacement",
            "device",
            "capteur",
            "capteur_data",
            "device_command_log",
        ],
        "color": "#1d4ed8",
        "fill": "#edf5ff",
    },
    "Réservation et supervision": {
        "tables": [
            "reservation",
            "charging_session",
            "session_telemetry",
            "alerte",
        ],
        "color": "#b45309",
        "fill": "#fff7e6",
    },
    "Maintenance": {
        "tables": [
            "technicien",
            "technicien_station",
            "maintenance",
        ],
        "color": "#7c3aed",
        "fill": "#f5f0ff",
    },
}


POSITIONS = {
    # Identités et accès.
    "utilisateur": (90, 180),
    "profil_utilisateur": (820, 180),
    "role": (90, 760),
    "utilisateur_role": (820, 760),
    "consentement": (90, 1060),
    "journal_securite": (820, 1060),
    "type_auth": (90, 1390),
    "auth_method": (820, 1390),
    # Infrastructure IoT.
    "station": (1640, 180),
    "borne": (2360, 180),
    "emplacement": (3080, 180),
    "device": (3800, 180),
    "capteur": (2360, 1080),
    "capteur_data": (3080, 1080),
    "device_command_log": (3800, 1080),
    # Réservations et supervision.
    "reservation": (1640, 1760),
    "charging_session": (2360, 1760),
    "session_telemetry": (3080, 1760),
    "alerte": (3800, 1700),
    # Maintenance.
    "technicien": (1640, 2560),
    "technicien_station": (2360, 2560),
    "maintenance": (3080, 2560),
}


RELATIONS = [
    RelationSpec("profil_utilisateur", "utilisateur", "1-1", "#047857"),
    RelationSpec("utilisateur_role", "utilisateur", "N-1", "#047857"),
    RelationSpec("utilisateur_role", "role", "N-1", "#047857"),
    RelationSpec("consentement", "utilisateur", "N-1", "#047857"),
    RelationSpec("journal_securite", "utilisateur", "N-1", "#047857"),
    RelationSpec("auth_method", "utilisateur", "N-1", "#047857"),
    RelationSpec("auth_method", "type_auth", "N-1", "#047857"),
    RelationSpec("borne", "station", "N-1", "#1d4ed8"),
    RelationSpec("emplacement", "borne", "N-1", "#1d4ed8"),
    RelationSpec("emplacement", "station", "N-1", "#1d4ed8", "up"),
    RelationSpec("device", "emplacement", "1-1", "#1d4ed8"),
    RelationSpec("capteur", "device", "N-1", "#1d4ed8"),
    RelationSpec("capteur_data", "capteur", "N-1", "#1d4ed8"),
    RelationSpec("device_command_log", "device", "N-1", "#1d4ed8"),
    RelationSpec("device_command_log", "charging_session", "N-1", "#1d4ed8", "left"),
    RelationSpec("reservation", "utilisateur", "N-1", "#b45309", "left"),
    RelationSpec("reservation", "emplacement", "N-1", "#b45309", "up"),
    RelationSpec("reservation", "auth_method", "N-1", "#b45309", "left"),
    RelationSpec("charging_session", "reservation", "1-1", "#b45309"),
    RelationSpec("charging_session", "emplacement", "N-1", "#b45309", "up"),
    RelationSpec("session_telemetry", "charging_session", "N-1", "#b45309"),
    RelationSpec("alerte", "charging_session", "N-1", "#b45309"),
    RelationSpec("alerte", "capteur_data", "N-1", "#b45309", "up"),
    RelationSpec("alerte", "technicien", "N-1", "#b45309", "left"),
    RelationSpec("technicien", "utilisateur", "0-1", "#7c3aed", "left"),
    RelationSpec("technicien_station", "technicien", "N-1", "#7c3aed"),
    RelationSpec("technicien_station", "station", "N-1", "#7c3aed", "up"),
    RelationSpec("maintenance", "station", "N-1", "#7c3aed", "up"),
    RelationSpec("maintenance", "technicien", "N-1", "#7c3aed"),
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


def domain_for_table(name: str) -> dict[str, object]:
    for config in DOMAINS.values():
        if name in config["tables"]:
            return config
    return {"color": "#334155", "fill": "#f8fafc"}


def is_pk(field: Field) -> bool:
    return "pk" in field.attrs


def is_fk(field: Field) -> bool:
    return "ref:" in field.attrs


def fields_for_table(table: Table) -> list[Field]:
    return table.fields


def table_size(table: Table) -> tuple[int, int]:
    field_count = len(fields_for_table(table))
    return CARD_WIDTH, HEADER_HEIGHT + 22 + field_count * ROW_HEIGHT + 28


def box_for(table_name: str, tables: dict[str, Table]) -> tuple[int, int, int, int]:
    x, y = POSITIONS[table_name]
    w, h = table_size(tables[table_name])
    return x, y, x + w, y + h


def anchor(box: tuple[int, int, int, int], side: str) -> tuple[int, int]:
    x1, y1, x2, y2 = box
    if side == "left":
        return x1, (y1 + y2) // 2
    if side == "right":
        return x2, (y1 + y2) // 2
    if side == "top":
        return (x1 + x2) // 2, y1
    return (x1 + x2) // 2, y2


def relation_points(source: tuple[int, int, int, int], target: tuple[int, int, int, int], lane: str) -> list[tuple[int, int]]:
    sx1, sy1, sx2, sy2 = source
    tx1, ty1, tx2, ty2 = target
    scx, scy = (sx1 + sx2) // 2, (sy1 + sy2) // 2
    tcx, tcy = (tx1 + tx2) // 2, (ty1 + ty2) // 2

    if lane == "up":
        start = anchor(source, "top")
        end = anchor(target, "bottom" if scy > tcy else "top")
        mid_y = min(start[1], end[1]) - 44
        return [start, (start[0], mid_y), (end[0], mid_y), end]
    if lane == "left":
        start = anchor(source, "left")
        end = anchor(target, "right" if scx > tcx else "left")
        mid_x = min(start[0], end[0]) - 64
        return [start, (mid_x, start[1]), (mid_x, end[1]), end]

    if abs(scx - tcx) >= abs(scy - tcy):
        start = anchor(source, "right" if scx < tcx else "left")
        end = anchor(target, "left" if scx < tcx else "right")
        mid_x = (start[0] + end[0]) // 2
        return [start, (mid_x, start[1]), (mid_x, end[1]), end]

    start = anchor(source, "bottom" if scy < tcy else "top")
    end = anchor(target, "top" if scy < tcy else "bottom")
    mid_y = (start[1] + end[1]) // 2
    return [start, (start[0], mid_y), (end[0], mid_y), end]


def draw_relation_line(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], color: str) -> None:
    draw.line(points, fill=color, width=3, joint="curve")


def relation_cardinalities(label: str) -> tuple[str, str]:
    if label == "0-1":
        return "0..1", "1"
    if "-" in label:
        left, right = label.split("-", 1)
        return left, right
    return label, label


def unit_vector(from_point: tuple[int, int], to_point: tuple[int, int]) -> tuple[float, float]:
    dx = to_point[0] - from_point[0]
    dy = to_point[1] - from_point[1]
    length = max((dx * dx + dy * dy) ** 0.5, 1)
    return dx / length, dy / length


def offset(point: tuple[int, int], ux: float, uy: float, distance: float) -> tuple[int, int]:
    return int(point[0] + ux * distance), int(point[1] + uy * distance)


def shifted(point: tuple[int, int], ux: float, uy: float, along: float, px: float, py: float, side: float) -> tuple[int, int]:
    return int(point[0] + ux * along + px * side), int(point[1] + uy * along + py * side)


def draw_one_marker(draw: ImageDraw.ImageDraw, endpoint: tuple[int, int], neighbor: tuple[int, int], color: str) -> None:
    ux, uy = unit_vector(endpoint, neighbor)
    px, py = -uy, ux
    center = offset(endpoint, ux, uy, 14)
    start = int(center[0] - px * 13), int(center[1] - py * 13)
    end = int(center[0] + px * 13), int(center[1] + py * 13)
    draw.line([start, end], fill=color, width=4)


def draw_many_marker(draw: ImageDraw.ImageDraw, endpoint: tuple[int, int], neighbor: tuple[int, int], color: str) -> None:
    ux, uy = unit_vector(endpoint, neighbor)
    px, py = -uy, ux
    base = offset(endpoint, ux, uy, 34)
    center_tip = endpoint
    upper_tip = shifted(endpoint, ux, uy, 0, px, py, -16)
    lower_tip = shifted(endpoint, ux, uy, 0, px, py, 16)
    draw.line([base, upper_tip], fill=color, width=4)
    draw.line([base, center_tip], fill=color, width=4)
    draw.line([base, lower_tip], fill=color, width=4)


def draw_optional_marker(draw: ImageDraw.ImageDraw, endpoint: tuple[int, int], neighbor: tuple[int, int], color: str) -> None:
    ux, uy = unit_vector(endpoint, neighbor)
    circle = offset(endpoint, ux, uy, 11)
    radius = 7
    draw.ellipse(
        (circle[0] - radius, circle[1] - radius, circle[0] + radius, circle[1] + radius),
        fill="white",
        outline=color,
        width=3,
    )
    px, py = -uy, ux
    center = offset(endpoint, ux, uy, 30)
    start = int(center[0] - px * 12), int(center[1] - py * 12)
    end = int(center[0] + px * 12), int(center[1] + py * 12)
    draw.line([start, end], fill=color, width=4)


def draw_crowfoot_marker(draw: ImageDraw.ImageDraw, cardinality: str, endpoint: tuple[int, int], neighbor: tuple[int, int], color: str) -> None:
    if cardinality == "N":
        draw_many_marker(draw, endpoint, neighbor, color)
    elif cardinality == "0..1":
        draw_optional_marker(draw, endpoint, neighbor, color)
    else:
        draw_one_marker(draw, endpoint, neighbor, color)


def draw_cardinalities(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[int, int]],
    label: str,
    color: str,
    source_box: tuple[int, int, int, int],
    target_box: tuple[int, int, int, int],
) -> None:
    source_cardinality, target_cardinality = relation_cardinalities(label)
    draw_crowfoot_marker(draw, source_cardinality, points[0], points[1], color)
    draw_crowfoot_marker(draw, target_cardinality, points[-1], points[-2], color)


def draw_domain_backgrounds(draw: ImageDraw.ImageDraw, tables: dict[str, Table]) -> None:
    for domain, config in DOMAINS.items():
        domain_boxes = []
        for table_name in config["tables"]:
            if table_name not in POSITIONS or table_name not in tables:
                continue
            domain_boxes.append(box_for(table_name, tables))

        x1 = min(box[0] for box in domain_boxes) - 34
        y1 = min(box[1] for box in domain_boxes) - 78
        x2 = max(box[2] for box in domain_boxes) + 34
        y2 = max(box[3] for box in domain_boxes) + 42
        draw.rounded_rectangle((x1, y1, x2, y2), radius=32, fill=str(config["fill"]), outline="#dbe4ef", width=2)
        draw.text((x1 + 24, y1 + 20), domain, font=DOMAIN_FONT, fill=str(config["color"]))


def draw_table(draw: ImageDraw.ImageDraw, table: Table, box: tuple[int, int, int, int]) -> None:
    config = domain_for_table(table.name)
    color = str(config["color"])
    x1, y1, x2, y2 = box

    draw.rounded_rectangle((x1 + 8, y1 + 10, x2 + 8, y2 + 10), radius=18, fill="#d1d5db")
    draw.rounded_rectangle((x1, y1, x2, y2), radius=18, fill="white", outline="#cbd5e1", width=2)
    draw.rounded_rectangle((x1, y1, x2, y1 + HEADER_HEIGHT), radius=18, fill=color)
    draw.rectangle((x1, y1 + 32, x2, y1 + HEADER_HEIGHT), fill=color)
    draw.text((x1 + 18, y1 + 14), table.name, font=HEADER_FONT, fill="white")

    y = y1 + HEADER_HEIGHT + 16
    for field in fields_for_table(table):
        tag = "PK" if is_pk(field) else "FK" if is_fk(field) else ""
        tag_color = "#0f766e" if tag == "PK" else "#2563eb" if tag == "FK" else "#f8fafc"
        field_font = FIELD_BOLD_FONT if tag else FIELD_FONT
        field_color = "#0f172a" if tag != "FK" else "#1d4ed8"

        if tag:
            draw.rounded_rectangle((x1 + 16, y + 1, x1 + 52, y + 22), radius=7, fill=tag_color)
            draw.text((x1 + 22, y + 2), tag, font=SMALL_BOLD_FONT, fill="white")
        draw.text((x1 + 64, y), field.name, font=field_font, fill=field_color)
        draw.text((x1 + 430, y), field.type_, font=FIELD_FONT, fill="#64748b")
        y += ROW_HEIGHT


def draw_title(draw: ImageDraw.ImageDraw) -> None:
    draw.text((90, 58), "Schéma entités-relations", font=TITLE_FONT, fill="#064e3b")
    draw.text(
        (92, 124),
        "Station de recharge intelligente - vue de synthèse issue du DBML",
        font=SUBTITLE_FONT,
        fill="#475569",
    )
    draw.line((90, 178, CANVAS_WIDTH - 90, 178), fill="#0f766e", width=4)


def draw_legend(draw: ImageDraw.ImageDraw) -> None:
    x, y, w, h = 90, 2298, 1840, 76
    draw.rounded_rectangle((x, y, x + w, y + h), radius=18, fill="white", outline="#cbd5e1", width=2)
    draw.rounded_rectangle((x + 22, y + 24, x + 58, y + 47), radius=7, fill="#0f766e")
    draw.text((x + 28, y + 25), "PK", font=SMALL_BOLD_FONT, fill="white")
    draw.text((x + 72, y + 25), "clé primaire", font=FOOTER_FONT, fill="#0f172a")
    draw.rounded_rectangle((x + 260, y + 24, x + 296, y + 47), radius=7, fill="#2563eb")
    draw.text((x + 266, y + 25), "FK", font=SMALL_BOLD_FONT, fill="white")
    draw.text((x + 310, y + 25), "clé étrangère", font=FOOTER_FONT, fill="#0f172a")
    draw.text((x + 560, y + 25), "N-1 / 1-1 : cardinalité simplifiée", font=FOOTER_FONT, fill="#0f172a")
    draw.text((x + 1065, y + 25), "Les champs non affichés restent présents dans le DBML.", font=FOOTER_FONT, fill="#475569")
    draw.text((CANVAS_WIDTH - 760, y + 27), "Généré depuis docs/source/_static/dbdiagram/station_recharge.dbml", font=FOOTER_FONT, fill="#64748b")


def main() -> None:
    tables = parse_dbml(DBML_PATH)
    image = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), "#f8fafc")
    draw = ImageDraw.Draw(image)

    draw_domain_backgrounds(draw, tables)

    boxes = {name: box_for(name, tables) for name in POSITIONS if name in tables}

    routed_relations: list[tuple[RelationSpec, list[tuple[int, int]], tuple[int, int, int, int], tuple[int, int, int, int]]] = []
    for relation in RELATIONS:
        if relation.source not in boxes or relation.target not in boxes:
            continue
        source_box = boxes[relation.source]
        target_box = boxes[relation.target]
        points = relation_points(source_box, target_box, relation.lane)
        routed_relations.append((relation, points, source_box, target_box))
        draw_relation_line(draw, points, relation.color)

    for relation, points, source_box, target_box in routed_relations:
        draw_cardinalities(draw, points, relation.label, relation.color, source_box, target_box)

    for table_name in POSITIONS:
        if table_name in tables:
            draw_table(draw, tables[table_name], boxes[table_name])

    output = image.resize((CANVAS_WIDTH * SCALE, CANVAS_HEIGHT * SCALE), Image.Resampling.LANCZOS)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output.save(OUTPUT_PATH, quality=96)
    print(f"Diagram generated: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
