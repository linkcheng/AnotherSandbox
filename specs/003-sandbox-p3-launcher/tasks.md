# Tasks: AI 个人沙箱 P3 — React 启动器与 SSO/OAuth

**Input**: Design documents from `/specs/003-sandbox-p3-launcher/`

**Prerequisites**: plan.md（M0-M6 + 项目结构 + Constitution Check）、spec.md（US1-US5 + FR-001~032 + FR-NI-1~6 + SC-001~010）、research.md（R1-R9 决策）、data-model.md（oauth_accounts + users 扩展 + Alembic 0002）、contracts/（3 份）、quickstart.md（8 场景）

**Tests**: 全 TDD（CLAUDE.md #5 + spec FR-028~032）。每个 feature 先写失败的 test（Red）再实现（Green）。前端 vitest + msw，后端 pytest + testcontainers，跨服务 pytest E2E。

**Organization**: 按 spec 的 US1-US5 优先级组织（实现顺序按依赖：Setup → Foundational → US1 OAuth → US2 列表/向导 → US3 真实启动+统一访问 → US4 监控 → US5 部署反代 → Polish）。每个 US 可独立验证。

## Format: `[ID] [P?] [US?] 描述，含 file path`

- **[P]**: 可并行（不同文件、无依赖）
- **[US#]**: user story 归属（仅 US 阶段；Setup/Foundational/Polish 不标）
- 每个任务含具体 file path（参照 plan.md §Project Structure）
- TDD：先 test（Red）再 impl（Green）；测试任务标注 `[test-unit/integration/e2e]`
- 追溯：任务描述末尾标 FR/SC（如 `(FR-004, SC-001)`）

## Path Conventions

- **launcher/**：新增 React 项目（Vite + React 19 + TS + shadcn/ui + tailwind + react-router + react-query + vitest + msw），容器内 nginx 托管 SPA + 反代。
- **orchestrator/**：P2 项目扩展（新增 `routers/oauth.py` / `models/oauth_account.py` / `services/oauth_*` / `migrations/0002_oauth.py`），P2 既有代码零改动。
- **cap-nginx/**：扩展模板（Phase 5 auth_request 落地 + launcher 反代配置）。
- 根：`docker-compose.orchestrator.yml` / `Makefile` / `.env.example` 扩展；`tests/e2e/` 跨服务 E2E。

---

## Phase 1: Setup（共享基础设施）

**Goal**: launcher 项目骨架 + orchestrator OAuth 依赖 + Makefile/.env 扩展。
**对应 milestone**: plan M0（部分）

- [ ] T001 [P] 编写 `launcher/package.json`：依赖 react@19 / react-dom@19 / react-router-dom / @tanstack/react-query / tailwindcss / class-variance-authority / clsx / tailwind-merge / lucide-react / @radix-ui/*（shadcn 底座）；dev 依赖 vite / @vitejs/plugin-react / typescript / vitest / @testing-library/react / jsdom / msw / @types/react（R8）
- [ ] T002 [P] 创建 launcher 脚手架：`vite.config.ts`（含 test 环境 jsdom）/ `tsconfig.json`（strict）/ `tailwind.config.js` / `postcss.config.js` / `index.html` / `src/main.tsx`（React 19 入口 + QueryClientProvider + BrowserRouter）
- [ ] T003 [P] 初始化 `launcher/components.json` + `src/lib/utils.ts`（cn）+ shadcn 基础组件（button/input/label/card/dialog/table/badge/sonner 或 toast/select）— R8
- [ ] T004 [P] 扩展 `orchestrator/pyproject.toml`：新增依赖 `authlib`（OAuth client，R1）；dev 依赖不变
- [ ] T005 [P] 扩展根 `.env.example`：新增 `OAUTH_GITHUB_CLIENT_ID/SECRET`、`OAUTH_GOOGLE_CLIENT_ID/SECRET`、`OAUTH_REDIRECT_URL=http://localhost:8080/api/v1/auth/oauth`、`OAUTH_MOCK=true`、`LAUNCHER_PORT=8080`（R9）
- [ ] T006 扩展根 `Makefile`：目标 `build-launcher`、`up-p3`、`stop-p3`、`test-launcher`、`test-e2e-p3`
- [ ] T007 [P] 编写 `launcher/Dockerfile`：multi-stage（`node:24` 构建产物 → `nginx` 托管 + 反代），target 同 P2 风格
- [ ] T008 [P] 编写 `launcher/nginx/launcher.conf.tmpl` 骨架：SPA 托管（`try_files $uri /index.html`）+ `/api/ → orchestrator:8000` 反代（R5）
- [ ] T009 [P] 编写 `launcher/vitest.config`（或并入 vite.config）+ `tests/msw/handlers.ts` 骨架 + `tests/setup.ts`

**Checkpoint**: `cd launcher && npm install && npm run build` 产物可起；`make build-launcher` 镜像可构建。

---

## Phase 2: Foundational（阻塞前置 — OAuth 数据模型 + 前端 API client）

**Goal**: oauth_accounts 表 + Alembic 0002 + 前端 API client/类型骨架。**⚠️ 阻塞所有 US**。
**对应 milestone**: plan M0/M1 数据层

- [ ] T010 [test-unit] `orchestrator/tests/unit/test_oauth_account_model.py`：断言 OAuthAccount 字段/约束（provider CHECK、UNIQUE(provider,provider_user_id)、FK cascade）— data-model §2.1 `(FR-003)`
- [ ] T011 [P] 实现 `orchestrator/src/orchestrator/models/oauth_account.py`：OAuthAccount ORM（id/provider/provider_user_id/user_id/email/raw_profile JSONB/created_at + 唯一约束 + 索引）— data-model §2.1
- [ ] T012 [P] 扩展 `orchestrator/src/orchestrator/models/user.py`：增 nullable 列 `display_name` / `avatar_url`（P2 字段不变）— data-model §2.2
- [ ] T013 [P] 实现 `orchestrator/src/orchestrator/schemas/oauth.py`：Pydantic `OAuthAccountOut`（provider/email/created_at）/ `OAuthAccountsResponse`
- [ ] T014 [P] 扩展 `orchestrator/src/orchestrator/core/config.py`：Settings 增 `oauth_github_client_id/secret` / `oauth_google_client_id/secret` / `oauth_redirect_url` / `oauth_mock`（bool）— R9
- [ ] T015 生成 `orchestrator/migrations/versions/0002_oauth.py`：`CREATE TABLE oauth_accounts`（CHECK/UNIQUE/索引）+ `ALTER TABLE users ADD COLUMN display_name/avatar_url`，`down_revision="0001"` — data-model §4
- [ ] T016 [test-integration] `orchestrator/tests/integration/test_migration_oauth.py`：testcontainers-postgres 验证 `0001→0002` upgrade 建表 + 增列 / `downgrade` 回退幂等 + 唯一约束生效 `(FR-026)`
- [ ] T017 [P] 实现 `launcher/src/types/index.ts`：TS 类型（Provider/User/OAuthAccount/Workspace/WorkspaceStatus/Role/AuditEvent/AuditType/Page/ApiError）— frontend-api-contract §2
- [ ] T018 [P] 实现 `launcher/src/api/client.ts`：fetch wrapper（baseURL `/api/v1`、`credentials:"include"`、`X-Requested-With` 头、JSON 解析、非 2xx 抛 ApiError）+ 401 refresh 拦截重试 + refresh 失败重定向 `/login` `(FR-013, R3)`

**Checkpoint**: `make test-orchestrator` 含 OAuth 模型/迁移用例全绿；launcher `npm run build` 通过。

---

## Phase 3: US1 — OAuth 社交登录（GitHub/Google）

**Story Goal**: 用户经 GitHub/Google OAuth 登录，orchestrator 建户/邮箱合并并签发等价 JWT，launcher 进入工作台。
**Independent Test**: OAuth 登录闭环（mock）→ 获 JWT cookie → 可访问受保护页；伪造回调拒绝。
**对应 milestone**: plan M1（后端）+ M2 登录部分

- [ ] T019 [US1] [test-unit] `orchestrator/tests/unit/test_oauth_provider.py`：mock IdP（httpx mock/respx）验证 GitHub/Google authorize_url 构造（state+PKCE）/ token 交换 / userinfo 解析；OAUTH_MOCK 返回预设 userinfo `(FR-001, R1/R9)`
- [ ] T020 [US1] [P] 实现 `orchestrator/src/orchestrator/services/oauth_provider.py`：authlib 封装 GitHub/Google（authorize_url/token/userinfo）+ `OAuthProviderMock`（OAUTH_MOCK=true 时返回固定 userinfo，走真实建户/签 JWT 路径）— R1/R9
- [ ] T021 [US1] [test-unit] `orchestrator/tests/unit/test_oauth_linker.py`：覆盖 ① 已绑定→复用 user_id ② 邮箱命中→合并 ③ 全新→建户（password_hash NULL）④ 并发唯一约束冲突→回查 `(FR-002/003, SC-006, R2)`
- [ ] T022 [US1] [P] 实现 `orchestrator/src/orchestrator/services/oauth_linker.py`：按 `(provider,provider_user_id)`→email 合并→建户/绑定，调 P2 `security.create_tokens()` 签等价 JWT — data-model §3, R2
- [ ] T023 [US1] [test-integration] `orchestrator/tests/integration/test_oauth_flow.py`：testcontainers-pg + mock provider，验证 `/login`→`/callback` 闭环（Set-Cookie access/refresh + 302）、state 不匹配 400、code 失效 401、`/accounts`/`/bind`/`/unbind` 鉴权与 409 `(FR-004/005/006, SC-006)`
- [ ] T024 [US1] 实现 `orchestrator/src/orchestrator/routers/oauth.py`：5 端点（`GET /auth/oauth/{p}/login`、`GET /auth/oauth/{p}/callback`、`GET /auth/oauth/accounts`、`POST /auth/oauth/{p}/bind`、`DELETE /auth/oauth/{p}/unbind`）— oauth-rest-api 契约；main.py 注册 router
- [ ] T025 [US1] [P] 扩展 `orchestrator/src/orchestrator/routers/auth.py`：`/login` 与 `/refresh` 成功响应**额外 Set-Cookie**（HttpOnly+Secure+SameSite=Lax，access Max-Age=900 / refresh Max-Age=604800），JSON body 不变（CLI 兼容）`(FR-002, R3)`
- [ ] T026 [US1] [P] 扩展 `orchestrator/src/orchestrator/routers/me.py`（或并入现有）：`GET /api/v1/me` 返回当前用户（含 display_name/avatar_url）— frontend-api-contract §1
- [ ] T027 [US1] [test-unit] `launcher/tests/unit/Login.test.tsx`：msw mock `/api/v1/auth/login` 成功 + OAuth 按钮 `window.location` 跳转断言 + `?error=` 展示 `(FR-008/014)`
- [ ] T028 [US1] 实现 `launcher/src/pages/Login.tsx`：本地登录表单（email/password）+ 「GitHub 登录」「Google 登录」按钮（`window.location.href=/api/v1/auth/oauth/{p}/login`）+ OAuth error 展示 — R3
- [ ] T029 [US1] [P] 实现 `launcher/src/hooks/useSession.ts`：`useCurrentUser()`（react-query，失败=未登录）+ 会话失效处理
- [ ] T030 [US1] 实现 `launcher/src/App.tsx`：路由（`/login` 公开；`/`、`/workspaces`、`/create`、`/monitor`、`/ws/...` 受保护，未登录重定向 `/login`）+ OAuth 回流 `?error` 处理 `(FR-013)`

**Checkpoint**: `OAUTH_MOCK=true` 时浏览器点「GitHub 登录」→ 闭环进入工作台；伪造回调被拒（quickstart 场景 2）。

---

## Phase 4: US2 — Workspace 列表与创建向导

**Story Goal**: 登录后查看 workspace 列表并经向导创建。
**Independent Test**: 列表展示自己的 workspace；向导提交合法 workspace 后列表出现。
**对应 milestone**: plan M2

- [ ] T031 [US2] [P] 实现 `launcher/src/api/workspaces.ts`：react-query hooks（useWorkspaces 5s 轮询 / useWorkspace / useCreateWorkspace / useWorkspaceAction / useDeleteWorkspace，invalidate 策略）— frontend-api-contract §3
- [ ] T032 [US2] [test-unit] `launcher/tests/unit/lib/workspace.test.ts`：slug 校验纯函数（格式/长度/URL-safe/冲突预检 flag）+ status→badge 映射
- [ ] T033 [US2] [P] 实现 `launcher/src/lib/workspace.ts`：纯函数（validateSlug / statusToVariant / 不可变更新 helper）— 函数式
- [ ] T034 [US2] [test-unit] `launcher/tests/unit/Workspaces.test.tsx`：msw mock 列表 + 状态展示 + 启动/停止 mutation + 乐观更新 + 越权不显示他人 `(FR-009/011, SC-002)`
- [ ] T035 [US2] 实现 `launcher/src/pages/Workspaces.tsx`：列表（WorkspaceCard：name/slug/status badge/port/role/创建时间 + 启动/停止/暂停/恢复/删除/打开 操作，按 status 禁用非法转换）
- [ ] T036 [US2] [test-unit] `launcher/tests/unit/CreateWizard.test.tsx`：步骤流转（模板→slug→确认）+ 校验拦截非法 slug + 提交成功 invalidate `(FR-010, SC-002)`
- [ ] T037 [US2] 实现 `launcher/src/pages/CreateWizard.tsx`：多步向导（模板选择 minimal / slug 填写+实时校验 / 确认 / 提交 useCreateWorkspace）— shadcn 表单
- [ ] T038 [US2] [P] 实现 `launcher/src/components/WorkspaceCard.tsx` + `StatusBadge.tsx`（shadcn 组合）

**Checkpoint**: 登录后列表正确；向导创建 workspace 后列表 < 3s 出现（quickstart 场景 3）。

---

## Phase 5: US3 — Workspace 真实启动与统一入口访问

**Story Goal**: 真实拉起 workspace 容器组，经 launcher 统一入口访问其 UI。
**Independent Test**: 启动→healthy；经 `/ws/{slug}/` 访问 UI；越权/fail-closed 拒绝。
**对应 milestone**: plan M3（部署补齐）+ M4（反代访问）

- [ ] T039 [US3] [P] 扩展 `orchestrator/Dockerfile`：prod 阶段装 docker compose v2 静态二进制（固定版本 pin）— R4
- [ ] T040 [US3] 扩展 `docker-compose.orchestrator.yml`：orchestrator 挂载 `/var/run/docker.sock` + workspace compose 模板与仓库根挂载（`WORKSPACE_COMPOSE_CWD`）+ env `WORKSPACE_VOLUME_ROOT`；保留 cap_drop/no-new-privileges（R4 安全）
- [ ] T041 [US3] [test-unit] `orchestrator/tests/unit/test_workspace_lifecycle_error.py`：compose up 失败（端口耗尽/镜像缺失/返回非 0）→ status=error + error_message 保留 `(FR-018, SC-003)`
- [ ] T042 [US3] 扩展 `orchestrator/src/orchestrator/services/workspace_lifecycle.py`：start 失败捕获 → status=`error` + 写 `error_message`（workspaces 增列或复用字段）— FR-018；compose_runner 零改动（FR-019）
- [ ] T043 [US3] [P] 扩展 `docker-compose.workspace.yml.tmpl`：cap-nginx `container_name: ${WORKSPACE_SLUG}-cap-nginx`（R5 方案A 命名约定）+ 挂载渲染后 auth_request 配置 + 加入与 launcher 共享网络
- [ ] T044 [US3] [P] 落地 `cap-nginx/nginx.workspace.conf.tmpl` Phase 5：`auth_request /_auth → ${ORCHESTRATOR_URL}/api/v1/verify` + `auth_request_set` 可信 header + `error_page 401 403` fail-closed（envsubst 渲染）— R6, P2 trusted-headers
- [ ] T045 [US3] 扩展 `launcher/nginx/launcher.conf.tmpl`：`location /ws/<slug>/`（`auth_request /_authsub`→orchestrator verify + `auth_request_set` 捕获 + `proxy_pass http://$slug-cap-nginx:80` + `resolver 127.0.0.11` + WebSocket Upgrade/Connection 透传 + `proxy_read_timeout 3600s` + `proxy_buffering off` + `error_page` 降级）— R5, launcher-workspace-proxy 契约
- [ ] T046 [US3] [test-integration] `orchestrator/tests/integration/test_real_start.py`：orchestrator 容器内真实 `docker compose -p itest-{rand} up` 拉起 1 workspace 到 cap-nginx healthy（需 Docker socket，CI/本地）`(FR-016/017, SC-003)`
- [ ] T047 [US3] [P] 扩展 `orchestrator/src/orchestrator/schemas/workspace.py`：Workspace 响应含 `error_message`（nullable，FR-018）；launcher types 对齐
- [ ] T048 [US3] [P] 编写 `launcher/nginx/workspace-denied.html`（越权/未启动/不可达的可读降级页，FR-024）

**Checkpoint**: 启动 workspace → 真实容器组 healthy；`/ws/{slug}/` 经鉴权加载桌面 UI；越权 403（quickstart 场景 4/5/6）。

---

## Phase 6: US4 — 监控面板（状态 + 审计）

**Story Goal**: 查看 workspace 运行状态 + 审计事件流，筛选与分页。
**Independent Test**: 触发操作后审计流可见；状态变更反映。
**对应 milestone**: plan M5

- [ ] T049 [US4] [P] 实现 `launcher/src/api/audit.ts`：`useAuditEvents(wsId, page)`（react-query，10s 轮询 refetchInterval，分页）— frontend-api-contract §3, R7
- [ ] T050 [US4] [test-unit] `launcher/tests/unit/Monitor.test.tsx`：msw mock 审计列表 + workspace 筛选切换 + 分页 + 状态展示 `(FR-012, SC-005)`
- [ ] T051 [US4] 实现 `launcher/src/pages/Monitor.tsx`：workspace 选择器 + 状态卡 + AuditTable（type/actor/时间/摘要，按时间倒序）+ 分页 + 10s 轮询
- [ ] T052 [US4] [P] 实现 `launcher/src/components/AuditTable.tsx`（shadcn Table + type 徽标 + 空态/错误态）

**Checkpoint**: workspace 内触发操作后，监控面板审计流可见（quickstart 场景 7）。

---

## Phase 7: US5 — 启动器部署与统一反代拓扑

**Story Goal**: launcher 独立部署，单一入口管理+访问所有 workspace。
**Independent Test**: 单域名未登录→登录页；登录后经路径访问任意已启动 workspace。
**对应 milestone**: plan M0（部署）+ M4（拓扑验证）

- [ ] T053 [US5] [P] 完善 `docker-compose.orchestrator.yml` launcher 服务：build `./launcher`、`${LAUNCHER_PORT}:80`、env `ORCH_URL`、`orchestrator-net` 网络、healthcheck（`/` 200）、depends_on orchestrator
- [ ] T054 [US5] [test-e2e] `tests/e2e/test_p3_launcher_proxy.py`：起 stack（orchestrator+postgres+launcher+1 workspace），验证 launcher `/` 登录页、`/api` 反代 orchestrator、`/ws/{slug}/` 统一入口鉴权访问、越权 403、停 orchestrator fail-closed `(FR-020~024, SC-004/009/010)`
- [ ] T055 [US5] [P] 验证三服务网络互通 + launcher nginx resolver 动态解析 workspace 容器名（R5 方案A）+ 健康检查编排

**Checkpoint**: `make up-p3` 后单域名完整可用（quickstart 场景 1/5/6）。

---

## Phase 8: Polish（E2E + 回归 + 文档）

**Goal**: 端到端全链路 + P1/P2 零迁移回归 + 文档/安全声明。
**对应 milestone**: plan M6

- [ ] T056 [test-e2e] `tests/e2e/test_p3_oauth_flow.py`：OAuth 登录→建户/邮箱合并→JWT 等价（复用本地账户鉴权链路）→审计 actor 正确 `(FR-001~007, SC-001/006)`
- [ ] T057 [test-e2e] `tests/e2e/test_p3_real_start.py`：OAuth 登录→创建→真实启动 healthy→统一入口访问 UI→触发操作→审计落库 全链路 `(FR-016/017/030, SC-003/004)`
- [ ] T058 [test-e2e] `tests/e2e/test_p1p2_regression.py`：P1 单 workspace（AUTH_MODE=none）+ P2 编排/认证/审计 E2E 在 `0002_oauth` 迁移后全绿 `(FR-025/026/027/032, SC-008)`
- [ ] T059 完善 Makefile `test-e2e-p3`：`make build && build-orchestrator && build-launcher` → `up-p3` → 跑 test_p3_* + test_p1p2_regression → `stop-p3`
- [ ] T060 [P] 更新 `README.md`：P3 阶段声明 + 目录加 launcher/ + 三阶段架构表 + P3 快速开始（launcher/OAuth/真实启动）+ 测试表加 launcher + 安全声明增 docker.sock 挂载风险
- [ ] T061 [P] 扩展 `docs/architecture.md`：P3 部分（launcher 入口层 + OAuth 身份扩展 + orchestrator-as-controller + 统一反代拓扑图）

---

## Dependencies（US 完成顺序）

```
Phase 1 Setup ──► Phase 2 Foundational（阻塞所有 US）
                        │
                        ├──► US1 OAuth（无依赖，可首发）
                        │       │
                        │       ▼
                        ├──► US2 列表/向导（依赖 client 骨架，US1 登录后才有会话）
                        │
                        ├──► US3 真实启动+统一访问（依赖 US1 会话 + US2 workspace）
                        │       │
                        │       ▼
                        ├──► US4 监控（依赖 US1 会话 + workspace 存在）
                        │
                        └──► US5 部署反代（依赖 US3 反代配置，验证拓扑）
                                │
                                ▼
                          Phase 8 Polish（E2E + 回归）
```

## Parallel Opportunities

- Phase 1：T001-T009 几乎全 [P]（launcher 骨架 / orchestrator 依赖 / Makefile / .env 独立文件）
- Phase 2：T011-T018 多数 [P]（model/schema/config/类型/client 独立）
- US1：T020 provider / T022 linker 可与前端 T028/T030 并行（前后端对契约）
- US2：T031 api hooks / T033 lib 纯函数 / T038 组件 [P]

## MVP Scope

**MVP = Phase 1 + Phase 2 + US1（OAuth 登录闭环，mock 模式）**。交付后即可演示「OAuth 登录 → 进入工作台」，是 P3 区别于 P2 的用户面入口（SC-001/006）。后续 US2-US5 增量交付。

## Implementation Strategy

- **契约先行**：contracts/ 3 份已定，前后端对同一契约并行实现（T024 oauth router ↔ T028 Login；T031 workspaces hooks ↔ P2 既有端点）。
- **复用 P2 内核**：OAuth 签发调 P2 `security.create_tokens()`；launcher auth_request 复用 P2 `/verify`；compose_runner 零改动（FR-019）。
- **TDD**：每个 US 先写 test（mock IdP / msw / testcontainers）再实现；前端组件 vitest+msw，后端 pytest，跨服务 E2E。
- **安全边界**：docker.sock 挂载（US3）是唯一新提权面，cap_drop + 单机受信 + 记入安全声明（R4）；OAuth 凭证仅后端 env（FR-007）；HttpOnly cookie（R3）。
