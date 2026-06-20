# Contract: cap-terminal shell-exec-api

**Date**: 2026-06-18
**Source**: [spec.md](../spec.md) FR-020, FR-021 · [data-model.md](../data-model.md) §5, §7 · [research.md](../research.md) R3

cap-terminal 容器同时承载两个 HTTP 服务：
- **ttyd**（端口 7681）：Web Terminal WebSocket，供人类通过 `/terminal/` 交互
- **shell-exec-api**（端口 7682）：FastAPI，供 cap-agent 与 cap-mcp 程序化调用

本文档定义 shell-exec-api 的契约。核心设计：基于 libtmux 在固定 session 名 `sandbox` 上执行命令，确保 Human（ttyd）与 Agent（shell-exec-api）共享同一 PTY/cwd（设计原则三，FR-021，research.md R3）。

**通用约定**：
- Base URL（容器内）：`http://cap-terminal:7682`
- 编码：UTF-8 JSON
- 错误格式：`{"error": {"code": "...", "message": "...", "details": {...}}}`
- 同步阻塞模型：每条命令阻塞直到完成或超时（research.md R3）

---

## 1. GET /api/v1/health

**用途**：healthcheck。同时探测 tmux server 是否存活（FR-020）。

**Response 200**：

```json
{"status": "ok", "tmux_server": "running", "session": "sandbox"}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| status | enum（`ok` / `degraded`） | 总体状态 |
| tmux_server | enum（`running` / `stopped`） | tmux server 是否存活 |
| session | string | 固定 `sandbox`；若 server 在但 session 缺失，自动 respawn |

**错误**：

| HTTP | code | 触发条件 |
|------|------|----------|
| 503 | `tmux_server_down` | tmux server 异常退出，正在 respawn |

---

## 2. POST /api/v1/exec

**用途**：在固定 session `sandbox` 的指定 window 上执行命令（FR-020、FR-021）。

### Request body

| 字段 | 类型 | 必填 | 默认 | 示例 | 说明 |
|------|------|------|------|------|------|
| command | string | 是 | — | `"echo hello"` | shell 命令；不支持复合命令分离（直接送 tmux） |
| window | string | 否 | `"0"` | `"1"` | tmux window 名（index 或 name） |
| timeout_s | float | 否 | `30.0` | `60.0` | 单条命令超时，超时强杀并返回已捕获输出 |
| interactive | bool | 否 | `false` | `true` | true 时命令进入后台 window，返回 window 名供 ttyd 接管 stdin |

**约束**：
- command 长度上限 10KB（防止误传二进制）
- timeout_s 范围 1.0 ~ 600.0

### Response 200（interactive=false）

```json
{
  "exit_code": 0,
  "stdout": "hello\n",
  "stderr": "",
  "duration_ms": 12,
  "window": "0"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| exit_code | int | 命令退出码；超时为 `-1`；进程被信号杀死为 `128 + signum` |
| stdout | string | 通过 `capture-pane` 捕获的合并输出 |
| stderr | string | P1 不分离 stdout/stderr（tmux pane 合并），固定 `""`；保留字段以兼容 |
| duration_ms | int | 命令执行耗时（不含排队） |
| window | string | 实际执行的 window 名（回显） |

### Response 200（interactive=true）

```json
{
  "ok": true,
  "window": "1",
  "ws_url": "/terminal/ws/1"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| ok | bool | 命令已派发到后台 window |
| window | string | ttyd 应连接的 window 名（通常是新建 window） |
| ws_url | string | ttyd WS 端点（相对 cap-nginx 根） |

**interactive 模式语义**：
- cap-terminal 创建新 window（或复用传入 window），send_keys 后立即返回
- 命令在 tmux 内持续运行，stdin 通过 ttyd WS 注入
- 适用场景：`vim`、`python -i`、`bash` 交互会话（research.md R3）

### 状态码与错误

| HTTP | code | 触发条件 |
|------|------|----------|
| 200 | — | 命令执行完成（interactive=true 时已派发） |
| 400 | `invalid_command` | command 空 / 超长 |
| 400 | `invalid_timeout` | timeout_s 超出范围 |
| 404 | `window_not_found` | 指定 window 不存在 |
| 422 | `validation_error` | Pydantic 校验失败 |
| 503 | `tmux_session_not_found` | session `sandbox` 缺失（启动中） |
| 504 | `command_timeout` | 超过 timeout_s；stdout 已捕获部分返回 |

### 示例

```bash
# 基本执行
curl -X POST http://cap-terminal:7682/api/v1/exec \
  -H "Content-Type: application/json" \
  -d '{"command":"echo hello"}'
# {"exit_code":0,"stdout":"hello\n","stderr":"","duration_ms":12,"window":"0"}

# 交互模式
curl -X POST http://cap-terminal:7682/api/v1/exec \
  -H "Content-Type: application/json" \
  -d '{"command":"vim /workspace/shared/note.md","interactive":true}'
# {"ok":true,"window":"1","ws_url":"/terminal/ws/1"}

# 指定 window 与超时
curl -X POST http://cap-terminal:7682/api/v1/exec \
  -H "Content-Type: application/json" \
  -d '{"command":"./long-build.sh","window":"build","timeout_s":600}'
```

---

## 3. GET /api/v1/terminal/status

**用途**：返回 tmux session 内所有 window 的状态（FR-020）。cap-agent `/v1/shell/sessions` 透传此端点。

**Response 200**：

```json
{
  "session": "sandbox",
  "windows": [
    {"index": 0, "name": "agent-shell", "active": true, "cwd": "/workspace/shared"},
    {"index": 1, "name": "human-ttyd", "active": false, "cwd": "/workspace"},
    {"index": 2, "name": "build", "active": false, "cwd": "/workspace/code"}
  ],
  "attached_clients": 2
}
```

字段定义见 `data-model.md` §5。

**错误**：

| HTTP | code | 触发条件 |
|------|------|----------|
| 503 | `tmux_session_not_found` | session `sandbox` 不存在（启动中或异常） |

---

## 4. 执行模型细节（实现契约）

> 本节描述行为契约，不约束具体实现。所有引用 research.md R3 与设计文档 §5。

### 4.1 同步阻塞与输出捕获

- 命令通过 `libtmux.Window.send_keys(cmd + "\n", enter=True)` 投递到指定 window
- 投递后立即记录开始时间，轮询 `Window.panes[0].capture_pane` 检测 prompt 返回
- 检测完成条件：pane 末行出现配置的 prompt marker（默认 `\x00DONE\x00<exitcode>\x00`，通过 `PROMPT_COMMAND` 注入）
- 超时未完成：发送 `Ctrl-C` 到 pane，返回已捕获的 stdout，exit_code = -1

### 4.2 并发与排队

- tmux session 单线程：同一 window 上多条命令排队（send_keys 顺序投递）
- 跨 window 可并行：调用方可指定不同 window 名实现并行执行
- libtmux server 调用本身非线程安全，cap-terminal 内用 `asyncio.Lock` 串行化 libtmux 调用（research.md R3、Edge Case: 多 MCP 并发不丢失）

### 4.3 Session 自动 respawn

- 启动时检测 session `sandbox` 是否存在，不存在则创建
- tmux server 异常退出后，下次 `/api/v1/exec` 调用触发 `tmux new-session -d -s sandbox`，恢复服务（Edge Case）
- respawn 不保留原 session 状态（cwd、history 丢失），属可接受降级

### 4.4 共享语义验证

- Human 通过 ttyd 连接到同一 session `sandbox`，看到 Agent 投递的命令历史（User Story 2 Acceptance 2）
- Agent 执行 `cd /workspace/shared && touch x` 后，Human 在 terminal `ls` 看到 `x`（共享 cwd，User Story 2 Acceptance 3）

---

## 5. 错误码汇总

| code | HTTP | 来源场景 |
|------|------|----------|
| `invalid_command` | 400 | command 空/超长 |
| `invalid_timeout` | 400 | timeout_s 越界 |
| `window_not_found` | 404 | 指定 window 不存在 |
| `validation_error` | 422 | Pydantic 校验失败 |
| `tmux_session_not_found` | 503 | session 缺失（启动中） |
| `tmux_server_down` | 503 | tmux server 异常 |
| `command_timeout` | 504 | 命令超时 |

---

## 6. 端点总览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/health` | healthcheck + tmux 探活 |
| POST | `/api/v1/exec` | 执行 shell 命令（同步/交互） |
| GET | `/api/v1/terminal/status` | session 与 window 状态 |

---

## 引用

- spec.md：FR-020（shell-exec-api 端点）、FR-021（libtmux + 固定 session）
- research.md：R3（libtmux + 固定 session 名 `sandbox`、同步阻塞、交互模式）
- data-model.md：§5（Tmux Session 模型）、§7（Shell Exec Request/Response）
