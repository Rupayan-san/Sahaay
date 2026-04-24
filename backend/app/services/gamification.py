from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from pymongo import DESCENDING, UpdateOne

from app.core.database import (
    get_assignment_collection,
    get_rating_collection,
    get_verification_collection,
    get_volunteer_collection,
)
from app.models.assignment import AssignmentStatus
from app.models.rating import (
    LeaderboardCategory,
    LeaderboardEntry,
    LeaderboardResponse,
    LeaderboardTimeframe,
)
from app.models.verification import VerificationVerdict

logger = logging.getLogger(__name__)

LEADERBOARD_CACHE_TTL = timedelta(minutes=5)
COMPLETE_TASK_POINTS = 10
FIVE_STAR_RATING_POINTS = 20
FOUR_STAR_RATING_POINTS = 10
ALL_IMAGES_PASS_POINTS = 15
STREAK_BONUS_POINTS = 50
FIRST_TASK_POINTS = 5

FIRST_STEPS_BADGE = "First Steps"
ROOKIE_BADGE = "Rookie"
RELIABLE_BADGE = "Reliable"
EXPERT_BADGE = "Expert"
PERFECT_RECORD_BADGE = "Perfect Record"
COMMUNITY_HERO_BADGE = "Community Hero"
BADGE_ORDER = [
    FIRST_STEPS_BADGE,
    ROOKIE_BADGE,
    RELIABLE_BADGE,
    EXPERT_BADGE,
    PERFECT_RECORD_BADGE,
    COMMUNITY_HERO_BADGE,
]


class GamificationService:
    """Award volunteer points, maintain badges, and serve cached leaderboards."""

    def __init__(self) -> None:
        self._leaderboard_cache: dict[tuple[str, str, int], tuple[datetime, LeaderboardResponse]] = {}

    async def initialize(self) -> None:
        collection = get_volunteer_collection()
        await collection.create_index([("points", DESCENDING), ("trust_score", DESCENDING), ("tasks_completed", DESCENDING)])
        await collection.create_index("rank")
        await self.refresh_ranks()

    async def award_completion_points(self, assignment_id: str, volunteer_id: str) -> int:
        volunteer_document = await self._get_volunteer_document(volunteer_id)
        awarded_points = COMPLETE_TASK_POINTS

        if await self._assignment_has_all_images_passing(assignment_id):
            awarded_points += ALL_IMAGES_PASS_POINTS

        if int(volunteer_document.get("tasks_completed", 0)) == 1:
            awarded_points += FIRST_TASK_POINTS

        success_streak = await self._get_success_streak(volunteer_id)
        if success_streak > 0 and success_streak % 5 == 0:
            awarded_points += STREAK_BONUS_POINTS

        await get_volunteer_collection().update_one(
            {"volunteer_id": volunteer_id},
            {"$inc": {"points": awarded_points}},
        )
        await self.refresh_volunteer_progress(
            volunteer_id,
            extra_badges={FIRST_STEPS_BADGE} if int(volunteer_document.get("tasks_completed", 0)) == 1 else None,
        )
        return awarded_points

    async def award_rating_points(self, assignment_id: str, volunteer_id: str, stars: int) -> int:
        _ = assignment_id
        if stars < 4:
            await self.refresh_volunteer_progress(volunteer_id)
            return 0

        awarded_points = FIVE_STAR_RATING_POINTS if stars == 5 else FOUR_STAR_RATING_POINTS
        await get_volunteer_collection().update_one(
            {"volunteer_id": volunteer_id},
            {"$inc": {"points": awarded_points}},
        )
        await self.refresh_volunteer_progress(volunteer_id)
        return awarded_points

    async def refresh_volunteer_progress(self, volunteer_id: str, *, extra_badges: set[str] | None = None) -> list[str]:
        volunteer_document = await self._get_volunteer_document(volunteer_id)
        updated_badges = self._build_badges(volunteer_document, extra_badges=extra_badges)
        await get_volunteer_collection().update_one(
            {"volunteer_id": volunteer_id},
            {"$set": {"badges": updated_badges}},
        )
        await self.refresh_ranks()
        return updated_badges

    async def refresh_ranks(self) -> None:
        collection = get_volunteer_collection()
        volunteers = await collection.find(
            {},
            projection={"_id": 1, "points": 1, "trust_score": 1, "tasks_completed": 1, "name": 1},
        ).to_list(length=None)

        volunteers.sort(
            key=lambda document: (
                -int(document.get("points", 0)),
                -float(document.get("trust_score", 0.0)),
                -int(document.get("tasks_completed", 0)),
                str(document.get("name", "")).casefold(),
            )
        )

        if volunteers:
            operations = [
                UpdateOne({"_id": document["_id"]}, {"$set": {"rank": rank}})
                for rank, document in enumerate(volunteers, start=1)
            ]
            await collection.bulk_write(operations, ordered=False)

        self.invalidate_cache()

    async def get_leaderboard(
        self,
        *,
        category: LeaderboardCategory,
        timeframe: LeaderboardTimeframe,
        limit: int,
    ) -> LeaderboardResponse:
        cache_key = (category.value, timeframe.value, limit)
        now = datetime.now(timezone.utc)
        cached_entry = self._leaderboard_cache.get(cache_key)
        if cached_entry is not None and now - cached_entry[0] < LEADERBOARD_CACHE_TTL:
            return cached_entry[1]

        volunteers = await self._get_leaderboard_candidates(timeframe)
        volunteers.sort(key=self._leaderboard_sort_key(category))
        entries = [
            LeaderboardEntry(
                rank=rank,
                volunteer_id=str(document["volunteer_id"]),
                name=str(document["name"]),
                points=int(document.get("points", 0)),
                trust_score=round(float(document.get("trust_score", 0.0)), 2),
                tasks_completed=int(document.get("tasks_completed", 0)),
                badges=[str(badge) for badge in document.get("badges", [])],
            )
            for rank, document in enumerate(volunteers[:limit], start=1)
        ]

        response = LeaderboardResponse(leaderboard=entries)
        self._leaderboard_cache[cache_key] = (now, response)
        return response

    def invalidate_cache(self) -> None:
        self._leaderboard_cache.clear()

    async def _get_leaderboard_candidates(self, timeframe: LeaderboardTimeframe) -> list[dict[str, Any]]:
        collection = get_volunteer_collection()
        projection = {
            "volunteer_id": 1,
            "name": 1,
            "points": 1,
            "trust_score": 1,
            "tasks_completed": 1,
            "badges": 1,
            "rank": 1,
        }
        if timeframe == LeaderboardTimeframe.ALL_TIME:
            return await collection.find({}, projection=projection).to_list(length=None)

        cutoff = self._cutoff_for_timeframe(timeframe)
        active_volunteer_ids = await self._get_recently_active_volunteer_ids(cutoff)
        if not active_volunteer_ids:
            return []
        return await collection.find(
            {"volunteer_id": {"$in": sorted(active_volunteer_ids)}},
            projection=projection,
        ).to_list(length=None)

    async def _get_recently_active_volunteer_ids(self, cutoff: datetime) -> set[str]:
        assignment_ids = await get_assignment_collection().find(
            {
                "updated_at": {"$gte": cutoff},
                "status": {"$in": [AssignmentStatus.COMPLETED.value, AssignmentStatus.REJECTED.value]},
            },
            projection={"volunteer_id": 1},
        ).to_list(length=None)
        rating_ids = await get_rating_collection().find(
            {"created_at": {"$gte": cutoff}},
            projection={"volunteer_id": 1},
        ).to_list(length=None)

        volunteer_ids = {
            str(document["volunteer_id"])
            for document in assignment_ids + rating_ids
            if str(document.get("volunteer_id", "")).strip()
        }
        return volunteer_ids

    async def _assignment_has_all_images_passing(self, assignment_id: str) -> bool:
        verifications = await get_verification_collection().find(
            {"assignment_id": assignment_id},
            projection={"overall_verdict": 1},
        ).to_list(length=None)
        if not verifications:
            return False
        return all(document.get("overall_verdict") == VerificationVerdict.PASS.value for document in verifications)

    async def _get_success_streak(self, volunteer_id: str) -> int:
        assignments = await get_assignment_collection().find(
            {
                "volunteer_id": volunteer_id,
                "status": {"$in": [AssignmentStatus.COMPLETED.value, AssignmentStatus.REJECTED.value]},
            },
            projection={"status": 1, "updated_at": 1},
        ).sort("updated_at", DESCENDING).to_list(length=None)

        streak = 0
        for assignment in assignments:
            if assignment.get("status") != AssignmentStatus.COMPLETED.value:
                break
            streak += 1
        return streak

    async def _get_volunteer_document(self, volunteer_id: str) -> dict[str, Any]:
        volunteer_document = await get_volunteer_collection().find_one({"volunteer_id": volunteer_id})
        if volunteer_document is None:
            raise LookupError("Volunteer not found")
        return volunteer_document

    def _build_badges(self, volunteer_document: dict[str, Any], *, extra_badges: set[str] | None = None) -> list[str]:
        tasks_completed = int(volunteer_document.get("tasks_completed", 0))
        trust_score = float(volunteer_document.get("trust_score", 0.0))
        average_rating = float(volunteer_document.get("average_rating", 0.0))
        failed_verifications = int(volunteer_document.get("failed_verifications", 0))

        preserved_badges = {
            str(badge).strip()
            for badge in volunteer_document.get("badges", [])
            if str(badge).strip() and str(badge).strip() not in BADGE_ORDER
        }
        badges = set(extra_badges or set())

        if tasks_completed >= 1:
            badges.add(ROOKIE_BADGE)
            badges.add(FIRST_STEPS_BADGE)
        if tasks_completed >= 10 and trust_score > 70:
            badges.add(RELIABLE_BADGE)
        if tasks_completed >= 50 and average_rating > 4.5:
            badges.add(EXPERT_BADGE)
        if tasks_completed >= 20 and failed_verifications == 0:
            badges.add(PERFECT_RECORD_BADGE)
        if tasks_completed >= 100:
            badges.add(COMMUNITY_HERO_BADGE)

        ordered_badges = [badge for badge in BADGE_ORDER if badge in badges]
        ordered_badges.extend(sorted(preserved_badges))
        return ordered_badges

    def _leaderboard_sort_key(self, category: LeaderboardCategory):
        if category == LeaderboardCategory.TRUST_SCORE:
            return lambda document: (
                -float(document.get("trust_score", 0.0)),
                -int(document.get("points", 0)),
                -int(document.get("tasks_completed", 0)),
                str(document.get("name", "")).casefold(),
            )
        return lambda document: (
            -int(document.get("points", 0)),
            -float(document.get("trust_score", 0.0)),
            -int(document.get("tasks_completed", 0)),
            str(document.get("name", "")).casefold(),
        )

    def _cutoff_for_timeframe(self, timeframe: LeaderboardTimeframe) -> datetime:
        now = datetime.now(timezone.utc)
        if timeframe == LeaderboardTimeframe.WEEK:
            return now - timedelta(days=7)
        if timeframe == LeaderboardTimeframe.MONTH:
            return now - timedelta(days=30)
        return datetime.min.replace(tzinfo=timezone.utc)


@lru_cache(maxsize=1)
def get_gamification_service() -> GamificationService:
    return GamificationService()
