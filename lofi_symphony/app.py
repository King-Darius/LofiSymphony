"""Streamlit entrypoint shim that dispatches to the package module in ``src``."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:  # pragma: no cover - defensive
    project_root = Path(__file__).resolve().parents[1]
    src_dir = project_root / "src"
    src_str = str(src_dir)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
    __package__ = "lofi_symphony"

from lofi_symphony.app import main as run_app


if __name__ == "__main__":  # pragma: no cover
    run_app()
