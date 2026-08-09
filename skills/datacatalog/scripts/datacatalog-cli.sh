#!/bin/bash
# DataCatalog CLI — thin bash wrapper that delegates to datacatalog-cli.py
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SKILL_DIR/datacatalog-cli.py" "$@"
