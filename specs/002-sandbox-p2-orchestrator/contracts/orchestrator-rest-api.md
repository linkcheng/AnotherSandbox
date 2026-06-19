# Contract: Orchestrator REST API

**Date**: 2026-06-19
**Source**: [spec.md](../spec.md) FR-001~023 · [research.md](../research.md) R5/R7/R8 · `.archive/sandbox-design.md` §9.3

Orchestrator 暴露的 REST API（FastAPI 自动生成 OpenAPI，`/docs` Swagger UI）。分 4 组：认证、workspace 生命周期、审计、内部 verify。所有时间 ISO 8601 UTC。示例 ID 均为虚构。

**Base URL**：`http://<orchestrator-host>:${ORCH_PORT:-8000}`
**认证**：除 `/auth/*`、`/healthz`、`/readyz`、`/api/v1/verify`、`/api/v1/audit/ingest` 外，均需 `Authorization: Bearer <access_jwt>`。
**统一响应**：成功返回资源对象；错误返回 `{"error": {"code": "...", "message": "...", "detail": {...}}}` + 对应 HTTP 状态码。

---

## 1. 认证（FR-011）

### POST /api/v1/auth/register
注册新用户。
```json
// Request
{ "email": "alice@example.com", "password": "<明文，仅传输>" }
// 201 Response
{ "id": "a1b2c3d4-...", "email": "alice@example.com", "created_at": "2026-06-19T04:00:00Z" }
// 409 email 已存在
```
> 密码经 passlib bcrypt 哈希后存 `users.password_hash`，明文不落库（FR-010）。

### POST /api/v1/auth/login
```json
// Request
{ "email": "alice@example.com", "password": "<明文>" }
// 200 Response
{ "access_token": "<jwt>", "refresh_token": "<opaque>", "token_type": "bearer", "expires_in": 900 }
// 401 凭证无效
```

### POST /api/v1/auth/refresh
```json
// Request
{ "refresh_token": "<opaque>" }
// 200 Response
{ "access_token": "<jwt>", "refresh_token": "<新>", "token_type": "bearer", "expires_in": 900 }
// 401 refresh token 无效/过期/已吊销
```
> 旧 refresh token 用后即吊销（rotation）。refresh token 明文不落库，存 sha256 hash（data-model §2.6）。

---

## 2. Workspace 生命周期（FR-001~006，参考 §9.3）

### POST /api/v1/workspaces
创建 workspace（不自动启动）。
```json
// Request（需 Bearer）
{
  "name": "alice-dev",                 // 可选，人类可读
  "template": "minimal"                // 可选，默认 minimal
}
// 201 Response
{
  "id": "ws-alice-001-...",
  "slug": "ws-alice-001",              // compose project 名
  "name": "alice-dev",
  "status": "created",
  "external_port": 8101,               // R2 自动分配
  "endpoints": { "nginx": "http://<host>:8101" },
  "owner": { "id": "a1b2c3d4-...", "role": "owner" },
  "created_at": "2026-06-19T04:00:00Z"
}
```
- `slug` 由 name slugify + 短随机后缀生成，全局唯一（`docker compose -p` 用）
- `external_port` 由 port_allocator 分配（R2）；冲突重试
- 创建者自动写入 `workspace_owners`（role=owner）

### GET /api/v1/workspaces
列出当前用户可见的 workspace（owner + collaborator + viewer）。
```json
// 200 Response
[
  { "id": "ws-alice-001-...", "slug": "ws-alice-001", "name": "alice-dev",
    "status": "running", "external_port": 8101, "role": "owner",
    "last_active_at": "2026-06-19T05:00:00Z" }
]
```

### GET /api/v1/workspaces/{id}
详情（含 healthcheck 聚合状态）。
```json
// 200
{ "id": "...", "slug": "...", "status": "running", "external_port": 8101,
  "endpoints": { "nginx": "http://<host>:8101" },
  "caps_health": { "cap-nginx": "healthy", "cap-agent": "healthy" },
  "owner": {}, "created_at": "...", "last_active_at": "..." }
// 403 非归属用户
```

### POST /api/v1/workspaces/{id}/start
`created`/`stopped` → `running`。内部：置 STARTING → `compose up -d --wait`（R7）→ 成功 RUNNING / 失败 ERROR。
```json
// 200 Response
{ "id": "...", "status": "running", "external_port": 8101 }
// 409 非法状态转换（如已 running——幂等则返回当前态，见 Edge Case）
// 502 compose 失败（置 ERROR，detail 含 stderr 摘要）
```

### POST /api/v1/workspaces/{id}/stop    # running/paused → stopped
### POST /api/v1/workspaces/{id}/pause   # running → paused
### POST /api/v1/workspaces/{id}/resume  # paused → running
> 响应同 start 风格（返回新 status）。状态机见 data-model §6 / §8.5。

### DELETE /api/v1/workspaces/{id}?purge=false
软删除（默认）：置 `deleted_at`，`compose down`（保留卷，R1 保留 7 天后清理任务硬删）。
`purge=true`：立即硬删（`compose down -v` + 删卷目录 + 删 DB 行）。
```json
// 204（无 body）
// 403 非所有者（仅 owner 可删）
```

---

## 3. 审计（FR-016/018/019）

### POST /api/v1/audit/ingest   ← cap-* 调用（详见 audit-ingest.md）
写入 `audit_logs`。详见 [`audit-ingest.md`](./audit-ingest.md)。

### GET /api/v1/audit?workspace_id=...&event_type=...&since=...&limit=...
查询审计（需 Bearer + workspace 归属）。
```json
// 200
[ { "id": 1234567, "workspace_id": "...", "actor_user_id": "...",
    "event_type": "shell.exec", "source": "cap-terminal",
    "detail": {"command":"echo hi","exit_code":0}, "success": true,
    "created_at": "2026-06-19T04:05:00Z" } ]
```
- query 参数：`workspace_id`（必填）、`event_type`（可选）、`actor_user_id`（可选）、`since`/`until`（ISO 8601，可选）、`limit`（默认 100，max 1000）、`success`（可选 bool）
- 403 非归属 workspace

---

## 4. 内部端点（非公开 API）

### POST /api/v1/verify   ← workspace cap-nginx `auth_request` 目标（R8）
校验请求身份 + workspace 归属，回写可信 header。
- 输入：`Authorization`（JWT）+ `X-Workspace-Id`（或路径前缀解析的 workspace slug）
- 输出：
  - **200**（放行）+ 响应 header：`X-User-Id` / `X-Workspace-Id` / `X-Permissions`（详见 [`trusted-headers.md`](./trusted-headers.md)）
  - **401**（无/坏 JWT）
  - **403**（越权：非该 workspace 的 owner/collaborator/viewer）
- nginx 用 `auth_request_set` 捕获上述 header 透传给 cap-agent（R8）
- body 不消费（`proxy_pass_request_body off`）

### GET /healthz
存活探针（liveness）：`200 {"status":"ok"}`（不查 DB）。

### GET /readyz
就绪探针（readiness）：`200 {"status":"ready","db":"ok"}`（查 DB 连通）；DB 不可达 `503`。

---

## 5. 错误模型

```json
{ "error": { "code": "workspace_conflict", "message": "workspace already running",
             "detail": { "current_status": "running" } } }
```

| HTTP | code 示例 | 触发 |
|------|-----------|------|
| 400 | `bad_request` | 参数校验失败 |
| 401 | `unauthorized` | 无/坏/过期 JWT |
| 403 | `forbidden` | 非 workspace 归属 |
| 404 | `not_found` | 资源不存在 |
| 409 | `workspace_conflict` / `email_exists` | 状态转换冲突 / 邮箱占用 |
| 422 | `validation_error` | Pydantic 校验失败 |
| 502 | `compose_failed` | docker compose 子进程失败（workspace 置 ERROR） |
| 503 | `db_unavailable` | PostgreSQL 不可用（运行期） |

---

## 6. OpenAPI / CLI 映射

- `/docs`（Swagger UI）+ `/openapi.json`：FastAPI 自动生成，覆盖上述全部端点（FR-021）
- CLI（`orchestrator` typer）：每个端点对应子命令（`workspace create/start/stop/list`、`user register/login`），见 tasks.md M7 / spec FR-020 / SC-007

---

## 引用
- spec.md：FR-001~023（编排/元数据/认证/审计/入口）
- research.md：R2（端口）、R5（JWT）、R7（compose_runner）、R8（auth_request）
- `.archive/sandbox-design.md` §9.3（Orchestrator API 草案）、§8.5（状态机）、§8.6.2（认证流程）
