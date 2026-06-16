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

公网部署需 P2 Orchestrator（JWT 校验 + workspace 权限 + 应用层认证中间件）。详见 `.archive/sandbox-design.md` §1.1.2 P1→P2 切换原则。

## 参考文档

- [架构总览](./architecture.md)
- [故障排查](./troubleshooting.md)
- [端到端验证手册](../specs/001-sandbox-p1-stack/quickstart.md)
- [设计原文](../.archive/sandbox-design.md)
