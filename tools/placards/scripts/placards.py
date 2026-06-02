#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml


WORKSPACE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY_DIR = WORKSPACE_DIR / "placards" / "registry"
DEFAULT_OUTPUT_ROOT = WORKSPACE_DIR / "dist" / "placards"
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SUPPORTED_MODELS = {"placard-title-description"}
PACKAGE_NAME = "placard.tgz"
BASE_OUTPUTS = [
    "model.scad",
    "substrate.scad",
    "placard.scad",
    "title-description.scad",
    "substrate-cut.scad",
    "placard.stl",
    "title-description.stl",
    "substrate-cut.stl",
    "placard.3mf",
]
QR_OUTPUTS = [
    "qr-background.scad",
    "qr-dots.scad",
    "qr-background.stl",
    "qr-dots.stl",
]


class ToolError(ValueError):
    pass


@dataclass(frozen=True)
class PlacardEntry:
    id: str
    model: str
    values: dict[str, Any]
    source_path: Path
    out_dir: Path


def workspace_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (WORKSPACE_DIR / path).resolve()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(WORKSPACE_DIR))
    except ValueError:
        return str(path)


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_builder() -> ModuleType:
    build_path = (
        WORKSPACE_DIR
        / "models"
        / "placard-title-description"
        / "scripts"
        / "build.py"
    )
    spec = importlib.util.spec_from_file_location("placard_title_description_build", build_path)
    if spec is None or spec.loader is None:
        raise ToolError(f"could not load builder from {display_path(build_path)}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def model_paths(model: str) -> tuple[Path, Path, Path]:
    if model != "placard-title-description":
        raise ToolError(f"unsupported model {model!r}")
    model_dir = WORKSPACE_DIR / "models" / model
    return (
        model_dir / "model.scad",
        model_dir / "scripts" / "build.py",
        WORKSPACE_DIR / "models" / "substrate" / "model.scad",
    )


def validate_id(value: Any, source_path: Path) -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise ToolError(
            f"{display_path(source_path)}: id must match {ID_PATTERN.pattern!r}"
        )
    return value


def validate_model(value: Any, source_path: Path) -> str:
    if not isinstance(value, str):
        raise ToolError(f"{display_path(source_path)}: model must be a string")
    if value not in SUPPORTED_MODELS:
        raise ToolError(f"{display_path(source_path)}: unsupported model {value!r}")
    return value


def validate_values(value: Any, source_path: Path) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ToolError(f"{display_path(source_path)}: values must be a mapping")
    return dict(value)


def normalize_entry_values(builder: ModuleType, entry: PlacardEntry) -> dict[str, Any]:
    try:
        return builder.normalize_values(dict(entry.values))
    except Exception as exc:
        raise ToolError(f"{display_path(entry.source_path)}: {exc}") from exc


def read_registry(registry_dir: Path, output_root: Path) -> list[PlacardEntry]:
    registry_dir = workspace_path(registry_dir)
    output_root = workspace_path(output_root)
    if not registry_dir.is_dir():
        raise ToolError(f"registry directory does not exist: {display_path(registry_dir)}")

    entries: list[PlacardEntry] = []
    seen: dict[str, Path] = {}
    for source_path in sorted(registry_dir.glob("*.yaml")):
        data = load_yaml(source_path)
        if not isinstance(data, dict):
            raise ToolError(f"{display_path(source_path)}: registry entry must be a mapping")

        placard_id = validate_id(data.get("id"), source_path)
        if placard_id in seen:
            raise ToolError(
                f"{display_path(source_path)}: duplicate id {placard_id!r}; "
                f"first declared in {display_path(seen[placard_id])}"
            )
        seen[placard_id] = source_path

        model = validate_model(data.get("model"), source_path)
        values = validate_values(data.get("values"), source_path)
        entries.append(
            PlacardEntry(
                id=placard_id,
                model=model,
                values=values,
                source_path=source_path,
                out_dir=output_root / placard_id,
            )
        )

    return entries


def direct_entry(values_path: Path, out_dir: Path, model: str) -> PlacardEntry:
    source_path = workspace_path(values_path)
    data = load_yaml(source_path)
    values = validate_values(data, source_path)
    model_name = validate_model(model, source_path)
    return PlacardEntry(
        id=source_path.parent.name,
        model=model_name,
        values=values,
        source_path=source_path,
        out_dir=workspace_path(out_dir),
    )


def select_entries(entries: list[PlacardEntry], placard_id: str | None) -> list[PlacardEntry]:
    if placard_id is None:
        return entries
    selected = [entry for entry in entries if entry.id == placard_id]
    if not selected:
        raise ToolError(f"unknown placard id {placard_id!r}")
    return selected


def entries_from_args(args: argparse.Namespace) -> list[PlacardEntry]:
    if (args.values is None) != (args.out_dir is None):
        raise ToolError("--values and --out-dir must be provided together")
    if args.values is not None:
        if getattr(args, "id", None) is not None:
            raise ToolError("--id cannot be used with --values/--out-dir")
        return [direct_entry(args.values, args.out_dir, args.model)]
    return select_entries(read_registry(args.registry_dir, args.output_root), args.id)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_fingerprints(entry: PlacardEntry) -> dict[str, str]:
    model_path, builder_path, substrate_model = model_paths(entry.model)
    paths = [
        entry.source_path,
        model_path,
        builder_path,
        substrate_model,
        WORKSPACE_DIR / "pyproject.toml",
        WORKSPACE_DIR / "uv.lock",
    ]
    return {display_path(path): sha256_file(path) for path in paths if path.exists()}


def fingerprint(entry: PlacardEntry) -> str:
    payload = {
        "id": entry.id,
        "model": entry.model,
        "values": entry.values,
        "sources": source_fingerprints(entry),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def expected_outputs(normalized_values: dict[str, Any]) -> list[str]:
    outputs = list(BASE_OUTPUTS)
    if normalized_values["qr_code"] != "":
        outputs.extend(QR_OUTPUTS)
    return outputs


def output_status(entry: PlacardEntry, expected: list[str]) -> list[str]:
    missing: list[str] = []
    for name in expected:
        path = entry.out_dir / name
        if not path.is_file() or path.stat().st_size == 0:
            missing.append(name)
    return missing


def manifest_path(entry: PlacardEntry) -> Path:
    return entry.out_dir / "build.json"


def read_manifest(entry: PlacardEntry) -> dict[str, Any] | None:
    path = manifest_path(entry)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def is_current(entry: PlacardEntry, entry_fingerprint: str, expected: list[str]) -> bool:
    manifest = read_manifest(entry)
    if manifest is None or manifest.get("fingerprint") != entry_fingerprint:
        return False
    return not output_status(entry, expected)


def write_manifest(
    entry: PlacardEntry,
    entry_fingerprint: str,
    expected: list[str],
    normalized_values: dict[str, Any],
) -> None:
    payload = {
        "id": entry.id,
        "model": entry.model,
        "source": display_path(entry.source_path),
        "fingerprint": entry_fingerprint,
        "outputs": expected,
        "values": normalized_values,
    }
    manifest_path(entry).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_entries(args: argparse.Namespace) -> int:
    builder = load_builder()
    for entry in entries_from_args(args):
        normalized_values = normalize_entry_values(builder, entry)
        expected = expected_outputs(normalized_values)
        entry_fingerprint = fingerprint(entry)
        if not args.force and is_current(entry, entry_fingerprint, expected):
            print(f"{entry.id}: up to date")
            continue

        model_path, _builder_path, substrate_model = model_paths(entry.model)
        builder.build_placard(
            dict(entry.values),
            model_path,
            entry.out_dir,
            substrate_model,
            args.skip_export,
        )
        write_manifest(entry, entry_fingerprint, expected, normalized_values)
        print(f"{entry.id}: built {display_path(entry.out_dir)}")
    return 0


def verify_entries(args: argparse.Namespace) -> int:
    builder = load_builder()
    failures: list[str] = []
    for entry in entries_from_args(args):
        normalized_values = normalize_entry_values(builder, entry)
        expected = expected_outputs(normalized_values)
        entry_fingerprint = fingerprint(entry)
        missing = output_status(entry, expected)
        manifest = read_manifest(entry)
        if missing:
            failures.append(f"{entry.id}: missing outputs: {', '.join(missing)}")
        if manifest is None:
            failures.append(f"{entry.id}: missing build.json")
        elif manifest.get("fingerprint") != entry_fingerprint:
            failures.append(f"{entry.id}: build.json fingerprint is stale")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    return 0


def package_entries(args: argparse.Namespace) -> int:
    builder = load_builder()
    for entry in entries_from_args(args):
        normalized_values = normalize_entry_values(builder, entry)
        expected = expected_outputs(normalized_values)
        missing = output_status(entry, expected)
        if missing:
            raise ToolError(f"{entry.id}: missing outputs: {', '.join(missing)}")

        package_path = entry.out_dir / args.package_name
        package_path.unlink(missing_ok=True)
        files = [entry.out_dir / name for name in expected]
        if manifest_path(entry).is_file():
            files.append(manifest_path(entry))

        with tarfile.open(package_path, "w:gz") as archive:
            for path in files:
                archive.add(path, arcname=path.name)
        print(f"{entry.id}: packaged {display_path(package_path)}")
    return 0


def validate_entries(args: argparse.Namespace) -> int:
    builder = load_builder()
    entries = read_registry(args.registry_dir, args.output_root)
    for entry in entries:
        normalize_entry_values(builder, entry)
    print(f"validated {len(entries)} placard registry entr{'y' if len(entries) == 1 else 'ies'}")
    return 0


def list_entries(args: argparse.Namespace) -> int:
    for entry in read_registry(args.registry_dir, args.output_root):
        print(entry.id)
    return 0


def clean_entries(args: argparse.Namespace) -> int:
    output_root = workspace_path(args.output_root)
    shutil.rmtree(output_root, ignore_errors=True)
    print(f"removed {display_path(output_root)}")
    return 0


def add_registry_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--registry-dir", type=Path, default=DEFAULT_REGISTRY_DIR)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)


def add_entry_args(parser: argparse.ArgumentParser) -> None:
    add_registry_args(parser)
    parser.add_argument("--id", help="Registry placard id to process")
    parser.add_argument("--values", type=Path, help="Direct values YAML to process")
    parser.add_argument("--out-dir", type=Path, help="Direct output directory")
    parser.add_argument("--model", default="placard-title-description")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and manage placard registry entries.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build")
    add_entry_args(build_parser)
    build_parser.add_argument("--force", action="store_true")
    build_parser.add_argument("--skip-export", action="store_true")
    build_parser.set_defaults(func=build_entries)

    package_parser = subparsers.add_parser("package")
    add_entry_args(package_parser)
    package_parser.add_argument("--package-name", default=PACKAGE_NAME)
    package_parser.set_defaults(func=package_entries)

    verify_parser = subparsers.add_parser("verify")
    add_entry_args(verify_parser)
    verify_parser.set_defaults(func=verify_entries)

    validate_parser = subparsers.add_parser("validate")
    add_registry_args(validate_parser)
    validate_parser.set_defaults(func=validate_entries)

    list_parser = subparsers.add_parser("list")
    add_registry_args(list_parser)
    list_parser.set_defaults(func=list_entries)

    clean_parser = subparsers.add_parser("clean")
    add_registry_args(clean_parser)
    clean_parser.set_defaults(func=clean_entries)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return args.func(args)
    except (ToolError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
