"""Self-contained launcher for the LofiSymphony application.

This script automates environment preparation so end users can double-click
``launcher.py`` (or the provided platform-specific wrappers) and the project will
bootstrap itself.  It creates an isolated virtual environment, installs all
package dependencies – including the optional audio extras – and then hands off
execution to the Streamlit entry point.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".lofi_venv"
IS_WINDOWS = os.name == "nt"
PYTHON_BIN = VENV_DIR / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")
PIP_BIN = VENV_DIR / ("Scripts/pip.exe" if IS_WINDOWS else "bin/pip")
DEPS_SENTINEL = VENV_DIR / ".deps_installed"
STREAMLIT_APP = PROJECT_ROOT / "src" / "lofi_symphony" / "app.py"


class LauncherError(RuntimeError):
    """Raised when automatic preparation fails."""


def _debug(message: str) -> None:
    print(f"[LofiSymphony] {message}")


def _check_python_version() -> None:
    if sys.version_info < (3, 9):
        raise LauncherError(
            "Python 3.9 or newer is required to bootstrap LofiSymphony. "
            "Please install a compatible version from https://www.python.org/downloads/."
        )


def _run_command(command: list[str], *, cwd: Path | None = None) -> None:
    display_cmd = " ".join(command)
    _debug(f"Running: {display_cmd}")
    try:
        subprocess.run(command, cwd=cwd, check=True)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive
        raise LauncherError(
            f"Command failed with exit code {exc.returncode}: {display_cmd}\n"
            "Check your internet connection and try again."
        ) from exc


def _create_virtualenv(force_recreate: bool) -> None:
    if force_recreate and VENV_DIR.exists():
        _debug("Removing existing virtual environment …")
        shutil.rmtree(VENV_DIR)

    if VENV_DIR.exists():
        _debug("Using existing virtual environment.")
        return

    _debug("Creating virtual environment …")
    _run_command([sys.executable, "-m", "venv", str(VENV_DIR)])


def _install_dependencies(upgrade: bool) -> None:
    if DEPS_SENTINEL.exists() and not upgrade:
        _debug("Dependencies already installed – skipping install step.")
        return

    if not PIP_BIN.exists():  # pragma: no cover - defensive
        raise LauncherError("Virtual environment is missing pip. Please re-run with --reset.")

    # Upgrade pip/setuptools first for better wheel compatibility.
    _debug("Upgrading pip and build backends …")
    _run_command([str(PYTHON_BIN), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])

    install_target = ".[audio]"
    command = [str(PYTHON_BIN), "-m", "pip", "install"]
    if upgrade:
        command.append("--upgrade")
    command.append(install_target)

    _debug("Installing project dependencies – this might take a while on first launch …")
    _run_command(command, cwd=PROJECT_ROOT)

    DEPS_SENTINEL.touch()


def _launch_streamlit(additional_args: list[str]) -> None:
    env = os.environ.copy()
    # Ensure the virtual environment is active for subprocess.
    if IS_WINDOWS:
        scripts_dir = VENV_DIR / "Scripts"
        env["PATH"] = f"{scripts_dir};" + env.get("PATH", "")
    else:
        bin_dir = VENV_DIR / "bin"
        env["PATH"] = f"{bin_dir}:" + env.get("PATH", "")
    env["VIRTUAL_ENV"] = str(VENV_DIR)

    command = [str(PYTHON_BIN), "-m", "streamlit", "run", str(STREAMLIT_APP)] + additional_args
    _debug("Launching Streamlit …")
    subprocess.run(command, env=env, check=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare and launch the LofiSymphony app.")
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Install dependencies and exit without starting the Streamlit server.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the managed virtual environment before installing dependencies.",
    )
    parser.add_argument(
        "--upgrade",
        action="store_true",
        help="Force reinstallation of the Python dependencies even if they are already present.",
    )
    parser.add_argument(
        "streamlit_args",
        nargs=argparse.REMAINDER,
        help=(
            "Any additional arguments after '--' are forwarded directly to Streamlit. "
            "Example: launcher.py -- --server.headless true"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    _check_python_version()

    force_recreate = args.reset
    _create_virtualenv(force_recreate)

    try:
        _install_dependencies(upgrade=args.upgrade or force_recreate)
    except LauncherError:
        if DEPS_SENTINEL.exists():
            DEPS_SENTINEL.unlink(missing_ok=True)
        raise

    if args.prepare_only:
        _debug("Environment ready. You can launch the app later by running launcher.py again.")
        return

    additional_args: list[str] = []
    if args.streamlit_args:
        # argparse includes the separating '--' in streamlit_args; remove it if present.
        additional_args = [arg for arg in args.streamlit_args if arg != "--"]

    _launch_streamlit(additional_args)


if __name__ == "__main__":  # pragma: no cover - manual execution path
    try:
        main()
    except LauncherError as error:
        _debug(str(error))
        sys.exit(1)
