from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import numpy as np
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from app.core.database import get_issue_collection, get_volunteer_collection
from app.models.issue import IssueRecord
from app.models.volunteer import (
    VolunteerCreateRequest,
    VolunteerMatch,
    VolunteerMatchBreakdown,
    VolunteerRecord,
)
from app.services.embedding_service import TARGET_EMBEDDING_DIMENSION, get_embedding_service
from app.services.gamification import get_gamification_service
from app.services.trust_calculator import TrustCalculator

logger = logging.getLogger(__name__)

MINIMUM_MATCH_SCORE = 0.3


@dataclass(slots=True)
class VolunteerMatchCandidate:
    volunteer_id: str
    name: str
    email: str
    match_score: float
    skill_similarity: float
    location_match: float
    performance_boost: float
    skills: str
    trust_score: float
    tasks_completed: int

    def to_response_model(self) -> VolunteerMatch:
        return VolunteerMatch(
            volunteer_id=self.volunteer_id,
            name=self.name,
            match_score=round(self.match_score, 4),
            breakdown=VolunteerMatchBreakdown(
                skill_similarity=round(self.skill_similarity, 4),
                location_match=round(self.location_match, 4),
                performance_boost=round(self.performance_boost, 4),
            ),
            skills=self.skills,
            trust_score=round(self.trust_score, 2),
            tasks_completed=self.tasks_completed,
        )


class VolunteerMatchingEngine:
    """Volunteer registration, retrieval, and issue matching."""

    def __init__(self) -> None:
        self._trust_calculator = TrustCalculator()

    async def initialize(self) -> None:
        collection = get_volunteer_collection()
        await collection.create_index("volunteer_id", unique=True)
        await collection.create_index("email", unique=True)
        await collection.create_index([("is_active", ASCENDING), ("trust_score", DESCENDING)])
        await collection.create_index(
            [("location.state", ASCENDING), ("location.district", ASCENDING), ("location.city", ASCENDING)]
        )

    async def register_volunteer(self, payload: VolunteerCreateRequest) -> VolunteerRecord:
        embedding_service = get_embedding_service()
        collection = get_volunteer_collection()
        current_time = datetime.now(timezone.utc)
        trust_score = self._trust_calculator.calculate(
            average_rating=payload.average_rating,
            tasks_completed=payload.tasks_completed,
            tasks_failed=payload.tasks_failed,
        )
        skills_embedding = await embedding_service.get_embedding(payload.skills)

        document = {
            "volunteer_id": str(uuid.uuid4()),
            "name": payload.name,
            "email": str(payload.email),
            "skills": payload.skills,
            "location": payload.location.model_dump(),
            "trust_score": trust_score,
            "tasks_completed": payload.tasks_completed,
            "tasks_failed": payload.tasks_failed,
            "total_images_submitted": 0,
            "failed_verifications": 0,
            "average_rating": payload.average_rating,
            "points": 0,
            "badges": [],
            "rank": 0,
            "skills_embedding": skills_embedding,
            "created_at": current_time,
            "is_active": payload.is_active,
        }

        try:
            insert_result = await collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise ValueError("A volunteer with this email already exists") from exc

        document["_id"] = insert_result.inserted_id
        await get_gamification_service().refresh_ranks()
        refreshed_document = await collection.find_one({"_id": insert_result.inserted_id})
        if refreshed_document is not None:
            document = refreshed_document
        return VolunteerRecord.from_mongo(document)

    async def list_volunteers(
        self,
        *,
        limit: int = 50,
        skip: int = 0,
        active_only: bool = False,
    ) -> list[VolunteerRecord]:
        collection = get_volunteer_collection()
        query: dict[str, Any] = {"is_active": True} if active_only else {}
        cursor = collection.find(query).sort([("trust_score", DESCENDING), ("tasks_completed", DESCENDING)])
        documents = await cursor.skip(skip).limit(limit).to_list(length=limit)
        return [VolunteerRecord.from_mongo(document) for document in documents]

    async def match_issue(
        self,
        issue_identifier: str,
        *,
        limit: int = 3,
        minimum_score: float = MINIMUM_MATCH_SCORE,
    ) -> list[VolunteerMatchCandidate]:
        issue_document = await self.get_issue_document(issue_identifier)
        if issue_document is None:
            raise LookupError("Issue not found")

        return await self.find_matches_for_issue_document(
            issue_document=issue_document,
            limit=limit,
            minimum_score=minimum_score,
        )

    async def get_issue_document(self, issue_identifier: str) -> dict[str, Any] | None:
        collection = get_issue_collection()
        query_options: list[dict[str, Any]] = [{"issue_id": issue_identifier}]
        if ObjectId.is_valid(issue_identifier):
            query_options.append({"_id": ObjectId(issue_identifier)})
        return await collection.find_one({"$or": query_options})

    async def get_issue_record(self, issue_identifier: str) -> IssueRecord:
        issue_document = await self.get_issue_document(issue_identifier)
        if issue_document is None:
            raise LookupError("Issue not found")
        return IssueRecord.from_mongo(issue_document)

    async def find_matches_for_issue_document(
        self,
        *,
        issue_document: dict[str, Any],
        limit: int = 3,
        minimum_score: float = MINIMUM_MATCH_SCORE,
    ) -> list[VolunteerMatchCandidate]:
        collection = get_volunteer_collection()
        projection = {
            "volunteer_id": 1,
            "name": 1,
            "email": 1,
            "skills": 1,
            "location": 1,
            "trust_score": 1,
            "tasks_completed": 1,
            "skills_embedding": 1,
            "is_active": 1,
        }
        volunteer_documents = [
            document
            async for document in collection.find({"is_active": True}, projection=projection)
        ]

        if not volunteer_documents:
            return []

        embedding_service = get_embedding_service()
        issue_embedding = np.asarray(
            await embedding_service.get_embedding(str(issue_document.get("description", "")).strip()),
            dtype="float32",
        )

        prepared_vectors: list[np.ndarray] = []
        eligible_documents: list[dict[str, Any]] = []

        for document in volunteer_documents:
            embedding = document.get("skills_embedding")
            if not isinstance(embedding, list) or not embedding:
                continue

            prepared_vectors.append(self._prepare_vector(embedding))
            eligible_documents.append(document)

        if not prepared_vectors:
            return []

        volunteer_matrix = np.vstack(prepared_vectors).astype("float32")
        skill_similarities = np.clip(volunteer_matrix @ issue_embedding, 0.0, 1.0)
        location_scores = np.asarray(
            [self._calculate_location_match(issue_document, document.get("location", {})) for document in eligible_documents],
            dtype="float32",
        )
        performance_scores = np.asarray(
            [self._calculate_performance_boost(float(document.get("trust_score", 0.0))) for document in eligible_documents],
            dtype="float32",
        )
        match_scores = (skill_similarities + location_scores + performance_scores) / 3.0

        ranked_indices = np.argsort(-match_scores)
        matches: list[VolunteerMatchCandidate] = []

        for index in ranked_indices:
            match_score = float(match_scores[index])
            if match_score < minimum_score:
                continue

            document = eligible_documents[int(index)]
            matches.append(
                VolunteerMatchCandidate(
                    volunteer_id=str(document["volunteer_id"]),
                    name=str(document["name"]),
                    email=str(document["email"]),
                    match_score=match_score,
                    skill_similarity=float(skill_similarities[index]),
                    location_match=float(location_scores[index]),
                    performance_boost=float(performance_scores[index]),
                    skills=str(document["skills"]),
                    trust_score=float(document.get("trust_score", 0.0)),
                    tasks_completed=int(document.get("tasks_completed", 0)),
                )
            )

            if len(matches) >= limit:
                break

        return matches

    def _calculate_location_match(self, issue_document: dict[str, Any], volunteer_location: dict[str, Any]) -> float:
        normalized_issue_location = self._normalize_text(str(issue_document.get("location", "")))
        issue_location_details = issue_document.get("location_details") or {}

        issue_city = self._normalize_text(str(issue_location_details.get("city", ""))) or normalized_issue_location
        issue_district = self._normalize_text(str(issue_location_details.get("district", "")))
        issue_state = self._normalize_text(str(issue_location_details.get("state", "")))

        volunteer_city = self._normalize_text(str(volunteer_location.get("city", "")))
        volunteer_district = self._normalize_text(str(volunteer_location.get("district", "")))
        volunteer_state = self._normalize_text(str(volunteer_location.get("state", "")))

        if issue_city and volunteer_city and issue_city == volunteer_city:
            return 1.0

        if issue_district and volunteer_district and issue_district == volunteer_district and issue_city != volunteer_city:
            return 0.7

        if issue_state and volunteer_state and issue_state == volunteer_state and issue_district != volunteer_district:
            return 0.4

        if normalized_issue_location and volunteer_district and (
            normalized_issue_location == volunteer_district
            or normalized_issue_location in volunteer_district
            or volunteer_district in normalized_issue_location
        ):
            return 0.7

        if normalized_issue_location and volunteer_state and (
            normalized_issue_location == volunteer_state
            or normalized_issue_location in volunteer_state
            or volunteer_state in normalized_issue_location
        ):
            return 0.4

        return 0.0

    def _calculate_performance_boost(self, trust_score: float) -> float:
        return max(0.0, min(trust_score / 100.0, 1.0))

    def _prepare_vector(self, embedding: list[float]) -> np.ndarray:
        vector = np.asarray(embedding, dtype="float32").reshape(-1)
        if vector.shape[0] < TARGET_EMBEDDING_DIMENSION:
            padded_vector = np.zeros(TARGET_EMBEDDING_DIMENSION, dtype="float32")
            padded_vector[: vector.shape[0]] = vector
            vector = padded_vector
        elif vector.shape[0] > TARGET_EMBEDDING_DIMENSION:
            vector = vector[:TARGET_EMBEDDING_DIMENSION]

        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        return vector

    def _normalize_text(self, value: str) -> str:
        return " ".join(value.casefold().split())


@lru_cache(maxsize=1)
def get_matching_engine() -> VolunteerMatchingEngine:
    return VolunteerMatchingEngine()
