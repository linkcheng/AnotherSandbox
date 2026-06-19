# Research: AI 个人沙箱 P3 — React 启动器与 SSO/OAuth

**Date**: 2026-06-20 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Phase 0 技术决策论证。每项含 **Decision / Rationale / Alternatives**。来源：`.archive/sandbox-design.md`、P2 已交付内核、行业最佳实践。

---

## R1. OAuth 流程与库选型

**Decision**：用 `authlib` 实现 OAuth 2.0 **Authorization Code Flow + PKCE**，统一封装 GitHub 与 Google；`httpx` 调 IdP token/userinfo 端点；登录成功后调 P2 既有 `security.create_tokens()` 签发**等价 JWT**（access + refresh），不另造会话体系。

**Rationale**：
- Authorization Code + PKCE 是当前 Web OAuth 最佳实践（防 authorization code 拦截），GitHub/Google 均支持。
- `authlib` 是 Python 生态成熟的 OAuth client（支持 OAUTH2.0/OIDC、state、PKCE），比手写更安全可靠，与 FastAPI/httpx 同 async 生态。
- 复用 P2 `create_tokens()` 保证 OAuth JWT 与本地账户 JWT **行为 100% 一致**（FR-002/SC-006），下游鉴权/审计零分支。

**Alternatives**：
- 手写 OAuth（httpx 直接调）：灵活但易漏 state/PKCE/校验，安全风险高 → 否决。
- OIDC（id_token）：GitHub 不支持完整 OIDC，统一用 OAuth2 + userinfo 更通用 → 采纳。
- `authlib` vs `httpx-oauth`：authlib 社区更广、文档全 → 选 authlib。

---

## R2. `oauth_accounts` 表 + `users` 扩展 + 邮箱合并

**Decision**：
- 新增 `oauth_accounts`（`id` / `provider`('github'|'google') / `provider_user_id` / `user_id`(FK→users) / `email` / `raw_profile`(JSONB) / `created_at`），唯一约束 `(provider, provider_user_id)`。
- `users` 增 nullable 列 `display_name` / `avatar_url`（OAuth 回调填充，本地账户留空）。
- **邮箱合并策略**：OAuth 回调取 userinfo.email → 若 `users.email` 已存在 → 绑定到既有 user（不新建）；否则新建 user（display_name/avatar 来自 profile，password_hash NULL）。`(provider, provider_user_id)` 唯一防止同外部账号重复绑定。

**Rationale**：
- `oauth_accounts` 与 `users` 解耦：一个 user 可绑多 provider，符合 FR-006。
- 邮箱合并实现 FR-003「按邮箱合并不产生重复用户」，并满足 SC-006。
- `raw_profile` JSONB 存 IdP 原始信息备查，schema 不需频繁迁移。

**Alternatives**：
- 不合并、OAuth 用户独立：同邮箱两套身份，归属割裂 → 否决（FR-003 要求合并）。
- 强制邮箱验证才合并：更安全但增加流程复杂度，P3 接受默认合并风险（Assumptions）→ 推迟严格校验。
- display_name/avatar 单独建表：过度设计 → 直接 users 增列。

---

## R3. JWT 前端存储与会话安全

**Decision**：JWT（access + refresh）存 **HttpOnly + Secure + SameSite=Lax cookie**，由 orchestrator OAuth/登录端点 `Set-Cookie` 下发；launcher API client（fetch）带 `credentials: 'include'`，无需 JS 读 token（防 XSS 窃取）。refresh 端点轮换 refresh token（延续 P2）。CSRF 用 SameSite=Lax + 自定义头（`X-Requested-With`）双重防护。

**Rationale**：
- HttpOnly cookie 防 XSS 窃 token，是 Web 安全首选（XSS 是 SPA 主要威胁）。
- SameSite=Lax 防 CSRF 跨站携带；OAuth 回调本身是 GET 跳转，Lax 允许顶层导航携带，登录态正常建立。
- 复用 P2 refresh 轮换，前端只需在 401 时触发 refresh 或重定向登录（FR-013）。

**Alternatives**：
- localStorage + Authorization 头：实现简单但 XSS 可读 token，安全差 → 否决。
- 内存 + sessionStorage：刷新丢失体验差 → 否决。
- BFF 模式：过度设计（P3 单后端 orchestrator 已是 BFF）→ 不需要额外层。

---

## R4. orchestrator-as-controller 部署（补齐真实启动）

**Decision**：
- orchestrator 镜像 multi-stage 增 `docker compose v2` CLI（固定版本 pin，从官方静态二进制）。
- `docker-compose.orchestrator.yml` 给 orchestrator 挂载：`/var/run/docker.sock:/var/run/docker.sock`、workspace compose 模板与构建上下文（`docker-compose.workspace.yml.tmpl` + cap-* 镜像已构建）、`WORKSPACE_COMPOSE_CWD=/workspace-compose`（仓库根挂载点）。
- 安全加固：orchestrator 保留 `cap_drop: [ALL]`（docker socket 本身不需额外 capability，socket 访问靠文件权限）+ `security_opt: no-new-privileges`；socket 挂载是已知提权面，限定单机受信环境并记入安全声明。
- compose_runner 代码**零改动**（FR-019），其在容器内 cwd=`WORKSPACE_COMPOSE_CWD` 调 `docker compose -p` 即可真实拉起 workspace。

**Rationale**：
- 根因定位：P2 缺口是「运行时部署」（socket + CLI + 模板可见），非代码（compose_runner 已就绪）。补部署即闭环。
- docker.sock 挂载是「orchestrator 控宿主 Docker」的标准做法（Portainer/Watchtower 同模式），单机受信可接受。
- 固定 compose v2 版本避免漂移。

**Alternatives**：
- SSH 到宿主执行 docker：多一层 SSH + 密钥管理，更复杂 → 否决。
- 引入 K8s/远程编排 API：超 P3 范围（Phase 3）→ 否决。
- 每个 workspace 独立 docker-in-docker：资源浪费 + 镜像重建 → 否决。

---

## R5. Launcher 统一反代拓扑与 WebSocket 透传

**Decision**：launcher 容器内置 nginx，单一配置 `nginx.launcher.conf.tmpl`：
- 托管 React SPA（`/` → 静态产物，try_files 回退 index.html 支持 client-side routing）。
- 反代 `/api/ → orchestrator:8000`（带 trailing slash 剥离）。
- 反代 `/ws/{slug}/ → {workspace}:80`（workspace cap-nginx），`{slug}` 由 orchestrator workspace 元数据解析为内部 host:port（通过 resolver + upstream 动态，或 launcher 启动时从 orchestrator 拉路由表生成）。
- 鉴权：`/ws/` location 加 `auth_request /authsub;` 子请求到 orchestrator `/api/v1/verify`（复用 P2），通过后注入可信 header 透传 workspace。
- **WebSocket 透传**：`proxy_http_version 1.1` + `proxy_set_header Upgrade $http_upgrade` + `Connection "upgrade"` + `proxy_read_timeout 3600s`（terminal/novnc 长连接）。
- 错误降级：workspace 不存在/未启动/越权 → auth_request 返回 403/自定义页，不透 5xx。

**Rationale**：
- nginx 同时承担 SPA 托管 + 反代 + auth_request，单容器单职责，符合「单端口对外」。
- WebSocket 透传是 terminal/novnc 可用的关键（FR-022）。
- 复用 P2 `verify` + 可信 header，鉴权零新增逻辑。

**Alternatives**：
- Node 反代（http-proxy）：不如 nginx 成熟/高性能，且 WebSocket 配置繁琐 → 否决。
- Traefik/Caddy：标签自动发现优秀，但引入新依赖 + 学习成本，P3 手写 nginx 模板更可控 → 否决（推迟）。
- 子域名路由（`{slug}.host`）：需 DNS/通配证书，P3 用路径前缀最小可用（Assumptions）。

**未决（plan 内已标注，实现时定）**：`{slug}→host:port` 解析用「nginx resolver + 变量」还是「launcher 启动拉路由表渲染」——M4 实现时按可维护性选其一，记录于 tasks。

---

## R6. cap-nginx auth_request Phase 5 配置渲染

**Decision**：P2 `nginx.workspace.conf.tmpl` 已起稿 auth_request（Phase 5 推迟），P3 落地：
- workspace 启动时（compose_runner up），workspace 的 cap-nginx 挂载渲染后的 `nginx.workspace.conf`（含 `auth_request /authsub → ORCHESTRATOR_URL/api/v1/verify` + `auth_request_set` 可信 header + fail-closed `error_page`）。
- 渲染通过 workspace compose 模板的环境变量 + entrypoint envsubst（P1 cap-nginx 已用 envsubst 模式）。
- launcher 反代 `/ws/{slug}/` 到该 workspace cap-nginx:80，鉴权链路：launcher auth_request → orchestrator verify → 透传 → workspace cap-nginx（已是受信内网，二次 auth_request 可去重或保留）。

**Rationale**：延续 P2 设计（Phase 5），P3 只是把「起稿」变「可用」。envsubst 复用 P1 cap-nginx 既有模式，零新机制。

**Alternatives**：launcher 层一次性 auth_request，workspace cap-nginx 不再 auth_request：减少一跳但破坏 P2「每 workspace 自带 auth_request fail-closed」契约 → 保留双层（纵深防御）。

---

## R7. 监控面板刷新方式

**Decision**：监控面板用**轮询**（`@tanstack/react-query` 的 `refetchInterval`，状态/审计分别 5s/10s 可配），**不引入 SSE/WebSocket 推送**。

**Rationale**：
- P2 已有 workspace 查询 + 审计查询 REST API，轮询零后端改动（最小化）。
- 监控面板非毫秒级实时需求，5-10s 轮询体验足够（SC-005「刷新/轮询周期内可见」）。
- SSE/WebSocket 需 orchestrator 新增推送端点 + 反代透传，工作量与 P3 范围不匹配 → 推迟。

**Alternatives**：SSE 实时推送：体验更好但需后端新增 + 反代透传，超范围 → 推迟（记入 follow-up）。

---

## R8. 前端架构与状态管理

**Decision**：
- 构建：**Vite + React 19 + TypeScript**（strict）。
- UI：**shadcn/ui**（Radix 底座 + tailwind variants）+ **tailwind css**。
- 路由：**react-router v6**（data routers）。
- 数据/状态：**@tanstack/react-query**（server state：workspace/审计，函数式 hooks + 不可变缓存）+ **React Context + useReducer**（client state：会话/UI，纯函数 reducer 保证不可变更新）。不引入 Redux/Zustand（YAGNI）。
- 函数式原则：纯函数组件、hooks、不可变状态更新、副作用隔离（effect 仅用于订阅/同步）。
- 目录：`api/`（client+hooks）/`pages/`/`components/`/`hooks/`/`lib/`（纯函数）/`types/`。

**Rationale**：
- react-query 处理 server state（缓存/轮询/失效/乐观更新），避免手写 loading/error 样板，天然函数式。
- useReducer + Context 处理少量 client state，不可变更新，符合「函数式」约束且零额外依赖。
- shadcn/ui 复制式组件（非 npm 黑盒），可定制，契合「Explicit > Magic」。

**Alternatives**：
- Redux Toolkit：状态机复杂时优秀，但 P3 状态简单（server state 为主）→ 过度。
- Zustand：轻量但 react-query 已覆盖 server state → 冗余。
- 类组件/继承：违反「函数式」约束 → 否决。

---

## R9. OAuth 开发态 mock

**Decision**：orchestrator 加 `OAUTH_MOCK=true` 开关（env）。开启时，oauth router 的 `/{provider}/callback` 不真实调 IdP，而是接受一个固定的 mock code（如 `mock-code-{provider}`），返回预设 mock userinfo（如 `dev-{provider}@local`/`provider_user_id=mock-123`），走完整建户/合并/签 JWT 流程。真实 IdP（`OAUTH_MOCK=false`）走 authlib 真实流程。

**Rationale**：
- 本地/CI 测试无法依赖真实 GitHub/Google（凭证/网络/配额），mock 让 OAuth 闭环可离线验证（FR-030 E2E）。
- mock 只替换 IdP 交互层，建户/合并/签 JWT 走真实代码路径，测试有效。
- 显式开关（Explicit > Magic），生产必须 `OAUTH_MOCK=false`。

**Alternatives**：
- 用真实 OAuth App 测试：凭证管理 + 网络依赖 + 无法 CI 化 → 否决。
- 第三方 mock IdP 容器：额外依赖 → mock 开关更轻。

---

## 决策汇总（速查）

| # | 决策 | 关键选择 |
|---|------|----------|
| R1 | OAuth 流程/库 | authlib + Authorization Code + PKCE；签发等价 P2 JWT |
| R2 | 数据模型 | oauth_accounts 表 + users 增 display_name/avatar；邮箱合并 |
| R3 | JWT 前端存储 | HttpOnly + Secure + SameSite=Lax cookie；防 XSS/CSRF |
| R4 | 真实启动部署 | docker.sock 挂载 + compose CLI + 模板挂载；compose_runner 零改动 |
| R5 | launcher 反代 | nginx SPA + /api + /ws/{slug}/ + auth_request + WebSocket 透传 |
| R6 | cap-nginx Phase5 | envsubst 渲染 auth_request；双层鉴权纵深 |
| R7 | 监控刷新 | 轮询（react-query refetchInterval），SSE 推迟 |
| R8 | 前端架构 | Vite+React19+shadcn+tailwind+react-router+react-query+useReducer |
| R9 | OAuth mock | OAUTH_MOCK 开关，mock userinfo 走真实建户/签 JWT |
