from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class IssueCategory(str, Enum):
    WATER = "water"
    MEDICAL = "medical"
    FOOD = "food"
    INFRASTRUCTURE = "infrastructure"
    SANITATION = "sanitation"
    ELECTRICITY = "electricity"
    EDUCATION = "education"
    OTHER = "other"


class IssueSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IssueStatus(str, Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    COMPLETED = "completed"


class IssueCreateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    raw_text: str = Field(
        ...,
        min_length=5,
        validation_alias=AliasChoices("raw_text", "content"),
        description="Raw issue text produced by the ingestion service.",
    )

    @field_validator("raw_text")
    @classmethod
    def validate_raw_text(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 5:
            raise ValueError("raw_text must be at least 5 characters long")
        return normalized


class ExtractedIssue(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    title: str = Field(..., min_length=5, max_length=120)
    category: IssueCategory
    location: str = Field(..., min_length=1, max_length=200)
    severity: IssueSeverity
    description: str = Field(..., min_length=10, max_length=2000)

    @field_validator("title", "location", "description")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("field cannot be empty")
        return normalized


class IssueRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    issue_id: str
    title: str
    category: IssueCategory
    location: str
    severity: IssueSeverity
    description: str
    report_count: int
    priority_score: int
    created_at: datetime
    updated_at: datetime
    status: IssueStatus

    @classmethod
    def from_mongo(cls, document: dict[str, Any]) -> "IssueRecord":
        return cls.model_validate(
            {
                "id": str(document["_id"]),
                "issue_id": document["issue_id"],
                "title": document["title"],
                "category": document["category"],
                "location": document["location"],
                "severity": document["severity"],
                "description": document["description"],
                "report_count": int(document["report_count"]),
                "priority_score": int(document["priority_score"]),
                "created_at": document["created_at"],
                "updated_at": document["updated_at"],
                "status": document["status"],
            }
        )


class IssueUpsertResponse(BaseModel):
    success: bool = True
    matched_existing: bool
    similarity: float | None = None
    data: IssueRecord


class IssueListResponse(BaseModel):
    success: bool = True
    data: list[IssueRecord]
