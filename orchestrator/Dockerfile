# syntax=docker/dockerfile:1.6
# Orchestrator 镜像（P2），基于 P1 base-python312（含 uv）
# multi-stage：test/prod 共享（FR-027）。默认构建 prod（docker compose target: prod）。

FROM base-python312 AS base
WORKDIR /app

# ─── prod ───
FROM base AS prod
# P3 (T039, R4)：装 docker CLI + compose v2 plugin，使 orchestrator 容器获编排者身份。
# compose_runner.py 调 `docker compose -p ...`，需 docker 主程序 + compose plugin 两者。
# 固定版本 pin；静态二进制下载到标准路径；--fail 快速失败；chmod +x。
# 注：仅 CLI，不含 dockerd（守护进程靠宿主机 docker.sock 挂载，见 docker-compose.orchestrator.yml）。
ARG DOCKER_CLI_VERSION=27.5.1
ARG DOCKER_COMPOSE_VERSION=v2.29.7
RUN mkdir -p /usr/local/lib/docker/cli-plugins /usr/local/bin && \
    curl -fsSL "https://download.docker.com/linux/static/stable/x86_64/docker-${DOCKER_CLI_VERSION}.tgz" \
        | tar -xz --strip-components=1 -C /usr/local/bin docker/docker && \
    chmod +x /usr/local/bin/docker && \
    curl -fsSL "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-linux-x86_64" \
        -o /usr/local/lib/docker/cli-plugins/docker-compose && \
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose && \
    docker compose version
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH" \
    DOCKER_CONFIG=/usr/local/lib/docker
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
