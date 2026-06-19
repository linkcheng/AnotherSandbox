# syntax=docker/dockerfile:1.6
# Orchestrator 镜像（P2），基于 P1 base-python312（含 uv）
# multi-stage：test/prod 共享（FR-027）。默认构建 prod（docker compose target: prod）。

FROM base-python312 AS base
WORKDIR /app

# ─── prod ───
FROM base AS prod
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn orchestrator.main:app --host 0.0.0.0 --port 8000"]

# ─── test（含 dev 依赖）───
FROM base AS test
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --all-extras --no-install-project
COPY src ./src
COPY tests ./tests
COPY alembic.ini ./
COPY migrations ./migrations
RUN uv sync --frozen --all-extras
ENV PATH="/app/.venv/bin:$PATH"
CMD ["pytest"]
