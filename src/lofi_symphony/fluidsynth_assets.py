"""Helpers for locating bundled FluidSynth binaries and soundfonts."""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path
from typing import Iterable, Iterator

FLUIDSYNTH_ENV_VAR = "LOFI_SYMPHONY_FLUIDSYNTH"
SOUNDFONT_ENV_VAR = "LOFI_SYMPHONY_SOUNDFONT"


__all__ = [
    "FLUIDSYNTH_ENV_VAR",
    "SOUNDFONT_ENV_VAR",
    "resolve_fluidsynth_executable",
    "iter_bundled_candidates",
    "iter_bundled_soundfonts",
    "resolve_soundfont_path",
]


def _platform_tag() -> str | None:
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "windows":
        if machine in {"amd64", "x86_64"}:
            return "win-amd64"
    return None


def _package_vendor_root() -> Path:
    return Path(__file__).resolve().parent / "_vendor"


def _fluidsynth_vendor_root() -> Path:
    return _package_vendor_root() / "fluidsynth"


def _soundfont_vendor_root() -> Path:
    return _package_vendor_root() / "soundfonts"


def iter_bundled_candidates() -> Iterator[Path]:
    """Yield possible FluidSynth executables bundled with the package."""

    exe_name = "fluidsynth.exe" if os.name == "nt" else "fluidsynth"
    tag = _platform_tag()

    if tag is not None:
        candidate = _fluidsynth_vendor_root() / tag / "bin" / exe_name
        if candidate.exists():
            yield candidate


def _iter_configured_locations() -> Iterable[Path]:
    override = os.getenv(FLUIDSYNTH_ENV_VAR)
    if override:
        override_path = Path(override)
        if override_path.exists():
            yield override_path

    yield from iter_bundled_candidates()


def resolve_fluidsynth_executable() -> str | None:
    """Return the path to a FluidSynth executable if one is available."""

    for candidate in _iter_configured_locations():
        if candidate.is_file():
            return str(candidate)

    located = shutil.which("fluidsynth")
    if located:
        return located

    return None


def iter_bundled_soundfonts() -> Iterator[Path]:
    """Yield bundled General MIDI soundfonts."""

    for path in _soundfont_vendor_root().glob("*.sf2"):
        if path.is_file():
            yield path


def _iter_soundfont_candidates(user_provided: str | None = None) -> Iterator[Path]:
    seen: set[Path] = set()

    def _yield(path: Path | None) -> Iterator[Path]:
        if path is None:
            return
        resolved = path.resolve()
        if resolved in seen:
            return
        if resolved.exists():
            seen.add(resolved)
            yield resolved

    if user_provided:
        yield from _yield(Path(user_provided))

    env_override = os.getenv(SOUNDFONT_ENV_VAR)
    if env_override:
        yield from _yield(Path(env_override))

    for bundled in iter_bundled_soundfonts():
        yield from _yield(bundled)

    default_locations = [
        Path("/usr/share/sounds/sf2/FluidR3_GM.sf2"),
        Path("/usr/share/soundfonts/default.sf2"),
        Path.cwd() / "default.sf2",
    ]
    for location in default_locations:
        yield from _yield(location)


def resolve_soundfont_path(preferred: str | None = None) -> str | None:
    """Return the path to an available soundfont, if any."""

    for candidate in _iter_soundfont_candidates(preferred):
        if candidate.is_file():
            return str(candidate)
    return None
