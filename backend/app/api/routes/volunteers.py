from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.models.volunteer import (
    VolunteerCreateRequest,
    VolunteerListResponse,
    VolunteerMatchResponse,
    VolunteerResponse,
)
from app.services.matching_engine import MINIMUM_MATCH_SCORE, get_matching_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["volunteers"])


@router.post("/volunteers", response_model=VolunteerResponse, status_code=status.HTTP_201_CREATED)
async def create_volunteer(payload: VolunteerCreateRequest) -> VolunteerResponse:
    matching_engine = get_matching_engine()

    try:
        volunteer = await matching_engine.register_volunteer(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected volunteer registration failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Volunteer registration failed",
        ) from exc

    return VolunteerResponse(data=volunteer)


@router.get("/volunteers", response_model=VolunteerListResponse, status_code=status.HTTP_200_OK)
async def get_volunteers(
    limit: int = Query(default=50, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
    active_only: bool = Query(default=False),
) -> VolunteerListResponse:
    matching_engine = get_matching_engine()

    try:
        volunteers = await matching_engine.list_volunteers(limit=limit, skip=skip, active_only=active_only)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected volunteer listing failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch volunteers",
        ) from exc

    return VolunteerListResponse(data=volunteers)


@router.post("/issues/{issue_id}/match", response_model=VolunteerMatchResponse, status_code=status.HTTP_200_OK)
async def match_issue_to_volunteers(issue_id: str) -> VolunteerMatchResponse:
    matching_engine = get_matching_engine()

    try:
        matches = await matching_engine.match_issue(issue_id, limit=3, minimum_score=MINIMUM_MATCH_SCORE)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected volunteer matching failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Volunteer matching failed",
        ) from exc

    return VolunteerMatchResponse(matches=[match.to_response_model() for match in matches])
