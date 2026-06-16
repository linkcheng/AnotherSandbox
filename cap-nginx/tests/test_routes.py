"""cap-nginx nginx.conf 路由契约测试。

对应 spec.md FR-014；tasks.md T029；contracts/nginx-routes.md。
"""
from __future__ import annotations

import re
from pathlib import Path

NGINX_CONF = Path(__file__).parent.parent / "nginx.conf"


def read_conf() -> str:
    return NGINX_CONF.read_text()


# 期望的所有 location 前缀（contracts/nginx-routes.md 表 1）
EXPECTED_LOCATIONS = [
    "/novnc/",       # cap-browser:6080（静态文件 + WS）
    "/websockify",   # cap-browser:6080（WS only）
    "/terminal/",    # cap-terminal:7681（WS）
    "/code-server/", # cap-code:8081
    "/jupyter/",     # cap-jupyter:8888
    "/v1/",          # cap-agent:9000
    "/gui/",         # cap-agent:9000
    "/cdp/",         # cap-agent:9000（WS）
    "/auth/",        # cap-agent:9000
    "/mcp/sandbox/", # cap-mcp:8940
]


# 期望的上游映射
EXPECTED_UPSTREAMS = {
    "/code-server/": "cap-code:8081",
    "/jupyter/": "cap-jupyter:8888",
    "/v1/": "cap-agent:9000",
    "/gui/": "cap-agent:9000",
    "/mcp/sandbox/": "cap-mcp:8940",
}


def test_conf_file_exists() -> None:
    assert NGINX_CONF.exists(), f"nginx.conf not found at {NGINX_CONF}"


def test_all_expected_locations_defined() -> None:
    """所有契约定义的 location 必须在 nginx.conf 中存在。"""
    conf = read_conf()
    for loc in EXPECTED_LOCATIONS:
        pattern = rf"location\s+{re.escape(loc)}\s*\{{"
        assert re.search(pattern, conf), f"缺少 location {loc}"


def test_upstream_mappings_correct() -> None:
    """每个反代 location 的 proxy_pass 指向上游容器。"""
    conf = read_conf()
    for loc, upstream in EXPECTED_UPSTREAMS.items():
        # 找到 location 块
        loc_pattern = rf"location\s+{re.escape(loc)}\s*\{{([^}}]+)\}}"
        match = re.search(loc_pattern, conf, re.DOTALL)
        assert match, f"location {loc} 块缺失"
        block = match.group(1)
        assert upstream in block, f"{loc} 未指向 {upstream}"


def test_websocket_locations_have_upgrade_headers() -> None:
    """WS location 必须设置 Upgrade/Connection header（FR-015）。"""
    conf = read_conf()
    ws_locations = ["/websockify", "/terminal/", "/cdp/"]
    for loc in ws_locations:
        loc_pattern = rf"location\s+{re.escape(loc)}\s*\{{([^}}]+)\}}"
        match = re.search(loc_pattern, conf, re.DOTALL)
        assert match, f"WS location {loc} 缺失"
        block = match.group(1)
        assert "proxy_http_version 1.1" in block, f"{loc} 缺少 proxy_http_version"
        assert "Upgrade" in block, f"{loc} 缺少 Upgrade header"
        assert "Connection" in block, f"{loc} 缺少 Connection header"
