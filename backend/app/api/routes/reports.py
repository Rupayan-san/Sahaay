from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.models.issue import IssueCategory
from app.models.report import (
    DashboardStatsResponse,
    IssueTrendResponse,
    VolunteerPerformanceReportResponse,
    WeeklyImpactReportResponse,
)
from app.services.report_generator import get_report_generator_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["reports"])


@router.get("/reports/weekly-impact", response_model=WeeklyImpactReportResponse, status_code=status.HTTP_200_OK)
async def get_weekly_impact_report(
    days: int = Query(default=7, ge=1, le=30),
) -> WeeklyImpactReportResponse:
    try:
        return await get_report_generator_service().generate_weekly_impact_report(days=days)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected weekly report failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate weekly report",
        ) from exc


@router.get("/reports/trends", response_model=IssueTrendResponse, status_code=status.HTTP_200_OK)
async def get_issue_trends(
    days: int = Query(default=30, ge=1, le=365),
    category: IssueCategory | None = Query(default=None),
) -> IssueTrendResponse:
    try:
        return await get_report_generator_service().get_issue_trend_analysis(days=days, category=category)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected trend analysis failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate trend analysis",
        ) from exc


@router.get("/volunteers/{volunteer_id}/report", response_model=VolunteerPerformanceReportResponse)
async def get_volunteer_report(volunteer_id: str) -> VolunteerPerformanceReportResponse:
    try:
        return await get_report_generator_service().get_volunteer_performance_report(volunteer_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected volunteer report failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate volunteer report",
        ) from exc


@router.get("/reports/dashboard", response_model=DashboardStatsResponse, status_code=status.HTTP_200_OK)
async def get_dashboard_stats() -> DashboardStatsResponse:
    try:
        return await get_report_generator_service().get_dashboard_stats()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected dashboard stats failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch dashboard stats",
        ) from exc
