# Contract: cap-agent HTTP API

**Date**: 2026-06-18
**Source**: [spec.md](../spec.md) FR-016, FR-017, FR-018, FR-019 · [data-model.md](../data-model.md) §3, §4, §6, §7

cap-agent 是 FastAPI 服务（内部端口 9000），作为业务编排层。它对外暴露：健康检查、shell 透传、文件上传下载、GUI 操作、CDP 反代。所有端点经 cap-nginx `/v1/`、`/gui/`、`/cdp/` 路由前缀对外（FR-014）。本文档定义每个端点的契约。

**通用约定**：
- Base URL（容器内）：`http://cap-agent:9000`
- Base URL（外部经 nginx）：`http://localhost/v1` / `/gui` / `/cdp`
- 编码：UTF-8 JSON
- 错误响应统一格式：`{"error": {"code": "...", "message": "...", "details": {...}}}`，HTTP 状态码见各端点
- 所有端点响应时间目标 < 500ms（不含下游命令本身执行，SC-005）

---

## 1. GET /v1/health

**用途**：healthcheck 端点，供 docker-compose 探活（FR-016）。

**Request**：无 body，无 query。

**Response 200**：

```json
{"status": "ok"}
```

| 字段 | 类型 | 示例 | 说明 |
|------|------|------|------|
| status | string（固定 `ok`） | `"ok"` | 健康标志 |

**错误**：本端点不返回非 200，进程未启动则 TCP 拒连（healthcheck 标 unhealthy）。

**示例**：

```bash
curl http://localhost/v1/health
# {"status":"ok"}
```

---

## 2. POST /v1/shell/exec

**用途**：透传到 cap-terminal:7682 的 shell-exec-api（FR-017）。cap-agent 仅做请求转发与错误归一化，不持有 shell 状态。

**Request body**（与 cap-terminal 完全一致，见 `cap-terminal-api.md` §2）：

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| command | string | 是 | — | shell 命令 |
| window | string | 否 | `"0"` | tmux window 名 |
| timeout_s | float | 否 | `30.0` | 超时 |
| interactive | bool | 否 | `false` | 后台 + ttyd 接管 |

**Response 200**（透传 cap-terminal 响应）：

```json
{
  "exit_code": 0,
  "stdout": "hello\n",
  "stderr": "",
  "duration_ms": 12,
  "window": "0"
}
```

**状态码与错误**：

| HTTP | code | 触发条件 |
|------|------|----------|
| 200 | — | 命令执行完成（不论 exit_code） |
| 400 | `invalid_command` | command 为空或超长（>10KB） |
| 422 | `validation_error` | Pydantic 校验失败（缺 command 字段等） |
| 502 | `terminal_unreachable` | cap-terminal:7682 不可达（健康检查失败/重启中） |
| 504 | `command_timeout` | 命令执行超过 timeout_s；返回时 stdout/stderr 为已捕获的部分 |

**示例**：

```bash
curl -X POST http://localhost/v1/shell/exec \
  -H "Content-Type: application/json" \
  -d '{"command":"echo hello"}'
```

---

## 3. GET /v1/shell/sessions

**用途**：列出当前 tmux session 下的 windows 与活动状态（FR-020 间接）。透传 cap-terminal `/api/v1/terminal/status`。

**Response 200**：

```json
{
  "session": "sandbox",
  "windows": [
    {"index": 0, "name": "agent-shell", "active": true, "cwd": "/workspace/shared"},
    {"index": 1, "name": "human-ttyd", "active": false, "cwd": "/workspace"}
  ],
  "attached_clients": 2
}
```

字段定义见 `data-model.md` §5。

**错误**：

| HTTP | code | 触发条件 |
|------|------|----------|
| 502 | `terminal_unreachable` | cap-terminal 不可达 |
| 503 | `tmux_session_not_found` | session `sandbox` 不存在（启动中或异常退出） |

---

## 4. POST /v1/file/upload

**用途**：上传文件到 `/workspace/`，multipart 流式（Edge Case: 大文件不撑爆内存）。

**Request**（multipart/form-data）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| destination | string（绝对路径） | 是 | 目标路径，必须在 `/workspace/` 下 |
| file | binary | 是 | 文件内容 |

**Response 200**：

```json
{"ok": true, "path": "/workspace/shared/uploaded.bin", "bytes": 1048576}
```

**错误**：

| HTTP | code | 触发条件 |
|------|------|----------|
| 400 | `path_outside_workspace` | destination 不在 `/workspace/` 下（路径穿越防御） |
| 413 | `payload_too_large` | 超过 `MAX_UPLOAD_BYTES`（默认 2GB） |
| 422 | `missing_file` | multipart 缺 file 字段 |

**示例**：

```bash
curl -X POST http://localhost/v1/file/upload \
  -F "destination=/workspace/shared/data.csv" \
  -F "file=@./local.csv"
```

---

## 5. GET /v1/file/download

**用途**：下载 `/workspace/` 下文件，StreamingResponse（Edge Case: 大文件流式）。

**Query 参数**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| path | string（绝对路径） | 是 | 必须在 `/workspace/` 下 |

**Response 200**：

- Headers：`Content-Type: application/octet-stream`（或按扩展名推断）、`Content-Disposition: attachment; filename="..."`、`Content-Length`
- Body：文件字节流

**错误**：

| HTTP | code | 触发条件 |
|------|------|----------|
| 400 | `path_outside_workspace` | path 不在 `/workspace/` 下 |
| 404 | `file_not_found` | 文件不存在 |

**示例**：

```bash
curl -o ./local.csv "http://localhost/v1/file/download?path=/workspace/shared/data.csv"
```

---

## 6. GET /gui/screenshot

**用途**：返回 cap-browser Xvnc 当前画面的 PNG 截图（FR-018）。pyautogui.screenshot() 持有者为 cap-agent（research.md R5）。

**Request**：可选 query `width` / `height`（整数，缩放后输出；省略返回原始分辨率）。

**Response 200**：

- Headers：`Content-Type: image/png`
- Body：PNG 字节流，大小 > 1KB（User Story 6 Acceptance 1）

**错误**：

| HTTP | code | 触发条件 |
|------|------|----------|
| 502 | `display_unreachable` | 无法连接 cap-browser 的 X display（`/tmp/.X11-unix/` 未挂载或 Xvnc 未启） |

**示例**：

```bash
curl http://localhost/gui/screenshot -o screen.png
file screen.png  # PNG image data
```

---

## 7. POST /gui/actions

**用途**：执行 pyautogui 桌面动作（16 种，FR-018）。discriminated union by `action_type`，schema 见 `data-model.md` §6。

**Request body**（示例：typing）：

```json
{"action_type": "typing", "text": "abc"}
```

**Request body**（示例：click）：

```json
{"action_type": "click", "x": 100, "y": 200, "button": "left", "clicks": 1}
```

完整字段表见 `data-model.md` §6。

**Response 200**：

```json
{"ok": true, "action_type": "typing", "duration_ms": 45}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| ok | bool | 动作执行成功 |
| action_type | string（回显） | 实际执行的动作类型 |
| duration_ms | int | 动作耗时 |

**错误**：

| HTTP | code | 触发条件 |
|------|------|----------|
| 422 | `validation_error` | action_type 非法或必填字段缺失 |
| 502 | `display_unreachable` | X display 不可达 |

**实现约束**：pyautogui 调用同步阻塞，路由内 `asyncio.to_thread()` 包裹（research.md R5、风险 R4）。

**示例**：

```bash
curl -X POST http://localhost/gui/actions \
  -H "Content-Type: application/json" \
  -d '{"action_type":"click","x":500,"y":400}'
```

---

## 8. GET /cdp/json

**用途**：反代 cap-browser:9222/json（FR-019）。返回当前 Chromium 内所有 page target。

**Response 200**：CDP Target 数组，结构见 `data-model.md` §4。

```json
[
  {
    "id": "A1B2C3D4...",
    "type": "page",
    "title": "Example Domain",
    "url": "https://example.com/",
    "webSocketDebuggerUrl": "ws://cap-browser:9222/devtools/page/A1B2...",
    "devtoolsFrontendUrl": "/devtools/inspector.html?ws=..."
  }
]
```

**错误**：

| HTTP | code | 触发条件 |
|------|------|----------|
| 502 | `browser_unreachable` | cap-browser:9222 不可达 |
| 503 | `chromium_not_ready` | 9222 端口可达但 Chromium 未完成启动 |

---

## 9. WS /cdp/devtools/{id}

**用途**：双向 WebSocket 透传到 cap-browser:9222/devtools/page/{id}（FR-019、FR-015）。供 DevTools 前端或 playwright 直连。

**路径参数**：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 来自 `/cdp/json` 的 target id |

**协议**：
- 子协议：`Sec-WebSocket-Protocol: chat`（CDP 默认）
- 客户端 → cap-agent：CDP JSON 命令（如 `{"id":1,"method":"Page.navigate","params":{...}}`）
- cap-agent → 客户端：CDP 事件流（如 `Page.frameNavigated`、`Network.responseReceived`）

**生命周期**：
- 建立：HTTP 101 Switching Protocols
- 心跳：cap-agent 不主动加 ping，依赖 CDP 自身保活；nginx 端空闲 5 分钟断开（Edge Case）
- 关闭：客户端主动 close 或上游断开时双向 close

**错误**：

| HTTP/WS | code | 触发条件 |
|---------|------|----------|
| 404 | `target_not_found` | id 不存在于当前 `/cdp/json` 列表 |
| 502 | `browser_unreachable` | cap-browser:9222 WS 不可达 |
| 1011 | `internal_error` | WS 透传过程中异常 |

**示例**（wscat）：

```bash
wscat -c ws://localhost/cdp/devtools/A1B2C3D4...
> {"id":1,"method":"Page.navigate","params":{"url":"https://example.com"}}
< {"id":1,"result":{"frameId":"..."}}
< {"method":"Page.frameStoppedLoading",...}
```

---

## 10. 端点总览

| 方法 | 路径 | 转发目标 | 说明 |
|------|------|----------|------|
| GET | `/v1/health` | 本地 | healthcheck |
| POST | `/v1/shell/exec` | cap-terminal:7682 | shell 透传 |
| GET | `/v1/shell/sessions` | cap-terminal:7682 | tmux session 状态 |
| POST | `/v1/file/upload` | 本地 IO（`/workspace/`） | 流式上传 |
| GET | `/v1/file/download` | 本地 IO（`/workspace/`） | 流式下载 |
| GET | `/gui/screenshot` | 本地 pyautogui → cap-browser X | 截图 |
| POST | `/gui/actions` | 本地 pyautogui → cap-browser X | 16 种动作 |
| GET | `/cdp/json` | cap-browser:9222 | CDP target 列表 |
| WS | `/cdp/devtools/{id}` | cap-browser:9222 | CDP 双向透传 |

---

## 11. 配置项（pydantic-settings）

cap-agent 通过环境变量读取下游地址（FR 不可见，但契约前置）：

| 变量 | 默认 | 说明 |
|------|------|------|
| `CAP_TERMINAL_URL` | `http://cap-terminal:7682` | shell-exec-api 地址 |
| `CAP_BROWSER_CDP_URL` | `http://cap-browser:9222` | CDP HTTP+WS 地址 |
| `DISPLAY` | `:1` | cap-browser Xvnc display 编号 |
| `MAX_UPLOAD_BYTES` | `2147483648`（2GB） | upload 上限 |
| `WORKSPACE_DIR` | `/workspace` | 容器内 workspace 挂载点 |
| `LOG_LEVEL` | `INFO` | uvicorn 日志级别 |

---

## 引用

- spec.md：FR-014（路由前缀）、FR-016（health）、FR-017（shell 透传）、FR-018（GUI）、FR-019（CDP 反代）
- research.md：R4（CDP/playwright）、R5（pyautogui 归属）
