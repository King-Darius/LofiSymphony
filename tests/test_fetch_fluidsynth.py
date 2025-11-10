"""Tests for the FluidSynth bundling helper script."""

from __future__ import annotations

import importlib.util
import io
import tarfile
import zipfile
from pathlib import Path

import pytest


def _load_script() -> object:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "fetch_fluidsynth.py"
    spec = importlib.util.spec_from_file_location("fetch_fluidsynth", script_path)
    if spec is None or spec.loader is None:  # pragma: no cover - importlib failure surface
        raise RuntimeError("Failed to load fetch_fluidsynth script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_zip_archive_strips_prefix(tmp_path):
    script = _load_script()

    archive = tmp_path / "fluidsynth.zip"
    nested_prefix = "fluidsynth-v2.5.1-win10-x64-cpp11/"

    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(nested_prefix + "bin/", "")
        bundle.writestr(nested_prefix + "bin/fluidsynth.exe", b"binary-data")
        bundle.writestr(nested_prefix + "bin/somesynth.dll", b"dll-data")

    dest = tmp_path / "extracted"
    dest.mkdir()

    script._extract_zip_archive(archive, dest, strip_components=1)

    exe_path = dest / "bin" / "fluidsynth.exe"
    dll_path = dest / "bin" / "somesynth.dll"

    assert exe_path.read_bytes() == b"binary-data"
    assert dll_path.read_bytes() == b"dll-data"


def test_extract_tar_archive_handles_strip_components(tmp_path):
    script = _load_script()

    archive = tmp_path / "bundle.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        data = b"exec"
        info = tarfile.TarInfo("fluid-synth/2.5.1/bin/fluidsynth")
        info.size = len(data)
        bundle.addfile(info, io.BytesIO(data))

    dest = tmp_path / "extracted"
    dest.mkdir()

    script._extract_tar_archive(archive, dest, strip_components=2)

    exe_path = dest / "bin" / "fluidsynth"
    assert exe_path.read_bytes() == b"exec"


def test_extract_tar_archive_preserves_symlinks(tmp_path):
    script = _load_script()

    archive = tmp_path / "bundle.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        target_data = b"shared-lib"
        lib_real = tarfile.TarInfo("fluid-synth/2.5.1/lib/libfluidsynth.so.3.5.0")
        lib_real.size = len(target_data)
        bundle.addfile(lib_real, io.BytesIO(target_data))

        lib_version = tarfile.TarInfo("fluid-synth/2.5.1/lib/libfluidsynth.so.3")
        lib_version.type = tarfile.SYMTYPE
        lib_version.linkname = "libfluidsynth.so.3.5.0"
        bundle.addfile(lib_version)

        lib_short = tarfile.TarInfo("fluid-synth/2.5.1/lib/libfluidsynth.so")
        lib_short.type = tarfile.SYMTYPE
        lib_short.linkname = "libfluidsynth.so.3"
        bundle.addfile(lib_short)

    dest = tmp_path / "extract"
    dest.mkdir()

    script._extract_tar_archive(archive, dest, strip_components=2)

    base = dest / "lib"
    real_path = base / "libfluidsynth.so.3.5.0"
    version_link = base / "libfluidsynth.so.3"
    short_link = base / "libfluidsynth.so"

    assert real_path.read_bytes() == b"shared-lib"
    assert version_link.exists()
    assert short_link.exists()

    if version_link.is_symlink():
        assert version_link.readlink() == Path("libfluidsynth.so.3.5.0")
    else:
        assert version_link.read_bytes() == real_path.read_bytes()

    if short_link.is_symlink():
        assert short_link.readlink() == Path("libfluidsynth.so.3")
    else:
        assert short_link.read_bytes() == real_path.read_bytes()


def test_extract_tar_archive_symlink_fallback_copies_after_members(tmp_path, monkeypatch):
    script = _load_script()

    archive = tmp_path / "bundle.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        lib_version = tarfile.TarInfo("fluid-synth/2.5.1/lib/libfluidsynth.so.3")
        lib_version.type = tarfile.SYMTYPE
        lib_version.linkname = "libfluidsynth.so.3.5.0"
        bundle.addfile(lib_version)

        target_data = b"shared-lib"
        lib_real = tarfile.TarInfo("fluid-synth/2.5.1/lib/libfluidsynth.so.3.5.0")
        lib_real.size = len(target_data)
        bundle.addfile(lib_real, io.BytesIO(target_data))

    dest = tmp_path / "extract"
    dest.mkdir()

    def _deny_symlinks(self, target, target_is_directory=False):
        raise OSError("symlinks disabled")

    monkeypatch.setattr(script.Path, "symlink_to", _deny_symlinks, raising=False)

    script._extract_tar_archive(archive, dest, strip_components=2)

    base = dest / "lib"
    target = base / "libfluidsynth.so.3"
    real_path = base / "libfluidsynth.so.3.5.0"

    assert target.exists()
    assert target.read_bytes() == real_path.read_bytes() == b"shared-lib"
