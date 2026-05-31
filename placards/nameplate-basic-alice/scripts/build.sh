#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
NAME="$(sed -n 's/^NAME=//p' "$PROJECT_DIR/values.env")"
mkdir -p "$PROJECT_DIR/dist"
printf 'Placard for %s\n' "$NAME" >"$PROJECT_DIR/dist/placard.txt"
