#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

cd "$WORKSPACE_DIR"

if command -v uv >/dev/null 2>&1; then
	exec env UV_LINK_MODE="${UV_LINK_MODE:-copy}" uv run --all-extras python3 "$SCRIPT_DIR/placards.py" "$@"
fi

exec python3 "$SCRIPT_DIR/placards.py" "$@"
