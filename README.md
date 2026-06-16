# AI 个人沙箱（MySandbox）

一个跑在你本机的、浏览器即达的全栈 AI 工作环境：Python + Node + GUI 桌面 + 终端 + Jupyter + MCP，所有能力容器化隔离，单一端口对外。

> **当前阶段：P1 全栈已交付** — 4 base 镜像 + 7 cap-* 服务 + 13 个 MCP 工具 + Unit/Integration/E2E 三层测试。

---

## 项目定位

- **隔离**：每个能力（agent / browser / terminal / code / jupyter / mcp / nginx）一个容器，共享 X11 socket 与 workspace 卷。
- **可控**：单端口对外（`cap-nginx :80`），其余服务仅在内部 `sandbox-net` 暴露。
- **可重建**：所有镜像由 Dockerfile 生成，配置即代码。
- **共享语义**：Human 与 AI Agent 共享同一 Chromium 实例（CDP）与同一 tmux session（libtmux）。

详细设计见 [`.archive/sandbox-design.md`](.archive/sandbox-design.md)（4331 行）。

---

## 目录结构

```
.
├── base/                 # Layer 层：4 个 base 镜像
│   ├── base-os/          # Ubuntu 24.04 + locale + sandbox 用户
│   ├── base-python312/   # uv + Python 3.12
│   ├── base-node24/      # Node.js 24 + pnpm
│   └── base-vnc/         # Xvnc + Openbox + 字体
├── cap-agent/            # FastAPI 业务编排（:9000）：health/shell/cdp/gui
├── cap-browser/          # Xvnc + Chromium（:9222 CDP + :6080 websocat）
├── cap-code/             # code-server（:8081，VS Code Web）
├── cap-jupyter/          # JupyterLab（:8888）
├── cap-mcp/              # FastMCP Streamable HTTP（:8940）：13 工具
├── cap-nginx/            # 唯一对外入口（:80）+ 10 location 反代
├── cap-terminal/         # tmux + libtmux shell-exec-api（:7682）
├── docs/                 # architecture / deployment / troubleshooting
├── specs/001-sandbox-p1-stack/
│   ├── spec.md           # 需求规格（32 FR + 8 SC + 7 用户故事）
│   ├── plan.md           # 开发计划（10 milestone）
│   ├── research.md       # 10 项技术决策
│   ├── data-model.md     # 8 类核心实体
│   ├── contracts/        # 4 个服务对外契约
│   ├── quickstart.md     # 端到端验证手册
│   └── tasks.md          # 94 任务清单
├── tests/e2e/            # 14 个 E2E 测试场景
├── docker-compose.yml    # 7 服务编排（含 healthcheck/资源限制/挂载矩阵）
├── Makefile              # 所有开发命令（14 target）
└── .env.example          # 环境变量样例
```

---

## 快速开始

```bash
# 1. 克隆与配置
git clone <repo-url> sandbox && cd sandbox
cp .env.example .env
mkdir -p "${WORKSPACE_DIR:-$HOME/sandbox-workspace}"

# 2. 一键部署
make build          # 构建所有镜像（首次约 5-8 分钟）
make up             # docker compose up -d（< 90s 到 healthy）

# 3. 验证
curl http://localhost/v1/health   # {"status":"ok"}

# 4. 浏览器访问
# - http://localhost/novnc/        远程桌面
# - http://localhost/code-server/  VS Code
# - http://localhost/jupyter/      JupyterLab
# - http://localhost/terminal/     Web Terminal
```

完整步骤见 [`specs/001-sandbox-p1-stack/quickstart.md`](specs/001-sandbox-p1-stack/quickstart.md)。

---

## MCP 工具清单（13 个）

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
make test-unit      # 各服务 pytest + 覆盖率 ≥80%
make test-e2e       # docker compose up + 14 个 e2e 场景
```

| 服务 | tests | 覆盖率 |
|------|-------|--------|
| cap-agent | 55 | 99.41% |
| cap-terminal | 20 | 88.30% |
| cap-mcp | 40 | 86.00% |
| cap-nginx | 4 | contract test |

---

## 常用命令

```bash
make help          # 列出所有 14 个 target
make build         # 构建所有 base + cap-* 镜像
make build-base    # 仅构建 4 个 base 镜像（并行）
make up            # docker compose up -d
make down          # 停止容器
make logs          # 跟踪所有服务日志
make test          # 跑所有单元 + e2e 测试
make test-unit     # 仅单元测试
make test-e2e      # 仅 e2e
make clean         # 清理容器、卷、缓存
```

---

## 相关文档

- [规格 spec.md](specs/001-sandbox-p1-stack/spec.md)
- [计划 plan.md](specs/001-sandbox-p1-stack/plan.md)
- [研究 research.md](specs/001-sandbox-p1-stack/research.md)
- [数据模型 data-model.md](specs/001-sandbox-p1-stack/data-model.md)
- [快速上手 quickstart.md](specs/001-sandbox-p1-stack/quickstart.md)
- [任务清单 tasks.md](specs/001-sandbox-p1-stack/tasks.md)
- [架构总览 docs/architecture.md](docs/architecture.md)
- [部署手册 docs/deployment.md](docs/deployment.md)
- [故障排查 docs/troubleshooting.md](docs/troubleshooting.md)
- [设计原文 .archive/sandbox-design.md](.archive/sandbox-design.md)

---

## 安全声明（P1）

⚠️ **P1 不适合公网部署**：
- 无应用层认证（`AUTH_MODE=none`），靠 sandbox-net 网络隔离
- Chromium `--no-sandbox`（P1 安全降级）
- 无审计落库（仅 `docker compose logs`）

公网部署需 P2 Orchestrator（JWT 校验 + workspace 权限 + 应用层认证）。详见 [`.archive/sandbox-design.md` §1.1.2](.archive/sandbox-design.md)。

---

## License

见 [LICENSE](LICENSE)。
