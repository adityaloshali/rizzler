"""
Session model - represents a conversation context (Tutor, Practice, or Analysis).
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.chat import ChatLog
    from app.models.user import User


class SessionMode(str, Enum):
    """Available session modes."""

    TUTOR = "tutor"  # RAG-based Q&A from uploaded knowledge
    PRACTICE = "practice"  # Uncensored roleplay
    ANALYSIS = "analysis"  # Screenshot analysis & suggestions


class Session(Base):
    """
    Session model.
    
    A session represents a conversation context that persists across time.
    Users can have multiple sessions, each with its own mode and persona settings.
    """

    __tablename__ = "sessions"

    # Foreign key to user
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Session metadata
    title: Mapped[str] = mapped_column(
        String(200),
        default="New Chat",
        doc="User-editable session title",
    )
    mode: Mapped[SessionMode] = mapped_column(
        String(20),
        default=SessionMode.TUTOR,
        index=True,
    )

    # Persona settings (for Practice mode)
    persona_settings: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        doc="""
        Practice mode persona config:
        {
            "name": "Alex",
            "age": 25,
            "gender": "female",
            "vibe": "flirty but hard to get",
            "backstory": "Met at a coffee shop...",
            "scenario": "First date texting"
        }
        """,
    )

    # Conversation summary (for long sessions)
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="AI-generated summary of the conversation for context compression",
    )

    # Activity tracking
    last_active: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    message_count: Mapped[int] = mapped_column(default=0)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")
    chat_logs: Mapped[list["ChatLog"]] = relationship(
        "ChatLog",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatLog.created_at",
    )

    def __repr__(self) -> str:
        return f"<Session {self.id} mode={self.mode}>"

