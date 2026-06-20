# 架构总览

**Date**: 2026-06-18
**Source**: `specs/001-sandbox-p1-stack/`

## 三层体系

```
┌─────────────────────────────────────────────────────┐
│  Profile 层：Workspace 目录（状态唯一载体）             │
│  /workspace/{code,notebooks,shared,.chromium,        │
│              .vscode,.jupyter,AGENTS.md}              │
└──────────────────────┬──────────────────────────────┘
                       │ 按子目录 rw/ro 挂载
┌──────────────────────▼──────────────────────────────┐
│  Capability 层：7 个 cap-* 容器                       │
│  cap-nginx :80（唯一对外端口）                         │
│  ├── cap-agent :9000   (FastAPI 业务编排)             │
│  ├── cap-browser :9222 (Chromium+Xvnc)               │
│  ├── cap-terminal :7682 (tmux+shell-exec-api)         │
│  ├── cap-code :8081    (code-server)                  │
│  ├── cap-jupyter :8888 (JupyterLab)                   │
│  └── cap-mcp :8940     (MCP Streamable HTTP)          │
└──────────────────────┬──────────────────────────────┘
                       │ FROM 继承
┌──────────────────────▼──────────────────────────────┐
│  Layer 层：4 个 base 镜像                              │
│  base-os (Ubuntu 24.04)                              │
│  ├── base-python312 (uv+Python 3.12)                  │
│  ├── base-vnc      (Xvnc+Openbox)                    │
│  └── base-node24   (Node 24+pnpm)                    │
└─────────────────────────────────────────────────────┘
```

## 服务依赖与挂载矩阵

| 服务 | 端口 | 依赖 | rw 挂载 | ro 挂载 |
|------|------|------|---------|---------|
| cap-nginx | 80 | 所有 cap-* healthy | — | — |
| cap-agent | 9000 expose | cap-browser/terminal healthy | — | `/workspace` ro + x11 socket |
| cap-browser | 9222/6080 expose | — | `/workspace/.chromium` rw | `/workspace` ro |
| cap-terminal | 7681/7682 expose | — | — | `/workspace/{code,shared}` ro |
| cap-code | 8081 expose | — | `/workspace/{code,.vscode}` rw | `/workspace/shared` ro |
| cap-jupyter | 8888 expose | — | `/workspace/{notebooks,.jupyter,shared}` rw | — |
| cap-mcp | 8940 expose | agent/browser/terminal healthy | — | `/workspace/{code,shared}` ro |

## 数据流（典型调用）

```
1. AI Agent 进程
   → MCP client (Streamable HTTP)
   → POST http://localhost/mcp/sandbox/

2. cap-nginx :80
   → 反代到 cap-mcp:8940/mcp/sandbox/mcp/

3. cap-mcp shell_exec tool
   → POST cap-agent:9000/v1/shell/exec

4. cap-agent terminal_client
   → POST cap-terminal:7682/api/v1/exec

5. cap-terminal tmux_session
   → libtmux → tmux session 'sandbox'
   → shell 执行 + capture_pane

6. 返回 {exit_code, stdout, stderr, duration_ms}
```

## 安全基线（P1）

- 所有容器 `cap_drop: [ALL]` + `security_opt: [no-new-privileges:true]`（FR-007）
- 资源限制（FR-008）：cap-browser 2g / cap-jupyter 2g / cap-code 1g / cap-mcp 768m / cap-terminal 512m / cap-agent 384m / cap-nginx 64m
- Chromium `--no-sandbox`（P1 安全降级，§1.1.2）
- 唯一对外端口 cap-nginx 80；其他 cap-* 仅 expose
- P1 不实现应用层认证（`AUTH_MODE=none`），靠 sandbox-net 网络隔离

## 测试分层（§18）

- Unit：每个 Python 服务 pytest + 全 mock，行覆盖 ≥80%
- Integration：cap-agent/cap-mcp 跨服务调用，respx mock 下游
- E2E：`make test-e2e` → docker compose up + httpx 打 cap-nginx

## 关键决策（出自 research.md）

- R1：Python 3.12 + uv + FastAPI
- R3：libtmux 共享 tmux session（设计原则三）
- R4：playwright connect_over_cdp（共享 Chromium）
- R5：pyautogui 唯一持有者为 cap-agent
- R6：nginx 显式 WS 升级
- R7：cap_drop ALL + Chromium --no-sandbox（P1）
- R10：bind mount + rw/ro 子目录隔离

---

## P2 Orchestrator 编排层（specs/002-sandbox-p2-orchestrator）

P2 在 P1 三层之上叠加 **Orchestrator**（可选叠加层，§8.8.5 不变量：P1 单 workspace 仍独立可用）。

```
宿主机
├── Orchestrator (FastAPI :8000) + PostgreSQL 16     ← orchestrator-net
│     编排 / 元数据 / JWT 认证 / 审计
└── workspace 容器组（docker compose -p {slug}）     ← 各自独立 sandbox-net（互隔离）
      cap-nginx :{external_port} → cap-agent/mcp/terminal/browser/code/jupyter
        │ auth_request → Orchestrator /api/v1/verify（回写可信 header）
        │ 审计上报    → Orchestrator /api/v1/audit/ingest（best-effort）
        └── extra_hosts: host.docker.internal:host-gateway（出站到 Orchestrator）
```

### 核心组件
- **Orchestrator**（独立 Python 服务 `orchestrator/`）：FastAPI + SQLAlchemy 2.x async + Alembic + PyJWT + passlib[bcrypt] + typer
- **元数据**（PostgreSQL）：6 表 users/workspaces/workspace_owners/templates/audit_logs/refresh_tokens
- **认证**：JWT register/login/refresh（rotation）+ nginx auth_request → `/verify` 注入可信 header（X-User-Id/X-Workspace-Id/X-Permissions）
- **编排**：`docker compose -p` 子进程（asyncio.create_subprocess_exec，非 shell）+ 状态机（§8.5）+ 端口分配（8100+）
- **审计**：cap-* fire-and-forget 上报 → `audit_logs`（best-effort，不阻塞业务）

### P2 安全增量（相对 P1）
- JWT 网关认证 + 可信 header + nginx auth_request fail-closed（R4）
- 审计落库（§8.8.6）
- **沿用 P1 宽松**（用户确认）：Shell `permissive`、Chromium `--no-sandbox`（FR-NI-4/5）

### 关注点分离（§8.6.3）
- Orchestrator 见用户身份（JWT），不见业务内容
- cap-agent 见业务内容，不见密码；通过 nginx 注入的可信 header 获知身份
- 网络隔离 + nginx `proxy_set_header` 覆盖（非透传）防外部伪造可信 header

### 测试分层
- orchestrator unit（≥80%）+ integration（testcontainers-postgres 真 PG）
- cap-agent auth（双模式）/ audit_client（fire-and-forget）unit
- nginx workspace 模板 contract
- E2E（完整 stack）：`tests/e2e/test_p2_*.py`（需 `make up-orchestrator` + workspace）

### 4 项技术决策（research.md R1-R4）
- R1 软删除保留 `WORKSPACE_RETENTION_DAYS=7` 天后硬删
- R2 每 workspace 1 对外端口，`WORKSPACE_PORT_START=8100` 递增
- R3 workspace 经 `host.docker.internal`（host-gateway）出站到 Orchestrator
- R4 `AUTH_FAILURE_MODE=fail-closed`（Orchestrator 不可达拒绝请求）

详见 `specs/002-sandbox-p2-orchestrator/`（plan / research / data-model / contracts）。

---

## P3 Launcher 入口层 + SSO/OAuth（specs/003-sandbox-p3-launcher）

P3 在 P2 之上叠加 **launcher**（React 启动器）与 **OAuth 身份扩展**，并补齐 **orchestrator-as-controller 真实启动**。不变量：P1/P2 零迁移（compose_runner 代码零改动，P2 既有端点/鉴权链路不变）。

```
浏览器（单域名 :8080）
  │
  ▼
launcher (nginx :8080)                              ← launcher-net（对外唯一入口）
  ├── /            → React SPA（登录页 / 工作台 / 监控）
  ├── /api/        → orchestrator:8000（反代，trailing slash 剥离）
  └── /ws/{slug}/  → {slug}-cap-nginx:80（统一入口 + auth_request + WebSocket 透传）
        │ auth_request /_authsub → orchestrator /api/v1/verify
        │ resolver 127.0.0.11 动态解析 {slug}-cap-nginx（R5 方案A 容器名约定）
        ▼
orchestrator (FastAPI :8000) + PostgreSQL 16         ← orchestrator-net（挂 docker.sock）
  ├── OAuth router（/auth/oauth/{p}/login|callback|bind|unbind, /accounts）
  │     └── authlib + PKCE；mock 模式（OAUTH_MOCK=true）离线闭环
  ├── oauth_linker：（provider,provider_user_id）→ 邮箱合并 → 建户 → 复用 P2 security.create_tokens()
  └── workspace start：compose up 前 render_workspace_nginx_conf（cap-nginx Phase5 auth_request）
        ▼
workspace 容器组（docker compose -p {slug}）         ← sandbox-launcher-net（launcher 与 cap-nginx 共享）
  cap-nginx（挂载渲染后的 nginx.workspace.conf）
    └── auth_request /_auth → orchestrator /api/v1/verify?workspace={id}（双层纵深防御 R6）
```

### 核心组件（相对 P2 新增）
- **launcher**（`launcher/`）：Vite + React 19 + TypeScript + shadcn/ui + tailwind + react-router + @tanstack/react-query；容器内 nginx 托管 SPA 并反代 `/api` + `/ws/{slug}/`。
- **OAuth 身份扩展**（orchestrator）：`routers/oauth.py` + `services/oauth_provider.py`（authlib GitHub/Google + Mock）+ `services/oauth_linker.py`（邮箱合并）+ `models/oauth_account.py` + Alembic `0002_oauth`。
- **orchestrator-as-controller**（research.md R4）：orchestrator 镜像装 docker compose v2 CLI + 挂 `/var/run/docker.sock` + workspace compose 模板可见（`WORKSPACE_COMPOSE_CWD`）；compose_runner **代码零改动**（FR-019），仅在容器内真实 `docker compose -p up`。
- **cap-nginx Phase5 渲染注入**（批次3 遗留，research.md R6）：`services/workspace_compose.py` 在 start 前渲染 `nginx.workspace.conf.tmpl`（`${ORCHESTRATOR_URL}/${WORKSPACE_ID}/${AUTH_FAILURE_MODE}`）到 `{volume_root}/{slug}/nginx.workspace.conf`，经 `WORKSPACE_NGINX_CONF` env 挂入 cap-nginx（compose 模板已预留 `${WORKSPACE_NGINX_CONF:-/dev/null}` 挂载点）。

### 统一反代与 cookie 鉴权链路（research.md R3/R5/R6）
- 浏览器 → launcher `/ws/{slug}/` → launcher `auth_request /_authsub` → orchestrator `/verify`（回写 X-User-Id/X-Workspace-Id/X-Permissions）→ launcher `proxy_pass http://{slug}-cap-nginx:80`。
- workspace cap-nginx 再做一次 `auth_request`（双层纵深，防 launcher 被绕过）。
- JWT 存 **HttpOnly + Secure + SameSite=Lax cookie**（防 XSS 窃取）；launcher fetch 带 `credentials:"include"`；refresh 端点轮换。
- WebSocket 透传：`proxy_http_version 1.1` + `Upgrade/Connection` + `proxy_read_timeout 3600s`（terminal/novnc 长连接核心，FR-022）。
- fail-closed：orchestrator 5xx/超时 → `error_page` 403（SC-010 无穿透）。

### P3 安全增量与风险（相对 P2）
- ⚠️ **docker.sock 挂载**是 P3 唯一新提权面：orchestrator 容器可控制宿主 Docker。缓解：`cap_drop: [ALL]` + `no-new-privileges` + 单机受信环境 + socket 文件权限。公网部署须改远程编排 API（超 P3 范围）。
- OAuth 凭证仅后端 env（FR-007）；OAuth JWT 复用 P2 内核（行为 100% 一致，下游鉴权/审计零分支）。
- `OAUTH_MOCK=true` 仅开发/测试；生产 fail-fast。

### 测试分层（P3 新增）
- orchestrator unit：OAuth provider/linker、workspace_compose 渲染、cap-nginx 模板注入（≥80%）。
- orchestrator integration：OAuth 闭环 testcontainers-postgres（mock provider）、迁移 `0002_oauth`。
- launcher unit：vitest + msw（Login/Workspaces/CreateWizard/Monitor 组件）。
- E2E（`tests/e2e/`）：`test_p3_oauth_flow.py`（OAuth 闭环）/ `test_p3_real_start.py`（真实启动 + 统一入口）/ `test_p1p2_regression.py`（零迁移回归）。无 Docker/镜像自动 skip。

### 9 项技术决策（research.md R1-R9）
- R1 authlib + Authorization Code + PKCE，签发等价 P2 JWT
- R2 oauth_accounts 表 + users 增 display_name/avatar + 邮箱合并
- R3 JWT 存 HttpOnly + Secure + SameSite=Lax cookie
- R4 orchestrator-as-controller：docker.sock + compose CLI + 模板挂载
- R5 launcher nginx：SPA + /api + /ws/{slug}/ + auth_request + WebSocket 透传
- R6 cap-nginx Phase5：envsubst 渲染 auth_request，双层鉴权纵深
- R7 监控刷新：轮询（react-query refetchInterval），SSE 推迟
- R8 前端架构：Vite + React 19 + shadcn/ui + tailwind + react-router + react-query
- R9 OAuth 开发态 mock（OAUTH_MOCK 开关，走真实建户/签 JWT）

详见 `specs/003-sandbox-p3-launcher/`（plan / research / quickstart / contracts）。
