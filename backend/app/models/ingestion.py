from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, validator


class SourceType(str, Enum):
    IMAGE = "image"
    AUDIO = "audio"
    FORM = "form"


class FormIngestionRequest(BaseModel):
    description: str = Field(..., min_length=10, description="Detailed issue description.")
    location: str = Field(..., min_length=1, description="Location where the issue was reported.")
    category: str | None = Field(default=None, description="Optional issue category.")
    severity: str | None = Field(default=None, description="Optional issue severity.")

    @validator("description", "location", pre=True)
    def strip_required_fields(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
        return value

    @validator("description")
    def validate_description(cls, value: str) -> str:
        if len(value) < 10:
            raise ValueError("description must be at least 10 characters long")
        return value

    @validator("location")
    def validate_location(cls, value: str) -> str:
        if not value:
            raise ValueError("location is required")
        return value

    @validator("category", "severity", pre=True)
    def normalize_optional_fields(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class IngestionData(BaseModel):
    content: str
    source_type: SourceType
    metadata: dict[str, Any] = Field(default_factory=dict)
    location: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IngestionResponse(BaseModel):
    success: bool = True
    data: IngestionData
