"""
RAG Service - Vector search and embedding generation.
"""

import uuid
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Document, DocumentStatus


# OpenAI client for embeddings
_openai_client: AsyncOpenAI | None = None


def get_openai() -> AsyncOpenAI:
    """Get OpenAI client instance."""
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client


async def generate_embedding(text: str) -> list[float]:
    """
    Generate embedding vector for text using OpenAI.
    
    Args:
        text: Text to embed (max ~8000 tokens for text-embedding-3-small)
    
    Returns:
        List of floats representing the embedding vector
    """
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY not configured")

    client = get_openai()

    response = await client.embeddings.create(
        model=settings.embedding_model,
        input=text,
        dimensions=settings.embedding_dimensions,
    )

    return response.data[0].embedding


async def search_similar_chunks(
    db: AsyncSession,
    user_id: uuid.UUID,
    query: str,
    limit: int = 5,
    similarity_threshold: float = 0.5,
) -> list[dict[str, Any]]:
    """
    Search for similar document chunks using cosine similarity.
    
    Args:
        db: Database session
        user_id: Filter to user's documents only
        query: Search query text
        limit: Max number of results
        similarity_threshold: Minimum similarity score (0-1)
    
    Returns:
        List of matching chunks with similarity scores
    """
    # Generate embedding for query
    query_embedding = await generate_embedding(query)

    # Convert to string for SQL
    embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

    # Perform vector similarity search using pgvector
    # cosine distance: 1 - cosine_similarity
    # So lower distance = more similar
    sql = text("""
        SELECT 
            id,
            filename,
            content,
            chunk_index,
            1 - (embedding <=> :embedding::vector) as similarity
        FROM documents
        WHERE 
            user_id = :user_id
            AND status = :status
            AND embedding IS NOT NULL
            AND 1 - (embedding <=> :embedding::vector) > :threshold
        ORDER BY embedding <=> :embedding::vector
        LIMIT :limit
    """)

    result = await db.execute(
        sql,
        {
            "user_id": str(user_id),
            "embedding": embedding_str,
            "status": DocumentStatus.COMPLETED.value,
            "threshold": similarity_threshold,
            "limit": limit,
        },
    )

    rows = result.fetchall()

    return [
        {
            "id": row.id,
            "filename": row.filename,
            "content": row.content,
            "chunk_index": row.chunk_index,
            "similarity": float(row.similarity),
        }
        for row in rows
    ]


async def get_document_chunks(
    db: AsyncSession,
    user_id: uuid.UUID,
    source_id: str,
) -> list[Document]:
    """
    Get all chunks for a specific document.
    
    Args:
        db: Database session
        user_id: Filter to user's documents
        source_id: Document source ID
    
    Returns:
        List of document chunks ordered by index
    """
    result = await db.execute(
        select(Document)
        .where(
            Document.user_id == user_id,
            Document.source_id == source_id,
        )
        .order_by(Document.chunk_index)
    )

    return list(result.scalars().all())

