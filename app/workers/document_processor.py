"""
Document processing Celery task.
Handles async document extraction, chunking, and embedding.
"""

import asyncio
import uuid

from celery import shared_task

from app.workers.celery_app import celery_app


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
)
def process_document(
    self,
    user_id: str,
    source_id: str,
    filename: str,
    file_type: str,
    content_b64: str,
) -> dict:
    """
    Process a document asynchronously.
    
    Args:
        user_id: User UUID string
        source_id: Document source ID
        filename: Original filename
        file_type: File extension
        content_b64: Base64 encoded file content
    
    Returns:
        Processing result dict
    """
    import base64

    from app.database import get_db_context
    from app.services.document_service import process_document_sync

    # Decode content
    content = base64.b64decode(content_b64)

    # Run async function in event loop
    async def _process():
        async with get_db_context() as db:
            await process_document_sync(
                db=db,
                user_id=uuid.UUID(user_id),
                source_id=source_id,
                filename=filename,
                file_type=file_type,
                content=content,
            )

    try:
        asyncio.run(_process())
        return {
            "status": "success",
            "source_id": source_id,
            "filename": filename,
        }
    except Exception as e:
        return {
            "status": "failed",
            "source_id": source_id,
            "filename": filename,
            "error": str(e),
        }


@shared_task
def cleanup_failed_documents(older_than_hours: int = 24) -> int:
    """
    Clean up failed document processing attempts.
    
    Args:
        older_than_hours: Delete failures older than this
    
    Returns:
        Number of documents deleted
    """
    from datetime import datetime, timedelta

    from sqlalchemy import delete

    from app.database import get_db_context
    from app.models.document import Document, DocumentStatus

    async def _cleanup():
        async with get_db_context() as db:
            cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
            result = await db.execute(
                delete(Document).where(
                    Document.status == DocumentStatus.FAILED,
                    Document.created_at < cutoff,
                )
            )
            await db.commit()
            return result.rowcount

    return asyncio.run(_cleanup())

