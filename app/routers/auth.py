"""
Authentication Router - Supabase Auth integration.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, get_supabase
from app.models.user import User

router = APIRouter()


# ===========================================
# Schemas
# ===========================================

class UserCreate(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str
    display_name: str | None = None


class UserLogin(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User response."""
    id: uuid.UUID
    email: str
    display_name: str | None
    
    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    """Authentication response with tokens."""
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    """Token refresh request."""
    refresh_token: str


# ===========================================
# Auth Dependency
# ===========================================

async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Validate JWT and return current user.
    
    Usage:
        @router.get("/me")
        async def get_me(user: User = Depends(get_current_user)):
            return user
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    # Verify token with Supabase
    try:
        supabase = get_supabase()
        auth_response = supabase.auth.get_user(token)

        if not auth_response or not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

        supabase_user = auth_response.user

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}",
        )

    # Get user from our database
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(supabase_user.id))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in database",
        )

    return user


# ===========================================
# Routes
# ===========================================

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Register a new user.
    Creates user in Supabase Auth and our database.
    """
    supabase = get_supabase()

    # Register with Supabase Auth
    try:
        auth_response = supabase.auth.sign_up({
            "email": user_data.email,
            "password": user_data.password,
        })

        if not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration failed",
            )

        supabase_user = auth_response.user
        session = auth_response.session

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(e)}",
        )

    # Create user in our database
    user = User(
        id=uuid.UUID(supabase_user.id),
        email=user_data.email,
        display_name=user_data.display_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return AuthResponse(
        user=UserResponse.model_validate(user),
        access_token=session.access_token if session else "",
        refresh_token=session.refresh_token if session else "",
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Login with email and password.
    Returns JWT tokens for subsequent requests.
    """
    supabase = get_supabase()

    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password,
        })

        if not auth_response.user or not auth_response.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        supabase_user = auth_response.user
        session = auth_response.session

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Login failed: {str(e)}",
        )

    # Get user from our database
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(supabase_user.id))
    )
    user = result.scalar_one_or_none()

    # Auto-create user if not in our DB (e.g., registered via Supabase directly)
    if not user:
        user = User(
            id=uuid.UUID(supabase_user.id),
            email=credentials.email,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return AuthResponse(
        user=UserResponse.model_validate(user),
        access_token=session.access_token,
        refresh_token=session.refresh_token,
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    token_data: TokenRefresh,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Refresh access token using refresh token.
    """
    supabase = get_supabase()

    try:
        auth_response = supabase.auth.refresh_session(token_data.refresh_token)

        if not auth_response.user or not auth_response.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        supabase_user = auth_response.user
        session = auth_response.session

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token refresh failed: {str(e)}",
        )

    # Get user from database
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(supabase_user.id))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return AuthResponse(
        user=UserResponse.model_validate(user),
        access_token=session.access_token,
        refresh_token=session.refresh_token,
    )


@router.post("/logout")
async def logout(
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """
    Logout current user (invalidates token on Supabase).
    """
    supabase = get_supabase()

    try:
        supabase.auth.sign_out()
    except Exception:
        pass  # Ignore errors - token might already be invalid

    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Get current authenticated user.
    """
    return UserResponse.model_validate(user)

