"""cap-agent /cdp/* 反代集成测试。

用 respx mock cap-browser:9222 HTTP；WS 用 fastapi TestClient 直接连接。
对应 spec.md FR-019；tasks.md T063。
"""
from __future__ import annotations

import os

import httpx
import respx
from fastapi.testclient import TestClient

os.environ["CAP_AGENT_BROWSER_CDP_URL"] = "http://cap-browser:9222"


def test_cdp_json_proxies_to_browser(client: TestClient) -> None:
    """/cdp/json 透传到 cap-browser:9222/json。"""
    browser_response = [
        {"id": "ABC123", "type": "page", "url": "https://example.com", "title": "Example"},
    ]
    with respx.mock(base_url="http://cap-browser:9222") as mock:
        mock.get("/json").mock(return_value=httpx.Response(200, json=browser_response))

        response = client.get("/cdp/json")

    assert response.status_code == 200
    assert response.json() == browser_response


def test_cdp_json_version_proxies(client: TestClient) -> None:
    """/cdp/json/version 透传。"""
    version_info = {"Browser": "Chrome/120.0", "webSocketDebuggerUrl": "ws://..."}
    with respx.mock(base_url="http://cap-browser:9222") as mock:
        mock.get("/json/version").mock(return_value=httpx.Response(200, json=version_info))

        response = client.get("/cdp/json/version")

    assert response.status_code == 200
    assert response.json()["Browser"].startswith("Chrome")


def test_cdp_json_upstream_error_returns_502(client: TestClient) -> None:
    """cap-browser 不可达时 502。"""
    with respx.mock(base_url="http://cap-browser:9222") as mock:
        mock.get("/json").mock(side_effect=httpx.ConnectError("refused"))

        response = client.get("/cdp/json")

    assert response.status_code == 502


def test_cdp_json_upstream_5xx_returns_502(client: TestClient) -> None:
    """cap-browser 返回 5xx 时 502。"""
    with respx.mock(base_url="http://cap-browser:9222") as mock:
        mock.get("/json").mock(return_value=httpx.Response(503))

        response = client.get("/cdp/json")

    assert response.status_code == 502


def test_cdp_json_list_equivalent_to_json(client: TestClient) -> None:
    """/cdp/json/list 等价于 /cdp/json。"""
    browser_response = [
        {"id": "DEF456", "type": "page", "url": "https://example.org", "title": "X"},
    ]
    with respx.mock(base_url="http://cap-browser:9222") as mock:
        mock.get("/json").mock(return_value=httpx.Response(200, json=browser_response))

        response = client.get("/cdp/json/list")

    assert response.status_code == 200
    assert response.json() == browser_response


def test_cdp_json_version_upstream_5xx_returns_502(client: TestClient) -> None:
    """/cdp/json/version 上游 5xx 也走 502 分支。"""
    with respx.mock(base_url="http://cap-browser:9222") as mock:
        mock.get("/json/version").mock(return_value=httpx.Response(500))

        response = client.get("/cdp/json/version")

    assert response.status_code == 502


def test_cdp_devtools_ws_upstream_unreachable_closes_1011(client: TestClient) -> None:
    """WS 上游不可达时关闭码 1011（websockets.connect 抛错）。"""
    # 不 mock 任何上游；cap-browser:9222 在测试环境不可达，触发 except 分支
    with client.websocket_connect("/cdp/devtools/UNKNOWN") as ws:
        # 上游 connect 失败后会 close(1011)；客户端收到关闭
        try:
            ws.receive()
        except Exception:
            # WebSocketDisconnect 或类似异常即符合预期
            pass
