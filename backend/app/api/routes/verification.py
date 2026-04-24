from __future__ import annotations

import logging
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from app.core.auth import AuthenticatedActor, require_admin
from app.core.database import get_assignment_collection
from app.models.assignment import SubmissionData
from app.models.verification import ImageVerificationRequest, ImageVerificationResponse, VerificationVerdict
from app.services.gamification import get_gamification_service
from app.services.image_verification import (
    ImageVerificationError,
    get_image_verification_service,
)
from app.services.trust_calculator import get_trust_calculator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["verification"])


@router.post(
    "/assignments/{assignment_id}/verify-images",
    response_model=ImageVerificationResponse,
    status_code=status.HTTP_200_OK,
)
async def verify_assignment_images(
    assignment_id: str,
    payload: ImageVerificationRequest,
    _: AuthenticatedActor = Depends(require_admin),
) -> ImageVerificationResponse:
    assignment_document = await _get_assignment_document(assignment_id)
    if assignment_document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    try:
        submission_data = SubmissionData.model_validate(assignment_document.get("submission_data") or {})
    except ValidationError:
        submission_data = SubmissionData()

    submitted_images = set(submission_data.all_images())
    if submitted_images and any(image_path not in submitted_images for image_path in payload.image_paths):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="image_paths")

    verification_service = get_image_verification_service()
    try:
        verification_response = await verification_service.verify_assignment_images(
            assignment_id=str(assignment_document["assignment_id"]),
            image_paths=payload.image_paths,
        )
        await _handle_failed_verifications(assignment_document, verification_response)
        return verification_response
    except ImageVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected verification failure for assignment %s", assignment_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Image verification failed",
        ) from exc


async def verify_assignment_submission_or_raise(assignment_document: dict[str, Any]) -> None:
    try:
        submission_data = SubmissionData.model_validate(assignment_document.get("submission_data") or {})
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="submission_data") from exc

    image_paths = submission_data.all_images()
    if not image_paths:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="submission_data.after_images")

    verification_service = get_image_verification_service()
    verification_response = await verification_service.verify_assignment_images(
        assignment_id=str(assignment_document["assignment_id"]),
        image_paths=image_paths,
    )
    await _handle_failed_verifications(assignment_document, verification_response)

    if any(result.overall_verdict == VerificationVerdict.FAIL for result in verification_response.results):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image verification failed")
    if any(result.overall_verdict == VerificationVerdict.SUSPICIOUS for result in verification_response.results):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image verification suspicious")


async def _get_assignment_document(assignment_identifier: str) -> dict[str, Any] | None:
    collection = get_assignment_collection()
    query_options: list[dict[str, Any]] = [{"assignment_id": assignment_identifier}]
    if ObjectId.is_valid(assignment_identifier):
        query_options.append({"_id": ObjectId(assignment_identifier)})
    return await collection.find_one({"$or": query_options})


async def _handle_failed_verifications(
    assignment_document: dict[str, Any],
    verification_response: ImageVerificationResponse,
) -> None:
    if not any(result.overall_verdict == VerificationVerdict.FAIL for result in verification_response.results):
        return

    volunteer_id = str(assignment_document.get("volunteer_id", "")).strip()
    if not volunteer_id:
        return

    await get_trust_calculator().recalculate_trust_score(volunteer_id)
    await get_gamification_service().refresh_volunteer_progress(volunteer_id)
