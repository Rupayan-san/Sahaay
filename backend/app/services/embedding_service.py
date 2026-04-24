from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

import faiss
import numpy as np
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from sentence_transformers import SentenceTransformer

from app.core.config import get_settings
from app.core.database import get_issue_collection
from app.models.issue import ExtractedIssue, IssueRecord, IssueSeverity, IssueStatus

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
TARGET_EMBEDDING_DIMENSION = 768
SEVERITY_FACTORS: dict[IssueSeverity, float] = {
    IssueSeverity.CRITICAL: 1.0,
    IssueSeverity.HIGH: 22 / 30,
    IssueSeverity.MEDIUM: 15 / 30,
    IssueSeverity.LOW: 7 / 30,
}


@dataclass(slots=True)
class AggregationResult:
    issue: IssueRecord
    matched_existing: bool
    similarity: float | None = None


class EmbeddingService:
    """Embeddings, FAISS similarity search, and issue aggregation."""

    def __init__(self) -> None:
        self._model: SentenceTransformer | None = None
        self._index: faiss.IndexFlatIP = faiss.IndexFlatIP(TARGET_EMBEDDING_DIMENSION)
        self._faiss_to_mongo: dict[int, str] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Rebuild the in-memory FAISS index from MongoDB on startup."""
        collection = get_issue_collection()
        await self._ensure_indexes(collection)

        documents = [document async for document in collection.find({}).sort("created_at", ASCENDING)]
        vectors: list[np.ndarray] = []
        mongo_ids: list[str] = []

        for document in documents:
            embedding = document.get("embedding")
            if not isinstance(embedding, list) or not embedding:
                description = str(document.get("description", "")).strip()
                if not description:
                    logger.warning("Skipping issue %s during FAISS rebuild because no description exists", document.get("_id"))
                    continue

                embedding = await self.get_embedding(description)
                await collection.update_one(
                    {"_id": document["_id"]},
                    {"$set": {"embedding": embedding, "updated_at": document.get("updated_at", datetime.now(timezone.utc))}},
                )

            vectors.append(self._prepare_vector(embedding))
            mongo_ids.append(str(document["_id"]))

        async with self._lock:
            self._index = faiss.IndexFlatIP(TARGET_EMBEDDING_DIMENSION)
            self._faiss_to_mongo = {}

            if vectors:
                matrix = np.vstack(vectors).astype("float32")
                self._index.add(matrix)
                self._faiss_to_mongo = {position: mongo_id for position, mongo_id in enumerate(mongo_ids)}

        logger.info("Rebuilt FAISS issue index with %s vectors", len(mongo_ids))

    async def get_embedding(self, text: str) -> list[float]:
        """Generate a normalized embedding vector with the service target dimension."""
        if not text.strip():
            raise ValueError("Cannot generate an embedding for empty text")

        vector = await asyncio.to_thread(self._encode_sync, text)
        return vector.tolist()

    async def upsert_issue(self, extracted_issue: ExtractedIssue) -> AggregationResult:
        """Aggregate a newly extracted issue into MongoDB and the FAISS index."""
        embedding = await self.get_embedding(extracted_issue.description)
        collection = get_issue_collection()
        similarity_threshold = get_settings().issue_similarity_threshold

        async with self._lock:
            match = await self._find_similar_issue(
                collection=collection,
                extracted_issue=extracted_issue,
                embedding=embedding,
                similarity_threshold=similarity_threshold,
            )
            current_time = datetime.now(timezone.utc)

            if match is not None:
                matched_document, similarity = match
                merged_severity = self._merge_severity(matched_document["severity"], extracted_issue.severity)
                updated_report_count = int(matched_document["report_count"]) + 1
                priority_score = self.calculate_priority_score(
                    report_count=updated_report_count,
                    severity=merged_severity,
                    reference_time=current_time,
                )

                updated_document = await collection.find_one_and_update(
                    {"_id": matched_document["_id"]},
                    {
                        "$set": {
                            "severity": merged_severity.value,
                            "priority_score": priority_score,
                            "updated_at": current_time,
                        },
                        "$inc": {"report_count": 1},
                    },
                    return_document=ReturnDocument.AFTER,
                )

                if updated_document is None:
                    raise RuntimeError("Failed to update matched issue")

                return AggregationResult(
                    issue=IssueRecord.from_mongo(updated_document),
                    matched_existing=True,
                    similarity=similarity,
                )

            document = self._build_issue_document(
                extracted_issue=extracted_issue,
                embedding=embedding,
                current_time=current_time,
            )
            insert_result = await collection.insert_one(document)
            document["_id"] = insert_result.inserted_id
            self._append_to_index(insert_result.inserted_id, embedding)

            return AggregationResult(
                issue=IssueRecord.from_mongo(document),
                matched_existing=False,
                similarity=None,
            )

    async def list_issues(
        self,
        *,
        limit: int = 50,
        skip: int = 0,
        status: IssueStatus | None = None,
        category: str | None = None,
        location: str | None = None,
    ) -> list[IssueRecord]:
        collection = get_issue_collection()
        query: dict[str, Any] = {}

        if status is not None:
            query["status"] = status.value
        if category is not None:
            query["category"] = category
        if location is not None:
            query["location"] = {"$regex": f"^{re.escape(location)}$", "$options": "i"}

        cursor = collection.find(query).sort(
            [("priority_score", DESCENDING), ("updated_at", DESCENDING), ("created_at", DESCENDING)]
        )
        documents = await cursor.skip(skip).limit(limit).to_list(length=limit)
        return [IssueRecord.from_mongo(document) for document in documents]

    def calculate_priority_score(
        self,
        *,
        report_count: int,
        severity: IssueSeverity,
        reference_time: datetime,
    ) -> int:
        severity_factor = SEVERITY_FACTORS[severity]
        recency_factor = self._recency_factor(reference_time)
        score = (report_count * 20) + (severity_factor * 30) + (recency_factor * 10)
        return min(100, int(round(score)))

    async def _find_similar_issue(
        self,
        *,
        collection: Any,
        extracted_issue: ExtractedIssue,
        embedding: list[float],
        similarity_threshold: float,
    ) -> tuple[dict[str, Any], float] | None:
        if self._index.ntotal == 0:
            return None

        query_vector = np.array([embedding], dtype="float32")
        faiss.normalize_L2(query_vector)
        top_k = min(10, self._index.ntotal)
        similarities, indices = self._index.search(query_vector, top_k)

        for similarity, faiss_index in zip(similarities[0], indices[0], strict=False):
            if faiss_index < 0 or float(similarity) <= similarity_threshold:
                continue

            mongo_issue_id = self._faiss_to_mongo.get(int(faiss_index))
            if mongo_issue_id is None:
                continue

            matched_document = await collection.find_one({"_id": ObjectId(mongo_issue_id)})
            if matched_document is None:
                continue

            if (
                matched_document.get("category") == extracted_issue.category.value
                and self._normalize_location(str(matched_document.get("location", "")))
                == self._normalize_location(extracted_issue.location)
            ):
                return matched_document, float(similarity)

        return None

    async def _ensure_indexes(self, collection: Any) -> None:
        await collection.create_index("issue_id", unique=True)
        await collection.create_index([("priority_score", DESCENDING), ("updated_at", DESCENDING)])
        await collection.create_index([("category", ASCENDING), ("location", ASCENDING)])

    def _encode_sync(self, text: str) -> np.ndarray:
        model = self._get_model()
        raw_vector = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        vector = np.asarray(raw_vector, dtype="float32").reshape(-1)

        # all-MiniLM-L6-v2 yields 384 dimensions. We pad to the platform's required 768-d schema.
        if vector.shape[0] < TARGET_EMBEDDING_DIMENSION:
            padded_vector = np.zeros(TARGET_EMBEDDING_DIMENSION, dtype="float32")
            padded_vector[: vector.shape[0]] = vector
            vector = padded_vector
        elif vector.shape[0] > TARGET_EMBEDDING_DIMENSION:
            vector = vector[:TARGET_EMBEDDING_DIMENSION]

        matrix = np.array([vector], dtype="float32")
        faiss.normalize_L2(matrix)
        return matrix[0]

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("Loading sentence-transformers model '%s'", EMBEDDING_MODEL_NAME)
            self._model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        return self._model

    def _prepare_vector(self, embedding: list[float]) -> np.ndarray:
        vector = np.asarray(embedding, dtype="float32").reshape(-1)
        if vector.shape[0] != TARGET_EMBEDDING_DIMENSION:
            if vector.shape[0] < TARGET_EMBEDDING_DIMENSION:
                padded_vector = np.zeros(TARGET_EMBEDDING_DIMENSION, dtype="float32")
                padded_vector[: vector.shape[0]] = vector
                vector = padded_vector
            else:
                vector = vector[:TARGET_EMBEDDING_DIMENSION]

        matrix = np.array([vector], dtype="float32")
        faiss.normalize_L2(matrix)
        return matrix[0]

    def _append_to_index(self, mongo_id: ObjectId, embedding: list[float]) -> None:
        vector = np.array([embedding], dtype="float32")
        faiss.normalize_L2(vector)
        self._index.add(vector)
        self._faiss_to_mongo[self._index.ntotal - 1] = str(mongo_id)

    def _build_issue_document(
        self,
        *,
        extracted_issue: ExtractedIssue,
        embedding: list[float],
        current_time: datetime,
    ) -> dict[str, Any]:
        priority_score = self.calculate_priority_score(
            report_count=1,
            severity=extracted_issue.severity,
            reference_time=current_time,
        )
        return {
            "issue_id": str(uuid.uuid4()),
            "title": extracted_issue.title,
            "category": extracted_issue.category.value,
            "location": extracted_issue.location,
            "severity": extracted_issue.severity.value,
            "description": extracted_issue.description,
            "report_count": 1,
            "priority_score": priority_score,
            "embedding": embedding,
            "created_at": current_time,
            "updated_at": current_time,
            "status": IssueStatus.OPEN.value,
        }

    def _merge_severity(self, current_severity: str, new_severity: IssueSeverity) -> IssueSeverity:
        current = IssueSeverity(current_severity)
        return current if SEVERITY_FACTORS[current] >= SEVERITY_FACTORS[new_severity] else new_severity

    def _normalize_location(self, location: str) -> str:
        return " ".join(location.casefold().split())

    def _recency_factor(self, reference_time: datetime) -> float:
        now = datetime.now(timezone.utc)
        age = now - reference_time.astimezone(timezone.utc)
        if age <= timedelta(hours=24):
            return 1.0
        if age <= timedelta(hours=48):
            return 0.5
        return 0.0


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
