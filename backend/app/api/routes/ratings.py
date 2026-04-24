from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from app.core.auth import AuthenticatedActor, require_admin
from app.core.database import get_assignment_collection, get_rating_collection
from app.models.assignment import AssignmentStatus
from app.models.rating import RatingCreateRequest, RatingRecord, RatingResponse
from app.services.gamification import get_gamification_service
from app.services.trust_calculator import get_trust_calculator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ratings"])


async def initialize_rating_indexes() -> None:
    collection = get_rating_collection()
    await collection.create_index("rating_id", unique=True)
    await collection.create_index("assignment_id", unique=True)
    await collection.create_index([("volunteer_id", ASCENDING), ("created_at", DESCENDING)])


@router.post(
    "/assignments/{assignment_id}/rate",
    response_model=RatingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def rate_assignment(
    assignment_id: str,
    payload: RatingCreateRequest,
    actor: AuthenticatedActor = Depends(require_admin),
) -> RatingResponse:
    assignment_document = await _get_assignment_document(assignment_id)
    if assignment_document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    if assignment_document.get("status") != AssignmentStatus.COMPLETED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignment must be completed before rating")

    rating_document = {
        "rating_id": str(uuid.uuid4()),
        "assignment_id": str(assignment_document["assignment_id"]),
        "volunteer_id": str(assignment_document["volunteer_id"]),
        "admin_id": actor.actor_id,
        "stars": payload.stars,
        "review": payload.review,
        "created_at": datetime.now(timezone.utc),
    }

    try:
        insert_result = await get_rating_collection().insert_one(rating_document)
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already rated") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected rating persistence failure for assignment %s", assignment_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Rating failed") from exc

    rating_document["_id"] = insert_result.inserted_id
    trust_score = await get_trust_calculator().recalculate_trust_score(str(assignment_document["volunteer_id"]))
    awarded_points = await get_gamification_service().award_rating_points(
        assignment_id=str(assignment_document["assignment_id"]),
        volunteer_id=str(assignment_document["volunteer_id"]),
        stars=payload.stars,
    )

    return RatingResponse(
        data=RatingRecord.from_mongo(rating_document),
        awarded_points=awarded_points,
        trust_score=trust_score,
    )


async def _get_assignment_document(assignment_identifier: str) -> dict[str, Any] | None:
    collection = get_assignment_collection()
    query_options: list[dict[str, Any]] = [{"assignment_id": assignment_identifier}]
    if ObjectId.is_valid(assignment_identifier):
        query_options.append({"_id": ObjectId(assignment_identifier)})
    return await collection.find_one({"$or": query_options})
