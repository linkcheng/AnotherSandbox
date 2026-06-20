# 部署手册

**Date**: 2026-06-18
**适用范围**：P1（本地/单机/受信网络）

## 前置要求

- **OS**：Linux x86_64/arm64（推荐）或 macOS（Chromium 性能略低）
- **Docker**：24+ 与 docker compose v2
- **端口**：默认 80 空闲；占用时设 `PORT=8080`
- **磁盘**：≥ 6GB（镜像 5GB + workspace）
- **内存**：≥ 8GB（7 容器稳态 ~5GB + 主机开销）

## 一键部署

```bash
# 1. 克隆
git clone <repo-url> sandbox && cd sandbox

# 2. 配置环境
cp .env.example .env
# 编辑 .env，设置 WORKSPACE_DIR（默认 ~/sandbox-workspace）
mkdir -p "${WORKSPACE_DIR:-$HOME/sandbox-workspace}"

# 3. 构建（首次约 5-8 分钟）
make build

# 4. 启动（< 90 秒到 healthy）
make up

# 5. 验证
curl http://localhost/v1/health
# {"status":"ok"}

# 6. 浏览器访问
# - http://localhost/novnc/        远程桌面
# - http://localhost/code-server/  VS Code
# - http://localhost/jupyter/      JupyterLab
# - http://localhost/terminal/     Web Terminal
```

## 平台差异

### Linux（推荐）

- 直接 `make up` 即可
- bind mount 性能最优（SC-006 < 100ms）
- Chromium `--no-sandbox` 无副作用

### macOS

- Docker Desktop → Settings → Resources → 给 ≥ 8GB 内存
- bind mount 经 VFS 套娃，文件 IO 延迟 ~100-300ms（接受范围）
- Apple Silicon：镜像自动 arm64 构建

## 端口冲突排查

| 现象 | 排查 |
|------|------|
| `make up` 后 80 端口占用 | `sudo lsof -i :80`；改 `.env: PORT=8080` |
| `bind: address already in use` | `docker compose down` 后 `make up` |
| cap-nginx healthcheck 不通 | 检查 `docker compose logs cap-nginx` |

## 日志与监控

```bash
make logs                 # 跟踪所有服务
docker compose logs -f cap-agent    # 单服务跟踪
docker compose ps         # 查看健康状态
docker compose stats      # 实时资源占用
```

## 停止与清理

```bash
make down                 # 停止容器（保留 volume 与 workspace）
make clean                # 删除容器、卷、镜像缓存
docker compose down -v --rmi local  # 完全清理（含镜像）
```

## 升级

```bash
git pull
make build               # 增量构建（base 镜像未变则秒级）
make up
```

## 备份 workspace

workspace 是状态唯一载体，定期 tar 打包：

```bash
tar -czf workspace-$(date +%Y%m%d).tar.gz -C "$WORKSPACE_DIR" .
```

## 生产部署警告

⚠️ **P1 不适合公网部署**：无应用层认证（`AUTH_MODE=none`）、Chromium `--no-sandbox`、无审计落库。

公网部署需 P2 Orchestrator（JWT 校验 + workspace 权限 + 应用层认证中间件）+ P3 launcher（统一入口 + OAuth 登录）。

## P2 + P3 部署（多租户 + React 启动器）

P2/P3 是 P1 之上的**可选叠加层**。P2 引入 Orchestrator（多 workspace 编排 + JWT + 审计），P3 在 P2 之上引入 launcher（React 启动器 + OAuth 登录 + 统一反代 `/ws/{slug}/`）并补齐 workspace 真实启动。P1 单 workspace 模式仍独立可用（零迁移）。

```bash
# 1. 前置：P1 镜像已构建（make build），用于 workspace 容器组
# 2. 构建 P2/P3 镜像
make build-orchestrator build-launcher

# 3. 配置 .env（OAuth 凭证；开发用 mock）
#    OAUTH_MOCK=true                      # 离线闭环（生产须 false + 真实 client_id/secret）
#    OAUTH_GITHUB_CLIENT_ID/SECRET=...    # GitHub OAuth App
#    OAUTH_GOOGLE_CLIENT_ID/SECRET=...    # Google OAuth App
#    LAUNCHER_PORT=8080

# 4. 启动 P3 stack（orchestrator + postgres + launcher，含 docker.sock 挂载）
make up-p3
curl http://localhost:8000/readyz        # {"status":"ready","db":"ok"}
curl http://localhost:8080/              # launcher 登录页（SPA）

# 5. OAuth 登录：浏览器访问 http://localhost:8080/ → 「GitHub 登录」→ 工作台
#    （OAUTH_MOCK=true 时离线闭环；curl 验证：curl -c cookies.txt -L localhost:8080/api/v1/auth/oauth/github/login）

# 6. 创建并启动 workspace（launcher UI 或 API）→ orchestrator 真实拉起 cap-* 容器组
#    经统一入口访问 workspace UI：http://localhost:8080/ws/{slug}/

make stop-p3                             # 停止 P3 stack（保留 postgres 数据卷）
```

**关键差异（vs P1）**：
- **orchestrator 挂载 `/var/run/docker.sock`**（orchestrator-as-controller，编排 workspace 容器组）—— 单机受信环境，`cap_drop: [ALL]` + socket 文件权限（P3 research.md R4）。这是 P3 唯一新提权面，公网部署须改远程编排 API。
- **launcher 容器内 nginx** 托管 SPA + 反代 `/api`（orchestrator）+ `/ws/{slug}/`（workspace，auth_request 鉴权 + WebSocket 透传）。
- **OAuth 凭证**经环境变量注入，不落库/不进前端；`OAUTH_MOCK=true` 用于离线/CI 闭环测试。
- **JWT cookie 鉴权**（HttpOnly + SameSite=Lax）：launcher 浏览器经 cookie，CLI 经 Bearer（并存，零迁移）。

详见 [P3 验证手册](../specs/003-sandbox-p3-launcher/quickstart.md)（8 场景）与 [架构总览 §P3](./architecture.md)。

## 参考文档

- [架构总览](./architecture.md)
- [故障排查](./troubleshooting.md)
- [端到端验证手册](../specs/001-sandbox-p1-stack/quickstart.md)
