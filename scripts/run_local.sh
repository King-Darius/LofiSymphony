#!/usr/bin/env bash
# Run the Streamlit app with the same hardening defaults documented in the README.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

if [[ -z "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="${PROJECT_ROOT}/src"
elif [[ ":${PYTHONPATH}:" != *":${PROJECT_ROOT}/src:"* ]]; then
  export PYTHONPATH="${PROJECT_ROOT}/src:${PYTHONPATH}"
fi

# Mirror the local-only + no-telemetry defaults from .streamlit/config.toml.
export STREAMLIT_BROWSER_GATHER_USAGE_STATS="false"

exec python -m streamlit run "${PROJECT_ROOT}/src/lofi_symphony/app.py" "$@"
