"""Route modules for the FastAPI application."""

from app.api.routes.ingestion import router as ingestion_router
from app.api.routes.issues import router as issues_router
from app.api.routes.volunteers import router as volunteers_router
from app.api.routes.assignments import router as assignments_router
from app.api.routes.ratings import router as ratings_router
from app.api.routes.leaderboard import router as leaderboard_router
from app.api.routes.reports import router as reports_router
from app.api.routes.verification import router as verification_router

__all__ = [
    "ingestion_router",
    "issues_router",
    "volunteers_router",
    "assignments_router",
    "ratings_router",
    "leaderboard_router",
    "reports_router",
    "verification_router",
]
