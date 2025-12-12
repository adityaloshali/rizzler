"""
Base model with common fields and utilities.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    Provides common fields: id, created_at, updated_at
    """

    # Common columns for all models
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }

