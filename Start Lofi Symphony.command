#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  PYTHON_BIN="python"
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  cat <<'MSG'

Python 3.9 or newer is required to run LofiSymphony.
Install it from https://www.python.org/downloads/ and then double-click this file again.
MSG
  read -rp $'\nPress Return to close this window…' _
  exit 1
fi

if ! "$PYTHON_BIN" -c 'import sys; exit(0 if (3, 9) <= sys.version_info < (3, 13) else 1)'; then
  cat <<'MSG'

This launcher needs Python between 3.9 and 3.12.
Install a supported version from https://www.python.org/downloads/ and then double-click this file again.
MSG
  read -rp $'\nPress Return to close this window…' _
  exit 1
fi

"$PYTHON_BIN" launcher.py "$@"
read -rp $'\nPress Return to close this window…' _
