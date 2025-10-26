from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import pytest

from lofi_symphony import audiocraft_integration as ai


class DummyMusicGenModel:
    sample_rate = 32000

    def __init__(self):
        self.params = None

    def set_generation_params(self, **kwargs):
        self.params = kwargs


class DummyMusicGenModule:
    call_count = 0

    class MusicGen:
        @staticmethod
        def get_pretrained(name, progress=True):
            DummyMusicGenModule.call_count += 1
            assert progress is True
            return DummyMusicGenModel()


def _reset_loader():
    ai.clear_cached_musicgen()
    DummyMusicGenModule.call_count = 0


def test_ensure_musicgen_assets_missing_module(monkeypatch):
    _reset_loader()

    def fake_import(name):
        raise ModuleNotFoundError('missing audiocraft')

    monkeypatch.setattr(ai.importlib, 'import_module', fake_import)

    with pytest.raises(ai.AudiocraftUnavailable):
        ai.ensure_musicgen_assets()


def test_ensure_musicgen_assets_downloads_once(monkeypatch):
    _reset_loader()

    def fake_import(name):
        assert name == 'audiocraft.models.musicgen'
        return DummyMusicGenModule

    monkeypatch.setattr(ai.importlib, 'import_module', fake_import)

    ai.ensure_musicgen_assets()
    ai.ensure_musicgen_assets()

    assert DummyMusicGenModule.call_count == 1
