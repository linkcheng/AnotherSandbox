# Implementation Plan: AI 个人沙箱 P1 全栈

**Branch**: `001-sandbox-p1-stack` | **Date**: 2026-06-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-sandbox-p1-stack/spec.md`

**Source**: `.archive/sandbox-design.md` §1–§18

## Summary

在本地单机受信环境部署一个 AI 与人类共享的 Linux 沙箱运行时。覆盖 4 个 base 镜像 + 7 个 cap-* 服务，全部以 TDD（Unit + Integration + 镜像 E2E）落地。P1 不引入多租户/应用层认证/公网部署。技术栈：Python 3.12 + uv + FastAPI + docker compose + Nginx。开发从 cap-agent 起步（业务优先），先 TDD 打通业务编排，再向上扩展到 cap-mcp/cap-terminal/cap-browser/cap-nginx，最后接入 cap-code/cap-jupyter 并跑完整 E2E。

## Technical Context

**Language/Version**: Python 3.12（cap-agent / cap-terminal / cap-mcp）+ Node.js 24（cap-code 上层 code-server）+ Bash（base-os 系统脚本）

**Primary Dependencies**:
- Web 框架：FastAPI + uvicorn[standard] + pydantic v2 + pydantic-settings
- HTTP 客户端：httpx（异步）
- MCP：fastmcp（Streamable HTTP）
- Shell 共享：libtmux（Python 绑定 tmux）+ terminado
- 测试：pytest + pytest-asyncio + respx + coverage + httpx
- 构建：uv（Python 包管理）+ Docker BuildKit（多阶段构建）+ make（编排）

**Storage**: 文件系统（bind mount `/workspace/`），无外部数据库。tmux session 作为运行时 PTY 持有者。

**Testing**:
- Unit：pytest，纯函数/类，全 mock 下游，行覆盖率 ≥80%
- Integration：pytest + respx mock HTTP，验证 cap-agent ↔ cap-terminal/browser 转发逻辑
- E2E：`make test-e2e`，docker compose up 完整 stack，httpx 打 cap-nginx

**Target Platform**: Linux x86_64 / arm64 主机，macOS 开发机（Chromium `--no-sandbox` 兼容）。Docker 24+ + docker compose v2。

**Project Type**: 多服务容器化平台（7 个独立 FastAPI / 静态服务 + 4 个 base 镜像）

**Performance Goals**:
- `make build` < 8 分钟（冷构建，11 个镜像）
- `make up` 到 healthy < 90 秒
- MCP `shell_exec` 端到端 < 500ms
- 稳态总内存 < 5GB

**Constraints**:
- P1 不引入应用层认证（`AUTH_MODE=none`）
- 所有容器 `cap_drop: [ALL]` + `no-new-privileges:true`
- Chromium `--no-sandbox`（P1 安全降级，§1.1.2）
- cap-nginx 唯一对外端口（默认 80）

**Scale/Scope**:
- 单 workspace 单用户（P1 不做多租户）
- 7 个容器、约 12K LOC（不含 vendored）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

仓库未提供 `.specify/memory/constitution.md`（仅有 template）。采用全局 CLAUDE.md（用户偏好）作为隐性 constitution，逐条核对：

| 原则 | 来源 | 本计划合规性 |
|------|------|--------------|
| 始终用中文 | CLAUDE.md #1 | ✅ 所有 spec/plan/tasks/README 用中文 |
| 目标不清晰先讨论 | CLAUDE.md #1 | ✅ 已通过 AskUserQuestion 收敛 4 项关键决策 |
| 最小化设计 | CLAUDE.md #2 | ⚠️ 任务范围"完整 P1 全部 7 服务"是用户明确选择；用 milestone 拆解降低复杂度 |
| Spec→Plan→Test→Code | CLAUDE.md #3 | ✅ speckit 工作流严格遵循 |
| Fail Fast / 无打补丁 | CLAUDE.md #2 | ✅ 测试先于实现（TDD），失败立即修根因 |
| Python uv + 3.12 + Type Hint + Async | CLAUDE.md #8 | ✅ cap-agent/terminal/mcp 全 async，全 type hint |
| 模块单职责、对外暴露协议 | CLAUDE.md #6 | ✅ 每个 cap-* 单容器单职责；MCP 工具走 JSON Schema 契约 |
| Unit→Integration→E2E | CLAUDE.md #5 | ✅ 三层全覆盖 |

**结论**：通过 Constitution Check。复杂度较高但已通过 milestone 拆解，无需 Complexity Tracking 条目。

## Project Structure

### Documentation (this feature)

```text
specs/001-sandbox-p1-stack/
├── spec.md              # 规格（已完成）
├── plan.md              # 本文件
├── research.md          # Phase 0：技术选型与不确定项研究
├── data-model.md        # Phase 1：核心实体与数据结构
├── quickstart.md        # Phase 1：端到端验证手册
├── contracts/           # Phase 1：服务对外契约
│   ├── cap-agent-api.md     # /v1/* /gui/* /cdp/*
│   ├── cap-terminal-api.md  # /api/v1/exec 等
│   ├── cap-mcp-tools.md     # MCP 工具列表与 schema
│   └── nginx-routes.md      # 路由表
└── tasks.md             # Phase 2：任务列表（/speckit-tasks）
```

### Source Code (repository root)

```text
sandbox/                                  # 仓库根
├── Makefile                              # build/up/down/test/logs
├── docker-compose.yml                    # 7 服务编排
├── .env.example                          # PORT/WORKSPACE_DIR 等
├── base/                                 # Layer 层镜像
│   ├── base-os/Dockerfile
│   ├── base-vnc/Dockerfile
│   ├── base-node24/Dockerfile
│   └── base-python312/Dockerfile
├── cap-agent/                            # FastAPI 业务编排 :9000
│   ├── Dockerfile
│   ├── pyproject.toml                    # uv 管理
│   ├── src/cap_agent/
│   │   ├── __init__.py
│   │   ├── main.py                       # FastAPI app + lifespan
│   │   ├── core/
│   │   │   ├── config.py                 # pydantic-settings
│   │   │   └── exceptions.py
│   │   ├── routers/
│   │   │   ├── health.py                 # GET /v1/health
│   │   │   ├── shell.py                  # POST /v1/shell/exec
│   │   │   ├── gui.py                    # /gui/screenshot, /gui/actions
│   │   │   └── cdp.py                    # /cdp/json, /cdp/devtools/*
│   │   ├── services/
│   │   │   ├── terminal_client.py        # → cap-terminal:7682
│   │   │   ├── browser_cdp_client.py     # → cap-browser:9222
│   │   │   └── gui_backend.py            # pyautogui 唯一持有者
│   │   └── models/
│   │       └── actions.py                # 16 种桌面动作 discriminated union
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── conftest.py
├── cap-terminal/                         # tmux + shell-exec-api :7682
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── src/cap_terminal/
│   │   ├── main.py
│   │   ├── tmux_session.py               # libtmux 包装
│   │   └── routers/
│   │       ├── exec.py                   # POST /api/v1/exec
│   │       └── status.py                 # GET /api/v1/terminal/status
│   └── tests/
├── cap-browser/                          # Xvnc + Chromium :9222
│   ├── Dockerfile
│   └── entrypoint.sh                     # Xvnc + Openbox + Chromium
├── cap-code/                             # code-server :8081
│   └── Dockerfile
├── cap-jupyter/                          # JupyterLab :8888
│   └── Dockerfile
├── cap-mcp/                              # MCP Streamable HTTP :8940
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── src/cap_mcp/
│   │   ├── main.py                       # fastmcp 实例
│   │   ├── tools/
│   │   │   ├── shell.py                  # shell_exec → cap-terminal
│   │   │   ├── fs.py                     # fs_* 直接 IO
│   │   │   ├── browser.py                # browser_* → cap-browser:9222
│   │   │   └── desktop.py                # desktop_* → cap-agent:9000
│   │   └── workspace_context.py          # AGENTS.md 注入
│   └── tests/
├── cap-nginx/                            # 反向代理 :80
│   ├── Dockerfile
│   └── nginx.conf
├── tests/                                # 顶层 E2E
│   ├── e2e/
│   │   ├── test_health.py
│   │   ├── test_shell_roundtrip.py
│   │   ├── test_fs_roundtrip.py
│   │   ├── test_browser_navigate.py
│   │   └── test_screenshot.py
│   ├── conftest.py                       # httpx client → http://localhost
│   └── pyproject.toml
└── docs/
    ├── architecture.md                   # 引用 .archive/sandbox-design.md
    ├── deployment.md                     # 部署手册
    └── troubleshooting.md
```

**Structure Decision**: 单仓库多服务（monorepo），每个 cap-* 是独立的 Python/容器项目。理由：
1. 跨服务共享的只有 workspace 挂载，无代码共享，无需 monorepo 工具
2. docker-compose 作为唯一编排入口
3. 各服务独立 pyproject.toml + Dockerfile，便于单独构建/测试

## Milestone 拆解

> 用户指定 TDD 起点：cap-agent。但因 cap-agent 依赖 base 镜像与 cap-terminal，需要前置基础工作。

| Milestone | 内容 | 验证手段 | 预估任务数 |
|-----------|------|----------|------------|
| **M0** 工程骨架 | 仓库结构、Makefile、.env.example、docker-compose 框架 | `make help` 输出可用 | 4 |
| **M1** Layer 镜像 | base-os / base-vnc / base-node24 / base-python312 | `make build-base` 成功，镜像 size 合理 | 6 |
| **M2** cap-agent MVP | FastAPI 骨架 + `/v1/health` + pytest 单测 + Dockerfile | `make test-agent` 全绿，行覆盖 ≥80% | 6 |
| **M3** cap-terminal | tmux + shell-exec-api + libtmux + 单测 + Dockerfile | `make test-terminal` 全绿，shell_exec 单测通过 | 8 |
| **M4** cap-agent 业务路由 | `/v1/shell/exec`、`/cdp/*`、`/gui/*` + integration 测试（respx mock） | `make test-agent` 含 integration 全绿 | 10 |
| **M5** cap-nginx | nginx.conf 路由 + WS 升级 + Dockerfile + e2e 验证 | `make up` 后 `curl /v1/health` 通 | 6 |
| **M6** cap-browser | Xvnc + Openbox + Chromium + websocat + entrypoint.sh | VNC 客户端连接看到桌面 | 6 |
| **M7** cap-mcp | fastmcp server + shell/fs/browser/desktop 工具 + 单测 | MCP `tools/list` + `shell_exec` 通 | 10 |
| **M8** cap-code + cap-jupyter | 第三方应用 Dockerfile + 反代验证 | 浏览器访问 /code-server/ 与 /jupyter/ | 4 |
| **M9** E2E 集成 | 顶层 tests/e2e/ + make test-e2e + 部署文档 | `make test-e2e` 全绿 | 8 |

**关键里程碑**：
- **M2 完成**：cap-agent 可独立跑测，验证 TDD 工作流（用户起点）
- **M5 完成**：cap-nginx + cap-agent + cap-terminal 三服务可联调（最小可用闭环）
- **M7 完成**：MCP 工具链全部可用（核心业务闭环）
- **M9 完成**：完整 P1 全栈交付

## Risks

| 编号 | 风险 | 影响 | 缓解 |
|------|------|------|------|
| **R1** | macOS 上 Chromium `--no-sandbox` 性能差，本地开发体验差 | 开发效率 | 开发期可选 mock CDP；CI 跑无头 |
| **R2** | libtmux 跨平台稳定性（macOS tmux 版本与 Linux 不一致） | cap-terminal 测试漂移 | Docker 内固定 tmux 版本；本机不直跑 |
| **R3** | 镜像构建时间长（>8 分钟）| 开发体验 | base 镜像分层缓存；CI 用 buildx cache |
| **R4** | FastAPI 异步与 pyautogui 同步阻塞冲突 | `/gui/actions` 性能 | pyautogui 调用包 `asyncio.to_thread` |
| **R5** | noVNC WebSocket 透传在 cap-nginx 配置易踩坑 | 远程桌面不可用 | M5 用 wscat 验证；保留 nginx 官方 WS 模板 |
| **R6** | MCP Streamable HTTP 协议演进快（fastmcp 版本） | cap-mcp 行为漂移 | pyproject.toml 锁版本；contract test 锁 schema |
| **R7** | P1 范围过大，单 PR 难以审查 | 交付延迟 | 按 milestone 分 PR；每 milestone 独立可发 |
| **R8** | bind mount 在 macOS 文件系统慢（VFS 套娃） | 文件读写延迟 | 推荐开发用 Linux；macOS 接受 100ms 延迟 |

## Implementation Strategy

### TDD 三步循环（每个 milestone 内）

```
1. Red：写失败的 unit test（pytest）
   - 先写 contract test（输入输出 schema）
   - 再写 behavior test（边界条件）
2. Green：写最小实现让 test 通过
   - 不过度设计
   - 不引入未测试的依赖
3. Refactor：重构实现 + 测试
   - 抽公共逻辑到 services/
   - 保持测试覆盖
```

### 服务间契约先行

每两个有依赖的服务（如 cap-agent → cap-terminal）：
1. 先在 `contracts/` 写 JSON Schema 契约
2. 上游服务先实现 stub 返回 mock 数据，下游单测可用
3. 双方实现就绪后，跑跨服务 integration 测试

### 镜像分层缓存策略

```text
base-os (年级)
  ├─→ base-python312 (季度)
  │     ├─→ cap-agent (周)
  │     ├─→ cap-terminal (周)
  │     ├─→ cap-mcp (周)
  │     └─→ cap-jupyter (月)
  ├─→ base-vnc (季度)
  │     └─→ cap-browser (月)
  └─→ base-node24 (季度)
        └─→ cap-code (月)

cap-nginx 直接基于 base-os
```

变更频率高的（cap-agent/terminal/mcp）走最快缓存链；变更慢的（cap-browser/code/jupyter）偶尔重建。

## Phase 0 / Phase 1 / Phase 2 输出

详见同目录：
- `research.md` — Phase 0 输出
- `data-model.md` — Phase 1 输出（核心实体）
- `contracts/*.md` — Phase 1 输出（服务契约）
- `quickstart.md` — Phase 1 输出（验证手册）
- `tasks.md` — Phase 2 输出（任务列表，下一步 `/speckit-tasks`）
