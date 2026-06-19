"""认证安全：bcrypt 密码哈希（直接用 bcrypt 库，绕过 passlib 兼容问题）+ PyJWT。research.md R5。"""
from datetime import datetime, timedelta, timezone

import bcrypt
import uuid

import jwt

from orchestrator.core.config import get_settings

_settings = get_settings()


def hash_password(plain: str) -> str:
    # bcrypt 限 72 字节；超长截断前的显式校验交调用方，这里直接 hash
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _create_token(sub: str, token_type: str, ttl: timedelta, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict = {"sub": sub, "type": token_type, "iat": now, "exp": now + ttl, "jti": uuid.uuid4().hex}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _settings.resolved_jwt_secret(), algorithm=_settings.jwt_alg)


def create_access_token(user_id: str) -> str:
    return _create_token(user_id, "access", timedelta(minutes=_settings.access_token_ttl_min))


def create_refresh_token(user_id: str) -> str:
    return _create_token(user_id, "refresh", timedelta(days=_settings.refresh_token_ttl_days))


def decode_token(token: str) -> dict:
    return jwt.decode(token, _settings.resolved_jwt_secret(), algorithms=[_settings.jwt_alg])
