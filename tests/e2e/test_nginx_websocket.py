"""cap-nginx WebSocket 透传端到端测试。

对应 spec.md FR-015；tasks.md T071。
前置：`make up` 已启动完整 stack。
"""
from __future__ import annotations

import asyncio
import socket

import pytest

try:
    import websockets  # type: ignore[import-not-found]
    HAS_WS = True
except ImportError:  # pragma: no cover
    HAS_WS = False


@pytest.mark.skipif(not HAS_WS, reason="websockets 库未安装")
@pytest.mark.smoke
def test_terminal_ws_connects_via_nginx() -> None:
    """/terminal/ WS 路径透传到 cap-terminal:7681。

    验证 WS 握手成功（不验证业务数据，仅透传可达）。
    """

    async def _connect() -> None:
        async with websockets.connect("ws://localhost/terminal/", close_timeout=5) as ws:
            # 发送一个回车，验证连接活跃
            await ws.send(b"\r")
            # ttyd 应该响应（或静默接受）
            try:
                await asyncio.wait_for(ws.recv(), timeout=2.0)
            except asyncio.TimeoutError:
                pass  # 连接存在但无响应也算透传成功

    asyncio.run(_connect())


@pytest.mark.smoke
def test_websockify_ws_handshake_responds() -> None:
    """/websockify WS 路径握手有响应（101/4xx/5xx 都算 nginx 透传到上游）。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect(("localhost", 80))
        # 标准 WS Upgrade 握手请求
        req = (
            "GET /websockify HTTP/1.1\r\n"
            "Host: localhost\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        ).encode()
        sock.send(req)
        response = sock.recv(1024).decode("utf-8", errors="ignore")
    finally:
        sock.close()

    # 101（成功）/ 400（cap-browser websocat 未启动）/ 502（上游不可达）
    # 任一都说明 nginx 已透传到上游
    assert any(code in response for code in ("101", "400", "502")), \
        f"未预期的 WS 响应: {response[:200]}"
