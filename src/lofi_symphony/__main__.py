"""Allow running the package with ``python -m lofi_symphony``."""

from __future__ import annotations

import sys
from typing import Sequence

from .cli import main as cli_main


def main(argv: Sequence[str] | None = None) -> None:
    cli_main(argv)


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])
