"""FastAPI dependencies for authentication and authorization."""

import uuid

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the caller from the bearer access token; 401 on any failure."""
    try:
        payload = decode_access_token(token)
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired access token.") from exc

    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type.")

    raw_user_id = payload.get("sub")
    if not raw_user_id:
        raise AuthenticationError("Invalid token payload.")

    try:
        user_id = uuid.UUID(raw_user_id)
    except (TypeError, ValueError) as exc:
        raise AuthenticationError("Invalid token payload.") from exc

    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or user.status != "ACTIVE":
        raise AuthenticationError("Account not found or deactivated.")

    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Gate for admin-only endpoints (design doc §2)."""
    if user.account_role != "ADMIN":
        raise PermissionDeniedError("Administrator privileges required.")
    return user
