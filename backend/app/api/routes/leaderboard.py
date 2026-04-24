from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.models.rating import (
    LeaderboardCategory,
    LeaderboardResponse,
    LeaderboardTimeframe,
)
from app.services.gamification import get_gamification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["leaderboard"])


@router.get("/leaderboard", response_model=LeaderboardResponse, status_code=status.HTTP_200_OK)
async def get_leaderboard(
    category: LeaderboardCategory = Query(default=LeaderboardCategory.POINTS),
    timeframe: LeaderboardTimeframe = Query(default=LeaderboardTimeframe.ALL_TIME),
    limit: int = Query(default=10, ge=1, le=100),
) -> LeaderboardResponse:
    try:
        return await get_gamification_service().get_leaderboard(
            category=category,
            timeframe=timeframe,
            limit=limit,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected leaderboard failure")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch leaderboard") from exc
