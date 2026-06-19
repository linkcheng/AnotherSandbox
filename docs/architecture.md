# 架构总览

**Date**: 2026-06-18
**Source**: `.archive/sandbox-design.md` §1–§18、`specs/001-sandbox-p1-stack/`

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

详细设计见 `.archive/sandbox-design.md` §2。

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

挂载矩阵出自 `.archive/sandbox-design.md` §7.2（设计原则二）。

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
