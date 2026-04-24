from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class LeaderboardCategory(str, Enum):
    POINTS = "points"
    TRUST_SCORE = "trust_score"


class LeaderboardTimeframe(str, Enum):
    ALL_TIME = "all_time"
    MONTH = "month"
    WEEK = "week"


class RatingCreateRequest(BaseModel):
    stars: int = Field(..., ge=1, le=5)
    review: str | None = Field(default=None, max_length=2000)

    @field_validator("review")
    @classmethod
    def normalize_review(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None


class RatingRecord(BaseModel):
    rating_id: str
    assignment_id: str
    volunteer_id: str
    admin_id: str
    stars: int
    review: str | None = None
    created_at: datetime

    @classmethod
    def from_mongo(cls, document: dict[str, Any]) -> "RatingRecord":
        return cls.model_validate(
            {
                "rating_id": document["rating_id"],
                "assignment_id": document["assignment_id"],
                "volunteer_id": document["volunteer_id"],
                "admin_id": document["admin_id"],
                "stars": int(document["stars"]),
                "review": document.get("review"),
                "created_at": document["created_at"],
            }
        )


class RatingResponse(BaseModel):
    success: bool = True
    data: RatingRecord
    awarded_points: int
    trust_score: float


class LeaderboardEntry(BaseModel):
    rank: int
    volunteer_id: str
    name: str
    points: int
    trust_score: float
    tasks_completed: int
    badges: list[str]


class LeaderboardResponse(BaseModel):
    leaderboard: list[LeaderboardEntry]
