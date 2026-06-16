# syntax=docker/dockerfile:1.6
FROM base-python312:latest AS builder

# 安装 tmux（cap-terminal 共享 PTY）
USER root
RUN apt-get update && apt-get install -y --no-install-recommends tmux && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先拷依赖文件，利用 uv 缓存
COPY pyproject.toml ./
COPY README.md ./
COPY src/ ./src/

# 同步生产依赖到 .venv（项目内）
RUN uv sync --no-dev --no-install-project

# ============ runtime（prod） ============
FROM base-python312:latest AS prod

# runtime 也需要 tmux
USER root
RUN apt-get update && apt-get install -y --no-install-recommends tmux && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/pyproject.toml /app/

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/src"

# tmux socket 目录（默认 /tmp/tmux-<uid>；显式 1777 防 perm 问题）
RUN mkdir -p /tmp/tmux && chmod 1777 /tmp/tmux

EXPOSE 7682
CMD ["uvicorn", "cap_terminal.main:app", "--host", "0.0.0.0", "--port", "7682"]

# ============ test target ============
FROM builder AS test
RUN uv sync --extra dev
CMD ["uv", "run", "pytest", "tests/", "--cov=cap_terminal", "--cov-report=term-missing"]
