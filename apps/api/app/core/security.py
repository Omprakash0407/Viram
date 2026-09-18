"""Security primitives: argon2id password hashing, JWT access tokens, refresh tokens.

- Passwords: argon2id via passlib.
- Access tokens: short-lived JWTs (HS256 by default), stateless.
- Refresh tokens: 256-bit opaque secrets; only sha-256 hashes are stored,
  mapped to revocable user_sessions rows (design doc §1.2).
"""

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

_REFRESH_BYTES = 32


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd_context.verify(plain, hashed)
    except ValueError:
        return False


def create_access_token(user_id: uuid.UUID, account_role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": account_role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
        "jti": secrets.token_hex(8),
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Raises JWTError on invalid/expired tokens."""
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["exp", "sub"]},
    )


def generate_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, sha256_hex_hash). Only the hash is persisted."""
    raw = secrets.token_urlsafe(_REFRESH_BYTES)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def refresh_tokens_equal(raw: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_refresh_token(raw), stored_hash)
