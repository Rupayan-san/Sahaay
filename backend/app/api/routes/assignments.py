from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import PurePath
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pymongo import ASCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.auth import AuthenticatedActor, get_current_actor
from app.core.database import get_assignment_collection, get_issue_collection, get_volunteer_collection
from app.models.assignment import (
    AssignmentAdminActionRequest,
    AssignmentApplyRequest,
    AssignmentRecord,
    AssignmentRejectRequest,
    AssignmentResponse,
    AssignmentStatus,
    AssignmentSubmitRequest,
    SubmissionData,
)
from app.models.issue import IssueStatus
from app.api.routes.verification import verify_assignment_submission_or_raise
from app.services.gamification import get_gamification_service
from app.services.notification_service import get_notification_service
from app.services.trust_calculator import get_trust_calculator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["assignments"])

ACTIVE_ASSIGNMENT_STATUSES = {
    AssignmentStatus.ASSIGNED.value,
    AssignmentStatus.IN_PROGRESS.value,
    AssignmentStatus.SUBMITTED.value,
    AssignmentStatus.VERIFIED.value,
}
UPLOAD_DIRECTORY_NAME = "uploads"


async def initialize_assignment_indexes() -> None:
    collection = get_assignment_collection()
    await collection.create_index("assignment_id", unique=True)
    await collection.create_index([("issue_id", ASCENDING), ("volunteer_id", ASCENDING)], unique=True)
    await collection.create_index([("issue_id", ASCENDING), ("status", ASCENDING)])
    await collection.create_index([("volunteer_id", ASCENDING), ("status", ASCENDING)])


@router.post("/issues/{issue_id}/apply", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
async def apply_to_issue(
    issue_id: str,
    payload: AssignmentApplyRequest,
    background_tasks: BackgroundTasks,
    actor: AuthenticatedActor = Depends(get_current_actor),
) -> AssignmentResponse:
    _ensure_volunteer_actor(actor)
    _ensure_actor_matches_volunteer(actor, payload.volunteer_id)

    issue_document = await _get_issue_document(issue_id)
    if issue_document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

    if issue_document.get("status") != IssueStatus.OPEN.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Issue no longer accepting applications",
        )

    volunteer_document = await _get_volunteer_document(payload.volunteer_id)
    if volunteer_document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Volunteer not found")
    if not bool(volunteer_document.get("is_active", False)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Volunteer is not active")

    current_time = datetime.now(timezone.utc)
    document = {
        "assignment_id": str(uuid.uuid4()),
        "issue_id": str(issue_document["issue_id"]),
        "volunteer_id": payload.volunteer_id,
        "status": AssignmentStatus.APPLIED.value,
        "applied_at": current_time,
        "assigned_at": None,
        "started_at": None,
        "submitted_at": None,
        "completed_at": None,
        "submission_data": None,
        "admin_notes": None,
        "application_message": payload.message,
        "created_at": current_time,
        "updated_at": current_time,
    }

    try:
        insert_result = await get_assignment_collection().insert_one(document)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already applied",
        ) from exc

    document["_id"] = insert_result.inserted_id
    background_tasks.add_task(
        get_notification_service().notify_admin,
        f"Volunteer {volunteer_document['name']} applied for issue {issue_document['title']}",
        (
            f"Volunteer {volunteer_document['name']} ({volunteer_document['email']}) applied for issue "
            f"{issue_document['title']} at {issue_document['location']}."
            + (f"\n\nApplication message:\n{payload.message}" if payload.message else "")
        ),
    )
    return AssignmentResponse(data=AssignmentRecord.from_mongo(document))


@router.post("/assignments/{assignment_id}/assign", response_model=AssignmentResponse, status_code=status.HTTP_200_OK)
async def assign_application(
    assignment_id: str,
    payload: AssignmentAdminActionRequest,
    background_tasks: BackgroundTasks,
    actor: AuthenticatedActor = Depends(get_current_actor),
) -> AssignmentResponse:
    _ensure_admin_actor(actor)
    _ensure_actor_matches_admin(actor, payload.admin_id)

    assignment_document = await _get_assignment_document(assignment_id)
    if assignment_document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    _ensure_transition_allowed(assignment_document["status"], AssignmentStatus.ASSIGNED)
    issue_document = await _get_issue_document(assignment_document["issue_id"])
    if issue_document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    if issue_document.get("status") == IssueStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Issue no longer accepting applications",
        )

    conflict = await get_assignment_collection().find_one(
        {
            "issue_id": assignment_document["issue_id"],
            "status": {"$in": list(ACTIVE_ASSIGNMENT_STATUSES)},
            "assignment_id": {"$ne": assignment_document["assignment_id"]},
        }
    )
    if conflict is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Issue already has an assigned volunteer",
        )

    current_time = datetime.now(timezone.utc)
    updated_document = await get_assignment_collection().find_one_and_update(
        {"_id": assignment_document["_id"], "status": AssignmentStatus.APPLIED.value},
        {
            "$set": {
                "status": AssignmentStatus.ASSIGNED.value,
                "assigned_at": current_time,
                "updated_at": current_time,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if updated_document is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change from applied to assigned")

    volunteer_document = await _get_volunteer_document(assignment_document["volunteer_id"])

    await _set_issue_status(str(assignment_document["issue_id"]), IssueStatus.ASSIGNED)

    if issue_document and volunteer_document:
        background_tasks.add_task(
            get_notification_service().notify_recipient,
            str(volunteer_document["email"]),
            "Task assigned",
            f"You've been assigned to issue: {issue_document['title']}",
        )

    return AssignmentResponse(data=AssignmentRecord.from_mongo(updated_document))


@router.post("/assignments/{assignment_id}/start", response_model=AssignmentResponse, status_code=status.HTTP_200_OK)
async def start_assignment(
    assignment_id: str,
    actor: AuthenticatedActor = Depends(get_current_actor),
) -> AssignmentResponse:
    _ensure_volunteer_actor(actor)
    assignment_document = await _get_assignment_document(assignment_id)
    if assignment_document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    _ensure_assignment_belongs_to_actor(assignment_document, actor)
    _ensure_transition_allowed(assignment_document["status"], AssignmentStatus.IN_PROGRESS)
    conflict = await get_assignment_collection().find_one(
        {
            "issue_id": assignment_document["issue_id"],
            "status": {"$in": list(ACTIVE_ASSIGNMENT_STATUSES)},
            "assignment_id": {"$ne": assignment_document["assignment_id"]},
        }
    )
    if conflict is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Issue already has an assigned volunteer",
        )

    current_time = datetime.now(timezone.utc)
    updated_document = await get_assignment_collection().find_one_and_update(
        {
            "_id": assignment_document["_id"],
            "status": {"$in": [AssignmentStatus.APPLIED.value, AssignmentStatus.ASSIGNED.value]},
        },
        {
            "$set": {
                "status": AssignmentStatus.IN_PROGRESS.value,
                "started_at": current_time,
                "updated_at": current_time,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if updated_document is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot change from {assignment_document['status']} to {AssignmentStatus.IN_PROGRESS.value}",
        )

    await _set_issue_status(str(assignment_document["issue_id"]), IssueStatus.ASSIGNED)
    return AssignmentResponse(data=AssignmentRecord.from_mongo(updated_document))


@router.post("/assignments/{assignment_id}/submit", response_model=AssignmentResponse, status_code=status.HTTP_200_OK)
async def submit_assignment(
    assignment_id: str,
    payload: AssignmentSubmitRequest,
    background_tasks: BackgroundTasks,
    actor: AuthenticatedActor = Depends(get_current_actor),
) -> AssignmentResponse:
    _ensure_volunteer_actor(actor)
    assignment_document = await _get_assignment_document(assignment_id)
    if assignment_document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    _ensure_assignment_belongs_to_actor(assignment_document, actor)
    _ensure_transition_allowed(assignment_document["status"], AssignmentStatus.SUBMITTED)
    _validate_submission_images(payload.submission_data)

    current_time = datetime.now(timezone.utc)
    updated_document = await get_assignment_collection().find_one_and_update(
        {"_id": assignment_document["_id"], "status": AssignmentStatus.IN_PROGRESS.value},
        {
            "$set": {
                "status": AssignmentStatus.SUBMITTED.value,
                "submission_data": payload.submission_data.model_dump(),
                "submitted_at": current_time,
                "updated_at": current_time,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if updated_document is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot change from {assignment_document['status']} to {AssignmentStatus.SUBMITTED.value}",
        )

    issue_document = await _get_issue_document(assignment_document["issue_id"])
    volunteer_document = await _get_volunteer_document(assignment_document["volunteer_id"])
    if issue_document and volunteer_document:
        background_tasks.add_task(
            get_notification_service().notify_admin,
            "Task submitted for verification",
            (
                f"{volunteer_document['name']} submitted work for issue {issue_document['title']} "
                f"at {issue_document['location']}."
            ),
        )

    return AssignmentResponse(data=AssignmentRecord.from_mongo(updated_document))


@router.post("/assignments/{assignment_id}/verify", response_model=AssignmentResponse, status_code=status.HTTP_200_OK)
async def verify_assignment(
    assignment_id: str,
    payload: AssignmentAdminActionRequest,
    actor: AuthenticatedActor = Depends(get_current_actor),
) -> AssignmentResponse:
    _ensure_admin_actor(actor)
    _ensure_actor_matches_admin(actor, payload.admin_id)

    assignment_document = await _get_assignment_document(assignment_id)
    if assignment_document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    _ensure_transition_allowed(assignment_document["status"], AssignmentStatus.VERIFIED)
    await verify_assignment_submission_or_raise(assignment_document)

    current_time = datetime.now(timezone.utc)
    updated_document = await get_assignment_collection().find_one_and_update(
        {"_id": assignment_document["_id"], "status": AssignmentStatus.SUBMITTED.value},
        {
            "$set": {
                "status": AssignmentStatus.VERIFIED.value,
                "updated_at": current_time,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if updated_document is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot change from {assignment_document['status']} to {AssignmentStatus.VERIFIED.value}",
        )

    return AssignmentResponse(data=AssignmentRecord.from_mongo(updated_document))


@router.post("/assignments/{assignment_id}/complete", response_model=AssignmentResponse, status_code=status.HTTP_200_OK)
async def complete_assignment(
    assignment_id: str,
    payload: AssignmentAdminActionRequest,
    background_tasks: BackgroundTasks,
    actor: AuthenticatedActor = Depends(get_current_actor),
) -> AssignmentResponse:
    _ensure_admin_actor(actor)
    _ensure_actor_matches_admin(actor, payload.admin_id)

    assignment_document = await _get_assignment_document(assignment_id)
    if assignment_document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    _ensure_transition_allowed(assignment_document["status"], AssignmentStatus.COMPLETED)

    volunteer_document = await _get_volunteer_document(assignment_document["volunteer_id"])
    if volunteer_document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Volunteer not found")

    current_time = datetime.now(timezone.utc)
    updated_document = await get_assignment_collection().find_one_and_update(
        {"_id": assignment_document["_id"], "status": AssignmentStatus.VERIFIED.value},
        {
            "$set": {
                "status": AssignmentStatus.COMPLETED.value,
                "completed_at": current_time,
                "updated_at": current_time,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if updated_document is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot change from {assignment_document['status']} to {AssignmentStatus.COMPLETED.value}",
        )

    trust_score = await get_trust_calculator().recalculate_trust_score(str(assignment_document["volunteer_id"]))
    awarded_points = await get_gamification_service().award_completion_points(
        assignment_id=str(assignment_document["assignment_id"]),
        volunteer_id=str(assignment_document["volunteer_id"]),
    )
    await _set_issue_status(str(assignment_document["issue_id"]), IssueStatus.COMPLETED)

    issue_document = await _get_issue_document(assignment_document["issue_id"])
    if issue_document is not None:
        background_tasks.add_task(
            get_notification_service().notify_recipient,
            str(volunteer_document["email"]),
            "Task verified and completed",
            (
                f"Task verified and completed. You earned {awarded_points} points.\n"
                f"Current trust score: {trust_score:.2f}\n\n"
                f"Issue: {issue_document['title']}"
            ),
        )

    return AssignmentResponse(data=AssignmentRecord.from_mongo(updated_document))


@router.post("/assignments/{assignment_id}/reject", response_model=AssignmentResponse, status_code=status.HTTP_200_OK)
async def reject_assignment(
    assignment_id: str,
    payload: AssignmentRejectRequest,
    background_tasks: BackgroundTasks,
    actor: AuthenticatedActor = Depends(get_current_actor),
) -> AssignmentResponse:
    _ensure_admin_actor(actor)
    _ensure_actor_matches_admin(actor, payload.admin_id)

    assignment_document = await _get_assignment_document(assignment_id)
    if assignment_document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    current_time = datetime.now(timezone.utc)
    updated_document = await get_assignment_collection().find_one_and_update(
        {"_id": assignment_document["_id"]},
        {
            "$set": {
                "status": AssignmentStatus.REJECTED.value,
                "admin_notes": payload.admin_notes,
                "updated_at": current_time,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if updated_document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    await _recalculate_issue_status(str(assignment_document["issue_id"]))
    await _refresh_volunteer_reputation(str(assignment_document["volunteer_id"]))

    volunteer_document = await _get_volunteer_document(assignment_document["volunteer_id"])
    issue_document = await _get_issue_document(assignment_document["issue_id"])
    if volunteer_document is not None and issue_document is not None:
        background_tasks.add_task(
            get_notification_service().notify_recipient,
            str(volunteer_document["email"]),
            "Task rejected",
            f"Task rejected. Reason: {payload.admin_notes}\n\nIssue: {issue_document['title']}",
        )

    return AssignmentResponse(data=AssignmentRecord.from_mongo(updated_document))


def _ensure_volunteer_actor(actor: AuthenticatedActor) -> None:
    if actor.role.value != "volunteer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Volunteer only")


def _ensure_admin_actor(actor: AuthenticatedActor) -> None:
    if actor.role.value != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")


def _ensure_actor_matches_volunteer(actor: AuthenticatedActor, volunteer_id: str) -> None:
    if actor.actor_id != volunteer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Volunteer only")


def _ensure_actor_matches_admin(actor: AuthenticatedActor, admin_id: str) -> None:
    if actor.actor_id != admin_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")


def _ensure_assignment_belongs_to_actor(assignment_document: dict[str, Any], actor: AuthenticatedActor) -> None:
    if assignment_document["volunteer_id"] != actor.actor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Volunteer only")


def _ensure_transition_allowed(current_status: str, target_status: AssignmentStatus) -> None:
    allowed_transitions: dict[str, set[str]] = {
        AssignmentStatus.APPLIED.value: {AssignmentStatus.ASSIGNED.value, AssignmentStatus.IN_PROGRESS.value},
        AssignmentStatus.ASSIGNED.value: {AssignmentStatus.IN_PROGRESS.value},
        AssignmentStatus.IN_PROGRESS.value: {AssignmentStatus.SUBMITTED.value},
        AssignmentStatus.SUBMITTED.value: {AssignmentStatus.VERIFIED.value},
        AssignmentStatus.VERIFIED.value: {AssignmentStatus.COMPLETED.value},
        AssignmentStatus.COMPLETED.value: set(),
        AssignmentStatus.REJECTED.value: set(),
    }
    if target_status.value not in allowed_transitions.get(current_status, set()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot change from {current_status} to {target_status.value}",
        )


def _validate_submission_images(submission_data: SubmissionData) -> None:
    if not submission_data.after_images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="submission_data.after_images",
        )

    all_images = submission_data.all_images()
    if not all_images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="submission_data.after_images",
        )

    invalid_images = [image for image in all_images if not _is_upload_path(image)]
    if invalid_images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="submission_data.images must be uploaded to /uploads first",
        )


def _is_upload_path(path: str) -> bool:
    normalized = path.strip().replace("\\", "/")
    if not normalized:
        return False

    if normalized.startswith("http://") or normalized.startswith("https://"):
        return f"/{UPLOAD_DIRECTORY_NAME}/" in normalized or normalized.endswith(f"/{UPLOAD_DIRECTORY_NAME}")

    parts = [part for part in PurePath(normalized).parts if part not in {"/", "\\"}]
    normalized_parts = [part.strip("/\\").lower() for part in parts]
    return UPLOAD_DIRECTORY_NAME in normalized_parts or normalized.lower().startswith(f"/{UPLOAD_DIRECTORY_NAME}/") or normalized.lower().startswith(f"{UPLOAD_DIRECTORY_NAME}/")


async def _get_issue_document(issue_identifier: str) -> dict[str, Any] | None:
    collection = get_issue_collection()
    query_options: list[dict[str, Any]] = [{"issue_id": issue_identifier}]
    if ObjectId.is_valid(issue_identifier):
        query_options.append({"_id": ObjectId(issue_identifier)})
    return await collection.find_one({"$or": query_options})


async def _get_volunteer_document(volunteer_id: str) -> dict[str, Any] | None:
    return await get_volunteer_collection().find_one({"volunteer_id": volunteer_id})


async def _get_assignment_document(assignment_identifier: str) -> dict[str, Any] | None:
    collection = get_assignment_collection()
    query_options: list[dict[str, Any]] = [{"assignment_id": assignment_identifier}]
    if ObjectId.is_valid(assignment_identifier):
        query_options.append({"_id": ObjectId(assignment_identifier)})
    return await collection.find_one({"$or": query_options})


async def _set_issue_status(issue_id: str, status_value: IssueStatus) -> None:
    await get_issue_collection().update_one(
        {"issue_id": issue_id},
        {"$set": {"status": status_value.value, "updated_at": datetime.now(timezone.utc)}},
    )


async def _recalculate_issue_status(issue_id: str) -> None:
    active_assignment = await get_assignment_collection().find_one(
        {
            "issue_id": issue_id,
            "status": {"$in": list(ACTIVE_ASSIGNMENT_STATUSES)},
        }
    )
    new_status = IssueStatus.ASSIGNED if active_assignment else IssueStatus.OPEN
    await _set_issue_status(issue_id, new_status)


async def _refresh_volunteer_reputation(volunteer_id: str) -> float:
    trust_score = await get_trust_calculator().recalculate_trust_score(volunteer_id)
    await get_gamification_service().refresh_volunteer_progress(volunteer_id)
    return trust_score
