# cap-terminal

AI 个人沙箱 shell 共享与执行服务。P1 阶段为最小占位实现，仅暴露健康检查端点；US2/US3/US4 将扩展为完整 shell-exec API。

## 契约

- `GET /api/v1/health` → `{"status": "ok"}`

## 开发

```bash
uv sync --extra dev
uv run pytest tests/ -v --cov=cap_terminal --cov-report=term-missing --cov-fail-under=80
```

## 运行

```bash
uv run uvicorn cap_terminal.main:app --host 0.0.0.0 --port 7682
```
