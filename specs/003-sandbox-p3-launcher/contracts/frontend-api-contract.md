# Contract: Launcher 前端 ↔ Orchestrator API（前端消费视图）

**Date**: 2026-06-20
**Source**: [spec.md](../spec.md) FR-008~014 · [research.md](../research.md) R3/R7/R8 · P2 [orchestrator-rest-api.md](../002-sandbox-p2-orchestrator/contracts/orchestrator-rest-api.md) · [oauth-rest-api.md](./oauth-rest-api.md)

定义 launcher 前端（React 19 + react-query）消费 orchestrator REST API 的契约视图：**认证方式、端点消费清单、TS 类型、react-query hooks 映射**。端点细节复用 P2 `orchestrator-rest-api.md` + P3 `oauth-rest-api.md`，本文不重复，只给前端视角。

**API 基址**：经 launcher nginx 反代 `/api/ → orchestrator:8000`，前端用相对路径 `/api/v1/...`。
**认证**：cookie（`credentials: 'include'`），access_token/refresh_token 由后端 Set-Cookie（HttpOnly，R3）。前端**不读 token**，401 时 react-query 拦截器触发 refresh 或重定向 `/login`（FR-013）。

---

## 1. 端点消费清单（前端用到的子集）

| 用途 | 方法 + 路径 | 认证 | 来源 | 前端调用点 |
|------|------------|------|------|-----------|
| 本地登录 | `POST /api/v1/auth/login` | 无 | P2 | Login 页表单 |
| 注册 | `POST /api/v1/auth/register` | 无 | P2 | Login 页（可选） |
| refresh | `POST /api/v1/auth/refresh` | 无 | P2 | 401 拦截器自动 |
| OAuth 发起 | `GET /api/v1/auth/oauth/{provider}/login` | 无 | P3 | Login 页「GitHub/Google」按钮（`window.location`） |
| OAuth 回调 | `GET /api/v1/auth/oauth/{provider}/callback` | state cookie | P3 | 浏览器跳转回流（后端 302 处理，前端无需显式调） |
| 已绑定账户 | `GET /api/v1/auth/oauth/accounts` | 是 | P3 | 账户页 |
| 当前用户 | `GET /api/v1/me` | 是 | P2/扩展 | 顶部栏（头像/display_name） |
| workspace 列表 | `GET /api/v1/workspaces` | 是 | P2 | Workspaces 页 |
| 创建 workspace | `POST /api/v1/workspaces` | 是 | P2 | CreateWizard |
| workspace 详情 | `GET /api/v1/workspaces/{id}` | 是 | P2 | 列表/监控 |
| 启动/停止/暂停/恢复 | `POST /api/v1/workspaces/{id}/{action}` | 是 | P2 | 列表行操作 |
| 删除 | `DELETE /api/v1/workspaces/{id}` | 是 | P2 | 列表行操作 |
| 审计查询 | `GET /api/v1/audit?workspace=&limit=&offset=` | 是 | P2 | Monitor 页 |

> OAuth `/login` 与 `/callback` 是**整页跳转**（302），前端用 `window.location.href` 发起、浏览器自动处理回调重定向，不经 fetch/react-query。

---

## 2. TS 类型（launcher `src/types/`，与后端 schema 对齐）

```ts
// 鉴权 / 用户
type Provider = "github" | "google";
interface User { id: string; email: string; display_name: string | null; avatar_url: string | null; }
interface OAuthAccount { provider: Provider; email: string | null; created_at: string; }  // ISO 8601 UTC

// Workspace（对齐 P2 workspace schema）
type WorkspaceStatus = "created" | "starting" | "running" | "paused" | "stopped" | "deleted" | "error";
type Role = "owner" | "collaborator" | "viewer";
interface Workspace {
  id: string; name: string; slug: string; status: WorkspaceStatus;
  external_port: number; role: Role; created_at: string; last_active_at: string | null;
  error_message: string | null;  // P3：error 状态的可读信息（FR-018）
}

// 审计（对齐 P2 audit schema）
type AuditType = "shell.exec" | "fs.write" | "browser.action" | "gui.action";
interface AuditEvent { id: string; workspace_id: string; type: AuditType; actor_user_id: string | null; created_at: string; summary: string; }
interface Page<T> { items: T[]; total: number; limit: number; offset: number; }

// 统一错误
interface ApiError { error: { code: string; message: string; detail?: unknown; }; }
```

---

## 3. react-query hooks 映射（launcher `src/api/`，函数式）

| Hook | query/mutation | key | 轮询 | 说明 |
|------|----------------|-----|------|------|
| `useCurrentUser()` | query | `["me"]` | — | 顶部栏；失败→未登录 |
| `useWorkspaces()` | query | `["workspaces"]` | `refetchInterval: 5000`（列表页，状态实时） | Workspaces 页 |
| `useWorkspace(id)` | query | `["workspace", id]` | `refetchInterval: 5000` | 监控/详情 |
| `useCreateWorkspace()` | mutation | invalidate `["workspaces"]` | — | CreateWizard 提交 |
| `useWorkspaceAction()` | mutation | invalidate `["workspaces"]`/`["workspace",id]` | — | 启动/停止/...（乐观更新状态） |
| `useDeleteWorkspace()` | mutation | invalidate `["workspaces"]` | — | 删除 |
| `useAuditEvents(wsId, page)` | query | `["audit", wsId, page]` | `refetchInterval: 10000`（监控，R7） | Monitor 页 |
| `useOAuthAccounts()` | query | `["oauth-accounts"]` | — | 账户页 |

**约定**（research R8）：
- 所有 fetch 经统一 `client.ts`：`credentials: "include"`、`X-Requested-With: XMLHttpRequest`（CSRF，R3）、`/api/v1` baseURL。
- 401 拦截 → 触发 `/auth/refresh`；refresh 也 401 → 清会话 + 重定向 `/login`（FR-013）。
- mutation 成功后 `queryClient.invalidateQueries` 刷新相关 key（不可变缓存更新）。

---

## 4. OAuth 流程的前端编排（Login 页）

1. 用户点「GitHub 登录」→ `window.location.href = "/api/v1/auth/oauth/github/login?redirect=/workspaces"`。
2. 后端 302 → GitHub → 用户授权 → GitHub 302 回 `/api/v1/auth/oauth/github/callback`。
3. 后端校验/建户/签 JWT/Set-Cookie → 302 回 `redirect`（`/workspaces`）。
4. 前端加载 `/workspaces`，`useCurrentUser()` 携带 cookie 成功 → 进入工作台。
5. 失败（`?error=oauth_failed`）→ Login 页展示错误（FR-014）。

---

## 5. 错误处理约定（FR-014）

- 前端 `client.ts` 把非 2xx 统一抛 `ApiError`；react-query 的 `error` 透传到 UI。
- UI 层（页面/组件）用 shadcn `Toast`/`Alert` 展示 `error.message`，**不暴露** `detail` 原始堆栈。
- 网络错误 / orchestrator 不可达 → 「服务暂不可用」可读提示（与 launcher-proxy 错误降级一致）。
