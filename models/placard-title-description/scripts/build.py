#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULTS: dict[str, Any] = {
    "width": 75,
    "aspect_ratio": 2,
    "thickness": 2,
    "border_thickness": 2,
    "border_radius": 5,
    "orientation": "landscape",
    "description": "",
}

ALLOWED_KEYS = set(DEFAULTS) | {"title"}
NUMERIC_KEYS = {
    "width",
    "aspect_ratio",
    "thickness",
    "border_thickness",
    "border_radius",
}
STRING_KEYS = {"title", "orientation", "description"}
ORIENTATIONS = {"landscape", "portrait"}


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

    for key in NUMERIC_KEYS:
        if isinstance(values[key], bool) or not isinstance(values[key], (int, float)):
            raise BuildError(f"{key} must be numeric")

    if values["width"] <= 0:
        raise BuildError("width must be greater than 0")
    if values["aspect_ratio"] <= 0:
        raise BuildError("aspect_ratio must be greater than 0")
    if values["thickness"] <= 0:
        raise BuildError("thickness must be greater than 0")
    if values["border_thickness"] < 0:
        raise BuildError("border_thickness must be 0 or greater")
    if values["border_radius"] < 0:
        raise BuildError("border_radius must be 0 or greater")

    short_side = values["width"] / values["aspect_ratio"]
    if values["border_radius"] > short_side / 2:
        raise BuildError("border_radius cannot exceed half of the short side")

    return values


def scad_string(value: str) -> str:
    return json.dumps(value)


def scad_number(value: int | float) -> str:
    if isinstance(value, int):
        return str(value)
    if value.is_integer():
        return str(int(value))
    return str(value)


def write_scad(values: dict[str, Any], model_name: str, out_path: Path) -> None:
    lines = [
        "// Generated by models/placard-title-description/scripts/build.py",
        "// Edit the source YAML values instead of this file.",
        "",
        f"use <{model_name}>;",
        "",
        f"width = {scad_number(values['width'])};",
        f"aspect_ratio = {scad_number(values['aspect_ratio'])};",
        f"thickness = {scad_number(values['thickness'])};",
        f"border_thickness = {scad_number(values['border_thickness'])};",
        f"border_radius = {scad_number(values['border_radius'])};",
        f"orientation = {scad_string(values['orientation'])};",
        f"title = {scad_string(values['title'])};",
        f"description = {scad_string(values['description'])};",
        "",
        "placard_title_description(",
        "  placard_width = width,",
        "  placard_aspect_ratio = aspect_ratio,",
        "  placard_thickness = thickness,",
        "  placard_border_thickness = border_thickness,",
        "  placard_border_radius = border_radius,",
        "  placard_orientation = orientation,",
        "  placard_title = title,",
        "  placard_description = description",
        ");",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def export_stl(scad_path: Path, stl_path: Path) -> None:
    openscad = shutil.which("openscad")
    if openscad is None:
        raise BuildError("openscad is required to export STL, but it was not found in PATH")

    subprocess.run([openscad, "-o", str(stl_path), str(scad_path)], check=True)


def main() -> int:
    args = parse_args()

    try:
        raw_values = load_values(args.values)
        values = normalize_values(raw_values)

        args.out_dir.mkdir(parents=True, exist_ok=True)
        model_out = args.out_dir / "model.scad"
        scad_out = args.out_dir / "placard.scad"
        stl_out = args.out_dir / "placard.stl"

        shutil.copyfile(args.model, model_out)
        write_scad(values, model_out.name, scad_out)

        if not args.skip_export:
            export_stl(scad_out, stl_out)

    except (BuildError, OSError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
