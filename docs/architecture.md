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
