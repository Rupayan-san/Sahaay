from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True, slots=True)
class Settings:
    gemini_api_key: str | None
    gemini_model_name: str
    mongodb_uri: str
    mongodb_db_name: str
    issue_similarity_threshold: float
    gmail_user: str | None
    gmail_app_password: str | None
    admin_notification_email: str | None
    google_search_api_key: str | None
    google_search_engine_id: str | None
    public_upload_base_url: str | None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        gemini_model_name=os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash-exp"),
        mongodb_uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        mongodb_db_name=os.getenv("MONGODB_DB_NAME", "sahaay_db"),
        issue_similarity_threshold=float(os.getenv("ISSUE_SIMILARITY_THRESHOLD", "0.85")),
        gmail_user=os.getenv("GMAIL_USER"),
        gmail_app_password=os.getenv("GMAIL_APP_PASSWORD"),
        admin_notification_email=os.getenv("ADMIN_NOTIFICATION_EMAIL"),
        google_search_api_key=os.getenv("GOOGLE_SEARCH_API_KEY"),
        google_search_engine_id=os.getenv("GOOGLE_SEARCH_ENGINE_ID"),
        public_upload_base_url=os.getenv("PUBLIC_UPLOAD_BASE_URL"),
    )
