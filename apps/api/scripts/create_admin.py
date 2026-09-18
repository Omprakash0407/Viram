"""Promote an existing account to ADMIN.

Usage:
    python -m scripts.create_admin admin@example.com

Run from apps/api with the venv active.
"""

import asyncio
import sys

from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal, dispose_engine
from app.models.user import User


async def promote(email: str) -> int:
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            print(f"No account found for {email}")
            return 1
        await db.execute(
            update(User).where(User.id == user.id).values(account_role="ADMIN")
        )
        await db.commit()
        print(f"{email} is now ADMIN.")
        return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.create_admin <email>")
        return 2
    try:
        return asyncio.run(promote(sys.argv[1]))
    finally:
        asyncio.run(dispose_engine())


if __name__ == "__main__":
    raise SystemExit(main())
