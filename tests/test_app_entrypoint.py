"""Tests for running the Streamlit app as a standalone script."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _app_path() -> Path:
    return Path(__file__).resolve().parents[1] / "src" / "lofi_symphony" / "app.py"


def test_app_script_sets_up_package_context():
    app_path = _app_path()
    src_root = app_path.parent.parent
    src_str = str(src_root)

    removed_index = None
    if src_str in sys.path:
        removed_index = sys.path.index(src_str)
        sys.path.pop(removed_index)

    saved_modules: dict[str, object] = {}
    for name in list(sys.modules):
        if name == "lofi_symphony" or name.startswith("lofi_symphony."):
            saved_modules[name] = sys.modules.pop(name)

    module_name = "standalone_lofi_app"
    spec = importlib.util.spec_from_file_location(module_name, app_path)
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)

        assert module.__package__ == "lofi_symphony"
        assert src_str in sys.path
        assert "lofi_symphony" in sys.modules
        assert sys.modules["lofi_symphony.app"] is module
    finally:
        sys.modules.pop(module_name, None)

        active_names = [
            name for name in sys.modules if name == "lofi_symphony" or name.startswith("lofi_symphony.")
        ]
        for name in active_names:
            sys.modules.pop(name, None)
        sys.modules.update(saved_modules)

        if src_str in sys.path:
            sys.path.remove(src_str)
        if removed_index is not None:
            sys.path.insert(removed_index, src_str)
