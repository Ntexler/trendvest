"""
Authentication router for TrendVest — JWT + TOTP 2FA.

Endpoints:
  POST /api/auth/register     — Create account
  POST /api/auth/login        — Login (returns tokens or 2FA challenge)
  POST /api/auth/login/2fa    — Complete login with TOTP code
  POST /api/auth/refresh      — Refresh access token
  GET  /api/auth/me           — Current user profile
  POST /api/auth/2fa/setup    — Generate TOTP secret + QR URI
  POST /api/auth/2fa/enable   — Verify TOTP code and enable 2FA
  POST /api/auth/2fa/disable  — Disable 2FA (requires current code)
"""
import os
import hmac
import hashlib
import struct
import time
import base64
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from passlib.context import CryptContext
from jose import jwt, JWTError

from ..models.schemas import RegisterRequest, LoginRequest, TokenResponse, UserProfile
from ..deps import get_db_pool, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Import shared JWT config from deps to avoid duplication
from ..deps import JWT_SECRET, JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Account lockout settings
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


def create_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


# ── TOTP Implementation (RFC 6238) ──

def _generate_totp_secret() -> str:
    """Generate a random base32-encoded TOTP secret."""
    return base64.b32encode(secrets.token_bytes(20)).decode("utf-8")


def _get_totp_code(secret: str, time_step: int = 30, digits: int = 6) -> str:
    """Generate current TOTP code from secret."""
    key = base64.b32decode(secret, casefold=True)
    counter = int(time.time()) // time_step
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)


def _verify_totp(secret: str, code: str, window: int = 1) -> bool:
    """Verify TOTP code with time window tolerance."""
    key = base64.b32decode(secret, casefold=True)
    now = int(time.time()) // 30
    for offset in range(-window, window + 1):
        counter = now + offset
        msg = struct.pack(">Q", counter)
        h = hmac.new(key, msg, hashlib.sha1).digest()
        o = h[-1] & 0x0F
        computed = struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF
        expected = str(computed % 1_000_000).zfill(6)
        if hmac.compare_digest(expected, code.strip()):
            return True
    return False


def _totp_uri(secret: str, email: str) -> str:
    """Generate otpauth:// URI for QR code scanning."""
    return f"otpauth://totp/TrendVest:{email}?secret={secret}&issuer=TrendVest&digits=6&period=30"


# ── Audit Helper ──

async def _audit(conn, user_id, action: str, request: Request, metadata: dict = None):
    """Log an action to the audit table."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:500]
    await conn.execute("""
        INSERT INTO audit_log (user_id, action, ip_address, user_agent, metadata)
        VALUES ($1, $2, $3, $4, $5)
    """, user_id, action, ip, ua, metadata or {})


# ── Request Models ──

class TwoFALoginRequest(BaseModel):
    email: str
    password: str
    totp_code: str = Field(..., min_length=6, max_length=6)

class TwoFASetupResponse(BaseModel):
    secret: str
    uri: str

class TwoFAVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)

class TwoFALoginResponse(BaseModel):
    requires_2fa: bool = True
    temp_token: str


# ── Endpoints ──

@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest, request: Request, pool=Depends(get_db_pool)):
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

        await _audit(conn, user_id, "register", request)

    access_token = create_token({"sub": str(user_id), "type": "access"}, timedelta(minutes=ACCESS_TOKEN_EXPIRE))
    refresh_token = create_token({"sub": str(user_id), "type": "refresh"}, timedelta(days=REFRESH_TOKEN_EXPIRE))

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login")
async def login(body: LoginRequest, request: Request, pool=Depends(get_db_pool)):
    """
    Login with email and password.
    If 2FA is enabled, returns a temporary token that must be used with /login/2fa.
    """
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, password_hash, totp_enabled, locked_until, failed_login_attempts FROM users WHERE email = $1",
            body.email.lower()
        )

        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Check lockout
        if user["locked_until"] and user["locked_until"] > datetime.now(timezone.utc):
            remaining = int((user["locked_until"] - datetime.now(timezone.utc)).total_seconds() / 60) + 1
            raise HTTPException(
                status_code=423,
                detail=f"Account locked. Try again in {remaining} minutes."
            )

        # Verify password
        if not pwd_context.verify(body.password, user["password_hash"]):
            attempts = (user["failed_login_attempts"] or 0) + 1
            update_data = {"attempts": attempts}
            if attempts >= MAX_LOGIN_ATTEMPTS:
                locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                await conn.execute(
                    "UPDATE users SET failed_login_attempts = $1, locked_until = $2 WHERE id = $3",
                    attempts, locked_until, user["id"]
                )
                await _audit(conn, user["id"], "login_locked", request, update_data)
                raise HTTPException(
                    status_code=423,
                    detail=f"Too many failed attempts. Account locked for {LOCKOUT_DURATION_MINUTES} minutes."
                )
            else:
                await conn.execute(
                    "UPDATE users SET failed_login_attempts = $1 WHERE id = $2",
                    attempts, user["id"]
                )
                await _audit(conn, user["id"], "login_failed", request, update_data)
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Reset failed attempts on success
        await conn.execute(
            "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = $1",
            user["id"]
        )

        # If 2FA is enabled, return temp token
        if user["totp_enabled"]:
            temp_token = create_token(
                {"sub": str(user["id"]), "type": "2fa_pending"},
                timedelta(minutes=5)
            )
            await _audit(conn, user["id"], "login_2fa_pending", request)
            return {"requires_2fa": True, "temp_token": temp_token}

        # No 2FA — issue full tokens
        await _audit(conn, user["id"], "login_success", request)

    access_token = create_token({"sub": str(user["id"]), "type": "access"}, timedelta(minutes=ACCESS_TOKEN_EXPIRE))
    refresh_token = create_token({"sub": str(user["id"]), "type": "refresh"}, timedelta(days=REFRESH_TOKEN_EXPIRE))

    return {"requires_2fa": False, "access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@router.post("/login/2fa", response_model=TokenResponse)
async def login_2fa(body: TwoFALoginRequest, request: Request, pool=Depends(get_db_pool)):
    """Complete 2FA login with TOTP code."""
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, password_hash, totp_secret, totp_enabled FROM users WHERE email = $1",
            body.email.lower()
        )

        if not user or not pwd_context.verify(body.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not user["totp_enabled"] or not user["totp_secret"]:
            raise HTTPException(status_code=400, detail="2FA not enabled for this account")

        if not _verify_totp(user["totp_secret"], body.totp_code):
            await _audit(conn, user["id"], "2fa_failed", request)
            raise HTTPException(status_code=401, detail="Invalid 2FA code")

        await _audit(conn, user["id"], "login_2fa_success", request)

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
async def get_me(
    user: dict = Depends(get_current_user),
    pool=Depends(get_db_pool),
):
    """Get current user profile."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT tier, created_at FROM users WHERE id = $1::uuid",
            user["id"]
        )
    return UserProfile(
        id=user["id"],
        email=user["email"],
        display_name=user["display_name"] or "",
        tier=row["tier"] if row else "free",
        role=user["role"],
        totp_enabled=user["totp_enabled"],
        created_at=row["created_at"] if row else datetime.now(timezone.utc),
    )


# ── 2FA Management ──

@router.post("/2fa/setup", response_model=TwoFASetupResponse)
async def setup_2fa(
    request: Request,
    user: dict = Depends(get_current_user),
    pool=Depends(get_db_pool),
):
    """Generate a TOTP secret and URI for QR code. Does NOT enable 2FA yet."""
    secret = _generate_totp_secret()

    async with pool.acquire() as conn:
        # Store secret but don't enable yet
        await conn.execute(
            "UPDATE users SET totp_secret = $1 WHERE id = $2::uuid",
            secret, user["id"]
        )
        await _audit(conn, None, "2fa_setup_initiated", request)

    return TwoFASetupResponse(
        secret=secret,
        uri=_totp_uri(secret, user["email"]),
    )


@router.post("/2fa/enable")
async def enable_2fa(
    body: TwoFAVerifyRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    pool=Depends(get_db_pool),
):
    """Verify TOTP code and enable 2FA. User must have called /2fa/setup first."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT totp_secret, totp_enabled FROM users WHERE id = $1::uuid",
            user["id"]
        )
        if not row or not row["totp_secret"]:
            raise HTTPException(status_code=400, detail="Run /2fa/setup first")
        if row["totp_enabled"]:
            raise HTTPException(status_code=400, detail="2FA already enabled")

        if not _verify_totp(row["totp_secret"], body.code):
            raise HTTPException(status_code=400, detail="Invalid TOTP code. Check your authenticator app.")

        await conn.execute(
            "UPDATE users SET totp_enabled = true WHERE id = $1::uuid",
            user["id"]
        )
        await _audit(conn, None, "2fa_enabled", request)

    return {"status": "2fa_enabled"}


@router.post("/2fa/disable")
async def disable_2fa(
    body: TwoFAVerifyRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    pool=Depends(get_db_pool),
):
    """Disable 2FA. Requires current TOTP code as confirmation."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT totp_secret, totp_enabled FROM users WHERE id = $1::uuid",
            user["id"]
        )
        if not row or not row["totp_enabled"]:
            raise HTTPException(status_code=400, detail="2FA not enabled")

        if not _verify_totp(row["totp_secret"], body.code):
            raise HTTPException(status_code=400, detail="Invalid TOTP code")

        await conn.execute(
            "UPDATE users SET totp_enabled = false, totp_secret = NULL WHERE id = $1::uuid",
            user["id"]
        )
        await _audit(conn, None, "2fa_disabled", request)

    return {"status": "2fa_disabled"}
