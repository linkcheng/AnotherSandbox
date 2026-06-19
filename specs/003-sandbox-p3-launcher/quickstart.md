# Quickstart: AI 个人沙箱 P3 — React 启动器与 SSO/OAuth 验证手册

**Date**: 2026-06-20 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

端到端验证 P3 四块增量（OAuth / 启动器 / 真实启动闭环 / 统一反代）。所有凭证/ID 为合成虚构值。详细端点见 [oauth-rest-api.md](./contracts/oauth-rest-api.md) / [launcher-workspace-proxy.md](./contracts/launcher-workspace-proxy.md) / [frontend-api-contract.md](./contracts/frontend-api-contract.md)。

---

## 前置

- P1 镜像（4 base + 7 cap-*）+ P2 orchestrator 镜像已构建（`make build && make build-orchestrator`）
- Docker 24+ / docker compose v2；`.env` 已配（`make up-orchestrator` 可用）
- P3 新增 env（写入 `.env`）：
  ```
  OAUTH_MOCK=true                       # 离线/验证用 mock provider（生产 false）
  OAUTH_GITHUB_CLIENT_ID=xxx            # 真实 IdP 时填
  OAUTH_GITHUB_CLIENT_SECRET=xxx
  OAUTH_GOOGLE_CLIENT_ID=xxx
  OAUTH_GOOGLE_CLIENT_SECRET=xxx
  OAUTH_REDIRECT_URL=http://localhost:8080/api/v1/auth/oauth
  LAUNCHER_PORT=8080
  ```
- `make build-launcher` 构建 launcher 镜像（multi-stage：node 构建 SPA → nginx 托管 + 反代）

---

## 场景 1：启动 P3 stack（orchestrator + postgres + launcher）

```bash
make up-p3          # docker compose -f docker-compose.orchestrator.yml up -d --wait（含 launcher）
# 健康检查
curl -s localhost:8000/readyz          # {"status":"ready","db":"ok"}   (orchestrator)
curl -s localhost:8080/                # launcher SPA HTML（未登录→登录页）
```
**预期**：三服务 healthy；launcher:8080 返回登录页 HTML（SC-008 部署基线）。

---

## 场景 2：OAuth 登录（US1 / SC-001 / SC-006）

### 2a. mock 模式（离线闭环，`OAUTH_MOCK=true`）
```bash
# 浏览器访问（整页跳转，curl 模拟追踪 302）
curl -i -c cookies.txt "localhost:8080/api/v1/auth/oauth/github/login?redirect=/workspaces"
# → 302 → mock callback → 建户(dev-github@local) → 签 JWT → Set-Cookie access_token/refresh_token → 302 /workspaces
```
**预期**：响应含 `Set-Cookie: access_token=...; HttpOnly` 与 `Set-Cookie: refresh_token=...; HttpOnly`，302 到 `/workspaces`（FR-002/003）。

### 2b. 邮箱合并（US1-2）
```bash
# 先注册本地账户 a@b.c
curl -s -X POST localhost:8000/api/v1/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"a@b.c","password":"pw123456"}'
# 再用相同邮箱的 OAuth 登录（mock 配置该邮箱）→ 应合并到同一 user，不新建
```
**预期**：oauth_accounts 行 user_id 指向既有本地 user，users 表无重复（SC-006）。

### 2c. 伪造回调拒绝（US1-4 / FR-005）
```bash
curl -i "localhost:8080/api/v1/auth/oauth/github/callback?code=x&state=tampered" 
# state 不匹配
```
**预期**：400 / 重定向登录页带 `?error=oauth_failed`，不签 JWT（SC-006）。

---

## 场景 3：workspace 列表 + 创建向导（US2 / SC-002）

> 经 launcher 浏览器 UI 操作；此处给底层 API 等效命令（前端经 `/api` 反代同样路径）。

```bash
# 带 cookie 列表（空）
curl -s -b cookies.txt localhost:8080/api/v1/workspaces      # {"items":[]}
# 创建（向导提交的等效）
curl -s -b cookies.txt -X POST localhost:8080/api/v1/workspaces \
  -H 'Content-Type: application/json' -d '{"name":"alice-dev","slug":"alice-dev","template":"minimal"}'
# → {"id":"ws-...","slug":"alice-dev","status":"created",...}
```
**预期**：列表 < 3s 出现新 workspace，状态 `created`（SC-002）；非法 slug 被前端/后端校验拒绝。

---

## 场景 4：真实启动 workspace（US3 / SC-003 / FR-016~018）

```bash
curl -s -b cookies.txt -X POST localhost:8080/api/v1/workspaces/<id>/start
# 轮询状态（前端列表 5s 轮询）
curl -s -b cookies.txt localhost:8080/api/v1/workspaces/<id>   # status: starting → running
docker ps --format '{{.Names}}' | grep alice-dev               # 真实容器组：<slug>-cap-nginx/agent/browser/...
```
**预期**：orchestrator 容器内经 docker.sock 真实拉起 cap-* 容器组，全部 healthy 后状态 `running`（< 120s，SC-003）。验证 orchestrator-as-controller 部署补齐生效（FR-016/017）。

---

## 场景 5：统一入口访问 workspace UI（US3 / FR-020~022 / SC-004）

```bash
# 经 launcher 统一入口（cookie 鉴权 + auth_request）
curl -i -b cookies.txt "localhost:8080/ws/alice-dev/"          # → workspace cap-nginx 桌面入口
curl -i -b cookies.txt "localhost:8080/ws/alice-dev/novnc/"    # novnc（WebSocket 透传）
```
**预期**：返回 workspace UI（非 5xx）；WebSocket 升级成功（FR-022）；浏览器访问可见桌面。

---

## 场景 6：越权拒绝 + fail-closed（SC-009 / SC-010 / FR-023）

```bash
# 用 bob 的 cookie 访问 alice 的 workspace
curl -i -b bob_cookies.txt "localhost:8080/ws/alice-dev/"      # → 403
# orchestrator 不可达（停 orchestrator 后）
make stop-orchestrator-server  # 仅停 orchestrator 进程模拟
curl -i -b cookies.txt "localhost:8080/ws/alice-dev/"          # → fail-closed 拒绝页
```
**预期**：越权 403（SC-009）；orchestrator 不可达 fail-closed，无穿透（SC-010）。

---

## 场景 7：监控面板（US4 / SC-005 / FR-012）

```bash
# 触发 workspace 内操作产生审计（经 workspace MCP/terminal 执行 shell 命令）
# 监控面板查询审计（前端 Monitor 页 10s 轮询的等效）
curl -s -b cookies.txt "localhost:8080/api/v1/audit?workspace=<id>&limit=20"
# {"items":[{"type":"shell.exec","actor_user_id":"...","created_at":"...","summary":"..."}],...}
```
**预期**：审计事件在轮询周期内可见（SC-005），含 4 类 type、actor、时间、摘要。

---

## 场景 8：P1 / P2 回归（零迁移，SC-008 / FR-032）

```bash
make test-e2e               # P1 单 workspace（AUTH_MODE=none）回归
make test-orchestrator      # P2 orchestrator unit + integration
make test-e2e-p3            # P3 完整 E2E（场景 1-7 自动化）
```
**预期**：三层全绿；P1/P2 在 `0002_oauth` 迁移后行为不变（零迁移验证）。

---

## 自动化一键验证

```bash
make test-e2e-p3            # 覆盖 OAuth→创建→真实启动→统一访问→越权→审计 全链路 + P1/P2 回归
```
