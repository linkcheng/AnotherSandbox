# syntax=docker/dockerfile:1.6
FROM base-os:latest

LABEL org.opencontainers.image.title="cap-nginx"
LABEL org.opencontainers.image.description="AI 个人沙箱 cap-nginx：HTTP/WebSocket 反向代理"

# 安装 nginx + wget/curl（healthcheck 与调试用）
RUN apt-get update && apt-get install -y --no-install-recommends \
        nginx wget curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 清除默认 site 配置（避免与自定义 nginx.conf 冲突）
RUN rm -f /etc/nginx/sites-enabled/default

COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

# 关闭 daemon 模式，让 nginx 在前台跑（容器生命周期与 nginx 一致）
CMD ["nginx", "-g", "daemon off;"]
