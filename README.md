# 3mf-placards

This repository is a Moon-orchestrated monorepo for model definitions, placard instances, and supporting tooling.

## Layout

- `models/*`: reusable 3D model definitions and sample model workflows
- `placards/*`: concrete model instances with specific values
- `tools/*`: support tooling for developing, packaging, deploying, and operating the repository

## Workspace Commands

```bash
moon run :format
moon run :check
moon run :build
moon run :verify
moon run :package
```

## Development Container

The canonical environment is the Dockerfile-based `.devcontainer`. On create, it runs:

```bash
checksy --config verify.checksy.yaml check
```

The devcontainer includes `uv` for Python package management.
