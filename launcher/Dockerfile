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

# 运行阶段：nginx 托管 SPA + 反代 /api → orchestrator
FROM nginx:1.27-alpine AS runtime

# 模板渲染依赖（envsubst）
RUN apk add --no-cache bash gettext

COPY nginx/launcher.conf.tmpl /etc/nginx/templates/launcher.conf.tmpl
COPY --from=builder /app/dist /usr/share/nginx/html

# 模板变量（默认值，可被 docker run/compose env 覆盖）
ENV ORCHESTRATOR_UPSTREAM="orchestrator:8000" \
    LAUNCHER_PORT="8080"

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -qO- "http://127.0.0.1:${LAUNCHER_PORT}/" >/dev/null 2>&1 || exit 1

EXPOSE 8080
