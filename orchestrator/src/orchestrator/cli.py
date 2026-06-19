"""orchestrator CLI（typer）。contracts/orchestrator-rest-api §6, spec SC-007。"""
from __future__ import annotations

import os
from pathlib import Path

import httpx
import typer

app = typer.Typer(help="AI 个人沙箱 Orchestrator CLI", no_args_is_help=True)
TOKEN_FILE = Path.home() / ".orchestrator" / "token"


def _base_url() -> str:
    return os.environ.get("ORCH_CLI_URL", "http://localhost:8000")


def _save_token(token: str) -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(token)


def _load_token() -> str | None:
    return TOKEN_FILE.read_text().strip() if TOKEN_FILE.exists() else None


def _headers() -> dict:
    t = _load_token()
    return {"Authorization": f"Bearer {t}"} if t else {}


@app.command()
def register(email: str, password: str) -> None:
    """注册新用户。"""
    r = httpx.post(f"{_base_url()}/api/v1/auth/register", json={"email": email, "password": password})
    typer.echo(r.text)


@app.command()
def login(email: str, password: str) -> None:
    """登录并把 token 存到 ~/.orchestrator/token。"""
    r = httpx.post(f"{_base_url()}/api/v1/auth/login", json={"email": email, "password": password})
    if r.status_code == 200:
        _save_token(r.json()["access_token"])
        typer.echo("logged in")
    else:
        typer.echo(f"login failed: {r.status_code} {r.text}", err=True)
        raise typer.Exit(1)


@app.command()
def create(name: str) -> None:
    """创建 workspace。"""
    r = httpx.post(f"{_base_url()}/api/v1/workspaces", json={"name": name}, headers=_headers())
    typer.echo(r.text)


@app.command()
def start(workspace_id: str) -> None:
    """启动 workspace。"""
    r = httpx.post(f"{_base_url()}/api/v1/workspaces/{workspace_id}/start", headers=_headers())
    typer.echo(r.text)


@app.command()
def stop(workspace_id: str) -> None:
    """停止 workspace。"""
    r = httpx.post(f"{_base_url()}/api/v1/workspaces/{workspace_id}/stop", headers=_headers())
    typer.echo(r.text)


@app.command(name="list")
def list_workspaces() -> None:
    """列出可见 workspace。"""
    r = httpx.get(f"{_base_url()}/api/v1/workspaces", headers=_headers())
    typer.echo(r.text)


def main() -> None:
    app()
