"""T067: CLI 测试（mock httpx，token 本地存取）。SC-007。"""
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from orchestrator import cli

runner = CliRunner()


def test_login_saves_token(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "TOKEN_FILE", tmp_path / "token")
    with patch("orchestrator.cli.httpx.post") as post:
        post.return_value = Mock(status_code=200, json=lambda: {"access_token": "tok-xyz"})
        r = runner.invoke(cli.app, ["login", "a@b.c", "pw"])
    assert r.exit_code == 0
    assert (tmp_path / "token").read_text() == "tok-xyz"


def test_create_sends_bearer_header(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "TOKEN_FILE", tmp_path / "token")
    (tmp_path / "token").write_text("tok-xyz")
    with patch("orchestrator.cli.httpx.post") as post:
        post.return_value = Mock(status_code=201, text='{"id":"ws-1"}')
        r = runner.invoke(cli.app, ["create", "alice-dev"])
    assert r.exit_code == 0
    headers = post.call_args.kwargs.get("headers", {})
    assert headers["Authorization"] == "Bearer tok-xyz"


def test_login_failure_exits_nonzero(monkeypatch):
    monkeypatch.setattr(cli, "TOKEN_FILE", tmp_path := __import__("pathlib").Path("/tmp/_orch_cli_test"))
    with patch("orchestrator.cli.httpx.post") as post:
        post.return_value = Mock(status_code=401, text="bad", json=lambda: {})
        r = runner.invoke(cli.app, ["login", "a@b.c", "wrong"])
    assert r.exit_code == 1


def test_list_uses_token(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "TOKEN_FILE", tmp_path / "token")
    (tmp_path / "token").write_text("tok")
    with patch("orchestrator.cli.httpx.get") as get:
        get.return_value = Mock(status_code=200, text="[]")
        runner.invoke(cli.app, ["list"])
    assert get.call_args.kwargs["headers"]["Authorization"] == "Bearer tok"
