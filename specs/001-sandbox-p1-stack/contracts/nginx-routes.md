# Contract: cap-nginx 路由表

**Date**: 2026-06-18
**Source**: [spec.md](../spec.md) FR-005, FR-014, FR-015 · [research.md](../research.md) R6 · `.archive/sandbox-design.md` §4.2

cap-nginx 是唯一对外 HTTP 入口（设计原则五，FR-005），监听端口 80（可通过 `PORT` 切换）。所有外部请求经 nginx 反代到 sandbox-net 内的 cap-* 服务。本文档定义每个 location 块的路由契约与配置要点。

**通用约定**：
- 对外端口：80（默认）或 `${PORT}`
- 上游服务名即 DNS 名（compose service name）
- WebSocket 升级：noVNC、ttyd、CDP WS 三处需要
- 静态文件：noVNC（由 nginx 直接服务，不走 cap-browser）

---

## 1. 路由总览

| 前缀 | 上游 | 协议 | WebSocket | 说明 |
|------|------|------|-----------|------|
| `/novnc/` | 本地静态 | HTTP | 否 | noVNC 前端静态文件 |
| `/websockify` | cap-browser:6080 | WS | 是 | noVNC → VNC 的 WS 桥 |
| `/terminal/` | cap-terminal:7681 | HTTP+WS | 是 | ttyd Web Terminal |
| `/code-server/` | cap-code:8081 | HTTP | 可选 | code-server（含内部 WS） |
| `/jupyter/` | cap-jupyter:8888 | HTTP+WS | 是 | JupyterLab（kernel WS） |
| `/v1/` | cap-agent:9000 | HTTP | 否 | API（health、shell、file） |
| `/auth/` | cap-agent:9000 | HTTP | 否 | 鉴权（P1 保留，FR-NI-1 不实现） |
| `/gui/` | cap-agent:9000 | HTTP | 否 | GUI 截图与动作 |
| `/cdp/` | cap-agent:9000 | HTTP+WS | 是 | CDP 反代（含 `/cdp/devtools/*` WS） |
| `/mcp/sandbox/` | cap-mcp:8940 | HTTP | 否 | MCP Streamable HTTP |

---

## 2. 静态文件路由

### 2.1 `/novnc/`（noVNC 前端）

| 项 | 值 |
|----|-----|
| 类型 | 静态文件 alias |
| 路径 | `/usr/share/novnc/`（nginx 容器内） |
| 上游 | 无（本地） |
| WebSocket | 否 |
| 超时 | 默认 |

**配置要点**：
- alias 末尾必须带 `/`，否则路径拼接错误
- 入口文件 `vnc.html`（或 `vnc_lite.html`）
- 用户访问 `/novnc/` 后，前端 JS 发起 `/websockify` WS 连接

**示例片段**：

```nginx
location /novnc/ {
    alias /usr/share/novnc/;
    index vnc.html;
    try_files $uri $uri/ /novnc/vnc.html;
}
```

---

## 3. WebSocket 路由

> 所有 WS 路由必须显式设置 `proxy_http_version 1.1` 与 `Upgrade` / `Connection` header（FR-015，research.md R6）。

### 3.1 `/websockify`（noVNC → VNC 桥）

| 项 | 值 |
|----|-----|
| 上游 | `http://cap-browser:6080` |
| 协议 | WebSocket |
| read_timeout | `3600s`（长连接） |
| send_timeout | `3600s` |

**示例片段**：

```nginx
location /websockify {
    proxy_pass http://cap-browser:6080;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
}
```

### 3.2 `/terminal/`（ttyd）

| 项 | 值 |
|----|-----|
| 上游 | `http://cap-terminal:7681` |
| 协议 | HTTP + WebSocket（ttyd WS 在 `/terminal/ws`） |
| read_timeout | `7200s` |

**配置要点**：HTTP 与 WS 走同一 location，靠 Upgrade header 区分；ttyd 静态前端与 WS 端点都在 7681。

**示例片段**：

```nginx
location /terminal/ {
    proxy_pass http://cap-terminal:7681;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_set_header Host $host;
    proxy_read_timeout 7200s;
}
```

> `$connection_upgrade` 是 map 变量：`http` → `""`，`websocket` → `"upgrade"`，避免非 WS 请求被强升。

### 3.3 `/cdp/`（Chromium DevTools 协议）

| 项 | 值 |
|----|-----|
| 上游 | `http://cap-agent:9000` |
| 协议 | HTTP（`/cdp/json`）+ WebSocket（`/cdp/devtools/{id}`） |
| read_timeout | `3600s` |

**配置要点**：HTTP 与 WS 共用 location；cap-agent 内部再透传到 cap-browser:9222。

**示例片段**：

```nginx
location /cdp/ {
    proxy_pass http://cap-agent:9000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_set_header Host $host;
    proxy_read_timeout 3600s;
    # CDP WS 消息可能较大（截图 base64）
    proxy_buffering off;
}
```

### 3.4 `/jupyter/`（JupyterLab）

| 项 | 值 |
|----|-----|
| 上游 | `http://cap-jupyter:8888` |
| 协议 | HTTP + WebSocket（kernel comm） |
| read_timeout | `3600s` |

**配置要点**：Jupyter 的 kernel WS 走 `/jupyter/api/kernels/{id}/channels`，与 HTTP API 同前缀；必须 `proxy_buffering off` 否则 kernel 输出延迟。

**示例片段**：

```nginx
location /jupyter/ {
    proxy_pass http://cap-jupyter:8888;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 3600s;
    proxy_buffering off;
}
```

### 3.5 `/code-server/`（code-server）

| 项 | 值 |
|----|-----|
| 上游 | `http://cap-code:8081` |
| 协议 | HTTP + WebSocket（terminal、live share） |
| read_timeout | `7200s` |

**配置要点**：code-server 内部 WS 走相对路径，nginx 转发即可。

**示例片段**：

```nginx
location /code-server/ {
    proxy_pass http://cap-code:8081;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_set_header Host $host;
    proxy_read_timeout 7200s;
}
```

---

## 4. 纯 HTTP 路由

### 4.1 `/v1/`（cap-agent API）

| 项 | 值 |
|----|-----|
| 上游 | `http://cap-agent:9000` |
| 协议 | HTTP |
| connect_timeout | `5s` |
| read_timeout | `120s`（shell exec 可能慢） |

**配置要点**：路径透传到 cap-agent；上游路径保留 `/v1/` 前缀。

**示例片段**：

```nginx
location /v1/ {
    proxy_pass http://cap-agent:9000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 120s;
    client_max_body_size 2g;   # /v1/file/upload 大文件
}
```

### 4.2 `/gui/`（GUI 截图与动作）

| 项 | 值 |
|----|-----|
| 上游 | `http://cap-agent:9000` |
| 协议 | HTTP |
| read_timeout | `30s`（pyautogui 单次动作） |

**示例片段**：

```nginx
location /gui/ {
    proxy_pass http://cap-agent:9000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_read_timeout 30s;
    # 截图响应可能较大
    proxy_buffering off;
}
```

### 4.3 `/auth/`（鉴权，P1 保留）

| 项 | 值 |
|----|-----|
| 上游 | `http://cap-agent:9000` |
| 协议 | HTTP |
| 状态 | P1 不实现（FR-NI-1），路由保留以兼容 P2 |

**示例片段**：

```nginx
location /auth/ {
    proxy_pass http://cap-agent:9000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
}
```

> P1 阶段 cap-agent 的 `/auth/*` 端点返回 501 Not Implemented；P2 接入应用层认证。

### 4.4 `/mcp/sandbox/`（MCP Streamable HTTP）

| 项 | 值 |
|----|-----|
| 上游 | `http://cap-mcp:8940` |
| 协议 | HTTP（Streamable HTTP，非传统 WS） |
| read_timeout | `300s`（MCP 长轮询可能较慢） |
| 缓冲 | off（SSE 风格流式） |

**配置要点**：Streamable HTTP 通过 POST 建立 session，响应可能是 SSE chunked；必须禁用 `proxy_buffering`。

**示例片段**：

```nginx
location /mcp/sandbox/ {
    proxy_pass http://cap-mcp:8940;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header Accept text/event-stream;
    proxy_buffering off;
    proxy_read_timeout 300s;
}
```

---

## 5. 全局配置

### 5.1 upstream 块

为可读性定义 upstream（可选，也可直接 `proxy_pass http://service:port`）：

```nginx
upstream cap_agent    { server cap-agent:9000;    keepalive 16; }
upstream cap_terminal { server cap-terminal:7681; server cap-terminal:7682; keepalive 16; }
upstream cap_browser  { server cap-browser:6080;  server cap-browser:9222; keepalive 16; }
upstream cap_code     { server cap-code:8081;     keepalive 16; }
upstream cap_jupyter  { server cap-jupyter:8888;  keepalive 16; }
upstream cap_mcp      { server cap-mcp:8940;      keepalive 16; }
```

### 5.2 server 块

```nginx
server {
    listen 80 default_server;
    server_name _;
    client_max_body_size 2g;

    # WebSocket connection_upgrade map（http 块定义）
    # map $http_upgrade $connection_upgrade {
    #     default upgrade;
    #     ''      '';
    # }

    # 路由 location 见上述各节
}
```

### 5.3 超时基线

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `connect_timeout` | `5s` | 上游建连超时 |
| `send_timeout` | `60s` | 向客户端发送超时（WS 路由单独覆盖） |
| `read_timeout` | `60s` 默认，WS 路由 `3600s~7200s` | 上游响应超时 |

### 5.4 健康检查与上游故障

| 场景 | 行为 | 关联 |
|------|------|------|
| 上游容器停 | nginx 返回 502 Bad Gateway | User Story 5 Acceptance 2 |
| 上游重启中 | 502，重试不卡死 | Edge Case |
| 上游响应慢 | 触发 `read_timeout`，返回 504 Gateway Timeout | — |
| WS 空闲 5 分钟（noVNC） | nginx 主动断开 | Edge Case |

---

## 6. 错误响应

nginx 自身错误（非上游）：

| HTTP | nginx code | 说明 |
|------|------------|------|
| 400 | `bad_request` | 请求格式错误 |
| 404 | `not_found` | 路径无匹配 location |
| 413 | `payload_too_large` | 超过 `client_max_body_size` |
| 502 | `bad_gateway` | 上游不可达 |
| 504 | `gateway_timeout` | 上游响应超时 |

错误页面可由 `error_page` 自定义，P1 默认 nginx 标准页。

---

## 7. 配置验证

部署后验证步骤：

1. `nginx -t`：语法检查（在 cap-nginx 容器内执行）
2. `nginx -s reload`：热加载
3. 对每个前缀发起测试请求，断言响应非 502/504（User Story 5 Independent Test）
4. WS 验证：用 `wscat` 连 `/websockify`、`/terminal/ws`、`/cdp/devtools/{id}`，断言握手成功

---

## 8. P2 演进点

- `/auth/` 接入应用层认证（FR-NI-1 解除）
- TLS 终止（HTTPS 443，certbot 自动续签）
- 限流（`limit_req_zone`）与基础 DDoS 防护
- 多 workspace 路由（路径前缀化 `/ws/{id}/...`）

---

## 引用

- spec.md：FR-005（nginx 唯一对外端口）、FR-014（路由前缀表）、FR-015（WebSocket 升级）
- research.md：R6（nginx 单文件 + WS 升级配置）
- `.archive/sandbox-design.md` §4.2（cap-nginx 职责）、§12（docker-compose 编排）
