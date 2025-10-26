"""Tests for launcher optional dependency handling."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import launcher


def test_optional_dependency_failure_is_non_fatal(monkeypatch, tmp_path):
    sentinel = tmp_path / "optional_failures.json"
    monkeypatch.setattr(launcher, "OPTIONAL_FAILURES_SENTINEL", sentinel)

    def fake_runtime_requirements(profile: str):
        return ({"streamlit": "streamlit"}, {"torch": "torch==2.1.2"})

    def fake_detect_missing(requirements: dict[str, str]):
        if "streamlit" in requirements.values():
            return []
        return list(requirements.values())

    def fake_run_command(command, **kwargs):
        if "torch==2.1.2" in command:
            raise launcher.LauncherError("pip failed")
        return None

    monkeypatch.setattr(launcher, "_runtime_requirements_for_current_python", fake_runtime_requirements)
    monkeypatch.setattr(launcher, "_detect_missing_modules", fake_detect_missing)
    monkeypatch.setattr(launcher, "_run_command", fake_run_command)

    launcher._ensure_runtime_requirements(profile=launcher.CORE_PROFILE, upgrade=False)

    assert sentinel.exists(), "Optional failure sentinel should be recorded"
    assert json.loads(sentinel.read_text()) == ["torch==2.1.2"]
