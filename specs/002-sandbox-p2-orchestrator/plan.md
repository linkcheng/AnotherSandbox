# Implementation Plan: AI 个人沙箱 P2 — Orchestrator 编排与认证层

**Branch**: `002-sandbox-p2-orchestrator` | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-sandbox-p2-orchestrator/spec.md`

**Source**: `.archive/sandbox-design.md` §8（多租户/Orchestrator）、§8.6（认证）、§8.8（Orchestrator 层）、§9.3（Orchestrator API）、§11（安全基线）

## Summary

在 P1 单 workspace 沙箱之上叠加 **Orchestrator**——一个独立 Python 服务（FastAPI + PostgreSQL + Alembic + SQLAlchemy），承担三层职责：① 编排（workspace 生命周期，通过 `docker compose -p {ws}` 驱动复用的 P1 镜像）② 元数据（PostgreSQL：users / workspaces / workspace_owners / templates / audit_logs）③ 入口（JWT 自建账户认证 + 可信 header 注入 + CLI + OpenAPI）。Orchestrator 是"可选叠加层"，不侵入 workspace 内业务代码（§8.8.5 不变量）；P1 单 workspace 模式仍独立可用。

P2 安全增量聚焦「JWT 网关认证 + 可信 header + 审计落库」，沿用 P1 的宽松处理（Shell `permissive`、Chromium `--no-sandbox`）。推迟项：Snapshot 编排、计量计费、React UI、SSO。全 TDD（Unit + Integration + 镜像 E2E），Orchestrator pytest 覆盖率 ≥80%。

## Technical Context

**Language/Version**: Python 3.12（Orchestrator + cap-agent/terminal/mcp 扩展），延续 P1 栈与 CLAUDE.md #8（uv + 3.12 + Type Hint + Async First）

**Primary Dependencies**:
- Web 框架：FastAPI + uvicorn[standard] + pydantic v2 + pydantic-settings（与 cap-agent 一致）
- 数据库：SQLAlchemy 2.x（async）+ asyncpg + Alembic（迁移）
- 认证：passlib[bcrypt]（密码哈希）+ PyJWT（签发/校验）
- CLI：typer（与 FastAPI 同生态，type hint 友好）
- HTTP 客户端：httpx（async，审计上报 + auth_request）
- 子进程：`asyncio.create_subprocess_exec` 调 `docker compose`（非 shell=True，避免注入）
- 测试：pytest + pytest-asyncio + httpx（ASGI Transport 直连）+ testcontainers-postgres（Integration）+ coverage

**Storage**: PostgreSQL 16（元数据 + 审计，单一数据库，§8.8.3）。无独立日志系统（审计入库 §8.8.6）。workspace Profile 仍走文件系统（P1 bind mount）。

**Testing**:
- Unit：pytest，纯函数/类（compose_runner mock subprocess、port_allocator、JWT/security、状态机），全 mock 下游，行覆盖率 ≥80%
- Integration：pytest + testcontainers-postgres（真实 PG，事务回滚隔离）+ docker compose 子进程用临时 project（`-p itest-{rand}`，测后 `down -v`）
- E2E：`make test-e2e-p2`，docker compose 起完整 stack（Orchestrator + postgres + ≥1 workspace），httpx 经 Orchestrator 验证 创建→登录→鉴权访问→审计落库；外加 P1 单 workspace 回归（SC-006 零迁移）

**Target Platform**: Linux x86_64 / arm64 主机，macOS 开发机。Docker 24+ + docker compose v2。PostgreSQL 16（docker compose 服务）。**`host.docker.internal` 需 Linux `host-gateway` 支持**（`extra_hosts`）。

**Project Type**: 多服务容器化平台的编排层（Orchestrator 独立 web-service + 对 P1 cap-* 的最小侵入扩展）

**Performance Goals**:
- 创建并启动一个新 workspace 到 healthy < 120s（SC-001，复用 P1 镜像）
- `auth_request` 子请求 < 200ms（SC-008）
- 审计上报额外开销 < 50ms（SC-004，best-effort 异步）
- Orchestrator API 常规端点 p95 < 100ms（不含 compose 子进程操作）

**Constraints**:
- 零代码迁移：P1 cap-agent 业务路由在 `AUTH_MODE=orchestrator` 下行为不变（FR-023 / SC-006）
- workspace 间网络隔离不可破坏（SC-005）
- 审计 best-effort：Orchestrator 不可达绝不阻塞业务命令（FR-018）
- 安全简化：Shell 仍 `permissive`、Chromium 仍 `--no-sandbox`（FR-NI-4/5）

**Scale/Scope**: 多 workspace（单机，目标并发 ≥3，SC-005）。Orchestrator 约 4-6K LOC（含测试）。不含 K8s（Phase 3，§8.8.5）。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

仓库无 `.specify/memory/constitution.md`。采用全局 CLAUDE.md（用户偏好）作为隐性 constitution，逐条核对：

| 原则 | 来源 | 本计划合规性 |
|------|------|--------------|
| 始终用中文 | CLAUDE.md #1 | ✅ 所有 spec/plan/tasks/contract/README 用中文 |
| 目标不清晰先讨论 | CLAUDE.md #1 | ✅ 范围经 AskUserQuestion 收敛 4 项关键决策；4 个技术点在 research 论证 |
| 最小化设计/改动 | CLAUDE.md #2 | ✅ 核心 MVP（砍 Snapshot/计量/UI/SSO）；Orchestrator 叠加不侵入 P1 业务代码 |
| Spec→Plan→Test→Code | CLAUDE.md #3 | ✅ speckit 工作流 + 全 TDD |
| 追根因不打补丁 | CLAUDE.md #2 | ✅ cap-agent 用 AuthMiddleware 抽象（P1 已为 P2 留接口位 §4.8.6），非临时 hack |
| Fail Fast | CLAUDE.md #2 | ✅ PostgreSQL 不可用 Orchestrator 启动期迁移失败即拒启动（Edge Case） |
| Python uv+3.12+TypeHint+Async | CLAUDE.md #8 | ✅ Orchestrator 全 async + asyncpg + async SQLAlchemy |
| 模块单职责/暴露协议 | CLAUDE.md #6 | ✅ Orchestrator 管"workspace 之间"，sandbox 管"之内"（§8.8.2 职责不重叠） |
| Explicit > Magic | CLAUDE.md #4 | ✅ `AUTH_MODE` 环境变量显式切换；可信 header 显式契约 |
| Unit→Integration→E2E | CLAUDE.md #5 | ✅ 三层全覆盖 + P1 回归 |

**结论**：通过 Constitution Check。范围已收敛至核心 MVP，无 Complexity Tracking 条目。

## Project Structure

### Documentation (this feature)

```text
specs/002-sandbox-p2-orchestrator/
├── spec.md              # 规格（已完成）
├── plan.md              # 本文件
├── research.md          # Phase 0：4 项技术决策论证 + 关键库选型
├── data-model.md        # Phase 1：PostgreSQL schema + Alembic 迁移 + 关键查询
├── quickstart.md        # Phase 1：端到端验证手册
├── contracts/           # Phase 1：对外契约
│   ├── orchestrator-rest-api.md       # workspace 生命周期 + user 认证 + audit（参考 §9.3）
│   ├── audit-ingest.md                # cap-* 审计上报契约（事件字段/endpoint/best-effort）
│   ├── trusted-headers.md             # X-User-Id/X-Workspace-Id/X-Permissions 约定
│   └── cap-agent-auth-middleware.md   # AUTH_MODE none/orchestrator 双模式契约
└── tasks.md             # Phase 2：任务列表（/speckit-tasks）
```

### Source Code (repository root)

```text
sandbox/                                  # 仓库根（P2 在 P1 基础上新增 orchestrator/ + 扩展 cap-*）
├── orchestrator/                         # 【新增】Orchestrator 编排层
│   ├── Dockerfile                        # multi-stage (FROM base-python312), target test/prod
│   ├── pyproject.toml                    # uv 管理
│   ├── alembic.ini
│   ├── migrations/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 0001_init.py              # users/workspaces/workspace_owners/templates/audit_logs
│   ├── src/orchestrator/
│   │   ├── __init__.py
│   │   ├── main.py                       # FastAPI app + lifespan + router 注册
│   │   ├── core/
│   │   │   ├── config.py                 # pydantic-settings: DB/JWT/port range/fail mode/retention
│   │   │   ├── db.py                     # async SQLAlchemy engine + session
│   │   │   └── security.py               # passlib bcrypt + PyJWT 签发/校验
│   │   ├── models/                       # SQLAlchemy ORM
│   │   │   ├── user.py
│   │   │   ├── workspace.py
│   │   │   ├── workspace_owner.py
│   │   │   ├── template.py
│   │   │   └── audit_log.py
│   │   ├── schemas/                      # Pydantic v2 请求/响应
│   │   │   ├── auth.py
│   │   │   ├── workspace.py
│   │   │   └── audit.py
│   │   ├── routers/
│   │   │   ├── auth.py                   # /api/v1/auth/{register,login,refresh}
│   │   │   ├── workspaces.py             # /api/v1/workspaces CRUD + start/stop/pause/resume
│   │   │   ├── audit.py                  # /api/v1/audit/{ingest,query}
│   │   │   └── verify.py                 # /api/v1/verify (auth_request 目标) + /healthz + /readyz
│   │   ├── services/
│   │   │   ├── compose_runner.py         # docker compose -p 子进程封装（async, 无 shell=True）
│   │   │   ├── workspace_lifecycle.py    # 状态机 + 生命周期动作
│   │   │   ├── port_allocator.py         # 端口分配（WORKSPACE_PORT_START 递增）
│   │   │   └── audit_sink.py             # 审计写入入口（best-effort）
│   │   ├── deps.py                       # 依赖注入: get_current_user / require_workspace_owner
│   │   └── cli.py                        # typer CLI: workspace/user 子命令
│   └── tests/
│       ├── conftest.py                   # ASGI TestClient + testcontainers-postgres fixture
│       ├── unit/
│       │   ├── test_security.py          # JWT 签发/校验/过期、bcrypt
│       │   ├── test_port_allocator.py
│       │   ├── test_workspace_state_machine.py
│       │   └── test_compose_runner.py    # mock subprocess
│       └── integration/
│           ├── test_auth_flow.py         # 注册/登录/refresh/401/403
│           ├── test_workspace_lifecycle.py  # 真实 PG + 临时 compose project
│           └── test_audit_ingest.py
├── cap-agent/                            # 【扩展】P1 服务 + auth 中间件 + 审计上报
│   └── src/cap_agent/
│       ├── core/
│       │   └── auth.py                   # 【新增】AuthMiddleware（none/orchestrator）+ TrustedHeader 解析
│       ├── services/
│       │   └── audit_client.py           # 【新增】best-effort 审计上报 httpx client
│       └── ...（P1 路由 health/shell/gui/cdp 不变）
├── cap-mcp/                              # 【扩展】+ 审计上报（fs.write/browser.action）
│   └── src/cap_mcp/services/audit_client.py  # 【新增】
├── cap-terminal/                         # 【扩展】+ 审计上报（shell.exec）
│   └── src/cap_terminal/services/audit_client.py  # 【新增】
├── cap-nginx/                            # 【扩展】workspace 模板加 auth_request + trusted header 透传
│   ├── nginx.conf                        # P1（单 workspace，AUTH_MODE=none）
│   └── nginx.workspace.conf.tmpl         # 【新增】P2 workspace 模板（auth_request + header 透传）
├── docker-compose.orchestrator.yml       # 【新增】Orchestrator + postgres 服务
├── docker-compose.workspace.yml.tmpl     # 【新增】workspace 模板（参数化 WORKSPACE/PORT/AUTH_MODE/ORCHESTRATOR_URL）
├── docker-compose.yml                    # P1（保留，AUTH_MODE=none 回归用）
├── Makefile                              # 扩展: build-orchestrator / test-orchestrator / up-p2 / test-e2e-p2
├── .env.example                          # 扩展: ORCH_PORT/DB/JWT/PORT_START/RETENTION/AUTH_FAILURE_MODE
└── tests/
    └── e2e/
        ├── test_p2_full_flow.py          # 【新增】创建→登录→鉴权→shell_exec→审计
        ├── test_p2_isolation.py          # 【新增】≥3 workspace 互隔离
        └── test_p1_regression.py         # 【新增】P1 AUTH_MODE=none 零迁移回归
```

**Structure Decision**：Orchestrator 作为仓库内独立的第 8 个服务项目（与 P1 七个 cap-* 并列，独立 `pyproject.toml` + `Dockerfile` + Alembic），延续 P1 的 monorepo + 单服务单职责约定。理由：
1. 与 cap-* 同构（都是独立 Python 项目 + Dockerfile），构建/测试流程统一
2. Orchestrator 与 workspace 通过 HTTP 契约（auth_request + audit ingest）解耦，无代码共享
3. 对 P1 cap-* 仅做"加法式"扩展（新增 auth.py / audit_client.py），不改动既有业务路由——零迁移

## Milestone 拆解

| Milestone | 内容 | 验证手段 | 预估任务数 |
|-----------|------|----------|------------|
| **M0** Orchestrator 骨架 + DB | pyproject + FastAPI app + SQLAlchemy 模型 + Alembic 初始迁移 + `/healthz` | `make test-orchestrator`（unit）全绿；Alembic upgrade 建表成功 | 8 |
| **M1** JWT 认证 | register/login/refresh + bcrypt + JWT 中间件 + deps（current_user） | integration: 401/403/200 全覆盖 | 6 |
| **M2** Workspace 元数据 CRUD | workspaces/workspace_owners/templates 表 + CRUD（无编排） | integration: 创建/列表/归属校验 | 6 |
| **M3** 编排引擎 | compose_runner（async subprocess）+ 状态机 + port_allocator + lifecycle 动作 | integration: 临时 compose project start/stop/pause/resume 真实跑通 | 8 |
| **M4** 鉴权穿透 | `/verify` 端点（auth_request 目标）+ 可信 header 注入 + nginx.workspace.conf.tmpl（auth_request + 透传） | integration: auth_request 2xx/401/fail-closed 分支 | 6 |
| **M5** cap-agent auth 中间件 | `AUTH_MODE=orchestrator` 的 OrchestratorHeaderAuthMiddleware + 与 none 共存 + audit_client 骨架 | unit: 双模式分支；P1 路由行为不变（SC-006 回归） | 6 |
| **M6** 审计落库 | audit ingest 端点 + audit_sink + 各 cap-*（terminal/mcp/agent）上报 + query 端点 | integration: shell.exec 落库 + 不可达不阻塞（SC-004） | 7 |
| **M7** CLI + OpenAPI | typer CLI（workspace/user）+ Swagger UI 校验 | e2e: 命令链 register→login→create→start→list（SC-007） | 5 |
| **M8** E2E + P1 回归 | test_p2_full_flow + test_p2_isolation + test_p1_regression + Makefile 集成 | `make test-e2e-p2` 全绿 | 6 |

**关键里程碑**：
- **M0 完成**：Orchestrator 可独立跑测 + DB 迁移可用（基础设施闭环）
- **M3 完成**：workspace 真实编排跑通（Orchestrator 灵魂 US1 可验证）
- **M4+M5 完成**：鉴权端到端穿透（US2/US3 闭环）
- **M8 完成**：P2 全栈交付 + P1 零迁移回归通过

## Risks

| 编号 | 风险 | 影响 | 缓解 |
|------|------|------|------|
| **R1** | `docker compose -p` 子进程在并发/异常下留下半启动容器 | 资源泄漏/状态漂移 | compose_runner 用 `--wait` + 捕获退出码；失败走 `down`；状态置 ERROR；提供 prune 清理 |
| **R2** | `host.docker.internal` 在 Linux 需 `host-gateway`（内核/版本差异） | 审计上报/auth_request 不通 | workspace 模板强制 `extra_hosts: host.docker.internal:host-gateway`；启动期连通性探活 |
| **R3** | nginx `auth_request` 对上游 5xx/超时默认返回 500，与 fail-closed 语义混淆 | 鉴权行为不符合预期 | 用 `error_page` + internal location 把 5xx/超时显式映射为 403（fail-closed）/ 放行（fail-open）；M4 专门测 |
| **R4** | 审计上报阻塞业务路径（同步 HTTP） | SC-004 不达标 | audit_client 用 fire-and-forget（`asyncio.create_task` + 有界队列 + 超时丢弃）；绝不 await 在请求关键路径 |
| **R5** | testcontainers-postgres 在 CI 慢/不可用 | Integration 测试不稳定 | 提供 SQLite-in-memory 降级（仅 schema 兼容部分）；JSONB 等不兼容用例标 skip + 依赖 testcontainers |
| **R6** | workspace 模板渲染（参数化 compose）易错 | 编排失败 | 用 env 插值（`docker compose --env-file`）而非字符串拼接；模板即真实 compose 文件，`docker compose config` 校验 |
| **R7** | JWT 密钥管理（开发/生产） | 安全 | 开发态随机生成并日志告警；生产强制 `JWT_SECRET_KEY` 环境变量，缺失拒启动 |
| **R8** | P1 cap-agent 无 auth 抽象占位（§4.8.6 设计了但 P1 可能未落地中间件层） | M5 需补抽象 | M5 起点先核对 P1 cap-agent 现状；若无中间件层，新增 `BaseAuthMiddleware` + 注册点，业务路由零改动 |

## Implementation Strategy

### TDD 三步循环（每个 milestone 内）
```
1. Red：写失败 test（unit 先，integration 次）—— contract/边界/异常分支
2. Green：最小实现通过——不引入未测依赖
3. Refactor：抽公共逻辑（compose_runner / audit_client 复用）
```

### 契约先行（contracts/ 作为 stub 起点）
- `orchestrator-rest-api.md` / `audit-ingest.md` / `trusted-headers.md` 先定 schema
- cap-* 的 audit_client 与 cap-agent auth 中间件可对 contract stub 单测先行
- Orchestrator 端点实现后跑跨服务 integration

### 复用 P1 习惯
- 镜像分层：`orchestrator` 基于 `base-python312`（与 cap-agent/terminal/mcp 同缓存链）
- multi-stage Dockerfile（test/prod target 共享，FR-027）
- Makefile 目标风格延续 P1（`build-orchestrator` / `test-orchestrator`）

### 安全简化边界（严守）
- Shell 策略：不实现（permissive）—— cap-terminal 不加 ShellPolicy
- Chromium：不启用 sandbox —— cap-browser entrypoint 保留 `--no-sandbox`
- P2 安全工作 = JWT 网关 + 可信 header + 审计，其余 P1 现状不变

## Phase 0 / Phase 1 / Phase 2 输出

详见同目录：
- `research.md` — Phase 0 输出（4 项技术决策论证 + JWT/Alembic/compose_runner/auth_request/audit 选型）
- `data-model.md` — Phase 1 输出（PostgreSQL schema + Alembic + 关键查询）
- `contracts/*.md` — Phase 1 输出（4 份契约）
- `quickstart.md` — Phase 1 输出（验证手册）
- `tasks.md` — Phase 2 输出（任务列表，下一步 `/speckit-tasks`）
