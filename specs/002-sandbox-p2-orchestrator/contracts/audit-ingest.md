# Contract: Audit Ingest（cap-* → Orchestrator）

**Date**: 2026-06-19
**Source**: [spec.md](../spec.md) FR-016/017/018 · [research.md](../research.md) R9 · `.archive/sandbox-design.md` §8.8.6

workspace 内 cap-terminal / cap-mcp / cap-agent 在关键操作后，经 HTTP 把结构化事件上报到 Orchestrator 写入 `audit_logs`。本契约定义事件结构、端点、best-effort 语义。

---

## 1. 端点

### POST `${ORCHESTRATOR_URL}/api/v1/audit/ingest`

- `ORCHESTRATOR_URL`：注入 workspace 各 cap-* 的环境变量（R3，如 `http://host.docker.internal:8000`）
- **无需 JWT**：本端点由 workspace 内受信 cap-* 调用（sandbox-net 隔离保证来源可信）；P2 不对其额外鉴权（FR-016 来源 = workspace 内服务）
- 请求/响应均 JSON

```json
// Request
{
  "workspace_id": "ws-alice-001-...",
  "actor_user_id": "a1b2c3d4-...",        // 可空（agent 操作）
  "event_type": "shell.exec",
  "source": "cap-terminal",
  "detail": { "command": "echo hi", "exit_code": 0 },
  "success": true
}

// 201 Response（成功写库）
{ "id": 1234567, "created_at": "2026-06-19T04:05:00Z" }

// 400 字段缺失/非法 event_type 或 source
```

---

## 2. 事件字段（对应 data-model §2.5）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| workspace_id | UUID (string) | 是 | 事件归属 workspace（注入 workspace 的 env `WORKSPACE_ID`） |
| actor_user_id | UUID (string) | 否 | 操作者；从可信 header `X-User-Id` 读（R8）；空=agent |
| event_type | string | 是 | `shell.exec` / `fs.write` / `browser.action` / `gui.action` |
| source | string | 是 | `cap-terminal` / `cap-mcp` / `cap-agent`（自报） |
| detail | object (JSONB) | 是 | 结构化 payload（见 §3 各类型约定） |
| success | boolean | 是 | 操作是否成功 |

---

## 3. 各 event_type 的 detail 约定（P2 最小集）

### shell.exec（source: cap-terminal）
```json
{ "command": "echo hi", "exit_code": 0, "duration_ms": 12 }
```
> P2 安全简化：不记录完整 stdout/stderr（仅 exit_code + 耗时 + 命令），避免日志膨胀与敏感数据落库。完整审计策略推迟。

### fs.write（source: cap-mcp）
```json
{ "path": "/workspace/shared/note.md", "bytes": 2 }
```
> 仅记路径 + 字节数，不记内容。

### browser.action（source: cap-mcp）
```json
{ "action": "navigate", "url": "https://example.com", "ok": true }
```
> `action` ∈ navigate/click/type/snapshot/screenshot。

### gui.action（source: cap-agent）
```json
{ "action_type": "click", "x": 100, "y": 200, "ok": true }
```

---

## 4. Best-effort 语义（FR-018 / R9 / SC-004）

- **上报绝不阻塞业务**：cap-* 用 `asyncio.create_task` fire-and-forget，不 await 在请求关键路径
- **超时丢弃**：httpx `timeout=2s`；超时/连接拒绝 → log warning + 丢弃，不重试不缓冲
- **Orchestrator 不可达**：业务命令仍 100% 成功（SC-004 不变量）
- **写库失败**（Orchestrator 收到但 DB 写失败）：Orchestrator 返回 5xx，cap-* 同样丢弃，不重试

> P2 不做持久化重试队列（R9 Alternatives：推迟）。审计是可观测支柱，非强一致账本。

---

## 5. cap-* 实现约定（audit_client.py）

各 cap-* 新增 `services/audit_client.py`，统一接口：

```python
class AuditClient:
    def __init__(self, orch_url: str, workspace_id: str, source: str): ...
    async def report(self, event_type: str, detail: dict, *,
                     actor_user_id: str | None, success: bool) -> None:
        # fire-and-forget：create_task + timeout=2s + 异常吞掉 log.warning
        ...
```

- 注入：`WORKSPACE_ID`（workspace 创建时由 compose env 注入）、`ORCHESTRATOR_URL`、`SOURCE`（各服务硬编码自身名）
- actor_user_id：从请求的 `X-User-Id` header 读取（cap-agent 中间件解析，见 [`cap-agent-auth-middleware.md`](./cap-agent-auth-middleware.md)）；cap-terminal/cap-mcp 经其调用链透传

---

## 6. 调用点（P2 覆盖范围）

| 服务 | 调用点 | event_type |
|------|--------|-----------|
| cap-terminal | `/api/v1/exec` 返回后 | `shell.exec` |
| cap-mcp | `fs_write` 工具返回后 | `fs.write` |
| cap-mcp | `browser_*` 工具返回后 | `browser.action` |
| cap-agent | `/gui/actions` 返回后 | `gui.action` |

> `fs_read`/`browser_snapshot` 等只读操作 P2 不上报（避免噪音）；只上报"写/动"类操作。

---

## 引用
- spec.md：FR-016/017/018/019
- research.md：R9（best-effort 机制）
- data-model.md：§2.5 audit_logs schema、§5.4/5.6 查询/写入
- `.archive/sandbox-design.md` §8.8.6（审计归 Orchestrator）
