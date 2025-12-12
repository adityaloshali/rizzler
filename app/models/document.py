"""
Document model - stores uploaded knowledge base content with embeddings for RAG.
"""

import uuid
from enum import Enum

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.config import settings


class DocumentStatus(str, Enum):
    """Document processing status."""

    PENDING = "pending"  # Uploaded, waiting for processing
    PROCESSING = "processing"  # Currently being processed
    COMPLETED = "completed"  # Ready for RAG queries
    FAILED = "failed"  # Processing failed


class Document(Base):
    """
    Document model for RAG knowledge base.
    
    Stores chunked content with vector embeddings for semantic search.
    Each row represents a chunk of a larger document.
    """

    __tablename__ = "documents"

    # Foreign key to user
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Source file info
    filename: Mapped[str] = mapped_column(
        String(255),
        doc="Original uploaded filename",
    )
    file_type: Mapped[str] = mapped_column(
        String(20),
        doc="File extension: pdf, txt, md, docx",
    )
    source_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        doc="Groups chunks from the same source file",
    )

    # Chunk info
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        default=0,
        doc="Position of this chunk in the source document",
    )
    content: Mapped[str] = mapped_column(
        Text,
        doc="The actual text content of this chunk",
    )
    token_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Approximate token count for this chunk",
    )

    # Vector embedding for semantic search
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dimensions),
        nullable=True,
        doc="OpenAI text-embedding-3-small vector",
    )

    # Processing status
    status: Mapped[DocumentStatus] = mapped_column(
        String(20),
        default=DocumentStatus.PENDING,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Error details if processing failed",
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="documents")

    def __repr__(self) -> str:
        return f"<Document {self.filename} chunk={self.chunk_index}>"


# Import User for type checking
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User

