# Implementation Plan: AI 个人沙箱 P3 — React 启动器与 SSO/OAuth

**Branch**: `003-sandbox-p3-launcher` | **Date**: 2026-06-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-sandbox-p3-launcher/spec.md`

**Source**: `.archive/sandbox-design.md`（React 启动器 / SSO 相关章节）、P2 spec `FR-NI-3`/`FR-NI-6`（推迟项）、P2 已交付内核（compose_runner / JWT / auth_request / 审计）

## Summary

在 P1（单 workspace 全栈）+ P2（Orchestrator 编排 + JWT + 审计，已交付）之上，交付 P2 推迟的两项 + 补齐一项遗留，共 **4 块增量**：

1. **SSO/OAuth（GitHub + Google）**：在 orchestrator 内新增 OAuth 路由 + `oauth_accounts` 表 + provider client；与 P2 本地账户并存，登录成功签发**等价 P2 JWT**（复用 access/refresh 内核），前端统一以 JWT 调 API。邮箱自动合并。
2. **React 19 启动器**（`launcher/`，函数式 + shadcn/ui + tailwind）：workspace 列表 / 创建向导 / 监控面板三大视图 + 登录（本地 + OAuth）。
3. **补齐 workspace 真实启动部署闭环**：orchestrator 容器获得编排者身份（docker socket + CLI + workspace 模板挂载 + compose cwd），使 P2 已实现的 compose_runner 在容器内真实生效，「创建→启动→healthy→访问」端到端可用。
4. **Launcher 统一反代入口**：launcher 容器（nginx）对外单域名，托管 SPA + 反代 `/api→orchestrator` + 反代 `/ws/{slug}/→workspace cap-nginx`，鉴权经 orchestrator `auth_request` 注入可信 header。

P3 是**叠加层 + 补齐**：不改 P2 编排/JWT/auth_request/审计内核（FR-026），不改 P1 workspace 业务路由（FR-025），OAuth 与 launcher 为纯新增式扩展。安全沿用 P2（JWT 网关 + 可信 header + fail-closed + 审计）+ P1 宽松（Shell permissive、Chromium --no-sandbox）。全 TDD（前端 vitest + 后端 pytest + E2E），零迁移回归。

## Technical Context

**Language/Version**:
- 后端：Python 3.12（orchestrator OAuth 扩展，延续 P2 栈 + CLAUDE.md #8：uv + 3.12 + Type Hint + Async First）
- 前端：TypeScript 5.x + React 19（launcher，函数式：函数组件 + hooks + 不可变状态）
- 网关：nginx（launcher 反代 + workspace auth_request，延续 P2 cap-nginx）

**Primary Dependencies**:
- 后端新增：`authlib`（OAuth 2.0 client，Authorization Code + state + PKCE）+ `httpx`（IdP token/userinfo，复用 P2）；复用 P2 PyJWT（签发等价 JWT）/ bcrypt / SQLAlchemy 2.x async / asyncpg / Alembic
- 前端：React 19 + Vite（构建）+ TypeScript + `shadcn/ui`（组件，Radix 底座）+ `tailwind css`（样式）+ `react-router`（路由）+ `@tanstack/react-query`（数据获取/缓存/轮询，函数式）+ 原生 fetch（API client）
- 前端测试：`vitest` + `@testing-library/react`（组件）+ `msw`（API mock）
- E2E：pytest + httpx（沿用 P2，launcher/反代用 httpx + 真实 compose stack）

**Storage**: PostgreSQL 16（P2 库扩展：新增 `oauth_accounts` 表 + `users` 增列 `display_name`/`avatar_url`，Alembic `0002_oauth`）。launcher 无服务端持久化（纯 SPA + 反代）。workspace Profile 仍走文件系统（P1 bind mount）。

**Testing**:
- 后端 Unit：pytest（OAuth provider client / callback 校验 / 自动建户 / 邮箱合并 / 绑定解绑 / JWT 等价签发），全 mock IdP，行覆盖率 ≥80%
- 后端 Integration：testcontainers-postgres（真实 PG）+ mock IdP（msw/httpx mock）回调流程
- 前端 Unit：vitest + testing-library（登录/列表/向导/监控视图关键交互）+ msw（orchestrator API mock）
- E2E：`make test-e2e-p3`，真实 stack（orchestrator + postgres + launcher + ≥1 workspace），OAuth 用开发态 mock provider；覆盖 登录→创建→真实启动→统一访问→越权拒绝→审计落库；外加 P1/P2 回归（SC-008 零迁移）

**Target Platform**: Linux x86_64/arm64 主机，macOS 开发机。Docker 24+ + docker compose v2。**orchestrator 容器需挂载宿主机 `/var/run/docker.sock`**（编排者身份，FR-016）。

**Project Type**: 多租户平台的前端入口层 + 编排部署补齐（launcher 独立容器 + orchestrator 扩展 OAuth + nginx 反代拓扑）。

**Performance Goals**（映射 SC）:
- OAuth 登录到工作台 < 10s（SC-001，含 IdP 跳转）
- 创建向导提交到列表出现 < 3s（SC-002）
- workspace 启动到 healthy < 120s（SC-003，延续 P2）
- `auth_request` 子请求 < 200ms（延续 P2 SC-008）

**Constraints**:
- 零迁移：P1 cap-agent 业务路由 + P2 编排/JWT/auth_request/审计 内核行为不变（FR-025/026/027 / SC-008）
- workspace 间鉴权隔离不可破坏（SC-009）
- orchestrator 不可达 fail-closed（SC-010，延续 P2）
- OAuth 凭证不硬编码/不落库/不进前端构建（FR-007）

**Scale/Scope**: 单机多租户（launcher 单实例 + 多 workspace 反代，目标并发 ≥3 workspace）。launcher 前端约 3-5K LOC（含测试），orchestrator OAuth 扩展约 1-2K LOC。不含 K8s / 公网 CDN / 移动端。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

仓库无 `.specify/memory/constitution.md`（同 P2）。采用全局 CLAUDE.md（用户偏好）作为隐性 constitution，逐条核对：

| 原则 | 来源 | 本计划合规性 |
|------|------|--------------|
| 始终用中文 | CLAUDE.md #1 | ✅ 所有 spec/plan/tasks/contract/README 用中文 |
| 目标不清晰先讨论 | CLAUDE.md #1 | ✅ 3 项核心架构决策经 AskUserQuestion 收敛（OAuth 关系/真实启动/入口拓扑）；9 项技术决策在 research 论证 |
| 最小化设计/改动 | CLAUDE.md #2 | ✅ 复用 P2 JWT/auth_request/compose_runner 内核；OAuth 与 launcher 纯新增式扩展；不重写编排（FR-019） |
| Spec→Plan→Test→Code | CLAUDE.md #3 | ✅ speckit 全流程 + 前后端全 TDD |
| 追根因不打补丁 | CLAUDE.md #2 | ✅ 真实启动缺口定位为「部署运行时」（socket/CLI/挂载）而非补丁式绕过；OAuth 复用 P2 身份内核而非另造会话 |
| Fail Fast | CLAUDE.md #2 | ✅ OAuth 回调校验失败即拒（FR-005）；workspace 启动失败转 error 并暴露（FR-018） |
| Python uv+3.12+TypeHint+Async | CLAUDE.md #8 | ✅ orchestrator OAuth 扩展全 async + type hint；uv 管理 |
| 前端 type:module + import.meta | CLAUDE.md #7 | ✅ launcher 用 Vite + ESM + import.meta |
| 模块单职责/暴露协议 | CLAUDE.md #6 | ✅ launcher（入口/反代）/ orchestrator（编排+身份）/ workspace（业务）三层职责不重叠；OAuth 为 orchestrator 身份源的扩展 |
| Explicit > Magic | CLAUDE.md #4 | ✅ OAuth provider 凭证显式环境变量；反代路径前缀显式契约；mock provider 显式开关 |
| Unit→Integration→E2E | CLAUDE.md #5 | ✅ 前后端三层 + P1/P2 回归 |

**结论**：通过 Constitution Check。范围聚焦 P2 推迟项 + 部署补齐，无 Complexity Tracking 阻塞条目。

## Project Structure

### Documentation (this feature)

```text
specs/003-sandbox-p3-launcher/
├── spec.md              # 规格（已完成）
├── plan.md              # 本文件
├── research.md          # Phase 0：9 项技术决策论证（OAuth 流程/数据模型/JWT 存储/部署/反代/前端架构…）
├── data-model.md        # Phase 1：oauth_accounts 表 + users 扩展 + Alembic 0002 + ER
├── quickstart.md        # Phase 1：端到端验证手册（OAuth/列表/创建/真实启动/统一访问/监控）
├── contracts/           # Phase 1：对外契约
│   ├── oauth-rest-api.md            # OAuth 登录/回调/绑定/解绑 端点契约
│   ├── launcher-workspace-proxy.md  # launcher 反代 workspace 路由/auth_request/WebSocket 契约
│   └── frontend-api-contract.md     # launcher 前端消费的 orchestrator REST API（P2 复用 + OAuth 扩展）
├── checklists/
│   └── requirements.md  # 规格质量清单（已完成）
└── tasks.md             # Phase 2：任务列表（/speckit-tasks）
```

### Source Code (repository root)

```text
sandbox/                                 # 仓库根（P3 在 P2 基础上新增 launcher/ + 扩展 orchestrator/cap-nginx）
├── launcher/                            # 【新增】React 启动器（前端 + 反代网关）
│   ├── Dockerfile                       # multi-stage: node 构建SPA → nginx 托管 + 反代
│   ├── package.json                     # vite/react19/shadcn/tailwind/react-router/react-query/vitest/msw
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.js / postcss.config.js
│   ├── index.html
│   ├── nginx/launcher.conf.tmpl        # SPA 托管 + /api→orchestrator + /ws/{slug}/→workspace 反代（auth_request）
│   ├── src/
│   │   ├── main.tsx                    # React 19 入口 + Router + QueryClient
│   │   ├── App.tsx                     # 路由根（受保护路由 + 登录路由）
│   │   ├── api/                        # orchestrator API client（fetch + react-query hooks）
│   │   │   ├── client.ts               # baseURL/JWT 注入/refresh 拦截器
│   │   │   ├── auth.ts                 # login/oauth 流程 hooks
│   │   │   ├── workspaces.ts           # list/create/start/stop/... hooks
│   │   │   └── audit.ts                # 审计查询 hooks（监控面板）
│   │   ├── pages/
│   │   │   ├── Login.tsx               # 本地登录表单 + GitHub/Google OAuth 入口
│   │   │   ├── Workspaces.tsx          # 列表 + 生命周期操作
│   │   │   ├── CreateWizard.tsx        # 多步创建向导（模板/slug/校验/确认）
│   │   │   └── Monitor.tsx             # 监控面板（状态 + 审计流 + 筛选/分页）
│   │   ├── components/                 # shadcn/ui 组合的业务组件（WorkspaceCard/AuditTable/StatusBadge…）
│   │   ├── hooks/                      # useAuth/useSession（JWT/refresh/失效重定向）
│   │   ├── lib/                        # 纯函数（slug 校验/状态映射/不可变更新）
│   │   └── types/                      # 与 orchestrator 契约对齐的 TS 类型
│   └── tests/
│       ├── unit/                       # vitest + testing-library（页面/组件/hooks）
│       └── msw/                        # handlers（orchestrator API mock）
├── orchestrator/                        # 【扩展】OAuth 身份源
│   └── src/orchestrator/
│       ├── routers/oauth.py            # 【新增】/api/v1/auth/oauth/{provider}/{login,callback} + /bind /unbind
│       ├── models/oauth_account.py     # 【新增】OAuthAccount ORM
│       ├── schemas/oauth.py            # 【新增】Pydantic 请求/响应
│       ├── services/oauth_provider.py  # 【新增】GitHub/Google client（authlib + httpx token/userinfo）
│       ├── services/oauth_linker.py    # 【新增】回调→建户/邮箱合并/绑定 解析逻辑
│       ├── core/config.py              # 【扩展】OAUTH_GITHUB_*/OAUTH_GOOGLE_*/OAUTH_REDIRECT_URL/OAUTH_MOCK
│       └── ...（P2 路由/服务不变）
│   └── migrations/versions/0002_oauth.py  # 【新增】oauth_accounts + users 增列
│   └── tests/unit/test_oauth_*.py + integration/test_oauth_flow.py
├── cap-nginx/                           # 【扩展】launcher 反代 + workspace auth_request 渲染
│   ├── nginx.launcher.conf.tmpl        # 【新增】launcher 网关配置（SPA + 反代 + auth_request）
│   └── nginx.workspace.conf.tmpl       # 【扩展】Phase 5 auth_request 配置（P2 已起稿，P3 落地渲染）
├── docker-compose.orchestrator.yml     # 【扩展】+ launcher 服务 + orchestrator docker.sock 挂载 + compose cwd
├── docker-compose.workspace.yml.tmpl   # 【扩展】workspace cap-nginx 挂载 launcher 反代可达性（如需）
├── Makefile                            # 【扩展】build-launcher / up-p3 / test-launcher / test-e2e-p3
├── .env.example                        # 【扩展】OAUTH_GITHUB_CLIENT_ID/SECRET/OAUTH_GOOGLE_*/OAUTH_REDIRECT_URL/OAUTH_MOCK/LAUNCHER_PORT
└── tests/
    └── e2e/
        ├── test_p3_oauth_flow.py       # 【新增】OAuth 登录→建户/合并→JWT 等价
        ├── test_p3_launcher_proxy.py   # 【新增】统一入口反代 + auth_request + 越权拒绝
        ├── test_p3_real_start.py       # 【新增】orchestrator-as-controller 真实拉起 workspace
        └── test_p1p2_regression.py     # 【新增】P1/P2 零迁移回归
```

**Structure Decision**：
1. **launcher 作为第 9 个独立服务项目**（与 7 个 cap-* + orchestrator 并列，独立 `package.json` + `Dockerfile` + nginx），延续 monorepo 单服务单职责。容器内 nginx 托管 SPA + 反代（避免额外反代容器）。
2. **OAuth 扩展集中在 orchestrator**（身份是 orchestrator 职责，§8.6 关注点分离），新增 `routers/oauth.py` + `oauth_account.py` + `oauth_provider.py`，不改动 P2 既有 auth/workspaces/audit 路由。
3. **补齐真实启动是部署变更**（compose_runner 代码不变，FR-019），仅改 Dockerfile/compose/socket 挂载。
4. **launcher 反代复用 P2 auth_request 机制**，cap-nginx workspace 模板的 Phase 5 配置在 P3 落地渲染。

## Milestone 拆解

| Milestone | 内容 | 验证手段 | 预估任务数 |
|-----------|------|----------|------------|
| **M0** launcher 骨架 | Vite + React 19 + shadcn/ui + tailwind + 路由 + react-query + nginx 容器 + `/api` 反代 | `make build-launcher` 产物可起；vitest 骨架绿；nginx 托管 SPA 可达 | 7 |
| **M1** OAuth 后端 | orchestrator oauth router/provider/linker + oauth_accounts 迁移 + mock provider + JWT 等价签发 | `test-orchestrator` OAuth 用例绿（回调/建户/合并/绑定/伪造拒绝） | 9 |
| **M2** launcher 登录+列表+向导 | Login（本地+OAuth入口）/ Workspaces 列表 / CreateWizard + API client + JWT 会话/refresh | vitest（页面+msw）绿；手动 OAuth 登录到列表闭环 | 9 |
| **M3** 真实启动部署补齐 | orchestrator Dockerfile 装 docker CLI + compose 挂载 docker.sock + 模板挂载 + compose cwd + cap-nginx Phase 5 渲染 | `test_p3_real_start`：orchestrator 容器内真实拉起 1 workspace 到 healthy | 7 |
| **M4** 统一反代+访问 | launcher nginx `/ws/{slug}/` 反代 + auth_request + WebSocket 透传 + 错误降级 | `test_p3_launcher_proxy`：统一入口访问 + 越权拒绝 + fail-closed | 7 |
| **M5** 监控面板 | Monitor（状态+审计流+筛选+分页，轮询）+ 状态机映射 | vitest（监控视图）绿；手动触发操作见审计 | 5 |
| **M6** E2E + 回归 | OAuth→创建→真实启动→统一访问→越权→审计 全链路 + P1/P2 回归 | `make test-e2e-p3` 全绿；P1/P2 回归全绿 | 6 |

## Risks

| 风险 | 影响 | 缓解 |
|------|------|------|
| docker.sock 挂载 = orchestrator 可控宿主全部容器（提权面） | 高（安全） | orchestrator 容器 cap_drop + read-only socket + 仅 compose 子进程路径；网络隔离；记录于安全声明（单机受信环境） |
| OAuth 凭证泄露 / 前端可见 | 高（安全） | 凭证仅后端 env；前端只发起跳转不持有 secret；回调 state 防 CSRF |
| 反代 WebSocket（terminal/novnc）被截断 | 中（功能） | nginx `proxy_http_version 1.1` + Upgrade/Connection 头透传 + 超时调大（R5） |
| 邮箱合并误并（不同真实用户同邮箱） | 中（安全/数据） | P3 接受默认合并并记录风险（Assumptions）；严格归属推迟 |
| orchestrator 容器装 docker CLI 增大镜像 / 版本漂移 | 低（运维） | multi-stage + 固定 docker compose v2 版本 pin |
| OAuth IdP 不可达 | 低（可用性） | 可读错误 + 重试；本地账户仍可登录（并存） |

## Implementation Strategy

### TDD 三步循环（每个 milestone 内）
RED（契约/测试先写）→ GREEN（最小实现）→ REFACTOR。前端组件先写 vitest + msw 期望，再实现；后端 OAuth 先写回调校验/建户测试（mock IdP），再实现 provider。

### 契约先行（contracts/ 作为 stub 起点）
`oauth-rest-api.md` / `launcher-workspace-proxy.md` / `frontend-api-contract.md` 先定，launcher API client 与 orchestrator oauth router 对同一契约双向实现，前后端可并行。

### 复用 P2 内核（零迁移）
- OAuth 登录成功 → 调 P2 既有 `security.create_tokens()` 签发等价 JWT（不另造会话）
- launcher 反代鉴权 → 复用 P2 `verify` 端点 + 可信 header 机制
- workspace 编排 → P2 compose_runner 原样（M3 仅部署补齐）

### 安全简化边界（严守）
- 沿用 P1 宽松：Shell permissive、Chromium --no-sandbox（FR-NI-6）
- 沿用 P2：JWT 网关 + auth_request fail-closed + 审计 4 类
- docker.sock 挂载是 P3 唯一新提权面，限于单机受信环境并记录

## Phase 0 / Phase 1 / Phase 2 输出

- **Phase 0**（research.md）：R1 OAuth 流程与库选型 / R2 oauth_accounts + users 扩展与邮箱合并 / R3 JWT 前端存储与 CSRF / R4 orchestrator-as-controller 部署 / R5 launcher 反代拓扑与 WebSocket / R6 cap-nginx auth_request Phase 5 渲染 / R7 监控刷新方式 / R8 前端架构与状态管理 / R9 OAuth 开发态 mock
- **Phase 1**：data-model.md（oauth_accounts + users 扩展 + Alembic 0002）/ contracts/（3 份）/ quickstart.md
- **Phase 2**（tasks.md）：M0-M6 任务分解（/speckit-tasks）
