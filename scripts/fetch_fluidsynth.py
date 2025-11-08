"""Utilities for bundling the FluidSynth runtime and default soundfont."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

FLUIDSYNTH_VERSION = "2.5.1"
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

# Release asset mapping for supported build platforms. Each entry describes
# how to download and unpack a Fluidsynth runtime for that platform.
_PLATFORM_ASSETS: dict[tuple[str, str], dict[str, str]] = {
    ("windows", "amd64"): {
        "kind": "zip",
        "url": "https://github.com/FluidSynth/fluidsynth/releases/download/v2.5.1/fluidsynth-v2.5.1-win10-x64-cpp11.zip",
        "sha256": "ed6fab7422deb3efd1a06eba4ca00a60a9bab7704d9847123236ba4b0982c5e2",
        "tag": "win-amd64",
        "archive_subdir": "fluidsynth-v2.5.1-win10-x64-cpp11",
        "exe_subpath": "bin/fluidsynth.exe",
    },
    ("darwin", "arm64"): {
        "kind": "ghcr",
        "repo": "homebrew/core/fluid-synth",
        "digest": "sha256:bdb87a8be3469df871cda8a6807e035e2797cbc28a9957b3991eeae5e0575230",
        "sha256": "bdb87a8be3469df871cda8a6807e035e2797cbc28a9957b3991eeae5e0575230",
        "tag": "mac-arm64",
        "archive_subdir": "fluid-synth/2.5.1",
        "strip_components": 2,
        "exe_subpath": "bin/fluidsynth",
    },
    ("darwin", "amd64"): {
        "kind": "ghcr",
        "repo": "homebrew/core/fluid-synth",
        "digest": "sha256:711437e42b4d1c6f506e97a63ebf493e8a9a9ba81f86c5f07d2ff8bb7bd5d4fc",
        "sha256": "711437e42b4d1c6f506e97a63ebf493e8a9a9ba81f86c5f07d2ff8bb7bd5d4fc",
        "tag": "mac-x86_64",
        "archive_subdir": "fluid-synth/2.5.1",
        "strip_components": 2,
        "exe_subpath": "bin/fluidsynth",
    },
    ("linux", "amd64"): {
        "kind": "ghcr",
        "repo": "homebrew/core/fluid-synth",
        "digest": "sha256:6a515821bf33ce73bd71ca02a159047cb1f85391ca72b7559c98b00cccb6c2a9",
        "sha256": "6a515821bf33ce73bd71ca02a159047cb1f85391ca72b7559c98b00cccb6c2a9",
        "tag": "linux-x86_64",
        "archive_subdir": "fluid-synth/2.5.1",
        "strip_components": 2,
        "exe_subpath": "bin/fluidsynth",
    },
    ("linux", "arm64"): {
        "kind": "ghcr",
        "repo": "homebrew/core/fluid-synth",
        "digest": "sha256:cceb10adb79d0a87a4cadc2e8279dde0cf42c1cc09a971b43e248a43b402af62",
        "sha256": "cceb10adb79d0a87a4cadc2e8279dde0cf42c1cc09a971b43e248a43b402af62",
        "tag": "linux-arm64",
        "archive_subdir": "fluid-synth/2.5.1",
        "strip_components": 2,
        "exe_subpath": "bin/fluidsynth",
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
    if canonical in {"aarch64", "arm64"}:
        return "arm64"
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

    _verify_sha256(dest, expected_sha256)


def _verify_sha256(path: Path, expected: str) -> None:
    actual_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_sha256 != expected:
        raise RuntimeError(
            "FluidSynth archive checksum mismatch: "
            f"expected {expected}, got {actual_sha256}"
        )


def _download_ghcr_blob(repo: str, digest: str, dest: Path) -> None:
    token_url = f"https://ghcr.io/token?service=ghcr.io&scope=repository:{repo}:pull"
    try:
        with urlopen(token_url) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except URLError as exc:  # pragma: no cover - network failure surface
        raise RuntimeError(f"Failed to request GHCR token: {exc}") from exc

    token = payload.get("token")
    if not token:
        raise RuntimeError("Failed to retrieve authentication token for GHCR download")

    request = Request(
        f"https://ghcr.io/v2/{repo}/blobs/{digest}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.oci.image.layer.v1.tar+gzip",
        },
    )

    try:
        with urlopen(request) as response, dest.open("wb") as downloaded:
            shutil.copyfileobj(response, downloaded)
    except URLError as exc:  # pragma: no cover - network failure surface
        raise RuntimeError(f"Failed to download FluidSynth bottle: {exc}") from exc


def _extract_zip_archive(archive: Path, dest: Path, *, strip_components: int = 0) -> None:
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        if not members:
            raise RuntimeError("FluidSynth archive was empty")
        for info in members:
            normalized = info.filename.replace("\\", "/")
            parts = [part for part in normalized.split("/") if part]
            if strip_components:
                if len(parts) <= strip_components:
                    continue
                parts = parts[strip_components:]
            target_path = dest.joinpath(*parts) if parts else dest
            if info.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(info) as source, target_path.open("wb") as target:
                    shutil.copyfileobj(source, target)
                permissions = info.external_attr >> 16
                if permissions:
                    target_path.chmod(permissions)


def _extract_tar_archive(archive: Path, dest: Path, *, strip_components: int = 0) -> None:
    def _safe_join(member_name: str) -> Path:
        target = dest / member_name
        resolved = target.resolve()
        if dest not in resolved.parents and resolved != dest.resolve():
            raise RuntimeError("Unsafe path detected in FluidSynth archive extraction")
        return target

    with tarfile.open(archive, "r:*") as bundle:
        members = bundle.getmembers()
        if not members:
            raise RuntimeError("FluidSynth archive was empty")
        for member in members:
            path_parts = Path(member.name).parts
            if strip_components:
                if len(path_parts) <= strip_components:
                    continue
                member.name = str(Path(*path_parts[strip_components:]))
            else:
                member.name = str(Path(*path_parts))
            if not member.name:
                continue
            target_path = _safe_join(member.name)
            if member.isdir():
                target_path.mkdir(parents=True, exist_ok=True)
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            extracted = bundle.extractfile(member)
            if extracted is None:
                continue
            with extracted, target_path.open("wb") as out_file:
                shutil.copyfileobj(extracted, out_file)
            if member.mode:
                target_path.chmod(member.mode)


def _write_version_marker(dest: Path, *, version: str) -> None:
    marker = dest / "VERSION"
    marker.write_text(version, encoding="utf-8")


def _has_current_bundle(dest: Path, *, version: str, exe_subpath: str) -> bool:
    marker = dest / "VERSION"
    exe_path = dest / exe_subpath
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
    exe_subpath = asset["exe_subpath"]

    if _has_current_bundle(target_dir, version=FLUIDSYNTH_VERSION, exe_subpath=exe_subpath):
        if verbose:
            print(f"FluidSynth {FLUIDSYNTH_VERSION} already bundled at {target_dir}.")
        return target_dir / exe_subpath

    if verbose:
        print(f"Bundling FluidSynth {FLUIDSYNTH_VERSION} for {asset['tag']}...")

    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = Path(tmpdir) / "fluidsynth.pkg"
        kind = asset["kind"]
        if kind == "zip":
            _download_file(asset["url"], archive_path, expected_sha256=asset["sha256"])
        elif kind == "ghcr":
            _download_ghcr_blob(asset["repo"], asset["digest"], archive_path)
            _verify_sha256(archive_path, asset["sha256"])
        else:  # pragma: no cover - defensive guard for future kinds
            raise RuntimeError(f"Unsupported asset kind: {kind}")

        extract_dir = Path(tmpdir) / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)
        if kind == "zip":
            _extract_zip_archive(
                archive_path,
                extract_dir,
                strip_components=int(asset.get("strip_components", 0)),
            )
        else:
            _extract_tar_archive(
                archive_path,
                extract_dir,
                strip_components=int(asset.get("strip_components", 0)),
            )

        archive_subdir = asset.get("archive_subdir")
        source_root = extract_dir if not archive_subdir else extract_dir / archive_subdir

        if not source_root.exists():
            raise RuntimeError(f"FluidSynth archive did not contain expected path {archive_subdir}")

        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(source_root, target_dir)
        _write_version_marker(target_dir, version=FLUIDSYNTH_VERSION)

    bundled_exe = target_dir / exe_subpath
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
