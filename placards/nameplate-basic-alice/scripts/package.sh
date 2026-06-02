#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
mkdir -p "$PROJECT_DIR/dist"
cd "$PROJECT_DIR/dist"
rm -f placard.tgz
tar -czf placard.tgz placard.txt
