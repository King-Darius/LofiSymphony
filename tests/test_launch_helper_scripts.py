"""Tests for the macOS command helper."""

from __future__ import annotations

import subprocess
from pathlib import Path


def test_macos_helper_waits_on_failure(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    helper_src = project_root / "Start Lofi Symphony.command"
    helper_copy = tmp_path / "Start.command"
    helper_copy.write_text(helper_src.read_text(encoding="utf-8"), encoding="utf-8")

    failing_launcher = tmp_path / "launcher.py"
    failing_launcher.write_text(
        "import sys\nprint('launcher failed')\nsys.exit(1)\n", encoding="utf-8"
    )

    result = subprocess.run(
        ["bash", str(helper_copy)],
        cwd=tmp_path,
        input="\n",
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "launcher failed" in result.stdout
    assert "Launch failed. Review the messages above for details." in result.stdout
