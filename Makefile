## AI 个人沙箱 P1 —— Makefile
## 所有 target 用 `## ` 注释，make help 会自动汇总

## Settings
PYTHON_VERSION := 3.12
NODE_VERSION := 24
PORT ?= 80
COMPOSE := docker compose
BUILDKIT := DOCKER_BUILDKIT=1

## Base 镜像列表（构建顺序：base-os 必须先构建，其余 3 个可并行）
BASE_OS := base-os
BASE_PARALLEL := base-python312 base-node24 base-vnc
BASE_ALL := $(BASE_OS) $(BASE_PARALLEL)

## Cap-* 镜像列表
CAP_ALL := cap-agent cap-browser cap-code cap-jupyter cap-mcp cap-nginx cap-terminal

## Help
.PHONY: help
help:  ## 显示此帮助
	@awk 'BEGIN {FS = ":.*##"; printf "Available targets:\n\n"} /^[a-zA-Z0-9_-]+:.*##/ { printf "  %-18s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

## Build
.PHONY: build build-base build-cap
build: build-base build-cap  ## 构建所有 base + cap-* 镜像

build-base: $(BASE_OS)  ## 仅构建 4 个 base 镜像（并行）
	@echo "==> 并行构建 base-python312 / base-node24 / base-vnc"
	$(MAKE) -j 3 $(BASE_PARALLEL)

build-cap:  ## 仅构建 7 个 cap-* 镜像（顺序构建，依赖 base-*）
	@for svc in $(CAP_ALL); do \
		echo "==> 构建 $$svc"; \
		$(BUILDKIT) docker buildx build \
			--load \
			--tag $$svc:latest \
			./cap-$$svc || exit 1; \
	done

## 单个 base 镜像构建规则
.PHONY: $(BASE_ALL)
$(BASE_OS):
	@echo "==> 构建 base-os（基础祖先）"
	$(BUILDKIT) docker buildx build --load --tag base-os:latest ./base/base-os

base-python312:
	@echo "==> 构建 base-python312"
	$(BUILDKIT) docker buildx build --load --tag base-python312:latest ./base/base-python312

base-node24:
	@echo "==> 构建 base-node24"
	$(BUILDKIT) docker buildx build --load --tag base-node24:latest ./base/base-node24

base-vnc:
	@echo "==> 构建 base-vnc"
	$(BUILDKIT) docker buildx build --load --tag base-vnc:latest ./base/base-vnc

## Run
.PHONY: up down logs
up:  ## docker compose up -d（后台启动）
	$(COMPOSE) up -d

down:  ## docker compose down
	$(COMPOSE) down

logs:  ## 跟踪所有服务日志
	$(COMPOSE) logs -f --tail=200

## Test
.PHONY: test test-unit test-e2e test-agent test-terminal test-mcp
test: test-unit test-e2e  ## 跑所有测试

test-unit: test-agent test-terminal test-mcp  ## 跑所有 Python 服务的单元测试（覆盖率 ≥80%）

test-agent:  ## cap-agent 单元测试（覆盖率 ≥80%）
	cd cap-agent && uv run pytest tests/ --cov=cap_agent --cov-report=term-missing --cov-fail-under=80

test-terminal:  ## cap-terminal 单元测试（覆盖率 ≥80%）
	cd cap-terminal && uv run pytest tests/ --cov=cap_terminal --cov-report=term-missing --cov-fail-under=80

test-mcp:  ## cap-mcp 单元测试（覆盖率 ≥80%）
	cd cap-mcp && uv run pytest tests/ --cov=cap_mcp --cov-report=term-missing --cov-fail-under=80

test-e2e:  ## docker compose up 完整 stack + 跑 e2e（保留容器便于调试，需清理用 make down）
	$(MAKE) build
	$(COMPOSE) up -d --wait
	cd tests && uv run pytest e2e -v

## Orchestrator（P2，specs/002-sandbox-p2-orchestrator）
.PHONY: build-orchestrator up-orchestrator stop-orchestrator test-orchestrator test-orchestrator-integration
build-orchestrator:  ## 构建 orchestrator 镜像（multi-stage，FROM base-python312）
	$(BUILDKIT) docker buildx build --load --tag sandbox/orchestrator:latest ./orchestrator

up-orchestrator:  ## 启动 Orchestrator + PostgreSQL（P2 编排层）
	$(COMPOSE) -f docker-compose.orchestrator.yml up -d --wait

stop-orchestrator:  ## 停止 Orchestrator + PostgreSQL
	$(COMPOSE) -f docker-compose.orchestrator.yml down

test-e2e-p2:  ## P2 完整 stack E2E（Orchestrator + workspace）
	$(MAKE) build-orchestrator
	$(COMPOSE) -f docker-compose.orchestrator.yml up -d --wait
	cd tests && uv run pytest e2e/test_p2_*.py -v
	$(COMPOSE) -f docker-compose.orchestrator.yml down

test-orchestrator:  ## orchestrator 单元测试（覆盖率 ≥80%，SC-003）
	cd orchestrator && uv run pytest tests/unit --cov=orchestrator --cov-report=term-missing --cov-fail-under=80

test-orchestrator-integration:  ## orchestrator 集成测试（需 Docker，testcontainers-postgres）
	cd orchestrator && uv run pytest tests/integration -v

## Misc
.PHONY: clean
clean:  ## 清理容器、卷、缓存
	$(COMPOSE) down -v --remove-orphans
	docker builder prune -f
	@echo "==> 已清理 compose 容器、卷、构建缓存"
