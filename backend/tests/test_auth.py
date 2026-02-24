"""
Tests for auth utilities — JWT token creation and verification.
"""
import pytest
from datetime import timedelta
from jose import jwt

from app.routers.auth import create_token, JWT_SECRET, JWT_ALGORITHM


class TestTokenCreation:
    def test_creates_valid_jwt(self):
        token = create_token({"sub": "user123", "type": "access"}, timedelta(minutes=30))
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert payload["sub"] == "user123"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_access_and_refresh_differ(self):
        access = create_token({"sub": "user1", "type": "access"}, timedelta(minutes=30))
        refresh = create_token({"sub": "user1", "type": "refresh"}, timedelta(days=7))
        assert access != refresh

        access_payload = jwt.decode(access, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        refresh_payload = jwt.decode(refresh, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert access_payload["type"] == "access"
        assert refresh_payload["type"] == "refresh"

    def test_expired_token_raises(self):
        token = create_token({"sub": "user1", "type": "access"}, timedelta(seconds=-1))
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

    def test_wrong_secret_raises(self):
        token = create_token({"sub": "user1", "type": "access"}, timedelta(minutes=30))
        with pytest.raises(jwt.JWTError):
            jwt.decode(token, "wrong-secret", algorithms=[JWT_ALGORITHM])

    def test_payload_preserved(self):
        token = create_token(
            {"sub": "abc-123", "type": "access", "tier": "pro"},
            timedelta(minutes=5),
        )
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert payload["tier"] == "pro"
