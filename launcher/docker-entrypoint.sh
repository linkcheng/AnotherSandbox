#!/bin/sh
# Launcher envsubst 渲染脚本（由 nginx 官方 /docker-entrypoint.sh 在 20-* 阶段调用）。
# 替代官方 20-envsubst-on-templates.sh（已删），用白名单避免破坏 nginx 运行时变量。
#
# 背景：nginx 官方 envsubst 默认替换所有 $VAR，会把 $slug/$http_upgrade 等运行时
# 变量替换为空。白名单模式（envsubst 第二参数指定变量列表）仅替换指定变量。
#
# 白名单变量（由 docker-compose.orchestrator.yml launcher.environment 注入）：
#   ORCH_URL             — orchestrator verify 端点（auth_request 子请求目标）
#   ORCHESTRATOR_UPSTREAM — orchestrator 反代上游（host:port）
#   LAUNCHER_PORT        — nginx 监听端口（容器内固定 80）
set -eu

TMPL_DIR=/etc/nginx/templates
OUT_DIR=/etc/nginx/conf.d
# envsubst 白名单：仅这些 ${VAR} 被替换，其余 $var 原样保留
ENVSUBST_VARS='\${ORCH_URL} \${ORCHESTRATOR_UPSTREAM} \${LAUNCHER_PORT}'

for tmpl in "$TMPL_DIR"/*.tmpl; do
    [ -f "$tmpl" ] || continue
    out_name=$(basename "$tmpl" .tmpl)
    echo "渲染 $tmpl → $OUT_DIR/$out_name"
    envsubst "$ENVSUBST_VARS" < "$tmpl" > "$OUT_DIR/$out_name"
done

# 不 exec、不 nginx -t：交给官方 entrypoint 后续脚本（30-tune）+ 最终 CMD 处理
