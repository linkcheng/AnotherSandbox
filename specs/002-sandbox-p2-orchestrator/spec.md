# Feature Specification: AI 个人沙箱 P2 — Orchestrator 编排与认证层

**Feature Branch**: `002-sandbox-p2-orchestrator`

**Created**: 2026-06-19

**Status**: Draft

**Source**: `.archive/sandbox-design.md` §8（多租户 / Orchestrator）、§8.6（认证与鉴权）、§8.8（Orchestrator 层）、§9.3（Orchestrator API）、§11（安全基线）

**Input**: 在 P1 单 workspace 沙箱（`specs/001-sandbox-p1-stack`，已交付）之上叠加 Orchestrator 层（独立 Python 服务，FastAPI + PostgreSQL），实现多租户 workspace 生命周期编排、JWT 统一认证、跨 workspace 元数据管理与审计落库。P2 是"可选叠加层"——叠加在 sandbox 之上，不侵入 workspace 内部业务代码（§8.8.5 不变量）。

**范围决策（已与 stakeholder 确认）**：
- **做（核心 MVP）**：① workspace 生命周期编排（`docker compose -p`）② PostgreSQL 元数据 ③ JWT 自建账户认证 + 可信 header 注入 ④ 审计落库 ⑤ cap-agent 认证中间件扩展（P1→P2 零迁移）⑥ CLI + OpenAPI
- **不做（推迟）**：Snapshot 编排、计量计费 `usage_metrics`、React 启动器 UI、SSO/OAuth
- **安全简化（沿用 P1 宽松处理）**：Shell 策略保持 `permissive`、Chromium 保持 `--no-sandbox`；P2 安全增量仅为「JWT 网关认证 + 可信 header + 审计落库」

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 多租户 Workspace 生命周期编排 (Priority: Core)

平台运维者通过 Orchestrator 创建、启动、停止、暂停、恢复、删除多个相互隔离的 workspace。每个 workspace 是一个独立的 docker compose project，复用 P1 已构建的镜像，仅区分 Profile 路径与端口前缀（§8.3 "Profile 即参数"）。Orchestrator 通过 `docker compose -p {workspace}` 驱动各 workspace 的 cap-* 容器组，并维护 workspace 状态机。

**Why this priority**: 没有多 workspace 编排，"多租户"无从谈起——这是 Orchestrator 存在的根本理由，也是其余所有用户故事（认证、审计、CLI）的运行时载体。

**Independent Test**: 通过 Orchestrator 创建一个 workspace 并 `start`，验证该 workspace 名下出现一组 healthy 的 cap-* 容器、独立网络、独立卷；`stop` 后容器消失但 Profile 数据保留。

**Acceptance Scenarios**:

1. **Given** 宿主机已有 P1 镜像，**When** 调用 Orchestrator 创建并启动 workspace `alice`，**Then** 出现独立的 `{prefix}-cap-*` 容器组全部 healthy，且 `alice` 的 `/workspace/` 与其他 workspace 物理隔离。
2. **Given** workspace `alice` 处于 RUNNING，**When** 调用 `pause`，**Then** 容器进入 paused 状态、Profile 保留；`resume` 后秒级恢复 RUNNING。
3. **Given** workspace `alice` 处于 RUNNING，**When** 调用 `stop`，**Then** 所有 cap-* 容器停止、Profile 保留；再次 `start` 后重新拉起。
4. **Given** workspace `alice` 存在，**When** 调用 `delete`，**Then** 容器组与网络移除，Profile 按策略处理（软删除标记 / 硬删除）。

---

### User Story 2 - JWT 用户认证与 Workspace 归属 (Priority: Core)

用户通过自建账户注册并登录，获得 JWT。访问任何 workspace API 时，Orchestrator 校验 JWT、解析目标 workspace、校验该用户对该 workspace 的归属关系（owner / collaborator / viewer），校验通过后向 workspace 注入可信 header（`X-User-Id` / `X-Workspace-Id` / `X-Permissions`）。

**Why this priority**: P1 的"网络隔离为唯一防线"在多租户下失效。统一身份认证 + workspace 归属是 P2 区别于 P1 的核心安全增量（§8.6.2）。

**Independent Test**: 未携带 JWT 访问被 401 拒绝；登录后访问自己拥有的 workspace 成功；访问他人 workspace 被 403 拒绝。

**Acceptance Scenarios**:

1. **Given** 一个未注册用户，**When** 提交注册（邮箱 + 密码），**Then** 账户创建成功并可登录获得 JWT。
2. **Given** 已登录用户 alice，**When** alice 携带 JWT 访问自己创建的 workspace，**Then** 请求被放行，workspace 收到含 alice 身份的可信 header。
3. **Given** 已登录用户 bob，**When** bob 携带 JWT 访问 alice 的 workspace（无授权），**Then** 返回 403。
4. **Given** 一个过期/伪造的 JWT，**When** 访问任意 workspace，**Then** 返回 401。

---

### User Story 3 - nginx auth_request 网关鉴权与可信 Header 透传 (Priority: Core)

workspace 的 cap-nginx 对所有入口请求发起 `auth_request` 子请求向 Orchestrator 校验身份（§8.6.2 / §11.5）；校验通过后，Orchestrator 注入的可信 header 被透传到 workspace 内部。cap-agent 在 `AUTH_MODE=orchestrator` 下读取可信 header 完成鉴权（不做 JWT 校验），与 P1 的 `AUTH_MODE=none` 共存，业务路由代码零改动。

**Why this priority**: 这是"关注点分离"（§8.6.3）的落地——Orchestrator 见身份不见业务，cap-agent 见业务不见密码。没有这层，多租户鉴权无法穿透到 workspace 内部。

**Independent Test**: 绕过 Orchestrator 直连 workspace cap-nginx 的请求被 `auth_request` 拒绝；经 Orchestrator 携带合法 JWT 的请求被放行，cap-agent 能读到可信 header 中的用户身份。

**Acceptance Scenarios**:

1. **Given** workspace cap-nginx 配置了 `auth_request` 指向 Orchestrator，**When** 一个携带合法 JWT（经 Orchestrator）的请求到达，**Then** `auth_request` 返回 2xx，请求透传到 cap-agent，cap-agent 读到 `X-User-Id` 等可信 header。
2. **Given** 一个未认证请求直接到达 workspace cap-nginx，**When** cap-nginx 发起 `auth_request`，**Then** Orchestrator 返回 401，cap-nginx 拒绝该请求（fail-closed）。
3. **Given** cap-agent 设置 `AUTH_MODE=orchestrator`，**When** 收到带可信 header 的请求，**Then** 正常执行业务（与 P1 业务路由行为一致）；当 `AUTH_MODE=none` 时，行为与 P1 完全一致（零迁移）。

---

### User Story 4 - 操作审计落库 (Priority: Important)

workspace 内 cap-terminal / cap-mcp / cap-agent 在执行关键操作（shell.exec / fs.write / browser.action / gui.action）后，通过 HTTP POST 把结构化事件上报到 Orchestrator `/api/v1/audit/ingest`，写入 `audit_logs` 表。上报为 best-effort：Orchestrator 不可达时不阻塞业务命令。运维者可按 workspace / user / 事件类型 / 时间范围查询审计记录（§8.8.6）。

**Why this priority**: 多租户场景必须具备可追溯性。审计是 P2 安全增量的可观测支柱，但不阻塞核心路径（best-effort）。

**Independent Test**: 在某 workspace 执行一条 shell 命令后，`audit_logs` 表出现对应 `shell.exec` 记录，含正确的 workspace_id / actor / detail；断开 Orchestrator 后同一命令仍成功执行（不被审计失败阻塞）。

**Acceptance Scenarios**:

1. **Given** 已认证用户在某 workspace 通过 MCP 执行 `shell_exec("echo hi")`，**When** 命令执行完成，**Then** `audit_logs` 新增一条 `event_type=shell.exec`、`success=true`、`detail` 含命令摘要的记录。
2. **Given** Orchestrator 审计端点临时不可达，**When** workspace 内执行命令，**Then** 命令仍正常完成并返回结果（best-effort，不阻塞）。
3. **Given** 审计库已有数据，**When** 运维者按 `workspace_id` + `event_type=fs.write` + 最近 7 天查询，**Then** 返回匹配的审计记录列表。

---

### User Story 5 - Orchestrator CLI 与 OpenAPI 入口 (Priority: Important)

提供 `orchestrator` CLI（workspace create / start / stop / pause / resume / list、user register / login）作为人机操作入口；FastAPI 自动生成 OpenAPI 文档与 Swagger UI 作为程序化集成入口。P2 不开发独立前端（§8.8.7 将 UI 列为可推迟项）。

**Why this priority**: 多租户运维需要可脚本化的入口。CLI + OpenAPI 是最低成本覆盖"人"与"程序"两类使用者的方案。

**Independent Test**: 一条命令链 `orchestrator user register → login → workspace create → start → list` 全部成功；Swagger UI（`/docs`）可访问并展示全部 workspace/user/audit 端点。

**Acceptance Scenarios**:

1. **Given** Orchestrator 服务已运行，**When** 执行 `orchestrator workspace create alice && orchestrator workspace start <id>`，**Then** workspace 被创建并启动（等价于调用 REST API）。
2. **Given** Orchestrator 服务已运行，**When** 浏览器访问 `/docs`，**Then** 看到 Swagger UI，列出 workspace 生命周期、user 认证、audit 查询等全部端点及其 schema。
3. **Given** CLI 已登录（本地保存 token），**When** 执行 `orchestrator workspace list`，**Then** 返回当前用户可见的 workspace 列表及状态。

---

### Edge Cases

- Orchestrator 启动 workspace 时 `docker compose` 子进程失败（镜像缺失 / 端口冲突 / 卷权限）→ workspace 状态置 `ERROR`，返回结构化错误，不留下半启动状态。
- cap-nginx `auth_request` 子请求到 Orchestrator 超时或 Orchestrator 不可达 → **fail-closed**：拒绝该 workspace 请求（安全优先于可用性）。
- 审计上报时 Orchestrator 不可达 → best-effort：本地短暂缓冲后重试，超限丢弃，绝不阻塞业务命令。
- 同一用户对同一 workspace 并发重复 `start`（已在 RUNNING）→ 幂等返回当前状态，不重复拉起。
- JWT 过期 → 返回 401，客户端可用 refresh token 换新；refresh token 失效则需重新登录。
- workspace 删除时仍有活跃连接 → 先优雅停止（stop）再清理，超时则强制移除容器组。
- PostgreSQL 不可用 → Orchestrator fail fast（启动期迁移失败即拒绝启动），运行期写失败返回 5xx，不静默降级。
- 端口前缀耗尽（并发 workspace 过多）→ 创建时明确报错，提示可分配范围。
- Orchestrator 重启后，对仍存活但元数据丢失的 workspace 容器组 → 提供 reconcile/adopt 机制或在 list 中标记 `orphan`。

## Requirements *(mandatory)*

### Functional Requirements

#### Orchestrator 服务与编排

- **FR-001**: 系统 MUST 提供独立 Orchestrator 服务（Python + FastAPI），作为 P1 sandbox 之上的可选叠加层。
- **FR-002**: Orchestrator MUST 通过 `docker compose -p {workspace}` 驱动各 workspace 的 cap-* 容器组，复用 P1 已构建镜像（不重建）。
- **FR-003**: 每个 workspace MUST 拥有独立的 docker compose project 名、独立 sandbox-net 网络、独立 Profile volume 路径，实现文件/进程/网络/端口隔离（§8.4）。
- **FR-004**: Orchestrator MUST 实现 workspace 状态机 `CREATED → STARTING → RUNNING ⇄ PAUSED → STOPPED → DELETED`（含 `ERROR`），动作语义（pause/resume/stop/start）遵循 §8.5。
- **FR-005**: Orchestrator MUST 为每个 workspace 分配并隔离端口前缀（PORT_PREFIX），对外端口无冲突。
- **FR-006**: Orchestrator MUST 聚合各 workspace 内 cap-* 的 healthcheck，维护 workspace 健康视图，并对异常 workspace 标记 `ERROR`。

#### 元数据存储

- **FR-007**: Orchestrator MUST 使用 PostgreSQL 持久化元数据，并通过 Alembic 管理 schema 迁移。
- **FR-008**: 数据模型 MUST 至少包含 `users` / `workspaces` / `workspace_owners` / `templates` / `audit_logs` 五张表（字段参考 §8.8.4 草案）。
- **FR-009**: workspace 与 user MUST 通过 `workspace_owners` 建立归属关系，支持 `owner` / `collaborator` / `viewer` 三种角色。
- **FR-010**: Orchestrator MUST 对敏感凭证（用户密码哈希、JWT 签名密钥）做安全存储，明文密码绝不落库。

#### 认证与鉴权

- **FR-011**: Orchestrator MUST 提供 JWT 自建账户体系：注册（邮箱 + 密码）、登录、token refresh。
- **FR-012**: Orchestrator MUST 在放行 workspace 请求前完成：JWT 校验 → workspace_id 解析 → ownership 校验（查 `workspace_owners`）→ 注入可信 header（`X-User-Id` / `X-Workspace-Id` / `X-Permissions`）。
- **FR-013**: workspace cap-nginx MUST 通过 `auth_request` 子请求向 Orchestrator 校验入口请求身份，仅放行 Orchestrator 确认的请求（§8.6.2 / §11.5）。
- **FR-014**: cap-agent MUST 支持 `AUTH_MODE=orchestrator` 的 `OrchestratorHeaderAuthMiddleware`（读可信 header，不做 JWT 校验），与 P1 的 `AUTH_MODE=none` 共存；通过环境变量切换，P1 业务路由代码零改动（§8.6.4）。
- **FR-015**: 未认证访问 MUST 返回 401；已认证但越权（无 ownership）访问 MUST 返回 403。

#### 审计

- **FR-016**: cap-terminal / cap-mcp / cap-agent MUST 在关键操作（`shell.exec` / `fs.write` / `browser.action` / `gui.action`）后，通过 HTTP POST 结构化事件到 Orchestrator `/api/v1/audit/ingest`，写入 `audit_logs`。
- **FR-017**: 审计事件 MUST 至少包含 `workspace_id` / `actor_user_id`（可空，表 agent）/ `event_type` / `source`（cap-terminal|cap-mcp|cap-agent）/ `detail`(JSONB) / `success` / `created_at`。
- **FR-018**: 审计上报 MUST 为 best-effort：Orchestrator 不可达时不阻塞业务命令（本地缓冲后重试，超限丢弃），审计失败不影响命令结果。
- **FR-019**: Orchestrator MUST 提供按 `workspace_id` / `actor_user_id` / `event_type` / 时间范围查询审计日志的端点。

#### 操作入口

- **FR-020**: Orchestrator MUST 提供 CLI，覆盖 workspace 生命周期（create / start / stop / pause / resume / list）与 user（register / login）。
- **FR-021**: Orchestrator MUST 通过 FastAPI 自动生成 OpenAPI 文档与 Swagger UI（`/docs`）。

#### 兼容性（P1 不变量）

- **FR-022**: P1 单 workspace 模式（`AUTH_MODE=none`，无 Orchestrator）MUST 仍可独立运行，不依赖 Orchestrator；Orchestrator 是可选叠加层（§8.8.5）。
- **FR-023**: P1 的 workspace 内业务路由（`/v1/*` / `/cdp` / `/gui`）代码 MUST 在 P2 下行为不变。

#### P2 明确不做（依据范围确认 + §8.8.7 / §11）

- **FR-NI-1**: P2 不实现 Snapshot 编排（create / restore / export），保留 P1 docker volume 级备份能力。
- **FR-NI-2**: P2 不实现计量计费（`usage_metrics`）。
- **FR-NI-3**: P2 不实现 React 启动器 UI。
- **FR-NI-4**: P2 不实现 Shell 命令策略（保持 `permissive`，§11.4）。
- **FR-NI-5**: P2 不重新启用 Chromium sandbox（保持 `--no-sandbox`，§11.1）。
- **FR-NI-6**: P2 不实现 SSO / OAuth（仅 JWT 自建账户）。

#### 测试

- **FR-024**: Orchestrator Python 服务 MUST 有 pytest 单元测试，行覆盖率 ≥ 80%。
- **FR-025**: Orchestrator MUST 有 Integration 测试（docker compose 子进程用临时 project 隔离；PostgreSQL 用 ephemeral 容器或事务回滚隔离）。
- **FR-026**: 系统 MUST 提供 E2E：经 Orchestrator 创建 workspace → 登录取 JWT → 经 Orchestrator+可信 header 访问 workspace `shell_exec` → 验证 `audit_logs` 落库。
- **FR-027**: 测试镜像 MUST 与生产镜像共享 Dockerfile（multi-stage target），延续 P1 FR-032 约定。

### Key Entities *(include if feature involves data)*

- **Workspace（多租户单元）**：独立 compose project + 网络 + Profile volume + 端口前缀；由状态机管理生命周期；与 P1 单 workspace 同构但参数化。
- **User**：自建账户（邮箱 + 密码哈希），持有 JWT 凭证，可拥有或协作多个 workspace。
- **WorkspaceOwner**：user 与 workspace 的归属关系，含角色（owner / collaborator / viewer）。
- **Template**：workspace 初始化模板（`init_script` / `agents_md_seed`），用于标准化创建。
- **AuditLog**：结构化操作事件（shell.exec / fs.write / browser.action / gui.action），关联 workspace 与 actor，存 PostgreSQL。
- **TrustedHeader**：Orchestrator 注入给 workspace 的可信身份载体（`X-User-Id` / `X-Workspace-Id` / `X-Permissions`），是 Orchestrator 与 workspace 内 cap-agent 的契约边界。
- **AuthMiddleware（cap-agent）**：认证中间件抽象，`none`（P1）与 `orchestrator`（P2）双实现，环境变量切换。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 通过 Orchestrator 创建并启动一个全新 workspace 到全部 cap-* healthy 的耗时 < 120 秒（P1 镜像已构建，复用缓存）。
- **SC-002**: 已认证用户完整链路（创建 workspace → 登录取 JWT → 经鉴权访问 → 审计落库）100% 通过；未认证访问 100% 返回 401、越权访问 100% 返回 403。
- **SC-003**: Orchestrator Python 服务单元测试行覆盖率 ≥ 80%。
- **SC-004**: 审计端点不可达时，workspace 内业务命令成功率与有审计时一致（100% 不阻塞），审计上报额外延迟开销 < 50ms。
- **SC-005**: 同一宿主机并发运行 ≥ 3 个 workspace（独立 compose project）时互彻底隔离：A 的 shell 看不到 B 的 `/workspace` 文件、A 的 sandbox-net 不可达 B 的容器。
- **SC-006**: P1 单 workspace 模式（`AUTH_MODE=none`，无 Orchestrator）回归 E2E 全绿，业务路由代码零改动（零迁移验证）。
- **SC-007**: `orchestrator` CLI 可在 ≤ 6 条命令内完成「注册→登录→创建→启动→列表→停止」全生命周期。
- **SC-008**: cap-nginx `auth_request` 鉴权在 Orchestrator 健康 < 200ms 内完成子请求；Orchestrator 不可达时 fail-closed，无未认证请求穿透。

## Assumptions

- 宿主机已安装 Docker 24+ 与 docker compose v2，且 P1 的 4 个 base 镜像与 7 个 cap-* 镜像已构建可用（P2 复用，不重建）。
- Orchestrator 自身及其依赖的 PostgreSQL 以 docker compose 服务形式与各 workspace 共存于同一宿主机（P2 不引入 K8s，§8.8.5 Phase 2 形态）。
- 端口分配采用 `PORT_PREFIX` 自动分配策略（按可用范围递增），默认 base 范围在 plan 阶段确定；用户也可显式指定。
- workspace 删除默认采用软删除（置 `deleted_at`，保留 Profile 一段可配置保留期），并提供硬删除选项；具体保留期在 plan 阶段细化。
- 密码存储采用行业标准的加盐哈希（如 bcrypt/argon2）；JWT 签名密钥由环境变量注入，默认开发态随机生成。
- `auth_request` 不可达时采用 fail-closed（拒绝请求），安全优先于可用性；该策略可在环境变量中切换为 fail-open（仅限受信内网调试）。
- P2 的"用户"是平台运维者与集成方（CLI / API 消费者），非终端 GUI 用户；故 UI 仅需 CLI + Swagger，无独立前端（§8.8.7）。
- 审计上报从 workspace 内 cap-* 出站到 Orchestrator 走宿主机网络（workspace 的 sandbox-net 与 Orchestrator 网络间通过宿主机回环或专属 bridge 互通，具体在 plan 阶段设计）。
- 各 cap-* 服务的 HTTP 客户端（用于审计上报与可信 header 读取）复用 P1 已有 httpx 基础设施。
- 模板（templates）表 P2 提供至少一个 `minimal` 默认模板；模板系统完整实现推迟（§8.8.7）。
- 跨 workspace 路由（`{workspace}.{host}` DNS 分发）P2 用端口前缀（PORT_PREFIX）实现最小可用，基于域名的路由分发推迟。
