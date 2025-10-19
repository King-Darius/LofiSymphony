"""Self-contained launcher for the LofiSymphony application.

This script automates environment preparation so end users can double-click
``launcher.py`` (or the provided platform-specific wrappers) and the project will
bootstrap itself. It creates an isolated virtual environment, installs every
core dependency from wheels, and then hands off execution to the Streamlit entry
point. Optional MusicGen extras can be layered on top via `--with-musicgen`.
"""

from __future__ import annotations

import argparse
import importlib.util
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
PROFILE_SENTINEL = VENV_DIR / ".install_profile"
FFMPEG_SENTINEL = VENV_DIR / ".ffmpeg_path"
SPACY_MODEL_SENTINEL = VENV_DIR / ".spacy_en_core_web_sm"
LAUNCH_ENTRYPOINT = "lofi_symphony"

CORE_PROFILE = "core"
MUSICGEN_PROFILE = "musicgen"

CORE_RUNTIME_REQUIREMENTS: dict[str, str] = {
    "streamlit": "streamlit",
    "pretty_midi": "pretty_midi",
    "music21": "music21",
    "numpy": "numpy",
    "pydub": "pydub",
    "rtmidi": "python-rtmidi",
    "pandas": "pandas",
    "plotly": "plotly",
    "fluidsynth": "pyfluidsynth",
}

MUSICGEN_RUNTIME_REQUIREMENTS: dict[str, str] = {
    "torch": "torch==2.1.2",
    "torchaudio": "torchaudio==2.1.2",
    "audiocraft": "audiocraft==1.0.0",
    "spacy": "spacy==3.5.2",
}


class LauncherError(RuntimeError):
    """Raised when automatic preparation fails."""


def _debug(message: str) -> None:
    print(f"[LofiSymphony] {message}")


def _read_installed_profile() -> str | None:
    if not PROFILE_SENTINEL.exists():
        return None
    try:
        return PROFILE_SENTINEL.read_text(encoding="utf-8").strip() or None
    except OSError:  # pragma: no cover - best effort fallback
        return None


def _write_installed_profile(profile: str) -> None:
    PROFILE_SENTINEL.write_text(profile, encoding="utf-8")


def _check_python_version() -> None:
    if sys.version_info < (3, 9) or sys.version_info >= (3, 12):
        raise LauncherError(
            "Python 3.9–3.11 is required to bootstrap LofiSymphony. "
            "Install a compatible interpreter from https://www.python.org/downloads/ and rerun the launcher."
        )


def _run_command(
    command: list[str], *, cwd: Path | None = None, extra_help: str | None = None
) -> None:
    display_cmd = " ".join(command)
    _debug(f"Running: {display_cmd}")
    try:
        subprocess.run(command, cwd=cwd, check=True)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive
        message = (
            f"Command failed with exit code {exc.returncode}: {display_cmd}\n"
            "Check your internet connection and try again."
        )
        if extra_help:
            message = f"{message}\n\n{extra_help}"
        raise LauncherError(message) from exc


def _create_virtualenv(force_recreate: bool) -> None:
    if force_recreate and VENV_DIR.exists():
        _debug("Removing existing virtual environment …")
        shutil.rmtree(VENV_DIR)

    if VENV_DIR.exists():
        _debug("Using existing virtual environment.")
        return

    _debug("Creating virtual environment …")
    _run_command([sys.executable, "-m", "venv", str(VENV_DIR)])


def _install_dependencies(*, upgrade: bool, profile: str) -> None:
    installed_profile = _read_installed_profile()
    if DEPS_SENTINEL.exists() and installed_profile == profile and not upgrade:
        _debug("Dependencies already installed for the requested profile – skipping install step.")
        _ensure_runtime_requirements(profile=profile, upgrade=False)
        _ensure_ffmpeg_available()
        if profile == MUSICGEN_PROFILE:
            _ensure_spacy_language_model()
        return

    if not PIP_BIN.exists():  # pragma: no cover - defensive
        raise LauncherError("Virtual environment is missing pip. Please re-run with --reset.")

    # Upgrade pip/setuptools first for better wheel compatibility.
    _debug("Upgrading pip and build backends …")
    _run_command([str(PYTHON_BIN), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])

    install_target = ".[audio]" if profile in {CORE_PROFILE, MUSICGEN_PROFILE} else "."
    command = [str(PYTHON_BIN), "-m", "pip", "install"]
    if upgrade:
        command.append("--upgrade")
    command.append(install_target)

    _debug("Installing project dependencies – this might take a while on first launch …")
    _run_command(command, cwd=PROJECT_ROOT)

    if profile == MUSICGEN_PROFILE:
        _install_musicgen_extras(upgrade=upgrade)

    DEPS_SENTINEL.touch()
    _write_installed_profile(profile)
    _ensure_runtime_requirements(profile=profile, upgrade=upgrade)
    _ensure_ffmpeg_available()
    if profile == MUSICGEN_PROFILE:
        _ensure_spacy_language_model()


def _install_musicgen_extras(*, upgrade: bool) -> None:
    _debug("Installing MusicGen extras (torch, torchaudio, audiocraft, spaCy) …")

    torch_command = [
        str(PYTHON_BIN),
        "-m",
        "pip",
        "install",
    ]
    if upgrade:
        torch_command.append("--upgrade")
    torch_command.extend(
        [
            "--extra-index-url",
            "https://download.pytorch.org/whl/cpu",
            "torch==2.1.2",
            "torchaudio==2.1.2",
        ]
    )
    _run_command(torch_command)

    extras_command = [str(PYTHON_BIN), "-m", "pip", "install"]
    if upgrade:
        extras_command.append("--upgrade")
    extras_command.extend(["audiocraft==1.0.0", "spacy==3.5.2"])
    extra_help = None
    if IS_WINDOWS:
        extra_help = (
            "MusicGen extras require native build tools on Windows. Install the "
            "Microsoft C++ Build Tools from https://visualstudio.microsoft.com/downloads/ "
            "before enabling MusicGen support."
        )
    _run_command(extras_command, extra_help=extra_help)


def _detect_missing_modules(requirements: dict[str, str]) -> list[str]:
    missing: list[str] = []
    for module_name, pip_name in requirements.items():
        if importlib.util.find_spec(module_name) is None:
            missing.append(pip_name)
    return missing


def _ensure_runtime_requirements(*, profile: str, upgrade: bool) -> None:
    requirements = dict(CORE_RUNTIME_REQUIREMENTS)
    if profile == MUSICGEN_PROFILE:
        requirements.update(MUSICGEN_RUNTIME_REQUIREMENTS)

    missing = _detect_missing_modules(requirements)
    if not missing:
        _debug("Verified Python packages are present.")
        return

    command = [str(PYTHON_BIN), "-m", "pip", "install"]
    if upgrade:
        command.append("--upgrade")
    command.extend(sorted(set(missing)))
    _debug(f"Installing missing runtime modules: {', '.join(sorted(set(missing)))}")
    _run_command(command)


def _ensure_spacy_language_model() -> None:
    if SPACY_MODEL_SENTINEL.exists():
        return

    if importlib.util.find_spec("spacy") is None:
        return

    if importlib.util.find_spec("en_core_web_sm") is not None:
        SPACY_MODEL_SENTINEL.touch()
        return

    _debug("Downloading spaCy English model …")
    _run_command([str(PYTHON_BIN), "-m", "spacy", "download", "en_core_web_sm"])
    SPACY_MODEL_SENTINEL.touch()


def _ensure_ffmpeg_available() -> Path:
    if FFMPEG_SENTINEL.exists():
        try:
            cached = Path(FFMPEG_SENTINEL.read_text(encoding="utf-8").strip())
        except OSError:
            cached = None
        else:
            if cached and cached.exists():
                return cached

    ffmpeg_path_str = shutil.which("ffmpeg")
    if ffmpeg_path_str:
        ffmpeg_path = Path(ffmpeg_path_str)
        FFMPEG_SENTINEL.write_text(str(ffmpeg_path), encoding="utf-8")
        return ffmpeg_path

    try:
        import imageio_ffmpeg
    except ImportError as exc:  # pragma: no cover - safety net
        raise LauncherError(
            "ffmpeg is required but not installed and automatic provisioning failed. "
            "Install ffmpeg manually and re-run the launcher."
        ) from exc

    ffmpeg_path = Path(imageio_ffmpeg.get_ffmpeg_exe())
    if not ffmpeg_path.exists():  # pragma: no cover - defensive
        raise LauncherError(
            "Unable to provision ffmpeg binary automatically. "
            "Install ffmpeg manually and re-run the launcher."
        )

    FFMPEG_SENTINEL.write_text(str(ffmpeg_path), encoding="utf-8")
    _debug(f"Provisioned ffmpeg at {ffmpeg_path}.")
    return ffmpeg_path


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

    try:
        ffmpeg_path = Path(FFMPEG_SENTINEL.read_text(encoding="utf-8").strip())
    except OSError:
        ffmpeg_path = None
    else:
        if not ffmpeg_path.exists():
            ffmpeg_path = None

    if ffmpeg_path:
        env.setdefault("FFMPEG_BINARY", str(ffmpeg_path))
        env["PATH"] = f"{ffmpeg_path.parent}{os.pathsep}" + env.get("PATH", "")

    command = [str(PYTHON_BIN), "-m", LAUNCH_ENTRYPOINT] + additional_args
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
        "--with-musicgen",
        action="store_true",
        help=(
            "Install optional MusicGen dependencies (torch, torchaudio, audiocraft). "
            "These packages are sizeable and may require native build tools on Windows."
        ),
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

    requested_profile = MUSICGEN_PROFILE if args.with_musicgen else CORE_PROFILE

    try:
        _install_dependencies(upgrade=args.upgrade or force_recreate, profile=requested_profile)
    except LauncherError:
        if DEPS_SENTINEL.exists():
            DEPS_SENTINEL.unlink(missing_ok=True)
        PROFILE_SENTINEL.unlink(missing_ok=True)
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
