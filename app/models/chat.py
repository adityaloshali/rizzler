"""
ChatLog model - stores conversation history.
"""

import uuid
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.session import Session


class MessageRole(str, Enum):
    """Message sender role."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatLog(Base):
    """
    ChatLog model.
    
    Stores individual messages in a conversation session.
    Supports text messages, image attachments, and metadata.
    """

    __tablename__ = "chat_logs"

    # Foreign key to session
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Message content
    role: Mapped[MessageRole] = mapped_column(
        String(20),
        default=MessageRole.USER,
    )
    content: Mapped[str] = mapped_column(
        Text,
        doc="The actual message text",
    )

    # Optional: Image attachment (for Analysis mode)
    image_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="URL to attached image (screenshot for analysis)",
    )

    # Message metadata
    message_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        doc="""
        Additional message metadata:
        {
            "model_used": "gemini-1.5-flash",
            "tokens_used": 150,
            "rag_sources": ["doc_id_1", "doc_id_2"],
            "reply_type": "risky" | "funny" | "safe"  # For analysis mode
        }
        """,
    )

    # Relationship
    session: Mapped["Session"] = relationship("Session", back_populates="chat_logs")

    def __repr__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<ChatLog {self.role}: {preview}>"

