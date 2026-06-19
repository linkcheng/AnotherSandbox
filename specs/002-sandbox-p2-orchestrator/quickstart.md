# Quickstart: AI 个人沙箱 P2 — Orchestrator 验证手册

**Date**: 2026-06-19
**Source**: [spec.md](./spec.md) SC-001~008 · [plan.md](./plan.md) M0-M8 · contracts/

端到端验证 P2 Orchestrator 可用的可执行场景清单。每条给出前置/命令/预期，覆盖 spec 全部 8 条 Success Criteria。具体实现见 tasks.md；契约细节见 `contracts/`，schema 见 [`data-model.md`](./data-model.md)，决策见 [`research.md`](./research.md)。

---

## 前置

- Docker 24+ / docker compose v2，宿主机可联网
- **P1 镜像已构建**（4 base + 7 cap-*）：`make build`（P2 复用，不重建，FR-002）
- P1 的 `docker-compose.yml`、`Makefile`、`.env.example` 已就绪
- 宿主机 8000（Orchestrator）、8100+（workspace）端口可用

---

## 场景 1：构建并启动 Orchestrator（SC-003 单测覆盖基础）

**目的**：Orchestrator 服务 + PostgreSQL 起来，Alembic 迁移成功。

```bash
make build-orchestrator          # 构建 orchestrator 镜像（multi-stage）
make up-orchestrator             # docker compose -f docker-compose.orchestrator.yml up -d
curl -sf http://localhost:8000/healthz          # → {"status":"ok"}
curl -sf http://localhost:8000/readyz           # → {"status":"ready","db":"ok"}
```

**预期**：`/readyz` 200 且 `db:"ok"`（Alembic upgrade head 成功，data-model §4 建表）。
**失败排查**：DB 不可达 → `docker compose -f docker-compose.orchestrator.yml logs postgres`；迁移失败 → `orchestrator` 容器日志（fail-fast，Edge Case）。

---

## 场景 2：JWT 注册/登录/越权（US2 / SC-002）

```bash
# 注册 + 登录 alice
curl -X POST localhost:8000/api/v1/auth/register -d '{"email":"alice@example.com","password":"pw1"}' -H 'Content-Type: application/json'
TOKEN=$(curl -sX POST localhost:8000/api/v1/auth/login -d '{"email":"alice@example.com","password":"pw1"}' -H 'Content-Type: application/json' | jq -r .access_token)

# 无 token 访问受保护端点 → 401
curl -s -o /dev/null -w '%{http_code}' localhost:8000/api/v1/workspaces   # → 401

# 有 token → 200（空列表）
curl -s -H "Authorization: Bearer $TOKEN" localhost:8000/api/v1/workspaces  # → []
```

**预期**：注册 201、登录 200、无 token 401、有 token 200。契约见 [`orchestrator-rest-api.md`](./contracts/orchestrator-rest-api.md) §1。

---

## 场景 3：创建并启动 workspace（US1 / SC-001）

```bash
# 创建
WS=$(curl -sX POST localhost:8000/api/v1/workspaces -H "Authorization: Bearer $TOKEN" \
     -d '{"name":"alice-dev"}' -H 'Content-Type: application/json')
WS_ID=$(echo $WS | jq -r .id); PORT=$(echo $WS | jq -r .external_port)
# → status=created, external_port=8101（R2 自动分配）

# 启动（内部 docker compose -p ws-alice-001 up -d --wait，R7）
curl -sX POST localhost:8000/api/v1/workspaces/$WS_ID/start -H "Authorization: Bearer $TOKEN"
# → status=running（< 120s，SC-001）

# 验证 workspace 容器组
docker compose -p ws-alice-001 ps   # → 7 个 cap-* healthy
```

**预期**：start 在 < 120s 返回 running；该 workspace 名下出现 healthy 的 cap-* 容器组（SC-001）。

---

## 场景 4：鉴权穿透访问 workspace（US3 / SC-002 / SC-008）

```bash
# 经 Orchestrator + auth_request 访问 workspace 的 /v1/health
# （workspace cap-nginx auth_request → Orchestrator /verify 注入可信 header）
curl -sf -H "Authorization: Bearer $TOKEN" \
     -H "X-Workspace-Id: $WS_ID" \
     http://localhost:$PORT/v1/health   # → {"status":"ok"}

# 越权：bob 的 token 访问 alice 的 workspace → 403
BOB_TOKEN=$(...注册并登录 bob...)
curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $BOB_TOKEN" \
     -H "X-Workspace-Id: $WS_ID" http://localhost:$PORT/v1/health   # → 403

# 绕过 Orchestrator 直连（伪造 header）→ 被 auth_request 拒（trusted-headers §4）
curl -s -o /dev/null -w '%{http_code}' -H "X-User-Id: fake" \
     http://localhost:$PORT/v1/health   # → 401（cap-nginx 无 Authorization → /verify 401）
```

**预期**：合法 token 200、越权 403、伪造/直连 401（SC-002 / SC-008 fail-closed）。契约见 [`trusted-headers.md`](./contracts/trusted-headers.md)。

---

## 场景 5：审计落库（US4 / SC-004）

```bash
# 在 workspace 内执行 shell（经鉴权路径，触发 cap-terminal 审计上报）
curl -sX POST -H "Authorization: Bearer $TOKEN" -H "X-Workspace-Id: $WS_ID" \
     -H 'Content-Type: application/json' \
     -d '{"command":"echo hi"}' http://localhost:$PORT/v1/shell/exec
# → {"exit_code":0,"stdout":"hi\n",...}

# 查询审计（Orchestrator）
curl -s -H "Authorization: Bearer $TOKEN" \
     "localhost:8000/api/v1/audit?workspace_id=$WS_ID&event_type=shell.exec" | jq
# → 含一条 shell.exec / success=true / detail.command="echo hi"

# best-effort：停 Orchestrator 后再执行 shell，命令仍成功（SC-004）
make stop-orchestrator
curl ... http://localhost:$PORT/v1/shell/exec   # → 仍 200（审计丢失，业务不阻塞）
```

**预期**：正常落库；Orchestrator 不可达时业务命令 100% 成功（SC-004）。契约见 [`audit-ingest.md`](./contracts/audit-ingest.md)。

---

## 场景 6：多 workspace 隔离（SC-005）

```bash
# 再创建 bob/carol 两个 workspace（SC-005 要求 ≥3）
# ...各 start...
# 在 alice 的 workspace shell 写文件
curl ... -d '{"command":"echo secret > /workspace/shared/a.txt"}' .../v1/shell/exec
# 在 bob 的 workspace shell 读 alice 的文件 → 不存在（独立 sandbox-net + 独立卷）
curl ... -d '{"command":"cat /workspace/shared/a.txt"}' <bob-port>/v1/shell/exec   # → 失败/空
```

**预期**：A 的文件/网络对 B 不可见（独立 compose project + 网络 + 卷，R3）。

---

## 场景 7：CLI 全生命周期（US5 / SC-007）

```bash
orchestrator user register alice@example.com pw1
orchestrator user login alice@example.com pw1     # 本地存 token
orchestrator workspace create alice-dev            # → id
orchestrator workspace start <id>
orchestrator workspace list                        # → [{...status:running}]
orchestrator workspace stop <id>
```

**预期**：≤6 条命令完成全生命周期（SC-007）；Swagger UI `http://localhost:8000/docs` 列出全部端点。

---

## 场景 8：P1 零迁移回归（SC-006）

```bash
# P1 单 workspace 模式（AUTH_MODE=none，无 Orchestrator）
AUTH_MODE=none make up          # P1 原命令
curl -sf http://localhost/v1/health   # → 200（无 Orchestrator 依赖）
make test-e2e                   # P1 E2E 全绿
make test-e2e-p2                # P2 E2E 全绿（含 test_p1_regression.py）
```

**预期**：P1 模式独立可用，业务路由代码未改（SC-006 零迁移）。

---

## 测试命令速查（plan M8）

| 命令 | 范围 | 关联 SC |
|------|------|---------|
| `make test-orchestrator` | Orchestrator unit（≥80% 覆盖） | SC-003 |
| `make test-orchestrator-integration` | testcontainers-postgres + 临时 compose project | SC-001/004 |
| `make test-e2e-p2` | 完整 stack（场景 1-8） | SC-001~008 |
| `make test-e2e` | P1 回归 | SC-006 |

> 场景 4-5 的 auth_request/审计需 workspace 真实启动（E2E 层）；unit/integration 层用 mock（契约 stub）先行。

---

## 引用
- spec.md：SC-001~008
- contracts/：[`orchestrator-rest-api.md`](./contracts/orchestrator-rest-api.md)、[`audit-ingest.md`](./contracts/audit-ingest.md)、[`trusted-headers.md`](./contracts/trusted-headers.md)、[`cap-agent-auth-middleware.md`](./contracts/cap-agent-auth-middleware.md)
- data-model.md / research.md / plan.md
