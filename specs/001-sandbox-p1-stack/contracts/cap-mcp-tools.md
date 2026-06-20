# Contract: cap-mcp MCP Tools

**Date**: 2026-06-18
**Source**: [spec.md](../spec.md) FR-026, FR-027, FR-028 · [data-model.md](../data-model.md) §3 · [research.md](../research.md) R2, R4

cap-mcp 基于 **fastmcp**（Streamable HTTP 传输）暴露 MCP server（FR-026），监听端口 8940，路径 `/mcp/sandbox/`。本文档定义所有 MCP 工具的 JSON Schema、转发目标与错误码。

---

## 1. MCP 协议说明

### 1.1 传输

- 协议：MCP Streamable HTTP（research.md R2）
- 端点：`POST http://cap-mcp:8940/mcp/sandbox/`（单端点，POST 即 session）
- Content-Type：`application/json`
- 经 cap-nginx 反代：`POST http://localhost/mcp/sandbox/`

### 1.2 协议方法

| 方法 | 用途 |
|------|------|
| `initialize` | 握手，协商 protocol version、capabilities |
| `tools/list` | 列出所有可用工具及其 schema |
| `tools/call` | 调用工具，传入 name 与 arguments |
| `notifications/initialized` | 客户端告知初始化完成 |

### 1.3 tools/list 响应结构

```json
{
  "tools": [
    {
      "name": "shell_exec",
      "description": "...",
      "inputSchema": {...},
      "outputSchema": {...}
    }
  ]
}
```

### 1.4 tools/call 请求与响应

**请求**：

```json
{
  "method": "tools/call",
  "params": {
    "name": "shell_exec",
    "arguments": {"command": "echo hello"}
  },
  "id": 1
}
```

**成功响应**：

```json
{
  "result": {
    "content": [
      {"type": "text", "text": "{\"exit_code\":0,\"stdout\":\"hello\\n\"}"}
    ],
    "isError": false
  },
  "id": 1
}
```

**工具错误响应**（HTTP 200，错误在 content 内）：

```json
{
  "result": {
    "content": [
      {"type": "text", "text": "{\"error\":{\"code\":\"command_timeout\",...}}"}
    ],
    "isError": true
  },
  "id": 1
}
```

---

## 2. 工具分类总览

按 `category` 与 `forward_target` 分组（data-model.md §3）：

| category | 工具 | forward_target |
|----------|------|----------------|
| shell | `shell_exec` | cap-terminal:7682 |
| fs | `fs_read`, `fs_write`, `fs_list`, `fs_search` | direct-fs（`/workspace/`） |
| browser | `browser_navigate`, `browser_click`, `browser_type`, `browser_snapshot`, `browser_screenshot` | cap-browser:9222（CDP 经 playwright） |
| desktop | `desktop_screenshot`, `desktop_click`, `desktop_type` | cap-agent:9000（/gui） |

---

## 3. Shell 类工具

### 3.1 shell_exec

**描述**：在 cap-terminal 的 tmux session `sandbox` 上执行 shell 命令，返回 stdout/stderr/exit_code。命令在固定 session 内执行，与人类通过 ttyd 的操作共享 PTY/cwd。

**inputSchema**：

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| command | string | 是 | — | shell 命令 |
| window | string | 否 | `"0"` | tmux window 名 |
| timeout_s | float | 否 | `30.0` | 超时 |
| interactive | bool | 否 | `false` | 后台模式 |

**outputSchema**（成功）：

| 字段 | 类型 | 说明 |
|------|------|------|
| exit_code | int | 退出码 |
| stdout | string | 标准输出 |
| stderr | string | 标准错误（P1 固定空） |
| duration_ms | int | 耗时 |
| window | string | 执行 window |

**转发**：`POST http://cap-terminal:7682/api/v1/exec`，body 透传（FR-028）。

**错误码**：透传 cap-terminal 错误（`command_timeout`、`tmux_session_not_found`、`window_not_found` 等）；下游不可达时返回 `terminal_unreachable`。

---

## 4. FS 类工具

> 直读直写 `/workspace/`，无下游转发。路径校验：必须 `/workspace/` 开头（防穿越）。

### 4.1 fs_read

**描述**：读取 workspace 内文件内容（UTF-8 文本）。

**inputSchema**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| path | string | 是 | 绝对路径，必须 `/workspace/` 开头 |
| max_bytes | int | 否 | 默认 1MB；超出截断并返回 `truncated: true` |

**outputSchema**：

| 字段 | 类型 | 说明 |
|------|------|------|
| path | string | 回显 |
| content | string | 文本内容 |
| bytes | int | 实际读取字节 |
| truncated | bool | 是否因 max_bytes 截断 |

**错误码**：

| code | 触发 |
|------|------|
| `path_outside_workspace` | path 不以 `/workspace/` 开头 |
| `file_not_found` | 文件不存在 |
| `is_directory` | 路径是目录 |

### 4.2 fs_write

**描述**：写入 workspace 内文件（覆盖式）。

**inputSchema**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| path | string | 是 | 绝对路径 |
| content | string | 是 | 文本内容 |
| create_parents | bool | 否 | 默认 true，自动创建父目录 |

**outputSchema**：

| 字段 | 类型 | 说明 |
|------|------|------|
| ok | bool | 是否成功 |
| path | string | 回显 |
| bytes | int | 写入字节数 |

**错误码**：`path_outside_workspace`、`read_only_path`（如 `/workspace/.chromium/` 对 cap-mcp 不可写，FR-012）。

### 4.3 fs_list

**描述**：列出目录内容。

**inputSchema**：

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| path | string | 是 | — | 目录绝对路径 |
| recursive | bool | 否 | `false` | 是否递归 |
| max_entries | int | 否 | `1000` | 上限 |

**outputSchema**：

| 字段 | 类型 | 说明 |
|------|------|------|
| path | string | 回显 |
| entries | Entry[] | 子项列表 |

**Entry**：`{"name": "...", "type": "file"|"dir", "size": int, "mtime": "ISO8601"}`

**错误码**：`path_outside_workspace`、`not_a_directory`、`file_not_found`。

### 4.4 fs_search

**描述**：在 workspace 内搜索文件名或文本内容。

**inputSchema**：

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| root | string | 否 | `/workspace/` | 搜索根目录 |
| pattern | string | 是 | — | glob 模式（如 `*.py`）或正则 |
| content_query | string | 否 | — | 文本内容搜索（ripgrep 风格） |
| max_results | int | 否 | `100` | 上限 |

**outputSchema**：

| 字段 | 类型 | 说明 |
|------|------|------|
| matches | Match[] | 匹配项 |

**Match**：`{"path": "...", "line": int?, "snippet": string?}`（filename 模式仅 path；content 模式含 line + snippet）

**错误码**：`path_outside_workspace`、`pattern_invalid`。

---

## 5. Browser 类工具

> 转发到 cap-browser:9222，经 playwright-python `connect_over_cdp`（research.md R4）。共享语义：与人类通过 VNC 浏览的 Chromium 是同一进程，共享 tab、cookie、登录态（User Story 3）。

### 5.1 browser_navigate

**描述**：导航当前 tab 到指定 URL。

**inputSchema**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| url | string | 是 | 目标 URL（http/https） |
| wait_until | enum（`load`/`domcontentloaded`/`networkidle`） | 否 | 默认 `load` |

**outputSchema**：

| 字段 | 类型 | 说明 |
|------|------|------|
| ok | bool | 是否成功 |
| url | string | 实际落地 URL（重定向后） |
| title | string | 页面标题 |

**转发**：`playwright.chromium.connect_over_cdp("http://cap-browser:9222")` → `page.goto(url)`。

**错误码**：

| code | 触发 |
|------|------|
| `invalid_url` | URL 格式非法 |
| `navigation_timeout` | wait_until 超时（默认 30s） |
| `browser_unreachable` | cap-browser:9222 不可达（重试 3 次后） |
| `page_not_found` | CDP 无 page target（Chromium 未启动或全部 tab 关闭） |

### 5.2 browser_click

**描述**：点击页面元素。

**inputSchema**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| selector | string | 是 | CSS 或 playwright locator（如 `text=Login`） |
| button | enum（`left`/`right`/`middle`） | 否 | 默认 `left` |
| click_count | int | 否 | 默认 1 |
| timeout_s | float | 否 | 默认 5.0 |

**outputSchema**：

| 字段 | 类型 | 说明 |
|------|------|------|
| ok | bool | 是否成功 |
| selector | string | 回显 |

**错误码**：`selector_not_found`、`selector_timeout`、`browser_unreachable`。

### 5.3 browser_type

**描述**：在聚焦元素中输入文本。

**inputSchema**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| selector | string | 是 | 目标元素 locator |
| text | string | 是 | 输入文本 |
| clear_first | bool | 否 | 默认 true，先清空 |
| delay_ms | int | 否 | 按键间隔，默认 0 |

**outputSchema**：

| 字段 | 类型 | 说明 |
|------|------|------|
| ok | bool | 是否成功 |
| value | string | 元素当前值（输入后） |

**错误码**：`selector_not_found`、`element_not_editable`、`browser_unreachable`。

### 5.4 browser_snapshot

**描述**：返回当前页面的可访问性树（accessibility snapshot），供 LLM 理解页面结构。

**inputSchema**：

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| interesting_only | bool | 否 | `true` | 仅返回有语义的节点 |
| max_depth | int | 否 | `10` | 树深度上限 |

**outputSchema**：

| 字段 | 类型 | 说明 |
|------|------|------|
| url | string | 当前 URL |
| title | string | 页面标题 |
| snapshot | object | accessibility tree（playwright `page.accessibility.snapshot()` 输出） |

**错误码**：`browser_unreachable`、`page_not_found`。

### 5.5 browser_screenshot

**描述**：返回当前页面 PNG（playwright 截图，区别于桌面级 `desktop_screenshot`）。

**inputSchema**：

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| full_page | bool | 否 | `false` | 是否截整页 |
| format | enum（`png`/`jpeg`） | 否 | `png` | 输出格式 |

**outputSchema**：

MCP content block：

```json
{"type": "image", "data": "<base64>", "mimeType": "image/png"}
```

**错误码**：`browser_unreachable`、`page_not_found`。

---

## 6. Desktop 类工具

> 转发到 cap-agent:9000 的 `/gui/*` 路由（FR-028、research.md R5）。pyautogui 唯一持有者为 cap-agent，作用于 cap-browser 的 Xvnc display。

### 6.1 desktop_screenshot

**描述**：桌面级截图（整个 X 屏幕，区别于 browser_screenshot）。

**inputSchema**：

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| width | int | 否 | 原始 | 缩放宽度 |
| height | int | 否 | 原始 | 缩放高度 |

**outputSchema**：MCP image content block（同 5.5）。

**转发**：`GET http://cap-agent:9000/gui/screenshot`。

**错误码**：`display_unreachable`、`agent_unreachable`。

### 6.2 desktop_click

**描述**：桌面级点击（pyautogui，基于屏幕坐标，不依赖 DOM）。

**inputSchema**：

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| x | int | 是 | — | 屏幕 x |
| y | int | 是 | — | 屏幕 y |
| button | enum（`left`/`right`/`middle`） | 否 | `left` | 鼠标键 |
| clicks | int | 否 | 1 | 次数 |
| interval_s | float | 否 | 0.0 | 间隔 |

**outputSchema**：

| 字段 | 类型 | 说明 |
|------|------|------|
| ok | bool | 是否成功 |
| action_type | string（固定 `"click"`） | 回显 |

**转发**：`POST http://cap-agent:9000/gui/actions`，body `{"action_type":"click",...}`。

**错误码**：`display_unreachable`、`agent_unreachable`、`validation_error`。

### 6.3 desktop_type

**描述**：桌面级文本输入（pyautogui.typewrite，作用于当前聚焦窗口，不论是否 Chromium）。

**inputSchema**：

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| text | string | 是 | — | 输入文本 |
| interval_s | float | 否 | 0.0 | 按键间隔 |

**outputSchema**：

| 字段 | 类型 | 说明 |
|------|------|------|
| ok | bool | 是否成功 |
| action_type | string（固定 `"typing"`） | 回显 |

**转发**：`POST http://cap-agent:9000/gui/actions`，body `{"action_type":"typing","text":...}`。

**错误码**：`display_unreachable`、`agent_unreachable`、`validation_error`。

---

## 7. 错误码汇总（全工具）

| code | 类别 | 触发场景 |
|------|------|----------|
| `validation_error` | 通用 | inputSchema 校验失败 |
| `terminal_unreachable` | shell | cap-terminal:7682 不可达 |
| `command_timeout` | shell | 命令超时（透传） |
| `tmux_session_not_found` | shell | session 缺失（透传） |
| `window_not_found` | shell | window 不存在（透传） |
| `path_outside_workspace` | fs | 路径越界 |
| `read_only_path` | fs | 写入只读挂载点 |
| `file_not_found` | fs | 文件不存在 |
| `is_directory` | fs | 路径是目录 |
| `not_a_directory` | fs | 路径不是目录 |
| `pattern_invalid` | fs | glob/正则非法 |
| `browser_unreachable` | browser | cap-browser:9222 不可达 |
| `page_not_found` | browser | CDP 无 page target |
| `navigation_timeout` | browser | 页面加载超时 |
| `selector_not_found` | browser | CSS locator 无匹配 |
| `selector_timeout` | browser | locator 等待超时 |
| `element_not_editable` | browser | 元素不可编辑 |
| `invalid_url` | browser | URL 格式非法 |
| `display_unreachable` | desktop | cap-agent X display 不可达 |
| `agent_unreachable` | desktop | cap-agent:9000 不可达 |

---

## 8. AGENTS.md 上下文注入（P2 stretch，FR-013）

cap-mcp 在 `initialize` 握手时读取（User Story 7）：
- 若 `/workspace/AGENTS.md` 存在：内容附加到 server metadata，作为 system prompt 上下文
- 若不存在：降级读 `/workspace/README.md`
- 都不存在：静默跳过

注入点：`tools/list` 响应的 `_meta.workspace_context` 字段（约定，非 MCP 标准）。

---

## 9. 工具清单总览

| 工具 | 转发 | 关联 FR |
|------|------|---------|
| shell_exec | cap-terminal:7682 | FR-017, FR-027 |
| fs_read | direct-fs | FR-027 |
| fs_write | direct-fs | FR-027 |
| fs_list | direct-fs | FR-027 |
| fs_search | direct-fs | FR-027 |
| browser_navigate | cap-browser:9222 (CDP) | FR-027 |
| browser_click | cap-browser:9222 (CDP) | FR-027 |
| browser_type | cap-browser:9222 (CDP) | FR-027 |
| browser_snapshot | cap-browser:9222 (CDP) | FR-027 |
| browser_screenshot | cap-browser:9222 (CDP) | FR-027 |
| desktop_screenshot | cap-agent:9000 | FR-018, FR-027 |
| desktop_click | cap-agent:9000 | FR-018, FR-027 |
| desktop_type | cap-agent:9000 | FR-018, FR-027 |

共 13 个工具，与 spec FR-027 完全对齐。

---

## 引用

- spec.md：FR-026（Streamable HTTP）、FR-027（工具清单）、FR-028（转发目标）、FR-013（AGENTS.md 注入）
- research.md：R2（fastmcp 选型）、R4（playwright CDP）
- data-model.md：§3（MCP Tool 实体）
