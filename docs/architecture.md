# Scalable Placard Repository Architecture

## Repository Model

This repository has three top-level concerns:

- `models/` contains reusable OpenSCAD model definitions and their model-level fixtures.
- `placards/` contains concrete placard data. Curated examples stay as directories, while bulk future placards live as registry YAML.
- `tools/` contains shared repository tooling for building, packaging, validating, and cleaning generated artifacts.

The long-term scaling path is a hybrid registry. Important examples such as
`placards/lorem-ipsum` and `placards/qr-sample` remain easy to inspect and run,
but hundreds of ordinary placards should be added as data-only entries under
`placards/registry/`.

## Placard Registry

Registry entries are flat files under `placards/registry/*.yaml`:

```yaml
id: qr-sample
model: placard-title-description
values:
  title: "JOIN THE WIFI"
  description: "SSID: MyNetwork\nsupersecret"
  qr_code: "WIFI:T:WPA;S:MyNetwork;P:supersecret;;"
```

Registry IDs use lowercase letters, numbers, and dashes. The first supported
model is `placard-title-description`; its `values` mapping is passed through the
same builder validation used by curated placards.

Bulk registry outputs are centralized under ignored paths:

```text
dist/placards/<id>/
```

Each built placard writes `build.json` with the source fingerprint, normalized
values, and expected outputs. The shared tool uses that manifest to skip
unchanged placards while still rebuilding if any required output is missing.

## Shared Tooling

`tools/placards` owns shared placard commands:

```bash
moon run placards:list
moon run placards:validate
moon run placards:build
moon run placards:build -- --id qr-sample
moon run placards:verify
moon run placards:package
moon run placards:clean
```

Curated title-description placards delegate their build and package scripts to
this tool. That keeps examples useful without copying the build/package logic
into every placard directory.

## Moon Actions

Root-level actions:

- `moon run :install`: run `uv sync --all-extras --locked`.
- `moon run :check`: run project checks, including Python dependency sync checks.
- `moon run :build`: build model samples, curated placards, registry placards, and tools.
- `moon run :verify`: validate generated outputs after the Moon build dependency has run.
- `moon run :package`: package existing build outputs after the Moon build dependency has run.
- `moon run :clean`: remove generated project output directories.
- `moon run :deep-clean`: remove reproducible ignored artifacts and caches.

`verify` rules should not rebuild outputs internally. If a verification target
needs generated artifacts, its Moon task should depend on `build`. Package
scripts should not call build directly; package tasks should depend on `build`.

`deep-clean` is intended to make the workspace resemble a fresh clone while
preserving source changes. It removes reproducible ignored artifacts such as
`dist/`, `**/dist/`, `.moon/cache/`, `.checksy-cache/`, `.venv/`, Python bytecode,
and `.DS_Store` files.
