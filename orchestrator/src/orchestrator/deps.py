"""FastAPI 依赖：get_current_user（JWT → User）。contracts/orchestrator-rest-api §4。"""
import uuid

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.db import get_session
from orchestrator.core.security import decode_token
from orchestrator.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if not token:
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized"}})
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized"}})
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized"}})
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized"}})
    user = await session.get(User, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized"}})
    return user
