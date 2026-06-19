# Data Model: AI 个人沙箱 P3 — OAuth 身份扩展

**Date**: 2026-06-20
**Source**: [spec.md](./spec.md) · [plan.md](./plan.md) · [research.md](./research.md)（R2）· P2 [data-model.md](../002-sandbox-p2-orchestrator/data-model.md)

本文档定义 P3 对 P2 PostgreSQL schema 的**增量扩展**：新增 `oauth_accounts` 表 + `users` 增列。**P2 既有 6 表（users / templates / workspaces / workspace_owners / audit_logs / refresh_tokens）结构不变**（零迁移，FR-026）。P3 由 Alembic 迁移 `0002_oauth` 落地。

所有时间字段 `TIMESTAMPTZ`（UTC）。主键 `UUID`。下表示例均为合成虚构值，非真实数据。

---

## 1. ER 增量关系

```
users (P2 不变结构) ──+── 增列 display_name / avatar_url（nullable，OAuth profile）
                     │
                     └── (1) ─────< oauth_accounts (N)   [provider, provider_user_id] 唯一
                                                          │
                                                          └── user_id FK → users.id

oauth_accounts.provider ∈ {github, google}（CHECK）
```

一个 user 可绑定 0..N 个 provider；同一 provider 同一外部账号不可重复绑定到不同 user（唯一约束）。

---

## 2. 表定义

### 2.1 `oauth_accounts` — OAuth 外部身份关联（P3 新增）

| 字段 | 类型 | 约束 | 示例 | 说明 |
|------|------|------|------|------|
| id | UUID | PK, default gen_random_uuid() | `oa-11223344-...` | 关联记录 ID |
| provider | TEXT | NOT NULL, CHECK in (github, google) | `github` | OAuth 提供者（FR-001） |
| provider_user_id | TEXT | NOT NULL | `12345678` | IdP 侧用户唯一 ID（GitHub `id` / Google `sub`） |
| user_id | UUID | FK→users.id ON DELETE CASCADE, NOT NULL | `a1b2c3d4-...` | 关联的本地 user |
| email | TEXT | nullable | `alice@example.com` | IdP 回传邮箱（合并依据，R2） |
| raw_profile | JSONB | nullable | `{"login":"alice",...}` | IdP userinfo 原始载荷，备查（schema 不频繁迁移） |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | `2026-06-20T04:00:00Z` | 绑定时间 |

**索引/约束**：
- `PK(id)`
- `UNIQUE(provider, provider_user_id)`（同 provider 同外部账号全局唯一，防重复绑定，R2）
- `INDEX(user_id)`（反查某 user 绑定的所有 provider）
- `INDEX(provider, email)`（OAuth 回调按 provider+email 定位合并候选）

### 2.2 `users` 扩展（P3 增列，结构其余沿用 P2）

P2 `users`（id / email / password_hash / is_active / created_at / updated_at）不变，**新增两列**：

| 新字段 | 类型 | 约束 | 示例 | 说明 |
|--------|------|------|------|------|
| display_name | TEXT | nullable | `Alice Chen` | OAuth profile 显示名；本地账户 NULL（前端兜底用 email） |
| avatar_url | TEXT | nullable | `https://avatars.../u/12345` | OAuth 头像 URL；本地账户 NULL |

**说明**：
- `password_hash` 对 OAuth 自动建户的 user 为 **NULL**（无密码，仅可经 OAuth 登录）；本地账户保持 bcrypt hash。登录端点需容忍 NULL（OAuth-only user 走 OAuth 入口）。
- `email` 仍 `UNIQUE NOT NULL`（P2 不变），是邮箱合并的锚点（R2）。

---

## 3. 邮箱合并逻辑（R2，实现于 `services/oauth_linker.py`）

OAuth 回调取得 userinfo（provider / provider_user_id / email / display_name / avatar_url）后：

1. **查 oauth_accounts** by `(provider, provider_user_id)` → 命中：取其 `user_id`（已绑定），刷新 profile，跳到 4。
2. 未命中 → **查 users by email**（小写规范化）：
   - 命中：绑定到既有 user（建 oauth_accounts 行，user_id=既有），刷新 display_name/avatar。
   - 未命中：**新建 user**（email / display_name / avatar_url 来自 profile，password_hash NULL），再建 oauth_accounts 行。
3. 记录 `oauth_accounts`（INSERT，`UNIQUE(provider, provider_user_id)` 兜底防并发重复）。
4. 调 P2 `security.create_tokens(user)` 签发等价 JWT（access + refresh）。

**并发安全**：`(provider, provider_user_id)` 唯一约束 + INSERT 失败时回查重试；email 合并存在 TOCTOU 窗口（P3 接受，Assumptions），生产可加 advisory lock。

---

## 4. Alembic 迁移：`0002_oauth`

- **文件**：`orchestrator/migrations/versions/0002_oauth.py`
- **依赖**：`down_revision = "0001"`（P2 init）
- **upgrade**：
  1. `CREATE TABLE oauth_accounts (...)`（含 CHECK / UNIQUE / 索引）
  2. `ALTER TABLE users ADD COLUMN display_name TEXT` / `ADD COLUMN avatar_url TEXT`
- **downgrade**：drop columns → drop table（逆序）
- **幂等**：标准 Alembic op，testcontainers-integration 验证 upgrade/downgrade 双向。

---

## 5. 关键查询

### 5.1 OAuth 回调定位/建户（合并，R2 §3）

```sql
-- 1) 命中已绑定
SELECT user_id FROM oauth_accounts WHERE provider=:p AND provider_user_id=:pid;
-- 2) 未命中→按 email 合并候选
SELECT id FROM users WHERE LOWER(email)=LOWER(:email);
```

### 5.2 列出某 user 绑定的 provider（账户绑定/解绑 UI，FR-006）

```sql
SELECT provider, email, created_at FROM oauth_accounts WHERE user_id=:uid;
```

### 5.3 解绑（FR-006，防止最后一个登录方式丢失由应用层判断）

```sql
DELETE FROM oauth_accounts WHERE user_id=:uid AND provider=:p;
```

---

## 6. 与 P2 的不变量（零迁移验证）

- P2 `users` 既有的注册/登录/JWT/归属/审计查询在 P3 增列后**行为不变**（增列 nullable，不破坏既有 SELECT/INSERT）。
- P2 `refresh_tokens` / `audit_logs` / `workspaces` 等零改动。
- 回归：P1/P2 E2E 在 `0002_oauth` 迁移后全绿（SC-008 / FR-032）。
