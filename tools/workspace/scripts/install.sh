#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
LOCK_DIR="${TMPDIR:-/tmp}/3mf-placards-install.lock"
STAMP="${TMPDIR:-/tmp}/3mf-placards-install.stamp"
STAMP_TTL_SECONDS=5

stamp_is_fresh() {
	[[ -f "$STAMP" ]] || return 1
	[[ -f "$WORKSPACE_DIR/.venv/pyvenv.cfg" ]] || return 1
	local now
	local modified
	now="$(date +%s)"
	modified="$(stat -c %Y "$STAMP")"
	((now - modified < STAMP_TTL_SECONDS))
}

if stamp_is_fresh; then
	exit 0
fi

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
	while [[ -d "$LOCK_DIR" ]]; do
		sleep 0.1
	done
	exit 0
fi

trap 'rmdir "$LOCK_DIR"' EXIT

if stamp_is_fresh; then
	exit 0
fi

uv sync --all-extras --locked
touch "$STAMP"
