"""Shared timestamp column factories.

Each factory returns a ``mapped_column``; annotate the class attribute as
``Mapped[datetime]`` at the use site (SQLAlchemy 2.0 typed declarative style).
"""

from typing import Any

from sqlalchemy import DateTime, func


def created_at() -> Any:
    return mapped_column_ts(server_default=func.now(), onupdate=None)


def updated_at() -> Any:
    return mapped_column_ts(server_default=func.now(), onupdate=func.now())


def mapped_column_ts(server_default: Any, onupdate: Any) -> Any:
    from sqlalchemy.orm import mapped_column

    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=server_default,
        onupdate=onupdate,
    )
