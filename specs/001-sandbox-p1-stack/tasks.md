# Tasks: AI 个人沙箱 P1 全栈

**Input**: Design documents from `/specs/001-sandbox-p1-stack/`

**Prerequisites**: plan.md（M0-M9 已拆解）、spec.md（US1-US7 + FR-001~FR-032 + SC-001~SC-008）、research.md、data-model.md、contracts/

**Tests**: 全 TDD。每个 feature 先写失败的 test（Red），再写实现（Green）。覆盖 Unit + Integration + 镜像 E2E 三层。

**Organization**: 任务按 Phase 组织（Setup → Foundational → US1-US7 → Polish），与 plan.md 的 M0-M9 对齐。每个 US 可独立验证。

## Format: `[ID] [P?] [US?] 描述，含 file path`

- **[P]**: 可并行（不同文件、无依赖）
- **[US#]**: user story 归属（仅 Phase 3+ 需要；Setup/Foundational/Polish 不标）
- 每个任务必须含具体 file path（参照 plan.md 项目结构）
- TDD：先 test（Red），再 impl（Green）；测试任务标注 unit/integration/contract/e2e

## Path Conventions

参照 plan.md §Project Structure：仓库根 `sandbox/`，各 cap-* 服务为独立 Python/容器项目（独立 `pyproject.toml` + `Dockerfile`）。顶层 `tests/e2e/` 跨服务 E2E。

---

## Phase 1: Setup (M0 工程骨架)

**Goal**: 仓库结构、Makefile、docker-compose 框架就绪。所有后续 cap-* 工作的基础。

**Independent Test**: `make help` 输出可用命令列表。

**对应 milestone**: M0

- [ ] T001 创建仓库根骨架：`Makefile`、`.env.example`、`docker-compose.yml` 占位（仅 services: 空 + sandbox-net 网络定义）
- [ ] T002 [P] 创建顶层目录树：`base/`、`cap-agent/`、`cap-terminal/`、`cap-browser/`、`cap-code/`、`cap-jupyter/`、`cap-mcp/`、`cap-nginx/`、`tests/e2e/`、`docs/`（参照 plan.md §Project Structure）
- [ ] T003 [P] 编写 `Makefile` 核心目标：`help`、`build`、`build-base`、`up`、`down`、`test`、`test-unit`、`test-e2e`、`logs`、`clean`
- [ ] T004 [P] 编写 `.env.example`：`PORT=80`、`WORKSPACE_DIR=~/sandbox-workspace`、`AUTH_MODE=none`、`PYTHON_VERSION=3.12`、`NODE_VERSION=24`
- [ ] T005 [P] 编写 `.gitignore`：`.venv/`、`__pycache__/`、`.pytest_cache/`、`node_modules/`、`workspace/`、`*.log`

**Checkpoint**: 仓库结构就绪，`make help` 可用。

---

## Phase 2: Foundational (M1 镜像 + M2 cap-agent MVP + M9 E2E 框架起点)

**Goal**: 4 个 base 镜像可构建；cap-agent FastAPI 骨架 + `/v1/health` TDD 闭环跑通；E2E 测试框架（顶层 `tests/`）就绪。

**⚠️ CRITICAL**: 此阶段完成前不可启动任何 US。

**对应 milestone**: M1 + M2 + M9（部分）

### Phase 2.1: Base 镜像 (M1, FR-001~FR-004)

- [ ] T006 [P] 编写 `base/base-os/Dockerfile`：`FROM ubuntu:24.04`，安装 ca-certificates、curl、tini、locales（zh_CN.UTF-8 + en_US.UTF-8），设置 entrypoint tini
- [ ] T007 [P] 编写 `base/base-python312/Dockerfile`：`FROM base-os`，安装 uv + Python 3.12（FR-001），设置 `UV_LINK_MODE=copy`
- [ ] T008 [P] 编写 `base/base-node24/Dockerfile`：`FROM base-os`，安装 Node.js 24 + pnpm（FR-001）
- [ ] T009 [P] 编写 `base/base-vnc/Dockerfile`：`FROM base-os`，安装 Xvnc、Openbox、tigervnc-common、fonts-noto-cjk、xterm（FR-001，§X 显示栈）
- [ ] T010 编写 `Makefile` 的 `build-base` 目标：并行构建 4 个 base 镜像（FR-003），支持 BuildKit cache
- [ ] T011 e2e 验证：`tests/e2e/test_base_images.py` 断言 4 个 base 镜像可 `docker run` 并执行 `--version`

### Phase 2.2: cap-agent MVP (M2, FR-016, FR-029)

**TDD 起点（用户指定）**：先写失败 test，再写 FastAPI 实现。

- [ ] T012 [P] [test-unit] 编写 `cap-agent/tests/unit/test_health.py`：断言 `GET /v1/health` 返回 `200 + {"status": "ok"}`（FR-016）
- [ ] T013 [P] 编写 `cap-agent/pyproject.toml`：依赖 fastapi、uvicorn[standard]、pydantic v2、pydantic-settings、httpx；dev 依赖 pytest、pytest-asyncio、respx、coverage
- [ ] T014 [P] 编写 `cap-agent/src/cap_agent/core/config.py`：pydantic-settings 读取 `TERMINAL_URL`、`BROWSER_CDP_URL`、`GUI_DISPLAY` 等环境变量
- [ ] T015 [P] 编写 `cap-agent/src/cap_agent/core/exceptions.py`：自定义 `UpstreamError`、`InvalidActionError`、`TmuxError`
- [ ] T016 实现 `cap-agent/src/cap_agent/routers/health.py`：`GET /v1/health` 返回 `{"status": "ok"}`（让 T012 通过）
- [ ] T017 编写 `cap-agent/src/cap_agent/main.py`：FastAPI app + lifespan + 注册 health router
- [ ] T018 [P] 编写 `cap-agent/Dockerfile`：`FROM base-python312`，多阶段（builder + runtime），target 区分 `prod`/`test`（FR-032）
- [ ] T019 [P] 编写 `cap-agent/tests/conftest.py`：`TestClient` fixture、临时 env override
- [ ] T020 实现 `Makefile` 的 `test-agent` 目标：`uv run pytest cap-agent/tests/unit --cov=cap_agent --cov-fail-under=80`（FR-029、SC-003）
- [ ] T021 [P] 编写 `cap-agent/README.md`：开发流程、测试运行、配置项说明

### Phase 2.3: E2E 框架起点 (M9 部分)

- [ ] T022 [P] 编写 `tests/pyproject.toml`：依赖 httpx、pytest、pytest-asyncio
- [ ] T023 [P] 编写 `tests/conftest.py`：`base_url = "http://localhost"` httpx client fixture（参照 plan.md 项目结构）
- [ ] T024 [P] e2e 占位测试 `tests/e2e/test_health.py`：断言 `GET /v1/health` 在 docker compose up 后返回 200（FR-031 起点，US1 真正实现）

**Checkpoint**: base 镜像构建成功；cap-agent `make test-agent` 全绿、行覆盖 ≥80%；E2E 框架就绪（test 暂为 skip）。

---

## Phase 3: User Story 1 - 一键启动整套沙箱 (Priority: P1) 🎯 MVP

**Goal**: `make up` 拉起 7 个 cap-* 容器，`http://localhost/` 可访问 noVNC、code-server、JupyterLab、terminal。

**Independent Test**: `make build && make up && curl http://localhost/v1/health` 返回 200（FR-005、SC-002）。

**对应 milestone**: M5（cap-nginx）+ M6（cap-browser）+ M8（cap-code/jupyter）

**关联 FR**: FR-005~FR-013、FR-014~FR-015、FR-022~FR-025

### Phase 3.1: docker-compose 编排骨架

- [ ] T025 [US1] 编写 `docker-compose.yml` 的 7 个服务定义（cap-nginx/cap-agent/cap-browser/cap-terminal/cap-code/cap-jupyter/cap-mcp），含 `sandbox-net` 网络（FR-005、FR-009）
- [ ] T026 [US1] 配置 docker-compose 安全与资源：所有服务 `cap_drop: [ALL]` + `no-new-privileges: true`（FR-007），按 FR-008 设置 mem_limit
- [ ] T027 [US1] 配置 docker-compose 端口策略：仅 cap-nginx `ports: ["${PORT:-80}:80"]`，其余 `expose`（FR-006）
- [ ] T028 [US1] 配置 docker-compose 挂载矩阵：`${WORKSPACE_DIR}` → `/workspace/`（FR-011），`.chromium/` 仅 cap-browser rw、其它不挂载（FR-012）

### Phase 3.2: cap-nginx (M5, FR-014~FR-015)

- [ ] T029 [P] [US1] [test-contract] 编写 `cap-nginx/tests/test_routes.py`：用 nginx-unit-test 或 python-nginx-test 断言 10 个 location 配置存在（参照 contracts/nginx-routes.md）
- [ ] T030 [US1] 编写 `cap-nginx/nginx.conf`：10 个 location 反代（FR-014），含 `/novnc/`→cap-browser:6080、`/terminal/`→cap-terminal:7681、`/code-server/`→cap-code:8081、`/jupyter/`→cap-jupyter:8888、`/v1/`+`/gui/`+`/cdp/`→cap-agent:9000、`/mcp/sandbox/`→cap-mcp:8940
- [ ] T031 [US1] 配置 cap-nginx WebSocket 升级：`proxy_http_version 1.1` + `Upgrade`/`Connection` header 透传（FR-015，US5 细化）
- [ ] T032 [P] [US1] 编写 `cap-nginx/Dockerfile`：`FROM base-os`，安装 nginx，COPY nginx.conf
- [ ] T033 [US1] 在 docker-compose.yml 为 cap-nginx 添加 healthcheck：`curl -f http://localhost/v1/health`

### Phase 3.3: cap-browser (M6, FR-022~FR-023)

- [ ] T034 [P] [US1] 编写 `cap-browser/entrypoint.sh`：启动 Xvnc（DISPLAY=:1）+ Openbox + Chromium（`--remote-debugging-port=9222 --no-sandbox`）+ websocat（:6080）（FR-022、FR-023）
- [ ] T035 [US1] 编写 `cap-browser/Dockerfile`：`FROM base-vnc`，安装 chromium、websocat、x11-utils，COPY entrypoint.sh
- [ ] T036 [US1] 在 docker-compose.yml 为 cap-browser 添加 healthcheck：检查 :9222 CDP endpoint 与 :6080 websocat 可达
- [ ] T037 [P] [US1] e2e 冒烟测试 `tests/e2e/test_health.py`：docker compose up 后断言 7 个容器 healthy + `GET /v1/health` 200（FR-031、SC-002）

### Phase 3.4: cap-code + cap-jupyter (M8, FR-024~FR-025)

- [ ] T038 [P] [US1] 编写 `cap-code/Dockerfile`：`FROM base-node24`，安装 code-server，`--auth none`（FR-024）
- [ ] T039 [P] [US1] 编写 `cap-jupyter/Dockerfile`：`FROM base-python312`，安装 jupyterlab，`--ServerApp.token=''`（FR-025）
- [ ] T040 [US1] e2e 验证 `tests/e2e/test_static_apps.py`：`GET /code-server/` 与 `GET /jupyter/` 非 502/504

**Checkpoint**: `make build && make up` 后浏览器访问 `http://localhost/{novnc,code-server,jupyter,terminal}/` 全部可用。

---

## Phase 4: User Story 2 - AI Agent 通过 MCP 执行 Shell 命令 (Priority: P1)

**Goal**: MCP `shell_exec("echo hello")` 经 cap-mcp → cap-agent → cap-terminal → tmux 执行返回 stdout。

**Independent Test**: MCP client 调用 `shell_exec({"command": "echo hello"})` 返回 `{"exit_code":0,"stdout":"hello\n"}`（FR-027、SC-005）。

**对应 milestone**: M3（cap-terminal）+ M7 shell 部分

**关联 FR**: FR-017、FR-020~FR-021、FR-027（shell_exec）、FR-028

### Phase 4.1: cap-terminal (M3, FR-020~FR-021)

- [ ] T041 [P] [US2] [test-unit] pytest unit test for cap-terminal exec endpoint in `cap-terminal/tests/unit/test_exec.py`：断言 `POST /api/v1/exec` 成功返回 `exit_code/stdout/stderr`，并覆盖超时、空命令、非零退出码分支（FR-020）
- [ ] T042 [P] [US2] [test-unit] 编写 `cap-terminal/tests/unit/test_tmux_session.py`：mock libtmux.Server，断言 session/window/pane 复用逻辑（FR-021，共享 PTY）
- [ ] T043 [P] [US2] [test-unit] 编写 `cap-terminal/tests/unit/test_status.py`：`GET /api/v1/terminal/status` 与 `GET /api/v1/health` 契约（FR-020）
- [ ] T044 [P] [US2] 编写 `cap-terminal/pyproject.toml`：依赖 fastapi、uvicorn、libtmux、pydantic；dev 同 cap-agent
- [ ] T045 [P] [US2] 实现 `cap-terminal/src/cap_terminal/tmux_session.py`：libtmux 包装，固定 session `sandbox` + window，懒初始化 + respawn（让 T042 通过；edge：tmux server 异常 respawn）
- [ ] T046 implementation of POST /api/v1/exec in `cap-terminal/src/cap_terminal/routers/exec.py`：调用 tmux_session.run，捕获 stdout/stderr/exit_code（让 T041 通过）
- [ ] T047 [P] [US2] 实现 `cap-terminal/src/cap_terminal/routers/status.py`：`GET /api/v1/terminal/status` + `GET /api/v1/health`（让 T043 通过）
- [ ] T048 [US2] 编写 `cap-terminal/src/cap_terminal/main.py`：FastAPI app + 注册 routers
- [ ] T049 [P] [US2] 编写 `cap-terminal/Dockerfile`：`FROM base-python312`，安装 tmux，多阶段（FR-032）
- [ ] T050 [US2] 实现 `Makefile` 的 `test-terminal`：`uv run pytest cap-terminal/tests --cov-fail-under=80`（FR-029、SC-003）

### Phase 4.2: cap-agent /v1/shell/exec 转发 (M4 部分, FR-017)

- [ ] T051 [US2] [test-integration] 编写 `cap-agent/tests/integration/test_shell_proxy.py`：用 respx mock cap-terminal:7682，断言 `POST /v1/shell/exec` 透传请求与响应（FR-017、FR-030）
- [ ] T052 [US2] 实现 `cap-agent/src/cap_agent/services/terminal_client.py`：async httpx client → cap-terminal:7682
- [ ] T053 [US2] 实现 `cap-agent/src/cap_agent/routers/shell.py`：`POST /v1/shell/exec` 调 terminal_client（让 T051 通过）

### Phase 4.3: cap-mcp shell_exec 工具 (M7 shell 部分, FR-026~FR-028)

- [ ] T054 [P] [US2] [test-unit] 编写 `cap-mcp/tests/unit/test_tool_shell.py`：mock cap-agent:9000/v1/shell/exec，断言 `shell_exec` MCP 工具转发与 JSON Schema（参照 contracts/cap-mcp-tools.md）
- [ ] T055 [P] [US2] 编写 `cap-mcp/pyproject.toml`：依赖 fastmcp、httpx、pydantic
- [ ] T056 [US2] 实现 `cap-mcp/src/cap_mcp/tools/shell.py`：`shell_exec` 工具 → cap-agent:9000/v1/shell/exec（让 T054 通过；FR-028）
- [ ] T057 [US2] 实现 `cap-mcp/src/cap_mcp/main.py`：fastmcp Streamable HTTP server 注册 shell 工具（FR-026）
- [ ] T058 [US2] e2e 验证 `tests/e2e/test_shell_roundtrip.py`：MCP client → `shell_exec("echo hello")` → 断言 stdout（FR-031、SC-005）

**Checkpoint**: MCP shell_exec 端到端通；浏览器 `/terminal/` 可见 AI 执行的命令历史（共享语义）。

---

## Phase 5: User Story 3 - AI Agent 通过 MCP 控制共享浏览器 (Priority: P1)

**Goal**: MCP `browser_navigate/click/snapshot` 操作 cap-browser 内同一 Chromium 实例。

**Independent Test**: 手动开 example.com，MCP `browser_snapshot()` 返回的 URL 与手动一致。

**对应 milestone**: M7 browser 部分（playwright-python）

**关联 FR**: FR-019、FR-027（browser_*）、FR-028

- [ ] T059 [P] [US3] [test-unit] 编写 `cap-mcp/tests/unit/test_tool_browser.py`：mock playwright，断言 `browser_navigate/click/type/snapshot/screenshot` 5 工具转发逻辑与 schema
- [ ] T060 [US3] 实现 `cap-mcp/src/cap_mcp/tools/browser.py`：用 playwright-python 连接 cap-browser:9222 CDP endpoint（FR-028；共享 tab）
- [ ] T061 [US3] 在 cap-mcp/main.py 注册 browser 工具（与 T057 合并或独立 import）
- [ ] T062 [US3] 实现 `cap-agent/src/cap_agent/routers/cdp.py` + `services/browser_cdp_client.py`：反代 `GET /cdp/json` + `WS /cdp/devtools/*` → cap-browser:9222（FR-019）
- [ ] T063 [US3] [test-integration] 编写 `cap-agent/tests/integration/test_cdp_proxy.py`：mock cap-browser:9222，断言 CDP 反代路径
- [ ] T064 [US3] e2e 验证 `tests/e2e/test_browser_navigate.py`：MCP `browser_navigate("https://example.com")` 返回 `{"ok":true,"title":"Example Domain"}`（FR-031）

**Checkpoint**: AI 与人类共享同一 Chromium tab；登录态跨 human/agent 一致。

---

## Phase 6: User Story 4 - 文件读写穿越容器边界 (Priority: P1)

**Goal**: MCP `fs_read/write/list` 操作 `/workspace/`，cap-code/cap-terminal 同步可见。

**Independent Test**: MCP 写 `/workspace/shared/test.txt`，cap-terminal `cat` 内容一致（SC-006）。

**对应 milestone**: M7 fs 部分

**关联 FR**: FR-011~FR-012、FR-027（fs_*）

- [ ] T065 [P] [US4] [test-unit] 编写 `cap-mcp/tests/unit/test_tool_fs.py`：临时目录 mock `/workspace/`，断言 `fs_read/write/list/search` 4 工具正确性与边界（不存在、权限、二进制）
- [ ] T066 [US4] 实现 `cap-mcp/src/cap_mcp/tools/fs.py`：直接文件 IO（async `aiofiles` 或 `asyncio.to_thread`），路径必须落在 `/workspace/` 内（防穿越）
- [ ] T067 [US4] 在 cap-mcp/main.py 注册 fs 工具
- [ ] T068 [US4] e2e 验证 `tests/e2e/test_fs_roundtrip.py`：`fs_write` → 在 cap-terminal `cat` → `fs_read` 内容一致（FR-031、SC-006）

**Checkpoint**: Workspace 跨容器 rw/ro 一致性验证通过。

---

## Phase 7: User Story 5 - cap-nginx 反代细节 (Priority: P1)

**Goal**: WS 升级稳定、上游不可用返回 502、超时与僵尸 WS 清理。

**Independent Test**: 每个路径前缀请求非 502/504；WS 长连接透传 ttyd（FR-015）。

**对应 milestone**: M5 细化

**关联 FR**: FR-014~FR-015

- [ ] T069 [US5] 完善 `cap-nginx/nginx.conf` 超时配置：`proxy_connect_timeout 5s`、`proxy_read_timeout 3600s`（WS）、`proxy_send_timeout 60s`
- [ ] T070 [US5] [test-e2e] 编写 `tests/e2e/test_nginx_502.py`：停止 cap-jupyter 后 `GET /jupyter/` 返回 502（不卡死，US5 AC2）
- [ ] T071 [US5] [test-e2e] 编写 `tests/e2e/test_nginx_websocket.py`：用 websockets client 连 `/terminal/` 与 `/novnc/`，断言 WS 透传 + 断开后释放
- [ ] T072 [US5] 配置 nginx 空闲 WS 超时断开：`proxy_read_timeout 300s`（5 分钟，edge case：僵尸 noVNC 连接）

**Checkpoint**: cap-nginx 反代健壮性达标。

---

## Phase 8: User Story 6 - GUI 桌面操作 (Priority: P1)

**Goal**: `/gui/screenshot` 返回 PNG；`/gui/actions` 支持 16 种 pyautogui 动作。

**Independent Test**: `GET /gui/screenshot` 返回 image/png 大小 > 1KB。

**对应 milestone**: M4 cap-agent /gui/*

**关联 FR**: FR-018、FR-027（desktop_*）、FR-028

- [ ] T073 [P] [US6] [test-unit] 编写 `cap-agent/tests/unit/test_gui_actions_model.py`：断言 16 种 action_type 的 pydantic discriminated union（参照 data-model.md 与 contracts/cap-agent-api.md）
- [ ] T074 [P] [US6] [test-unit] 编写 `cap-agent/tests/unit/test_gui_screenshot.py`：mock pyautogui + PIL，断言返回 PNG bytes > 1KB
- [ ] T075 [P] [US6] 实现 `cap-agent/src/cap_agent/models/actions.py`：16 种桌面动作 discriminated union（click/dbl_click/right_click/move_to/move_rel/scroll/drag/typing/hotkey/key_down/key_up/screenshot/wait/locate/wait_for/resize）
- [ ] T076 [US6] 实现 `cap-agent/src/cap_agent/services/gui_backend.py`：pyautogui 唯一持有者，所有调用包 `asyncio.to_thread`（R4 缓解）
- [ ] T077 [US6] 实现 `cap-agent/src/cap_agent/routers/gui.py`：`GET /gui/screenshot` + `POST /gui/actions`（让 T073、T074 通过；FR-018）
- [ ] T078 [US6] 配置 cap-agent 容器 DISPLAY=:1 + X 共享 cap-browser（Xvnc TCP 5901 或共享 socket）
- [ ] T079 [P] [US6] [test-unit] 编写 `cap-mcp/tests/unit/test_tool_desktop.py`：mock cap-agent:9000/gui，断言 `desktop_screenshot/click/type` 3 工具转发
- [ ] T080 [US6] 实现 `cap-mcp/src/cap_mcp/tools/desktop.py`：转发到 cap-agent:9000/gui（FR-028）
- [ ] T081 [US6] e2e 验证 `tests/e2e/test_screenshot.py`：`GET /gui/screenshot` 返回 PNG（FR-031）

**Checkpoint**: 跨容器 X 共享 + pyautogui 桌面操作可用。

---

## Phase 9: User Story 7 - AGENTS.md 启动注入 (Priority: P2)

**Goal**: cap-mcp 首次收到 MCP 请求时读取 `/workspace/AGENTS.md` + `README.md` + 顶层目录列表作为 system prompt 上下文。

**Independent Test**: workspace 放置 AGENTS.md，调用 MCP `tools/list` 后 server metadata 含 workspace context。

**对应 milestone**: M7 workspace_context.py（stretch goal）

**关联 FR**: FR-013

- [ ] T082 [P] [US7] [test-unit] 编写 `cap-mcp/tests/unit/test_workspace_context.py`：mock 文件系统，断言 AGENTS.md 存在/不存在/降级 README 三种场景
- [ ] T083 [US7] 实现 `cap-mcp/src/cap_mcp/workspace_context.py`：懒加载，首次请求时读取并 cache；AGENTS.md 不存在则降级 README.md，再否则仅列目录（让 T082 通过；FR-013）
- [ ] T084 [US7] 在 cap-mcp/main.py 把 workspace_context 注入 fastmcp server 的 system prompt（lifespan hook）
- [ ] T085 [US7] [test-integration] 编写 `cap-mcp/tests/integration/test_agents_md_injection.py`：临时 workspace + AGENTS.md，启动 fastmcp client 断言 metadata

**Checkpoint**: AGENTS.md 注入按约定工作。

---

## Phase 10: Polish & Cross-Cutting Concerns (M9 完整 E2E + 部署 + 安全)

**Goal**: 全量 E2E 全绿、部署文档完整、安全 hardening、性能验证。

**对应 milestone**: M9 完整

**关联 FR**: FR-029~FR-032、SC-001~SC-008

- [ ] T086 [P] 实现 `Makefile` 的 `test-e2e` 目标：`docker compose up -d --wait && pytest tests/e2e`（FR-031、SC-004）
- [ ] T087 [P] 编写 `docs/architecture.md`：绘制服务依赖图与挂载矩阵
- [ ] T088 [P] 编写 `docs/deployment.md`：从 quickstart.md 提炼的部署手册，含 macOS/Linux 差异、端口冲突排查
- [ ] T089 [P] 编写 `docs/troubleshooting.md`：常见问题（Chromium no-sandbox、libtmux 版本、bind mount 慢、WS 升级失败）
- [ ] T090 [P] 安全 hardening 审计：核对 FR-007（cap_drop）、FR-008（mem_limit）、FR-012（挂载矩阵）在 docker-compose.yml 全部生效
- [ ] T091 性能验证脚本 `tests/e2e/test_perf_scs.py`：覆盖 SC-001（build <8min）、SC-002（up <90s）、SC-005（shell_exec <500ms）、SC-006（fs 一致性 <100ms）、SC-007（内存 <5GB）
- [ ] T092 [P] 完善 quickstart.md 端到端验证清单：对每条 SC 编写可执行命令
- [ ] T093 [P] [test-e2e] 编写 `tests/e2e/test_resilience.py`：cap-browser 崩溃重启后 cap-mcp browser 工具自动恢复 <10s（SC-008、edge case）
- [ ] T094 顶层 README.md：项目介绍、快速开始、文档导航、license

**Checkpoint**: P1 全栈交付完成，`make build && make up && make test-e2e` 全绿。

---

## Dependencies & Execution Order

### Phase 依赖

- **Phase 1 Setup**: 无依赖，立即开始
- **Phase 2 Foundational**: 依赖 Phase 1。**阻塞所有 US**
- **Phase 3 US1 (MVP)**: 依赖 Phase 2 完成。阻塞 Phase 4-9（US1 是其他 US 的运行时基础）
- **Phase 4 US2 shell**: 依赖 Phase 2（cap-agent MVP）+ Phase 3（cap-nginx 反代就绪）
- **Phase 5 US3 browser**: 依赖 Phase 2（cap-agent/cap-mcp 骨架）+ Phase 3（cap-browser 容器就绪）
- **Phase 6 US4 fs**: 依赖 Phase 2（cap-mcp 骨架）+ Phase 3（workspace 挂载就绪）。**与 Phase 4/5 完全并行**
- **Phase 7 US5 nginx 细化**: 依赖 Phase 3（cap-nginx 基础就绪）
- **Phase 8 US6 gui**: 依赖 Phase 3（cap-browser X server 就绪）
- **Phase 9 US7 AGENTS.md**: 依赖 Phase 2（cap-mcp 骨架）。**P2，可与任何 P1 US 并行**
- **Phase 10 Polish**: 依赖所有目标 US 完成

### US 依赖

| US | 优先级 | 前置 |
|----|--------|------|
| US1 | P1 | Phase 2 |
| US2 | P1 | Phase 2 + US1（nginx） |
| US3 | P1 | Phase 2 + US1（cap-browser 容器） |
| US4 | P1 | Phase 2 + US1（workspace 挂载） |
| US5 | P1 | US1（cap-nginx 基础） |
| US6 | P1 | US1（cap-browser X 共享） |
| US7 | P2 | Phase 2 |

### Phase 内部顺序

- Test（Red）→ Model → Service → Router（Green）→ E2E
- cap-terminal 先 tmux_session 后 router/exec
- cap-agent 先 services/* 后 routers/*
- cap-mcp 先 tools/* 后 main.py 注册

### Parallel Opportunities

- Phase 1：T002-T005 全部 [P]
- Phase 2.1：T006-T009（4 个 base Dockerfile）全部 [P]
- Phase 2.2：T012-T015、T018-T019、T021 多数 [P]
- Phase 2.3：T022-T024 全部 [P]
- Phase 3.2：T029、T032 [P]
- Phase 3.3：T034、T037 [P]
- Phase 3.4：T038-T039 [P]
- Phase 4.1：T041-T044、T047、T049 多数 [P]
- Phase 5-9：US4/US5/US6/US7 在 Phase 3 完成后可并行（不同文件、不同模块）
- Phase 10：T087-T092、T094 多数 [P]

---

## Parallel Example: Phase 4 (US2) 并行块

```bash
# 三个 cap-terminal 的 unit test 可并行（不同文件、无依赖）
Task: "T041 pytest unit test for cap-terminal exec endpoint in cap-terminal/tests/unit/test_exec.py"
Task: "T042 cap-terminal/tests/unit/test_tmux_session.py"
Task: "T043 cap-terminal/tests/unit/test_status.py"

# cap-mcp 的工具单测可与 cap-agent integration 并行
Task: "T054 cap-mcp/tests/unit/test_tool_shell.py"
Task: "T051 cap-agent/tests/integration/test_shell_proxy.py"
```

---

## Implementation Strategy

### MVP First (US1 + US2 双核心闭环)

1. Phase 1 Setup → 仓库骨架
2. Phase 2 Foundational → base 镜像 + cap-agent MVP + E2E 框架
3. Phase 3 US1 → `make up` 一键拉起，`curl /v1/health` 200（**MVP checkpoint 1**）
4. Phase 4 US2 → MCP shell_exec 端到端通（**MVP checkpoint 2**，覆盖核心业务闭环）
5. **STOP and VALIDATE**：跑 `make test-e2e`，确认核心路径全绿

### Incremental Delivery

1. Phase 1-2 → 基础设施就绪
2. +Phase 3 → 一键启动 demo 可用
3. +Phase 4 → AI shell 能力可用
4. +Phase 5 → AI 浏览器能力可用
5. +Phase 6 → 文件读写一致性验证
6. +Phase 7 → 反代健壮性达标
7. +Phase 8 → GUI 桌面操作可用
8. +Phase 9（stretch）→ AGENTS.md 注入
9. +Phase 10 → 全栈交付、文档、安全 hardening

### Parallel Team Strategy

多开发者协作：

1. 团队共同完成 Phase 1-3（US1 是后续基础，串行）
2. US1 完成后：
   - Dev A：Phase 4 US2（cap-terminal + shell 工具链）
   - Dev B：Phase 5 US3（browser 工具链）
   - Dev C：Phase 6 US4（fs 工具链）+ Phase 9 US7
3. 并行收口：Phase 7 US5（nginx）、Phase 8 US6（gui）由熟悉 cap-browser/cap-nginx 的开发者承担
4. Phase 10 Polish 团队共同 review

---

## Notes

- [P] 任务 = 不同文件、无依赖，可并行
- [US#] 标签映射到 spec.md 对应 user story，便于追溯 FR/SC
- TDD 严格：每个 feature 先写失败 test，再写实现；不允许"先写实现再补 test"
- 跨服务契约（contracts/*.md）作为 stub-first 起点：上游先返回 mock，下游单测可先行
- 镜像分层缓存：变更频繁的 cap-agent/terminal/mcp 走 base-python312 → 周级缓存链
- 测试镜像与生产共享 Dockerfile（multi-stage target，FR-032）
- 每个 checkpoint 后提交一次 git commit，便于回滚
- macOS 开发注意：Chromium `--no-sandbox`、libtmux 版本、bind mount 性能（R1/R2/R8）
- 避免：跨 US 的隐式依赖（US4 fs 不应依赖 US2 shell 实现）；同文件并发修改（同一 router 内的 test 与 impl 串行）
