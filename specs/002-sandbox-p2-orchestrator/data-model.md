# Data Model: AI 个人沙箱 P2 — Orchestrator 编排与认证层

**Date**: 2026-06-19
**Source**: [spec.md](./spec.md) · [plan.md](./plan.md) · [research.md](./research.md) · `.archive/sandbox-design.md` §8.8.4（schema 草案）/ §8.8.6（审计查询）

本文档定义 P2 Orchestrator 的 PostgreSQL schema、SQLAlchemy ORM 映射、Alembic 迁移设计与关键查询。P2 在 §8.8.4 草案基础上补全字段、约束、索引，并新增 `refresh_tokens` 表（R5：refresh token 存库可吊销）。共 **6 张表**（spec FR-008 要求"至少 5 张"）。

所有时间字段用 `TIMESTAMPTZ`（UTC）。主键 `UUID`（除 audit_logs 用 `BIGSERIAL` 高写入）。合成示例值均为虚构，非真实数据。

---

## 1. 实体关系图（ER）

```
users (1) ─────< workspace_owners >───── (1) workspaces
  │                                            │
  │                                            ├── template_id ──> templates (1)
  │                                            ├── owner_user_id ─> users
  │                                            └── external_port (唯一, 软删除除外)
  │
  └── (1) ─────< refresh_tokens

workspaces (1) ─────< audit_logs (N) >──── actor_user_id ──> users (nullable)
```

---

## 2. 表定义

### 2.1 `users` — 用户账户

| 字段 | 类型 | 约束 | 示例 | 说明 |
|------|------|------|------|------|
| id | UUID | PK, default gen_random_uuid() | `a1b2c3d4-...` | 用户唯一 ID（JWT `sub`） |
| email | TEXT | UNIQUE NOT NULL, LOWER 索引 | `alice@example.com` | 登录邮箱（小写规范化） |
| password_hash | TEXT | NOT NULL | bcrypt hash | passlib bcrypt 哈希，明文不落库（FR-010） |
| is_active | BOOLEAN | NOT NULL DEFAULT true | `true` | 账户启用态（可禁用） |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | `2026-06-19T04:00:00Z` | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | — | 最后更新（触发器维护） |

**索引**：`UNIQUE LOWER(email)`、`PK(id)`。

### 2.2 `templates` — Workspace 初始化模板

| 字段 | 类型 | 约束 | 示例 | 说明 |
|------|------|------|------|------|
| id | UUID | PK | `tpl-minimal-...` | 模板 ID |
| name | TEXT | UNIQUE NOT NULL | `minimal` | 模板名（spec Assumption：P2 提供 minimal） |
| description | TEXT | nullable | `"最小可用 workspace"` | 说明 |
| init_script | TEXT | nullable | `pip install pandas` | 创建时执行的 shell（推迟完整实现，P2 仅记录） |
| agents_md_seed | TEXT | nullable | `# 项目说明...` | AGENTS.md 初始内容（§4.6.6） |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | — | — |

**索引**：`UNIQUE(name)`、`PK(id)`。

### 2.3 `workspaces` — Workspace 元数据（核心）

| 字段 | 类型 | 约束 | 示例 | 说明 |
|------|------|------|------|------|
| id | UUID | PK | `ws-alice-001...` | workspace 唯一 ID |
| name | TEXT | NOT NULL | `alice-dev` | 人类可读名 |
| slug | TEXT | UNIQUE NOT NULL | `ws-alice-001` | compose project 名（`docker compose -p {slug}`），全局唯一，URL-safe |
| owner_user_id | UUID | FK→users.id, NOT NULL | `a1b2c3d4-...` | 创建者（owner） |
| template_id | UUID | FK→templates.id, nullable | `tpl-minimal-...` | 初始化模板 |
| status | TEXT | NOT NULL, CHECK in (created, starting, running, paused, stopped, deleted, error) | `running` | 状态机（§8.5） |
| compose_project | TEXT | NOT NULL | `ws-alice-001` | = slug，冗余存便于 compose_runner 直读 |
| external_port | INT | NOT NULL, CHECK (1024..65535) | `8101` | 对外端口（R2，仅 cap-nginx） |
| volume_path | TEXT | NOT NULL | `/data/workspaces/ws-alice-001` | 宿主机 Profile 卷路径 |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | — | 创建时间 |
| last_active_at | TIMESTAMPTZ | nullable | — | 最近活跃（healthcheck 更新） |
| deleted_at | TIMESTAMPTZ | nullable | — | 软删除标记（R1，NULL=未删） |

**索引**：
- `PK(id)`
- `UNIQUE(slug)`
- `UNIQUE(external_port) WHERE deleted_at IS NULL`（partial unique，R2 并发分配兜底）
- `INDEX(owner_user_id)`（列出某用户 workspace）

### 2.4 `workspace_owners` — 归属关系（多对多 + 角色）

| 字段 | 类型 | 约束 | 示例 | 说明 |
|------|------|------|------|------|
| workspace_id | UUID | FK→workspaces.id ON DELETE CASCADE, NOT NULL | `ws-alice-001...` | — |
| user_id | UUID | FK→users.id ON DELETE CASCADE, NOT NULL | `a1b2c3d4-...` | — |
| role | TEXT | NOT NULL, CHECK in (owner, collaborator, viewer) | `owner` | 角色（FR-009） |
| granted_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | — | 授权时间 |

**约束/索引**：
- `PK(workspace_id, user_id)`（复合主键）
- `INDEX(user_id)`（反查用户的所有 workspace）

### 2.5 `audit_logs` — 审计事件（高写入）

| 字段 | 类型 | 约束 | 示例 | 说明 |
|------|------|------|------|------|
| id | BIGSERIAL | PK | `1234567` | 自增（写入友好） |
| workspace_id | UUID | FK→workspaces.id, NOT NULL | `ws-alice-001...` | 事件归属 workspace |
| actor_user_id | UUID | FK→users.id, nullable | `a1b2c3d4-...` | 操作者（NULL=agent，FR-017） |
| event_type | TEXT | NOT NULL | `shell.exec` | 事件类型（shell.exec/fs.write/browser.action/gui.action，FR-017） |
| source | TEXT | NOT NULL, CHECK in (cap-terminal, cap-mcp, cap-agent) | `cap-terminal` | 事件来源服务 |
| detail | JSONB | NOT NULL | `{"command":"echo hi","exit_code":0}` | 结构化 payload（FR-017） |
| success | BOOLEAN | NOT NULL | `true` | 操作是否成功 |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | `2026-06-05T04:05:00Z` | 事件时间 |

**索引**（§8.8.4）：
- `PK(id)`
- `INDEX(workspace_id, created_at DESC)` — 按空间查最近事件
- `INDEX(event_type, created_at DESC)` — 按类型查
- `INDEX(actor_user_id, created_at DESC)` — 按用户查

> **分区预留**：audit_logs 高写入，P2 单表 + 索引足够（SC-005 仅 ≥3 workspace）。若未来量大，按 `created_at` 月分区（推迟，P2 不做）。

### 2.6 `refresh_tokens` — Refresh Token（R5，可吊销）

| 字段 | 类型 | 约束 | 示例 | 说明 |
|------|------|------|------|------|
| id | UUID | PK | `rt-...` | — |
| user_id | UUID | FK→users.id ON DELETE CASCADE, NOT NULL | `a1b2c3d4-...` | 归属用户 |
| token_hash | TEXT | NOT NULL, UNIQUE | sha256 hash | refresh token 哈希（不存明文） |
| expires_at | TIMESTAMPTZ | NOT NULL | `2026-06-26T04:00:00Z` | 过期时间（默认 created+7d） |
| revoked_at | TIMESTAMPTZ | nullable | — | 吊销时间（NULL=有效） |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | — | — |

**索引**：`PK(id)`、`UNIQUE(token_hash)`、`INDEX(user_id)`。

> 这张表是 spec FR-008"至少 5 张"之外的**第 6 张辅助表**，支撑 R5 的 refresh token 可吊销需求。

---

## 3. SQLAlchemy 2.x ORM 映射（示意）

```python
# orchestrator/src/orchestrator/models/workspace.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint("status IN ('created','starting','running','paused','stopped','deleted','error')"),
        UniqueConstraint("external_port", name="uq_external_port_active",
                         postgresql_where=Text("deleted_at IS NULL")),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("templates.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="created")
    compose_project: Mapped[str] = mapped_column(String(64), nullable=False)
    external_port: Mapped[int] = mapped_column(Integer, nullable=False)
    volume_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(timezone=True, default=lambda: datetime.now(timezone.utc))
    last_active_at: Mapped[datetime | None] = mapped_column(timezone=True, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(timezone=True, nullable=True)
```

> 其余表（users/templates/workspace_owners/audit_logs/refresh_tokens）ORM 结构同 §2 字段表，完整实现见 tasks.md M0。所有模型用 SQLAlchemy 2.x `Mapped[...]` 风格 + async session。

---

## 4. Alembic 迁移设计

### 4.1 初始迁移 `0001_init`

```text
up:
  CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
  CREATE TABLE users (...);
  CREATE TABLE templates (...);
  CREATE TABLE workspaces (...);               -- 含 partial unique index
  CREATE TABLE workspace_owners (...);
  CREATE TABLE refresh_tokens (...);
  CREATE TABLE audit_logs (...);
  CREATE INDEX idx_audit_workspace_time ON audit_logs (workspace_id, created_at DESC);
  CREATE INDEX idx_audit_event_type ON audit_logs (event_type, created_at DESC);
  CREATE INDEX idx_audit_actor ON audit_logs (actor_user_id, created_at DESC);
  CREATE UNIQUE INDEX uq_workspaces_external_port_active
      ON workspaces (external_port) WHERE deleted_at IS NULL;
  INSERT INTO templates (id, name, description) VALUES (gen_random_uuid(), 'minimal', '最小可用 workspace');
down:
  DROP TABLE audit_logs; DROP TABLE refresh_tokens; DROP TABLE workspace_owners;
  DROP TABLE workspaces; DROP TABLE templates; DROP TABLE users;
```

### 4.2 流程约定

- `orchestrator/migrations/env.py`：async engine + `target_metadata = Base.metadata`
- 改 model → `uv run alembic revision --autogenerate -m "msg"` → 人工 review（autogenerate 对 partial index/enum 推断不全，需手补）→ commit
- Orchestrator lifespan 启动期 `alembic upgrade head`，失败 fail-fast 拒启动（R6 / Edge Case）

### 4.3 测试

- Integration（testcontainers-postgres）：`upgrade head` 建表成功 + `downgrade base` + `upgrade head` 往返幂等
- partial unique index 验证：插入两条同 `external_port`（一条 deleted_at=NULL 一条非 NULL）应成功；两条均 NULL 应报唯一冲突

---

## 5. 关键查询（§8.8.6）

### 5.1 列出用户拥有的 workspace（CLI `workspace list`）

```sql
SELECT w.* FROM workspaces w
JOIN workspace_owners wo ON wo.workspace_id = w.id
WHERE wo.user_id = $1 AND w.deleted_at IS NULL
ORDER BY w.last_active_at DESC NULLS LAST;
```

### 5.2 workspace 归属校验（FR-012，`/verify` 与 deps 复用）

```sql
-- 用户 $user 对 workspace $ws 的角色（无行=无权限）
SELECT role FROM workspace_owners
WHERE workspace_id = $ws AND user_id = $user;
```

### 5.3 端口分配：最小可用端口（R2）

```sql
-- 找 [WORKSPACE_PORT_START, END] 内未被活跃 workspace 占用的最小端口
SELECT port FROM generate_series($start, $end) AS port
LEFT JOIN workspaces w ON w.external_port = port AND w.deleted_at IS NULL
WHERE w.id IS NULL
ORDER BY port LIMIT 1;
```

> 并发兜底：partial unique index 保证重复插入失败，调用方捕获 `IntegrityError` 重试（R2）。

### 5.4 审计：某 workspace 最近 N 天 shell.exec（§8.8.6）

```sql
SELECT * FROM audit_logs
WHERE workspace_id = $1 AND event_type = 'shell.exec'
  AND created_at > now() - interval '7 days'
ORDER BY created_at DESC;
```

### 5.5 审计：某用户所有 workspace 的失败 browser.action

```sql
SELECT al.* FROM audit_logs al
JOIN workspace_owners wo ON wo.workspace_id = al.workspace_id
WHERE wo.user_id = $1 AND al.event_type = 'browser.action' AND al.success = false
ORDER BY al.created_at DESC LIMIT 100;
```

### 5.6 审计写入（`/api/v1/audit/ingest`，高频）

```sql
INSERT INTO audit_logs
  (workspace_id, actor_user_id, event_type, source, detail, success)
VALUES ($1, $2, $3, $4, $5::jsonb, $6);
```

---

## 6. 状态机字段值流转（§8.5，对应 FR-004）

| 动作 | 前置状态 | 目标状态 | compose 操作 | Profile |
|------|----------|----------|--------------|---------|
| create | — | created | 无（仅建目录+DB 行） | 建 volume_path 目录 |
| start | created/stopped | starting→running | `up -d --wait` | 保留 |
| pause | running | paused | `pause` | 保留（冻结） |
| resume | paused | running | `unpause` | 不变 |
| stop | running/paused | stopped | `down`（不删卷） | 保留 |
| delete | running/stopped | deleted（软） | `down -v`（R1 硬删触发） | 软删保留，R1 清理任务后删 |
| (异常) | starting/running | error | 失败 `down` 兜底 | 保留（可排查） |

> `starting` 是瞬态：lifecycle 调 `up --wait` 前置 STARTING，成功 RUNNING / 失败 ERROR。

---

## 7. 不在数据模型范围内（P2 明确排除）

- **`usage_metrics` 表**（计量计费，FR-NI-2，推迟）
- **`snapshots` 表**（Snapshot 编排，FR-NI-1，推迟）
- workspace 内业务实体（shell/browser/file）——仍在 cap-* 内，不入 Orchestrator DB（§8.8.2 职责不重叠）
- 多 workspace 协作的邀请/分享令牌表（P2 仅 owner/collaborator/viewer 直接授权，邀请流程推迟）
