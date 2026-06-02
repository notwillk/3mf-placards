#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


DEFAULTS: dict[str, Any] = {
    "width": 75,
    "aspect_ratio": 2,
    "thickness": 2,
    "backing_thickness": 0.4,
    "border_thickness": 2,
    "border_radius": 5,
    "orientation": "landscape",
    "padding": 2,
    "gap": 1,
    "description": "",
    "qr_code": "",
    "title_typeface": "",
    "title_size": 6,
    "title_alignment": "center",
    "description_typeface": "",
    "description_size": 4,
    "description_line_height": 1.25,
    "description_alignment": "center",
    "description_vertical_alignment": "top",
    "text_color": "#000000",
    "substrate_color": "#FFFFFF",
}

ALLOWED_KEYS = set(DEFAULTS) | {"title"}
NUMERIC_KEYS = {
    "width",
    "aspect_ratio",
    "thickness",
    "backing_thickness",
    "border_thickness",
    "border_radius",
    "padding",
    "gap",
    "title_size",
    "description_size",
    "description_line_height",
}
STRING_KEYS = {
    "title",
    "orientation",
    "description",
    "qr_code",
    "title_typeface",
    "title_alignment",
    "description_typeface",
    "description_alignment",
    "description_vertical_alignment",
    "text_color",
    "substrate_color",
}
ORIENTATIONS = {"landscape", "portrait"}
ALIGNMENTS = {"left", "center", "right"}
VERTICAL_ALIGNMENTS = {"top", "bottom", "center", "centered"}
MODEL_SUBSTRATE_USE = "use <../substrate/model.scad>;"
DIST_SUBSTRATE_USE = "use <substrate.scad>;"
HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")
CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
MATERIAL_NS = "http://schemas.microsoft.com/3dmanufacturing/material/2015/02"
XML_NS = "http://www.w3.org/XML/1998/namespace"
COLOR_GROUP_ID = "1"
TITLE_BLOCK_HEIGHT_FACTOR = 1.25
TEXT_WIDTH_SAFETY_FACTOR = 1.1
QR_TEXT_WIDTH_SAFETY_FACTOR = 1.2
QR_BORDER_MODULES = 4
QR_BACKGROUND_COLOR = "#FFFFFF"
QR_DOT_COLOR = "#000000"


MeshVertices = list[tuple[str, str, str]]
MeshTriangles = list[tuple[int, int, int]]


@dataclass(frozen=True)
class MeshObject:
    name: str
    color_index: int
    vertices: MeshVertices
    triangles: MeshTriangles


class BuildError(ValueError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a title/description placard from flat YAML values."
    )
    parser.add_argument("--values", required=True, type=Path, help="Input YAML file")
    parser.add_argument("--model", required=True, type=Path, help="OpenSCAD model file")
    parser.add_argument("--out-dir", required=True, type=Path, help="Output dist directory")
    parser.add_argument(
        "--substrate-model",
        type=Path,
        help="OpenSCAD substrate model file. Defaults to ../substrate/model.scad.",
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="Write generated SCAD without exporting STL.",
    )
    return parser.parse_args()


def load_values(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return load_flat_yaml(path)

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise BuildError("values YAML must be a flat mapping")
    return data


def load_flat_yaml(path: Path) -> dict[str, Any]:
    values: dict[str, Any] = {}

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise BuildError(f"{path}:{line_number}: expected 'key: value'")

        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = strip_unquoted_comment(raw_value.strip())

        if not key:
            raise BuildError(f"{path}:{line_number}: key cannot be empty")
        if not value:
            values[key] = ""
            continue

        values[key] = parse_scalar(value)

    return values


def strip_unquoted_comment(value: str) -> str:
    in_quote: str | None = None
    escaped = False

    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char in {"'", '"'}:
            if in_quote == char:
                in_quote = None
            elif in_quote is None:
                in_quote = char
            continue
        if char == "#" and in_quote is None and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()

    return value


def parse_scalar(value: str) -> Any:
    if value in {"''", '""'}:
        return ""
    if value[0] in {"'", '"'}:
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError) as exc:
            raise BuildError(f"invalid quoted string {value!r}") from exc

    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"

    try:
        number = float(value)
    except ValueError:
        return value

    if number.is_integer():
        return int(number)
    return number


def plate_dimensions(values: dict[str, Any]) -> tuple[float, float]:
    if values["orientation"] == "portrait":
        return values["width"] / values["aspect_ratio"], values["width"]
    return values["width"], values["width"] / values["aspect_ratio"]


def char_width_factor(char: str) -> float:
    if char.isspace():
        return 0.33
    if char in "ilI1.,:;'!|":
        return 0.35
    if char in "mwMW@#%&":
        return 0.9
    if char.isupper():
        return 0.72
    if char.isdigit():
        return 0.62
    return 0.6


def estimate_text_width(
    text: str,
    size: float,
    safety_factor: float = TEXT_WIDTH_SAFETY_FACTOR,
) -> float:
    return (
        size
        * sum(char_width_factor(char) for char in text)
        * safety_factor
    )


def split_long_word(
    word: str,
    max_width: float,
    size: float,
    safety_factor: float = TEXT_WIDTH_SAFETY_FACTOR,
) -> list[str]:
    chunks: list[str] = []
    current = ""

    for char in word:
        candidate = f"{current}{char}"
        if current and estimate_text_width(candidate, size, safety_factor) > max_width:
            chunks.append(current)
            current = char
        else:
            current = candidate

    if current:
        chunks.append(current)
    return chunks


def append_wrapped_piece(
    lines: list[str],
    current: str,
    piece: str,
    max_width: float,
    size: float,
    safety_factor: float = TEXT_WIDTH_SAFETY_FACTOR,
) -> str:
    if not current:
        return piece

    candidate = f"{current} {piece}"
    if estimate_text_width(candidate, size, safety_factor) <= max_width:
        return candidate

    lines.append(current)
    return piece


def wrap_text_line(
    line: str,
    max_width: float,
    size: float,
    safety_factor: float = TEXT_WIDTH_SAFETY_FACTOR,
) -> list[str]:
    normalized = " ".join(line.split())
    if not normalized:
        return []

    lines: list[str] = []
    current = ""

    for word in normalized.split(" "):
        pieces = (
            split_long_word(word, max_width, size, safety_factor)
            if estimate_text_width(word, size, safety_factor) > max_width
            else [word]
        )

        for piece in pieces:
            current = append_wrapped_piece(
                lines,
                current,
                piece,
                max_width,
                size,
                safety_factor,
            )

    if current:
        lines.append(current)
    return lines


def wrap_text(
    text: str,
    max_width: float,
    size: float,
    safety_factor: float = TEXT_WIDTH_SAFETY_FACTOR,
) -> list[str]:
    physical_lines = [line.strip() for line in text.split("\n")]

    while physical_lines and physical_lines[0] == "":
        physical_lines.pop(0)
    while physical_lines and physical_lines[-1] == "":
        physical_lines.pop()
    if not physical_lines:
        return []

    lines: list[str] = []
    for physical_line in physical_lines:
        if physical_line == "":
            lines.append("")
            continue
        lines.extend(wrap_text_line(physical_line, max_width, size, safety_factor))
    return lines


def generate_qr_modules(qr_code: str) -> tuple[int, list[tuple[int, int]]]:
    try:
        import segno  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise BuildError(
            "qr_code requires the Python segno package; install it with "
            "`uv sync --extra qr` or run the builder with `uv run --extra qr`"
        ) from exc

    try:
        qr = segno.make(qr_code)
        rows = [
            list(row)
            for row in qr.matrix_iter(scale=1, border=QR_BORDER_MODULES)
        ]
    except Exception as exc:
        raise BuildError(f"qr_code could not be encoded as a QR code: {exc}") from exc

    if not rows:
        raise BuildError("qr_code generated an empty QR matrix")

    module_count = len(rows)
    if any(len(row) != module_count for row in rows):
        raise BuildError("qr_code generated a non-square QR matrix")

    modules: list[tuple[int, int]] = []
    for row_index, row in enumerate(rows):
        for column_index, cell in enumerate(row):
            if cell:
                modules.append((column_index, row_index))

    return module_count, modules


def normalize_hex_color(value: str, key: str) -> str:
    if not HEX_COLOR_PATTERN.fullmatch(value):
        raise BuildError(f"{key} must be a hex color like '#000000' or '#000000FF'")
    return f"#{value[1:].upper()}"


def normalize_values(raw_values: dict[str, Any]) -> dict[str, Any]:
    unknown_keys = sorted(set(raw_values) - ALLOWED_KEYS)
    if unknown_keys:
        raise BuildError(f"unknown value key(s): {', '.join(unknown_keys)}")

    values = dict(DEFAULTS)
    values.update(raw_values)

    title = values.get("title")
    if not isinstance(title, str) or not title.strip():
        raise BuildError("title is required and must be a non-empty string")

    for key in STRING_KEYS:
        if not isinstance(values[key], str):
            raise BuildError(f"{key} must be a string")

    values["orientation"] = values["orientation"].lower()
    if values["orientation"] not in ORIENTATIONS:
        raise BuildError("orientation must be 'landscape' or 'portrait'")

    values["title_alignment"] = values["title_alignment"].lower()
    if values["title_alignment"] not in ALIGNMENTS:
        raise BuildError("title_alignment must be 'left', 'center', or 'right'")

    values["description_alignment"] = values["description_alignment"].lower()
    if values["description_alignment"] not in ALIGNMENTS:
        raise BuildError("description_alignment must be 'left', 'center', or 'right'")

    values["description_vertical_alignment"] = values[
        "description_vertical_alignment"
    ].lower()
    if values["description_vertical_alignment"] not in VERTICAL_ALIGNMENTS:
        raise BuildError(
            "description_vertical_alignment must be 'top', 'bottom', or 'center'"
        )
    if values["description_vertical_alignment"] == "centered":
        values["description_vertical_alignment"] = "center"

    values["text_color"] = normalize_hex_color(values["text_color"], "text_color")
    values["substrate_color"] = normalize_hex_color(
        values["substrate_color"],
        "substrate_color",
    )

    for key in NUMERIC_KEYS:
        if isinstance(values[key], bool) or not isinstance(values[key], (int, float)):
            raise BuildError(f"{key} must be numeric")

    if values["width"] <= 0:
        raise BuildError("width must be greater than 0")
    if values["aspect_ratio"] <= 0:
        raise BuildError("aspect_ratio must be greater than 0")
    if values["thickness"] <= 0:
        raise BuildError("thickness must be greater than 0")
    if values["backing_thickness"] <= 0:
        raise BuildError("backing_thickness must be greater than 0")
    if values["backing_thickness"] >= values["thickness"]:
        raise BuildError("backing_thickness must be less than thickness")
    if values["border_thickness"] < 0:
        raise BuildError("border_thickness must be 0 or greater")
    if values["border_radius"] < 0:
        raise BuildError("border_radius must be 0 or greater")
    if values["padding"] < 0:
        raise BuildError("padding must be 0 or greater")
    if values["gap"] < 0:
        raise BuildError("gap must be 0 or greater")
    if values["title_size"] <= 0:
        raise BuildError("title_size must be greater than 0")
    if values["description_size"] <= 0:
        raise BuildError("description_size must be greater than 0")
    if values["description_line_height"] <= 0:
        raise BuildError("description_line_height must be greater than 0")

    plate_width, plate_height = plate_dimensions(values)
    if values["border_radius"] > min(plate_width, plate_height) / 2:
        raise BuildError("border_radius cannot exceed half of the short side")
    if values["border_thickness"] >= min(plate_width, plate_height) / 2:
        raise BuildError("border_thickness must leave a visible interior")

    text_inset = values["border_thickness"] + values["padding"]
    text_width = plate_width - (2 * text_inset)
    text_height = plate_height - (2 * text_inset)
    if text_width <= 0 or text_height <= 0:
        raise BuildError("border_thickness and padding leave no text area")

    title_block_height = values["title_size"] * TITLE_BLOCK_HEIGHT_FACTOR
    available_description_height = text_height - title_block_height - values["gap"]
    has_qr_code = values["qr_code"] != ""
    if has_qr_code:
        if available_description_height <= 0:
            raise BuildError("qr_code does not fit below the title with the current layout")

        description_text_width = (
            text_width - available_description_height - values["gap"]
        )
        if description_text_width <= 0:
            raise BuildError(
                "qr_code leaves no description width with the current layout"
            )

        values["qr_module_count"], values["qr_modules"] = generate_qr_modules(
            values["qr_code"]
        )
    else:
        description_text_width = text_width
        values["qr_module_count"] = 0
        values["qr_modules"] = []

    values["description_text_width"] = description_text_width

    values["description_lines"] = wrap_text(
        values["description"],
        description_text_width,
        values["description_size"],
        QR_TEXT_WIDTH_SAFETY_FACTOR if has_qr_code else TEXT_WIDTH_SAFETY_FACTOR,
    )
    values["description_line_spacing"] = (
        values["description_size"] * values["description_line_height"]
    )

    if values["description_lines"]:
        required_description_height = values["description_size"] + (
            (len(values["description_lines"]) - 1) * values["description_line_spacing"]
        )
        if required_description_height > available_description_height + 0.001:
            raise BuildError("description does not fit below the title with the current layout")

    return values


def scad_string(value: str) -> str:
    return json.dumps(value)


def scad_string_list(values: list[str]) -> str:
    return "[" + ", ".join(scad_string(value) for value in values) + "]"


def scad_int_pair_list(values: list[tuple[int, int]]) -> str:
    return "[" + ", ".join(f"[{left}, {right}]" for left, right in values) + "]"


def scad_number(value: int | float) -> str:
    if isinstance(value, int):
        return str(value)
    if value.is_integer():
        return str(int(value))
    return f"{value:.6g}"


FEATURE_ARGUMENTS = [
    ("placard_width", "width"),
    ("placard_aspect_ratio", "aspect_ratio"),
    ("placard_thickness", "thickness"),
    ("placard_backing_thickness", "backing_thickness"),
    ("placard_border_thickness", "border_thickness"),
    ("placard_border_radius", "border_radius"),
    ("placard_orientation", "orientation"),
    ("placard_padding", "padding"),
    ("placard_gap", "gap"),
    ("placard_title", "title"),
    ("placard_title_typeface", "title_typeface"),
    ("placard_title_size", "title_size"),
    ("placard_title_block_height_factor", "title_block_height_factor"),
    ("placard_title_alignment", "title_alignment"),
    ("placard_description", "description"),
    ("placard_description_typeface", "description_typeface"),
    ("placard_description_size", "description_size"),
    ("placard_description_alignment", "description_alignment"),
    ("placard_description_vertical_alignment", "description_vertical_alignment"),
    ("placard_description_lines", "description_lines"),
    ("placard_description_line_spacing", "description_line_spacing"),
    ("placard_description_text_width", "description_text_width"),
    ("placard_qr_code", "qr_code"),
    ("placard_qr_module_count", "qr_module_count"),
    ("placard_qr_modules", "qr_modules"),
]
FULL_PLACARD_ARGUMENTS = FEATURE_ARGUMENTS + [
    ("placard_text_color", "text_color"),
    ("placard_substrate_color", "substrate_color"),
]
SUBSTRATE_CUT_ARGUMENTS = FEATURE_ARGUMENTS + [
    ("placard_substrate_color", "substrate_color"),
]


def generated_header(model_name: str) -> list[str]:
    return [
        "// Generated by models/placard-title-description/scripts/build.py",
        "// Edit the source YAML values instead of this file.",
        "",
        f"use <{model_name}>;",
        "",
    ]


def value_assignment_lines(values: dict[str, Any]) -> list[str]:
    return [
        f"width = {scad_number(values['width'])};",
        f"aspect_ratio = {scad_number(values['aspect_ratio'])};",
        f"thickness = {scad_number(values['thickness'])};",
        f"backing_thickness = {scad_number(values['backing_thickness'])};",
        f"border_thickness = {scad_number(values['border_thickness'])};",
        f"border_radius = {scad_number(values['border_radius'])};",
        f"orientation = {scad_string(values['orientation'])};",
        f"padding = {scad_number(values['padding'])};",
        f"gap = {scad_number(values['gap'])};",
        f"title = {scad_string(values['title'])};",
        f"title_typeface = {scad_string(values['title_typeface'])};",
        f"title_size = {scad_number(values['title_size'])};",
        f"title_block_height_factor = {scad_number(TITLE_BLOCK_HEIGHT_FACTOR)};",
        f"title_alignment = {scad_string(values['title_alignment'])};",
        f"description = {scad_string(values['description'])};",
        f"description_typeface = {scad_string(values['description_typeface'])};",
        f"description_size = {scad_number(values['description_size'])};",
        f"description_line_height = {scad_number(values['description_line_height'])};",
        f"description_alignment = {scad_string(values['description_alignment'])};",
        f"description_vertical_alignment = {scad_string(values['description_vertical_alignment'])};",
        f"description_lines = {scad_string_list(values['description_lines'])};",
        f"description_line_spacing = {scad_number(values['description_line_spacing'])};",
        f"description_text_width = {scad_number(values['description_text_width'])};",
        f"qr_code = {scad_string(values['qr_code'])};",
        f"qr_module_count = {scad_number(values['qr_module_count'])};",
        f"qr_modules = {scad_int_pair_list(values['qr_modules'])};",
        f"text_color = {scad_string(values['text_color'])};",
        f"substrate_color = {scad_string(values['substrate_color'])};",
    ]


def render_call_arguments(
    arguments: list[tuple[str, str]],
    indent: str = "  ",
) -> list[str]:
    lines: list[str] = []
    for index, (parameter, variable) in enumerate(arguments):
        suffix = "," if index < len(arguments) - 1 else ""
        lines.append(f"{indent}{parameter} = {variable}{suffix}")
    return lines


def write_scad(values: dict[str, Any], model_name: str, out_path: Path) -> None:
    lines = [
        *generated_header(model_name),
        *value_assignment_lines(values),
        "",
        "placard_title_description(",
        *render_call_arguments(FULL_PLACARD_ARGUMENTS),
        ");",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_title_description_scad(
    values: dict[str, Any],
    model_name: str,
    out_path: Path,
) -> None:
    lines = [
        *generated_header(model_name),
        *value_assignment_lines(values),
        "",
        "color(text_color) {",
        "  placard_title_description_body(",
        *render_call_arguments(FEATURE_ARGUMENTS, "    "),
        "  );",
        "}",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_qr_background_scad(
    values: dict[str, Any],
    model_name: str,
    out_path: Path,
) -> None:
    lines = [
        *generated_header(model_name),
        *value_assignment_lines(values),
        "",
        f"color({scad_string(QR_BACKGROUND_COLOR)}) {{",
        "  placard_qr_background(",
        *render_call_arguments(FEATURE_ARGUMENTS, "    "),
        "  );",
        "}",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_qr_dots_scad(
    values: dict[str, Any],
    model_name: str,
    out_path: Path,
) -> None:
    lines = [
        *generated_header(model_name),
        *value_assignment_lines(values),
        "",
        f"color({scad_string(QR_DOT_COLOR)}) {{",
        "  placard_qr_dots(",
        *render_call_arguments(FEATURE_ARGUMENTS, "    "),
        "  );",
        "}",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_substrate_cut_scad(
    values: dict[str, Any],
    model_name: str,
    out_path: Path,
) -> None:
    lines = [
        *generated_header(model_name),
        *value_assignment_lines(values),
        "",
        "placard_substrate_cut(",
        *render_call_arguments(SUBSTRATE_CUT_ARGUMENTS),
        ");",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def resolve_substrate_model_path(model_path: Path, substrate_model: Path | None) -> Path:
    if substrate_model is not None:
        return substrate_model
    return model_path.parent.parent / "substrate" / "model.scad"


def resolve_substrate_model(args: argparse.Namespace) -> Path:
    return resolve_substrate_model_path(args.model, args.substrate_model)


def copy_model_for_dist(model_path: Path, out_path: Path) -> None:
    source = model_path.read_text(encoding="utf-8")
    out_path.write_text(
        source.replace(MODEL_SUBSTRATE_USE, DIST_SUBSTRATE_USE),
        encoding="utf-8",
    )


def unlink_optional_outputs(paths: list[Path]) -> None:
    for path in paths:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def format_mesh_number(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        return "0"
    return text


def parse_ascii_stl(stl_path: Path) -> tuple[MeshVertices, MeshTriangles]:
    vertices: MeshVertices = []
    vertex_indexes: dict[tuple[str, str, str], int] = {}
    triangles: list[tuple[int, int, int]] = []
    triangle_vertices: list[int] = []

    for line_number, raw_line in enumerate(stl_path.read_text(encoding="utf-8").splitlines(), 1):
        parts = raw_line.strip().split()
        if len(parts) != 4 or parts[0] != "vertex":
            continue

        try:
            vertex = tuple(format_mesh_number(float(part)) for part in parts[1:4])
        except ValueError as exc:
            raise BuildError(f"{stl_path}:{line_number}: invalid STL vertex") from exc

        if len(vertex) != 3:
            raise BuildError(f"{stl_path}:{line_number}: invalid STL vertex")

        if vertex not in vertex_indexes:
            vertex_indexes[vertex] = len(vertices)
            vertices.append(vertex)

        triangle_vertices.append(vertex_indexes[vertex])
        if len(triangle_vertices) == 3:
            triangles.append(
                (
                    triangle_vertices[0],
                    triangle_vertices[1],
                    triangle_vertices[2],
                )
            )
            triangle_vertices = []

    if triangle_vertices:
        raise BuildError(f"{stl_path}: incomplete STL triangle")
    if not triangles:
        raise BuildError(f"{stl_path}: exported mesh contains no triangles")

    return vertices, triangles


def core_tag(name: str) -> str:
    return f"{{{CORE_NS}}}{name}"


def material_tag(name: str) -> str:
    return f"{{{MATERIAL_NS}}}{name}"


def add_mesh_object(
    resources: ET.Element,
    object_id: int,
    name: str,
    color_index: int,
    vertices: MeshVertices,
    triangles: MeshTriangles,
) -> None:
    model_object = ET.SubElement(
        resources,
        core_tag("object"),
        {
            "id": str(object_id),
            "name": name,
            "type": "model",
            "pid": COLOR_GROUP_ID,
            "pindex": str(color_index),
        },
    )
    mesh = ET.SubElement(model_object, core_tag("mesh"))
    vertex_container = ET.SubElement(mesh, core_tag("vertices"))
    for x, y, z in vertices:
        ET.SubElement(vertex_container, core_tag("vertex"), {"x": x, "y": y, "z": z})

    triangle_container = ET.SubElement(mesh, core_tag("triangles"))
    for v1, v2, v3 in triangles:
        ET.SubElement(
            triangle_container,
            core_tag("triangle"),
            {
                "v1": str(v1),
                "v2": str(v2),
                "v3": str(v3),
                "pid": COLOR_GROUP_ID,
                "p1": str(color_index),
            },
        )


def content_types_xml() -> bytes:
    return (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        b'<Default Extension="rels" '
        b'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        b'<Default Extension="model" '
        b'ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
        b"</Types>\n"
    )


def relationships_xml() -> bytes:
    return (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<Relationships '
        b'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Target="/3D/3dmodel.model" Id="rel0" '
        b'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        b"</Relationships>\n"
    )


def model_xml(mesh_objects: list[MeshObject], color_values: list[str]) -> bytes:
    ET.register_namespace("", CORE_NS)
    ET.register_namespace("m", MATERIAL_NS)

    model = ET.Element(
        core_tag("model"),
        {
            "unit": "millimeter",
            "recommendedextensions": "m",
            f"{{{XML_NS}}}lang": "en-US",
        },
    )
    resources = ET.SubElement(model, core_tag("resources"))
    color_group = ET.SubElement(
        resources,
        material_tag("colorgroup"),
        {"id": COLOR_GROUP_ID},
    )
    for color in color_values:
        ET.SubElement(color_group, material_tag("color"), {"color": color})

    for offset, mesh_object in enumerate(mesh_objects):
        add_mesh_object(
            resources,
            2 + offset,
            mesh_object.name,
            mesh_object.color_index,
            mesh_object.vertices,
            mesh_object.triangles,
        )

    build = ET.SubElement(model, core_tag("build"))
    for offset, _mesh_object in enumerate(mesh_objects):
        ET.SubElement(build, core_tag("item"), {"objectid": str(2 + offset)})

    if hasattr(ET, "indent"):
        ET.indent(model)

    return ET.tostring(model, encoding="utf-8", xml_declaration=True)


def write_3mf(
    text_stl_path: Path,
    substrate_stl_path: Path,
    three_mf_path: Path,
    text_color: str,
    substrate_color: str,
    qr_stl_paths: tuple[Path, Path] | None = None,
) -> None:
    text_vertices, text_triangles = parse_ascii_stl(text_stl_path)
    substrate_vertices, substrate_triangles = parse_ascii_stl(substrate_stl_path)
    mesh_objects = [
        MeshObject("title-description", 0, text_vertices, text_triangles),
    ]
    colors = [text_color, substrate_color]

    if qr_stl_paths is not None:
        qr_background_vertices, qr_background_triangles = parse_ascii_stl(qr_stl_paths[0])
        qr_dots_vertices, qr_dots_triangles = parse_ascii_stl(qr_stl_paths[1])
        colors.extend([QR_BACKGROUND_COLOR, QR_DOT_COLOR])
        mesh_objects.extend(
            [
                MeshObject(
                    "qr-background",
                    2,
                    qr_background_vertices,
                    qr_background_triangles,
                ),
                MeshObject("qr-dots", 3, qr_dots_vertices, qr_dots_triangles),
            ]
        )

    mesh_objects.append(MeshObject("substrate", 1, substrate_vertices, substrate_triangles))

    with zipfile.ZipFile(three_mf_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml())
        archive.writestr("_rels/.rels", relationships_xml())
        archive.writestr("3D/3dmodel.model", model_xml(mesh_objects, colors))


def export_stl(scad_path: Path, stl_path: Path) -> None:
    openscad = shutil.which("openscad")
    if openscad is None:
        raise BuildError("openscad is required to export STL, but it was not found in PATH")

    subprocess.run(
        [openscad, "--export-format", "asciistl", "-o", str(stl_path), str(scad_path)],
        check=True,
    )


def build_placard(
    raw_values: dict[str, Any],
    model_path: Path,
    out_dir: Path,
    substrate_model: Path | None = None,
    skip_export: bool = False,
) -> dict[str, Any]:
    values = normalize_values(raw_values)
    resolved_substrate_model = resolve_substrate_model_path(model_path, substrate_model)

    out_dir.mkdir(parents=True, exist_ok=True)
    model_out = out_dir / "model.scad"
    substrate_out = out_dir / "substrate.scad"
    scad_out = out_dir / "placard.scad"
    text_scad_out = out_dir / "title-description.scad"
    qr_background_scad_out = out_dir / "qr-background.scad"
    qr_dots_scad_out = out_dir / "qr-dots.scad"
    substrate_cut_scad_out = out_dir / "substrate-cut.scad"
    stl_out = out_dir / "placard.stl"
    text_stl_out = out_dir / "title-description.stl"
    qr_background_stl_out = out_dir / "qr-background.stl"
    qr_dots_stl_out = out_dir / "qr-dots.stl"
    substrate_cut_stl_out = out_dir / "substrate-cut.stl"
    three_mf_out = out_dir / "placard.3mf"
    qr_outputs = [
        qr_background_scad_out,
        qr_dots_scad_out,
        qr_background_stl_out,
        qr_dots_stl_out,
    ]

    copy_model_for_dist(model_path, model_out)
    shutil.copyfile(resolved_substrate_model, substrate_out)
    write_scad(values, model_out.name, scad_out)
    write_title_description_scad(values, model_out.name, text_scad_out)
    if values["qr_code"] != "":
        write_qr_background_scad(values, model_out.name, qr_background_scad_out)
        write_qr_dots_scad(values, model_out.name, qr_dots_scad_out)
    else:
        unlink_optional_outputs(qr_outputs)
    write_substrate_cut_scad(values, model_out.name, substrate_cut_scad_out)

    if not skip_export:
        export_stl(scad_out, stl_out)
        export_stl(text_scad_out, text_stl_out)
        qr_stl_paths = None
        if values["qr_code"] != "":
            export_stl(qr_background_scad_out, qr_background_stl_out)
            export_stl(qr_dots_scad_out, qr_dots_stl_out)
            qr_stl_paths = (qr_background_stl_out, qr_dots_stl_out)
        export_stl(substrate_cut_scad_out, substrate_cut_stl_out)
        write_3mf(
            text_stl_out,
            substrate_cut_stl_out,
            three_mf_out,
            values["text_color"],
            values["substrate_color"],
            qr_stl_paths,
        )

    return values


def main() -> int:
    args = parse_args()

    try:
        raw_values = load_values(args.values)
        build_placard(
            raw_values,
            args.model,
            args.out_dir,
            resolve_substrate_model(args),
            args.skip_export,
        )

    except (BuildError, OSError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
