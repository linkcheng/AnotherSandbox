# Research: AI 个人沙箱 P2 — Orchestrator 编排与认证层

**Date**: 2026-06-19
**Source**: [spec.md](./spec.md) · [plan.md](./plan.md) · `.archive/sandbox-design.md` §8 / §8.6 / §8.8 / §9.3 / §11

本文档解决 plan.md Technical Context 的 4 项待定技术决策（R1-R4），并记录 5 项关键技术/库选型（R5-R9）。每项给出 **Decision / Rationale / Alternatives**。

---

## R1. Workspace 软删除保留期与硬删除

**Decision**：默认**软删除保留 7 天**后由后台清理任务硬删除；提供 `purge` 动作立即硬删除。保留期由 `WORKSPACE_RETENTION_DAYS` 环境变量配置（默认 7）。

**硬删除触发条件**（任一）：
1. 软删除后超过 `WORKSPACE_RETENTION_DAYS`（后台周期任务扫描 `deleted_at`）
2. 用户显式 `purge`
3. `WORKSPACE_RETENTION_DAYS=0`（删除即硬删，适用于测试/CI）

**硬删除动作**：`docker compose -p {ws} down -v --remove-orphans`（移除容器 + 网络 + 卷）+ 删除宿主机 Profile 目录 + 删 DB 行。

**Rationale**：
- 误删可恢复（7 天窗口）符合多租户 SaaS 惯例
- `down -v` 确保卷不残留（避免磁盘泄漏，§8.9 存储增长风险）
- 可配置保留期覆盖 CI（=0）与生产（=30）不同需求

**Alternatives**：
- 立即硬删除：简单但误删不可逆，多租户不可接受
- 永久软删除（只标记不清理）：磁盘泄漏，违背 §8.9
- 回收站 UI：P2 无前端（FR-NI-3），推迟

**关联**：FR-004 状态机 DELETED；spec Edge Case "workspace 删除时仍有活跃连接"。

---

## R2. 端口前缀（PORT_PREFIX）自动分配

**Decision**：每个 workspace 分配**单个对外端口**（仅 cap-nginx，其余 cap-* 在 workspace 内部 sandbox-net 不对外）。范围 `WORKSPACE_PORT_START`（默认 **8100**）递增，存 `workspaces.external_port`。分配策略：查询 DB 中未被软删除 workspace 占用的端口，取最小可用值；并发创建用 DB 唯一约束兜底（重试）。

**Rationale**：
- 设计文档 §8.3 的 `PORT_PREFIX=81 → 8180` 是双位前缀方案，仅支持 ~9 个 workspace，扩展性差
- 实际上 P1 单 workspace 只有 cap-nginx 一个对外端口（§1.1.3 / §11.3），workspace 内 cap-* 全 `expose`。P2 每个 workspace 复用同一模型——**只需 1 个对外端口**
- 8100-8199 默认支持 100 个并发 workspace（SC-005 要求 ≥3，富余）；范围可通过 `WORKSPACE_PORT_START` / `WORKSPACE_PORT_END` 调整
- DB 唯一约束（`external_port` partial index `WHERE deleted_at IS NULL`）防并发分配冲突，比内存游标更可靠（Orchestrator 可重启）

**端口冲突处理**：若宿主机端口已被非 Orchestrator 进程占用，`docker compose up` 失败 → workspace 置 ERROR + 重新分配下一个端口重试（≤2 次）。

**Alternatives**：
- 双位前缀（§8.3 原案）：扩展性差，放弃
- 多端口块（每 ws 占 nginx+vnc+code 多端口）：浪费且复杂，P1 模型证明单端口足够
- 基于域名路由（`{ws}.{host}`）：设计文档 §8.8.7 列为推迟项（需 DNS/通配证书），P2 用端口实现最小可用

**关联**：FR-005；spec Assumption "端口分配采用自动分配"。

---

## R3. Orchestrator ↔ Workspace 网络互通形态

**Decision**：workspace 容器通过 **`host.docker.internal`** 出站访问宿主机上的 Orchestrator。workspace 模板为所有需出站的容器（cap-nginx 做 auth_request、cap-terminal/cap-mcp/cap-agent 做审计上报）统一注入：
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```
Orchestrator 的访问地址通过环境变量 `ORCHESTRATOR_URL`（如 `http://host.docker.internal:8000`）注入到 workspace 各 cap-*。

**网络拓扑**：
```
宿主机
├── orchestrator-net (bridge): [orchestrator, postgres]   ← Orchestrator publish 8000 到宿主机
└── ws-alice (独立 project + 独立 sandbox-net): [cap-nginx, cap-agent, ...]
      │  extra_hosts: host.docker.internal → host-gateway
      │  env: ORCHESTRATOR_URL=http://host.docker.internal:8000
      └── 出站 → host:8000 (Orchestrator)
```

**Rationale**：
- 保持 workspace 间**完全隔离**（各自独立 sandbox-net，互不可达，SC-005）——共享网络会破坏隔离
- `host.docker.internal` 是 Docker 官方跨平台机制（macOS/Windows 内置；Linux 通过 `host-gateway` 映射），不需要把 Orchestrator 加入 workspace 网络
- Orchestrator publish 端口到宿主机（`8000:8000`），workspace 经 host-gateway 访问——Orchestrator 不需知道 workspace 的内部网络
- 审计上报与 auth_request 共用同一路径，统一 `ORCHESTRATOR_URL`

**连通性保障**：
- workspace 启动后，cap-* 对 `ORCHESTRATOR_URL` 做启动期探活（best-effort，失败不阻断启动——审计本就 best-effort；auth_request 失败按 R4 fail-closed）
- Orchestrator 侧 `/verify` 与 `/api/v1/audit/ingest` 仅依赖 Orchestrator 自身可用，无需反向连入 workspace

**Alternatives**：
- 把 Orchestrator 容器加入每个 workspace 的 sandbox-net：破坏 workspace 间隔离（Orchestrator 成跨 workspace 桥），且 compose -p 跨 project 网络共享语义复杂，放弃
- Orchestrator 监听 host network (`network_mode: host`)：与多 workspace 端口隔离冲突，且 macOS 不支持 host networking，放弃
- workspace 容器 `network_mode: host`：彻底破坏 sandbox-net 隔离，放弃

**关联**：FR-013（auth_request）、FR-016（审计上报）、SC-005（隔离）、R2/R4。

---

## R4. Fail-closed / Fail-open 鉴权降级策略

**Decision**：默认 **fail-closed**——`auth_request` 到 Orchestrator 失败（超时 / 5xx / 连接拒绝）时，cap-nginx **拒绝**该请求（返回 403）。由环境变量 `AUTH_FAILURE_MODE` 控制（`fail-closed` 默认 / `fail-open` 仅受信内网调试）。

**nginx 实现要点**（`nginx.workspace.conf.tmpl`）：
- `auth_request /_auth;` 指向 internal location → `proxy_pass http://host.docker.internal:8000/api/v1/verify;`
- Orchestrator `/verify` 返回：**2xx**（放行，并设置可信 header）/ **401**（未认证）/ **403**（越权）
- nginx `auth_request` 对上游 **401/403 直接透传**拒绝；对 **5xx/超时默认返回 500**
- fail-closed：用 `error_page 500 502 503 504 = @auth_fail_closed;`（internal location 返回 403）
- fail-open：`error_page 500 502 503 504 = @auth_pass;`（放行）——**仅当 `AUTH_FAILURE_MODE=fail-open` 时渲染此分支**

**Rationale**：
- 多租户公网场景，"无法确认身份"等价于"不可信"，应拒绝（安全优先于可用性，spec Assumption）
- fail-open 仅作受信内网调试逃生口，默认关闭，避免误配导致未认证穿透（SC-008）
- 显式 `error_page` 映射消除 nginx auth_request 5xx→500 的语义混淆（plan R3）

**测试覆盖**（M4）：
- Orchestrator 健康 + 合法 JWT → 2xx 放行
- Orchestrator 健康 + 无/坏 JWT → 401
- Orchestrator 健康 + 越权 → 403
- Orchestrator 关闭/超时 + `fail-closed` → 403
- Orchestrator 关闭 + `fail-open` → 放行

**Alternatives**：
- 始终 fail-open：不安全，多租户不可接受
- 始终 fail-closed 不可配：内网调试困难（Orchestrator 开发期频繁重启）
- 应用层（cap-agent）做降级而非 nginx 层：违背关注点分离（§8.6.3），cap-agent 不应持有降级决策

**关联**：FR-013/FR-014/FR-015、spec Edge Case "auth_request 超时/不可达"、SC-008。

---

## R5. JWT 库选型

**Decision**：**PyJWT**（签发 + 校验）+ **passlib[bcrypt]**（密码哈希）。

**Rationale**：
- PyJWT 是 Python JWT 事实标准，单一职责、维护活跃、依赖少（对比 python-jose 较重且维护滞后）
- passlib 提供可升级的密码哈希抽象（bcrypt → argon2 平滑迁移），避免硬绑单一算法
- 与 FastAPI 生态契合，type hint 友好

**Token 设计**：
- access token：短 TTL（默认 15min），claim 含 `sub`(user_id) / `email` / `exp` / `iat` / `type=access`
- refresh token：长 TTL（默认 7d），`type=refresh`，存 DB（可吊销）
- 算法 HS256（对称，`JWT_SECRET_KEY`）；生产可切 RS256（推迟，P2 用 HS256 简化密钥管理）

**Alternatives**：
- python-jose：功能全但偏重，P2 不需要 JWE/JWK 复杂特性
- authlib：Starlette 集成好但抽象层厚，P2 需求简单（签发+校验+refresh），过度
- 复用 cap-agent 的认证：cap-agent 设计上不持 JWT（§8.6.3 关注点分离），认证归 Orchestrator

---

## R6. Alembic 迁移策略

**Decision**：**SQLAlchemy 2.x declarative + Alembic autogenerate**，迁移文件纳入版本控制（`orchestrator/migrations/versions/`）。

**Rationale**：
- SQLAlchemy + Alembic 是 §8.8.3 既定技术栈，与团队 Python 栈一致
- autogenerate 减少手写 SQL，但每次迁移需人工 review（autogenerate 对 enum/索引推断不完美）
- 迁移文件即代码（Code as Cache），可重建 DB

**流程**：
- 初始迁移 `0001_init`：建 5 表（users/workspaces/workspace_owners/templates/audit_logs）+ 索引
- 后续 schema 变更：改 ORM model → `alembic revision --autogenerate` → review → commit
- Orchestrator 启动期 `alembic upgrade head`（lifespan）；失败 fail-fast 拒启动（Edge Case / R7）

**测试**：
- Integration 用 testcontainers-postgres 跑真实 `upgrade head` 验证迁移可应用
- 迁移幂等性：`downgrade base` + `upgrade head` 往返不报错

**Alternatives**：
- 手写 SQL 迁移：易错、不可重建
- 不用迁移（create_all 直接建表）：无版本历史，生产 schema 演进失控
- 其他迁移工具：生态小众

---

## R7. docker compose 子进程编排（compose_runner）

**Decision**：用 **`asyncio.create_subprocess_exec`** 直接调 `docker compose`（**非 `shell=True`**），参数列表化避免注入。

**核心 API**（`compose_runner.py`）：
- `up(project, env_file, wait=True)` → `docker compose -p {project} --env-file {env} up -d --wait`
- `down(project, volumes=True)` → `docker compose -p {project} down -v --remove-orphans`
- `stop(project)` / `pause(project)` / `unpause(project)`
- `ps(project)` → 解析 JSON（`docker compose ps --format json`）聚合 healthcheck

**Rationale**：
- `create_subprocess_exec`（非 shell）天然防注入：project 名/workspace 名作为独立 argv 传入，不经 shell 解释
- `--wait` 让 `up` 阻塞到 healthy（或失败），compose_runner 据退出码判定 STARTING→RUNNING / →ERROR
- async 使 Orchestrator 可并发管理多 workspace（每个 lifecycle 操作一个 task）

**状态机联动**（`workspace_lifecycle.py`）：
- `start`：CREATED/STOPPED → STARTING → 调 `up` → 成功 RUNNING / 失败 ERROR
- `stop`：RUNNING/PAUSED → 调 `down`(volumes=False) → STOPPED
- `pause`/`resume`：调 `pause`/`unpause` 子进程
- 任何 compose 失败：捕获退出码+stderr，状态 ERROR，返回结构化错误（Edge Case "半启动"）

**测试**：
- Unit：mock `create_subprocess_exec`，断言 argv（含 project/env_file 正确插值）+ 退出码→状态映射
- Integration：真实 `docker compose -p itest-{rand} up/down`（临时 project，测后 `down -v` 清理）

**Alternatives**：
- `docker` Python SDK（docker-py）：compose 支持弱（需手写 compose 解析），放弃
- shell=True 拼命令：注入风险，放弃
- Docker HTTP socket API：低层，重写 compose 逻辑成本高，放弃

---

## R8. nginx auth_request 配置与可信 header 透传

**Decision**：workspace 的 `nginx.workspace.conf.tmpl` 对所有 location 统一加 `auth_request /_auth;`，internal location 反代到 Orchestrator `/api/v1/verify`。Orchestrator 在 `/verify` 响应中**回写可信 header**（`X-User-Id` 等），nginx 用 `auth_request_set` 捕获 + `proxy_set_header` 注入上游 cap-*。

**关键配置片段**（详见 `contracts/orchestrator-rest-api.md`）：
```nginx
location = /_auth {
    internal;
    proxy_pass http://host.docker.internal:8000/api/v1/verify;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
    proxy_set_header X-Original-URI $request_uri;
    proxy_set_header Authorization $http_authorization;
}

location /v1/ {
    auth_request /_auth;
    auth_request_set $x_user_id $upstream_http_x_user_id;
    auth_request_set $x_workspace_id $upstream_http_x_workspace_id;
    auth_request_set $x_permissions $upstream_http_x_permissions;
    proxy_set_header X-User-Id $x_user_id;
    proxy_set_header X-Workspace-Id $x_workspace_id;
    proxy_set_header X-Permissions $x_permissions;
    proxy_pass http://cap-agent:9000;
    error_page 500 502 503 504 = @auth_closed;   # fail-closed 默认
}
location @auth_closed { internal; return 403; }
```

**Rationale**：
- `auth_request` 是 nginx 原生子请求鉴权（§11.5），无需额外网关进程
- `auth_request_set` 捕获 Orchestrator 响应 header，再 `proxy_set_header` 注入上游——这是"可信 header"的注入路径（§8.6.2）

**防伪造要点**：
- cap-agent 的 `OrchestratorHeaderAuthMiddleware` 信任 header 的前提是"请求必经 nginx auth_request"——外部不可直连 cap-agent:9000（sandbox-net 隔离保证）
- nginx 用 `proxy_set_header`（覆盖）而非透传客户端值，外部伪造的 `X-User-Id` 会被覆盖

**Alternatives**：
- 应用层（cap-agent）校验 JWT：违背 §8.6.3 关注点分离（cap-agent 见业务不见密码）
- 独立网关进程（如 oauth2-proxy）：引入额外组件，P2 用 nginx 原生足够
- mTLS：P2 过重，推迟

---

## R9. 审计 best-effort 上报机制

**Decision**：各 cap-* 的 `audit_client.py` 用 **fire-and-forget 异步上报**：`asyncio.create_task` 发起 httpx POST，**不 await 在业务请求关键路径**；超时丢弃；Orchestrator `/api/v1/audit/ingest` 同步写库（单表 INSERT）。

**上报流程**（cap-terminal shell.exec 为例）：
```
shell.exec 处理 → 返回响应给调用方（关键路径，不阻塞）
            ↘ asyncio.create_task(audit_client.report(
                  workspace_id, actor, "shell.exec", detail, success))
                  → httpx.post(ORCHESTRATOR_URL/audit/ingest, json=..., timeout=2s)
                  → 失败：log warning + 丢弃（不入队重试，避免无限堆积）
```

**Rationale**：
- best-effort 的本质是"审计失败不能影响业务"（FR-018 / SC-004）
- `create_task` 解耦：业务响应延迟 = 0（审计完全后台）
- 不做持久化重试队列（P2 简化）：避免本地状态漂移；超限即丢，可接受（审计是可观测支柱非强一致账本）
- Orchestrator 侧单表 INSERT + 索引（§8.8.4 idx_audit_workspace_time），写入快

**事件结构**（见 `contracts/audit-ingest.md`）：`workspace_id` / `actor_user_id` / `event_type` / `source` / `detail`(JSONB) / `success` / `created_at`。

**测试**（M6）：
- 正常：shell.exec 后 audit_logs 有记录
- 不可达：mock httpx 超时/拒绝，断言业务命令仍成功（SC-004）
- 字段：event_type/source/detail 正确

**Alternatives**：
- 同步上报+重试：阻塞业务，违背 FR-018
- 本地文件缓冲+批量上报：P2 过度（需持久化+重放），推迟；P2 用内存/丢弃
- 消息队列（Kafka/Redis）：P2 过重（§8.8.3 不引入独立日志/队列系统）

**关联**：FR-016/017/018/019、SC-004、§8.8.6。

---

## 决策汇总（速查）

| 编号 | 决策 | 关键参数/默认 |
|------|------|---------------|
| R1 | 软删除保留 7 天后硬删；可 purge 立即删 | `WORKSPACE_RETENTION_DAYS=7` |
| R2 | 每 workspace 1 对外端口，8100 递增 | `WORKSPACE_PORT_START=8100` |
| R3 | workspace 经 host.docker.internal 出站到 Orchestrator | `ORCHESTRATOR_URL` + `extra_hosts: host-gateway` |
| R4 | 默认 fail-closed，可配 fail-open | `AUTH_FAILURE_MODE=fail-closed` |
| R5 | PyJWT + passlib[bcrypt]；HS256 | access 15min / refresh 7d |
| R6 | SQLAlchemy 2.x + Alembic autogenerate | 启动期 `upgrade head` |
| R7 | asyncio.create_subprocess_exec 调 docker compose（非 shell） | `--wait` + 退出码判定 |
| R8 | nginx auth_request + auth_request_set 透传可信 header | proxy_set_header 覆盖防伪造 |
| R9 | fire-and-forget 异步审计，超时丢弃不重试 | timeout=2s，不入业务关键路径 |

所有 4 项待定决策（R1-R4）已解决，无残留 NEEDS CLARIFICATION。Phase 1 设计（data-model / contracts）可基于此推进。
