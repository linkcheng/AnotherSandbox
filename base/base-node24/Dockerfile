FROM base-os:latest

LABEL org.opencontainers.image.title="base-node24"

ENV NODE_VERSION=24.17.0 \
    NPM_CONFIG_GLOBALCONFIG=/etc/npmrc \
    PATH="/opt/node/bin:${PATH}"

# 安装 Node.js 24（npmmirror 国内镜像）+ pnpm
# 注：dpkg --print-architecture 返回 amd64/aarch64；nodejs.org 用 x64/arm64
RUN ARCH=$(dpkg --print-architecture | sed 's/amd64/x64/;s/aarch64/arm64/') && \
    NODE_TARBALL="/tmp/node.tar.gz" && \
    curl -fsSL --retry 5 --retry-delay 2 \
        -o "${NODE_TARBALL}" \
        "https://cdn.npmmirror.com/binaries/node/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${ARCH}.tar.gz" && \
    test -s "${NODE_TARBALL}" && \
    tar -xz -C /opt -f "${NODE_TARBALL}" && \
    rm "${NODE_TARBALL}" && \
    ln -sf /opt/node-v${NODE_VERSION}-linux-${ARCH} /opt/node && \
    /opt/node/bin/npm config set registry https://registry.npmmirror.com && \
    /opt/node/bin/npm install -g pnpm@latest

CMD ["node"]
