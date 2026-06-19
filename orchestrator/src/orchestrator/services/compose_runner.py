"""docker compose 子进程封装（asyncio.create_subprocess_exec，非 shell=True）。research.md R7。"""
import asyncio
import os
from dataclasses import dataclass

TEMPLATE_FILE = "docker-compose.workspace.yml.tmpl"  # 相对 cwd（仓库根）


@dataclass
class ComposeResult:
    success: bool
    returncode: int
    stderr: str = ""


def workspace_env(
    slug: str, port: int, workspace_id, volume: str, orch_url: str,
    auth_mode: str, auth_failure: str,
) -> dict:
    return {
        "WORKSPACE_SLUG": slug,
        "WS_NGINX_PORT": str(port),
        "WORKSPACE_ID": str(workspace_id),
        "WORKSPACE_VOLUME": volume,
        "AUTH_MODE": auth_mode,
        "ORCHESTRATOR_URL": orch_url,
        "AUTH_FAILURE_MODE": auth_failure,
    }


async def _compose(args: list[str], project: str, env: dict, cwd: str) -> ComposeResult:
    # 非 shell：project/env 作为独立 argv / 环境变量，杜绝注入（R7）
    cmd = ["docker", "compose", "-p", project, "-f", TEMPLATE_FILE, *args]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, **env},
        cwd=cwd,
    )
    _, stderr = await proc.communicate()
    rc = proc.returncode or 0
    return ComposeResult(success=rc == 0, returncode=rc, stderr=stderr.decode(errors="replace"))


async def up(project: str, env: dict, cwd: str) -> ComposeResult:
    return await _compose(["up", "-d", "--wait"], project, env, cwd)


async def down(project: str, env: dict, cwd: str, volumes: bool = True) -> ComposeResult:
    v = ["-v"] if volumes else []
    return await _compose(["down", *v, "--remove-orphans"], project, env, cwd)


async def pause(project: str, env: dict, cwd: str) -> ComposeResult:
    return await _compose(["pause"], project, env, cwd)


async def unpause(project: str, env: dict, cwd: str) -> ComposeResult:
    return await _compose(["unpause"], project, env, cwd)
