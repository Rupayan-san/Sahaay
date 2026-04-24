from __future__ import annotations

import html
import json
import logging
import re
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from typing import Any, Awaitable, Callable, TypeVar

import google.generativeai as genai
from pymongo.errors import ExecutionTimeout

from app.core.config import get_settings
from app.core.database import (
    get_assignment_collection,
    get_issue_collection,
    get_rating_collection,
    get_volunteer_collection,
)
from app.models.assignment import AssignmentStatus, SubmissionData
from app.models.issue import IssueCategory, IssueStatus
from app.models.report import (
    CategoryCount,
    DashboardStatsResponse,
    IssueTrendResponse,
    TrendChartData,
    VolunteerActivity,
    VolunteerPerformanceReportResponse,
    VolunteerPerformanceStats,
    VolunteerRecentTask,
    WeeklyImpactReportResponse,
    WeeklyImpactStats,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")
AGGREGATION_TIMEOUT_MS = 3_000
WEEKLY_IMPACT_PROMPT = """Generate a professional weekly impact report for a community organization.

Data:
- Issues reported: {total_issues}
- Issues resolved: {resolved_issues}
- Average resolution time: {avg_time} hours
- Top categories: {top_categories}
- Most active volunteers: {top_volunteers}
- Trust score distribution: {score_distribution}

Format as a 3-paragraph executive summary followed by bullet-point highlights.
Use professional tone, focus on impact and actionable insights.
"""

TREND_ANALYSIS_PROMPT = """You are generating an issue trend analysis summary for a community coordination platform.

Structured data:
{trend_payload}

Write a concise 1-2 sentence summary that states whether the trend is increasing, decreasing, or stable,
mentions the percentage change, and highlights the main location concentration if available.
"""

VOLUNTEER_REPORT_PROMPT = """Generate a concise volunteer performance summary for a community coordination platform.

Structured data:
{volunteer_payload}

Write a factual 2-sentence summary that mentions completed tasks, average rating, trust score, and main specialization.
"""


class ReportGenerationService:
    """Generate analytics and natural-language reports from MongoDB data."""

    def __init__(self) -> None:
        settings = get_settings()
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)

        self._model = genai.GenerativeModel(
            model_name=settings.gemini_model_name,
            generation_config=genai.GenerationConfig(
                temperature=0.3,
                max_output_tokens=500,
            ),
        )
        self._analytics_cache: dict[str, T] = {}

    async def generate_weekly_impact_report(self, *, days: int = 7) -> WeeklyImpactReportResponse:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)
        cache_key = f"weekly:{start.date().isoformat()}:{now.date().isoformat()}"

        async def builder() -> WeeklyImpactReportResponse:
            stats = await self._build_weekly_stats(start=start, end=now)
            if stats.total_issues_reported == 0 and stats.issues_resolved == 0:
                report_markdown = "No activity in this period"
            else:
                report_markdown = await self._generate_weekly_summary(stats)

            date_range = f"{start.date().isoformat()} to {now.date().isoformat()}"
            return WeeklyImpactReportResponse(
                date_range=date_range,
                report_markdown=report_markdown,
                stats=stats,
            )

        return await self._with_cache_fallback(cache_key, builder)

    async def get_issue_trend_analysis(
        self,
        *,
        days: int,
        category: IssueCategory | None = None,
    ) -> IssueTrendResponse:
        normalized_days = max(1, days)
        category_key = category.value if category else "all"
        cache_key = f"trend:{normalized_days}:{category_key}"

        async def builder() -> IssueTrendResponse:
            now = datetime.now(timezone.utc)
            start = now - timedelta(days=normalized_days - 1)
            previous_start = start - timedelta(days=normalized_days)

            daily_counts = await self._aggregate_issue_counts_by_day(start=start, end=now, category=category)
            current_total = sum(daily_counts.values())
            previous_total = await self._count_issues(
                start=previous_start,
                end=start - timedelta(microseconds=1),
                category=category,
            )

            percentage_change = self._calculate_percentage_change(current_total=current_total, previous_total=previous_total)
            if percentage_change > 5:
                trend = "increasing"
            elif percentage_change < -5:
                trend = "decreasing"
            else:
                trend = "stable"

            chart_data = self._build_chart_data(start_date=start.date(), end_date=now.date(), daily_counts=daily_counts)
            top_location = await self._get_top_issue_location(start=start, end=now, category=category)
            summary = await self._generate_trend_summary(
                trend=trend,
                percentage_change=percentage_change,
                days=normalized_days,
                category=category_key,
                top_location=top_location,
            )

            if current_total == 0 and previous_total == 0:
                summary = "No activity in this period"

            return IssueTrendResponse(
                trend=trend,
                percentage_change=round(percentage_change, 1),
                summary=summary,
                chart_data=chart_data,
            )

        return await self._with_cache_fallback(cache_key, builder)

    async def get_volunteer_performance_report(self, volunteer_id: str) -> VolunteerPerformanceReportResponse:
        cache_key = f"volunteer-report:{volunteer_id}"

        async def builder() -> VolunteerPerformanceReportResponse:
            volunteer_document = await get_volunteer_collection().find_one({"volunteer_id": volunteer_id})
            if volunteer_document is None:
                raise LookupError("Volunteer not found")

            assignments = await get_assignment_collection().find(
                {"volunteer_id": volunteer_id},
                projection={
                    "assignment_id": 1,
                    "issue_id": 1,
                    "status": 1,
                    "applied_at": 1,
                    "assigned_at": 1,
                    "started_at": 1,
                    "completed_at": 1,
                    "submission_data": 1,
                },
            ).to_list(length=None)

            issue_ids = [str(assignment.get("issue_id", "")).strip() for assignment in assignments if assignment.get("issue_id")]
            issues = await get_issue_collection().find(
                {"issue_id": {"$in": sorted(set(issue_ids))}},
                projection={"issue_id": 1, "title": 1, "category": 1},
            ).to_list(length=None)
            issue_map = {str(issue["issue_id"]): issue for issue in issues}

            completed_assignments = [assignment for assignment in assignments if assignment.get("status") == AssignmentStatus.COMPLETED.value]
            response_time_avg = self._calculate_average_response_time(assignments)
            top_categories = self._get_top_categories_for_assignments(completed_assignments, issue_map)
            recent_tasks = self._build_recent_tasks(completed_assignments, issue_map)

            stats = VolunteerPerformanceStats(
                tasks_completed=int(volunteer_document.get("tasks_completed", 0)),
                average_rating=round(float(volunteer_document.get("average_rating", 0.0)), 2),
                trust_score=round(float(volunteer_document.get("trust_score", 0.0)), 2),
                response_time_avg=round(response_time_avg, 2),
                top_categories=top_categories,
            )
            summary = await self._generate_volunteer_summary(
                volunteer_name=str(volunteer_document["name"]),
                stats=stats,
            )

            return VolunteerPerformanceReportResponse(
                volunteer_name=str(volunteer_document["name"]),
                summary=summary,
                stats=stats,
                recent_tasks=recent_tasks,
                badges=[str(badge) for badge in volunteer_document.get("badges", [])],
            )

        return await self._with_cache_fallback(cache_key, builder)

    async def get_dashboard_stats(self) -> DashboardStatsResponse:
        cache_key = "dashboard"

        async def builder() -> DashboardStatsResponse:
            today_start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)

            active_issues = await get_issue_collection().count_documents(
                {"status": {"$in": [IssueStatus.OPEN.value, IssueStatus.ASSIGNED.value]}}
            )
            pending_assignments = await get_assignment_collection().count_documents(
                {
                    "status": {
                        "$in": [
                            AssignmentStatus.APPLIED.value,
                            AssignmentStatus.ASSIGNED.value,
                            AssignmentStatus.IN_PROGRESS.value,
                            AssignmentStatus.SUBMITTED.value,
                            AssignmentStatus.VERIFIED.value,
                        ]
                    }
                }
            )
            volunteers_active = await get_volunteer_collection().count_documents({"is_active": True})
            avg_trust_pipeline = [
                {"$match": {"is_active": True}},
                {"$group": {"_id": None, "value": {"$avg": "$trust_score"}}},
            ]
            avg_trust_documents = await get_volunteer_collection().aggregate(
                avg_trust_pipeline,
                maxTimeMS=AGGREGATION_TIMEOUT_MS,
            ).to_list(length=1)
            avg_trust_score = round(float(avg_trust_documents[0]["value"]), 2) if avg_trust_documents else 0.0

            issues_resolved_today = await get_issue_collection().count_documents(
                {
                    "status": IssueStatus.COMPLETED.value,
                    "updated_at": {"$gte": today_start},
                }
            )
            high_priority_open = await get_issue_collection().count_documents(
                {
                    "status": IssueStatus.OPEN.value,
                    "priority_score": {"$gt": 70},
                }
            )

            return DashboardStatsResponse(
                active_issues=active_issues,
                pending_assignments=pending_assignments,
                volunteers_active=volunteers_active,
                avg_trust_score=avg_trust_score,
                issues_resolved_today=issues_resolved_today,
                high_priority_open=high_priority_open,
            )

        return await self._with_cache_fallback(cache_key, builder)

    def render_markdown_as_html(self, markdown_text: str) -> str:
        lines = markdown_text.strip().splitlines()
        html_parts: list[str] = ["<html><body>"]
        in_list = False

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                if in_list:
                    html_parts.append("</ul>")
                    in_list = False
                continue

            if line.startswith("- "):
                if not in_list:
                    html_parts.append("<ul>")
                    in_list = True
                html_parts.append(f"<li>{self._inline_markdown_to_html(line[2:])}</li>")
                continue

            if in_list:
                html_parts.append("</ul>")
                in_list = False

            html_parts.append(f"<p>{self._inline_markdown_to_html(line)}</p>")

        if in_list:
            html_parts.append("</ul>")

        html_parts.append("</body></html>")
        return "".join(html_parts)

    async def _build_weekly_stats(self, *, start: datetime, end: datetime) -> WeeklyImpactStats:
        total_issues = await self._count_issues(start=start, end=end, category=None)
        resolved_issues = await get_issue_collection().count_documents(
            {
                "status": IssueStatus.COMPLETED.value,
                "updated_at": {"$gte": start, "$lte": end},
            }
        )

        resolution_pipeline = [
            {"$match": {"status": IssueStatus.COMPLETED.value, "updated_at": {"$gte": start, "$lte": end}}},
            {
                "$project": {
                    "resolution_hours": {
                        "$divide": [{"$subtract": ["$updated_at", "$created_at"]}, 1000 * 60 * 60]
                    }
                }
            },
            {"$group": {"_id": None, "avg_resolution_hours": {"$avg": "$resolution_hours"}}},
        ]
        resolution_documents = await get_issue_collection().aggregate(
            resolution_pipeline,
            maxTimeMS=AGGREGATION_TIMEOUT_MS,
        ).to_list(length=1)
        avg_resolution_hours = round(
            float(resolution_documents[0]["avg_resolution_hours"]),
            2,
        ) if resolution_documents else 0.0

        category_pipeline = [
            {"$match": {"created_at": {"$gte": start, "$lte": end}}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 3},
        ]
        category_documents = await get_issue_collection().aggregate(
            category_pipeline,
            maxTimeMS=AGGREGATION_TIMEOUT_MS,
        ).to_list(length=3)
        top_categories = [
            CategoryCount(category=str(document["_id"]), count=int(document["count"]))
            for document in category_documents
            if str(document.get("_id", "")).strip()
        ]

        volunteer_pipeline = [
            {"$match": {"status": AssignmentStatus.COMPLETED.value, "completed_at": {"$gte": start, "$lte": end}}},
            {"$group": {"_id": "$volunteer_id", "tasks_completed": {"$sum": 1}}},
            {"$sort": {"tasks_completed": -1}},
            {"$limit": 5},
        ]
        volunteer_documents = await get_assignment_collection().aggregate(
            volunteer_pipeline,
            maxTimeMS=AGGREGATION_TIMEOUT_MS,
        ).to_list(length=5)
        volunteer_ids = [str(document["_id"]) for document in volunteer_documents if str(document.get("_id", "")).strip()]
        volunteers = await get_volunteer_collection().find(
            {"volunteer_id": {"$in": volunteer_ids}},
            projection={"volunteer_id": 1, "name": 1},
        ).to_list(length=None)
        volunteer_map = {str(document["volunteer_id"]): str(document["name"]) for document in volunteers}
        most_active_volunteers = [
            VolunteerActivity(
                volunteer_id=str(document["_id"]),
                name=volunteer_map.get(str(document["_id"]), "Unknown volunteer"),
                tasks_completed=int(document["tasks_completed"]),
            )
            for document in volunteer_documents
        ]

        trust_score_distribution = await self._build_trust_score_distribution()
        return WeeklyImpactStats(
            total_issues_reported=total_issues,
            issues_resolved=resolved_issues,
            average_resolution_time_hours=avg_resolution_hours,
            top_categories=top_categories,
            most_active_volunteers=most_active_volunteers,
            trust_score_distribution=trust_score_distribution,
        )

    async def _build_trust_score_distribution(self) -> dict[str, int]:
        volunteers = await get_volunteer_collection().find(
            {},
            projection={"trust_score": 1},
        ).to_list(length=None)
        distribution = {
            "0-49": 0,
            "50-69": 0,
            "70-84": 0,
            "85-100": 0,
        }
        for volunteer in volunteers:
            score = float(volunteer.get("trust_score", 0.0))
            if score < 50:
                distribution["0-49"] += 1
            elif score < 70:
                distribution["50-69"] += 1
            elif score < 85:
                distribution["70-84"] += 1
            else:
                distribution["85-100"] += 1
        return distribution

    async def _count_issues(
        self,
        *,
        start: datetime,
        end: datetime,
        category: IssueCategory | None,
    ) -> int:
        query: dict[str, Any] = {"created_at": {"$gte": start, "$lte": end}}
        if category is not None:
            query["category"] = category.value
        return await get_issue_collection().count_documents(query)

    async def _aggregate_issue_counts_by_day(
        self,
        *,
        start: datetime,
        end: datetime,
        category: IssueCategory | None,
    ) -> dict[str, int]:
        match_query: dict[str, Any] = {"created_at": {"$gte": start, "$lte": end}}
        if category is not None:
            match_query["category"] = category.value

        pipeline = [
            {"$match": match_query},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$created_at",
                            "timezone": "UTC",
                        }
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id": 1}},
        ]
        documents = await get_issue_collection().aggregate(
            pipeline,
            maxTimeMS=AGGREGATION_TIMEOUT_MS,
        ).to_list(length=None)
        return {str(document["_id"]): int(document["count"]) for document in documents}

    async def _get_top_issue_location(
        self,
        *,
        start: datetime,
        end: datetime,
        category: IssueCategory | None,
    ) -> str | None:
        match_query: dict[str, Any] = {"created_at": {"$gte": start, "$lte": end}}
        if category is not None:
            match_query["category"] = category.value

        pipeline = [
            {"$match": match_query},
            {"$group": {"_id": "$location", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 1},
        ]
        documents = await get_issue_collection().aggregate(
            pipeline,
            maxTimeMS=AGGREGATION_TIMEOUT_MS,
        ).to_list(length=1)
        if not documents:
            return None
        return str(documents[0].get("_id") or "").strip() or None

    async def _generate_weekly_summary(self, stats: WeeklyImpactStats) -> str:
        prompt = WEEKLY_IMPACT_PROMPT.format(
            total_issues=stats.total_issues_reported,
            resolved_issues=stats.issues_resolved,
            avg_time=stats.average_resolution_time_hours,
            top_categories=json.dumps([item.model_dump() for item in stats.top_categories]),
            top_volunteers=json.dumps([item.model_dump() for item in stats.most_active_volunteers]),
            score_distribution=json.dumps(stats.trust_score_distribution),
        )
        return await self._generate_text(
            prompt=prompt,
            fallback=self._build_weekly_fallback(stats),
        )

    async def _generate_trend_summary(
        self,
        *,
        trend: str,
        percentage_change: float,
        days: int,
        category: str,
        top_location: str | None,
    ) -> str:
        trend_payload = {
            "trend": trend,
            "percentage_change": round(percentage_change, 1),
            "days": days,
            "category": category,
            "top_location": top_location,
        }
        fallback = self._build_trend_fallback(
            trend=trend,
            percentage_change=percentage_change,
            category=category,
            top_location=top_location,
        )
        return await self._generate_text(
            prompt=TREND_ANALYSIS_PROMPT.format(trend_payload=json.dumps(trend_payload)),
            fallback=fallback,
        )

    async def _generate_volunteer_summary(
        self,
        *,
        volunteer_name: str,
        stats: VolunteerPerformanceStats,
    ) -> str:
        volunteer_payload = {
            "volunteer_name": volunteer_name,
            "tasks_completed": stats.tasks_completed,
            "average_rating": stats.average_rating,
            "trust_score": stats.trust_score,
            "response_time_avg": stats.response_time_avg,
            "top_categories": stats.top_categories,
        }
        fallback = self._build_volunteer_fallback(volunteer_name=volunteer_name, stats=stats)
        return await self._generate_text(
            prompt=VOLUNTEER_REPORT_PROMPT.format(volunteer_payload=json.dumps(volunteer_payload)),
            fallback=fallback,
        )

    async def _generate_text(self, *, prompt: str, fallback: str) -> str:
        settings = get_settings()
        if not settings.gemini_api_key:
            return fallback

        try:
            response = await self._model.generate_content_async(prompt)
        except Exception:  # noqa: BLE001
            logger.exception("Gemini report generation failed")
            return fallback

        response_text = (getattr(response, "text", "") or "").strip()
        return response_text or fallback

    def _build_weekly_fallback(self, stats: WeeklyImpactStats) -> str:
        top_categories = ", ".join(f"{item.category} ({item.count})" for item in stats.top_categories) or "none"
        top_volunteers = ", ".join(
            f"{item.name} ({item.tasks_completed} completed)"
            for item in stats.most_active_volunteers
        ) or "none"
        strong_trust = sum(
            count for label, count in stats.trust_score_distribution.items() if label in {"70-84", "85-100"}
        )
        total_tracked = sum(stats.trust_score_distribution.values()) or 1
        trust_share = round((strong_trust / total_tracked) * 100, 1)

        return (
            f"This week, the platform recorded {stats.total_issues_reported} new issue reports and resolved "
            f"{stats.issues_resolved} issues. The average resolution time across completed issues was "
            f"{stats.average_resolution_time_hours:.1f} hours.\n\n"
            f"The most common issue categories were {top_categories}. Volunteer participation remained strongest among "
            f"{top_volunteers}, helping sustain response capacity across the reporting period.\n\n"
            f"Trust signals remain healthy, with {trust_share}% of tracked volunteers scoring 70 or above. "
            "Focus attention on unresolved high-priority categories and emerging workload concentrations.\n\n"
            f"- Issues reported: {stats.total_issues_reported}\n"
            f"- Issues resolved: {stats.issues_resolved}\n"
            f"- Average resolution time: {stats.average_resolution_time_hours:.1f} hours\n"
            f"- Top categories: {top_categories}\n"
            f"- Most active volunteers: {top_volunteers}"
        )

    def _build_trend_fallback(
        self,
        *,
        trend: str,
        percentage_change: float,
        category: str,
        top_location: str | None,
    ) -> str:
        label = category if category != "all" else "all"
        location_fragment = f", concentrated in {top_location}" if top_location else ""
        direction = "increased" if percentage_change >= 0 else "decreased"
        return (
            f"{label.capitalize()} issues {direction} {abs(round(percentage_change, 1))}% over the selected period, "
            f"indicating a {trend} trend{location_fragment}."
        )

    def _build_volunteer_fallback(self, *, volunteer_name: str, stats: VolunteerPerformanceStats) -> str:
        specialties = ", ".join(stats.top_categories) or "general response work"
        return (
            f"{volunteer_name} completed {stats.tasks_completed} tasks with an average rating of "
            f"{stats.average_rating:.1f}/5 and a trust score of {stats.trust_score:.1f}. "
            f"Primary focus areas include {specialties}."
        )

    def _build_chart_data(
        self,
        *,
        start_date: date,
        end_date: date,
        daily_counts: dict[str, int],
    ) -> TrendChartData:
        dates: list[str] = []
        counts: list[int] = []
        current_date = start_date
        while current_date <= end_date:
            key = current_date.isoformat()
            dates.append(key)
            counts.append(int(daily_counts.get(key, 0)))
            current_date += timedelta(days=1)
        return TrendChartData(dates=dates, counts=counts)

    def _calculate_percentage_change(self, *, current_total: int, previous_total: int) -> float:
        if previous_total <= 0:
            return 100.0 if current_total > 0 else 0.0
        return ((current_total - previous_total) / previous_total) * 100.0

    def _calculate_average_response_time(self, assignments: list[dict[str, Any]]) -> float:
        response_times: list[float] = []
        for assignment in assignments:
            started_at = assignment.get("started_at")
            if started_at is None:
                continue

            baseline = assignment.get("assigned_at") or assignment.get("applied_at")
            if baseline is None:
                continue

            delta = started_at - baseline
            response_times.append(delta.total_seconds() / 3600.0)

        if not response_times:
            return 0.0
        return sum(response_times) / len(response_times)

    def _get_top_categories_for_assignments(
        self,
        assignments: list[dict[str, Any]],
        issue_map: dict[str, dict[str, Any]],
    ) -> list[str]:
        category_counts: dict[str, int] = {}
        for assignment in assignments:
            issue = issue_map.get(str(assignment.get("issue_id", "")))
            category = str(issue.get("category", "") if issue else "").strip()
            if not category:
                continue
            category_counts[category] = category_counts.get(category, 0) + 1

        ranked_categories = sorted(category_counts.items(), key=lambda item: (-item[1], item[0]))
        return [category for category, _ in ranked_categories[:3]]

    def _build_recent_tasks(
        self,
        assignments: list[dict[str, Any]],
        issue_map: dict[str, dict[str, Any]],
    ) -> list[VolunteerRecentTask]:
        sorted_assignments = sorted(
            assignments,
            key=lambda assignment: assignment.get("completed_at") or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        tasks: list[VolunteerRecentTask] = []
        for assignment in sorted_assignments[:5]:
            issue = issue_map.get(str(assignment.get("issue_id", ""))) or {}
            tasks.append(
                VolunteerRecentTask(
                    assignment_id=str(assignment.get("assignment_id", "")),
                    issue_id=str(assignment.get("issue_id", "")),
                    issue_title=str(issue.get("title", "Unknown issue")),
                    category=str(issue.get("category", "other")),
                    status=str(assignment.get("status", "")),
                    completed_at=assignment.get("completed_at"),
                )
            )
        return tasks

    async def _with_cache_fallback(
        self,
        cache_key: str,
        builder: Callable[[], Awaitable[T]],
    ) -> T:
        try:
            result = await builder()
            self._analytics_cache[cache_key] = result
            return result
        except Exception as exc:  # noqa: BLE001
            if self._is_timeout_error(exc) and cache_key in self._analytics_cache:
                logger.warning("Returning cached report data for %s after timeout", cache_key, exc_info=exc)
                return self._analytics_cache[cache_key]
            raise

    def _is_timeout_error(self, exc: Exception) -> bool:
        if isinstance(exc, ExecutionTimeout):
            return True
        error_message = str(exc).casefold()
        return "time limit" in error_message or "timed out" in error_message

    def _inline_markdown_to_html(self, value: str) -> str:
        escaped = html.escape(value)
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


@lru_cache(maxsize=1)
def get_report_generator_service() -> ReportGenerationService:
    return ReportGenerationService()
