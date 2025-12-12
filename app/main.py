"""
Rizzler - AI Dating Coach & Companion
FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import close_db, init_db


# ===========================================
# Lifespan Events
# ===========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    print(f"🚀 Starting {settings.app_name} v0.1.0")
    print(f"📦 Environment: {settings.app_env}")

    # Initialize database (creates tables if needed)
    if settings.database_url:
        try:
            await init_db()
            print("✅ Database initialized")
        except Exception as e:
            print(f"⚠️  Database init skipped: {e}")

    yield

    # Shutdown
    print("👋 Shutting down...")
    await close_db()


# ===========================================
# FastAPI App
# ===========================================

app = FastAPI(
    title=settings.app_name,
    description="""
    🔥 **Rizzler** - Your AI Dating Coach & Companion
    
    An intelligent dating assistant with three powerful modes:
    
    - **Tutor Mode**: Learn from your uploaded dating guides & resources
    - **Practice Mode**: Roleplay conversations with customizable personas  
    - **Analysis Mode**: Get AI-powered reply suggestions for real chats
    
    ---
    
    Built with ❤️ using FastAPI, Supabase, and modern LLMs.
    """,
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)


# ===========================================
# Middleware
# ===========================================

# CORS - Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================================
# Exception Handlers
# ===========================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler.
    In production, logs errors; in development, returns details.
    """
    if settings.debug:
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "detail": str(exc),
                "type": type(exc).__name__,
            },
        )
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error"},
    )


# ===========================================
# Health Check Routes
# ===========================================

@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    """Root endpoint - API info."""
    return {
        "app": settings.app_name,
        "version": "0.1.0",
        "status": "operational",
        "docs": "/docs" if settings.debug else "disabled",
    }


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, Any]:
    """
    Health check endpoint for load balancers and monitoring.
    Returns service status and basic diagnostics.
    """
    health_status: dict[str, Any] = {
        "status": "healthy",
        "environment": settings.app_env,
        "services": {},
    }

    # Check database connectivity
    if settings.database_url:
        try:
            from app.database import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                await session.execute("SELECT 1")  # type: ignore
            health_status["services"]["database"] = "connected"
        except Exception as e:
            health_status["services"]["database"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
    else:
        health_status["services"]["database"] = "not configured"

    return health_status


@app.get("/health/ready", tags=["Health"])
async def readiness_check() -> dict[str, str]:
    """
    Readiness probe for Kubernetes/container orchestration.
    Returns 200 only when the app is ready to serve traffic.
    """
    # Add checks for required services here
    return {"status": "ready"}


@app.get("/health/live", tags=["Health"])
async def liveness_check() -> dict[str, str]:
    """
    Liveness probe for Kubernetes/container orchestration.
    Returns 200 if the app is running (even if dependencies are down).
    """
    return {"status": "alive"}


# ===========================================
# Register Routers
# ===========================================

from app.routers import auth_router, chat_router, sessions_router, upload_router

app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(sessions_router, prefix="/api/v1/sessions", tags=["Sessions"])
app.include_router(chat_router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(upload_router, prefix="/api/v1/upload", tags=["Upload"])


# ===========================================
# Development Server
# ===========================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=settings.workers if not settings.debug else 1,
    )

