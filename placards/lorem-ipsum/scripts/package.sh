#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

"$SCRIPT_DIR/build.sh"
mkdir -p "$PROJECT_DIR/dist"
cd "$PROJECT_DIR/dist"
rm -f placard.tgz
tar -czf placard.tgz model.scad placard.scad placard.stl
