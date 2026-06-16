# cap-mcp

AI 个人沙箱 MCP server。P1 阶段为最小占位实现，仅暴露健康检查端点；US2/US3 将扩展为基于 fastmcp 与 playwright 的 MCP 工具服务。

## 契约

- `GET /health` → `{"status": "ok"}`

## 开发

```bash
uv sync --extra dev
uv run pytest tests/ -v --cov=cap_mcp --cov-report=term-missing --cov-fail-under=80
```

## 运行

```bash
uv run uvicorn cap_mcp.main:app --host 0.0.0.0 --port 8940
```
