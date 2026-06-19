# AI 个人沙箱（MySandbox）

一个跑在你本机的、浏览器即达的全栈 AI 工作环境：Python + Node + GUI 桌面 + 终端 + Jupyter + MCP，所有能力容器化隔离，单一端口对外。P2 引入 Orchestrator 编排层支持多租户。

> **当前阶段：P1 全栈 + P2 Orchestrator 已交付** — 4 base 镜像 + 7 cap-* 服务 + Orchestrator 编排层（多租户 / JWT 认证 / 审计）+ 13 MCP 工具 + Unit/Integration/E2E 三层测试。

---

## 项目定位

- **隔离**：每个能力（agent / browser / terminal / code / jupyter / mcp / nginx）一个容器，共享 X11 socket 与 workspace 卷；P2 workspace 间独立 sandbox-net + 卷隔离
- **可控**：单端口对外（P1 `cap-nginx :80`；P2 每 workspace 1 端口 + Orchestrator `:8000`）
- **可重建**：所有镜像由 Dockerfile 生成，配置即代码
- **共享语义**：Human 与 AI Agent 共享同一 Chromium（CDP）与 tmux session（libtmux）
- **多租户（P2）**：Orchestrator 编排多 workspace，JWT 认证 + 可信 header + 审计落库

详细设计见 [`.archive/sandbox-design.md`](.archive/sandbox-design.md)（4331 行）。

---

## 两阶段架构

| 阶段 | 范围 | 部署 |
|------|------|------|
| **P1** | 单 workspace 全栈能力（shell/browser/file/GUI/code/jupyter + MCP） | 本地 / 内网，`AUTH_MODE=none` |
| **P2** | Orchestrator 编排层（多 workspace + JWT 认证 + 审计） | 多租户，叠加在 P1 之上（可选） |

P2 是**可选叠加层**：P1 单 workspace 模式仍独立可用（零迁移，业务路由代码不变）。

---

## 目录结构

```
.
├── base/                   # Layer 层：4 个 base 镜像
├── cap-agent/              # FastAPI 业务编排（:9000）：health/shell/cdp/gui + auth 中间件 + 审计
├── cap-browser/            # Xvnc + Chromium（:9222 CDP + :6080）
├── cap-code/               # code-server（:8081）
├── cap-jupyter/            # JupyterLab（:8888）
├── cap-mcp/                # FastMCP（:8940）：13 工具 + 审计上报
├── cap-nginx/              # 唯一对外入口（:80）+ workspace auth_request 模板（P2）
├── cap-terminal/           # tmux + shell-exec-api（:7682）+ 审计上报
├── orchestrator/           # 【P2】Orchestrator 编排层：FastAPI + PostgreSQL + Alembic
├── specs/
│   ├── 001-sandbox-p1-stack/         # P1 规格（32 FR + 8 SC + 7 US + contracts）
│   └── 002-sandbox-p2-orchestrator/  # P2 规格（27 FR + 8 SC + 5 US + 4 contracts + 79 tasks）
├── docs/                  # architecture（P1+P2）/ deployment / troubleshooting
├── tests/e2e/             # P1 + P2 E2E
├── docker-compose.yml                # P1：7 服务编排
├── docker-compose.orchestrator.yml   # P2：Orchestrator + PostgreSQL
├── docker-compose.workspace.yml.tmpl # P2：workspace 模板（参数化）
├── Makefile               # 所有开发命令（P1 + P2 target）
└── .env.example           # 环境变量样例（P1 + P2）
```

---

## 快速开始

### P1：单 workspace 全栈

```bash
git clone <repo-url> sandbox && cd sandbox
cp .env.example .env
make build          # 构建所有镜像（首次约 5-8 分钟）
make up             # docker compose up -d（< 90s healthy）
curl http://localhost/v1/health   # {"status":"ok"}
# 浏览器：/novnc/  /code-server/  /jupyter/  /terminal/
```

### P2：Orchestrator 编排层（多租户）

```bash
make build-orchestrator   # 构建 orchestrator 镜像（FROM base-python312）
make up-orchestrator      # 启动 Orchestrator + PostgreSQL（alembic 自动迁移）
curl http://localhost:8000/readyz   # {"status":"ready","db":"ok"}

# API 闭环：register → login → create workspace → verify → audit
curl -X POST localhost:8000/api/v1/auth/register \
  -d '{"email":"a@b.c","password":"pw"}' -H 'Content-Type: application/json'
# 详见 specs/002-sandbox-p2-orchestrator/quickstart.md
```

CLI（P2）：`orchestrator user register/login` + `workspace create/start/stop/list`

---

## MCP 工具清单（13 个，P1）

cap-mcp 通过 Streamable HTTP 暴露：

| 类别 | 工具 | 转发目标 |
|------|------|----------|
| shell | `shell_exec` | cap-terminal (libtmux) |
| fs | `fs_read` / `fs_write` / `fs_list` / `fs_search` | 直接 IO（防穿越） |
| browser | `browser_navigate` / `click` / `type` / `snapshot` / `screenshot` | cap-browser:9222 (playwright CDP) |
| desktop | `desktop_screenshot` / `click` / `type` | cap-agent:9000/gui (pyautogui) |

---

## 测试

```bash
make test-unit                    # P1 各服务 pytest + 覆盖率 ≥80%
make test-e2e                     # P1 docker compose + e2e
make test-orchestrator            # P2 orchestrator unit（覆盖率 ≥80%）
make test-orchestrator-integration # P2 testcontainers-postgres 集成
```

| 服务 | tests | 覆盖率 |
|------|-------|--------|
| cap-agent | 55 | 99% |
| cap-terminal | 20 | 88% |
| cap-mcp | 40 | 86% |
| cap-nginx | 4 | contract |
| orchestrator（P2） | 51 | 83% |

---

## 常用命令

```bash
make help                    # 列出所有 target
# P1
make build / up / down / logs / test / clean
# P2
make build-orchestrator / up-orchestrator / stop-orchestrator
make test-orchestrator / test-orchestrator-integration / test-e2e-p2
```

---

## 相关文档

**P1**：[spec](specs/001-sandbox-p1-stack/spec.md) · [plan](specs/001-sandbox-p1-stack/plan.md) · [research](specs/001-sandbox-p1-stack/research.md) · [data-model](specs/001-sandbox-p1-stack/data-model.md) · [quickstart](specs/001-sandbox-p1-stack/quickstart.md) · [tasks](specs/001-sandbox-p1-stack/tasks.md)

**P2**：[spec](specs/002-sandbox-p2-orchestrator/spec.md) · [plan](specs/002-sandbox-p2-orchestrator/plan.md) · [research](specs/002-sandbox-p2-orchestrator/research.md)（9 决策）· [data-model](specs/002-sandbox-p2-orchestrator/data-model.md)（6 表）· [quickstart](specs/002-sandbox-p2-orchestrator/quickstart.md) · [tasks](specs/002-sandbox-p2-orchestrator/tasks.md) · [contracts](specs/002-sandbox-p2-orchestrator/contracts/)（4 份）

通用：[架构 docs/architecture.md](docs/architecture.md) · [部署 docs/deployment.md](docs/deployment.md) · [故障 docs/troubleshooting.md](docs/troubleshooting.md) · [设计原文 .archive/sandbox-design.md](.archive/sandbox-design.md)

---

## 安全声明

**P1**（`AUTH_MODE=none`）：⚠️ 不适合公网——靠 sandbox-net 网络隔离，Chromium `--no-sandbox`，无应用层认证。适用本地 / 内网受信环境。

**P2**（Orchestrator）：JWT 网关认证 + 可信 header 注入 + nginx `auth_request` fail-closed + 审计落库（`shell.exec` / `fs.write` / `browser.action` / `gui.action` 4 类）。沿用 P1 宽松处理（Shell `permissive`、Chromium `--no-sandbox`）作为 P2 安全增量基线。

详见 [`.archive/sandbox-design.md` §1.1.2 / §8.6 / §11](.archive/sandbox-design.md)。

---

## License

见 [LICENSE](LICENSE)。
