# Feature Specification: AI 个人沙箱 P1 全栈

**Feature Branch**: `001-sandbox-p1-stack`

**Created**: 2026-06-18

**Status**: Draft

**Source**: `.archive/sandbox-design.md`（4331 行设计文档 §1–§18）

**Input**: 在本地单机受信环境部署一个 AI 与人类共享的 Linux 沙箱运行时。覆盖 4 个 base 镜像 + 7 个 cap-* 服务，全部以 TDD（Unit + Integration + 镜像 E2E）落地。P1 不引入多租户/应用层认证/公网部署。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 本地开发者启动整套沙箱 (Priority: P1)

开发者 `git clone` 仓库后执行 `make up`，docker compose 拉起 7 个 cap-* 容器，浏览器访问 `http://localhost/` 即可看到 noVNC 桌面、`/code-server/` Web VS Code、`/jupyter/` JupyterLab、`/terminal/` Web Terminal，所有功能开箱即用。

**Why this priority**: 没有"一键启动"，后续所有用户故事都无法验证。这是验证整套 P1 架构的最小可独立单元。

**Independent Test**: `make up && curl http://localhost/v1/health` 返回 200 即视为通过。

**Acceptance Scenarios**:

1. **Given** 干净的 Docker 环境，**When** 执行 `make build && make up`，**Then** 7 个 cap-* 容器全部 healthy，耗时 < 5 分钟。
2. **Given** 容器已 healthy，**When** 浏览器访问 `http://localhost/novnc/`，**Then** 看到 cap-browser 内的 Xfce 桌面。
3. **Given** 容器已 healthy，**When** 浏览器访问 `http://localhost/code-server/`，**Then** 进入 code-server 编辑器界面。
4. **Given** 容器已 healthy，**When** 浏览器访问 `http://localhost/terminal/`，**Then** 进入 ttyd 终端。

---

### User Story 2 - AI Agent 通过 MCP 执行 Shell 命令 (Priority: P1)

AI Agent 进程通过 MCP Streamable HTTP 协议（`POST http://localhost/mcp/sandbox/`）调用 `shell_exec` 工具，命令最终在 cap-terminal 容器内的 tmux session 中执行，返回 stdout/stderr/exit_code。

**Why this priority**: Shell 是 Agent 操作沙箱的最核心能力，也是设计原则三（Human+Agent 共享运行时）的最小验证场景。

**Independent Test**: 启动 MCP client，调用 `shell_exec("echo hello")`，断言 stdout 包含 `hello`。

**Acceptance Scenarios**:

1. **Given** cap-mcp + cap-terminal 已 healthy，**When** 通过 MCP 协议调用 `shell_exec({"command": "echo hello"})`，**Then** 返回 `{"exit_code": 0, "stdout": "hello\n", "stderr": ""}`。
2. **Given** 已执行过一条 shell 命令，**When** 人类用户在浏览器打开 `/terminal/`，**Then** 看到刚才 AI 执行的命令历史出现在 tmux session 中（共享语义）。
3. **Given** Agent 执行 `cd /workspace/shared && touch from-agent.txt`，**When** 人类在 terminal 执行 `ls /workspace/shared/`，**Then** 看到 `from-agent.txt`（共享 cwd）。

---

### User Story 3 - AI Agent 通过 MCP 控制共享浏览器 (Priority: P1)

AI Agent 通过 MCP 调用 `browser_navigate` / `browser_click` / `browser_snapshot`，操作 cap-browser 容器内正在被用户通过 VNC 看着的同一个 Chromium 实例。

**Why this priority**: Browser 共享是设计原则三的第二大验证场景，验证 CDP 协议在 human/agent 双客户端下不冲突。

**Independent Test**: 浏览器手动打开 example.com，MCP 调用 `browser_snapshot()` 返回的 URL 与手动一致。

**Acceptance Scenarios**:

1. **Given** cap-mcp + cap-browser 已 healthy，**When** 调用 `browser_navigate({"url": "https://example.com"})`，**Then** 返回 `{"ok": true, "title": "Example Domain"}`。
2. **Given** Agent 已 navigate 到某 URL，**When** 人类在 VNC 看 Chromium，**Then** Chromium 显示同一 URL（共享 tab）。
3. **Given** Agent 已登录某网站并保存 cookie，**When** 人类在同一 Chromium 重新打开该网站，**Then** 无需重新登录（共享登录态）。

---

### User Story 4 - 文件读写穿越容器边界 (Priority: P1)

AI Agent 通过 MCP 的 `fs_read` / `fs_write` / `fs_list` 工具操作 `/workspace/` 目录下的文件，cap-code（VS Code）和 cap-terminal 也能看到同样的文件变更。

**Why this priority**: Workspace 即 Memory（设计原则二、四）是整个系统的状态载体，必须验证挂载矩阵正确。

**Independent Test**: MCP 写入 `/workspace/shared/test.txt`，在 cap-terminal 内 `cat` 该文件内容一致。

**Acceptance Scenarios**:

1. **Given** 所有服务 healthy，**When** MCP 调用 `fs_write({"path": "/workspace/shared/note.md", "content": "hi"})`，**Then** 返回 `{"ok": true, "bytes": 2}`。
2. **Given** Agent 已写入 `/workspace/shared/note.md`，**When** 人类在 cap-code 内打开同一文件，**Then** 看到 `hi`（rw 共享）。
3. **Given** cap-code 用户保存了 `/workspace/code/main.py`，**When** Agent 通过 `fs_read` 读取该文件，**Then** 内容一致（ro 读访问）。

---

### User Story 5 - cap-nginx 反代各服务到统一端口 (Priority: P1)

外部所有访问 `http://localhost/` 的请求由 cap-nginx 反向代理到对应 cap-* 服务，路由前缀包括 `/novnc/` `/terminal/` `/code-server/` `/jupyter/` `/v1/` `/cdp/` `/gui/` `/mcp/sandbox/`。

**Why this priority**: 设计原则五（nginx 唯一 HTTP 入口），是所有外部访问的咽喉。

**Independent Test**: 对每个路径前缀发起 HTTP 请求，断言响应非 502/504。

**Acceptance Scenarios**:

1. **Given** 所有上游服务 healthy，**When** 客户端 `GET /code-server/`，**Then** 返回 code-server 静态资源（HTTP 200）。
2. **Given** cap-jupyter 重启中，**When** 客户端 `GET /jupyter/`，**Then** 返回 502（上游不可用，不卡死）。
3. **Given** 客户端通过 `/terminal/` 建立 WebSocket，**Then** WebSocket 长连接透传到 ttyd，断开后释放。

---

### User Story 6 - 桌面操作通过 GUI 路由 (Priority: P1)

cap-agent 暴露 `/gui/screenshot` 与 `/gui/actions`，把 pyautogui 风格的桌面操作（16 种动作）转发到 cap-browser 的 DISPLAY 上。

**Why this priority**: 验证 GUI 操作的归属（pyautogui 唯一持有者为 cap-agent）和跨容器 X server 访问。

**Independent Test**: 调用 `/gui/screenshot` 返回 PNG 截图（非空）。

**Acceptance Scenarios**:

1. **Given** cap-agent + cap-browser 已 healthy，**When** `GET /gui/screenshot`，**Then** 返回 `image/png` 且大小 > 1KB。
2. **Given** 用户已在 Chromium 上聚焦输入框，**When** `POST /gui/actions` 提交 `{"action_type": "typing", "text": "abc"}`，**Then** 输入框内容更新为 `abc`。

---

### User Story 7 - AGENTS.md 启动注入 (Priority: P2)

cap-mcp 首次收到 MCP 请求时，读取 `/workspace/AGENTS.md`（若存在）、`/workspace/README.md`、列出 workspace 顶层目录，作为 system prompt 上下文附加。

**Why this priority**: 设计原则四的物理落地，但属于元能力增强，不影响核心功能。可作为 P1 的 stretch goal。

**Independent Test**: workspace 放置 AGENTS.md，调用 MCP `tools/list` 后查看 server 返回的 metadata 中是否含 workspace context。

**Acceptance Scenarios**:

1. **Given** `/workspace/AGENTS.md` 存在内容 `# 项目说明 ...`，**When** cap-mcp 收到首个请求，**Then** 该内容被附加到 server 上下文。
2. **Given** `/workspace/AGENTS.md` 不存在，**When** cap-mcp 收到首个请求，**Then** 降级使用 README.md（若存在），不报错。

---

### Edge Cases

- cap-browser 崩溃重启后，CDP 端点恢复，cap-mcp 的浏览器工具自动重连。
- cap-terminal 内 tmux server 异常退出时，shell-exec-api 自动 respawn。
- `/workspace/.chromium/` 目录权限丢失时，cap-browser 启动应失败并给出明确错误。
- 多个 MCP 客户端并发调用 `shell_exec` 时，命令在 tmux 中排队执行，不丢失。
- 大文件（>1GB）通过 `/v1/file/upload` 上传时，不撑爆内存（流式）。
- WebSocket 在 `/novnc/` 空闲超过 5 分钟时被 cap-nginx 主动断开（避免僵尸连接）。

## Requirements *(mandatory)*

### Functional Requirements

#### 镜像构建

- **FR-001**: 系统 MUST 提供 4 个 base 镜像：`base-os`（Ubuntu 24.04）、`base-vnc`（X 显示栈）、`base-node24`（Node.js 24）、`base-python312`（uv + Python 3.12）。
- **FR-002**: base 镜像 MUST 通过 Dockerfile 多阶段构建，`base-os` 作为所有其它镜像的祖先。
- **FR-003**: 镜像构建 MUST 通过 `make build` 一键完成，支持并行构建以加速。
- **FR-004**: 每个 cap-* 镜像 MUST 显式声明 `FROM base-*`，不允许跳过继承链。

#### 容器编排

- **FR-005**: 系统 MUST 通过 `docker-compose.yml` 编排 7 个 cap-* 服务，cap-nginx 作为唯一对外端口（默认 80）。
- **FR-006**: 除 cap-nginx 外的所有 cap-* 服务 MUST 仅 `expose`（不 `ports`），仅 sandbox-net 内可达。
- **FR-007**: docker-compose MUST 为所有服务设置 `cap_drop: [ALL]` 与 `security_opt: [no-new-privileges:true]`。
- **FR-008**: docker-compose MUST 设置资源限制：cap-browser 2g / cap-jupyter 2g / cap-code 1g / cap-mcp 768m / cap-terminal 512m / cap-agent 384m / cap-nginx 64m。
- **FR-009**: docker-compose MUST 定义 `sandbox-net`（bridge）网络，所有 cap-* 加入。
- **FR-010**: cap-mcp 与 cap-agent MUST 通过 `depends_on` + healthcheck 依赖 cap-browser 与 cap-terminal。

#### Profile 层

- **FR-011**: 系统 MUST 把宿主机 `~/sandbox-workspace/`（或 `${WORKSPACE_DIR}`）挂载到所有容器的 `/workspace/`。
- **FR-012**: docker-compose MUST 按设计文档 §7.2 挂载矩阵分别配置 rw/ro 权限（如 `.chromium/` 仅 cap-browser rw，其它容器无此挂载）。
- **FR-013**: 系统 MUST 支持读取 `/workspace/AGENTS.md` 作为 Agent 启动上下文注入（若文件存在）。

#### 服务能力

- **FR-014**: cap-nginx MUST 反代以下路径前缀到对应上游：`/novnc/`→cap-browser:6080、`/terminal/`→cap-terminal:7681、`/code-server/`→cap-code:8081、`/jupyter/`→cap-jupyter:8888、`/v1/`、`/auth/`、`/cdp/`、`/gui/`→cap-agent:9000、`/mcp/sandbox/`→cap-mcp:8940。
- **FR-015**: cap-nginx MUST 支持 WebSocket 升级（用于 noVNC、ttyd、CDP WS）。
- **FR-016**: cap-agent MUST 暴露 `GET /v1/health` 返回 `{"status": "ok"}` 用于 healthcheck。
- **FR-017**: cap-agent MUST 暴露 `POST /v1/shell/exec` 透传到 cap-terminal:7682。
- **FR-018**: cap-agent MUST 暴露 `GET /gui/screenshot` 与 `POST /gui/actions`（16 种 pyautogui 动作）。
- **FR-019**: cap-agent MUST 反代 `GET /cdp/json` 与 `WS /cdp/devtools/*` 到 cap-browser:9222。
- **FR-020**: cap-terminal MUST 提供 shell-exec-api（端口 7682）：`POST /api/v1/exec`、`GET /api/v1/terminal/status`、`GET /api/v1/health`。
- **FR-021**: cap-terminal shell-exec-api MUST 基于 libtmux 在固定 session（如 `sandbox`）的 window 上执行命令，确保 Human+Agent 共享。
- **FR-022**: cap-browser MUST 启动 Chromium 监听 `--remote-debugging-port=9222 --no-sandbox`（P1 安全降级，§1.1.2）。
- **FR-023**: cap-browser MUST 启动 Xvnc（DISPLAY=:1）+ Openbox + websocat（端口 6080），noVNC 静态文件由 cap-nginx 提供。
- **FR-024**: cap-code MUST 启动 code-server 监听端口 8081，auth 设为 `none`（P1）。
- **FR-025**: cap-jupyter MUST 启动 JupyterLab 监听端口 8888，token 设为空（P1）。
- **FR-026**: cap-mcp MUST 通过 Streamable HTTP（端口 8940）暴露 MCP server。
- **FR-027**: cap-mcp MUST 实现以下工具：`shell_exec`、`fs_read`、`fs_write`、`fs_list`、`fs_search`、`browser_navigate`、`browser_click`、`browser_type`、`browser_snapshot`、`browser_screenshot`、`desktop_screenshot`、`desktop_click`、`desktop_type`。
- **FR-028**: cap-mcp 的 `shell_exec` MUST 转发到 cap-terminal:7682，`browser_*` MUST 转发到 cap-browser:9222（CDP），`desktop_*` MUST 转发到 cap-agent:9000/gui。

#### P1 明确不做（依据 §1.1.2 能力矩阵）

- **FR-NI-1**: P1 不实现应用层认证（`AUTH_MODE=none`），仅靠 sandbox-net 网络隔离。
- **FR-NI-2**: P1 不实现 shell 命令策略（`permissive` 模式，不拦任何命令）。
- **FR-NI-3**: P1 不实现 LLM endpoint 白名单。
- **FR-NI-4**: P1 不实现审计落库（仅 `docker compose logs`）。
- **FR-NI-5**: P1 不实现跨 workspace 元数据（无 Orchestrator）。
- **FR-NI-6**: P1 不实现 Snapshot 编排（仅保留 docker volume 级别备份能力）。

#### 测试

- **FR-029**: 每个 Python 服务（cap-agent/cap-terminal/cap-mcp）MUST 有 pytest 单元测试，行覆盖率 ≥ 80%。
- **FR-030**: cap-agent MUST 有 Integration 测试，使用 respx mock cap-terminal/cap-browser 的 HTTP 调用。
- **FR-031**: 系统 MUST 提供 `make test-e2e`，通过 docker compose 起完整 stack 后用 httpx 打 cap-nginx 验证关键路径（health、shell_exec、fs_roundtrip、browser_navigate）。
- **FR-032**: 测试镜像 MUST 与生产镜像共享 Dockerfile（multi-stage target 区分），避免双倍维护。

### Key Entities *(include if feature involves data)*

- **Workspace**: 宿主机目录，挂载到所有容器 `/workspace/`，是状态唯一载体。包含子目录 `code/` `notebooks/` `shared/` `.chromium/` `.vscode/` `.jupyter/` 与 `AGENTS.md`。
- **Sandbox-Net**: Docker bridge 网络，所有 cap-* 加入，对外仅 cap-nginx 暴露 80 端口。
- **MCP Tool**: cap-mcp 暴露的命名工具（`shell_exec` / `fs_read` 等），有名字、JSON Schema 参数、转发目标。
- **CDP Target**: cap-browser 内 Chromium 的远程调试 endpoint（端口 9222），cap-agent 与 cap-mcp 共用。
- **Tmux Session**: cap-terminal 内固定 session 名（如 `sandbox`），Human 与 Agent 通过同一 session 共享 PTY。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 干净环境执行 `make build` 完成时间 < 8 分钟（4 base + 7 cap 镜像，首次冷构建）。
- **SC-002**: 干净环境执行 `make up` 到所有服务 healthy 时间 < 90 秒（镜像已构建）。
- **SC-003**: 所有 Python 服务的 pytest 单元测试行覆盖率 ≥ 80%。
- **SC-004**: `make test-e2e` 在 5 分钟内全绿，覆盖至少 5 个核心路径（health/shell/fs/browser/screenshot）。
- **SC-005**: MCP 调用 `shell_exec("echo hello")` 端到端延迟 < 500ms（不含命令本身执行时间）。
- **SC-006**: 文件 `/workspace/shared/x` 写入后，在 cap-code/cap-terminal 内可见的延迟 < 100ms（bind mount 一致性）。
- **SC-007**: 7 个 cap-* 容器稳态总内存占用 < 5GB（不含 Chromium 渲染开销）。
- **SC-008**: cap-browser 崩溃重启后，cap-mcp 的 browser 工具自动恢复 < 10 秒。

## Assumptions

- 用户在 Linux/macOS 主机上运行 Docker（macOS 下 Chromium `--no-sandbox` 兼容，性能略低）。
- 宿主机已安装 Docker 24+ 与 docker compose v2。
- 主机默认无其他服务占用 80 端口；如占用可通过 `PORT=8080 make up` 切换。
- 用户具备 sudo 权限（用于配置 `/etc/hosts` 或 host firewall，可选）。
- P1 阶段不暴露到公网，所有访问通过 `localhost` 或 LAN IP。
- 各 Python 服务可访问互联网以下载 PyPI 依赖；P2 才考虑离线/镜像源。
- code-server、JupyterLab、Chromium、TigerVNC 等使用各官方源的最新稳定版本。
- AGENTS.md 注入是约定而非 schema——文件存在时附加，不存在时静默跳过。
- snapshot/restore 仅做 docker volume 级别（`docker run --volumes-from` tar 打包），P2 才上 Orchestrator 编排。
- 测试中 cap-browser 的真实 Chromium 不可在 CI 上跑（需 GUI）；CI 上 E2E 用 mock Chromium 或仅跑非 GUI 路径。
