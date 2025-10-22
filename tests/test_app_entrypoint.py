"""Tests for running the Streamlit app as a standalone script."""

from __future__ import annotations

import importlib
import importlib.util
import shutil
import sys
from pathlib import Path


def _app_path() -> Path:
    return Path(__file__).resolve().parents[1] / "src" / "lofi_symphony" / "app.py"


def _remove_lofi_modules() -> dict[str, object]:
    saved: dict[str, object] = {}
    for name in list(sys.modules):
        if name == "lofi_symphony" or name.startswith("lofi_symphony."):
            saved[name] = sys.modules.pop(name)
    return saved


def _restore_lofi_modules(saved: dict[str, object]) -> None:
    active = [name for name in sys.modules if name == "lofi_symphony" or name.startswith("lofi_symphony.")]
    for name in active:
        sys.modules.pop(name, None)
    sys.modules.update(saved)


def _remove_sys_path_entry(entry: str) -> int | None:
    if entry in sys.path:
        index = sys.path.index(entry)
        sys.path.pop(index)
        return index
    return None


def _restore_sys_path_entry(entry: str, index: int | None) -> None:
    if entry in sys.path:
        sys.path.remove(entry)
    if index is not None:
        sys.path.insert(index, entry)


def test_app_script_sets_up_package_context():
    app_path = _app_path()
    src_root = app_path.parent.parent
    src_str = str(src_root)

    removed_index = _remove_sys_path_entry(src_str)
    saved_modules = _remove_lofi_modules()

    module_name = "standalone_lofi_app"
    spec = importlib.util.spec_from_file_location(module_name, app_path)
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)

        assert module.__package__ == "lofi_symphony"
        assert module.__spec__ is not None
        assert module.__spec__.name == "lofi_symphony.app"
        assert src_str in sys.path
        assert "lofi_symphony" in sys.modules
        assert sys.modules["lofi_symphony.app"] is module
    finally:
        sys.modules.pop(module_name, None)
        _restore_lofi_modules(saved_modules)
        _restore_sys_path_entry(src_str, removed_index)


def test_app_script_bootstraps_installed_layout(tmp_path: Path):
    project_root = Path(__file__).resolve().parents[1]
    package_src = project_root / "src" / "lofi_symphony"
    installed_root = tmp_path / "site-packages"
    package_dest = installed_root / "lofi_symphony"
    shutil.copytree(package_src, package_dest)

    app_path = package_dest / "app.py"
    site_packages_entry = str(installed_root)

    removed_entries: list[tuple[str, int | None]] = []
    for candidate in {site_packages_entry, str(project_root / "src"), str(project_root)}:
        removed_entries.append((candidate, _remove_sys_path_entry(candidate)))

    saved_modules = _remove_lofi_modules()

    module_name = "installed_lofi_app"
    spec = importlib.util.spec_from_file_location(module_name, app_path)
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)

        assert module.__package__ == "lofi_symphony"
        assert module.__spec__ is not None
        assert module.__spec__.name == "lofi_symphony.app"
        assert site_packages_entry in sys.path

        imported = importlib.import_module("lofi_symphony.audiocraft_integration")
        assert imported.__package__ == "lofi_symphony"
    finally:
        sys.modules.pop(module_name, None)
        _restore_lofi_modules(saved_modules)
        for entry, index in removed_entries:
            _restore_sys_path_entry(entry, index)
