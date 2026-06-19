"""A. cap-nginx Phase5 渲染注入 unit 测试（批次3 遗留，research.md R6）。

验证：
1. render_workspace_nginx_conf 渲染 cap-nginx/nginx.workspace.conf.tmpl，
   把 ${ORCHESTRATOR_URL} / ${WORKSPACE_ID} / ${AUTH_FAILURE_MODE} 正确替换。
2. 输出文件位于 {workspace_volume_root}/{slug}/nginx.workspace.conf。
3. workspace_env 传入 nginx_conf_path 时注入 WORKSPACE_NGINX_CONF（compose 模板挂载点）；
   不传时缺省回落 /dev/null（compose 模板 ${WORKSPACE_NGINX_CONF:-/dev/null}，P1 兼容）。

compose_runner 零改动（FR-019）：本测试只验渲染纯函数 + env 字段。
"""
import pytest

from orchestrator.services import compose_runner
from orchestrator.services.workspace_compose import render_workspace_nginx_conf


def _fake_ws():
    """最小 workspace 替身（仅渲染所需字段）。"""

    class _Ws:
        slug = "alice-dev-abc123"
        id = "ws-uuid-001"

    return _Ws()


def _fake_settings(tmp_path, monkeypatch):
    """构造 settings：模板位于仓库根，volume_root 指向 tmp_path。"""
    from orchestrator.core import config

    # 仓库根 = orchestrator 包的祖父目录（cap-nginx/nginx.workspace.conf.tmpl 在此）
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    tmpl_dir = repo_root / "cap-nginx"
    tmpl_dir.mkdir()
    (tmpl_dir / "nginx.workspace.conf.tmpl").write_text(
        "# test template\n"
        "proxy_pass ${ORCHESTRATOR_URL}/api/v1/verify?workspace=${WORKSPACE_ID};\n"
        "error_page 500 = @auth_${AUTH_FAILURE_MODE};\n"
    )
    vol_root = tmp_path / "vols"
    vol_root.mkdir()

    s = config.Settings(
        workspace_volume_root=str(vol_root),
        orch_url="http://orch:8000",
        auth_failure_mode="fail-closed",
    )
    # workspace_compose 读取模板相对 cwd；用 monkeypatch 指向 repo_root
    monkeypatch.setattr(
        "orchestrator.services.workspace_compose._TEMPLATE_PATH",
        repo_root / "cap-nginx" / "nginx.workspace.conf.tmpl",
    )
    return s, vol_root


def test_render_substitutes_template_vars(tmp_path, monkeypatch):
    """渲染应正确替换 ORCHESTRATOR_URL / WORKSPACE_ID / AUTH_FAILURE_MODE。"""
    s, vol_root = _fake_settings(tmp_path, monkeypatch)
    ws = _fake_ws()

    out = render_workspace_nginx_conf(ws, s)

    text = out.read_text()
    assert "http://orch:8000/api/v1/verify?workspace=ws-uuid-001" in text
    assert "${" not in text  # 无残留占位
    assert "@auth_fail-closed" in text


def test_render_writes_under_volume_root(tmp_path, monkeypatch):
    """渲染产物必须落在 {volume_root}/{slug}/nginx.workspace.conf（便于审计/挂载）。"""
    s, vol_root = _fake_settings(tmp_path, monkeypatch)
    ws = _fake_ws()

    out = render_workspace_nginx_conf(ws, s)

    assert out == vol_root / ws.slug / "nginx.workspace.conf"
    assert out.exists()


def test_render_idempotent_overwrite(tmp_path, monkeypatch):
    """重复渲染覆盖旧文件（workspace 重启不残留陈旧 WORKSPACE_ID）。"""
    s, _ = _fake_settings(tmp_path, monkeypatch)
    ws = _fake_ws()

    first = render_workspace_nginx_conf(ws, s)
    first.write_text("STALE")
    second = render_workspace_nginx_conf(ws, s)
    assert "STALE" not in second.read_text()
    assert "ws-uuid-001" in second.read_text()


def test_workspace_env_includes_nginx_conf_when_provided():
    """传入 nginx_conf_path 时 env 含 WORKSPACE_NGINX_CONF（compose 模板挂载点）。"""
    env = compose_runner.workspace_env(
        "ws-alice", 8101, "wid", "/v", "http://h:8000", "orchestrator", "fail-closed",
        nginx_conf_path="/data/ws/nginx.workspace.conf",
    )
    assert env["WORKSPACE_NGINX_CONF"] == "/data/ws/nginx.workspace.conf"


def test_workspace_env_omits_nginx_conf_by_default():
    """不传时 env 不含 WORKSPACE_NGINX_CONF（compose 模板 ${VAR:-/dev/null} 回落，P1 兼容）。"""
    env = compose_runner.workspace_env(
        "ws-alice", 8101, "wid", "/v", "http://h:8000", "orchestrator", "fail-closed",
    )
    assert "WORKSPACE_NGINX_CONF" not in env
