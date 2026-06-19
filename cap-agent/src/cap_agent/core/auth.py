"""cap-agent 认证中间件：AUTH_MODE none/orchestrator 双模式。

contracts/cap-agent-auth-middleware.md, research.md R8。
P1（none）所有请求受信；P2（orchestrator）读 nginx 透传的可信 header。
业务路由代码零改动——仅 main.py 按 auth_mode 注册中间件。
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from pydantic import BaseModel


class Identity(BaseModel):
    user_id: str | None = None
    workspace_id: str | None = None
    permissions: str | None = None


class BaseAuthMiddleware(BaseHTTPMiddleware):
    PUBLIC_PATHS = {"/v1/health"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)
        identity = await self.authenticate(request)
        if identity is None:
            return JSONResponse(status_code=401, content={"error": {"code": "unauthorized"}})
        request.state.user = identity
        return await call_next(request)

    async def authenticate(self, request: Request) -> Identity | None:
        raise NotImplementedError


class NoAuthMiddleware(BaseAuthMiddleware):
    """P1 模式：所有请求受信，注入空 Identity。"""

    async def authenticate(self, request: Request) -> Identity | None:
        return Identity()


class OrchestratorHeaderAuthMiddleware(BaseAuthMiddleware):
    """P2 模式：读可信 header（缺一即 401，fail-closed）。"""

    REQUIRED = ("X-User-Id", "X-Workspace-Id", "X-Permissions")

    async def authenticate(self, request: Request) -> Identity | None:
        vals = {h: request.headers.get(h) for h in self.REQUIRED}
        if any(v is None for v in vals.values()):
            return None
        return Identity(
            user_id=vals["X-User-Id"],
            workspace_id=vals["X-Workspace-Id"],
            permissions=vals["X-Permissions"],
        )


def build_auth_middleware(mode: str) -> type[BaseAuthMiddleware]:
    if mode == "orchestrator":
        return OrchestratorHeaderAuthMiddleware
    return NoAuthMiddleware
