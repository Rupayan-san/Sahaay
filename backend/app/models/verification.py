from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class VerificationVerdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SUSPICIOUS = "suspicious"


class ReverseSearchCheck(BaseModel):
    passed: bool | None
    confidence: float = Field(..., ge=0.0, le=1.0)
    found_urls: list[str] = Field(default_factory=list)
    notes: str


class AIGeneratedCheck(BaseModel):
    passed: bool | None
    confidence: float = Field(..., ge=0.0, le=1.0)
    indicators: list[str] = Field(default_factory=list)
    notes: str


class DuplicateCheck(BaseModel):
    passed: bool | None
    confidence: float = Field(..., ge=0.0, le=1.0)
    similar_images: list[str] = Field(default_factory=list)
    notes: str


class VerificationChecks(BaseModel):
    reverse_search: ReverseSearchCheck
    ai_generated: AIGeneratedCheck
    duplicate_check: DuplicateCheck


class VerificationResult(BaseModel):
    image_path: str
    checks: VerificationChecks
    overall_verdict: VerificationVerdict
    final_confidence: float = Field(..., ge=0.0, le=1.0)


class VerificationRecord(VerificationResult):
    verification_id: str
    assignment_id: str
    created_at: datetime

    @classmethod
    def from_mongo(cls, document: dict[str, Any]) -> "VerificationRecord":
        return cls.model_validate(
            {
                "verification_id": document["verification_id"],
                "assignment_id": document["assignment_id"],
                "image_path": document["image_path"],
                "checks": document["checks"],
                "overall_verdict": document["overall_verdict"],
                "final_confidence": float(document["final_confidence"]),
                "created_at": document["created_at"],
            }
        )

    def to_result(self) -> VerificationResult:
        return VerificationResult(
            image_path=self.image_path,
            checks=self.checks,
            overall_verdict=self.overall_verdict,
            final_confidence=self.final_confidence,
        )


class ImageVerificationRequest(BaseModel):
    image_paths: list[str] = Field(..., min_length=1)

    @field_validator("image_paths")
    @classmethod
    def normalize_image_paths(cls, value: list[str]) -> list[str]:
        normalized_paths = [" ".join(path.strip().split()) for path in value if str(path).strip()]
        if not normalized_paths:
            raise ValueError("image_paths is required")
        return normalized_paths


class ImageVerificationSummary(BaseModel):
    total_images: int
    passed: int
    failed: int
    suspicious: int


class ImageVerificationResponse(BaseModel):
    results: list[VerificationResult]
    summary: ImageVerificationSummary
