"""Command-line helpers for launching LofiSymphony."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Sequence


def _app_path() -> Path:
    return Path(__file__).with_name("app.py")


def _launch_streamlit(
    app_path: Path | None = None,
    *,
    streamlit_args: Sequence[str] | None = None,
) -> None:
    """Start the Streamlit runtime for the packaged app."""

    target = app_path or _app_path()
    args = [sys.executable, "-m", "streamlit", "run", str(target)]
    if streamlit_args:
        args.extend(streamlit_args)

    subprocess.run(args, check=True)


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
    parser.add_argument(
        "streamlit_args",
        nargs=argparse.REMAINDER,
        help=(
            "Any additional arguments after '--' are forwarded directly to Streamlit. "
            "Example: lofi-symphony -- --server.headless true"
        ),
    )

    args = parser.parse_args(argv)

    if args.smoke_test:
        _run_smoke_test()
        return

    forwarded_args = [arg for arg in args.streamlit_args if arg != "--"] if args.streamlit_args else []

    _launch_streamlit(streamlit_args=forwarded_args)


if __name__ == "__main__":  # pragma: no cover
    main()
