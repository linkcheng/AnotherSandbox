"""T052: cap-agent auth 中间件双模式测试。contracts/cap-agent-auth-middleware.md §6。"""
from starlette.requests import Request
from starlette.testclient import TestClient
from fastapi import FastAPI

from cap_agent.core.auth import (
    BaseAuthMiddleware, Identity, NoAuthMiddleware, OrchestratorHeaderAuthMiddleware,
    build_auth_middleware,
)


def _make_app(mode: str) -> FastAPI:
    app = FastAPI()
    app.add_middleware(build_auth_middleware(mode))

    @app.get("/v1/health")
    def health():
        return {"status": "ok"}

    @app.get("/v1/secret")
    def secret(request: Request):
        return {"user_id": request.state.user.user_id}

    return app


def test_build_middleware_maps_mode():
    assert build_auth_middleware("orchestrator") is OrchestratorHeaderAuthMiddleware
    assert build_auth_middleware("none") is NoAuthMiddleware
    assert build_auth_middleware("unknown") is NoAuthMiddleware  # 兜底 none


def test_none_mode_allows_all_requests():
    with TestClient(_make_app("none")) as c:
        assert c.get("/v1/health").status_code == 200
        r = c.get("/v1/secret")
        assert r.status_code == 200  # none 放行
        assert r.json()["user_id"] is None  # 空 Identity


def test_orchestrator_mode_rejects_missing_headers():
    with TestClient(_make_app("orchestrator")) as c:
        assert c.get("/v1/health").status_code == 200  # health 仍公开
        assert c.get("/v1/secret").status_code == 401  # 缺可信 header


def test_orchestrator_mode_accepts_trusted_headers():
    app = _make_app("orchestrator")
    with TestClient(app) as c:
        r = c.get("/v1/secret", headers={
            "X-User-Id": "u-123",
            "X-Workspace-Id": "w-456",
            "X-Permissions": "owner",
        })
        assert r.status_code == 200
        assert r.json()["user_id"] == "u-123"


def test_orchestrator_mode_partial_headers_rejected():
    with TestClient(_make_app("orchestrator")) as c:
        # 仅一个 header → 401
        r = c.get("/v1/secret", headers={"X-User-Id": "u"})
        assert r.status_code == 401
