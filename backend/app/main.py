"""
ElectroQuest Backend

A production-ready FastAPI application for electrical engineering learning.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import setup_logging
from app.api import auth, users, courses, learning, gamification, billing, admin, dashboard, journey, sources
from app.core.database import engine, Base
from app.models import models
from app.core.database import init_db
from app.core.cache import redis_ready
from app.core.rate_limit import RateLimitMiddleware

# Setup logging
setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    await init_db()
    yield
    # Shutdown


app = FastAPI(
    title="ElectroQuest API",
    description="Production-ready API for electrical engineering learning platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)


# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/ready", tags=["System"])
async def readiness_check():
    """Report dependency readiness; Redis degradation does not corrupt data."""
    database_ok = True
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        database_ok = False
    payload = {"ready": database_ok, "database": database_ok, "redis": await redis_ready()}
    return payload if database_ok else JSONResponse(payload, status_code=503)


# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(courses.router, prefix="/api/courses", tags=["Courses"])
app.include_router(learning.router, prefix="/api/learning", tags=["Learning"])
app.include_router(gamification.router, prefix="/api/gamification", tags=["Gamification"])
app.include_router(billing.router, prefix="/api/billing", tags=["Billing"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(journey.router, prefix="/api/journey", tags=["Adaptive Journey"])
app.include_router(sources.router, prefix="/api/sources", tags=["Source Library"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
