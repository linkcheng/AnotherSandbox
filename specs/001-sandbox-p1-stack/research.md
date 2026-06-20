# Phase 0 Research: AI 个人沙箱 P1 全栈

**Date**: 2026-06-18
**Status**: Complete

本文档记录 P1 全栈实施前的技术选型与不确定项研究结论。所有"NEEDS CLARIFICATION"在 spec 阶段已通过用户确认闭合，本文件聚焦"如何实施"层面的决策与替代方案。

---

## R1. Python 服务运行时与包管理

**Decision**: Python 3.12 + uv + FastAPI

**Rationale**:
- 用户全局 CLAUDE.md §8 明确规定 Python 3.12+ / uv / 全量 Type Hint / Async First
- uv 较 poetry 快 10–100x（实测冷装 6s vs 90s），适合 7 镜像 CI
- FastAPI 提供原生 async、Pydantic v2 校验、OpenAPI 自动生成，契合"协议优先"原则
- libtmux 与 httpx 都是 async 友好

**Alternatives considered**:
- poetry：成熟但慢；CLAUDE.md 不偏好
- pip + requirements.txt：无锁文件，可重现性差
- Flask 2 + async：生态弱、类型支持不完整
- Litestar：FastAPI 替代但社区小

---

## R2. MCP 协议与 SDK 选择

**Decision**: fastmcp（Streamable HTTP 传输）

**Rationale**:
- 设计原则六明确要求 Streamable HTTP 优先（§1）
- fastmcp 是 Model Context Protocol 官方 Python SDK，原生支持 Streamable HTTP
- 单文件 server + `@mcp.tool()` 装饰器，契合"Generate > Maintain"
- 协议演进快，pyproject.toml 锁定 minor 版本

**Alternatives considered**:
- 自实现 MCP over SSE：违反设计原则六
- mcp-proxy：仅做转发，不提供工具注册 DSL
- TypeScript MCP SDK：与 Python 服务栈不一致

---

## R3. Shell 共享语义实现

**Decision**: libtmux + 固定 session 名（`sandbox`）

**Rationale**:
- 设计原则三要求 Human+Agent 共享 PTY/cwd；tmux session 天然多客户端
- libtmux 是 tmux 的 Python 绑定，比 subprocess 调用更稳定
- 固定 session 名 `sandbox`，所有命令在固定 window 内执行
- 命令输出通过 `capture-pane` 拿到，无需重定向文件

**关键决策点**:
- 命令执行模型：**同步阻塞**（等待命令完成返回 stdout/stderr/exit_code），超时（默认 30s）后强制中断
- 交互模式：`interactive: true` 时返回 window 名，客户端通过 ttyd WS 继续 stdin 交互
- 并发：libtmux session 单线程，命令在 tmux 内排队（避免 race）

**Alternatives considered**:
- pexpect：底层、跨平台差，无法被多个客户端共享
- 直接 spawn PTY：丢失共享语义
- shell_exec via bash subprocess：每条命令独立进程，无 cwd 持久化

---

## R4. 浏览器控制：CDP 直连 vs Playwright

**Decision**: cap-mcp 的 browser_* 工具用 playwright-python（CDP wire 协议直连 cap-browser:9222）

**Rationale**:
- Chromium 启动 `--remote-debugging-port=9222`，任何 CDP 客户端可接
- playwright-python 提供 high-level API（click/type/snapshot），比裸 CDP 简单 10x
- 共享语义保留：playwright 连接已有 Chromium 实例（`connect_over_cdp`），不启动新进程
- 与 human VNC 浏览的 Chromium 是同一进程，CDP 与渲染不冲突

**关键决策点**:
- playwright 连接模式：`playwright.chromium.connect_over_cdp("http://cap-browser:9222")`
- 不在 cap-mcp 内启 Chromium；Chromium 唯一在 cap-browser 内
- 重连策略：连接失败重试 3 次，每次间隔 1s，失败返回工具错误

**Alternatives considered**:
- mcp-server-puppeteer：Node.js 实现，与 Python 服务栈不匹配（设计文档已剔除）
- 裸 CDP client（pychrome）：开发成本高，无 high-level API
- browser-use：依赖 playwright，且偏 LLM-driven，超出 P1 范围

---

## R5. 桌面操作：pyautogui 归属与跨容器 X

**Decision**: pyautogui 唯一合法持有者为 cap-agent；通过共享 X display socket 访问 cap-browser 的 Xvnc

**Rationale**:
- 设计文档 §4.8 明确：pyautogui 在 cap-agent，DISPLAY 指向 cap-browser 的 Xvnc
- 共享方式：cap-browser 容器 `/tmp/.X11-unix/` 通过 docker volume 共享给 cap-agent
- cap-agent 设置 `DISPLAY=:1`（cap-browser 的 Xvnc display 编号）
- pyautogui 调用是同步阻塞，FastAPI 异步路由内用 `asyncio.to_thread()` 包裹

**关键决策点**:
- X socket 共享：`volumes: [x11-unix-volume]`，cap-browser 与 cap-agent 都挂载
- 截图：pyautogui.screenshot() → PNG bytes → StreamingResponse
- 动作 discriminated union：16 种 action_type，pydantic `Annotated[Union[...], Field(discriminator="action_type")]`

**Alternatives considered**:
- pyautogui 在 cap-browser 内 + HTTP 暴露：违反"pyautogui 唯一持有"原则
- 用 CDP 的 Input.dispatchKeyEvent 替代 typing：复杂且不支持鼠标 hover
- Xvnc 跨网络（TCP 5900）：增加延迟，无收益

---

## R6. Nginx 反代与 WebSocket 升级

**Decision**: Nginx 单文件 nginx.conf，每个 location 块明确 `proxy_http_version 1.1` + `Upgrade` / `Connection` header

**Rationale**:
- 设计原则五：nginx 是唯一 HTTP 入口
- WebSocket 升级必须每个 location 显式配置（默认 Nginx 不转发 Upgrade）
- 静态文件 noVNC 由 nginx 直接服务（不走 cap-browser）

**关键 location 块**（参考，详细在 contracts/nginx-routes.md）:
```nginx
# noVNC 静态文件
location /novnc/ {
  alias /usr/share/novnc/;
}
# noVNC WebSocket
location /websockify {
  proxy_pass http://cap-browser:6080;
  proxy_http_version 1.1;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
  proxy_read_timeout 3600s;
}
# MCP Streamable HTTP
location /mcp/sandbox/ {
  proxy_pass http://cap-mcp:8940;
  proxy_http_version 1.1;
}
```

**Alternatives considered**:
- Traefik：自动服务发现，但学习成本高，nginx 更普及
- Caddy：自动 HTTPS，但 P1 不需要 TLS
- HAProxy：偏 TCP 负载均衡，HTTP 配置繁琐

---

## R7. 容器隔离与权限

**Decision**: 所有容器 `cap_drop: [ALL]` + `security_opt: [no-new-privileges:true]`；Chromium `--no-sandbox`（P1）

**Rationale**:
- 设计文档 §1.1.2 与 §11 安全基线明确
- `cap_drop: ALL` 移除所有 Linux capabilities，最小权限
- Chromium 自带 sandbox 需要 `setuid` 与 namespace capability，P1 简化为 `--no-sandbox`
- 容器隔离 + sandbox-net 网络隔离是 P1 唯一防线（不引入应用层认证）

**P2 演进路径**:
- 启用 Chromium sandbox（需 chrome-sandbox setuid root）
- 加精细 seccomp profile（白名单 syscall）
- 引入 Orchestrator 应用层认证

**Alternatives considered**:
- 启用 Chromium sandbox：违反 P1 范围
- AppArmor profile：与 seccomp 重叠，先做 seccomp

---

## R8. 测试策略与覆盖率

**Decision**: Unit（≥80% 行覆盖）+ Integration（respx mock HTTP）+ E2E（docker compose + httpx）

**Rationale**:
- 设计文档 §18 已明确分层
- Unit 测试纯逻辑（无 IO），fast feedback
- Integration 测试 cap-agent 的 router → service → httpx 转发链，用 respx mock 下游
- E2E 测试整 stack，验证 docker-compose 与跨容器协作

**工具链**:
- pytest + pytest-asyncio：异步测试框架
- respx：mock httpx（比 responses 更现代）
- coverage.py：覆盖率，CI 门禁 ≥80%
- testcontainers（可选）：跨服务集成测试，但 docker compose 已够用

**E2E 关键场景**（出自 §18.7）:
- `test_shell_exec_via_mcp`：MCP → cap-terminal → echo hello
- `test_fs_roundtrip`：MCP fs_write → cap-code 内可见
- `test_browser_navigate_via_mcp`：MCP → CDP → example.com
- `test_health_endpoint`：所有服务 health 返回 200

**Alternatives considered**:
- 仅 Unit：跨服务契约无法验证，回归风险高
- 仅 E2E：CI 慢，定位 bug 困难
- 引入 testcontainers：与 docker compose 重叠

---

## R9. 镜像分层与构建性能

**Decision**: 4 层 base 镜像 + 7 个 cap-* 镜像；make build 并行

**Rationale**:
- 设计文档 §3 明确继承链：base-os → base-vnc / base-node24 / base-python312 → cap-*
- base-os 年级变化，base-* 季度级，cap-* 周级
- 每层独立 Dockerfile，docker build 缓存友好
- make 用 `--parallel` 标志并行构建（依赖关系由 Dockerfile FROM 自动处理）

**预估镜像大小**:
- base-os: ~150MB
- base-python312: +200MB = ~350MB
- base-vnc: +300MB = ~450MB
- base-node24: +250MB = ~400MB
- cap-agent: +100MB = ~450MB
- cap-browser: +400MB（Chromium）= ~850MB
- cap-mcp: +150MB（playwright python）= ~500MB
- cap-terminal: +50MB = ~400MB
- cap-code: +500MB（code-server）= ~900MB
- cap-jupyter: +300MB = ~650MB
- cap-nginx: +50MB = ~200MB
- 总磁盘占用：~5GB（首次冷构建）

**Alternatives considered**:
- 单层镜像（每个 cap-* 直接 FROM ubuntu）：失去缓存优势
- Distroless：减小体积但调试困难
- Multi-stage 编译型镜像：Python 服务不适用

---

## R10. Workspace 挂载矩阵

**Decision**: 宿主机 `~/sandbox-workspace/` → 容器 `/workspace/`；按 §7.2 子目录分别 rw/ro 挂载

**Rationale**:
- 设计原则二：Workspace 是第一公民，状态唯一载体
- bind mount 比 named volume 更透明（用户可直接 `ls ~/sandbox-workspace/`）
- 按目录粒度 rw/ro 限制爆炸半径（如 `.chromium/` 仅 cap-browser 可写）

**关键挂载**（详细在 contracts 中）:

| 路径 | cap-browser | cap-terminal | cap-code | cap-jupyter | cap-mcp | cap-agent |
|------|-------------|--------------|----------|-------------|---------|-----------|
| `/workspace/code/` | ro | ro | **rw** | ro | ro | ro |
| `/workspace/notebooks/` | - | - | - | **rw** | - | - |
| `/workspace/shared/` | ro | ro | ro | ro | ro | ro |
| `/workspace/.chromium/` | **rw** | - | - | - | - | - |
| `/workspace/.vscode/` | - | - | **rw** | - | - | - |
| `/workspace/.jupyter/` | - | - | - | **rw** | - | - |
| `/workspace/AGENTS.md` | ro | ro | ro | ro | ro | ro |

**Alternatives considered**:
- 单一只读 root + tmpfs 持久化目录：失去"打开即见"透明性
- 单一 rw 挂载到所有容器：爆炸半径过大，违反最小权限

---

## 未决问题（已在 spec 阶段闭合）

无遗留 NEEDS CLARIFICATION。所有关键决策在 spec.md 与本文件中已固化。
