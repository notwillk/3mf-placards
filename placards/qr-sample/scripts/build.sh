#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WORKSPACE_DIR="$(cd "$PROJECT_DIR/../.." && pwd)"
MODEL_DIR="$WORKSPACE_DIR/models/placard-title-description"

if command -v uv >/dev/null 2>&1; then
	RUNNER=(env UV_LINK_MODE="${UV_LINK_MODE:-copy}" uv run --extra qr python3 "$MODEL_DIR/scripts/build.py")
else
	RUNNER=(python3 "$MODEL_DIR/scripts/build.py")
fi

"${RUNNER[@]}" \
	--values "$PROJECT_DIR/values.yaml" \
	--model "$MODEL_DIR/model.scad" \
	--substrate-model "$WORKSPACE_DIR/models/substrate/model.scad" \
	--out-dir "$PROJECT_DIR/dist"
