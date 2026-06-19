"""A. cap-nginx Phase5 auth_request 配置渲染（批次3 遗留，research.md R6）。

职责：在 workspace 启动（compose up）前，把 cap-nginx/nginx.workspace.conf.tmpl
渲染成成品 conf（envsubst 替换 ${ORCHESTRATOR_URL}/${WORKSPACE_ID}/${AUTH_FAILURE_MODE}），
写到 {workspace_volume_root}/{slug}/nginx.workspace.conf，供 compose 模板的
${WORKSPACE_NGINX_CONF} 挂载点（docker-compose.workspace.yml.tmpl 已预留）挂入 cap-nginx。

设计要点：
- 纯函数（同步文件 IO，渲染开销忽略不计），返回 Path 供调用方并入 compose env。
- 用 string.Template 做安全替换：仅认 ${VAR}，不误伤 nginx 变量 $http_upgrade 等
  （模板中 nginx 内置变量写作 $var，无 ${}，二者天然分离）。
- compose_runner 零改动（FR-019）：渲染产物经 workspace_env 的 WORKSPACE_NGINX_CONF
  字段透传，compose_runner 仍是 docker compose -p up，不感知渲染。
- 不依赖外部 envsubst 二进制（Python 自带 string.Template，可移植 + 可测）。
"""
from pathlib import Path
from string import Template

from orchestrator.core.config import Settings

# 模板路径：仓库根的 cap-nginx/nginx.workspace.conf.tmpl。
# 默认相对 orchestrator 包定位（orchestrator/src/orchestrator/services → 仓库根）；
# 测试通过 monkeypatch 覆盖本常量指向合成模板。
_PACKAGE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PACKAGE_DIR.parents[3]  # orchestrator/src/orchestrator/services → repo root
_TEMPLATE_PATH = _REPO_ROOT / "cap-nginx" / "nginx.workspace.conf.tmpl"

# 渲染产物文件名（挂载到 cap-nginx /etc/nginx/conf.d/workspace.conf）
_CONF_FILENAME = "nginx.workspace.conf"


def render_workspace_nginx_conf(ws, settings: Settings) -> Path:
    """渲染 workspace cap-nginx 的 auth_request 配置并落盘，返回产物路径。

    参数：
        ws: Workspace ORM（需 .slug / .id）
        settings: 全局配置（取 workspace_volume_root / orch_url / auth_failure_mode）

    返回：
        Path = {workspace_volume_root}/{slug}/nginx.workspace.conf

    幂等：重复调用覆盖旧文件（workspace 重启不残留陈旧 WORKSPACE_ID）。
    失败：模板缺失 → FileNotFoundError（fail-fast，启动期暴露配置问题）。
    """
    tmpl_text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    rendered = Template(tmpl_text).safe_substitute(
        ORCHESTRATOR_URL=settings.orch_url,
        WORKSPACE_ID=str(ws.id),
        AUTH_FAILURE_MODE=settings.auth_failure_mode,
    )
    out_dir = Path(settings.workspace_volume_root) / ws.slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / _CONF_FILENAME
    out_path.write_text(rendered, encoding="utf-8")
    return out_path
