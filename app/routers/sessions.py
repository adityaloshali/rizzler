"""
Sessions Router - Manage conversation sessions.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.session import Session, SessionMode
from app.models.user import User
from app.routers.auth import get_current_user

router = APIRouter()


# ===========================================
# Schemas
# ===========================================

class PersonaSettings(BaseModel):
    """Persona configuration for Practice mode."""
    name: str = Field(default="Alex", max_length=50)
    age: int = Field(default=25, ge=18, le=99)
    gender: str = Field(default="female", max_length=20)
    vibe: str = Field(
        default="friendly and flirty",
        max_length=200,
        description="Personality description",
    )
    backstory: str | None = Field(
        default=None,
        max_length=500,
        description="How you met this person",
    )
    scenario: str | None = Field(
        default=None,
        max_length=200,
        description="Current situation (e.g., 'first date texting')",
    )


class SessionCreate(BaseModel):
    """Create a new session."""
    title: str = Field(default="New Chat", max_length=200)
    mode: SessionMode = SessionMode.TUTOR
    persona_settings: PersonaSettings | None = None


class SessionUpdate(BaseModel):
    """Update session details."""
    title: str | None = Field(default=None, max_length=200)
    mode: SessionMode | None = None
    persona_settings: PersonaSettings | None = None


class SessionResponse(BaseModel):
    """Session response."""
    id: uuid.UUID
    title: str
    mode: SessionMode
    persona_settings: dict[str, Any] | None
    message_count: int
    created_at: str
    last_active: str

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """Paginated session list."""
    sessions: list[SessionResponse]
    total: int
    page: int
    per_page: int


# ===========================================
# Routes
# ===========================================

@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_data: SessionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """
    Create a new conversation session.
    """
    session = Session(
        user_id=user.id,
        title=session_data.title,
        mode=session_data.mode,
        persona_settings=(
            session_data.persona_settings.model_dump()
            if session_data.persona_settings
            else None
        ),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return SessionResponse(
        id=session.id,
        title=session.title,
        mode=session.mode,
        persona_settings=session.persona_settings,
        message_count=session.message_count,
        created_at=session.created_at.isoformat(),
        last_active=session.last_active.isoformat(),
    )


@router.get("/", response_model=SessionListResponse)
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    mode: SessionMode | None = Query(default=None, description="Filter by mode"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> SessionListResponse:
    """
    List all sessions for the current user.
    Supports filtering by mode and pagination.
    """
    # Base query
    query = select(Session).where(Session.user_id == user.id)

    # Filter by mode if specified
    if mode:
        query = query.where(Session.mode == mode)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    query = (
        query
        .order_by(Session.last_active.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )

    result = await db.execute(query)
    sessions = result.scalars().all()

    return SessionListResponse(
        sessions=[
            SessionResponse(
                id=s.id,
                title=s.title,
                mode=s.mode,
                persona_settings=s.persona_settings,
                message_count=s.message_count,
                created_at=s.created_at.isoformat(),
                last_active=s.last_active.isoformat(),
            )
            for s in sessions
        ],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """
    Get a specific session by ID.
    """
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

    return SessionResponse(
        id=session.id,
        title=session.title,
        mode=session.mode,
        persona_settings=session.persona_settings,
        message_count=session.message_count,
        created_at=session.created_at.isoformat(),
        last_active=session.last_active.isoformat(),
    )


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: uuid.UUID,
    update_data: SessionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """
    Update session details (title, mode, persona settings).
    """
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

    # Update fields if provided
    if update_data.title is not None:
        session.title = update_data.title
    if update_data.mode is not None:
        session.mode = update_data.mode
    if update_data.persona_settings is not None:
        session.persona_settings = update_data.persona_settings.model_dump()

    await db.commit()
    await db.refresh(session)

    return SessionResponse(
        id=session.id,
        title=session.title,
        mode=session.mode,
        persona_settings=session.persona_settings,
        message_count=session.message_count,
        created_at=session.created_at.isoformat(),
        last_active=session.last_active.isoformat(),
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a session and all its chat history.
    """
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

    await db.delete(session)
    await db.commit()

