from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from bson import ObjectId
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.core import database as db_module
from app.main import app
from app.models.issue import ExtractedIssue, IssueCategory, IssueRecord, IssueSeverity, IssueStatus
from app.models.rating import LeaderboardEntry, LeaderboardResponse
from app.models.verification import (
    AIGeneratedCheck,
    DuplicateCheck,
    ImageVerificationResponse,
    ImageVerificationSummary,
    ReverseSearchCheck,
    VerificationChecks,
    VerificationResult,
    VerificationVerdict,
)
from app.models.volunteer import VolunteerLocation, VolunteerMatch, VolunteerMatchBreakdown, VolunteerRecord


def build_issue_record() -> IssueRecord:
    now = datetime.now(timezone.utc)
    return IssueRecord(
        id="mongo-issue-id",
        issue_id="test-issue-id",
        title="Water pump broken",
        category=IssueCategory.WATER,
        location="Village A",
        severity=IssueSeverity.HIGH,
        description="Main water pump at Village A is broken",
        report_count=1,
        priority_score=75,
        created_at=now,
        updated_at=now,
        status=IssueStatus.OPEN,
    )


def build_extracted_issue() -> ExtractedIssue:
    return ExtractedIssue(
        title="Water pump broken",
        category=IssueCategory.WATER,
        location="Village A",
        severity=IssueSeverity.HIGH,
        description="Main water pump at Village A is broken",
    )


def build_volunteer_record() -> VolunteerRecord:
    now = datetime.now(timezone.utc)
    return VolunteerRecord(
        id="mongo-volunteer-id",
        volunteer_id="test-vol-id",
        name="Test Vol",
        email="john@test.com",
        skills="plumber pipe repair",
        location=VolunteerLocation(city="Kolkata", district="North", state="WB"),
        trust_score=72.5,
        tasks_completed=4,
        tasks_failed=0,
        total_images_submitted=6,
        failed_verifications=0,
        average_rating=4.5,
        points=40,
        badges=["Rookie"],
        rank=1,
        created_at=now,
        is_active=True,
    )


def build_verification_response() -> ImageVerificationResponse:
    result = VerificationResult(
        image_path="uploads/after-1.jpg",
        checks=VerificationChecks(
            reverse_search=ReverseSearchCheck(
                passed=True,
                confidence=0.95,
                found_urls=[],
                notes="No stock-photo matches found",
            ),
            ai_generated=AIGeneratedCheck(
                passed=True,
                confidence=0.92,
                indicators=[],
                notes="No AI indicators found",
            ),
            duplicate_check=DuplicateCheck(
                passed=True,
                confidence=0.9,
                similar_images=[],
                notes="No similar submitted images found",
            ),
        ),
        overall_verdict=VerificationVerdict.PASS,
        final_confidence=0.92,
    )
    return ImageVerificationResponse(
        results=[result],
        summary=ImageVerificationSummary(total_images=1, passed=1, failed=0, suspicious=0),
    )


def build_leaderboard_response() -> LeaderboardResponse:
    return LeaderboardResponse(
        leaderboard=[
            LeaderboardEntry(
                rank=1,
                volunteer_id="test-vol-id",
                name="Test Vol",
                points=40,
                trust_score=72.5,
                tasks_completed=4,
                badges=["Rookie"],
            )
        ]
    )


class MatchCandidateStub:
    def __init__(self) -> None:
        self._payload = VolunteerMatch(
            volunteer_id="test-vol-id",
            name="Test Vol",
            match_score=0.91,
            breakdown=VolunteerMatchBreakdown(
                skill_similarity=0.93,
                location_match=1.0,
                performance_boost=0.8,
            ),
            skills="plumber pipe repair",
            trust_score=72.5,
            tasks_completed=4,
        )

    def to_response_model(self) -> VolunteerMatch:
        return self._payload


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    original_client = db_module._client
    original_database = db_module._database
    mock_client = AsyncMongoMockClient()
    mock_database = mock_client["sahaay_test_db"]
    db_module._client = mock_client
    db_module._database = mock_database

    issue_record = build_issue_record()
    volunteer_record = build_volunteer_record()

    gemini_service = MagicMock()
    gemini_service.extract_issue = AsyncMock(return_value=build_extracted_issue())

    embedding_service = MagicMock()
    embedding_service.initialize = AsyncMock()
    embedding_service.upsert_issue = AsyncMock(
        return_value=SimpleNamespace(
            matched_existing=False,
            similarity=0.0,
            issue=issue_record,
        )
    )
    embedding_service.list_issues = AsyncMock(return_value=[issue_record])

    matching_engine = MagicMock()
    matching_engine.initialize = AsyncMock()
    matching_engine.register_volunteer = AsyncMock(return_value=volunteer_record)
    matching_engine.list_volunteers = AsyncMock(return_value=[volunteer_record])
    matching_engine.match_issue = AsyncMock(return_value=[MatchCandidateStub()])

    gamification_service = MagicMock()
    gamification_service.initialize = AsyncMock()
    gamification_service.refresh_ranks = AsyncMock()
    gamification_service.refresh_volunteer_progress = AsyncMock(return_value=["Rookie"])
    gamification_service.award_completion_points = AsyncMock(return_value=10)
    gamification_service.award_rating_points = AsyncMock(return_value=10)
    gamification_service.get_leaderboard = AsyncMock(return_value=build_leaderboard_response())

    image_verification_service = MagicMock()
    image_verification_service.initialize = AsyncMock()
    image_verification_service.verify_assignment_images = AsyncMock(return_value=build_verification_response())

    notification_service = MagicMock()
    notification_service.notify_high_priority_issue = AsyncMock()
    notification_service.notify_admin = AsyncMock()
    notification_service.notify_recipient = AsyncMock()

    trust_calculator = MagicMock()
    trust_calculator.recalculate_trust_score = AsyncMock(return_value=75.0)

    patches = [
        patch("app.main.connect_to_mongo", AsyncMock()),
        patch("app.main.close_mongo_connection", AsyncMock()),
        patch("app.main.get_embedding_service", return_value=embedding_service),
        patch("app.main.get_matching_engine", return_value=matching_engine),
        patch("app.main.get_gamification_service", return_value=gamification_service),
        patch("app.main.get_image_verification_service", return_value=image_verification_service),
        patch("app.main.start_scheduled_reports", AsyncMock()),
        patch("app.main.stop_scheduled_reports", AsyncMock()),
        patch("app.api.routes.issues.get_embedding_service", return_value=embedding_service),
        patch("app.api.routes.issues.get_gemini_service", return_value=gemini_service),
        patch("app.api.routes.issues.get_notification_service", return_value=notification_service),
        patch("app.api.routes.volunteers.get_matching_engine", return_value=matching_engine),
        patch("app.api.routes.assignments.get_notification_service", return_value=notification_service),
        patch("app.api.routes.assignments.get_trust_calculator", return_value=trust_calculator),
        patch("app.api.routes.assignments.get_gamification_service", return_value=gamification_service),
        patch("app.api.routes.verification.get_image_verification_service", return_value=image_verification_service),
        patch("app.api.routes.verification.get_trust_calculator", return_value=trust_calculator),
        patch("app.api.routes.verification.get_gamification_service", return_value=gamification_service),
        patch("app.api.routes.leaderboard.get_gamification_service", return_value=gamification_service),
        patch("app.api.routes.ratings.get_trust_calculator", return_value=trust_calculator),
        patch("app.api.routes.ratings.get_gamification_service", return_value=gamification_service),
    ]

    try:
        with ExitStack() as stack:
            for active_patch in patches:
                stack.enter_context(active_patch)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as async_client:
                async_client.service_mocks = {
                    "gemini": gemini_service,
                    "embedding": embedding_service,
                    "matching": matching_engine,
                    "gamification": gamification_service,
                    "image_verification": image_verification_service,
                    "notification": notification_service,
                    "trust": trust_calculator,
                }
                async_client.test_database = mock_database
                yield async_client
    finally:
        db_module._client = original_client
        db_module._database = original_database


@pytest.fixture
def service_mocks(client: AsyncClient) -> dict[str, MagicMock]:
    return client.service_mocks


@pytest.fixture
def test_database(client: AsyncClient):
    return client.test_database


@pytest_asyncio.fixture
async def seeded_issue(test_database):
    now = datetime.now(timezone.utc)
    document = {
        "_id": ObjectId(),
        "issue_id": "test-issue-id",
        "title": "Water pump broken",
        "category": "water",
        "location": "Village A",
        "severity": "high",
        "description": "Main water pump at Village A is broken",
        "report_count": 1,
        "priority_score": 75,
        "embedding": [0.0] * 768,
        "created_at": now,
        "updated_at": now,
        "status": "open",
    }
    await test_database.get_collection("issues").insert_one(document)
    return document


@pytest_asyncio.fixture
async def seeded_volunteer(test_database):
    now = datetime.now(timezone.utc)
    document = {
        "_id": ObjectId(),
        "volunteer_id": "vol-123",
        "name": "John",
        "email": "john@test.com",
        "skills": "plumber pipe repair",
        "location": {"city": "Kolkata", "district": "North", "state": "WB"},
        "trust_score": 70.0,
        "tasks_completed": 2,
        "tasks_failed": 0,
        "total_images_submitted": 0,
        "failed_verifications": 0,
        "average_rating": 4.5,
        "points": 10,
        "badges": [],
        "rank": 1,
        "skills_embedding": [0.0] * 768,
        "created_at": now,
        "is_active": True,
    }
    await test_database.get_collection("volunteers").insert_one(document)
    return document


@pytest_asyncio.fixture
async def seeded_assignment(test_database):
    now = datetime.now(timezone.utc)
    document = {
        "_id": ObjectId(),
        "assignment_id": "test-assignment-id",
        "issue_id": "test-issue-id",
        "volunteer_id": "vol-123",
        "status": "applied",
        "applied_at": now,
        "assigned_at": None,
        "started_at": None,
        "submitted_at": None,
        "completed_at": None,
        "submission_data": None,
        "admin_notes": None,
        "application_message": None,
        "created_at": now,
        "updated_at": now,
    }
    await test_database.get_collection("assignments").insert_one(document)
    return document
