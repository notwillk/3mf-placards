#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

"$SCRIPT_DIR/build.py" \
	--values "$PROJECT_DIR/sample-values.yaml" \
	--model "$PROJECT_DIR/model.scad" \
	--out-dir "$PROJECT_DIR/dist"
