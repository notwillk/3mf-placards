#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WORKSPACE_DIR="$(cd "$PROJECT_DIR/../.." && pwd)"

"$WORKSPACE_DIR/tools/placards/scripts/placards.sh" build \
	--values "$PROJECT_DIR/values.yaml" \
	--model placard-title-description \
	--out-dir "$PROJECT_DIR/dist"
