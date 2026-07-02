"""WUTT — AI Personal Stylist (Myanmar) — FastAPI Application Entry Point.

Start with:
    uvicorn main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings, check_production_safety
from database import init_db

# Import models so they register on Base.metadata before init_db() runs.
# This import is intentionally kept even though "unused" — SQLAlchemy's
# declarative Base discovers table definitions at import time.
import models  # noqa: F401


# ── Lifespan ───────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: safety-check secrets, then initialise database tables."""
    check_production_safety()
    init_db()
    yield


# ── App ────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware — must be added BEFORE routes (CLAUDE.md rule)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5500",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "https://wutt-frontend.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health Check ───────────────────────────────────────
@app.get("/health")
def health_check() -> dict[str, str]:
    """Liveness probe — returns 200 when the server is up."""
    return {"status": "ok"}


# ── Route registration ─────────────────────────────────
from routes.auth import router as auth_router           # Task 10
app.include_router(auth_router, prefix="/auth", tags=["Auth"])

from routes.profile import router as profile_router     # Task 11
app.include_router(profile_router, prefix="/profile", tags=["Profile"])

from routes.wardrobe import router as wardrobe_router   # Task 12
app.include_router(wardrobe_router, prefix="/wardrobe", tags=["Wardrobe"])

from routes.stylist import router as stylist_router     # Task 13
app.include_router(stylist_router, prefix="/stylist", tags=["Stylist"])
