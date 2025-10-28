"""Self-contained launcher for the LofiSymphony application.

This script automates environment preparation so end users can double-click
``launcher.py`` (or the provided platform-specific wrappers) and the project will
bootstrap itself. It creates an isolated virtual environment, installs every
core dependency from wheels, and then hands off execution to the Streamlit entry
point. MusicGen dependencies are bundled automatically; the legacy
`--with-musicgen` flag is retained for backwards compatibility and to trigger
spaCy language model downloads.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".lofi_venv"
IS_WINDOWS = os.name == "nt"
PYTHON_BIN = VENV_DIR / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")
PIP_BIN = VENV_DIR / ("Scripts/pip.exe" if IS_WINDOWS else "bin/pip")
DEPS_SENTINEL = VENV_DIR / ".deps_installed"
PROFILE_SENTINEL = VENV_DIR / ".install_profile"
FFMPEG_SENTINEL = VENV_DIR / ".ffmpeg_path"
SPACY_MODEL_SENTINEL = VENV_DIR / ".spacy_en_core_web_sm"
OPTIONAL_FAILURES_SENTINEL = VENV_DIR / ".optional_failures.json"
OPTIONAL_FAILURES_ENV_VAR = "LOFI_SYMPHONY_OPTIONAL_FAILURES"
LAUNCH_ENTRYPOINT = "lofi_symphony"

PYTORCH_INDEX_URL = "https://download.pytorch.org/whl/cpu"
PYTORCH_PACKAGE_NAMES = {"torch", "torchaudio", "torchvision"}

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

BEST_EFFORT_RUNTIME_REQUIREMENTS: dict[str, str] = {
    "torch": "torch==2.1.2",
    "torchaudio": "torchaudio==2.1.2",
    "audiocraft": "audiocraft==1.0.0",
    "spacy": "spacy==3.5.2",
}

MUSICGEN_RUNTIME_REQUIREMENTS: dict[str, str] = {}


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
    if sys.version_info < (3, 9) or sys.version_info >= (3, 13):
        raise LauncherError(
            "Python 3.9–3.12 is required to bootstrap LofiSymphony. "
            "Install a compatible interpreter from https://www.python.org/downloads/ and rerun the launcher."
        )


def _run_command(
    command: list[str], *, cwd: Path | None = None, extra_help: str | None = None, retries: int = 0
) -> None:
    display_cmd = " ".join(command)
    _debug(f"Running: {display_cmd}")
    attempt = 0
    last_exc: subprocess.CalledProcessError | None = None
    while attempt <= retries:
        try:
            subprocess.run(command, cwd=cwd, check=True)
        except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive
            last_exc = exc
            attempt += 1
            if attempt > retries:
                break
            _debug(
                "Command failed – retrying once the network settles …"
            )
        else:
            return

    assert last_exc is not None  # for type checkers
    message = (
        f"Command failed with exit code {last_exc.returncode}: {display_cmd}\n"
        "Check your internet connection and try again."
    )
    if extra_help:
        message = f"{message}\n\n{extra_help}"
    raise LauncherError(message) from last_exc


def _normalize_requirement_name(requirement: str) -> str:
    name = requirement.strip()
    if not name:
        return ""

    # Remove environment markers and extras.
    for delimiter in (";", "["):
        index = name.find(delimiter)
        if index != -1:
            name = name[:index]

    # Trim version specifiers and comparison operators.
    for operator in ("===", "==", "<=", ">=", "~=", "!=", "<", ">"):
        index = name.find(operator)
        if index != -1:
            name = name[:index]

    return name.strip().lower().replace("_", "-")


def _maybe_add_pytorch_index(command: list[str], packages: Iterable[str]) -> bool:
    for package in packages:
        if package.strip() == ".[audio]":
            command.extend(["--extra-index-url", PYTORCH_INDEX_URL])
            return True
        normalized = _normalize_requirement_name(package)
        if normalized in PYTORCH_PACKAGE_NAMES:
            command.extend(["--extra-index-url", PYTORCH_INDEX_URL])
            return True
    return False


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
    _clear_optional_failure_state()
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
    _run_command(
        [str(PYTHON_BIN), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
        retries=1,
    )

    install_target = ".[audio]" if profile in {CORE_PROFILE, MUSICGEN_PROFILE} else "."
    command = [str(PYTHON_BIN), "-m", "pip", "install"]
    if upgrade:
        command.append("--upgrade")
    used_pytorch_index = _maybe_add_pytorch_index(command, [install_target])
    if used_pytorch_index:
        _debug("Using the official PyTorch wheel index to resolve audio dependencies.")
    command.append(install_target)

    _debug("Installing project dependencies – this might take a while on first launch …")
    _run_command(command, cwd=PROJECT_ROOT, retries=1)

    _, optional_requirements = _runtime_requirements_for_current_python(profile)
    if optional_requirements:
        _debug(
            "Attempting to install optional MusicGen helpers automatically. Failures are logged but never block launch."
        )
        _install_optional_packages(optional_requirements.values(), upgrade=upgrade)

    if profile == MUSICGEN_PROFILE:
        _debug(
            "MusicGen dependencies are bundled with the core install – skipping legacy extras installer."
        )

    DEPS_SENTINEL.touch()
    _write_installed_profile(profile)
    _ensure_runtime_requirements(profile=profile, upgrade=upgrade)
    _ensure_ffmpeg_available()
    if profile == MUSICGEN_PROFILE:
        _ensure_spacy_language_model()


def _detect_missing_modules(requirements: dict[str, str]) -> list[str]:
    missing: list[str] = []
    for module_name, pip_name in requirements.items():
        if importlib.util.find_spec(module_name) is None:
            missing.append(pip_name)
    return missing


def _runtime_requirements_for_current_python(profile: str) -> tuple[dict[str, str], dict[str, str]]:
    requirements = dict(CORE_RUNTIME_REQUIREMENTS)
    optional_requirements = dict(BEST_EFFORT_RUNTIME_REQUIREMENTS)

    if profile == MUSICGEN_PROFILE:
        requirements.update(MUSICGEN_RUNTIME_REQUIREMENTS)

    if sys.version_info >= (3, 12):
        _debug(
            "Python 3.12 detected – optional MusicGen dependencies will be attempted automatically. Installation failures are non-fatal."
        )

    return requirements, optional_requirements


def _ensure_runtime_requirements(*, profile: str, upgrade: bool) -> None:
    requirements, optional_requirements = _runtime_requirements_for_current_python(profile)

    missing_core = _detect_missing_modules(requirements)
    if missing_core:
        command = [str(PYTHON_BIN), "-m", "pip", "install"]
        if upgrade:
            command.append("--upgrade")
        normalized_missing = sorted(set(missing_core))
        used_pytorch_index = _maybe_add_pytorch_index(command, normalized_missing)
        if used_pytorch_index:
            _debug("Using the official PyTorch wheel index for required runtime modules.")
        command.extend(normalized_missing)
        _debug(f"Installing required runtime modules: {', '.join(sorted(set(missing_core)))}")
        _run_command(command, retries=1)
    else:
        _debug("Verified core Python packages are present.")

    missing_optional = _detect_missing_modules(optional_requirements)
    if missing_optional:
        _debug(
            "Attempting to install optional AI helpers: "
            + ", ".join(sorted(set(missing_optional)))
        )
        _install_optional_packages(missing_optional, upgrade=upgrade)
    else:
        _remove_optional_failures(optional_requirements.values())


def _load_optional_failure_state() -> set[str]:
    if not OPTIONAL_FAILURES_SENTINEL.exists():
        return set()
    try:
        data = json.loads(OPTIONAL_FAILURES_SENTINEL.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):  # pragma: no cover - best effort
        return set()
    if isinstance(data, list):
        return {str(item) for item in data if str(item)}
    return set()


def _save_optional_failure_state(packages: set[str]) -> None:
    if not packages:
        OPTIONAL_FAILURES_SENTINEL.unlink(missing_ok=True)
        return
    OPTIONAL_FAILURES_SENTINEL.parent.mkdir(parents=True, exist_ok=True)
    OPTIONAL_FAILURES_SENTINEL.write_text(
        json.dumps(sorted(packages)), encoding="utf-8"
    )


def _record_optional_failures(packages: Iterable[str]) -> None:
    state = _load_optional_failure_state()
    state.update({package for package in packages if package})
    _save_optional_failure_state(state)


def _remove_optional_failures(packages: Iterable[str]) -> None:
    state = _load_optional_failure_state()
    removed = False
    for package in packages:
        if package in state:
            state.remove(package)
            removed = True
    if removed:
        _save_optional_failure_state(state)


def _clear_optional_failure_state() -> None:
    OPTIONAL_FAILURES_SENTINEL.unlink(missing_ok=True)


def _install_optional_packages(packages: Iterable[str], *, upgrade: bool) -> None:
    unique = sorted({package for package in packages if package})
    if not unique:
        return

    command = [str(PYTHON_BIN), "-m", "pip", "install"]
    if upgrade:
        command.append("--upgrade")
    used_pytorch_index = _maybe_add_pytorch_index(command, unique)
    if used_pytorch_index:
        _debug("Using the official PyTorch wheel index for optional AI helpers.")
    command.extend(unique)

    try:
        _run_command(command, retries=1)
    except LauncherError as exc:
        _debug(
            "Optional dependency installation failed but will be ignored: "
            + ", ".join(unique)
        )
        _record_optional_failures(unique)
        _debug(str(exc))
    else:
        _remove_optional_failures(unique)


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


def _ensure_ffmpeg_available() -> Path | None:
    if FFMPEG_SENTINEL.exists():
        try:
            cached = Path(FFMPEG_SENTINEL.read_text(encoding="utf-8").strip())
        except OSError:
            cached = None
        else:
            if cached and cached.exists():
                return cached
        FFMPEG_SENTINEL.unlink(missing_ok=True)

    ffmpeg_path_str = shutil.which("ffmpeg")
    if ffmpeg_path_str:
        ffmpeg_path = Path(ffmpeg_path_str)
        FFMPEG_SENTINEL.write_text(str(ffmpeg_path), encoding="utf-8")
        return ffmpeg_path

    try:
        import imageio_ffmpeg
    except ImportError:
        _debug("imageio-ffmpeg missing – installing automatically …")
        try:
            _run_command([str(PYTHON_BIN), "-m", "pip", "install", "imageio-ffmpeg"], retries=1)
        except LauncherError as exc:  # pragma: no cover - best effort
            _debug(
                "Automatic imageio-ffmpeg installation failed; continuing without automatic ffmpeg provisioning."
            )
            FFMPEG_SENTINEL.unlink(missing_ok=True)
            return None
        try:
            import imageio_ffmpeg  # type: ignore  # noqa: F401
        except ImportError:  # pragma: no cover - defensive
            _debug(
                "imageio-ffmpeg still unavailable after installation; continuing without automatic ffmpeg provisioning."
            )
            FFMPEG_SENTINEL.unlink(missing_ok=True)
            return None

    try:
        ffmpeg_path = Path(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:  # pragma: no cover - best effort
        _debug(
            "Automatic ffmpeg download failed; continuing without bundled ffmpeg."
        )
        FFMPEG_SENTINEL.unlink(missing_ok=True)
        return None

    if not ffmpeg_path.exists():  # pragma: no cover - defensive
        _debug(
            "Downloaded ffmpeg path not found; continuing without bundled ffmpeg."
        )
        FFMPEG_SENTINEL.unlink(missing_ok=True)
        return None

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
    env[OPTIONAL_FAILURES_ENV_VAR] = str(OPTIONAL_FAILURES_SENTINEL)

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
            "Deprecated compatibility flag. MusicGen dependencies install automatically; "
            "use this to force downloading the spaCy language model."
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
