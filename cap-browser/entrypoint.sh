#!/bin/bash
# cap-browser 启动脚本：Xvnc + Openbox + Chromium + websocat
# 对应 spec.md FR-022/FR-023；tasks.md T034。
set -e

# 启动 D-Bus session（Openbox 需要）
dbus-uuidgen --ensure
mkdir -p /run/dbus && dbus-daemon --system --fork

# 首次启动生成 VNC passwd（base-vnc build 时跳过，避免 buildkit alternatives 问题）
mkdir -p /root/.vnc
if [ ! -f /root/.vnc/passwd ]; then
    printf "123456\n" | vncpasswd -f > /root/.vnc/passwd
    chmod 600 /root/.vnc/passwd
fi

# 启动 Xvnc（DISPLAY=:1）
Xvnc :1 -geometry 1280x800 -depth 24 -rfbauth /root/.vnc/passwd -rfbport 5901 &
sleep 2

# 启动 Openbox 窗口管理器
DISPLAY=:1 openbox-session &

# 启动 Chromium（CDP on 9222，no-sandbox 是 P1 安全降级）
# 用绝对路径 /usr/bin/chromium（install_chromium.sh 已确保存在；同时建立 chromium-browser 符号链接）
# 参数参考 .archive/workspaces-images kasm 脚本的 CHROME_ARGS
DISPLAY=:1 /usr/bin/chromium \
    --no-sandbox \
    --password-store=basic \
    --ignore-gpu-blocklist \
    --disable-gpu \
    --no-first-run \
    --disable-features=TranslateUI \
    --simulate-outdated-no-au='Tue, 31 Dec 2099 23:59:59 GMT' \
    --remote-debugging-port=9222 \
    --remote-debugging-address=0.0.0.0 \
    --user-data-dir=/workspace/.chromium &

# 启动 websocat（VNC → WebSocket 桥接，端口 6080）
# noVNC 客户端通过 WS 连接此端口
websocat -t ws-l:0.0.0.0:6080 tcp:127.0.0.1:5901 &

# 等待任一进程退出
wait -n
