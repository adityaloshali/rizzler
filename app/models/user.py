"""
User model - integrates with Supabase Auth.
"""

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.session import Session


class User(Base):
    """
    User model.
    
    The `id` matches the Supabase Auth user ID for seamless integration.
    We store additional profile data that Supabase Auth doesn't handle.
    """

    __tablename__ = "users"

    # Override id to accept external UUID from Supabase Auth
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )

    # Basic info
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # User preferences (stored as JSON for flexibility)
    preferences: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        doc="User preferences: goals, communication style, etc.",
    )

    # Onboarding data
    bio: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="User's dating bio/about me for context",
    )

    # Relationships
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"

