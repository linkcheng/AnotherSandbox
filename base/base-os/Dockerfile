# syntax=docker/dockerfile:1.6
FROM ubuntu:24.04

LABEL org.opencontainers.image.title="base-os"
LABEL org.opencontainers.image.description="AI 沙箱基础镜像（公共祖先）"

# 时区与 locale
ENV TZ=Asia/Shanghai \
    LANG=zh_CN.UTF-8 \
    LANGUAGE=zh_CN:zh \
    LC_ALL=zh_CN.UTF-8 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl wget git vim tini locales sudo tzdata \
        gnupg lsb-release procps && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    sed -i '/zh_CN.UTF-8/s/^# //g' /etc/locale.gen && \
    sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen && \
    update-locale LANG=zh_CN.UTF-8 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 默认用户（uid 1000，Ubuntu 24.04 自带 ubuntu 用户需先删除）
RUN userdel -r ubuntu 2>/dev/null || true && \
    useradd -m -u 1000 -s /bin/bash sandbox && \
    echo "sandbox ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

WORKDIR /workspace
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash"]
