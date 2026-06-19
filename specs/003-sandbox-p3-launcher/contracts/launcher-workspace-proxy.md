# Contract: Launcher 统一反代 Workspace（入口拓扑）

**Date**: 2026-06-20
**Source**: [spec.md](../spec.md) FR-020~024 · [research.md](../research.md) R5/R6 · P2 [trusted-headers.md](../002-sandbox-p2-orchestrator/contracts/trusted-headers.md)

定义 launcher 容器（nginx）作为**单一对外入口**的路由/鉴权/反代契约：托管 SPA + 反代 orchestrator API + 以统一路径前缀反代各 workspace 的 cap-nginx，鉴权经 orchestrator `auth_request` 注入可信 header。终端用户只记忆一个域名即可管理并访问所有 workspace（FR-020/021，SC-009）。

**对外入口**：`http://<launcher-host>:${LAUNCHER_PORT:-8080}`
**内部依赖**：orchestrator（`${ORCH_URL}`）、各 workspace cap-nginx（动态 host:port）。

---

## 1. 路由表

| 路径 | 方法 | 目标 | 鉴权 | 说明 |
|------|------|------|------|------|
| `/` | GET | SPA 静态产物 | 未登录→登录页；已登录→工作台 | `try_files $uri /index.html`（client-side routing 回退） |
| `/api/` | * | orchestrator:8000 | 透传（orchestrator 自鉴权） | 反代 `/api/v1/...`，剥前缀；cookie/Bearer 透传 |
| `/ws/{slug}/` | *（含 WS） | workspace cap-nginx | `auth_request` 子请求 | **workspace 统一入口**（FR-021），见 §2/§3 |
| `/assets/`、`/static/` | GET | SPA 静态 | 无 | 构建产物（js/css/图片） |

---

## 2. `/ws/{slug}/` 反代与鉴权链路（核心，FR-021/023）

```
浏览器 GET /ws/alice-dev/novnc/  (携带 access_token cookie)
   │
   ▼
launcher nginx  location /ws/<slug>/
   │   ① auth_request /_authsub;            # 子请求（仅鉴权，不返回体）
   │      internal location /_authsub {
   │          proxy_pass ${ORCH_URL}/api/v1/verify?workspace=<slug>;
   │          proxy_set_header X-Original-URI $uri;
   │      }
   ▼
orchestrator POST /api/v1/verify?workspace=<slug>
   │   校验 access_token cookie/Bearer + 该 user 对 <slug> 的归属（P2 既有）
   │   2xx=放行 / 401 未认证 / 403 无归属
   ▼
   ◄── auth_request_set 捕获响应 header（X-User-Id/X-Workspace-Id/X-Permissions，P2 trusted-headers）──
   │   ② proxy_pass http://<workspace-host>:<port>;     # 解析 {slug}→host:port（§4）
   │      proxy_set_header X-User-Id $x_user_id;        # 覆盖防伪造
   │      ...
   ▼
workspace cap-nginx  →  cap-agent/cap-browser/...  (可信 header 已注入)
```

- **fail-closed**（FR-023/SC-010）：orchestrator 不可达或 auth_request 非 2xx → nginx 返回 403（`error_page 403 /workspace-denied.html`），**无未认证请求穿透**。
- **越权**（SC-009）：bob 访问 alice 的 `/ws/alice-dev/` → orchestrator verify 返回 403 → 拒绝。

---

## 3. WebSocket / 长连接透传（FR-022）

`/ws/{slug}/` 下含 terminal（WebSocket）、novnc（WebSocket）等长连接，nginx 反代须透传：

```nginx
location /ws/<slug>/ {
    auth_request /_authsub;
    proxy_pass http://<workspace-host>:<port>;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";      # 或映射 $connection_upgrade
    proxy_set_header Host $host;
    proxy_read_timeout 3600s;                   # 长连接不早断
    proxy_buffering off;                        # terminal/novnc 流式不缓冲
}
```

- 不满足透传 → terminal/novnc 不可用（FR-022 失败）。

---

## 4. `{slug}` → workspace host:port 解析（research R5 未决项）

workspace 的内部地址（cap-nginx 的 `external_port`，data-model §2.3）需在反代时解析。两种方案，M4 实现时择一：

- **方案 A（resolver + 变量）**：workspace 容器名遵循约定（如 `<slug>-cap-nginx`）+ 同 Docker 网络，nginx 用 `resolver 127.0.0.11 valid=10s;` + `proxy_pass http://$slug-cap-nginx:80;` 动态解析。零额外服务，依赖容器命名约定。
- **方案 B（路由表渲染）**：launcher 启动/定时从 orchestrator `/api/v1/workspaces` 拉运行中 workspace 列表，envsubst 渲染 `location` 块。显式但需刷新。

> **决策**：优先**方案 A**（最小化、零轮询），命名约定记入 workspace compose 模板（`container_name: ${WORKSPACE_SLUG}-cap-nginx`）。方案 B 作为 fallback。

---

## 5. 错误降级（FR-024，UX）

| 场景 | 行为 |
|------|------|
| workspace slug 不存在 | orchestrator verify 404 → launcher 返回可读页「workspace 不存在」 |
| workspace 未启动（非 running） | launcher 探测状态（或 verify 拒绝）→ 「请先启动 workspace」+ 跳转列表 |
| 越权（无归属） | verify 403 → 「无权访问该 workspace」 |
| orchestrator 不可达 | fail-closed → 「服务暂不可用，请稍后重试」（不透 5xx） |

---

## 6. 与 P2 契约的关系（零迁移）

- launcher `auth_request` 复用 P2 `/api/v1/verify` + 可信 header 契约（trusted-headers.md），**不新增鉴权逻辑**。
- workspace cap-nginx 的 Phase 5 auth_request 配置（R6）由 workspace compose 模板 envsubst 渲染，双层鉴权（launcher + workspace）纵深防御。
- P2 单 workspace 模式（`AUTH_MODE=none`，无 launcher）仍独立可用（FR-025）——launcher 是 P3 新增的可选入口。
