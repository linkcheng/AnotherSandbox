# Orchestrator

AI 个人沙箱 **P2 编排层**：叠加在 P1 sandbox 之上的多租户控制平面。

## 职责

- **编排**：workspace 生命周期（create/start/stop/pause/resume/delete），通过 `docker compose -p {slug}` 驱动复用的 P1 镜像
- **元数据**：PostgreSQL（users / workspaces / workspace_owners / templates / audit_logs / refresh_tokens）
- **认证**：JWT 自建账户 + 可信 header 注入 + workspace 归属校验
- **审计**：cap-* 操作事件落库（best-effort）

详见 `specs/002-sandbox-p2-orchestrator/`（spec / plan / research / data-model / contracts）。

## 开发

```bash
# 安装依赖（uv）
cd orchestrator && uv sync --all-extras

# 单元测试（覆盖率 ≥80%）
make test-orchestrator

# 启动 Orchestrator + PostgreSQL
make up-orchestrator
curl localhost:8000/readyz   # → {"status":"ready","db":"ok"}
```

## 配置（环境变量，见根 .env.example）

| 变量 | 默认 | 说明 |
|------|------|------|
| `ORCH_PORT` | 8000 | Orchestrator 对外端口 |
| `DATABASE_URL` | — | PostgreSQL async URL |
| `JWT_SECRET_KEY` | 随机(开发) | HS256 签名密钥；生产必填 |
| `WORKSPACE_PORT_START/END` | 8100/8199 | workspace 对外端口分配范围 |
| `WORKSPACE_RETENTION_DAYS` | 7 | 软删除保留期 |
| `AUTH_FAILURE_MODE` | fail-closed | auth_request 降级策略 |

## 与 P1 的关系

Orchestrator 是**可选叠加层**（§8.8.5）：P1 单 workspace 模式（`AUTH_MODE=none`，无 Orchestrator）仍独立可用。Orchestrator 管"workspace 之间"，sandbox 管"workspace 之内"，职责不重叠。

## CLI（Phase 7）

```bash
orchestrator user register/login
orchestrator workspace create/start/stop/list
```

## 测试

- Unit：`tests/unit/`（纯逻辑，全 mock）
- Integration：`tests/integration/`（testcontainers-postgres + 临时 compose project）
- E2E：仓库根 `tests/e2e/test_p2_*.py`（Phase 8）
