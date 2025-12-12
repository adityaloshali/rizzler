"""
Document Processing Service - Text extraction, chunking, and embedding.
"""

import io
import uuid
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Document, DocumentStatus
from app.services.rag_service import generate_embedding


# ===========================================
# Text Extraction
# ===========================================

def extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF bytes."""
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text_parts = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            return "\n\n".join(text_parts)
    except Exception as e:
        # Fallback to PyPDF2
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(io.BytesIO(content))
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            return "\n\n".join(text_parts)
        except Exception as e2:
            raise Exception(f"PDF extraction failed: {e}, {e2}")


def extract_text_from_docx(content: bytes) -> str:
    """Extract text from DOCX bytes."""
    from docx import Document as DocxDocument

    doc = DocxDocument(io.BytesIO(content))
    text_parts = []
    for para in doc.paragraphs:
        if para.text.strip():
            text_parts.append(para.text)
    return "\n\n".join(text_parts)


def extract_text(content: bytes, file_type: str) -> str:
    """
    Extract text from various file formats.
    
    Args:
        content: File content as bytes
        file_type: File extension (pdf, txt, md, docx)
    
    Returns:
        Extracted text
    """
    file_type = file_type.lower().lstrip(".")

    if file_type == "pdf":
        return extract_text_from_pdf(content)
    elif file_type == "docx":
        return extract_text_from_docx(content)
    elif file_type in ("txt", "md"):
        # Try common encodings
        for encoding in ["utf-8", "latin-1", "cp1252"]:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise Exception("Could not decode text file")
    else:
        raise Exception(f"Unsupported file type: {file_type}")


# ===========================================
# Text Chunking
# ===========================================

def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[dict[str, Any]]:
    """
    Split text into overlapping chunks for embedding.
    
    Uses a simple character-based approach with sentence boundaries.
    
    Args:
        text: Full text to chunk
        chunk_size: Target size per chunk (in characters)
        chunk_overlap: Overlap between chunks
    
    Returns:
        List of chunk dicts with 'content' and 'index'
    """
    if not text.strip():
        return []

    # Clean up the text
    text = text.strip()

    # Simple chunking strategy: split by paragraphs first
    paragraphs = text.split("\n\n")

    chunks = []
    current_chunk = ""
    chunk_index = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If adding this paragraph would exceed chunk size
        if len(current_chunk) + len(para) + 2 > chunk_size:
            # Save current chunk if not empty
            if current_chunk:
                chunks.append({
                    "content": current_chunk.strip(),
                    "index": chunk_index,
                    "token_count": len(current_chunk) // 4,  # Rough estimate
                })
                chunk_index += 1

                # Start new chunk with overlap
                # Take last portion of current chunk for overlap
                if chunk_overlap > 0:
                    words = current_chunk.split()
                    overlap_words = words[-chunk_overlap // 5:]  # ~5 chars per word
                    current_chunk = " ".join(overlap_words) + "\n\n" + para
                else:
                    current_chunk = para
            else:
                current_chunk = para
        else:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append({
            "content": current_chunk.strip(),
            "index": chunk_index,
            "token_count": len(current_chunk) // 4,
        })

    return chunks


# ===========================================
# Document Processing Pipeline
# ===========================================

async def process_document_sync(
    db: AsyncSession,
    user_id: uuid.UUID,
    source_id: str,
    filename: str,
    file_type: str,
    content: bytes,
) -> None:
    """
    Process a document: extract text, chunk, embed, and store.
    
    This is a synchronous version for simple deployments.
    For production, use Celery task instead.
    
    Args:
        db: Database session
        user_id: Owner of the document
        source_id: Unique ID for this upload
        filename: Original filename
        file_type: File extension
        content: File content as bytes
    """
    # Delete any existing chunks with this source_id (for re-processing)
    await db.execute(
        delete(Document).where(
            Document.source_id == source_id,
            Document.user_id == user_id,
        )
    )

    try:
        # Step 1: Extract text
        text = extract_text(content, file_type)

        if not text.strip():
            raise Exception("No text could be extracted from document")

        # Step 2: Chunk the text
        chunks = chunk_text(text)

        if not chunks:
            raise Exception("Document produced no chunks")

        # Step 3: Generate embeddings and store chunks
        for chunk_data in chunks:
            # Generate embedding
            try:
                embedding = await generate_embedding(chunk_data["content"])
            except Exception as e:
                # Skip embedding errors but log them
                print(f"Embedding error for chunk {chunk_data['index']}: {e}")
                embedding = None

            # Create document chunk
            doc = Document(
                user_id=user_id,
                filename=filename,
                file_type=file_type,
                source_id=source_id,
                chunk_index=chunk_data["index"],
                content=chunk_data["content"],
                token_count=chunk_data.get("token_count"),
                embedding=embedding,
                status=DocumentStatus.COMPLETED if embedding else DocumentStatus.FAILED,
            )
            db.add(doc)

        await db.commit()

    except Exception as e:
        # Create a failed placeholder
        failed_doc = Document(
            user_id=user_id,
            filename=filename,
            file_type=file_type,
            source_id=source_id,
            chunk_index=0,
            content="",
            status=DocumentStatus.FAILED,
            error_message=str(e),
        )
        db.add(failed_doc)
        await db.commit()
        raise

