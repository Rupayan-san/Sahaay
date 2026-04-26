from __future__ import annotations

import json
import logging
import re
from functools import lru_cache

import google.generativeai as genai
from langchain_core.prompts import PromptTemplate
from pydantic import ValidationError

from app.core.config import get_settings
from app.models.issue import ExtractedIssue, IssueCategory, IssueSeverity

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT_TEXT = """You are an issue extraction AI for a community coordination platform.

Extract the following from this report:
- title: Short 5-10 word summary of the problem
- category: ONE of [water, medical, food, infrastructure, sanitation, electricity, education, other]
- location: Specific place name (village/neighborhood/landmark)
- severity: ONE of [critical, high, medium, low]
- description: 2-3 sentence detailed description

Input text: {raw_text}

Return ONLY valid JSON:
{{
  "title": "...",
  "category": "...",
  "location": "...",
  "severity": "...",
  "description": "..."
}}
"""

SIMPLIFIED_RETRY_PROMPT_TEXT = """Extract issue data from the report below and return JSON only.

Allowed categories: water, medical, food, infrastructure, sanitation, electricity, education, other
Allowed severities: critical, high, medium, low

Report: {raw_text}

Return JSON with exactly these keys:
{{
  "title": "...",
  "category": "...",
  "location": "...",
  "severity": "...",
  "description": "..."
}}
"""

EXTRACTION_PROMPT = PromptTemplate.from_template(EXTRACTION_PROMPT_TEXT)
SIMPLIFIED_RETRY_PROMPT = PromptTemplate.from_template(SIMPLIFIED_RETRY_PROMPT_TEXT)
GEMINI_MODEL_NAME = "gemini-2.0-flash-exp"


class GeminiExtractionService:
    """Wrapper around Gemini for structured issue extraction."""

    def __init__(self) -> None:
        settings = get_settings()
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)

        self._model = genai.GenerativeModel(
            model_name=settings.gemini_model_name or GEMINI_MODEL_NAME,
            generation_config=genai.GenerationConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        )

    async def extract_issue(self, raw_text: str) -> ExtractedIssue:
        normalized_text = " ".join(raw_text.strip().split())
        if not normalized_text:
            raise ValueError("raw_text must not be empty")

        settings = get_settings()
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        try:
            return await self._extract_with_prompt(normalized_text, EXTRACTION_PROMPT)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            logger.warning("Gemini returned invalid structured output for input: %s", normalized_text, exc_info=exc)
        except Exception as exc:  # noqa: BLE001
            logger.error("Gemini API error for input: %s", normalized_text, exc_info=exc)
            return self._build_fallback_issue(normalized_text)

        try:
            return await self._extract_with_prompt(normalized_text, SIMPLIFIED_RETRY_PROMPT)
        except Exception as exc:  # noqa: BLE001
            logger.error("Gemini extraction failed after retry for input: %s", normalized_text, exc_info=exc)
            return self._build_fallback_issue(normalized_text)

    async def _extract_with_prompt(self, raw_text: str, prompt_template: PromptTemplate) -> ExtractedIssue:
        prompt = prompt_template.format(raw_text=raw_text)
        response = await self._model.generate_content_async(prompt)
        response_text = self._extract_response_text(response)
        response_payload = self._parse_json_response(response_text)
        return ExtractedIssue.model_validate(response_payload)

    def _extract_response_text(self, response: object) -> str:
        response_text = getattr(response, "text", "") or ""
        normalized = response_text.strip()
        if not normalized:
            raise ValueError("Gemini returned an empty response")
        return normalized

    def _parse_json_response(self, response_text: str) -> dict[str, object]:
        cleaned_text = response_text.strip()
        if cleaned_text.startswith("```"):
            cleaned_text = re.sub(r"^```(?:json)?\s*", "", cleaned_text)
            cleaned_text = re.sub(r"\s*```$", "", cleaned_text)

        try:
            payload = json.loads(cleaned_text)
        except json.JSONDecodeError:
            start = cleaned_text.find("{")
            end = cleaned_text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise
            payload = json.loads(cleaned_text[start : end + 1])

        if not isinstance(payload, dict):
            raise ValueError("Gemini response must be a JSON object")

        return payload

    def _build_fallback_issue(self, raw_text: str) -> ExtractedIssue:
        title_words = raw_text.split()
        title = " ".join(title_words[:8]).strip().rstrip(".,;:") or "Community issue reported"
        title = title[:120]

        location = self._guess_location(raw_text)
        description = raw_text[:2000]

        return ExtractedIssue(
            title=title,
            category=IssueCategory.OTHER,
            location=location,
            severity=IssueSeverity.MEDIUM,
            description=description,
        )

    def _guess_location(self, raw_text: str) -> str:
        location_match = re.search(r"\b(?:at|in|near)\s+([A-Z][\w\s-]{2,80})", raw_text)
        if location_match:
            return " ".join(location_match.group(1).strip().split())
        return "Unknown location"


@lru_cache(maxsize=1)
def get_gemini_service() -> GeminiExtractionService:
    return GeminiExtractionService()
