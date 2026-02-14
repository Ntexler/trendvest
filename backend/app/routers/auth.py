"""
Authentication router for TrendVest — JWT-based email/password auth.
"""
import os
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from passlib.context import CryptContext
from jose import jwt, JWTError

from ..models.schemas import RegisterRequest, LoginRequest, TokenResponse, UserProfile
from ..deps import get_db_pool

router = APIRouter(prefix="/api/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "trendvest-dev-secret-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def create_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest, pool=Depends(get_db_pool)):
    """Create a new account."""
    async with pool.acquire() as conn:
        existing = await conn.fetchval("SELECT id FROM users WHERE email = $1", body.email.lower())
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")

        password_hash = pwd_context.hash(body.password)
        user_id = await conn.fetchval("""
            INSERT INTO users (email, password_hash, display_name)
            VALUES ($1, $2, $3)
            RETURNING id
        """, body.email.lower(), password_hash, body.display_name or body.email.split("@")[0])

    access_token = create_token({"sub": str(user_id), "type": "access"}, timedelta(minutes=ACCESS_TOKEN_EXPIRE))
    refresh_token = create_token({"sub": str(user_id), "type": "refresh"}, timedelta(days=REFRESH_TOKEN_EXPIRE))

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, pool=Depends(get_db_pool)):
    """Login with email and password."""
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, password_hash FROM users WHERE email = $1",
            body.email.lower()
        )

    if not user or not pwd_context.verify(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_token({"sub": str(user["id"]), "type": "access"}, timedelta(minutes=ACCESS_TOKEN_EXPIRE))
    refresh_token = create_token({"sub": str(user["id"]), "type": "refresh"}, timedelta(days=REFRESH_TOKEN_EXPIRE))

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str, pool=Depends(get_db_pool)):
    """Refresh an expired access token."""
    try:
        payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT id FROM users WHERE id = $1::uuid", user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access_token = create_token({"sub": user_id, "type": "access"}, timedelta(minutes=ACCESS_TOKEN_EXPIRE))
    new_refresh = create_token({"sub": user_id, "type": "refresh"}, timedelta(days=REFRESH_TOKEN_EXPIRE))

    return TokenResponse(access_token=access_token, refresh_token=new_refresh)


@router.get("/me", response_model=UserProfile)
async def get_me(token: str, pool=Depends(get_db_pool)):
    """Get current user profile from token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, email, display_name, tier, created_at FROM users WHERE id = $1::uuid",
            user_id
        )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserProfile(
        id=str(user["id"]),
        email=user["email"],
        display_name=user["display_name"] or "",
        tier=user["tier"],
        created_at=user["created_at"],
    )
