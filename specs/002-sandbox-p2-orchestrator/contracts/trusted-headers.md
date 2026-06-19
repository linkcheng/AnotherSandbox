# Contract: Trusted Headers（可信身份 Header）

**Date**: 2026-06-19
**Source**: [spec.md](../spec.md) FR-012/013/014 · [research.md](../research.md) R3/R8 · `.archive/sandbox-design.md` §8.6.2/§8.6.3

定义 Orchestrator 与 workspace 内 cap-agent 之间的"可信 header"契约——Orchestrator 完成身份认证 + workspace 归属校验后，把已认证身份以 HTTP header 形式注入，由 workspace cap-nginx 透传给 cap-agent。这是"关注点分离"（§8.6.3）的载体：Orchestrator 见身份不见业务，cap-agent 见业务不见密码。

---

## 1. Header 定义

| Header | 类型 | 示例 | 由谁设置 | 含义 |
|--------|------|------|----------|------|
| `X-User-Id` | UUID string | `a1b2c3d4-...` | Orchestrator `/verify` 响应 → nginx 透传 | 已认证用户 ID（对应 `users.id` / JWT `sub`） |
| `X-Workspace-Id` | UUID string | `ws-alice-001-...` | 同上 | 目标 workspace ID |
| `X-Permissions` | string | `owner` / `collaborator` / `viewer` | 同上 | 用户对该 workspace 的角色（data-model §2.4 role） |

- **全部由 Orchestrator 设置**，外部客户端**不可信**的携带值会被 nginx `proxy_set_header` **覆盖**（见 R8 防伪造）
- 缺失任一 header（非 `AUTH_MODE=none` 场景）→ cap-agent 视为未认证（401）

---

## 2. 注入链路（端到端）

```
客户端请求（带 Authorization: Bearer <jwt>）
   │
   ▼
workspace cap-nginx
   │  location /v1/ { auth_request /_auth; ... }
   ▼
/_auth (internal) ──proxy_pass──► Orchestrator POST /api/v1/verify
                                        │  校验 JWT + workspace 归属
                                        │  响应 header:
                                        │    X-User-Id / X-Workspace-Id / X-Permissions
                                        ▼  (2xx=放行 / 401 / 403)
   ◄──────────────── auth_request_set 捕获 upstream_http_x_* ────────────
   │
   │  proxy_set_header X-User-Id $x_user_id;        # 覆盖（防伪造）
   │  proxy_set_header X-Workspace-Id $x_workspace_id;
   │  proxy_set_header X-Permissions $x_permissions;
   ▼
cap-agent（AUTH_MODE=orchestrator）
   │  OrchestratorHeaderAuthMiddleware 读 X-User-Id 等 → 注入 request.state.user
   ▼
业务路由（/v1/shell/exec 等，零改动）
```

---

## 3. Orchestrator `/verify` 响应约定（R8）

| 场景 | HTTP | 响应 header | 含义 |
|------|------|-------------|------|
| 认证 + 归属通过 | **200** | `X-User-Id` / `X-Workspace-Id` / `X-Permissions` 均设置 | 放行，身份可信 |
| 无/坏/过期 JWT | **401** | 不设置 | 未认证 |
| JWT 有效但非该 workspace 归属 | **403** | 不设置 | 越权 |
| Orchestrator 内部错误 | **5xx** | 不设置 | nginx 按 `AUTH_FAILURE_MODE` 处理（R4） |

> `/verify` 不返回 body（nginx `auth_request` 只看状态码 + 响应 header）；身份信息全部走 header。

---

## 4. 防伪造保证

可信 header 之所以"可信"，依赖两条不变量：

1. **网络隔离**：workspace 外部不可直连 cap-agent:9000（sandbox-net `expose` only，§11.3）。任何到 cap-agent 的请求必经 cap-nginx
2. **nginx 覆盖**：cap-nginx 用 `proxy_set_header`（**覆盖**客户端传入的同名 header）而非 `proxy_pass_header`（透传）。即使外部伪造 `X-User-Id: <victim>`，到达 cap-agent 时已被 `/_auth` 的真实值覆盖

破坏任一不变量（如误把 cap-agent `ports:` 暴露、或 nginx 漏配 `proxy_set_header`）即破坏安全性——M4/M5 测试必须覆盖伪造场景。

---

## 5. P1 兼容（`AUTH_MODE=none`）

P1 单 workspace 模式下，cap-nginx 不配置 `auth_request`、不注入可信 header；cap-agent `AUTH_MODE=none` 的 `NoAuthMiddleware` 不读 header，所有请求视为本地受信（§8.6.1）。

- **零迁移**：业务路由代码不感知 header 存在；P1→P2 切换仅改 `AUTH_MODE` + nginx 配置 + 是否前置 Orchestrator（FR-022/023 / SC-006）
- `X-Permissions` 等 header 在 `none` 模式下不存在/被忽略，不影响业务

---

## 引用
- spec.md：FR-012（注入）/FR-013（auth_request）/FR-014（cap-agent 读 header）/FR-022（P1 兼容）
- research.md：R3（网络）、R8（nginx auth_request + auth_request_set）
- `.archive/sandbox-design.md` §8.6.2（可信 header）/ §8.6.3（关注点分离）/ §8.6.4（Phase 不变量）
