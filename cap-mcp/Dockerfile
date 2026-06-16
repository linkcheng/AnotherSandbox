# syntax=docker/dockerfile:1.6
FROM base-python312:latest AS builder

WORKDIR /app

# 先拷依赖文件，利用 uv 缓存
COPY pyproject.toml ./
COPY README.md ./
COPY src/ ./src/

# 同步生产依赖到 .venv（项目内）
RUN uv sync --no-dev --no-install-project

# ============ runtime（prod） ============
FROM base-python312:latest AS prod

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/pyproject.toml /app/

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/src"

EXPOSE 8940
CMD ["uvicorn", "cap_mcp.main:app", "--host", "0.0.0.0", "--port", "8940"]

# ============ test target ============
FROM builder AS test
RUN uv sync --extra dev
CMD ["uv", "run", "pytest", "tests/", "--cov=cap_mcp", "--cov-report=term-missing"]
