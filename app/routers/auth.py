"""Auth routes: register, login, create/list API keys."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApiKey, User
from app.db.schemas import ApiKeyCreate, ApiKeyOut, TokenOut, UserCreate, UserOut
from app.db.session import get_db
from app.middleware.auth import (
    AuthenticatedCaller,
    create_access_token,
    generate_api_key,
    get_current_caller,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(email=body.email, hashed_password=hash_password(body.password))
    db.add(user)
    await db.flush()
    return user


@router.post("/login", response_model=TokenOut)
async def login(body: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email, User.is_active == True))
    user: User | None = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(subject=str(user.id), extra={"tier": user.tier})
    return TokenOut(access_token=token)


@router.post("/keys", response_model=ApiKeyOut, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreate,
    caller: AuthenticatedCaller = Depends(get_current_caller),
    db: AsyncSession = Depends(get_db),
):
    raw_key, key_hash, prefix = generate_api_key()
    api_key = ApiKey(
        user_id=caller.user.id,
        key_hash=key_hash,
        key_prefix=prefix,
        label=body.label,
    )
    db.add(api_key)
    await db.flush()
    return ApiKeyOut(id=api_key.id, key_prefix=prefix, label=body.label, raw_key=raw_key)


@router.get("/keys", response_model=list[ApiKeyOut])
async def list_api_keys(
    caller: AuthenticatedCaller = Depends(get_current_caller),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == caller.user.id, ApiKey.is_active == True)
    )
    return [
        ApiKeyOut(
            id=k.id,
            key_prefix=k.key_prefix,
            label=k.label,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
        )
        for k in result.scalars()
    ]
