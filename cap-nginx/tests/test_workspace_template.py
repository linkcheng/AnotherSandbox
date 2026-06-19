"""T051: nginx.workspace.conf.tmpl contract test。contracts/trusted-headers §2, research.md R4/R8。"""
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "nginx.workspace.conf.tmpl"


def _content() -> str:
    return TEMPLATE.read_text()


def test_template_has_auth_request_target():
    c = _content()
    assert "auth_request /_auth" in c
    assert "location = /_auth" in c
    assert "internal;" in c
    assert "proxy_pass http://host.docker.internal" in c
    assert "/api/v1/verify" in c


def test_template_captures_and_forwards_trusted_headers():
    c = _content()
    # auth_request_set 捕获
    assert "auth_request_set $x_user_id $upstream_http_x_user_id" in c
    assert "auth_request_set $x_workspace_id $upstream_http_x_workspace_id" in c
    assert "auth_request_set $x_permissions $upstream_http_x_permissions" in c
    # proxy_set_header 覆盖注入（防伪造）
    for h in ("X-User-Id", "X-Workspace-Id", "X-Permissions"):
        assert f"proxy_set_header {h}" in c


def test_template_has_fail_closed_branch():
    c = _content()
    assert "@auth_closed" in c
    assert "return 403" in c
    assert "error_page 500 502 503 504 = @auth_closed" in c


def test_template_forwards_authorization_to_verify():
    c = _content()
    assert "proxy_set_header Authorization $http_authorization" in c
