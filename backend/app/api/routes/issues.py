from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from app.models.issue import (
    IssueCategory,
    IssueCreateRequest,
    IssueListResponse,
    IssueStatus,
    IssueUpsertResponse,
)
from app.services.embedding_service import get_embedding_service
from app.services.gemini_client import get_gemini_service
from app.services.notification_service import get_notification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["issues"])


@router.post("/issues", response_model=IssueUpsertResponse, status_code=status.HTTP_200_OK)
async def create_issue(payload: IssueCreateRequest, background_tasks: BackgroundTasks) -> IssueUpsertResponse:
    gemini_service = get_gemini_service()
    embedding_service = get_embedding_service()

    try:
        extracted_issue = await gemini_service.extract_issue(payload.raw_text)
        aggregation_result = await embedding_service.upsert_issue(extracted_issue)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Issue creation configuration error")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected issue creation failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Issue extraction and aggregation failed",
        ) from exc

    if not aggregation_result.matched_existing and aggregation_result.issue.priority_score > 70:
        background_tasks.add_task(
            get_notification_service().notify_high_priority_issue,
            aggregation_result.issue.issue_id,
            notification_limit=5,
        )

    return IssueUpsertResponse(
        matched_existing=aggregation_result.matched_existing,
        similarity=aggregation_result.similarity,
        data=aggregation_result.issue,
    )


@router.get("/issues", response_model=IssueListResponse, status_code=status.HTTP_200_OK)
async def get_issues(
    limit: int = Query(default=50, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
    status_filter: IssueStatus | None = Query(default=None, alias="status"),
    category: IssueCategory | None = Query(default=None),
    location: str | None = Query(default=None, min_length=1),
) -> IssueListResponse:
    embedding_service = get_embedding_service()

    try:
        issues = await embedding_service.list_issues(
            limit=limit,
            skip=skip,
            status=status_filter,
            category=category.value if category else None,
            location=location.strip() if location else None,
        )
    except RuntimeError as exc:
        logger.exception("Issue listing configuration error")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected issue listing failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch issues",
        ) from exc

    return IssueListResponse(data=issues)
