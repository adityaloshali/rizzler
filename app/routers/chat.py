"""
Chat Router - Core conversation endpoint.
Handles all three modes: Tutor, Practice, Analysis.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.chat import ChatLog, MessageRole
from app.models.session import Session, SessionMode
from app.models.user import User
from app.routers.auth import get_current_user
from app.services.llm_router import LLMRouter, get_llm_router

router = APIRouter()


# ===========================================
# Schemas
# ===========================================

class ChatMessage(BaseModel):
    """A single chat message."""
    role: MessageRole
    content: str
    image_url: str | None = None
    message_metadata: dict[str, Any] | None = None


class ChatRequest(BaseModel):
    """Chat request payload."""
    session_id: uuid.UUID
    message: str = Field(min_length=1, max_length=10000)
    image_url: str | None = Field(
        default=None,
        description="Image URL for Analysis mode (screenshot)",
    )


class ChatResponse(BaseModel):
    """Chat response payload."""
    message: ChatMessage
    session_id: uuid.UUID
    suggestions: list[str] | None = Field(
        default=None,
        description="Reply suggestions for Analysis mode",
    )


class ChatHistoryResponse(BaseModel):
    """Chat history response."""
    session_id: uuid.UUID
    mode: SessionMode
    messages: list[ChatMessage]
    total: int


# ===========================================
# Routes
# ===========================================

@router.post("/", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm: LLMRouter = Depends(get_llm_router),
) -> ChatResponse:
    """
    Send a message and get AI response.
    
    The response varies based on session mode:
    - **Tutor**: RAG-enhanced answer from knowledge base
    - **Practice**: Roleplay response from persona
    - **Analysis**: Reply suggestions (Risky, Funny, Safe)
    """
    # Get session
    result = await db.execute(
        select(Session)
        .where(Session.id == request.session_id, Session.user_id == user.id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Get recent chat history for context
    history_result = await db.execute(
        select(ChatLog)
        .where(ChatLog.session_id == session.id)
        .order_by(ChatLog.created_at.desc())
        .limit(20)
    )
    history = list(reversed(history_result.scalars().all()))

    # Convert to message format
    messages = [
        {"role": msg.role.value, "content": msg.content}
        for msg in history
    ]

    # Save user message
    user_message = ChatLog(
        session_id=session.id,
        role=MessageRole.USER,
        content=request.message,
        image_url=request.image_url,
    )
    db.add(user_message)

    # Generate response based on mode
    try:
        if session.mode == SessionMode.TUTOR:
            response_content, metadata = await llm.tutor_response(
                user_id=user.id,
                messages=messages,
                user_message=request.message,
                db=db,
            )
            suggestions = None

        elif session.mode == SessionMode.PRACTICE:
            response_content, metadata = await llm.practice_response(
                messages=messages,
                user_message=request.message,
                persona_settings=session.persona_settings or {},
            )
            suggestions = None

        elif session.mode == SessionMode.ANALYSIS:
            response_content, suggestions, metadata = await llm.analysis_response(
                user_id=user.id,
                messages=messages,
                user_message=request.message,
                image_url=request.image_url,
                db=db,
            )

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown session mode: {session.mode}",
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI generation failed: {str(e)}",
        )

    # Save assistant message
    assistant_message = ChatLog(
        session_id=session.id,
        role=MessageRole.ASSISTANT,
        content=response_content,
        message_metadata=metadata,
    )
    db.add(assistant_message)

    # Update session stats
    session.message_count += 2

    await db.commit()

    return ChatResponse(
        message=ChatMessage(
            role=MessageRole.ASSISTANT,
            content=response_content,
            message_metadata=metadata,
        ),
        session_id=session.id,
        suggestions=suggestions,
    )


@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
) -> ChatHistoryResponse:
    """
    Get chat history for a session.
    Returns messages in chronological order.
    """
    # Verify session belongs to user
    result = await db.execute(
        select(Session)
        .where(Session.id == session_id, Session.user_id == user.id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Get messages
    history_result = await db.execute(
        select(ChatLog)
        .where(ChatLog.session_id == session_id)
        .order_by(ChatLog.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    messages = history_result.scalars().all()

    return ChatHistoryResponse(
        session_id=session_id,
        mode=session.mode,
        messages=[
            ChatMessage(
                role=msg.role,
                content=msg.content,
                image_url=msg.image_url,
                message_metadata=msg.message_metadata,
            )
            for msg in messages
        ],
        total=session.message_count,
    )


@router.delete("/history/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def clear_chat_history(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Clear all chat history for a session.
    The session itself is preserved.
    """
    # Verify session belongs to user
    result = await db.execute(
        select(Session)
        .where(Session.id == session_id, Session.user_id == user.id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Delete all messages
    await db.execute(
        ChatLog.__table__.delete().where(ChatLog.session_id == session_id)
    )

    # Reset message count
    session.message_count = 0
    session.summary = None

    await db.commit()

