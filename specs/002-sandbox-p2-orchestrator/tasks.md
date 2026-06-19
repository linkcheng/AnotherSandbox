# Tasks: AI 个人沙箱 P2 — Orchestrator 编排与认证层

**Input**: Design documents from `/specs/002-sandbox-p2-orchestrator/`

**Prerequisites**: plan.md（M0-M8 + 项目结构）、spec.md（US1-US5 + FR-001~027 + FR-NI-1~6 + SC-001~008）、research.md（R1-R9 决策）、data-model.md（6 表 + Alembic）、contracts/（4 份）、quickstart.md（8 场景）

**Tests**: 全 TDD。每个 feature 先写失败的 test（Red），再写实现（Green）。覆盖 Unit + Integration + 镜像 E2E 三层。

**Organization**: 按 plan.md 的 M0-M8 milestone 组织，进一步归入 5 个 User Story（实现顺序按依赖：US2 认证 → US1 编排 → US3 鉴权穿透 → US4 审计 → US5 CLI）。每个 US 可独立验证。

## Format: `[ID] [P?] [US?] 描述，含 file path`

- **[P]**: 可并行（不同文件、无依赖）
- **[US#]**: user story 归属（仅 US 阶段需要；Setup/Foundational/Polish 不标）
- 每个任务含具体 file path（参照 plan.md §Project Structure）
- TDD：先 test（Red）再 impl（Green）；测试任务标注 [test-unit/integration/contract/e2e]
- 追溯：任务描述末尾标 FR/SC（如 `(FR-004, SC-001)`）

## Path Conventions

Orchestrator 为独立 Python 项目 `orchestrator/`（`pyproject.toml` + `Dockerfile` + Alembic），延续 P1 约定（uv + Python 3.12 + async）。对 P1 cap-* 仅加法式扩展（新增文件为主，不改业务路由）。顶层 `tests/e2e/` 跨服务 E2E。

---

## Phase 1: Setup（共享基础设施）

**Goal**: Orchestrator 项目骨架 + 编排 compose 模板 + Makefile/.env 扩展。

**对应 milestone**: plan M0（部分）

- [ ] T001 [P] 编写 `orchestrator/pyproject.toml`：依赖 fastapi、uvicorn[standard]、pydantic v2、pydantic-settings、sqlalchemy[asyncio]、asyncpg、alembic、pyjwt、"passlib[bcrypt]"、typer、httpx；dev 依赖 pytest、pytest-asyncio、httpx、testcontainers[postgres]、coverage、respx
- [ ] T002 [P] 创建 `orchestrator/src/orchestrator/__init__.py` 与子包骨架目录 `core/` `models/` `schemas/` `routers/` `services/`（仅 `__init__.py`）
- [ ] T003 [P] 扩展根 `.env.example`：新增 `ORCH_PORT=8000`、`DATABASE_URL=postgresql+asyncpg://...`、`JWT_SECRET_KEY=`、`JWT_ALG=HS256`、`ACCESS_TOKEN_TTL_MIN=15`、`REFRESH_TOKEN_TTL_DAYS=7`、`WORKSPACE_PORT_START=8100`、`WORKSPACE_PORT_END=8199`、`WORKSPACE_RETENTION_DAYS=7`、`AUTH_FAILURE_MODE=fail-closed`（R1/R2/R4）
- [ ] T004 [P] 编写 `docker-compose.orchestrator.yml`：`orchestrator-net` bridge + `postgres:16` 服务 + `orchestrator` 服务（publish `${ORCH_PORT}:8000`，depends_on postgres healthcheck）
- [ ] T005 [P] 编写 `docker-compose.workspace.yml.tmpl`：参数化 `${WORKSPACE_SLUG}` `${WS_NGINX_PORT}` `${AUTH_MODE}` `${ORCHESTRATOR_URL}` `${WORKSPACE_ID}` 的 7 个 cap-* 服务，所有容器加 `extra_hosts: ["host.docker.internal:host-gateway"]`（R3）；cap-nginx 用 `${WS_NGINX_PORT}:80`
- [ ] T006 扩展根 `Makefile`：目标 `build-orchestrator`、`up-orchestrator`、`stop-orchestrator`、`test-orchestrator`、`test-e2e-p2`（参照 P1 Makefile 风格）
- [ ] T007 [P] 编写 `orchestrator/.python-version`（3.12）与 `orchestrator/README.md` 骨架（开发流程/测试/配置项/CLI 占位）

**Checkpoint**: `make build-orchestrator` 可构建；项目骨架就绪。

---

## Phase 2: Foundational（阻塞前置 — DB + 模型 + Alembic + App）

**Goal**: SQLAlchemy 模型 + Alembic 初始迁移 + FastAPI app + `/healthz` `/readyz`。**⚠️ 阻塞所有 US**。

**对应 milestone**: plan M0

- [ ] T008 [P] [test-unit] `orchestrator/tests/unit/test_config.py`：断言 Settings 读取所有环境变量 + 合理默认（port_start=8100、retention=7、auth_failure_mode=fail-closed）；JWT_SECRET 缺失时开发态随机生成（R7）
- [ ] T009 [P] 实现 `orchestrator/src/orchestrator/core/config.py`：pydantic-settings Settings（含上述字段 + `orch_url`）+ `get_settings()` lru_cache
- [ ] T010 [P] 实现 `orchestrator/src/orchestrator/core/db.py`：async engine（create_async_engine）+ `async_sessionmaker` + `get_session()` 依赖（async generator）
- [ ] T011 [P] 实现 `orchestrator/src/orchestrator/models/base.py`：`DeclarativeBase`
- [ ] T012 [P] 实现 `orchestrator/src/orchestrator/models/user.py`：User（id UUID、email UNIQUE LOWER、password_hash、is_active、created_at、updated_at）— data-model §2.1
- [ ] T013 [P] 实现 `orchestrator/src/orchestrator/models/template.py`：Template（id、name UNIQUE、description、init_script、agents_md_seed、created_at）— §2.2
- [ ] T014 [P] 实现 `orchestrator/src/orchestrator/models/workspace.py`：Workspace（含 status CHECK、partial unique index `WHERE deleted_at IS NULL`）— §2.3
- [ ] T015 [P] 实现 `orchestrator/src/orchestrator/models/workspace_owner.py`：WorkspaceOwner（复合 PK、role CHECK、ON DELETE CASCADE）— §2.4
- [ ] T016 [P] 实现 `orchestrator/src/orchestrator/models/audit_log.py`：AuditLog（BIGSERIAL、JSONB detail、3 索引）— §2.5
- [ ] T017 [P] 实现 `orchestrator/src/orchestrator/models/refresh_token.py`：RefreshToken（token_hash UNIQUE、expires_at、revoked_at）— §2.6
- [ ] T018 编写 `orchestrator/alembic.ini` + `orchestrator/migrations/env.py`：async engine + `target_metadata = Base.metadata`（R6）
- [ ] T019 生成 `orchestrator/migrations/versions/0001_init.py`：6 表 + 全部索引 + `CREATE EXTENSION pgcrypto` + 种子 `minimal` 模板（data-model §4.1）
- [ ] T020 [test-integration] `orchestrator/tests/integration/test_migrations.py`：testcontainers-postgres 验证 `upgrade head` 建表 + `downgrade base`→`upgrade head` 往返幂等 + partial unique（两条同 port 一条 deleted 成功 / 均活跃报冲突）`(FR-007)`
- [ ] T021 实现 `orchestrator/src/orchestrator/main.py`：FastAPI app + lifespan（启动期 `alembic upgrade head`，失败 fail-fast）+ 注册 health router
- [ ] T022 [P] 实现 `orchestrator/src/orchestrator/routers/health.py`：`GET /healthz`（不查 DB → 200）+ `GET /readyz`（查 DB → 200/503）— contracts §4
- [ ] T023 [test-integration] `orchestrator/tests/integration/test_health.py`：`/healthz` 恒 200；`/readyz` DB 可达 200 / DB 断开 503
- [ ] T024 [P] 编写 `orchestrator/tests/conftest.py`：ASGI TestClient fixture + testcontainers-postgres fixture（每个测试事务回滚隔离）+ Settings override
- [ ] T025 [P] 编写 `orchestrator/Dockerfile`：multi-stage `FROM base-python312`，target `test`（含 dev 依赖）/`prod`（FR-027）
- [ ] T026 实现 Makefile `test-orchestrator`：`uv run pytest orchestrator/tests --cov=orchestrator --cov-fail-under=80`（SC-003）

**Checkpoint**: `make up-orchestrator` 后 `curl /readyz` → 200 db:ok；`make test-orchestrator` 全绿覆盖 ≥80%。

---

## Phase 3: User Story 2 — JWT 认证与归属 (Priority: Core)

**Goal**: 自建账户注册/登录/refresh + JWT 中间件 + `get_current_user` 依赖。**实现先于 US1，因其保护所有 workspace 端点。**

**Independent Test**: 无 token → 401；登录后带 token → 200；坏 token → 401。

**对应 milestone**: plan M1 · 关联 FR-010/011/015 · SC-002

- [ ] T027 [P] [test-unit] `orchestrator/tests/unit/test_security.py`：bcrypt hash/verify；JWT 签发（access/refresh type claim）/校验/过期拒绝/签名错误拒绝（R5）
- [ ] T028 [P] 实现 `orchestrator/src/orchestrator/core/security.py`：`hash_password`/`verify_password`（passlib bcrypt）+ `create_access_token`/`create_refresh_token`/`decode_token`（PyJWT HS256）
- [ ] T029 [P] 实现 `orchestrator/src/orchestrator/schemas/auth.py`：RegisterIn/LoginIn/TokenOut（access_token/refresh_token/expires_in）
- [ ] T030 [test-integration] `orchestrator/tests/integration/test_auth_flow.py`：register 201 / 409(重复 email)；login 200 / 401(错密码)；refresh 200 + 旧 token 吊销(rotation) / 401(过期/吊销)
- [ ] T031 实现 `orchestrator/src/orchestrator/routers/auth.py`：`POST /auth/register`、`/auth/login`、`/auth/refresh`（refresh rotation：吊销旧 token_hash、签发新对，写 refresh_tokens）
- [ ] T032 实现 `orchestrator/src/orchestrator/deps.py`：`get_current_user`（OAuth2PasswordBearer → decode JWT → 查 users → 注入 user；401 失败）
- [ ] T033 在 `main.py` 注册 auth router（register/login/refresh 为 public）
- [ ] T034 [test-integration] `orchestrator/tests/integration/test_protected_endpoint.py`：临时受保护路由无 token 401 / 坏 token 401 / 有效 token 200 `(SC-002)`

**Checkpoint**: 认证闭环可用；`get_current_user` 可被后续 router 复用。

---

## Phase 4: User Story 1 — Workspace 生命周期编排 (Priority: Core)

**Goal**: workspace 元数据 CRUD + 编排引擎（compose_runner + 状态机 + 端口分配）。Orchestrator 灵魂能力。

**Independent Test**: 创建 workspace → start（<120s running）→ stop；容器组随状态变化。

**对应 milestone**: plan M2（元数据）+ M3（编排）· 关联 FR-001~006 · SC-001/005

- [ ] T035 [P] 实现 `orchestrator/src/orchestrator/schemas/workspace.py`：WorkspaceCreateIn/WorkspaceOut（含 endpoints、status 枚举）
- [ ] T036 [P] [test-unit] `orchestrator/tests/unit/test_port_allocator.py`：最小可用端口返回；并发 IntegrityError 重试；范围耗尽报错；已占用端口跳过（R2，data-model §5.3）
- [ ] T037 [P] 实现 `orchestrator/src/orchestrator/services/port_allocator.py`：`generate_series` 查询最小可用端口 + 插入重试（捕获 IntegrityError）
- [ ] T038 [P] [test-unit] `orchestrator/tests/unit/test_workspace_state_machine.py`：合法转换（created→starting→running 等）；非法转换拒绝；start 幂等（已 running 返回当前态）— §8.5 / data-model §6
- [ ] T039 [P] 实现 `orchestrator/src/orchestrator/services/workspace_lifecycle.py`：状态机 + slug 生成（name slugify + 短随机后缀）+ volume_path 拼接 + 动作分发（调 compose_runner）
- [ ] T040 [test-unit] `orchestrator/tests/unit/test_compose_runner.py`：mock `create_subprocess_exec`，断言 argv（含 `-p {slug}`、`--env-file`、`--wait`）、退出码→状态映射（0→running / 非0→error）、**非 shell 调用**（R7）
- [ ] T041 实现 `orchestrator/src/orchestrator/services/compose_runner.py`：`asyncio.create_subprocess_exec` 封装 `up -d --wait` / `down -v` / `stop` / `pause` / `unpause` / `ps --format json`；env-file 用 env 插值渲染 workspace 模板（R6/R7）
- [ ] T042 [test-integration] `orchestrator/tests/integration/test_workspace_lifecycle.py`：真实 PG + 临时 compose project：create(201, port=8101) → list → get → start(<120s running, SC-001) → pause/resume → stop → delete(软删) `(SC-001)`
- [ ] T043 实现 `orchestrator/src/orchestrator/routers/workspaces.py`：`POST /workspaces`、`GET /workspaces`、`GET /workspaces/{id}`、`DELETE /workspaces/{id}?purge=`、`POST /workspaces/{id}/{start,stop,pause,resume}`；全部需 `get_current_user`
- [ ] T044 在 `deps.py` 加 `require_workspace_owner`：查 workspace_owners（data-model §5.2）→ 注入 workspace + role；无归属 403 `(SC-002)`
- [ ] T045 [P] 实现 `orchestrator/src/orchestrator/services/reaper.py`：后台周期任务（lifespan 启动）扫描 `deleted_at + WORKSPACE_RETENTION_DAYS < now` → `down -v` + 删卷目录 + 删 DB 行（R1 硬删）
- [ ] T046 在 `main.py` 注册 workspaces router + lifespan 启动 reaper

**Checkpoint**: 经 Orchestrator 创建→启动一个 workspace 到 healthy（SC-001）；越权访问 403（SC-002）。

---

## Phase 5: User Story 3 — nginx auth_request 网关鉴权与可信 Header 透传 (Priority: Core)

**Goal**: `/verify` 端点 + workspace nginx 模板（auth_request）+ cap-agent auth 中间件（双模式）。鉴权端到端穿透。

**Independent Test**: 经 cap-nginx + 合法 JWT 访问 workspace → 200 且 cap-agent 读到可信 header；越权 → 403；伪造/直连 → 401；fail-closed。

**对应 milestone**: plan M4（verify+nginx）+ M5（cap-agent auth）· 关联 FR-012/013/014/022/023 · SC-006/008

- [ ] T047 起点核对：读 P1 `cap-agent/src/cap_agent/main.py` 与 `core/`，确认是否已有中间件层（plan R8）；记录结论（影响 T053/T054 接入方式）
- [ ] T048 [test-unit] `orchestrator/tests/unit/test_verify.py`：`/verify` 合法 JWT+归属 → 200 + 响应 header X-User-Id/X-Workspace-Id/X-Permissions；无/坏 JWT → 401；越权 → 403；body 不消费（R8，contracts §3）
- [ ] T049 实现 `orchestrator/src/orchestrator/routers/verify.py`：`POST /api/v1/verify`（解析 Authorization + X-Workspace-Id → ownership 校验 → 回写可信 header，无 body）— contracts/trusted-headers
- [ ] T050 实现 `cap-nginx/nginx.workspace.conf.tmpl`：`auth_request /_auth` → `proxy_pass http://host.docker.internal:8000/api/v1/verify` + `auth_request_set` 捕获三 header + `proxy_set_header` 覆盖注入 + `error_page 5xx @auth_closed`(fail-closed，可切 fail-open)（R4/R8，contracts §2）
- [ ] T051 [test-contract] `cap-nginx/tests/test_workspace_template.py`：断言模板含 auth_request /_auth、auth_request_set 三 header、error_page fail-closed 分支；`docker compose -f <渲染后> config` 校验语法
- [ ] T052 [P] [test-unit] `cap-agent/tests/unit/test_auth.py`：`AUTH_MODE=none` 放行 + 空 Identity；`orchestrator` 三 header 齐全 → 200 + Identity 正确；缺一 header → 401；`/v1/health` 两模式均公开（contracts/cap-agent-auth-middleware §6）`(SC-006)`
- [ ] T053 [P] 实现 `cap-agent/src/cap_agent/core/auth.py`：`Identity` + `BaseAuthMiddleware`（PUBLIC_PATHS={"/v1/health"}）+ `NoAuthMiddleware` + `OrchestratorHeaderAuthMiddleware` + `build_auth_middleware(mode)`（contracts/cap-agent-auth-middleware §2/3）
- [ ] T054 修改 `cap-agent/src/cap_agent/main.py`：启动期读 `AUTH_MODE` 注册对应中间件（业务路由 health/shell/gui/cdp **不改**，零迁移，FR-023）
- [ ] T055 [test-e2e] `tests/e2e/test_auth_penetration.py`：workspace start → 经 cap-nginx auth_request 访问 `/v1/health`：合法 JWT 200 / 越权 403 / 伪造 header 401 / Orchestrator 关闭 fail-closed 403 `(SC-008)`

**Checkpoint**: 鉴权端到端穿透（US3 闭环）；P1 业务路由零改动可证（T052 none 模式）。

---

## Phase 6: User Story 4 — 操作审计落库 (Priority: Important)

**Goal**: audit ingest 端点 + 各 cap-* `audit_client.py`（fire-and-forget）+ query 端点。

**Independent Test**: shell.exec 后 audit_logs 有记录；Orchestrator 不可达时命令仍成功（best-effort）。

**对应 milestone**: plan M6 · 关联 FR-016/017/018/019 · SC-004

- [ ] T056 [P] 实现 `orchestrator/src/orchestrator/schemas/audit.py`：AuditIngestIn（workspace_id/actor_user_id?/event_type/source/detail/success）+ AuditOut
- [ ] T057 [test-integration] `orchestrator/tests/integration/test_audit_ingest.py`：ingest 201 写 audit_logs（字段正确）；非法 event_type/source 400；query 按 workspace/event_type/时间过滤（contracts/audit-ingest）
- [ ] T058 [P] 实现 `orchestrator/src/orchestrator/services/audit_sink.py`：写入 audit_logs + event_type/source 白名单校验（contracts/audit-ingest §2）
- [ ] T059 实现 `orchestrator/src/orchestrator/routers/audit.py`：`POST /audit/ingest`（workspace 内调用，public-from-trusted-network）+ `GET /audit`（需归属，data-model §5.4/5.5）
- [ ] T060 [test-unit] `cap-agent/tests/unit/test_audit_client.py`：mock httpx，断言 fire-and-forget（create_task 不阻塞）、timeout=2s、异常吞掉 log.warning、调用方不感知失败（R9，contracts/audit-ingest §4/5）
- [ ] T061 [P] 实现 `cap-agent/src/cap_agent/services/audit_client.py`：`AuditClient`（orch_url/workspace_id/source + `report()` fire-and-forget）
- [ ] T062 [P] 实现 `cap-terminal/src/cap_terminal/services/audit_client.py` 与 `cap-mcp/src/cap_mcp/services/audit_client.py`（同接口，source 分别为 cap-terminal/cap-mcp）
- [ ] T063 修改 `cap-terminal/src/cap_terminal/routers/exec.py`：`/api/v1/exec` 返回后 `audit_client.report("shell.exec", {command,exit_code,duration_ms}, actor=X-User-Id)`（contracts/audit-ingest §3/6）
- [ ] T064 [P] 修改 `cap-mcp/src/cap_mcp/tools/fs.py`（fs.write 上报）与 `tools/browser.py`（browser.action 上报）
- [ ] T065 [P] 修改 `cap-agent/src/cap_agent/routers/gui.py`：`/gui/actions` 返回后上报 gui.action
- [ ] T066 [test-e2e] `tests/e2e/test_audit_e2e.py`：经鉴权路径 shell_exec → audit_logs 出现 shell.exec 记录；停 Orchestrator 后再执行 shell_exec 仍 200（审计丢弃，业务不阻塞）`(SC-004)`

**Checkpoint**: 审计端到端落库 + best-effort 不阻塞（SC-004）。

---

## Phase 7: User Story 5 — Orchestrator CLI 与 OpenAPI 入口 (Priority: Important)

**Goal**: `orchestrator` typer CLI（workspace/user 子命令）+ Swagger UI 验证。

**Independent Test**: 命令链 `user register → login → workspace create → start → list` 全成功；`/docs` 列出全部端点。

**对应 milestone**: plan M7 · 关联 FR-020/021 · SC-007

- [ ] T067 [test-unit] `orchestrator/tests/unit/test_cli.py`：`workspace create/start/stop/list`、`user register/login`（mock httpx 调 REST）；token 本地存取（`~/.orchestrator/token`）
- [ ] T068 实现 `orchestrator/src/orchestrator/cli.py`：typer app，子命令调对应 REST 端点；登录后 token 存本地供后续命令用（contracts/orchestrator-rest-api §6）
- [ ] T069 [test-integration] `orchestrator/tests/integration/test_openapi.py`：`/openapi.json` 含全部端点（auth/workspaces/audit/verify/health）；`/docs` 返回 Swagger UI（FR-021）
- [ ] T070 在 `main.py` 确认 `/docs` `/openapi.json` 暴露（FastAPI 默认，仅核对 title/version）

**Checkpoint**: CLI 全生命周期可用（SC-007）；OpenAPI 文档完整（FR-021）。

---

## Phase 8: Polish & Cross-Cutting（E2E + 回归 + 文档 + 安全核对）

**Goal**: 完整 E2E（覆盖全部 SC）+ P1 零迁移回归 + 文档 + 安全 hardening 核对。

**对应 milestone**: plan M8 · 关联 FR-022/023/024~027 · SC-001~008

- [ ] T071 [P] 扩展 `tests/e2e/conftest.py`：orchestrator base_url fixture + workspace 创建/启停 fixture（复用 Orchestrator API）+ JWT 登录 fixture
- [ ] T072 [test-e2e] `tests/e2e/test_p2_full_flow.py`：注册→登录→创建→启动(<120s)→鉴权访问 /v1/health→shell_exec→审计落库 全链路 `(SC-001, SC-002)`
- [ ] T073 [test-e2e] `tests/e2e/test_p2_isolation.py`：≥3 workspace 并发，A 的文件/网络对 B/C 不可见 `(SC-005)`
- [ ] T074 [test-e2e] `tests/e2e/test_p1_regression.py`：`AUTH_MODE=none make up` + P1 `make test-e2e` 全绿，业务路由代码未改（零迁移）`(SC-006)`
- [ ] T075 实现 Makefile `test-e2e-p2`：`make up-orchestrator && pytest tests/e2e/test_p2_*`
- [ ] T076 [P] 完善 `orchestrator/README.md`：开发流程、`make test-orchestrator`、配置项、CLI 用法、与 P1 的关系（叠加层）
- [ ] T077 [P] 更新 `docs/architecture.md`：增 P2 Orchestrator 层章节（编排/元数据/认证/审计），引用 data-model.md 与 contracts/
- [ ] T078 SC 门禁核对：CLI ≤6 命令全生命周期（SC-007）；`make test-orchestrator` 覆盖率 ≥80%（SC-003）；全部 SC 有对应 E2E
- [ ] T079 [P] 安全 hardening 核对：`JWT_SECRET_KEY` 缺失生产态拒启动（R7）；`AUTH_MODE` 切换；`AUTH_FAILURE_MODE=fail-closed` 默认；workspace 容器 `cap_drop`/`no-new-privileges` 沿用 P1；Shell 仍 permissive、Chromium 仍 --no-sandbox（FR-NI-4/5 边界）

**Checkpoint**: `make test-e2e-p2` 全绿（SC-001~008 全覆盖）；P1 回归通过（SC-006）。

---

## Dependencies & Execution Order

### Phase 依赖

- **Phase 1 Setup**: 无依赖，立即开始
- **Phase 2 Foundational**: 依赖 Phase 1。**阻塞所有 US**
- **Phase 3 US2 认证**: 依赖 Foundational（users 表）。**先于 US1**（保护 workspace 端点）
- **Phase 4 US1 编排**: 依赖 Foundational（workspaces 表）+ US2（`get_current_user`/`require_workspace_owner`）
- **Phase 5 US3 鉴权穿透**: 依赖 US1（workspace 存在）+ US2（JWT/ownership）。**cap-agent auth 中间件独立于 Orchestrator 可单测**
- **Phase 6 US4 审计**: 依赖 US1（audit_logs 关联 workspace）+ US3（actor 从 X-User-Id）。Orchestrator 端与 cap-* 端可并行
- **Phase 7 US5 CLI**: 依赖 US1/US2（调用其端点）。OpenAPI 部分独立
- **Phase 8 Polish**: 依赖所有 US 完成

### 实现顺序说明（优先级 vs 依赖）

spec 中 US1/US2/US3 均为 Core（能力优先级），但**实现顺序按依赖**：US2（认证）先于 US1（编排）—— 因所有 workspace 端点需认证保护。这不改变能力优先级，仅是工程顺序。

### Phase 内部顺序

- Test（Red）→ Model/Schema → Service → Router（Green）→ Integration/E2E
- Orchestrator: models → alembic → services（compose_runner/lifecycle/port_allocator）→ routers
- cap-* 扩展：audit_client/auth 先行（独立单测），router 接入最后

### Parallel Opportunities

- Phase 1：T001/T003/T004/T005/T007 全部 [P]
- Phase 2：T008-T017（config/db/6 模型）多数 [P]；T022/T024/T025 [P]
- Phase 3：T027/T029 [P]
- Phase 4：T035/T036/T037、T038/T039 [P]
- Phase 5：cap-agent auth（T052/T053）与 Orchestrator verify（T048/T049）跨服务并行
- Phase 6：三个 cap-* 的 audit_client（T061/T062）并行；Orchestrator audit（T056/T058）与 cap-* 并行
- Phase 8：T071/T076/T077/T079 多数 [P]

---

## Parallel Example: Phase 2（Foundational 并行块）

```bash
# 6 个 ORM 模型可并行（不同文件、无依赖）
Task: "T012 models/user.py"
Task: "T013 models/template.py"
Task: "T014 models/workspace.py"
Task: "T015 models/workspace_owner.py"
Task: "T016 models/audit_log.py"
Task: "T017 models/refresh_token.py"
```

## Parallel Example: Phase 6（cap-* 审计客户端并行）

```bash
# 三个 cap-* 的 audit_client 接口相同，可并行实现
Task: "T061 cap-agent/services/audit_client.py"
Task: "T062 cap-terminal + cap-mcp services/audit_client.py"
```

---

## Implementation Strategy

### MVP First（认证 + 编排双核心闭环）

1. Phase 1 Setup → Orchestrator 骨架
2. Phase 2 Foundational → DB + 模型 + Alembic + `/healthz`
3. Phase 3 US2 → JWT 认证闭环（**MVP checkpoint 1**：register/login/受保护端点 401/200）
4. Phase 4 US1 → workspace 编排闭环（**MVP checkpoint 2**：创建→启动<120s→healthy，SC-001）
5. **STOP and VALIDATE**：`make test-orchestrator` + 关键 integration 全绿

### Incremental Delivery

1. Phase 1-2 → 基础设施就绪
2. +Phase 3 → 认证可用
3. +Phase 4 → 多租户编排可用（Orchestrator 核心）
4. +Phase 5 → 鉴权端到端穿透（P2 安全增量主体）
5. +Phase 6 → 审计可追溯
6. +Phase 7 → CLI/OpenAPI 入口
7. +Phase 8 → 全栈交付 + P1 回归

### Parallel Team Strategy

1. 团队共完成 Phase 1-2（基础设施，串行）
2. Foundational 完成后：
   - Dev A：Phase 4 US1（编排引擎，最重）
   - Dev B：Phase 5 US3 的 cap-agent auth（独立于 Orchestrator）
   - Dev C：Phase 6 US4 的 Orchestrator audit 端
3. Phase 3 US2 认证作为 Phase 4/5/6 的前置，优先完成
4. Phase 8 团队共同 review + E2E 收口

---

## Notes

- [P] = 不同文件、无依赖，可并行
- [US#] 映射 spec.md user story，便于追溯 FR/SC
- TDD 严格：先 test 后 impl；不允许"先写实现再补 test"
- 跨服务契约（contracts/）作为 stub-first 起点：cap-* 单测可对 contract mock 先行，Orchestrator 端点就绪后跑 integration
- **零迁移红线**：Phase 5 不得修改 P1 cap-agent 业务路由逻辑（health/shell/gui/cdp），仅新增 auth.py + main.py 注册中间件（T054）
- **安全简化边界**：全程不实现 Shell 策略（permissive）、不启用 Chromium sandbox（FR-NI-4/5）；P2 安全工作 = JWT 网关 + 可信 header + 审计
- 镜像分层：orchestrator 基于 base-python312（与 cap-agent 同缓存链）
- macOS 开发注意：`host.docker.internal` 内置；Linux 需 `host-gateway`（workspace 模板已配，R2/R3）
- 每个 checkpoint 后提交一次 git commit，便于回滚
