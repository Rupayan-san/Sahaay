from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class VolunteerLocation(BaseModel):
    city: str = Field(..., min_length=1, max_length=120)
    district: str = Field(..., min_length=1, max_length=120)
    state: str = Field(..., min_length=1, max_length=120)
    coordinates: tuple[float, float] | None = None

    @field_validator("city", "district", "state")
    @classmethod
    def normalize_location_text(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("location fields cannot be empty")
        return normalized

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, value: tuple[float, float] | None) -> tuple[float, float] | None:
        if value is None:
            return value

        latitude, longitude = value
        if not -90 <= latitude <= 90:
            raise ValueError("latitude must be between -90 and 90")
        if not -180 <= longitude <= 180:
            raise ValueError("longitude must be between -180 and 180")
        return value


class VolunteerCreateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    skills: str = Field(..., min_length=5, max_length=1000)
    location: VolunteerLocation
    tasks_completed: int = Field(default=0, ge=0)
    tasks_failed: int = Field(default=0, ge=0)
    average_rating: float = Field(default=0.0, ge=0.0, le=5.0)
    is_active: bool = True

    @field_validator("name", "skills")
    @classmethod
    def normalize_text_fields(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("field cannot be empty")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class VolunteerRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    volunteer_id: str
    name: str
    email: EmailStr
    skills: str
    location: VolunteerLocation
    trust_score: float
    tasks_completed: int
    tasks_failed: int
    total_images_submitted: int
    failed_verifications: int
    average_rating: float
    points: int
    badges: list[str]
    rank: int
    created_at: datetime
    is_active: bool

    @classmethod
    def from_mongo(cls, document: dict[str, Any]) -> "VolunteerRecord":
        return cls.model_validate(
            {
                "id": str(document["_id"]),
                "volunteer_id": document["volunteer_id"],
                "name": document["name"],
                "email": document["email"],
                "skills": document["skills"],
                "location": document["location"],
                "trust_score": float(document["trust_score"]),
                "tasks_completed": int(document["tasks_completed"]),
                "tasks_failed": int(document["tasks_failed"]),
                "total_images_submitted": int(document.get("total_images_submitted", 0)),
                "failed_verifications": int(document.get("failed_verifications", 0)),
                "average_rating": float(document["average_rating"]),
                "points": int(document.get("points", 0)),
                "badges": [str(badge) for badge in document.get("badges", [])],
                "rank": int(document.get("rank", 0)),
                "created_at": document["created_at"],
                "is_active": bool(document["is_active"]),
            }
        )


class VolunteerListResponse(BaseModel):
    success: bool = True
    data: list[VolunteerRecord]


class VolunteerResponse(BaseModel):
    success: bool = True
    data: VolunteerRecord


class VolunteerMatchBreakdown(BaseModel):
    skill_similarity: float
    location_match: float
    performance_boost: float


class VolunteerMatch(BaseModel):
    volunteer_id: str
    name: str
    match_score: float
    breakdown: VolunteerMatchBreakdown
    skills: str
    trust_score: float
    tasks_completed: int


class VolunteerMatchResponse(BaseModel):
    matches: list[VolunteerMatch]
