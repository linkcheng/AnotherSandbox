# Contract: OAuth REST API（SSO/OAuth 身份入口）

**Date**: 2026-06-20
**Source**: [spec.md](../spec.md) FR-001~007 · [research.md](../research.md) R1/R2/R3/R9 · [data-model.md](../data-model.md) §2/§3

Orchestrator 新增的 OAuth 2.0 登录/绑定端点（叠加在 P2 REST API 之上，P2 既有端点不变）。provider ∈ `{github, google}`。OAuth 登录成功签发**等价 P2 JWT**（FR-002），浏览器场景经 **HttpOnly Cookie** 下发（R3），CLI 场景仍可用 P2 `/auth/login` 的 JSON body。

**Base URL**：`http://<orchestrator-host>:${ORCH_PORT:-8000}`
**认证**：`/login` 无需认证；`/callback` 经 state 校验；`/accounts`、`/bind`、`/unbind` 需已登录（Bearer 或 session cookie）。
**统一错误**：`{"error": {"code": "...", "message": "...", "detail": {...}}}` + HTTP 状态码。

---

## 1. 发起 OAuth 登录

### GET /api/v1/auth/oauth/{provider}/login
重定向（302）到 IdP 授权页。生成 `state`（随机 + 签名/HMAC，存 cookie 或服务端短 TTL），拼 Authorization Code URL（含 PKCE `code_challenge`）。
- **Path**：`provider` ∈ `{github, google}`
- **Query**（可选）：`redirect=<launcher 路径>`（登录成功后回到的 launcher 页面，默认 `/`）
- **Response**：`302 Location: https://github.com/login/oauth/authorize?...&state=...`
- **Set-Cookie**：`oauth_state=<hmac>`（HttpOnly, 短 TTL, SameSite=Lax），回调时比对防 CSRF（FR-004）。
- **400**：`provider` 不在白名单。

> `OAUTH_MOCK=true` 时，`/login` 直接 302 到 `/callback?code=mock-code-{provider}&state=...`，便于离线闭环（R9）。

---

## 2. OAuth 回调（核心：建户/合并/签 JWT）

### GET /api/v1/auth/oauth/{provider}/callback
IdP 回调端点。校验 state → 用 `code` 换 access_token → 取 userinfo → 建户/邮箱合并 → 签 JWT → Set-Cookie → 重定向 launcher。

- **Path**：`provider` ∈ `{github, google}`
- **Query**：`code=<authorization_code>`、`state=<...>`
- **流程**（research R1/R2）：
  1. 比对 `state` 与 `oauth_state` cookie（不匹配 → 400，FR-005）。
  2. `code` → IdP token 端点换 `access_token`（mock 模式跳过）。
  3. `access_token` → IdP userinfo 端点取 `provider_user_id` / `email` / `display_name` / `avatar_url`。
  4. `oauth_linker` 按 `(provider, provider_user_id)` → email 合并 → 建户/绑定（data-model §3）。
  5. 调 P2 `security.create_tokens(user)` 签等价 JWT（access + refresh）。
- **Response**：`302 Location: <redirect|/>`
- **Set-Cookie**（R3）：
  - `access_token=<jwt>`; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=900
  - `refresh_token=<opaque>`; HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth/refresh; Max-Age=604800
- **错误**：
  - `400` state 不匹配 / 缺 code（FR-005）
  - `401` code 失效 / token 交换失败 / userinfo 取不到（FR-005）→ 重定向 launcher 登录页带 `?error=oauth_failed`
  - `502` IdP 不可达（Edge Case）→ `?error=oauth_unreachable`

> OAuth-only 用户 `password_hash` 为 NULL，仅可经 OAuth 登录（data-model §2.2）。所得 JWT 与本地账户 JWT 在下游鉴权/审计 100% 一致（SC-006）。

---

## 3. 查询已绑定的 OAuth 身份

### GET /api/v1/auth/oauth/accounts
列出当前登录用户绑定的 provider（账户页/解绑 UI）。
```json
// 200 Response（需已登录）
{
  "accounts": [
    { "provider": "github", "email": "alice@example.com", "created_at": "2026-06-20T04:00:00Z" },
    { "provider": "google", "email": "alice@gmail.com", "created_at": "2026-06-20T05:00:00Z" }
  ]
}
// 401 未登录
```

---

## 4. 绑定 / 解绑（已登录用户，FR-006）

### POST /api/v1/auth/oauth/{provider}/bind
为当前登录用户发起绑定（流程同 `/login`，但回调时 `user_id` = 当前用户而非新建/合并）。重定向到 IdP。
- **Response**：`302 Location: <IdP 授权页>`
- **401**：未登录。
- **409**：该 `(provider, provider_user_id)` 已绑定到**其他** user（不可重复绑定，FR-006）。

### DELETE /api/v1/auth/oauth/{provider}/unbind
解绑当前用户的某 provider。
```json
// 200 Response
{ "unbound": "github" }
// 401 未登录 / 404 未绑定该 provider
// 409 该用户将失去所有登录方式（无 password 且无其余 provider）→ 拒绝，提示先设置密码或绑定其他 provider
```

---

## 5. 环境与配置（research R9）

| 变量 | 说明 |
|------|------|
| `OAUTH_GITHUB_CLIENT_ID` / `OAUTH_GITHUB_CLIENT_SECRET` | GitHub OAuth App 凭证（env，不落库/不进前端，FR-007） |
| `OAUTH_GOOGLE_CLIENT_ID` / `OAUTH_GOOGLE_CLIENT_SECRET` | Google OAuth 凭证 |
| `OAUTH_REDIRECT_URL` | 回调基址（如 `http://launcher.local/api/v1/auth/oauth`，经 launcher `/api` 反代到 orchestrator） |
| `OAUTH_MOCK` | `true` 时启用 mock provider（离线/CI），生产必须 `false`（R9） |

---

## 6. 与 P2 的关系（零迁移）

- P2 `/auth/register` / `/auth/login` / `/auth/refresh` **行为不变**；为兼容浏览器 SPA，P3 给 `/login` 与 `/refresh` 的成功响应**额外 Set-Cookie**（JSON body 保留不变，CLI 无感知）。
- P2 `verify` / `workspaces` / `audit` 端点零改动；OAuth 所得 JWT 直接复用这些端点的 Bearer 鉴权。
- `oauth_accounts` 表 + `users` 增列由 Alembic `0002_oauth` 落地（data-model §4）。
