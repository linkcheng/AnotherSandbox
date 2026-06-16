# syntax=docker/dockerfile:1.6
FROM base-vnc:latest

LABEL org.opencontainers.image.title="cap-browser"
LABEL org.opencontainers.image.description="AI 个人沙箱 cap-browser：Chromium + Xvnc + noVNC WebSocket 桥"

# 安装 Chromium（从 Debian Bookworm 源，绕过 Ubuntu 24.04 snap transitional）
# 参考实现：.archive/workspaces-images/src/ubuntu/install/chromium/install_chromium.sh
COPY install_chromium.sh /tmp/install_chromium.sh
RUN bash /tmp/install_chromium.sh && rm /tmp/install_chromium.sh

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 9222 6080

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/entrypoint.sh"]
