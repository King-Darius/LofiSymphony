from types import SimpleNamespace

import pytest

from lofi_symphony import cli


def test_smoke_test_branch_invokes_smoke(monkeypatch):
    called = SimpleNamespace(smoke=False, launch=False)

    def fake_smoke(timeout=5.0):
        called.smoke = True
        assert timeout == 5.0

    def fake_launch(*, streamlit_args=None, app_path=None):  # pragma: no cover - should not run
        called.launch = True

    monkeypatch.setattr(cli, "_run_smoke_test", fake_smoke)
    monkeypatch.setattr(cli, "_launch_streamlit", fake_launch)

    cli.main(["--smoke-test"])

    assert called.smoke is True
    assert called.launch is False


@pytest.mark.parametrize(
    "argv, expected",
    [
        (["--", "--server.port", "9000"], ["--server.port", "9000"]),
        ([], []),
    ],
)
def test_main_forwards_streamlit_flags(monkeypatch, argv, expected):
    captured = {}

    def fake_launch(*, streamlit_args, app_path=None):
        captured["args"] = list(streamlit_args)

    def fail_smoke(*_, **__):  # pragma: no cover - defensive
        raise AssertionError("Smoke test should not run")

    monkeypatch.setattr(cli, "_launch_streamlit", fake_launch)
    monkeypatch.setattr(cli, "_run_smoke_test", fail_smoke)

    cli.main(argv)

    assert captured.get("args", []) == expected
