#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  PYTHON_BIN="python"
fi
"$PYTHON_BIN" launcher.py "$@"
read -rp $'\nPress Return to close this window…' _
