"""Entrypoint for running the packaged Streamlit app locally."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence


def _ensure_src_on_path() -> None:
    """Add the local ``src`` directory to ``sys.path`` when running from source."""

    project_root = Path(__file__).resolve().parent
    src_path = project_root / "src"
    if src_path.exists():
        src_str = str(src_path)
        if src_str not in sys.path:
            sys.path.insert(0, src_str)


def main(argv: Sequence[str] | None = None) -> None:
    """Delegate to the CLI launcher so ``python app.py`` behaves like the console script."""

    _ensure_src_on_path()
    from lofi_symphony.cli import main as cli_main

    cli_main(argv)


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])
