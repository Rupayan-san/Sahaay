from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.assignments import initialize_assignment_indexes, router as assignments_router
from app.api.routes.leaderboard import router as leaderboard_router
from app.api.routes.issues import router as issues_router
from app.api.routes.ratings import initialize_rating_indexes, router as ratings_router
from app.api.routes.reports import router as reports_router
from app.api.routes.verification import router as verification_router
from app.api.routes.volunteers import router as volunteers_router
from app.core.database import close_mongo_connection, connect_to_mongo
from app.api.routes.ingestion import router as ingestion_router
from app.services.embedding_service import get_embedding_service
from app.services.gamification import get_gamification_service
from app.services.image_verification import get_image_verification_service
from app.services.matching_engine import get_matching_engine
from app.tasks.scheduled_reports import start_scheduled_reports, stop_scheduled_reports


@asynccontextmanager
async def lifespan(_: FastAPI):
    await connect_to_mongo()
    await get_embedding_service().initialize()
    await get_matching_engine().initialize()
    await get_gamification_service().initialize()
    await get_image_verification_service().initialize()
    await initialize_assignment_indexes()
    await initialize_rating_indexes()
    await start_scheduled_reports()
    try:
        yield
    finally:
        await stop_scheduled_reports()
        await close_mongo_connection()


app = FastAPI(title="Community Coordination Platform API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

app.include_router(ingestion_router)
app.include_router(issues_router)
app.include_router(volunteers_router)
app.include_router(assignments_router)
app.include_router(verification_router)
app.include_router(ratings_router)
app.include_router(leaderboard_router)
app.include_router(reports_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    from app.core.database import get_database
    try:
        get_database()
        db_status = "connected"
    except RuntimeError:
        db_status = "disconnected"
    return {"status": "ok", "database": db_status}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: object, exc: RequestValidationError) -> JSONResponse:
    messages: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", []) if part != "body")
        message = error.get("msg", "Invalid value")
        messages.append(f"{location}: {message}" if location else message)

    return JSONResponse(status_code=400, content={"detail": "; ".join(messages) or "Invalid request payload"})
