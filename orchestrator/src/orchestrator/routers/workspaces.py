"""Workspace CRUD + 生命周期。contracts/orchestrator-rest-api §2, research.md R1/R2/R7。"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.config import get_settings
from orchestrator.core.db import get_session
from orchestrator.deps import get_current_user, require_workspace_owner
from orchestrator.models.user import User
from orchestrator.models.workspace import Workspace
from orchestrator.models.workspace_owner import WorkspaceOwner
from orchestrator.schemas.workspace import WorkspaceCreateIn, WorkspaceOut
from orchestrator.services import compose_runner
from orchestrator.services.port_allocator import allocate_port
from orchestrator.services.workspace_lifecycle import apply_start_result, make_slug, validate_transition, volume_path

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])
_settings = get_settings()


def _ws_env(ws: Workspace) -> dict:
    return compose_runner.workspace_env(
        ws.slug, ws.external_port, ws.id, ws.volume_path,
        _settings.orch_url, "orchestrator", _settings.auth_failure_mode,
    )


async def _do_create(body: WorkspaceCreateIn, user: User, session: AsyncSession) -> Workspace:
    """分配端口 + 建目录元数据；并发端口冲突重试一次（partial unique 兜底）。"""
    ws: Workspace | None = None
    for attempt in range(2):
        port = await allocate_port(session)
        slug = make_slug(body.name)
        ws = Workspace(
            name=body.name, slug=slug, owner_user_id=user.id, status="created",
            compose_project=slug, external_port=port,
            volume_path=volume_path(_settings.workspace_volume_root, slug),
        )
        session.add(ws)
        try:
            await session.commit()
            break
        except IntegrityError:
            await session.rollback()
            if attempt:  # 重试用尽
                raise HTTPException(status_code=409, detail={"error": {"code": "port_conflict"}})
    assert ws is not None
    session.add(WorkspaceOwner(workspace_id=ws.id, user_id=user.id, role="owner"))
    await session.commit()
    await session.refresh(ws)
    return ws


@router.post("", response_model=WorkspaceOut, status_code=201)
async def create_workspace(
    body: WorkspaceCreateIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _do_create(body, user, session)


@router.get("", response_model=list[WorkspaceOut])
async def list_workspaces(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    rows = await session.execute(
        select(Workspace)
        .join(WorkspaceOwner, WorkspaceOwner.workspace_id == Workspace.id)
        .where(WorkspaceOwner.user_id == user.id, Workspace.deleted_at.is_(None))
    )
    return rows.scalars().all()


@router.get("/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(ws_role: tuple[Workspace, str] = Depends(require_workspace_owner)):
    return ws_role[0]


@router.post("/{workspace_id}/start", response_model=WorkspaceOut)
async def start_workspace(
    ws_role: tuple[Workspace, str] = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    ws = ws_role[0]
    target = validate_transition("start", ws.status)
    if target != ws.status and target == "running":
        ws.status = "starting"
        await session.commit()
        result = await compose_runner.up(ws.slug, _ws_env(ws), _settings.workspace_compose_cwd)
        # FR-018：失败转 error 并写 error_message 摘要；成功清空历史错误（compose_runner 零改动）
        apply_start_result(ws, result)
        await session.commit()
    return ws


@router.post("/{workspace_id}/stop", response_model=WorkspaceOut)
async def stop_workspace(
    ws_role: tuple[Workspace, str] = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    ws = ws_role[0]
    target = validate_transition("stop", ws.status)
    if target != ws.status:
        await compose_runner.down(ws.slug, _ws_env(ws), _settings.workspace_compose_cwd, volumes=False)
        ws.status = "stopped"
        await session.commit()
    return ws


@router.post("/{workspace_id}/pause", response_model=WorkspaceOut)
async def pause_workspace(
    ws_role: tuple[Workspace, str] = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    ws = ws_role[0]
    target = validate_transition("pause", ws.status)
    if target != ws.status:
        await compose_runner.pause(ws.slug, _ws_env(ws), _settings.workspace_compose_cwd)
        ws.status = "paused"
        await session.commit()
    return ws


@router.post("/{workspace_id}/resume", response_model=WorkspaceOut)
async def resume_workspace(
    ws_role: tuple[Workspace, str] = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    ws = ws_role[0]
    target = validate_transition("resume", ws.status)
    if target != ws.status:
        await compose_runner.unpause(ws.slug, _ws_env(ws), _settings.workspace_compose_cwd)
        ws.status = "running"
        await session.commit()
    return ws


@router.delete("/{workspace_id}")
async def delete_workspace(
    ws_role: tuple[Workspace, str] = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
    purge: bool = False,
):
    ws, role = ws_role
    if role != "owner":
        raise HTTPException(status_code=403, detail={"error": {"code": "forbidden"}})
    if purge:
        await compose_runner.down(ws.slug, _ws_env(ws), _settings.workspace_compose_cwd, volumes=True)
        await session.delete(ws)
    else:
        ws.deleted_at = datetime.now(timezone.utc)
        ws.status = "deleted"
    await session.commit()
    return {"status": "deleted", "purged": purge}
