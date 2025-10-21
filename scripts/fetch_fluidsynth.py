"""Utilities for bundling the FluidSynth runtime and default soundfont."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

FLUIDSYNTH_VERSION = "2.3.3"
SOUNDFONT_VERSION = "TimGM6mb-1.3"
SOUNDFONT_FILENAME = "TimGM6mb.sf2"
SOUNDFONT_SHA256 = "82475b91a76de15cb28a104707d3247ba932e228bada3f47bba63c6b31aaf7a1"
SOUNDFONT_URL = (
    "https://raw.githubusercontent.com/craffel/pretty-midi/main/pretty_midi/TimGM6mb.sf2"
)

SOUNDFONT_SUMMARY = """TimGM6mb.sf2\n"""
"""General MIDI soundfont authored by Tim Brechbill and David Bolton.\n"""
"""Distributed under the GNU GPL v2. Bundled copy retrieved from the MuseScore\n"""
"""patch-set mirror at https://github.com/craffel/pretty-midi. See GPL-2.0.txt\n"""
"""in this directory for the full license text.\n"""

SKIP_SOUNDFONT_ENV = "LOFI_SYMPHONY_SKIP_SOUNDFONT"
GPL_LICENSE_BASENAME = "GPL-2.0.txt"

# Release asset mapping for supported build platforms. Extend this when
# additional prebuilt archives become available upstream.
_PLATFORM_ASSETS: dict[tuple[str, str], dict[str, str]] = {
    (
        "windows",
        "amd64",
    ): {
        "url": "https://github.com/FluidSynth/fluidsynth/releases/download/v2.3.3/fluidsynth-2.3.3-win10-x64.zip",
        "sha256": "a71f3b3022c2ac9917d1022a8f1e9abcdaba439c17a330c594633742be3b1588",
        "tag": "win-amd64",
        "exe_name": "fluidsynth.exe",
    },
}


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _package_vendor_root() -> Path:
    return _project_root() / "src" / "lofi_symphony" / "_vendor"


def _normalise_machine(raw: str) -> str:
    canonical = raw.lower()
    if canonical in {"x86_64", "amd64"}:
        return "amd64"
    return canonical


def _select_asset() -> dict[str, str] | None:
    system = platform.system().lower()
    machine = _normalise_machine(platform.machine())
    key = (system, machine)
    return _PLATFORM_ASSETS.get(key)


def _fluidsynth_vendor_root() -> Path:
    return _package_vendor_root() / "fluidsynth"


def _soundfont_vendor_root() -> Path:
    return _package_vendor_root() / "soundfonts"


def _licenses_root() -> Path:
    return _project_root() / "licenses"


def _download_file(url: str, dest: Path, *, expected_sha256: str) -> None:
    try:
        with urlopen(url) as response, dest.open("wb") as downloaded:
            shutil.copyfileobj(response, downloaded)
    except URLError as exc:  # pragma: no cover - network failure surface
        raise RuntimeError(f"Failed to download FluidSynth archive: {exc}") from exc

    actual_sha256 = hashlib.sha256(dest.read_bytes()).hexdigest()
    if actual_sha256 != expected_sha256:
        raise RuntimeError(
            "FluidSynth archive checksum mismatch: "
            f"expected {expected_sha256}, got {actual_sha256}"
        )


def _extract_windows_zip(archive: Path, dest: Path) -> None:
    """Extract the ``bin/`` directory from a FluidSynth Windows archive."""

    with zipfile.ZipFile(archive) as bundle:
        extracted_any = False

        for info in bundle.infolist():
            normalized = info.filename.replace("\\", "/")
            parts = [part for part in normalized.split("/") if part]
            if not parts:
                continue

            try:
                bin_index = parts.index("bin")
            except ValueError:
                continue

            relative_parts = parts[bin_index:]
            if not relative_parts:
                continue

            target_path = dest.joinpath(*relative_parts)
            if info.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(info) as source, target_path.open("wb") as target:
                    shutil.copyfileobj(source, target)

                permissions = info.external_attr >> 16
                if permissions:
                    target_path.chmod(permissions)

            extracted_any = True

        if not extracted_any:
            # ``ensure_fluidsynth_bundle`` will surface a clearer error message, but
            # raising here keeps the temporary extraction directory clean in tests.
            raise RuntimeError("FluidSynth archive did not contain a bin/ directory")


def _write_version_marker(dest: Path, *, version: str) -> None:
    marker = dest / "VERSION"
    marker.write_text(version, encoding="utf-8")


def _has_current_bundle(dest: Path, *, version: str, exe_name: str) -> bool:
    marker = dest / "VERSION"
    exe_path = dest / "bin" / exe_name
    return marker.exists() and exe_path.exists() and marker.read_text(encoding="utf-8").strip() == version


def ensure_fluidsynth_bundle(*, verbose: bool = True) -> Path | None:
    """Download and cache the FluidSynth runtime for supported platforms."""

    asset = _select_asset()
    vendor_root = _fluidsynth_vendor_root()
    vendor_root.mkdir(parents=True, exist_ok=True)

    if asset is None:
        if verbose:
            print("Skipping FluidSynth bundling: no prebuilt asset configured for this platform.")
        return None

    target_dir = vendor_root / asset["tag"]
    exe_name = asset["exe_name"]

    if _has_current_bundle(target_dir, version=FLUIDSYNTH_VERSION, exe_name=exe_name):
        if verbose:
            print(f"FluidSynth {FLUIDSYNTH_VERSION} already bundled at {target_dir}.")
        return target_dir / "bin" / exe_name

    if verbose:
        print(f"Bundling FluidSynth {FLUIDSYNTH_VERSION} for {asset['tag']}...")

    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = Path(tmpdir) / "fluidsynth.zip"
        _download_file(asset["url"], archive_path, expected_sha256=asset["sha256"])

        extract_dir = Path(tmpdir) / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)
        _extract_windows_zip(archive_path, extract_dir)

        # The archive ships DLLs alongside the executable in bin/. Preserve that layout.
        bin_source = extract_dir / "bin"
        if not bin_source.exists():
            raise RuntimeError("FluidSynth archive did not contain a bin/ directory")

        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_bin = target_dir / "bin"
        shutil.copytree(bin_source, target_bin)
        _write_version_marker(target_dir, version=FLUIDSYNTH_VERSION)

    bundled_exe = target_dir / "bin" / exe_name
    if not bundled_exe.exists():
        raise RuntimeError(f"Expected FluidSynth executable was not written to {bundled_exe}")

    if verbose:
        print(f"FluidSynth runtime written to {bundled_exe}.")

    return bundled_exe


def _soundfont_target_path() -> Path:
    return _soundfont_vendor_root() / SOUNDFONT_FILENAME


def _soundfont_version_marker() -> Path:
    return _soundfont_vendor_root() / "VERSION"


def _has_current_soundfont() -> bool:
    target = _soundfont_target_path()
    if not target.exists():
        return False
    actual_sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
    if actual_sha256 != SOUNDFONT_SHA256:
        return False
    marker = _soundfont_version_marker()
    return marker.exists() and marker.read_text(encoding="utf-8").strip() == SOUNDFONT_VERSION


def _write_soundfont_metadata() -> None:
    dest_dir = _soundfont_vendor_root()
    dest_dir.mkdir(parents=True, exist_ok=True)

    summary_path = dest_dir / f"{SOUNDFONT_FILENAME}.LICENSE"
    summary_path.write_text(SOUNDFONT_SUMMARY.strip() + "\n", encoding="utf-8")

    gpl_source = _licenses_root() / GPL_LICENSE_BASENAME
    gpl_dest = dest_dir / GPL_LICENSE_BASENAME
    if gpl_source.exists():
        shutil.copyfile(gpl_source, gpl_dest)

    _soundfont_version_marker().write_text(SOUNDFONT_VERSION, encoding="utf-8")


def ensure_soundfont_bundle(*, verbose: bool = True) -> Path | None:
    """Ensure the default TimGM6mb soundfont is cached alongside the package."""

    if os.getenv(SKIP_SOUNDFONT_ENV):
        if verbose:
            print(
                "Skipping soundfont bundling: LOFI_SYMPHONY_SKIP_SOUNDFONT is set."
            )
        return None

    dest_dir = _soundfont_vendor_root()
    dest_dir.mkdir(parents=True, exist_ok=True)
    target_path = _soundfont_target_path()

    if _has_current_soundfont():
        if verbose:
            print(f"Soundfont {SOUNDFONT_VERSION} already cached at {target_path}.")
        _write_soundfont_metadata()
        return target_path

    if verbose:
        print(f"Bundling default soundfont {SOUNDFONT_VERSION}...")

    with tempfile.NamedTemporaryFile(suffix=".sf2", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        _download_file(SOUNDFONT_URL, tmp_path, expected_sha256=SOUNDFONT_SHA256)
        if target_path.exists():
            target_path.unlink()
        shutil.move(str(tmp_path), target_path)
        _write_soundfont_metadata()
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    if verbose:
        print(f"Soundfont written to {target_path}.")

    return target_path


def ensure_audio_assets(*, verbose: bool = True) -> tuple[Path | None, Path | None]:
    """Bundle FluidSynth binaries and the default soundfont where possible."""

    fluidsynth_path = ensure_fluidsynth_bundle(verbose=verbose)
    soundfont_path = ensure_soundfont_bundle(verbose=verbose)
    return fluidsynth_path, soundfont_path


if __name__ == "__main__":
    fs_path, sf2_path = ensure_audio_assets(verbose=True)
    if not fs_path:
        print("No FluidSynth asset was bundled.")
    if not sf2_path:
        print("No soundfont asset was bundled.")
