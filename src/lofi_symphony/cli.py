"""Command-line helpers for launching LofiSymphony."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from streamlit.web import bootstrap


def _app_path() -> Path:
    return Path(__file__).with_name("app.py")


def _run_smoke_test(timeout: float = 5.0) -> None:
    """Run a headless smoke test to ensure the app loads without errors."""

    from streamlit.testing.v1 import AppTest

    app_test = AppTest.from_file(str(_app_path()))
    app_test.run(timeout=timeout)

    if app_test.exception:
        print("Streamlit smoke test failed:", app_test.exception)
        raise SystemExit(1)


def main(argv: Sequence[str] | None = None) -> None:
    """Launch the Streamlit UI or run diagnostics."""

    parser = argparse.ArgumentParser(description="Utilities for the LofiSymphony Streamlit app")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run a quick headless Streamlit smoke test instead of launching the server.",
    )

    args = parser.parse_args(argv)

    if args.smoke_test:
        _run_smoke_test()
        return

    bootstrap.run(str(_app_path()), "", [], flag_options={})


if __name__ == "__main__":  # pragma: no cover
    main()
