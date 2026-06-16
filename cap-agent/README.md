# cap-agent

AI 个人沙箱 **cap-agent**：FastAPI 业务编排服务（端口 9000），负责鉴权、CDP 路由、GUI action 编排与业务路由。

## 角色定位

| 上游 | cap-agent | 下游 |
|------|-----------|------|
| orchestrator / 用户 CLI | 鉴权 + 编排 | cap-terminal（tmux/PTY，:7682） |
|                      |             | cap-browser（CDP，:9222） |
|                      |             | GUI（pyautogui，共享 cap-browser 的 X display） |

P1 阶段仅暴露 `/v1/health` 端点，作为 Docker Compose 存活探针；其余 8 个业务端点（FR-017~FR-024）在后续阶段实现。

## 开发流程

```bash
# 安装依赖（含 dev 工具链）
uv sync --extra dev

# 运行单元测试（覆盖率门槛 80%）
uv run pytest tests/ --cov=cap_agent --cov-report=term-missing

# 仅跑 health 测试
uv run pytest tests/unit/test_health.py -v

# 本地启动开发服务（端口 9000）
uv run uvicorn cap_agent.main:app --reload --port 9000
```

## 配置项

通过环境变量配置（前缀 `CAP_AGENT_`，可在 `.env` 中设置）：

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `CAP_AGENT_TERMINAL_URL` | `http://cap-terminal:7682` | cap-terminal 服务地址（容器内 DNS） |
| `CAP_AGENT_BROWSER_CDP_URL` | `http://cap-browser:9222` | cap-browser CDP 端点 |
| `CAP_AGENT_GUI_DISPLAY` | `:1` | GUI 共享的 X display |
| `CAP_AGENT_AUTH_MODE` | `none` | 鉴权模式（P1 固定 none，P2 切换到 orchestrator） |

> pytest fixture 中通过 `TERMINAL_URL` / `BROWSER_CDP_URL` 注入测试桩地址（无前缀）。

## Docker 构建

multi-stage，三个 target：`builder`、`prod`、`test`。

```bash
# 生产镜像
docker buildx build --load --tag cap-agent:latest --target prod ./cap-agent

# 测试镜像（CI 中跑覆盖率）
docker buildx build --load --tag cap-agent:test --target test ./cap-agent
docker run --rm cap-agent:test
```

## 依赖关系

- **base-python312**：祖先镜像，提供 `uv` + Python 3.12。
- **cap-terminal**：必须先启动并监听 `:7682`，cap-agent 的业务路由才能成功转发。
- **cap-browser**：必须先启动并监听 `:9222`（CDP），GUI 编排复用其 X display `:1`。

## 测试分层

- `tests/unit/`：纯单元测试，无外部依赖，使用 `TestClient`。
- `tests/integration/`：跨服务集成测试（标记 `@pytest.mark.integration`），需 docker-compose 拉起完整栈。

## 相关规格

- `specs/001-sandbox-p1-stack/spec.md`：FR-016（health）、FR-029（覆盖率 ≥80%）
- `specs/001-sandbox-p1-stack/contracts/cap-agent-api.md`：9 端点契约定义
- `specs/001-sandbox-p1-stack/tasks.md`：Phase 2.2 T012-T021
