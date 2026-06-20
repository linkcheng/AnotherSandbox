# 故障排查

**Date**: 2026-06-18

## Chromium 相关

### `chromium-browser` 包在 Ubuntu 24.04 安装失败

**原因**：Ubuntu 24.04 的 `chromium-browser` 是 transitional package 指向 snap 版（容器内 snap 不可用）。

**解决**：改用 Mozilla PPA 或直接 deb：
```dockerfile
# 方案 A：Mozilla PPA
RUN add-apt-repository ppa:mozillateam/ppa && \
    apt-get update && apt-get install -y chromium
# 方案 B：deb 直接下载
RUN curl -fsSL https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -o chrome.deb && \
    dpkg -i chrome.deb || apt-get -f install -y
```

### Chromium 启动失败：`--no-sandbox` 仍报错

**原因**：容器 cap_drop ALL 移除了 `CAP_SYS_ADMIN`，但 Chromium sandbox（P1 禁用）需要。

**解决**：确认 entrypoint.sh 含 `--no-sandbox --disable-gpu --disable-dev-shm-usage`。`/dev/shm` 太小（默认 64MB）会触发崩溃，docker-compose 已加 `shm_size: 1g`。

### noVNC 黑屏 / 鼠标不响应

**排查**：
```bash
docker compose exec cap-browser bash -c "DISPLAY=:1 xrandr"
docker compose logs cap-browser | grep -i Xvnc
```
若 Xvnc 未启动，重启 `docker compose restart cap-browser`。

## libtmux / Shell 相关

### `libtmux.exc.LibTmuxException: server not running`

**原因**：cap-terminal 启动时 tmux server 未初始化。

**解决**：tmux_session.py 懒初始化逻辑会自动 `new_session`。若仍失败：
```bash
docker compose exec cap-terminal tmux -L sandbox list-sessions
docker compose restart cap-terminal
```

### shell_exec 命令历史在 ttyd 不可见

**原因**：libtmux 与 ttyd 未共享同一 tmux socket。

**确认**：
- ttyd 启动时 `tmux -L sandbox attach -t sandbox`
- shell-exec-api 连接相同 socket_name `sandbox`

## bind mount / 文件相关

### macOS 文件读写慢（>1s）

**原因**：Docker Desktop 的 bind mount 经 osxfs/VFS 套娃。

**解决**：
- 大文件放 named volume（牺牲透明性）
- 或用 Linux 主机
- 或开 Docker Desktop 的 VirtioFS（Settings → General → "Use VirtioFS for file sharing"）

### cap-code 保存的文件 cap-mcp 读不到

**原因**：挂载矩阵 rw/ro 错误。

**确认** docker-compose.yml：
- cap-code 挂 `/workspace/code` rw
- cap-mcp 挂 `/workspace/code` ro（读权限，应可见）

```bash
docker compose exec cap-mcp ls /workspace/code/
```

## WebSocket / Nginx 相关

### `/terminal/` WS 连接失败（502/504）

**排查**：
```bash
# 检查 cap-terminal 是否 healthy
docker compose ps cap-terminal

# 检查 nginx 配置
docker compose exec cap-nginx nginx -t

# 看 nginx error log
docker compose logs cap-nginx | grep -i error
```

### `/novnc/` 连接频繁断开

**原因**：T072 配置 WS 空闲超时 300s。

**解决**：客户端实现心跳（每 60s 发一个 ping），或调整 nginx.conf `proxy_read_timeout 3600s`（仅 noVNC）。

## MCP / FastMCP 相关

### MCP `tools/list` 返回 404

**原因**：路径不对。FastMCP 内部端点是 `/mcp/sandbox/mcp`，nginx 已 rewrite。

**正确客户端路径**：`POST http://localhost/mcp/sandbox/`

### fastmcp 启动失败：`cryptography build error`

**原因**：fastmcp 2.x 拉 cryptography 49，需 rust 工具链。

**解决**：本仓库已锁定 `cryptography>=48.0.0,<49`（用预编译 wheel）。若仍失败：
```bash
rustup default stable
pip install --upgrade pip
```

## 覆盖率门禁相关

### `--cov-fail-under=80` 报错

**原因**：覆盖率 <80%。

**临时跳过**：`uv run pytest --no-cov`（不推荐长期）
**根治**：补单测覆盖未测分支（参照 `--cov-report=term-missing`）

## 镜像构建相关

### `make build` 超时（>10 分钟）

**原因**：首次冷构建 + 网络慢。

**加速**：
- 开 BuildKit cache：`export DOCKER_BUILDKIT=1`
- 国内可设镜像源：`/etc/docker/daemon.json` 加 `registry-mirrors`
- base 镜像构建后是缓存，cap-* 重构建秒级

### `docker compose config` 报 `services must be a mapping`

**原因**：docker-compose.yml 缩进错误。

**确认**：`docker compose config --quiet` 检查 YAML 语法。

## 其他

### `pyautogui.ImageNotFoundException` in cap-agent

**原因**：DISPLAY 环境变量未设、或 cap-browser X socket 未共享。

**确认**：
```bash
docker compose exec cap-agent bash -c "echo DISPLAY=\$DISPLAY && ls /tmp/.X11-unix/"
```

### 子任务 `--strict-markers` 失败

**原因**：pytest 未注册的 marker。

**解决**：在对应 pyproject.toml `[tool.pytest.ini_options] markers` 注册。

## 联系

未列入的问题：
1. 查 `specs/001-sandbox-p1-stack/` 规格与契约
2. 提 issue 到仓库
