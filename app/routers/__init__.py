"""
API Routers for Rizzler.
"""

from app.routers.auth import router as auth_router
from app.routers.sessions import router as sessions_router
from app.routers.chat import router as chat_router
from app.routers.upload import router as upload_router

__all__ = ["auth_router", "sessions_router", "chat_router", "upload_router"]

