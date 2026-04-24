from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AssignmentStatus(str, Enum):
    APPLIED = "applied"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    VERIFIED = "verified"
    COMPLETED = "completed"
    REJECTED = "rejected"


class SubmissionData(BaseModel):
    images: list[str] = Field(default_factory=list)
    notes: str | None = None
    before_images: list[str] = Field(default_factory=list)
    after_images: list[str] = Field(default_factory=list)

    @field_validator("images", "before_images", "after_images", mode="before")
    @classmethod
    def normalize_image_lists(cls, value: Any) -> Any:
        if value is None:
            return []
        return value

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None

    @field_validator("images", "before_images", "after_images")
    @classmethod
    def validate_image_paths(cls, value: list[str]) -> list[str]:
        normalized_paths = [" ".join(path.strip().split()) for path in value if str(path).strip()]
        return normalized_paths

    def all_images(self) -> list[str]:
        merged: list[str] = []
        for image_group in (self.images, self.before_images, self.after_images):
            for image in image_group:
                if image not in merged:
                    merged.append(image)
        return merged


class AssignmentApplyRequest(BaseModel):
    volunteer_id: str = Field(..., min_length=1)
    message: str | None = None

    @field_validator("volunteer_id")
    @classmethod
    def normalize_volunteer_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("volunteer_id is required")
        return normalized

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None


class AssignmentAdminActionRequest(BaseModel):
    admin_id: str = Field(..., min_length=1)

    @field_validator("admin_id")
    @classmethod
    def normalize_admin_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("admin_id is required")
        return normalized


class AssignmentSubmitRequest(BaseModel):
    submission_data: SubmissionData

    @model_validator(mode="after")
    def validate_submission_requirements(self) -> "AssignmentSubmitRequest":
        if not self.submission_data.after_images:
            raise ValueError("submission_data.after_images is required")
        if not self.submission_data.all_images():
            raise ValueError("submission_data.after_images is required")
        return self


class AssignmentRejectRequest(AssignmentAdminActionRequest):
    admin_notes: str = Field(..., min_length=1, max_length=2000)

    @field_validator("admin_notes")
    @classmethod
    def normalize_admin_notes(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("admin_notes is required")
        return normalized


class AssignmentRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    assignment_id: str
    issue_id: str
    volunteer_id: str
    status: AssignmentStatus
    applied_at: datetime
    assigned_at: datetime | None = None
    started_at: datetime | None = None
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    submission_data: SubmissionData | None = None
    admin_notes: str | None = None
    application_message: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_mongo(cls, document: dict[str, Any]) -> "AssignmentRecord":
        return cls.model_validate(
            {
                "id": str(document["_id"]),
                "assignment_id": document["assignment_id"],
                "issue_id": document["issue_id"],
                "volunteer_id": document["volunteer_id"],
                "status": document["status"],
                "applied_at": document["applied_at"],
                "assigned_at": document.get("assigned_at"),
                "started_at": document.get("started_at"),
                "submitted_at": document.get("submitted_at"),
                "completed_at": document.get("completed_at"),
                "submission_data": document.get("submission_data"),
                "admin_notes": document.get("admin_notes"),
                "application_message": document.get("application_message"),
                "created_at": document["created_at"],
                "updated_at": document["updated_at"],
            }
        )


class AssignmentResponse(BaseModel):
    success: bool = True
    data: AssignmentRecord
