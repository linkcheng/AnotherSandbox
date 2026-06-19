"""T023: 健康端点测试。/healthz unit 可测；/readyz 需 DB 归 integration。"""
from starlette.testclient import TestClient

from orchestrator.main import app


def test_healthz_returns_ok():
    with TestClient(app) as c:
        r = c.get("/healthz")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


def test_readyz_without_db_returns_503():
    # 无运行中的 PostgreSQL 时，readyz 应 fail-closed 返回 503
    with TestClient(app) as c:
        r = c.get("/readyz")
        assert r.status_code == 503
        assert r.json()["db"] == "unavailable"
