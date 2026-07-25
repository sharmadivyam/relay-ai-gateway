"""
Authentication middleware.

Two supported auth methods:
  1. Bearer JWT  — for human users/dashboard calls
  2. API Key     — for machine-to-machine proxy calls (like OpenAI SDK clients)
       Header: Authorization: Bearer sk-gw_<key>
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from app.db.models import IST
from typing import Optional

import uuid as _uuid_module
import bcrypt as _bcrypt
from fastapi import HTTPException, Request, status, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import ApiKey, User, UserTier
from app.db.session import get_db

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)

# ──────────────────────────────────────────────
# Password helpers
# ──────────────────────────────────────────────

def hash_password(plain: str) -> str:
    # bcrypt silently truncates at 72 bytes — we do it explicitly so the
    # behaviour is visible and consistent across all bcrypt versions.
    return _bcrypt.hashpw(plain[:72].encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain[:72].encode(), hashed.encode())


# ──────────────────────────────────────────────
# API key helpers
# ──────────────────────────────────────────────

def generate_api_key() -> tuple[str, str, str]:
    """Returns (raw_key, key_hash, key_prefix)."""
    raw = "sk-gw_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    prefix = raw[:8]
    return raw, key_hash, prefix


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ──────────────────────────────────────────────
# JWT helpers
# ──────────────────────────────────────────────

def create_access_token(subject: str, extra: dict | None = None) -> str:
    payload = {
        "sub": subject,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
        **(extra or {}),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ──────────────────────────────────────────────
# Dependency: resolve the caller's identity
# ──────────────────────────────────────────────

class AuthenticatedCaller:
    """Resolved identity attached to request.state after auth."""
    def __init__(self, user: User, api_key_prefix: Optional[str] = None):
        self.user = user
        self.api_key_prefix = api_key_prefix
        self.tier: UserTier = user.tier


async def get_current_caller(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedCaller:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")

    token = credentials.credentials

    # ── API key path: starts with "sk-gw_"
    if token.startswith("sk-gw_"):
        key_hash = hash_api_key(token)
        result = await db.execute(
            select(ApiKey)
            .where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
        )
        api_key_row: Optional[ApiKey] = result.scalar_one_or_none()
        if api_key_row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

        user_result = await db.execute(select(User).where(User.id == api_key_row.user_id))
        user = user_result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

        # Update last_used without blocking
        api_key_row.last_used_at = datetime.now(IST)
        return AuthenticatedCaller(user=user, api_key_prefix=api_key_row.key_prefix)

    # ── JWT path
    payload = decode_token(token)
    user_id = payload.get("sub")
    try:
        user_uuid = _uuid_module.UUID(user_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")
    result = await db.execute(select(User).where(User.id == user_uuid, User.is_active == True))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return AuthenticatedCaller(user=user)
