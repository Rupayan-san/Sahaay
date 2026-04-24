from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CategoryCount(BaseModel):
    category: str
    count: int = Field(..., ge=0)


class VolunteerActivity(BaseModel):
    volunteer_id: str
    name: str
    tasks_completed: int = Field(..., ge=0)


class WeeklyImpactStats(BaseModel):
    total_issues_reported: int = Field(..., ge=0)
    issues_resolved: int = Field(..., ge=0)
    average_resolution_time_hours: float = Field(..., ge=0.0)
    top_categories: list[CategoryCount]
    most_active_volunteers: list[VolunteerActivity]
    trust_score_distribution: dict[str, int]


class WeeklyImpactReportResponse(BaseModel):
    date_range: str
    report_markdown: str
    stats: WeeklyImpactStats


class TrendChartData(BaseModel):
    dates: list[str]
    counts: list[int]


class IssueTrendResponse(BaseModel):
    trend: str
    percentage_change: float
    summary: str
    chart_data: TrendChartData


class VolunteerPerformanceStats(BaseModel):
    tasks_completed: int = Field(..., ge=0)
    average_rating: float = Field(..., ge=0.0, le=5.0)
    trust_score: float = Field(..., ge=0.0, le=100.0)
    response_time_avg: float = Field(..., ge=0.0)
    top_categories: list[str]


class VolunteerRecentTask(BaseModel):
    assignment_id: str
    issue_id: str
    issue_title: str
    category: str
    status: str
    completed_at: datetime | None = None


class VolunteerPerformanceReportResponse(BaseModel):
    volunteer_name: str
    summary: str
    stats: VolunteerPerformanceStats
    recent_tasks: list[VolunteerRecentTask]
    badges: list[str]


class DashboardStatsResponse(BaseModel):
    active_issues: int = Field(..., ge=0)
    pending_assignments: int = Field(..., ge=0)
    volunteers_active: int = Field(..., ge=0)
    avg_trust_score: float = Field(..., ge=0.0, le=100.0)
    issues_resolved_today: int = Field(..., ge=0)
    high_priority_open: int = Field(..., ge=0)
