"""
Dependency injection functions for TrendVest.
Avoids circular imports: routers import deps, main sets deps at startup.
"""
import os
import re
from typing import Optional

from fastapi import Depends, HTTPException, Header
from jose import jwt, JWTError

_db_pool = None
_stock_service = None

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "")
if not JWT_SECRET:
    import warnings
    warnings.warn("JWT_SECRET_KEY not set — using insecure dev default. Set JWT_SECRET_KEY in production!", stacklevel=2)
    JWT_SECRET = "trendvest-dev-only-" + os.getenv("HOSTNAME", "local")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# Valid ticker: 1-10 uppercase letters, dots, or hyphens
TICKER_REGEX = re.compile(r"^[A-Z0-9.\-]{1,10}$")


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


def set_stock_service(service):
    global _stock_service
    _stock_service = service


async def get_db_pool():
    if _db_pool is None:
        raise RuntimeError("Database pool not initialized")
    return _db_pool


async def get_stock_service():
    if _stock_service is None:
        from .services.stocks import StockPriceService
        set_stock_service(StockPriceService())
    return _stock_service


# ── Auth Guards ──

async def get_current_user(
    authorization: str = Header(None),
    pool=Depends(get_db_pool),
) -> dict:
    """
    Extract and validate JWT from Authorization header.
    Returns user dict with id, email, role.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    # Accept "Bearer <token>" or raw token
    token = authorization
    if authorization.startswith("Bearer "):
        token = authorization[7:]

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, email, display_name, role, totp_enabled FROM users WHERE id = $1::uuid",
            user_id
        )

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Check if account is locked
    if user.get("locked_until"):
        from datetime import datetime, timezone
        if user["locked_until"] > datetime.now(timezone.utc):
            raise HTTPException(status_code=423, detail="Account temporarily locked")

    return {
        "id": str(user["id"]),
        "email": user["email"],
        "display_name": user["display_name"],
        "role": user["role"] or "user",
        "totp_enabled": user["totp_enabled"] or False,
    }


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Require admin role."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ── Input Validation ──

def validate_ticker(ticker: str) -> str:
    """Validate and sanitize ticker input."""
    ticker = ticker.strip().upper()
    if not TICKER_REGEX.match(ticker):
        raise HTTPException(status_code=400, detail="Invalid ticker format")
    return ticker
