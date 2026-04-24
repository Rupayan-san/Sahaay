from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from math import isfinite
from typing import Any

from pydantic import ValidationError
from pymongo.errors import PyMongoError

from app.core.database import (
    get_assignment_collection,
    get_mongo_client,
    get_rating_collection,
    get_verification_collection,
    get_volunteer_collection,
)
from app.models.assignment import AssignmentStatus, SubmissionData
from app.models.verification import VerificationVerdict

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TrustScoreSnapshot:
    volunteer_id: str
    trust_score: float
    average_rating: float
    tasks_completed: int
    tasks_failed: int
    total_images_submitted: int
    failed_verifications: int


class TrustCalculator:
    """Recalculate volunteer trust scores from assignments, ratings, and verification history."""

    def calculate(
        self,
        *,
        average_rating: float,
        tasks_completed: int,
        tasks_failed: int,
        total_images_submitted: int = 0,
        failed_verifications: int = 0,
    ) -> float:
        completed = max(0, int(tasks_completed))
        failed = max(0, int(tasks_failed))
        total_tasks = completed + failed
        if total_tasks == 0:
            return 50.0

        rating = float(average_rating)
        if not isfinite(rating):
            rating = 0.0
        rating = min(max(rating, 0.0), 5.0)

        images_submitted = max(0, int(total_images_submitted))
        verification_failures = min(max(0, int(failed_verifications)), images_submitted) if images_submitted else 0

        rating_component = (rating / 5.0) * 40.0
        completion_rate = completed / total_tasks if total_tasks else 0.0
        completion_component = completion_rate * 30.0

        if images_submitted == 0:
            verification_rate = 1.0
        else:
            verification_rate = max(0.0, (images_submitted - verification_failures) / images_submitted)
        verification_component = verification_rate * 30.0

        trust_score = rating_component + completion_component + verification_component
        return round(min(100.0, max(0.0, trust_score)), 2)

    async def recalculate_trust_score(self, volunteer_id: str, *, session: Any | None = None) -> float:
        if session is not None:
            snapshot = await self._recalculate(volunteer_id, session=session)
            return snapshot.trust_score

        client = get_mongo_client()
        try:
            async with await client.start_session() as managed_session:
                async with managed_session.start_transaction():
                    snapshot = await self._recalculate(volunteer_id, session=managed_session)
                return snapshot.trust_score
        except PyMongoError:
            logger.warning(
                "MongoDB transactions unavailable while recalculating trust for %s; falling back to non-transactional update",
                volunteer_id,
                exc_info=True,
            )
            snapshot = await self._recalculate(volunteer_id, session=None)
            return snapshot.trust_score

    async def get_snapshot(self, volunteer_id: str, *, session: Any | None = None) -> TrustScoreSnapshot:
        volunteer_document = await get_volunteer_collection().find_one({"volunteer_id": volunteer_id}, session=session)
        if volunteer_document is None:
            raise LookupError("Volunteer not found")

        assignments = await get_assignment_collection().find(
            {"volunteer_id": volunteer_id},
            projection={"assignment_id": 1, "status": 1, "submission_data": 1},
            session=session,
        ).to_list(length=None)

        ratings = await get_rating_collection().find(
            {"volunteer_id": volunteer_id},
            projection={"stars": 1},
            session=session,
        ).to_list(length=None)

        tasks_completed = sum(1 for assignment in assignments if assignment.get("status") == AssignmentStatus.COMPLETED.value)
        tasks_failed = sum(1 for assignment in assignments if assignment.get("status") == AssignmentStatus.REJECTED.value)

        total_images_submitted = 0
        assignment_ids: set[str] = set()
        for assignment in assignments:
            assignment_id = str(assignment.get("assignment_id", "")).strip()
            if assignment_id:
                assignment_ids.add(assignment_id)

            submission_payload = assignment.get("submission_data") or {}
            try:
                submission_data = SubmissionData.model_validate(submission_payload)
            except ValidationError:
                logger.warning("Skipping malformed submission_data while recalculating trust for %s", volunteer_id)
                submission_data = SubmissionData()
            total_images_submitted += len(submission_data.all_images())

        failed_verifications = 0
        if assignment_ids:
            failed_verifications = await get_verification_collection().count_documents(
                {
                    "assignment_id": {"$in": sorted(assignment_ids)},
                    "overall_verdict": VerificationVerdict.FAIL.value,
                },
                session=session,
            )

        average_rating = 0.0
        if ratings:
            average_rating = round(sum(float(rating.get("stars", 0)) for rating in ratings) / len(ratings), 2)

        trust_score = self.calculate(
            average_rating=average_rating,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            total_images_submitted=total_images_submitted,
            failed_verifications=failed_verifications,
        )

        return TrustScoreSnapshot(
            volunteer_id=volunteer_id,
            trust_score=trust_score,
            average_rating=average_rating,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            total_images_submitted=total_images_submitted,
            failed_verifications=failed_verifications,
        )

    async def _recalculate(self, volunteer_id: str, *, session: Any | None) -> TrustScoreSnapshot:
        snapshot = await self.get_snapshot(volunteer_id, session=session)
        update_result = await get_volunteer_collection().update_one(
            {"volunteer_id": volunteer_id},
            {
                "$set": {
                    "trust_score": snapshot.trust_score,
                    "average_rating": snapshot.average_rating,
                    "tasks_completed": snapshot.tasks_completed,
                    "tasks_failed": snapshot.tasks_failed,
                    "total_images_submitted": snapshot.total_images_submitted,
                    "failed_verifications": snapshot.failed_verifications,
                }
            },
            session=session,
        )
        if update_result.matched_count == 0:
            raise LookupError("Volunteer not found")

        return snapshot


@lru_cache(maxsize=1)
def get_trust_calculator() -> TrustCalculator:
    return TrustCalculator()


async def recalculate_trust_score(volunteer_id: str) -> float:
    return await get_trust_calculator().recalculate_trust_score(volunteer_id)
