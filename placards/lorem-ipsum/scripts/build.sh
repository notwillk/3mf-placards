#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WORKSPACE_DIR="$(cd "$PROJECT_DIR/../.." && pwd)"
MODEL_DIR="$WORKSPACE_DIR/models/placard-title-description"

"$MODEL_DIR/scripts/build.py" \
	--values "$PROJECT_DIR/values.yaml" \
	--model "$MODEL_DIR/model.scad" \
	--out-dir "$PROJECT_DIR/dist"
