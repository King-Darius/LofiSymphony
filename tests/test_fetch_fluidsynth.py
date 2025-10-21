"""Tests for the FluidSynth bundling helper script."""

from __future__ import annotations

import importlib.util
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


def test_extract_windows_zip_handles_nested_prefix(tmp_path):
    script = _load_script()

    archive = tmp_path / "fluidsynth.zip"
    nested_prefix = "fluidsynth-2.3.3-win10-x64/"

    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(nested_prefix + "bin/", "")
        bundle.writestr(nested_prefix + "bin/fluidsynth.exe", b"binary-data")
        bundle.writestr(nested_prefix + "bin/somesynth.dll", b"dll-data")

    dest = tmp_path / "extracted"
    dest.mkdir()

    script._extract_windows_zip(archive, dest)

    exe_path = dest / "bin" / "fluidsynth.exe"
    dll_path = dest / "bin" / "somesynth.dll"

    assert exe_path.read_bytes() == b"binary-data"
    assert dll_path.read_bytes() == b"dll-data"


def test_extract_windows_zip_raises_when_missing_bin(tmp_path):
    script = _load_script()

    archive = tmp_path / "fluidsynth.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("fluidsynth-2.3.3/README.txt", "no bin here")

    dest = tmp_path / "extracted"
    dest.mkdir()

    with pytest.raises(RuntimeError, match="bin/ directory"):
        script._extract_windows_zip(archive, dest)
