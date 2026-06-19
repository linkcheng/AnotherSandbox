"""认证路由：register/login/refresh。research.md R5, contracts/orchestrator-rest-api §1。"""
import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.config import get_settings
from orchestrator.core.db import get_session
from orchestrator.core.security import (
    create_access_token, create_refresh_token, decode_token, hash_password, verify_password,
)
from orchestrator.models.refresh_token import RefreshToken
from orchestrator.models.user import User
from orchestrator.schemas.auth import LoginIn, RefreshIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
_settings = get_settings()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def _issue_tokens(session: AsyncSession, user: User) -> TokenOut:
    access = create_access_token(str(user.id))
    refresh_tok = create_refresh_token(str(user.id))
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_hash_token(refresh_tok),
            expires_at=datetime.now(timezone.utc) + timedelta(days=_settings.refresh_token_ttl_days),
        )
    )
    await session.commit()
    return TokenOut(
        access_token=access, refresh_token=refresh_tok,
        expires_in=_settings.access_token_ttl_min * 60,
    )


@router.post("/register", response_model=UserOut, status_code=201)
async def register(body: RegisterIn, session: AsyncSession = Depends(get_session)):
    if await session.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(status_code=409, detail={"error": {"code": "email_exists"}})
    user = User(email=body.email, password_hash=hash_password(body.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, session: AsyncSession = Depends(get_session)):
    user = await session.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized"}})
    return await _issue_tokens(session, user)


@router.post("/refresh", response_model=TokenOut)
async def refresh(body: RefreshIn, session: AsyncSession = Depends(get_session)):
    try:
        payload = decode_token(body.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized"}})
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized"}})
    rt = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == _hash_token(body.refresh_token))
    )
    now = datetime.now(timezone.utc)
    if not rt or rt.revoked_at is not None or rt.expires_at < now:
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized"}})
    rt.revoked_at = now  # rotation：吊销旧 token
    user = await session.get(User, rt.user_id)
    if not user:
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized"}})
    await session.commit()
    return await _issue_tokens(session, user)
