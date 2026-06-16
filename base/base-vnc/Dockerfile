# syntax=docker/dockerfile:1.6
FROM base-os:latest

LABEL org.opencontainers.image.title="base-vnc"
LABEL org.opencontainers.image.description="GUI 显示栈（Xvnc + Openbox + 字体），不含 tmux/ttyd"

ENV DISPLAY=:1

# TigerVNC（Xvnc）+ Openbox + 字体 + websocat
# 注：noVNC 静态文件由 cap-nginx 提供，此处只装显示栈
RUN apt-get update && apt-get install -y --no-install-recommends \
        tigervnc-standalone-server tigervnc-common \
        openbox \
        fonts-noto-cjk fonts-wqy-microhei fonts-wqy-zenhei \
        xterm dbus-x11 x11-utils x11-xserver-utils \
        libgl1 libegl1 libglx-mesa0 libgbm1 \
        ca-certificates curl xz-utils && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    curl -fsSL --retry 5 --retry-delay 3 -o /usr/local/bin/websocat \
        https://github.com/vi/websocat/releases/download/v1.14.1/websocat.x86_64-unknown-linux-musl && \
    chmod +x /usr/local/bin/websocat && \
    mkdir -p /root/.vnc

CMD ["Xvnc", "-geometry", "1280x800"]
