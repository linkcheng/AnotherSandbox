# Quickstart: AI 个人沙箱 P1 全栈端到端验证

**Date**: 2026-06-18
**Source**: [spec.md](./spec.md) SC-001 ~ SC-008 · [plan.md](./plan.md) M0 ~ M9 · `.archive/sandbox-design.md` §18

本手册指导如何从零启动整套 P1 沙箱并执行端到端验证。**不含实现代码**，仅是 run guide 与故障排查。所有命令在仓库根目录执行。

---

## 1. 前置条件

| 项 | 要求 | 验证命令 |
|----|------|----------|
| 操作系统 | Linux x86_64/arm64 或 macOS | `uname -a` |
| Docker Engine | 24.0+ | `docker version` |
| docker compose | v2（plugin 形式） | `docker compose version` |
| 可用磁盘 | ≥ 10GB（镜像 + workspace） | `df -h .` |
| 可用内存 | ≥ 6GB（SC-007 + 缓冲） | `free -h` / macOS Activity Monitor |
| 80 端口 | 空闲（或用 `PORT` 切换） | `lsof -i :80` 应无输出 |
| 工作目录 | 可写 `~/sandbox-workspace/` | — |

> macOS 注意：Chromium `--no-sandbox` 兼容但性能略低（R1）；bind mount 文件 IO 较慢（R8，约 100ms 延迟）。

---

## 2. 首次启动

### 2.1 克隆并配置环境变量

```bash
git clone <repo-url> sandbox
cd sandbox
cp .env.example .env
```

编辑 `.env`：

| 变量 | 默认 | 说明 |
|------|------|------|
| `PORT` | `80` | 对外端口，被占用时改 `8080` |
| `WORKSPACE_DIR` | `~/sandbox-workspace` | 宿主机 workspace 路径 |
| `AUTH_MODE` | `none` | P1 固定（FR-NI-1） |

### 2.2 创建 workspace 目录骨架

```bash
mkdir -p "${WORKSPACE_DIR}"/{code,notebooks,shared,.chromium,.vscode,.jupyter}
touch "${WORKSPACE_DIR}/AGENTS.md"
```

> 子目录用途见 `data-model.md` §1；`.chromium/` 必须由 cap-browser 独占 rw（FR-012）。

### 2.3 构建镜像

```bash
make build
```

**预期**：SC-001，冷构建 4 个 base + 7 个 cap-* 共 11 个镜像，< 8 分钟。

**输出标志**：
- `make build-base` 子目标先跑（base-os/vnc/node24/python312）
- 然后并行构建 cap-*（依赖 base 已就绪）
- 最终 `docker images | grep -E 'base-|cap-'` 应列出 11 个镜像

### 2.4 启动整套 stack

```bash
make up
```

**预期**：SC-002，所有 7 个 cap-* 容器到 healthy 状态 < 90 秒。

**进度观察**：

```bash
docker compose ps
# 期望所有服务 STATUS = Up (healthy)
```

> healthcheck 由 cap-agent `/v1/health` 与各服务自有端点驱动（FR-016、FR-020）。

---

## 3. 端到端验证步骤

### 验证 1：API 健康

**目标**：cap-nginx + cap-agent 通路通畅。

```bash
curl -fsS http://localhost/v1/health
```

**期望输出**：

```json
{"status":"ok"}
```

失败排查见 §4。如果改了 `PORT=8080`，URL 改为 `http://localhost:8080/v1/health`。

### 验证 2：noVNC 桌面

**目标**：cap-nginx 静态文件 + cap-browser Xvnc + websockify WS 全链路。

浏览器打开：

```
http://localhost/novnc/vnc.html
```

**期望**：
- 页面加载 noVNC 前端
- 自动连接 `/websockify` WS
- 显示 cap-browser 内 Xfce 桌面（Openbox 窗口管理器）

**判定通过**：看到桌面背景与一个终端窗口或菜单（User Story 1 Acceptance 2）。

### 验证 3：code-server Web VS Code

**目标**：cap-nginx + cap-code 通路 + workspace rw 挂载。

浏览器打开：

```
http://localhost/code-server/
```

**期望**：
- 进入 code-server 编辑器界面（auth=none，FR-024）
- 左侧文件浏览器可见 `/workspace/code/`
- 在 `/workspace/code/` 下新建 `test.py`，保存

**判定通过**：宿主机 `${WORKSPACE_DIR}/code/test.py` 立即可见（< 100ms，SC-006）。

### 验证 4：MCP shell_exec

**目标**：cap-mcp + cap-terminal + tmux 共享语义全链路（SC-005 < 500ms）。

**用 MCP client**（如 Claude Desktop、cursor、或脚本）配置：

```
URL: http://localhost/mcp/sandbox/
Transport: Streamable HTTP
```

调用工具：

```json
{
  "method": "tools/call",
  "params": {
    "name": "shell_exec",
    "arguments": {"command": "echo hello"}
  }
}
```

**期望响应**（成功路径）：

```json
{"exit_code": 0, "stdout": "hello\n", "stderr": "", "duration_ms": 12}
```

**共享语义验证**（User Story 2）：
1. 调用 `shell_exec({"command":"cd /workspace/shared && touch from-agent.txt"})`
2. 浏览器打开 `http://localhost/terminal/`，进入 ttyd
3. 在 ttyd 执行 `ls /workspace/shared/`
4. 应看到 `from-agent.txt`（Human+Agent 共享 cwd）

### 验证 5：E2E 测试套件

**目标**：跑通 5 个核心路径的自动化测试（SC-004，< 5 分钟全绿）。

```bash
make test-e2e
```

**覆盖路径**（FR-031）：

| 测试 | 验证点 |
|------|--------|
| `test_health.py` | 所有服务 `/health` 返回 200 |
| `test_shell_roundtrip.py` | MCP shell_exec → tmux → stdout 回环 |
| `test_fs_roundtrip.py` | fs_write → cap-code 可见 |
| `test_browser_navigate.py` | browser_navigate → example.com |
| `test_screenshot.py` | `/gui/screenshot` 返回 PNG > 1KB |

**判定通过**：所有测试 `PASSED`，覆盖率报告生成在 `tests/e2e/.coverage`。

> CI 注意：真实 Chromium 不可在无 GUI 的 CI 上跑（spec Assumptions）；CI 上 E2E 用 mock 或仅跑非 GUI 路径。

---

## 4. 故障排查

### 4.1 端口被占用

**症状**：`make up` 报 `Bind for 0.0.0.0:80 failed: port is already allocated`。

**排查**：

```bash
lsof -i :80          # macOS/Linux
sudo netstat -tlnp | grep :80   # Linux
```

**解决**：
- 停掉占用进程，或
- 改 `.env`：`PORT=8080`，重启 `make down && make up`
- 验证：`curl http://localhost:8080/v1/health`

### 4.2 镜像拉取/构建失败

**症状**：`make build` 中途失败，`docker images` 缺镜像。

**常见原因**：
- 网络问题：apt/npm/PyPI 源不可达
- base 镜像继承断裂（base-os 未构建就跑 cap-*）

**排查**：

```bash
make build-base          # 先单独构建 base
docker images | grep base-
make build               # 再构建 cap-*
```

**清理重试**：

```bash
make clean-images
make build
```

### 4.3 Chromium 崩溃 / `/novnc/` 黑屏

**症状**：noVNC 连接成功但桌面黑屏；或 `browser_*` MCP 工具报 `browser_unreachable`。

**排查**：

```bash
docker compose logs cap-browser | tail -50
# 关注 "Failed to move to new namespace" 或 "GPU process isn't usable"
```

**常见原因与解决**：

| 原因 | 解决 |
|------|------|
| `/workspace/.chromium/` 权限不对 | `chmod -R 777 ${WORKSPACE_DIR}/.chromium`（P1 受信环境） |
| Xvnc 未启 | `docker compose restart cap-browser` |
| Chromium `--no-sandbox` 缺失 | 检查 entrypoint.sh 启动参数（FR-022） |
| 内存不足（cap-browser 2g 限制） | 调高 `docker-compose.yml` 中 cap-browser 的 mem_limit |
| macOS 性能差 | 接受降级，或开发期用 mock CDP（R1） |

### 4.4 shell_exec 超时

**症状**：MCP `shell_exec` 报 `command_timeout`。

**排查**：

```bash
docker compose exec cap-terminal tmux ls
# 期望看到 session: sandbox
```

**常见原因**：
- 命令本身慢：调用方传 `timeout_s: 600`
- tmux session 死锁：`docker compose restart cap-terminal`，session 自动 respawn（research.md R3）
- 命令等待 stdin（如 `cat` 无参数）：用 `interactive: true` 模式（contracts/cap-terminal-api.md §2）

### 4.5 容器不 healthy

**症状**：`docker compose ps` 中某服务 `Up (unhealthy)` 或 `Up (health: starting)`。

**排查**：

```bash
docker inspect --format '{{json .State.Health}}' <container> | jq
# 关注最近 5 次 healthcheck 输出
```

**常见原因**：
- cap-agent 不 healthy：检查 `/v1/health`，可能是 cap-terminal/cap-browser 未就绪（depends_on 未生效）
- cap-terminal 不 healthy：tmux server 启动失败
- cap-mcp 不 healthy：fastmcp 初始化失败，看日志

### 4.6 文件挂载不一致

**症状**：cap-code 保存的文件在 cap-terminal 看不到，或反之。

**排查**：

```bash
docker compose exec cap-code ls /workspace/code/
docker compose exec cap-terminal ls /workspace/code/
# 两边应一致
```

**常见原因**：
- `${WORKSPACE_DIR}` 路径错（macOS 用户名含空格）
- 挂载 rw/ro 与 `data-model.md` §1 矩阵不符（FR-012）
- macOS bind mount 延迟（R8，约 100ms，等一会再看）

### 4.7 MCP 工具调用 404 / 502

**症状**：MCP client 调工具返回非预期。

**排查路径**：
1. `curl http://localhost/mcp/sandbox/` 是否可达
2. `docker compose logs cap-mcp` 看转发日志
3. 检查转发目标是否 healthy（shell → cap-terminal、browser → cap-browser、desktop → cap-agent）

---

## 5. 清理

### 5.1 停止 stack（保留镜像与数据）

```bash
make down
```

`docker compose down` 移除容器与网络，**保留** `${WORKSPACE_DIR}` 数据与已构建镜像。

### 5.2 完全清理

```bash
make down              # 停容器
make clean-images      # 删镜像（谨慎，下次 build 全冷启动）
rm -rf "${WORKSPACE_DIR}"   # 删 workspace 数据（不可恢复）
```

### 5.3 单服务重启

```bash
docker compose restart cap-browser
docker compose restart cap-terminal cap-mcp   # 多个
```

---

## 6. 常用调试命令速查

| 任务 | 命令 |
|------|------|
| 查看所有服务状态 | `docker compose ps` |
| 查看某服务日志（实时） | `docker compose logs -f cap-agent` |
| 进入容器 | `docker compose exec cap-terminal bash` |
| 看 tmux session | `docker compose exec cap-terminal tmux attach -t sandbox`（Ctrl-b d 退出） |
| 看 Chromium target | `curl http://localhost/cdp/json \| jq` |
| 手动触发 GUI 截图 | `curl http://localhost/gui/screenshot -o /tmp/s.png && open /tmp/s.png` |
| 重载 nginx 配置 | `docker compose exec cap-nginx nginx -s reload` |
| 跑单服务单测 | `make test-agent` / `make test-terminal` / `make test-mcp` |
| 跑 E2E | `make test-e2e` |

---

## 7. 性能基线（SC 指标自检）

| 指标 | 目标 | 自检方法 |
|------|------|----------|
| SC-001 构建时间 | < 8 分钟 | `time make build` |
| SC-002 启动到 healthy | < 90 秒 | `time make up` + 轮询 `docker compose ps` |
| SC-005 MCP shell_exec 延迟 | < 500ms | MCP client 计时 `echo hello` |
| SC-006 文件可见延迟 | < 100ms | 手动 ls 验证（或 e2e `test_fs_roundtrip`） |
| SC-007 稳态总内存 | < 5GB | `docker stats --no-stream` 求和 |

未达标见 §4 对应排查项。

---

## 引用

- spec.md：SC-001 ~ SC-008（成功标准）、User Story 1 ~ 6（验收场景）
- plan.md：M0 ~ M9 milestone
- `.archive/sandbox-design.md` §18（测试策略）、§12（docker-compose）
