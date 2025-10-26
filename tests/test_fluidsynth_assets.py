from pathlib import Path
from types import SimpleNamespace
import sys
import hashlib
import io


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from lofi_symphony import fluidsynth_assets as assets


@pytest.fixture
def fake_vendor_root(tmp_path, monkeypatch):
    vendor_root = tmp_path / "_vendor"
    vendor_root.mkdir()
    monkeypatch.setattr(assets, "_package_vendor_root", lambda: vendor_root)
    monkeypatch.setattr(assets, "_USER_SOUNDFONT_DIR", tmp_path / "user_soundfonts")
    return vendor_root


def test_iter_bundled_candidates_windows(tmp_path, monkeypatch, fake_vendor_root):
    monkeypatch.setattr(assets, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(assets, "_platform_tag", lambda: "win-amd64")

    bin_dir = fake_vendor_root / "fluidsynth" / "win-amd64" / "bin"
    bin_dir.mkdir(parents=True)
    exe_path = bin_dir / "fluidsynth.exe"
    exe_path.write_text("")

    candidates = list(assets.iter_bundled_candidates())
    assert candidates == [exe_path]


def test_iter_bundled_soundfonts(fake_vendor_root):
    soundfont_dir = fake_vendor_root / "soundfonts"
    soundfont_dir.mkdir(parents=True)
    sf2_path = soundfont_dir / "TimGM6mb.sf2"
    sf2_path.write_text("")

    assert list(assets.iter_bundled_soundfonts()) == [sf2_path]


def test_resolve_fluidsynth_prefers_env_override(tmp_path, monkeypatch):
    override_path = tmp_path / "custom" / "fluidsynth.exe"
    override_path.parent.mkdir()
    override_path.write_text("")

    monkeypatch.setenv(assets.FLUIDSYNTH_ENV_VAR, str(override_path))
    try:
        assert assets.resolve_fluidsynth_executable() == str(override_path)
    finally:
        monkeypatch.delenv(assets.FLUIDSYNTH_ENV_VAR, raising=False)


def test_resolve_fluidsynth_falls_back_to_shutil(monkeypatch):
    monkeypatch.setattr(assets, "_iter_configured_locations", lambda: [])
    monkeypatch.setattr(assets.shutil, "which", lambda exe: "fake-path" if exe == "fluidsynth" else None)

    assert assets.resolve_fluidsynth_executable() == "fake-path"


def test_resolve_soundfont_prefers_argument(tmp_path, monkeypatch, fake_vendor_root):
    requested = tmp_path / "custom.sf2"
    requested.write_text("")
    env_override = tmp_path / "env.sf2"
    env_override.write_text("")
    monkeypatch.setenv(assets.SOUNDFONT_ENV_VAR, str(env_override))
    try:
        assert assets.resolve_soundfont_path(str(requested)) == str(requested)
    finally:
        monkeypatch.delenv(assets.SOUNDFONT_ENV_VAR, raising=False)


def test_resolve_soundfont_prefers_env(monkeypatch, tmp_path, fake_vendor_root):
    env_override = tmp_path / "env.sf2"
    env_override.write_text("")
    monkeypatch.setenv(assets.SOUNDFONT_ENV_VAR, str(env_override))
    try:
        assert assets.resolve_soundfont_path() == str(env_override)
    finally:
        monkeypatch.delenv(assets.SOUNDFONT_ENV_VAR, raising=False)


def test_resolve_soundfont_uses_bundled(fake_vendor_root):
    bundled_path = fake_vendor_root / "soundfonts" / "TimGM6mb.sf2"
    bundled_path.parent.mkdir(parents=True)
    bundled_path.write_text("")

    assert assets.resolve_soundfont_path() == str(bundled_path)


def test_resolve_soundfont_falls_back_to_default(tmp_path, monkeypatch, fake_vendor_root):
    monkeypatch.chdir(tmp_path)
    default_path = tmp_path / "default.sf2"
    default_path.write_text("")

    assert assets.resolve_soundfont_path() == str(default_path)


def test_resolve_soundfont_picks_user_directory(tmp_path, fake_vendor_root):
    user_dir = assets._USER_SOUNDFONT_DIR
    user_dir.mkdir(parents=True, exist_ok=True)
    user_font = user_dir / "custom.sf3"
    user_font.write_text("")

    assert assets.resolve_soundfont_path() == str(user_font)


def test_recommended_soundfonts_expose_curated_list():
    sources = assets.recommended_soundfonts()
    assert {source.slug for source in sources} >= {"timgm6mb", "fluidr3mono"}


class _FakeResponse(io.BytesIO):
    def __init__(self, payload: bytes):
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self):  # pragma: no cover - context protocol glue
        return self

    def __exit__(self, exc_type, exc, tb):  # pragma: no cover - context protocol glue
        return False


def test_download_soundfont_streams_and_verifies(tmp_path, monkeypatch):
    payload = b"sf2-bytes"
    checksum = hashlib.sha256(payload).hexdigest()
    source = assets.SoundfontSource(
        slug="test",
        name="Test Font",
        filename="test.sf2",
        url="https://example.com/test.sf2",
        sha256=checksum,
        size_mb=0.1,
        license="Test",
    )

    progress_updates: list[tuple[int, int]] = []

    def fake_urlopen(url: str):
        assert url == source.url
        return _FakeResponse(payload)

    monkeypatch.setattr(assets, "urlopen", fake_urlopen)

    target = assets.download_soundfont(
        source,
        destination_dir=tmp_path,
        progress_hook=lambda current, total: progress_updates.append((current, total)),
    )

    assert target == tmp_path / source.filename
    assert target.read_bytes() == payload
    assert progress_updates[-1] == (len(payload), len(payload))


def test_download_soundfont_skips_when_present(tmp_path, monkeypatch):
    payload = b"cached"
    checksum = hashlib.sha256(payload).hexdigest()
    source = assets.SoundfontSource(
        slug="cached",
        name="Cached Font",
        filename="cached.sf2",
        url="https://example.com/cached.sf2",
        sha256=checksum,
        size_mb=0.1,
        license="Test",
    )

    existing = tmp_path / source.filename
    existing.write_bytes(payload)

    def fail_urlopen(url: str):  # pragma: no cover - should not be called
        raise AssertionError("download attempted despite valid cache")

    monkeypatch.setattr(assets, "urlopen", fail_urlopen)

    result = assets.download_soundfont(source, destination_dir=tmp_path)
    assert result == existing


def test_download_soundfont_raises_on_checksum_mismatch(tmp_path, monkeypatch):
    payload = b"tampered"
    source = assets.SoundfontSource(
        slug="bad",
        name="Bad Font",
        filename="bad.sf2",
        url="https://example.com/bad.sf2",
        sha256="deadbeef",
        size_mb=0.1,
        license="Test",
    )

    monkeypatch.setattr(assets, "urlopen", lambda url: _FakeResponse(payload))

    with pytest.raises(RuntimeError) as excinfo:
        assets.download_soundfont(source, destination_dir=tmp_path)

    assert "Checksum mismatch" in str(excinfo.value)
    assert not (tmp_path / source.filename).exists()
