# syntax=docker/dockerfile:1.6
# Orchestrator 镜像（P2），基于 P1 base-python312（含 uv）
# multi-stage：test/prod 共享（FR-027）

FROM base-python312 AS base
WORKDIR /app

# ─── prod ───
FROM base AS prod
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY alembic.ini migrations ./migrations
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
# 启动期 alembic upgrade head（fail-fast）+ uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn orchestrator.main:app --host 0.0.0.0 --port 8000"]

# ─── test（含 dev 依赖）───
FROM base AS test
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --all-extras --no-install-project
COPY src tests migrations alembic.ini ./
RUN uv sync --frozen --all-extras
ENV PATH="/app/.venv/bin:$PATH"
CMD ["pytest"]
