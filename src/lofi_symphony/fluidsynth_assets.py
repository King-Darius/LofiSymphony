"""Helpers for locating bundled FluidSynth binaries and soundfonts."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator
from urllib.error import URLError
from urllib.request import urlopen

FLUIDSYNTH_ENV_VAR = "LOFI_SYMPHONY_FLUIDSYNTH"
SOUNDFONT_ENV_VAR = "LOFI_SYMPHONY_SOUNDFONT"


__all__ = [
    "FLUIDSYNTH_ENV_VAR",
    "SOUNDFONT_ENV_VAR",
    "resolve_fluidsynth_executable",
    "iter_bundled_candidates",
    "iter_bundled_soundfonts",
    "resolve_soundfont_path",
    "SoundfontSource",
    "recommended_soundfonts",
    "download_soundfont",
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


_USER_SOUNDFONT_DIR = Path.home() / ".lofi_symphony" / "soundfonts"


@dataclass(frozen=True)
class SoundfontSource:
    """Metadata describing a curated, downloadable soundfont."""

    slug: str
    name: str
    filename: str
    url: str
    sha256: str
    size_mb: float
    license: str

    def size_label(self) -> str:
        return f"{self.size_mb:.1f} MB"


_RECOMMENDED_SOUNDFONTS: tuple[SoundfontSource, ...] = (
    SoundfontSource(
        slug="timgm6mb",
        name="TimGM6mb",
        filename="TimGM6mb.sf2",
        url="https://raw.githubusercontent.com/craffel/pretty-midi/main/pretty_midi/TimGM6mb.sf2",
        sha256="82475b91a76de15cb28a104707d3247ba932e228bada3f47bba63c6b31aaf7a1",
        size_mb=5.7,
        license="GPL-2.0",
    ),
    SoundfontSource(
        slug="fluidr3mono",
        name="FluidR3Mono GM (SF3)",
        filename="FluidR3Mono_GM.sf3",
        url="https://github.com/musescore/MuseScore/raw/master/share/sound/FluidR3Mono_GM.sf3",
        sha256="2aacd036d7058d40a371846ef2f5dc5f130d648ab3837fe2626591ba49a71254",
        size_mb=22.6,
        license="GPL-2.0",
    ),
)


def recommended_soundfonts() -> tuple[SoundfontSource, ...]:
    """Return curated soundfont downloads that the UI can surface."""

    return _RECOMMENDED_SOUNDFONTS


def _iter_user_soundfonts() -> Iterator[Path]:
    directory = _USER_SOUNDFONT_DIR
    if not directory.exists():
        return
    for path in sorted(directory.glob("*.sf[23]")):
        if path.is_file():
            yield path


def download_soundfont(
    source: SoundfontSource,
    *,
    destination_dir: Path | None = None,
    progress_hook: Callable[[int, int], None] | None = None,
) -> Path:
    """Download a curated soundfont, verifying its checksum before installing."""

    dest_dir = destination_dir or _USER_SOUNDFONT_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    target_path = dest_dir / source.filename

    if target_path.exists():
        if hashlib.sha256(target_path.read_bytes()).hexdigest() == source.sha256:
            return target_path
        target_path.unlink()

    with tempfile.NamedTemporaryFile(suffix=Path(source.filename).suffix, delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        try:
            response = urlopen(source.url)
        except URLError as exc:  # pragma: no cover - network failure surface
            raise RuntimeError(f"Failed to download {source.name}: {exc}") from exc

        with response, tmp_path.open("wb") as downloaded:
            content_length = response.headers.get("Content-Length")
            total_bytes = int(content_length) if content_length else 0
            read_bytes = 0
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                downloaded.write(chunk)
                read_bytes += len(chunk)
                if progress_hook:
                    progress_hook(read_bytes, total_bytes)

        actual_sha256 = hashlib.sha256(tmp_path.read_bytes()).hexdigest()
        if actual_sha256 != source.sha256:
            raise RuntimeError(
                f"Checksum mismatch for {source.name}: expected {source.sha256}, got {actual_sha256}"
            )

        shutil.move(str(tmp_path), target_path)
        if progress_hook:
            progress_hook(read_bytes, read_bytes)
        return target_path
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
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

    for user_path in _iter_user_soundfonts():
        yield from _yield(user_path)

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
