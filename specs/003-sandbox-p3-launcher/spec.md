# Feature Specification: AI 个人沙箱 P3 — React 启动器与 SSO/OAuth

**Feature Branch**: `003-sandbox-p3-launcher`

**Created**: 2026-06-20

**Status**: Draft

**Source**: `.archive/sandbox-design.md`（React 启动器 / SSO 认证相关章节）、P2 spec `FR-NI-3`（React 启动器 UI 推迟）/ `FR-NI-6`（SSO/OAuth 推迟）

**Input**: 在 P1（单 workspace 全栈能力，`specs/001`）+ P2（Orchestrator 编排 + JWT 认证 + 审计，`specs/002`）之上，交付 P2 明确推迟的两项：① React 启动器 UI（workspace 列表 / 创建向导 / 监控面板）② SSO/OAuth（GitHub + Google）认证。同时补齐 P2 遗留的「workspace 真实启动部署闭环」。P3 是叠加层——不侵入 P1 workspace 内业务路由、不改动 P2 编排内核与 JWT/auth_request/审计契约，仅做**新增式扩展**（OAuth 身份源 + 前端 + 部署补齐 + 反代入口）。

**范围决策（已与 stakeholder 确认）**：

- **做（核心交付）**：
  1. **React 19 启动器**（函数式 + shadcn/ui + tailwind）：workspace 列表 / 创建向导 / 监控面板三大视图
  2. **SSO/OAuth（GitHub + Google）**：与 P2 本地账户（邮箱密码）**并存**；OAuth 登录成功后由 orchestrator **签发 P2 JWT**（复用 access/refresh 轮换体系），前端统一以 JWT 调 API；新增 `oauth_accounts` 表关联 `user`
  3. **补齐 workspace 真实启动部署闭环**：orchestrator 容器获得 docker 编排能力（socket + CLI + workspace 模板挂载），使「创建 → 真实拉起 cap-* 容器组 → 健康 → 访问」端到端可用（P2 编排代码已就绪，缺口在运行时部署）
  4. **Launcher 统一反代入口**：单域名 + 路径区分 workspace，经 orchestrator `auth_request` 注入可信 header 后反代到目标 workspace 的 cap-nginx
- **不做（继续推迟）**：Snapshot 编排、计量计费 `usage_metrics`、workspace 内文件级权限细化、SAML/企业 IdP、移动端原生应用
- **安全沿用（不重做）**：复用 P2 JWT 网关认证 + 可信 header + nginx `auth_request` fail-closed + 审计 4 类落库内核；workspace 内部沿用 P1 宽松基线（Shell `permissive`、Chromium `--no-sandbox`）

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - OAuth 社交登录（GitHub / Google）(Priority: Core)

用户在启动器登录页选择「使用 GitHub 登录」或「使用 Google 登录」，跳转到 IdP 完成授权后回调到启动器；orchestrator 校验 IdP 回调、首次登录自动创建/绑定本地用户记录，随后签发与本地账户登录完全等价的 JWT（access + refresh）。已注册的本地账户可通过 OAuth 绑定同一身份；同一邮箱的 OAuth 账户与本地账户按邮箱合并。

**Why this priority**: 登录是进入启动器的前置门槛；OAuth 显著降低注册摩擦，是 P2「仅 CLI / 自建账户」向「真实终端用户」过渡的关键一跃，也是 P3 区别于 P2 的用户面入口。

**Independent Test**: 在启动器登录页点击「GitHub 登录」完成授权回调后，启动器进入已登录态并能看到自己的 workspace 列表；未授权/伪造的回调被拒绝。

**Acceptance Scenarios**:

1. **Given** 一个未登录用户，**When** 点击「GitHub 登录」并在 GitHub 完成授权，**Then** 回调到启动器后自动登录成功，获得有效 JWT，可访问受保护页面。
2. **Given** 一个已有本地账户（邮箱 `a@b.c`）的用户，**When** 用邮箱相同的 GitHub 账户首次 OAuth 登录，**Then** 系统按邮箱将 OAuth 身份绑定到既有本地账户，不产生重复用户。
3. **Given** 一个全新 OAuth 用户，**When** 首次 OAuth 登录成功，**Then** 自动创建用户记录与 `oauth_accounts` 关联，无需额外注册步骤。
4. **Given** 一个伪造/过期/被撤销的 OAuth 回调（state 不匹配 / code 失效），**When** 回调到 orchestrator，**Then** 拒绝登录，不签发 JWT。
5. **Given** OAuth 登录成功，**When** 携带所得 JWT 访问任意 orchestrator API，**Then** 与本地账户登录的 JWT 行为完全一致（同套鉴权、同套可信 header、同套审计）。

---

### User Story 2 - Workspace 列表与创建向导 (Priority: Core)

已登录用户在启动器看到自己拥有/参与的 workspace 列表（名称、状态、端口、创建时间、角色），并通过多步创建向导新建 workspace：选择模板 → 填写名称/slug → 确认配置 → 提交。列表与向导均通过 orchestrator REST API（P2 已交付）交互，前端仅做展示与编排。

**Why this priority**: 列表是启动器的主视图与「我有什么」的入口；创建向导把 P2 的 CLI/API 创建能力暴露给终端用户，是从「能创建」到「好用地创建」的体验层。

**Independent Test**: 登录后列表正确展示自己的 workspace（含状态）；通过向导提交一个合法 workspace 后，列表中出现该 workspace 且状态为 `created`/`starting`。

**Acceptance Scenarios**:

1. **Given** 已登录用户 alice 拥有 2 个 workspace，**When** 打开列表视图，**Then** 看到 2 条记录，含名称、状态、端口、创建时间、角色；他人 workspace 不出现。
2. **Given** alice 在创建向导，**When** 选择 `minimal` 模板、填写合法 slug、提交，**Then** orchestrator 创建成功，列表实时出现新 workspace。
3. **Given** alice 提交非法 slug（冲突/格式错误/超长），**When** 提交，**Then** 前端展示明确校验错误，不发起创建。
4. **Given** 列表中的一个 workspace 处于 `running`，**When** alice 查看该行，**Then** 可见运行状态与访问入口链接。

---

### User Story 3 - Workspace 真实启动与统一入口访问 (Priority: Core)

用户在列表中对处于 `created`/`stopped` 的 workspace 执行「启动」，orchestrator 真实拉起该 workspace 的 cap-* 容器组（复用 P1 镜像 + P2 compose 编排），健康后该 workspace 在启动器「打开」即可经统一入口（单域名 + 路径）访问其内部 UI（novnc / code-server / terminal / jupyter），访问全程经 `auth_request` 注入可信 header 完成鉴权。

**Why this priority**: 这是 P3「补齐真实启动」决策的落地，也是启动器从「管理面板」升级为「可用工作入口」的核心——没有真实启动与统一访问，启动器只是 P2 API 的薄壳。P2 编排代码已就绪，本故事补齐的是运行时部署 + 反代入口 + 端到端闭环。

**Independent Test**: 在启动器对一个新建 workspace 点「启动」，等待健康后点「打开」，浏览器在统一域名下加载到该 workspace 的桌面 UI，且该访问经过鉴权（越权被拒）。

**Acceptance Scenarios**:

1. **Given** 一个 `created` 状态的 workspace，**When** 用户点「启动」，**Then** orchestrator 真实拉起该 workspace 的 cap-* 容器组，全部 healthy 后状态转为 `running`，列表反映该变化。
2. **Given** 一个 `running` 的 workspace，**When** 用户点「打开」，**Then** 经统一入口（单域名 + 路径）加载该 workspace 的 cap-nginx 暴露的 UI（novnc 等），鉴权通过。
3. **Given** workspace `alice-ws` 处于 `running`，**When** 用户 bob（无授权）试图访问其统一入口路径，**Then** `auth_request` 拒绝（403），无法加载 UI。
4. **Given** 一个 `running` 的 workspace，**When** 用户执行「停止」，**Then** 容器组停止、状态转 `stopped`、统一入口对该 workspace 不再可达；再次「启动」恢复。
5. **Given** workspace 启动失败（端口耗尽 / 镜像缺失 / compose 错误），**When** 启动，**Then** 状态转 `error` 并向用户展示可读错误，统一入口不可达。

---

### User Story 4 - 监控面板（状态 + 审计）(Priority: Important)

用户在监控面板查看自己 workspace 的运行时状态（运行/暂停/停止/错误、端口、最近状态变更）与审计事件流（shell.exec / fs.write / browser.action / gui.action，源自 P2 审计落库），按 workspace 筛选与分页。监控数据全部来自 orchestrator 已有 API（workspace 查询 + 审计查询），前端不引入独立数据源。

**Why this priority**: 监控把 P2 的「审计落库」与「状态机」对终端用户可见化，是从「可审计」到「可观测」的体验补全；依赖 P2 既有能力，增量主要在前端。

**Independent Test**: 触发一次 workspace 内操作（如 shell 命令）后，监控面板该 workspace 的审计流中出现对应事件；状态变更在面板实时反映。

**Acceptance Scenarios**:

1. **Given** alice 有一个 `running` workspace 且近期有 shell 操作，**When** 打开监控面板并选中该 workspace，**Then** 看到运行状态与按时间倒序的审计事件（含类型、actor、时间、摘要）。
2. **Given** 多个 workspace，**When** alice 切换筛选，**Then** 面板只展示所选 workspace 的状态与审计。
3. **Given** 审计事件超过一页，**When** alice 翻页，**Then** 分页加载，不重复/不遗漏。
4. **Given** 一个 `error` 状态的 workspace，**When** 查看面板，**Then** 错误状态与（若有）相关错误信息可见。

---

### User Story 5 - 启动器部署与统一反代拓扑 (Priority: Important)

启动器作为独立服务部署（与 orchestrator + postgres 同网络），对外暴露单一入口；经登录鉴权后，启动器自身承载 SPA，并以统一路径前缀反代各 workspace 的 cap-nginx（鉴权由 orchestrator `auth_request` 完成）。该拓扑使终端用户只需记忆一个域名即可管理并访问所有 workspace。

**Why this priority**: 统一入口是「单端口对外」设计目标（§1）在多租户下的延续，也是 US3「打开 workspace」的承载；明确部署形态让 P3 可独立交付与验证。

**Independent Test**: 部署后，浏览器访问单一启动器域名，未登录被导向登录页；登录后可经同域名路径访问任意已启动 workspace。

**Acceptance Scenarios**:

1. **Given** 启动器已部署，**When** 浏览器访问启动器域名，**Then** 加载登录页（未登录）或工作台（已登录）。
2. **Given** 已登录用户，**When** 访问 `/ws/{slug}/...`（workspace 统一路径），**Then** 启动器反代到该 workspace 的 cap-nginx，鉴权通过后返回其 UI。
3. **Given** orchestrator 不可达，**When** 访问任意 workspace 路径，**Then** `auth_request` fail-closed，拒绝访问（无穿透）。
4. **Given** 启动器与 orchestrator + workspace 共存部署，**When** 执行部署编排，**Then** 三者网络互通、健康检查通过、入口可达。

---

### Edge Cases

- OAuth IdP（GitHub/Google）临时不可达或回调超时如何处理？→ 展示可读错误与重试，不签发 JWT。
- workspace 启动时端口范围耗尽如何处理？→ 状态转 `error`，向用户提示端口耗尽，不静默失败。
- 同一浏览器多个 OAuth provider 交叉登录（GitHub 已登录又点 Google 且邮箱相同）如何处理？→ 按邮箱合并到同一用户，刷新 JWT。
- OAuth 账户与本地账户邮箱相同但属于不同真实用户（邮箱被复用）如何处理？→ 默认按邮箱合并（P3 范围内可接受的风险，记录于 Assumptions）；更严格的归属校验推迟。
- 用户在 workspace 启动中途关闭浏览器如何处理？→ 启动为异步，orchestrator 继续推进状态机，用户重新进入列表可见最终状态。
- JWT 在前端持有期间过期如何处理？→ 用 refresh token 静默续签；refresh 也失效则导向登录页。
- 统一反代目标 workspace 处于 `stopped`/`error` 如何处理？→ 返回可读提示并引导用户启动，不暴露 5xx 原始错误。
- launcher 反代遇到大文件上传/长连接（如 terminal WebSocket / novnc）如何处理？→ 反代需透传 WebSocket 与长连接，不截断（在 plan 阶段细化）。

---

## Requirements *(mandatory)*

### Functional Requirements

#### OAuth 与身份（并存签发 JWT）

- **FR-001**: 系统 MUST 支持 GitHub 与 Google 两个 OAuth 2.0 provider 作为登录入口，与 P2 本地账户（邮箱密码）并存。
- **FR-002**: OAuth 登录成功后，orchestrator MUST 签发与本地账户登录完全等价的 P2 JWT（access + refresh，同套 TTL/轮换/jti 唯一性），前端统一以 JWT 调用 orchestrator API。
- **FR-003**: 系统 MUST 在首次 OAuth 登录时自动创建用户记录（或按邮箱合并到既有本地账户），并持久化 `oauth_accounts`（provider / provider_user_id / user_id / email）关联，无需额外注册步骤。
- **FR-004**: 系统 MUST 使用标准 OAuth 2.0 Authorization Code 流程，`state` 参数防 CSRF，回调 `code` 经 IdP token 端点交换，全程安全回调。
- **FR-005**: 系统 MUST 拒绝伪造/过期/被撤销的 OAuth 回调（state 不匹配、code 失效、token 校验失败），不签发 JWT。
- **FR-006**: 已登录的本地账户 MUST 能主动绑定/解绑 OAuth 身份（同一 provider 同一外部账号不可重复绑定到不同本地账户）。
- **FR-007**: OAuth provider 凭证（client_id / client_secret）MUST 经环境变量注入，不硬编码、不落库、不进前端构建产物；开发态提供可配置的 mock/占位以脱离真实 IdP 运行。

#### 启动器前端（React 19 + shadcn/ui + tailwind，函数式）

- **FR-008**: 启动器 MUST 提供登录视图：本地账户登录表单 + GitHub/Google OAuth 入口；登录成功后持久化 JWT（access + refresh）并以已登录态进入工作台。
- **FR-009**: 启动器 MUST 提供 workspace 列表视图：展示当前用户拥有/参与的 workspace（名称、slug、状态、端口、创建时间、角色），仅显示有权的 workspace。
- **FR-010**: 启动器 MUST 提供 workspace 创建向导：模板选择 → 名称/slug 填写（含前端校验：格式、长度、冲突预检）→ 确认 → 提交；提交对接 P2 workspace 创建 API。
- **FR-011**: 启动器 MUST 在列表中暴露 workspace 生命周期操作（启动 / 停止 / 暂停 / 恢复 / 删除），操作结果实时反映到状态；非法状态转换被禁用并提示。
- **FR-012**: 启动器 MUST 提供监控面板：按 workspace 展示运行状态 + 审计事件流（4 类），支持筛选与分页；数据来自 P2 既有 workspace/审计 API。
- **FR-013**: 启动器 MUST 实现 JWT 过期静默续签（refresh）与失效重定向登录，会话失效有明确提示。
- **FR-014**: 启动器 MUST 对所有 API 错误（4xx/5xx）展示用户可读的反馈，不暴露原始堆栈/内部细节。
- **FR-015**: 启动器前端 MUST 以函数式风格组织（函数组件 + hooks + 不可变状态更新），技术栈固定为 React 19 + shadcn/ui + tailwind css（stakeholder 约束）。

#### Workspace 真实启动部署补齐（orchestrator-as-controller）

- **FR-016**: orchestrator 容器 MUST 获得在宿主机编排 workspace 的能力——可访问 docker daemon（socket）与 docker compose CLI，并可见 workspace compose 模板文件与构建产物挂载点，使 P2 已实现的 compose 编排（up/down/pause/unpause）在容器内真实生效。
- **FR-017**: 「创建 → 启动 → 全部 healthy → 可访问」MUST 形成端到端闭环：用户在启动器启动 workspace 后，该 workspace 的 cap-* 容器组真实拉起、健康，并经统一入口可达。
- **FR-018**: workspace 启动失败（端口耗尽 / 镜像缺失 / compose 错误）MUST 使状态转 `error` 并保留可读错误信息，供启动器展示；不静默失败或卡在 `starting`。
- **FR-019**: orchestrator 编排 workspace 的代码路径 MUST 沿用 P2 已交付实现（compose_runner / 状态机 / 端口分配），P3 仅补齐运行时部署与必要的 Phase 5（cap-nginx auth_request 配置渲染），不重写编排内核。

#### Launcher 统一反代入口

- **FR-020**: 启动器 MUST 作为独立服务对外暴露单一入口域名，未登录导向登录页，已登录进入工作台。
- **FR-021**: 启动器 MUST 以统一路径前缀（如 `/ws/{slug}/`）反代各已启动 workspace 的 cap-nginx，鉴权由 orchestrator `auth_request` 完成（注入可信 header），单域名 + 路径区分 workspace。
- **FR-022**: 反代 MUST 透传 workspace 内的长连接与 WebSocket（terminal / novnc），不截断、不缓冲破坏实时性。
- **FR-023**: orchestrator 不可达时，反代鉴权 MUST fail-closed（拒绝），无未认证请求穿透到 workspace（延续 P2 `auth_request` fail-closed 契约）。
- **FR-024**: 反代目标 workspace 不存在 / 未启动 / 越权时，MUST 返回用户可读提示，不暴露 5xx 内部错误。

#### 兼容性（P1 / P2 不变量）

- **FR-025**: P1 单 workspace 模式（`AUTH_MODE=none`，无 orchestrator / launcher）MUST 仍可独立运行，不依赖 P3（零迁移延续 P2 FR-022）。
- **FR-026**: P2 的编排内核（compose_runner / 状态机 / 端口分配 / JWT / auth_request / 审计）MUST 在 P3 下行为不变；OAuth 与 launcher 为新增式扩展，不改动 P2 既有路由与契约。
- **FR-027**: P2 已登录用户的本地账户与 JWT MUST 在 P3 下继续可用，OAuth 为并存入口而非替换。

#### P3 明确不做（依据范围确认）

- **FR-NI-1**: P3 不实现 Snapshot 编排（create / restore / export）。
- **FR-NI-2**: P3 不实现计量计费（`usage_metrics`）。
- **FR-NI-3**: P3 不实现 workspace 内文件级权限细化（沿用 P2 workspace 级归属/角色）。
- **FR-NI-4**: P3 不接入 SAML / 企业 IdP（仅 GitHub + Google OAuth 2.0）。
- **FR-NI-5**: P3 不实现移动端原生应用（响应式 Web 即可）。
- **FR-NI-6**: P3 不重新启用 Chromium sandbox 或收紧 Shell 策略（沿用 P1 宽松基线）。

#### 测试

- **FR-028**: 启动器前端 MUST 有自动化测试（组件/视图级，含列表/向导/监控/登录关键路径），关键交互有覆盖。
- **FR-029**: orchestrator 的 OAuth 扩展（回调校验 / 自动建户 / 邮箱合并 / JWT 签发 / 绑定解绑）MUST 有测试，含伪造回调拒绝用例。
- **FR-030**: 系统 MUST 提供 E2E：经启动器 OAuth 登录 → 创建 workspace → 真实启动到 healthy → 经统一入口访问 workspace UI → 验证越权被拒 → 验证审计落库。
- **FR-031**: P3 部署补齐（orchestrator-as-controller）MUST 有验证：orchestrator 容器内能真实拉起一个 workspace compose project 到全部 healthy。
- **FR-032**: P1 单 workspace 模式与 P2 编排/认证/审计回归测试 MUST 在 P3 下全绿（零迁移验证，延续 P2 FR-022/FR-026）。

### Key Entities *(include if feature involves data)*

- **OAuthAccount（新增）**：外部身份与本地用户的关联（provider / provider_user_id / user_id / email），一个 user 可绑定多个 provider；与 P2 `user` 一对多；用于 OAuth 登录定位/创建本地用户。新增 `oauth_accounts` 表，是 P2 `data-model` 的纯增量扩展。
- **LauncherSession**：启动器前端会话，由 P2 JWT（access + refresh）承载，无独立服务端持久化；过期经 refresh 续签。
- **WorkspaceProxyRoute（运行时）**：launcher 反代 workspace 的路由映射（slug → workspace 内部 cap-nginx 端点），由 orchestrator workspace 元数据 + 路径前缀动态解析，非持久实体。
- **Launcher（服务）**：独立部署的 React SPA + 反代网关，与 orchestrator + workspace 共存同网络，是终端用户的单一入口。
- **（复用 P2 不变）**：Workspace / User / WorkspaceOwner / Template / AuditLog / TrustedHeader / AuthMiddleware 在 P3 下语义不变（详见 P2 Key Entities）；OAuth 仅扩展 User 的身份来源，不改动既有关系。

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用户从启动器点击 GitHub/Google 登录到进入已登录工作台，正常路径耗时 < 10 秒（含 IdP 跳转）。
- **SC-002**: 用户在创建向导提交合法 workspace 到列表中出现该记录，端到端 < 3 秒；非法输入 100% 被前端校验拦截。
- **SC-003**: 用户对 `created` workspace 点「启动」到全部 cap-* healthy 状态转 `running`，耗时 < 120 秒（P1 镜像已构建，延续 P2 SC-001）。
- **SC-004**: `running` workspace 经统一入口（单域名 + 路径）100% 可加载其桌面 UI（novnc 等）；越权访问 100% 被 `auth_request` 拒绝（403）。
- **SC-005**: 监控面板在 workspace 内触发操作后，相关审计事件在刷新/轮询周期内可见；状态变更在面板反映。
- **SC-006**: OAuth 回调伪造/过期/撤销的拒绝率 100%（不签发 JWT）；OAuth 登录所得 JWT 与本地账户 JWT 在鉴权/审计行为上 100% 一致。
- **SC-007**: 启动器前端关键路径（登录 / 列表 / 创建向导 / 监控）有自动化测试覆盖；orchestrator OAuth 扩展单元测试覆盖率与 P2 持平（≥ 80%）。
- **SC-008**: P1 单 workspace 模式 + P2 编排/认证/审计回归 E2E 在 P3 下全绿（零迁移验证）；P2 既有 API 契约无破坏性变更。
- **SC-009**: 同一启动器域名下，已登录用户可经路径访问任意自己有权且已启动的 workspace，跨 workspace 鉴权隔离 100%（A 用户无法访问 B 用户的 workspace UI）。
- **SC-010**: orchestrator 不可达时，所有 workspace 统一入口路径 100% fail-closed，无未认证请求穿透到 workspace 内部。

---

## Assumptions

- 宿主机已安装 Docker 24+ 与 docker compose v2；P1 的 4 个 base 镜像 + 7 个 cap-* 镜像与 P2 的 orchestrator 镜像均已构建可用（P3 复用，不重建）。
- 启动器前端技术栈由 stakeholder 指定固定为 **React 19 + shadcn/ui + tailwind css + 函数式风格**（函数组件 + hooks + 不可变状态更新），不引入重型 FP 状态库（除非 plan 阶段论证必要）。
- 启动器作为**独立容器服务**部署，与 orchestrator + postgres 同网络（`orchestrator-net` 或扩展网络），对外单一入口；不嵌入 orchestrator 进程内托管。
- orchestrator 容器在 P3 获得**编排者**身份：挂载宿主机 docker socket、镜像内含 docker compose CLI、挂载 workspace compose 模板与构建上下文、配置 workspace compose 工作目录。此为部署变更，具体挂载点/网络/权限在 plan 阶段细化。
- GitHub 与 Google 的 OAuth App 凭证（client_id / client_secret）与回调 URL 由环境变量注入；开发态提供可配置 mock（绕过真实 IdP 完成本地闭环测试），凭证不进前端构建产物、不落库。
- OAuth 账户与本地账户按**邮箱自动合并**（默认策略）；邮箱被不同真实用户复用的极端冲突在 P3 范围内接受（记录风险），更严格归属校验推迟。
- workspace 统一入口采用**路径前缀**（`/ws/{slug}/`）在单域名下区分，延续 P2「端口前缀 + 路径」最小可用形态；基于子域名（`{slug}.{host}`）的 DNS 分发推迟。
- 启动器反代 workspace 时复用 P2 已设计的 cap-nginx `auth_request` + 可信 header 机制（Phase 5），P3 补齐该配置在真实部署下的渲染与挂载注入。
- 审计 4 类（shell.exec / fs.write / browser.action / gui.action）在 P3 下沿用 P2 落库机制，监控面板仅消费 P2 审计查询 API，不引入新审计源。
- 启动器前端的会话安全（JWT 存储 / XSS / CSRF）遵循 Web 安全常规实践（HttpOnly cookie 或内存+短期 localStorage 二选一，在 plan 阶段决策并记录权衡）。
- 终端实时连接（terminal WebSocket / novnc）经反代透传，具体超时/缓冲策略在 plan 阶段细化。
