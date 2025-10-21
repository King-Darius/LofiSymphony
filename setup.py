from __future__ import annotations

import sys
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py
from setuptools.command.develop import develop as _develop
from setuptools.command.sdist import sdist as _sdist


def _ensure_audio_assets() -> None:
    # Import lazily to avoid importing project code when not required.
    fetcher_path = Path(__file__).resolve().parent / "scripts"
    sys_path_added = False
    try:
        if str(fetcher_path) not in sys.path:
            sys.path.insert(0, str(fetcher_path))
            sys_path_added = True
        from fetch_fluidsynth import ensure_audio_assets  # type: ignore

        ensure_audio_assets(verbose=False)
    finally:
        if sys_path_added:
            sys.path.remove(str(fetcher_path))


class build_py(_build_py):
    def run(self) -> None:  # noqa: D401 - setuptools API signature
        _ensure_audio_assets()
        super().run()


class develop(_develop):
    def run(self) -> None:  # noqa: D401 - setuptools API signature
        _ensure_audio_assets()
        super().run()


class sdist(_sdist):
    def run(self) -> None:  # noqa: D401 - setuptools API signature
        _ensure_audio_assets()
        super().run()


setup(cmdclass={"build_py": build_py, "develop": develop, "sdist": sdist})
