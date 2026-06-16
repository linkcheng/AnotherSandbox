# syntax=docker/dockerfile:1.6
FROM base-os:latest

LABEL org.opencontainers.image.title="base-python312"

ENV UV_VERSION=0.4.18 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:/opt/python/bin:${PATH}"

# 安装 uv 与 Python 3.12（UV_INSTALL_DIR 强制路径，避免新版默认 /root/.cargo/bin）
RUN curl -fsSL https://astral.sh/uv/install.sh \
        | env UV_VERSION=${UV_VERSION} UV_INSTALL_DIR=/usr/local/bin sh && \
    uv python install 3.12 && \
    uv venv /opt/venv --python 3.12 && \
    chmod -R 755 /opt

CMD ["python3"]
