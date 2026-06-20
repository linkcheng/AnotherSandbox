# Launcher 镜像：multi-stage node:24 构建 SPA → nginx 托管 + 反代
# specs/003-sandbox-p3-launcher/plan.md T007
FROM node:24-slim AS builder
WORKDIR /app

# 先装依赖（利用 layer cache）
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund

# 再拷源码构建
COPY tsconfig.json tsconfig.node.json vite.config.ts index.html ./
COPY tailwind.config.js postcss.config.js components.json ./
COPY src ./src
COPY public ./public
RUN npm run build

# 运行阶段：nginx 托管 SPA + 反代 /api → orchestrator + /ws/<slug>/ → workspace
FROM nginx:1.27-alpine AS runtime

# bash（entrypoint 用）+ gettext（envsubst）。wget 已在 nginx:alpine。
RUN apk add --no-cache bash gettext

# 删除 nginx 自带默认 server（listen 80 + location / → html），避免与 launcher.conf
# 的 server 冲突（两者都 listen 80 + location /，default.conf 会抢占 /api 等请求 → 404）
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx/launcher.conf.tmpl /etc/nginx/templates/launcher.conf.tmpl
# P3 (T048)：降级页放 nginx html 根（launcher.conf.tmpl 的 error_page 指向 /workspace-denied.html）
COPY nginx/workspace-denied.html /usr/share/nginx/html/workspace-denied.html
COPY --from=builder /app/dist /usr/share/nginx/html
# P3：自定义 envsubst（白名单渲染，避免官方 20 脚本破坏 nginx 运行时变量）
# 禁用官方 20-envsubst-on-templates.sh（它会用默认模式替换所有 $VAR，破坏 $slug 等）
RUN rm -f /docker-entrypoint.d/20-envsubst-on-templates.sh
COPY docker-entrypoint.sh /docker-entrypoint.d/20-launcher-envsubst.sh
RUN chmod +x /docker-entrypoint.d/20-launcher-envsubst.sh

# 模板变量（默认值，可被 docker run/compose env 覆盖）
# 容器内 nginx 固定 listen 80；LAUNCHER_PORT 仅用于宿主机端口映射（见 compose）
ENV ORCH_URL="http://orchestrator:8000" \
    ORCHESTRATOR_UPSTREAM="orchestrator:8000" \
    LAUNCHER_PORT="80"

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -qO- "http://127.0.0.1:80/" >/dev/null 2>&1 || exit 1

EXPOSE 80
