"""Allow running the package with ``python -m lofi_symphony``."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

if __package__ in {None, ""}:  # pragma: no cover - defensive import guard
    package_dir = Path(__file__).resolve().parent
    src_root = package_dir.parent
    src_str = str(src_root)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
    __package__ = "lofi_symphony"

from .cli import main as cli_main


def main(argv: Sequence[str] | None = None) -> None:
    cli_main(argv)


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])
