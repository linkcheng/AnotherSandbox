# Data Model: AI 个人沙箱 P1 全栈

**Date**: 2026-06-18
**Source**: [spec.md](./spec.md) · [plan.md](./plan.md) · [research.md](./research.md)

本文档定义 P1 阶段所有跨服务共享的核心实体与数据结构。P1 不引入数据库，这些实体是**契约形状（shape）**，由 Pydantic v2 模型在 cap-agent / cap-terminal / cap-mcp 中实现。每个实体给出：字段（中文描述）+ 类型 + 示例 + 关联实体。

---

## 1. Workspace（工作空间目录）

**关联**：所有 cap-* 容器（FR-011、FR-012）；Workspace 是状态唯一载体（设计原则二）。

宿主机 `~/sandbox-workspace/`（或 `${WORKSPACE_DIR}`）通过 bind mount 挂载到所有容器的 `/workspace/`，按子目录粒度区分 rw/ro（设计文档 §7.2 挂载矩阵）。

| 子目录 | 用途 | 主要持有者（rw） | 其他容器（ro 或无） |
|--------|------|------------------|---------------------|
| `code/` | 项目源代码 | cap-code | cap-browser ro、cap-terminal ro、cap-mcp ro、cap-agent ro |
| `notebooks/` | JupyterLab notebooks | cap-jupyter | 其他无挂载 |
| `shared/` | Human+Agent 共享交换区 | 无（只读全局） | 全部 ro |
| `.chromium/` | Chromium 用户数据（profile、cookies、cache） | cap-browser | 其他无挂载 |
| `.vscode/` | code-server 配置与扩展 | cap-code | 其他无挂载 |
| `.jupyter/` | JupyterLab 配置 | cap-jupyter | 其他无挂载 |
| `AGENTS.md` | Agent 启动上下文注入（可选，约定非 schema） | 文件（无写者） | 全部 ro（cap-mcp 读取并注入，FR-013） |
| `README.md` | 项目说明（AGENTS.md 缺失时降级使用） | 文件 | 全部 ro |

**示例路径**：
- 容器内绝对路径：`/workspace/shared/note.md`
- 宿主机对应路径：`~/sandbox-workspace/shared/note.md`

---

## 2. Sandbox-Net（容器网络）

**关联**：docker-compose 编排（FR-009）；cap-nginx 为唯一对外入口（FR-005）。

| 字段 | 类型 | 示例 | 说明 |
|------|------|------|------|
| 名称 | string | `sandbox-net` | docker bridge 网络名 |
| 驱动 | enum | `bridge` | docker compose 默认驱动 |
| 对外端口 | int | `80`（cap-nginx）| 默认；可通过 `PORT` 环境变量切换（如 8080） |
| 内部 DNS | string | `cap-agent` / `cap-terminal` / `cap-browser` / `cap-code` / `cap-jupyter` / `cap-mcp` | compose service 名即 DNS 名 |
| 隔离策略 | enum | `expose-only` | 除 cap-nginx 外所有服务仅 `expose`，不 `ports`（FR-006） |

**内部端口分配表**（FR-014、FR-016 ~ FR-028）：

| 服务 | 内部端口 | 协议 | 暴露给 |
|------|----------|------|--------|
| cap-nginx | 80 | HTTP + WS | 宿主机（唯一对外） |
| cap-agent | 9000 | HTTP | sandbox-net |
| cap-terminal | 7681（ttyd WS）、7682（shell-exec-api HTTP） | HTTP + WS | sandbox-net |
| cap-browser | 9222（CDP HTTP+WS）、6080（websockify WS） | HTTP + WS | sandbox-net |
| cap-code | 8081 | HTTP | sandbox-net |
| cap-jupyter | 8888 | HTTP | sandbox-net |
| cap-mcp | 8940 | HTTP（Streamable HTTP） | sandbox-net |

---

## 3. MCP Tool（MCP 工具定义）

**关联**：cap-mcp（FR-026、FR-027）；MCP 协议（tools/list、tools/call）；research.md R2。

| 字段 | 类型 | 示例 | 说明 |
|------|------|------|------|
| name | string（snake_case） | `shell_exec` | 工具唯一名，MCP 协议要求 |
| description | string | `"在 cap-terminal 的 tmux session 中执行 shell 命令"` | 给 LLM 的说明 |
| parameters | JSON Schema (object) | 见下 | 输入参数 schema |
| returns | JSON Schema (object) | 见 contracts/cap-mcp-tools.md | 输出 schema |
| forward_target | enum | `cap-terminal:7682` / `cap-browser:9222` / `cap-agent:9000` / `direct-fs` | 转发目标分类（FR-028） |
| category | enum | `shell` / `fs` / `browser` / `desktop` | 工具分组，便于组织 tools/list |

**命名规范**：
- snake_case 单词
- 动词 + 名词（如 `browser_navigate`、`fs_read`、`desktop_click`）
- 不使用前缀 `mcp_`（避免冗余）

**转发目标分类**：
- `shell_exec` → cap-terminal:7682（FR-017、FR-028）
- `fs_read` / `fs_write` / `fs_list` / `fs_search` → 直读直写 `/workspace/`（cap-mcp 容器内 IO）
- `browser_*` → cap-browser:9222（CDP，经 playwright connect_over_cdp，research.md R4）
- `desktop_*` → cap-agent:9000（/gui 路由，research.md R5）

完整工具清单见 `contracts/cap-mcp-tools.md`。

---

## 4. CDP Target（Chromium 远程调试 endpoint）

**关联**：cap-browser（FR-022、FR-023）；cap-agent 反代（FR-019）；cap-mcp 的 browser_* 工具（research.md R4）。

Chromium 启动参数：`chromium --remote-debugging-port=9222 --no-sandbox --user-data-dir=/workspace/.chromium`（FR-022，P1 安全降级）。

`GET http://cap-browser:9222/json` 返回 target 数组：

| 字段 | 类型 | 示例 | 说明 |
|------|------|------|------|
| id | string | `"A1B2C3D4..."` | target 唯一 ID，用于 WS 连接 |
| type | enum | `page` / `background_page` / `service_worker` | target 类型 |
| title | string | `"Example Domain"` | 页面标题 |
| url | string | `"https://example.com/"` | 当前 URL |
| webSocketDebuggerUrl | string | `ws://cap-browser:9222/devtools/page/A1B2...` | 调试 WS endpoint |
| devtoolsFrontendUrl | string | `/devtools/inspector.html?ws=...` | DevTools 前端入口 |

**关联操作**：
- cap-agent 反代 `GET /cdp/json`（透传该数组）与 `WS /cdp/devtools/{id}`（双向 WS 透传）
- cap-mcp 通过 playwright `connect_over_cdp("http://cap-browser:9222")` 直接消费（不经过 cap-agent）

---

## 5. Tmux Session（Shell 共享模型）

**关联**：cap-terminal（FR-020、FR-021）；Human+Agent 共享语义（设计原则三、research.md R3）。

**层级模型**：

```
Server (tmux 进程)
  └─ Session: sandbox（固定名，FR-021）
       └─ Window: 0（默认 window，Agent 用）
            └─ Pane: 全屏单一 pane
       └─ Window: 1（interactive 模式时 ttyd 接管）
            └─ Pane
```

| 字段 | 类型 | 示例 | 说明 |
|------|------|------|------|
| session_name | string（固定） | `sandbox` | 所有命令都在此 session 内执行 |
| windows | Window[] | 见下 | session 下 window 列表 |
| attached_clients | int | `2`（Agent + Human） | 当前连接客户端数 |

**Window 实体**：

| 字段 | 类型 | 示例 | 说明 |
|------|------|------|------|
| index | int | `0` | window 编号 |
| name | string | `agent-shell` / `human-ttyd` | 自动或手动命名 |
| active_pane | Pane | — | 当前焦点 pane |
| cwd | string（路径） | `/workspace/shared` | 工作目录，命令继承 |

**执行模型**：
- 同步阻塞：调用 `libtmux.Window.send_keys(cmd, enter=True)` 后 `capture-pane` 轮询直到命令完成或超时（默认 30s）
- 并发：tmux session 单线程，命令在 session 内排队执行，避免 race（Edge Case: 多 MCP 并发不丢失）
- interactive=true：命令进入后台 window，API 返回 window 名，ttyd 通过 `/terminal/` WS 接管 stdin（research.md R3）

---

## 6. GUI Action（16 种 pyautogui 动作）

**关联**：cap-agent `/gui/actions`（FR-018）；pyautogui（research.md R5）；discriminated union by `action_type`。

base 实体（所有动作公共字段）：

| 字段 | 类型 | 说明 |
|------|------|------|
| action_type | enum（16 值，见下） | 判别字段，决定后续字段 |

16 种 action_type 及其独有字段：

| action_type | 独有字段 | 描述 |
|-------------|----------|------|
| `click` | `x: int, y: int, button: "left"|"right"="left", clicks: int=1, interval_s: float=0.0` | 单击坐标 |
| `right_click` | `x: int, y: int` | 右键单击（click 的 button=right 快捷） |
| `double_click` | `x: int, y: int` | 双击 |
| `triple_click` | `x: int, y: int` | 三击 |
| `move_to` | `x: int, y: int, duration_s: float=0.0` | 移动光标 |
| `move_relative` | `dx: int, dy: int, duration_s: float=0.0` | 相对移动 |
| `drag_to` | `x: int, y: int, duration_s: float=0.5, button: str="left"` | 拖拽到坐标 |
| `drag_relative` | `dx: int, dy: int, duration_s: float=0.5` | 相对拖拽 |
| `scroll` | `dx: int=0, dy: int=0` | 滚轮（垂直 dy，水平 dx） |
| `mouse_down` | `x: int, y: int, button: str="left"` | 按下鼠标 |
| `mouse_up` | `x: int, y: int, button: str="left"` | 释放鼠标 |
| `typing` | `text: str, interval_s: float=0.0` | 输入文本 |
| `key_press` | `keys: string[]`（如 `["ctrl", "c"]`） | 按组合键 |
| `key_down` | `key: str` | 按下 |
| `key_up` | `key: str` | 释放 |
| `hotkey` | `keys: string[]` | 顺序按下后逆序释放（如 `["ctrl","shift","esc"]`） |

**实现约束**：pyautogui 同步阻塞，FastAPI 异步路由用 `asyncio.to_thread()` 包裹（research.md R5）。

---

## 7. Shell Exec Request / Response

**关联**：cap-terminal `/api/v1/exec`（FR-020）；cap-agent `/v1/shell/exec`（FR-017）；cap-mcp `shell_exec`（FR-027）。

### Request

| 字段 | 类型 | 必填 | 默认 | 示例 | 说明 |
|------|------|------|------|------|------|
| command | string | 是 | — | `"echo hello"` | 要执行的 shell 命令 |
| window | string | 否 | `"0"` | `"1"` | 在指定 tmux window 执行；省略用默认 |
| timeout_s | float | 否 | `30.0` | `60.0` | 单条命令超时，超时强杀 |
| interactive | bool | 否 | `false` | `true` | true 时返回 window 名并进入后台，由 ttyd 接管 stdin |

### Response（interactive=false）

| 字段 | 类型 | 示例 | 说明 |
|------|------|------|------|
| exit_code | int | `0` | 命令退出码；超时为 -1 |
| stdout | string | `"hello\n"` | 标准输出（合并） |
| stderr | string | `""` | 标准错误 |
| duration_ms | int | `12` | 命令执行耗时 |
| window | string | `"0"` | 实际执行的 window 名 |

### Response（interactive=true）

| 字段 | 类型 | 示例 | 说明 |
|------|------|------|------|
| ok | bool | `true` | 命令已派发 |
| window | string | `"1"` | ttyd 应连接的 window 名 |
| ws_url | string | `/terminal/ws/1` | ttyd WS 端点（相对 cap-nginx 根） |

---

## 8. Health Response

**关联**：所有服务的 healthcheck（FR-016、FR-020）；docker-compose `healthcheck` 字段。

统一健康响应格式：

| 字段 | 类型 | 示例 | 说明 |
|------|------|------|------|
| status | enum（`ok` / `degraded` / `down`） | `"ok"` | 服务总体健康状态 |
| service | string | `"cap-agent"` | 服务名（自报） |
| version | string | `"0.1.0"` | 服务版本（取自 pyproject 或镜像 label） |
| dependencies（可选） | object | `{"cap-terminal": "ok", "cap-browser": "ok"}` | 下游服务探测结果（cap-agent / cap-mcp 含此字段） |
| uptime_s（可选） | int | `1245` | 进程启动后秒数 |

**最小健康端点**（FR-016）：`GET /v1/health` 返回 `{"status": "ok"}`，仅用于 docker-compose healthcheck，不带 dependencies。

---

## 9. 实体关系总览

```
Workspace (文件系统)
   │
   ├─→ AGENTS.md ──→ cap-mcp (启动注入，FR-013)
   ├─→ code/notebooks/shared ──→ fs_* MCP 工具
   └─→ .chromium/ ──→ CDP Target ──→ browser_* MCP 工具
                                    │
Sandbox-Net (网络)                 cap-browser:9222
   │                                ▲
   ├─→ cap-nginx:80 ───────────────┤
   │      │                        │
   │      ├─→ cap-agent:9000 ─→ GUI Action (pyautogui) → cap-browser X display
   │      │      └→ /v1/shell/exec ─┐
   │      ├─→ cap-terminal:7682 ────┤
   │      │      └→ Tmux Session (sandbox) ←── Human (ttyd:7681)
   │      ├─→ cap-browser:6080 (websockify)
   │      ├─→ cap-code:8081
   │      ├─→ cap-jupyter:8888
   │      └─→ cap-mcp:8940 ─→ MCP Tool → 各 forward_target
```

---

## 10. 不在数据模型范围内（P1 明确排除）

- 数据库 schema（P1 无 DB，FR-NI-5）
- 多 workspace 元数据（无 Orchestrator）
- 审计日志结构化 schema（FR-NI-4，仅 `docker compose logs`）
- 用户/会话/Token 实体（FR-NI-1，无应用层认证）
- Snapshot manifest（FR-NI-6，仅 volume 级备份）
