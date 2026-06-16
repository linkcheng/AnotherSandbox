#!/usr/bin/env bash
# 安装 Chromium（绕过 Ubuntu 24.04 snap transitional package）。
#
# 参考实现：.archive/workspaces-images/src/ubuntu/install/chromium/install_chromium.sh
# 做法：从 Debian Bookworm 源装真·chromium deb（非 snap），适配 P1 容器场景。
set -ex

# 1. 移除 Ubuntu 24.04 自带的 snap transitional package（如已安装）
apt-get update
apt-get remove -y chromium-browser-l10n chromium-codecs-ffmpeg chromium-browser 2>/dev/null || true

# 2. 安装依赖（curl/software-properties-common 用于加源；Chromium 运行时库）
apt-get install -y --no-install-recommends \
    curl software-properties-common \
    fonts-liberation libappindicator3-1 libnss3 libxss1 \
    libasound2t64 libatk-bridge2.0-0 libatk1.0-0 libcairo2 \
    libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 libnspr4 \
    libpango-1.0-0 libpangocairo-1.0-0 libx11-xcb1 libxcb1 \
    libxcomposite1 libxcursor1 libxdamage1 libxfixes3 libxi6 \
    libxrandr2 libxrender1 libxshmfence1 libxtst6 xdg-utils

# 3. 添加 Debian Bookworm 源（用于 chromium deb 包）
mkdir -p /etc/apt/keyrings
curl -fsSL https://ftp-master.debian.org/keys/archive-key-12.asc \
    -o /etc/apt/keyrings/debian-archive-key-12.asc
echo "deb [signed-by=/etc/apt/keyrings/debian-archive-key-12.asc] http://deb.debian.org/debian bookworm main" \
    > /etc/apt/sources.list.d/debian-bookworm.list
echo -e "Package: *\nPin: release a=bookworm\nPin-Priority: 100" \
    > /etc/apt/preferences.d/debian-bookworm

# 4. 安装 chromium（来自 bookworm，绕过 snap）
apt-get update
apt-get install -y --no-install-recommends chromium chromium-sandbox

# 5. 清理 bookworm 源（避免污染后续 apt）
rm -f /etc/apt/sources.list.d/debian-bookworm.list
rm -f /etc/apt/preferences.d/debian-bookworm
rm -f /etc/apt/keyrings/debian-archive-key-12.asc
apt-get update

# 6. 建立符号链接兼容 entrypoint（chromium vs chromium-browser）
if [ ! -f /usr/bin/chromium-browser ]; then
    ln -sf /usr/bin/chromium /usr/bin/chromium-browser
fi

# 7. 清理
apt-get autoclean
rm -rf /var/lib/apt/lists/* /var/tmp/*

# 8. 验证
chromium --version
echo "✓ chromium 安装成功"
