"""
Upload Router - Document upload and knowledge base management.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.document import Document, DocumentStatus
from app.models.user import User
from app.routers.auth import get_current_user

router = APIRouter()


# ===========================================
# Schemas
# ===========================================

class DocumentResponse(BaseModel):
    """Document/chunk response."""
    id: uuid.UUID
    filename: str
    file_type: str
    status: DocumentStatus
    chunk_index: int
    content_preview: str
    created_at: str

    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    """Upload response."""
    message: str
    source_id: str
    filename: str
    status: DocumentStatus


class DocumentListResponse(BaseModel):
    """List of uploaded documents (grouped by source)."""
    documents: list[dict[str, Any]]
    total: int


class KnowledgeSearchRequest(BaseModel):
    """Search knowledge base."""
    query: str
    limit: int = 5


class KnowledgeSearchResult(BaseModel):
    """Search result."""
    chunk_id: uuid.UUID
    filename: str
    content: str
    similarity: float


# ===========================================
# Allowed File Types
# ===========================================

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def validate_file(file: UploadFile) -> str:
    """Validate uploaded file and return extension."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    # Check extension
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Check size (from content-length header if available)
    if file.size and file.size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {settings.max_upload_size_mb}MB",
        )

    return ext


# ===========================================
# Routes
# ===========================================

@router.post("/", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """
    Upload a document to the knowledge base.
    
    Supported formats: PDF, TXT, MD, DOCX
    
    The document is processed asynchronously:
    1. File is saved
    2. Text is extracted
    3. Content is chunked
    4. Embeddings are generated
    5. Chunks are stored for RAG
    """
    ext = validate_file(file)

    # Generate source ID to group chunks from same file
    source_id = str(uuid.uuid4())

    # Read file content
    content = await file.read()

    # Create placeholder document (will be processed by Celery)
    document = Document(
        user_id=user.id,
        filename=file.filename or "unknown",
        file_type=ext.lstrip("."),
        source_id=source_id,
        chunk_index=0,
        content="Processing...",  # Will be updated by worker
        status=DocumentStatus.PENDING,
    )
    db.add(document)
    await db.commit()

    # TODO: Queue Celery task for processing
    # from app.workers.document_processor import process_document
    # process_document.delay(source_id, content, ext)

    # For now, we'll process synchronously (move to Celery later)
    try:
        from app.services.document_service import process_document_sync

        await process_document_sync(
            db=db,
            user_id=user.id,
            source_id=source_id,
            filename=file.filename or "unknown",
            file_type=ext.lstrip("."),
            content=content,
        )
        status_result = DocumentStatus.COMPLETED

    except Exception as e:
        document.status = DocumentStatus.FAILED
        document.error_message = str(e)
        await db.commit()
        status_result = DocumentStatus.FAILED

    return DocumentUploadResponse(
        message="Document uploaded and queued for processing",
        source_id=source_id,
        filename=file.filename or "unknown",
        status=status_result,
    )


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> DocumentListResponse:
    """
    List all uploaded documents (grouped by source file).
    """
    # Get distinct source files with stats
    query = (
        select(
            Document.source_id,
            Document.filename,
            Document.file_type,
            Document.status,
            func.count(Document.id).label("chunk_count"),
            func.min(Document.created_at).label("created_at"),
        )
        .where(Document.user_id == user.id)
        .group_by(
            Document.source_id,
            Document.filename,
            Document.file_type,
            Document.status,
        )
        .order_by(func.min(Document.created_at).desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )

    result = await db.execute(query)
    rows = result.all()

    # Count total unique sources
    count_query = (
        select(func.count(func.distinct(Document.source_id)))
        .where(Document.user_id == user.id)
    )
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    documents = [
        {
            "source_id": row.source_id,
            "filename": row.filename,
            "file_type": row.file_type,
            "status": row.status,
            "chunk_count": row.chunk_count,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]

    return DocumentListResponse(documents=documents, total=total)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    source_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a document and all its chunks from the knowledge base.
    """
    # Verify document belongs to user
    result = await db.execute(
        select(Document)
        .where(Document.source_id == source_id, Document.user_id == user.id)
        .limit(1)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Delete all chunks with this source_id
    await db.execute(
        Document.__table__.delete().where(
            Document.source_id == source_id,
            Document.user_id == user.id,
        )
    )
    await db.commit()


@router.post("/search", response_model=list[KnowledgeSearchResult])
async def search_knowledge(
    request: KnowledgeSearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeSearchResult]:
    """
    Search the knowledge base using semantic similarity.
    Returns the most relevant chunks for a given query.
    """
    from app.services.rag_service import search_similar_chunks

    results = await search_similar_chunks(
        db=db,
        user_id=user.id,
        query=request.query,
        limit=request.limit,
    )

    return [
        KnowledgeSearchResult(
            chunk_id=r["id"],
            filename=r["filename"],
            content=r["content"],
            similarity=r["similarity"],
        )
        for r in results
    ]

