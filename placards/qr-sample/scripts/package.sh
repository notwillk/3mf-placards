#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

"$SCRIPT_DIR/build.sh"
mkdir -p "$PROJECT_DIR/dist"
cd "$PROJECT_DIR/dist"
rm -f placard.tgz
files=(
	model.scad
	substrate.scad
	placard.scad
	title-description.scad
	substrate-cut.scad
	placard.stl
	title-description.stl
	substrate-cut.stl
	placard.3mf
)
for optional in qr-background.scad qr-dots.scad qr-background.stl qr-dots.stl; do
	if [[ -f "$optional" ]]; then
		files+=("$optional")
	fi
done
tar -czf placard.tgz "${files[@]}"
