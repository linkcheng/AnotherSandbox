# Contract: cap-agent Auth Middleware（AUTH_MODE 双模式）

**Date**: 2026-06-19
**Source**: [spec.md](../spec.md) FR-014/022/023 · [research.md](../research.md) R8

定义 cap-agent 的认证中间件契约——通过 `AUTH_MODE` 环境变量在 P1（`none`）与 P2（`orchestrator`）之间切换，**业务路由代码零改动**（FR-023 / SC-006）。本契约约束中间件的接口、两种模式行为、与可信 header 的关系。

> **起点核对（plan R8）**：M5 实现前先核对 P1 cap-agent 是否已有中间件层。若无，本契约的 `BaseAuthMiddleware` 即为新增抽象层；P1 业务路由（health/shell/gui/cdp）保持不变，仅在 app 注册中间件。

---

## 1. 环境变量

| 变量 | 取值 | 默认 | 说明 |
|------|------|------|------|
| `AUTH_MODE` | `none` / `orchestrator` | `none`（延续 P1） | 认证模式切换（§4.8.6） |
| `AUTH_FAILURE_MODE` | `fail-closed` / `fail-open` | `fail-closed` | 仅 nginx 层用（R4）；cap-agent 不做降级，header 缺失即 401 |

---

## 2. 中间件抽象（`cap-agent/src/cap_agent/core/auth.py`）

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class BaseAuthMiddleware(BaseHTTPMiddleware):
    """认证中间件基类。子类实现 authenticate()。"""
    PUBLIC_PATHS = {"/v1/health"}   # healthcheck 永远公开（不应被鉴权阻塞）

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)
        identity = await self.authenticate(request)
        if identity is None:
            return JSONResponse(status_code=401, content={"error": {"code": "unauthorized"}})
        request.state.user = identity     # 注入业务路由可读的身份
        return await call_next(request)

    async def authenticate(self, request: Request) -> Identity | None:
        raise NotImplementedError
```

```python
class Identity(BaseModel):
    user_id: str | None        # X-User-Id（orchestrator 模式）；none 模式为 None
    workspace_id: str | None
    permissions: str | None    # owner/collaborator/viewer
```

---

## 3. 两种模式

### 3.1 `AUTH_MODE=none`（P1，默认）— NoAuthMiddleware

```python
class NoAuthMiddleware(BaseAuthMiddleware):
    async def authenticate(self, request: Request) -> Identity | None:
        return Identity(user_id=None, workspace_id=None, permissions=None)
```
- **所有请求视为本地受信**，不读任何 header（§8.6.1）
- 行为与 P1 完全一致——回归测试 SC-006 验证
- `request.state.user` 仍被注入（空 Identity），业务路由若引用 user 字段不会 KeyError

### 3.2 `AUTH_MODE=orchestrator`（P2）— OrchestratorHeaderAuthMiddleware

```python
class OrchestratorHeaderAuthMiddleware(BaseAuthMiddleware):
    REQUIRED_HEADERS = ("X-User-Id", "X-Workspace-Id", "X-Permissions")

    async def authenticate(self, request: Request) -> Identity | None:
        values = {h: request.headers.get(h) for h in self.REQUIRED_HEADERS}
        if any(v is None for v in values.values()):
            return None          # 缺 header → 401（请求未经 Orchestrator/nginx）
        return Identity(user_id=values["X-User-Id"],
                        workspace_id=values["X-Workspace-Id"],
                        permissions=values["X-Permissions"])
```
- **不做 JWT 校验**（JWT 已由 Orchestrator `/verify` 完成，§8.6.3 关注点分离）
- **信任 `X-*` header**——前提是请求必经 cap-nginx auth_request（网络隔离 + nginx 覆盖，见 [`trusted-headers.md`](./trusted-headers.md) §4）
- 缺任一 header → 401（fail-closed 在 cap-agent 层：未经网关的直连请求必被拒）

---

## 4. 启动期模式选择（main.py）

```python
def build_auth_middleware(mode: str) -> BaseAuthMiddleware:
    if mode == "orchestrator":
        return OrchestratorHeaderAuthMiddleware()
    return NoAuthMiddleware()

# main.py
app.add_middleware(<由 AUTH_MODE 决定的具体子类>)
```

- 启动期读 `AUTH_MODE` 一次，注册对应中间件（运行期不切换）
- 业务路由（shell/gui/cdp/health）**完全不感知**模式——只从 `request.state.user` 读身份（或忽略）

---

## 5. 业务路由影响（零改动验证）

| 路由 | P1（none） | P2（orchestrator） | 改动 |
|------|-----------|--------------------|------|
| `GET /v1/health` | 公开 200 | 公开 200（PUBLIC_PATHS） | 无 |
| `POST /v1/shell/exec` | 不校验，执行 | 读 `request.state.user` 透传给 audit（actor），执行 | 路由逻辑不变（仅可选读 user 给审计） |
| `GET /gui/screenshot` / `POST /gui/actions` | 不校验 | 同上 | 无 |
| `/cdp/*` | 不校验 | 同上 | 无 |

> 中间件统一拦截，路由内**不写**鉴权代码——这是零迁移的保证（FR-023）。audit 上报从 `request.state.user.user_id` 读 actor（见 [`audit-ingest.md`](./audit-ingest.md) §5）。

---

## 6. 测试要求（M5）

- **unit**（`cap-agent/tests/unit/test_auth.py`）：
  - `none` 模式：任意请求 → 200，`request.state.user` 非空对象但字段 None
  - `orchestrator` + 三 header 齐全 → 200，Identity 字段正确
  - `orchestrator` + 缺一 header → 401
  - `/v1/health` 两种模式均公开
- **回归**（SC-006）：P1 单 workspace（`AUTH_MODE=none`，无 Orchestrator）E2E 全绿，业务路由行为不变

---

## 引用
- spec.md：FR-014（中间件）/FR-022（P1 独立可用）/FR-023（业务路由零改动）/SC-006
- research.md：R8（可信 header 透传）
- trusted-headers.md：§4 防伪造不变量、§5 P1 兼容
