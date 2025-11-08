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
