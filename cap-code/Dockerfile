# syntax=docker/dockerfile:1.6
FROM base-node24:latest

LABEL org.opencontainers.image.title="cap-code"
LABEL org.opencontainers.image.description="AI 个人沙箱 cap-code：code-server（VS Code in browser）"

# 安装 code-server（VS Code in browser）
RUN curl -fsSL https://code-server.dev/install.sh | sh && \
    mkdir -p /workspace/.vscode

# P1 阶段 auth=none（FR-024）
ENV AUTH=none

EXPOSE 8081

CMD ["code-server", \
     "--bind-addr", "0.0.0.0:8081", \
     "--auth", "none", \
     "--user-data-dir", "/workspace/.vscode", \
     "/workspace/code"]
