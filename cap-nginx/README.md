# cap-nginx

AI 个人沙箱 **唯一对外 HTTP/WebSocket 入口**（FR-005）。
所有外部流量经此容器反代到 sandbox-net 内的 cap-* 服务。

## 路由表

完整契约见 `specs/001-sandbox-p1-stack/contracts/nginx-routes.md`。

| 前缀 | 上游 | 协议 | WS | 说明 |
|------|------|------|----|------|
| `/novnc/` | 本地 alias | HTTP | 否 | noVNC 静态前端 |
| `/websockify` | cap-browser:6080 | WS | 是 | noVNC → VNC 桥 |
| `/terminal/` | cap-terminal:7681 | HTTP+WS | 是 | ttyd Web Terminal |
| `/code-server/` | cap-code:8081 | HTTP+WS | 可选 | VS Code |
| `/jupyter/` | cap-jupyter:8888 | HTTP+WS | 是 | JupyterLab |
| `/v1/` | cap-agent:9000 | HTTP | 否 | API（health/shell/file） |
| `/gui/` | cap-agent:9000 | HTTP | 否 | GUI 截图与动作 |
| `/cdp/` | cap-agent:9000 | HTTP+WS | 是 | Chromium DevTools |
| `/auth/` | cap-agent:9000 | HTTP | 否 | 鉴权（P1 保留） |
| `/mcp/sandbox/` | cap-mcp:8940 | HTTP | 否 | MCP Streamable HTTP |

WS 路由统一使用 `map $http_upgrade $connection_upgrade` + `proxy_http_version 1.1` + `Upgrade`/`Connection` header 透传（FR-015）。

## 健康检查

docker-compose 中通过 `wget -qO- http://cap-agent:9000/v1/health` 探活。
仅在所有上游服务 healthy 后才启动本容器（`depends_on: condition: service_healthy`）。

## 配置文件

- `nginx.conf`：完整反代配置，被 Dockerfile `COPY` 到 `/etc/nginx/nginx.conf`
- `tests/test_routes.py`：契约测试，断言 nginx.conf 中 10 个 location 与 WS 升级 header 都已就位
- `Dockerfile`：基于 `base-os:latest`，安装 nginx + wget + curl

## 开发流程

```bash
# 1. 跑 contract test（无需启动 nginx）
cd cap-nginx
uv sync --extra dev
uv run pytest tests/ -v

# 2. 在仓库根构建并启动完整 stack
cd ..
make build && make up

# 3. 浏览器访问 http://localhost/{novnc,code-server,jupyter,terminal,v1}/
```

修改 `nginx.conf` 后必须先跑 contract test 再 `make build cap-nginx`。
