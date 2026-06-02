# 3mf-placards

This repository is a Moon-orchestrated monorepo for model definitions, placard instances, and supporting tooling.

## Layout

- `models/*`: reusable 3D model definitions and sample model workflows
- `placards/*`: curated concrete model instances with specific values
- `placards/registry/*`: data-only placard entries for bulk generation
- `tools/*`: support tooling for developing, packaging, deploying, and operating the repository

## Workspace Commands

```bash
moon run :install
moon run :format
moon run :check
moon run :build
moon run :verify
moon run :package
moon run :clean
moon run :deep-clean
```

Registry placards can be managed through the shared placard tooling:

```bash
moon run placards:list
moon run placards:validate
moon run placards:build
moon run placards:build -- --id qr-sample
moon run placards:package
```

## Development Container

The canonical environment is the Dockerfile-based `.devcontainer`. On create, it runs:

```bash
checksy --config verify.checksy.yaml check
```

The devcontainer includes `uv` for Python package management.
