"""GET /api/v1/me：返回当前登录用户（含 OAuth profile 字段）。T026, frontend-api-contract §1。"""
from fastapi import APIRouter, Depends

from orchestrator.deps import get_current_user_optional_cookie
from orchestrator.models.user import User
from orchestrator.schemas.oauth import MeOut

router = APIRouter(prefix="/api/v1", tags=["me"])


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(get_current_user_optional_cookie)) -> MeOut:
    """当前 user（cookie 或 Bearer 鉴权）。含 display_name/avatar_url。"""
    return MeOut.model_validate(user)
