from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import faiss
import numpy as np
import requests
import torch
import torch.nn as nn
from PIL import ExifTags, Image, UnidentifiedImageError
from pymongo import ASCENDING, ReturnDocument
from requests import HTTPError
from torchvision.models import ResNet50_Weights, resnet50

from app.core.config import get_settings
from app.core.database import get_verification_collection
from app.models.verification import (
    AIGeneratedCheck,
    DuplicateCheck,
    ImageVerificationResponse,
    ImageVerificationSummary,
    ReverseSearchCheck,
    VerificationChecks,
    VerificationRecord,
    VerificationVerdict,
)
from app.utils.image_hash import HashBundle, compute_hash_bundle, hash_bundle_similarity

logger = logging.getLogger(__name__)

GOOGLE_CUSTOM_SEARCH_ENDPOINT = "https://customsearch.googleapis.com/customsearch/v1"
GOOGLE_FREE_DAILY_LIMIT = 100
IMAGE_EMBEDDING_DIMENSION = 2048
KNOWN_AI_SOFTWARE_MARKERS = (
    "midjourney",
    "dall-e",
    "dalle",
    "stable diffusion",
    "sdxl",
    "automatic1111",
    "comfyui",
    "fooocus",
)


class ImageVerificationError(Exception):
    """Raised when an image cannot be processed for verification."""


class ReverseSearchRateLimitError(Exception):
    """Raised when the Google Custom Search quota is exhausted."""


@dataclass(slots=True)
class LoadedImage:
    image_path: str
    resolved_path: Path
    image: Image.Image
    exif_data: dict[str, Any]
    sha256: str
    public_url: str | None


class ImageVerificationService:
    """3-layer image verification using Google search, perceptual hashes, and FAISS."""

    def __init__(self) -> None:
        self._duplicate_index: faiss.IndexFlatIP = faiss.IndexFlatIP(IMAGE_EMBEDDING_DIMENSION)
        self._faiss_to_image_path: dict[int, str] = {}
        self._indexed_paths: set[str] = set()
        self._known_ai_hashes: dict[str, HashBundle] = {}
        self._reverse_search_cache: dict[str, ReverseSearchCheck] = {}
        self._reverse_search_day: date | None = None
        self._reverse_search_calls_today = 0
        self._duplicate_lock = asyncio.Lock()
        self._reverse_search_lock = asyncio.Lock()
        self._image_model: nn.Module | None = None
        self._image_preprocess: Any = None
        self._project_root = Path(__file__).resolve().parents[3]
        self._backend_root = Path(__file__).resolve().parents[2]

    async def initialize(self) -> None:
        collection = get_verification_collection()
        await collection.create_index([("assignment_id", ASCENDING), ("image_path", ASCENDING)], unique=True)
        await collection.create_index("verification_id", unique=True)
        await collection.create_index([("overall_verdict", ASCENDING), ("created_at", ASCENDING)])

        documents = [
            document
            async for document in collection.find(
                {},
                projection={
                    "image_path": 1,
                    "embedding": 1,
                    "hash_artifacts": 1,
                    "checks.ai_generated.passed": 1,
                },
            ).sort("created_at", ASCENDING)
        ]

        vectors: list[np.ndarray] = []
        indexed_paths: list[str] = []
        known_ai_hashes: dict[str, HashBundle] = {}

        for document in documents:
            image_path = str(document.get("image_path", "")).strip()
            if not image_path:
                continue

            embedding_payload = document.get("embedding")
            if isinstance(embedding_payload, list) and embedding_payload and image_path not in indexed_paths:
                vectors.append(self._prepare_embedding(embedding_payload))
                indexed_paths.append(image_path)

            ai_passed = (((document.get("checks") or {}).get("ai_generated") or {}).get("passed"))
            hash_artifacts = document.get("hash_artifacts")
            if ai_passed is False and isinstance(hash_artifacts, dict):
                try:
                    known_ai_hashes[image_path] = HashBundle.from_mapping(hash_artifacts)
                except KeyError:
                    logger.warning("Skipping malformed AI hash artifacts for %s", image_path)

        async with self._duplicate_lock:
            self._duplicate_index = faiss.IndexFlatIP(IMAGE_EMBEDDING_DIMENSION)
            self._faiss_to_image_path = {}
            self._indexed_paths = set(indexed_paths)
            if vectors:
                matrix = np.vstack(vectors).astype("float32")
                self._duplicate_index.add(matrix)
                self._faiss_to_image_path = {position: path for position, path in enumerate(indexed_paths)}

        self._known_ai_hashes = known_ai_hashes
        logger.info("Rebuilt verification duplicate index with %s images", len(indexed_paths))

    async def verify_assignment_images(self, assignment_id: str, image_paths: list[str]) -> ImageVerificationResponse:
        records: list[VerificationRecord] = []

        for image_path in image_paths:
            records.append(await self.verify_image(assignment_id=assignment_id, image_path=image_path))

        summary = ImageVerificationSummary(
            total_images=len(records),
            passed=sum(1 for record in records if record.overall_verdict == VerificationVerdict.PASS),
            failed=sum(1 for record in records if record.overall_verdict == VerificationVerdict.FAIL),
            suspicious=sum(1 for record in records if record.overall_verdict == VerificationVerdict.SUSPICIOUS),
        )
        return ImageVerificationResponse(results=[record.to_result() for record in records], summary=summary)

    async def verify_image(self, *, assignment_id: str, image_path: str) -> VerificationRecord:
        try:
            loaded_image = await asyncio.to_thread(self._load_image_sync, image_path)
        except ImageVerificationError:
            logger.exception("Cannot process image for verification: %s", image_path)
            raise

        try:
            reverse_search_check = await self._run_reverse_search(loaded_image)
            ai_generated_check, hash_bundle = await asyncio.to_thread(self._run_ai_generated_check_sync, loaded_image)
            duplicate_check, embedding = await self._run_duplicate_check(loaded_image)
        finally:
            loaded_image.image.close()

        overall_verdict = self._compute_overall_verdict(
            reverse_search_check=reverse_search_check,
            ai_generated_check=ai_generated_check,
            duplicate_check=duplicate_check,
        )
        final_confidence = round(
            (
                reverse_search_check.confidence
                + ai_generated_check.confidence
                + duplicate_check.confidence
            )
            / 3,
            4,
        )

        verification_record = VerificationRecord(
            verification_id=str(uuid.uuid4()),
            assignment_id=assignment_id,
            image_path=image_path,
            checks=VerificationChecks(
                reverse_search=reverse_search_check,
                ai_generated=ai_generated_check,
                duplicate_check=duplicate_check,
            ),
            overall_verdict=overall_verdict,
            final_confidence=final_confidence,
            created_at=datetime.now(timezone.utc),
        )
        persisted_record = await self._persist_verification(
            verification_record=verification_record,
            embedding=embedding,
            hash_bundle=hash_bundle,
            file_digest=loaded_image.sha256,
        )

        await self._add_to_duplicate_index(image_path=image_path, embedding=embedding)
        if ai_generated_check.passed is False:
            self._known_ai_hashes[image_path] = hash_bundle

        if overall_verdict != VerificationVerdict.PASS:
            logger.warning("Image verification flagged %s as %s", image_path, overall_verdict.value)

        return persisted_record

    async def _persist_verification(
        self,
        *,
        verification_record: VerificationRecord,
        embedding: list[float],
        hash_bundle: HashBundle,
        file_digest: str,
    ) -> VerificationRecord:
        collection = get_verification_collection()
        payload = verification_record.model_dump(mode="json")
        payload.update(
            {
                "embedding": embedding,
                "hash_artifacts": hash_bundle.as_dict(),
                "file_digest": file_digest,
            }
        )

        updated_document = await collection.find_one_and_update(
            {"assignment_id": verification_record.assignment_id, "image_path": verification_record.image_path},
            {"$set": payload},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        if updated_document is None:
            updated_document = await collection.find_one(
                {"assignment_id": verification_record.assignment_id, "image_path": verification_record.image_path}
            )

        if updated_document is None:
            raise RuntimeError("Failed to persist verification record")

        return VerificationRecord.from_mongo(updated_document)

    async def _run_reverse_search(self, loaded_image: LoadedImage) -> ReverseSearchCheck:
        settings = get_settings()
        if not settings.google_search_api_key or not settings.google_search_engine_id:
            return ReverseSearchCheck(
                passed=None,
                confidence=0.5,
                found_urls=[],
                notes="not_checked: Google Custom Search credentials are not configured",
            )

        if not loaded_image.public_url:
            return ReverseSearchCheck(
                passed=None,
                confidence=0.5,
                found_urls=[],
                notes="not_checked: public image URL unavailable for Google search",
            )

        cached = self._reverse_search_cache.get(loaded_image.sha256)
        if cached is not None:
            return cached.model_copy(deep=True)

        async with self._reverse_search_lock:
            self._reset_google_usage_if_needed()
            if self._reverse_search_calls_today >= GOOGLE_FREE_DAILY_LIMIT:
                result = ReverseSearchCheck(
                    passed=None,
                    confidence=0.5,
                    found_urls=[],
                    notes="not_checked: Google Custom Search daily quota exceeded",
                )
                self._reverse_search_cache[loaded_image.sha256] = result
                return result.model_copy(deep=True)
            self._reverse_search_calls_today += 1

        try:
            found_urls = await asyncio.to_thread(self._fetch_reverse_search_urls_sync, loaded_image.public_url)
        except ReverseSearchRateLimitError:
            async with self._reverse_search_lock:
                self._reverse_search_calls_today = GOOGLE_FREE_DAILY_LIMIT
            result = ReverseSearchCheck(
                passed=None,
                confidence=0.5,
                found_urls=[],
                notes="not_checked: Google Custom Search quota exceeded",
            )
            self._reverse_search_cache[loaded_image.sha256] = result
            return result.model_copy(deep=True)
        except Exception:  # noqa: BLE001
            logger.exception("Reverse search failed for %s", loaded_image.image_path)
            result = ReverseSearchCheck(
                passed=None,
                confidence=0.5,
                found_urls=[],
                notes="not_checked: reverse search request failed",
            )
            self._reverse_search_cache[loaded_image.sha256] = result
            return result.model_copy(deep=True)

        confidence = max(0.0, 1.0 - (len(found_urls) / 10))
        passed = len(found_urls) < 2
        notes = "No indexed matches found" if not found_urls else f"Found {len(found_urls)} indexed matches"
        result = ReverseSearchCheck(
            passed=passed,
            confidence=round(confidence, 4),
            found_urls=found_urls,
            notes=notes,
        )
        self._reverse_search_cache[loaded_image.sha256] = result
        return result.model_copy(deep=True)

    def _fetch_reverse_search_urls_sync(self, public_url: str) -> list[str]:
        settings = get_settings()
        file_name = Path(urlparse(public_url).path).name
        file_stem = Path(file_name).stem.replace("_", " ").replace("-", " ").strip()
        query = f'"{file_name}"'
        if file_stem and file_stem.lower() != file_name.lower():
            query = f'{query} "{file_stem}"'

        params = {
            "key": settings.google_search_api_key,
            "cx": settings.google_search_engine_id,
            "q": query,
            "searchType": "image",
            "linkSite": public_url,
            "num": 10,
            "safe": "active",
        }

        response = requests.get(GOOGLE_CUSTOM_SEARCH_ENDPOINT, params=params, timeout=10)
        try:
            response.raise_for_status()
        except HTTPError as exc:
            body = response.text.lower()
            if response.status_code in {403, 429} and any(
                marker in body for marker in ("quota", "rate limit", "daily limit", "exceeded")
            ):
                raise ReverseSearchRateLimitError from exc
            raise

        payload = response.json()
        items = payload.get("items") or []
        unique_urls: list[str] = []
        seen_urls: set[str] = set()
        for item in items:
            link = str(item.get("link", "")).strip()
            if not link or link in seen_urls:
                continue
            seen_urls.add(link)
            unique_urls.append(link)
        return unique_urls

    def _run_ai_generated_check_sync(self, loaded_image: LoadedImage) -> tuple[AIGeneratedCheck, HashBundle]:
        hash_bundle = compute_hash_bundle(loaded_image.image)
        indicators: list[str] = []
        software = str(loaded_image.exif_data.get("Software", "")).strip()
        software_lower = software.casefold()

        if software and any(marker in software_lower for marker in KNOWN_AI_SOFTWARE_MARKERS):
            indicators.append(f"Software metadata indicates AI tool: {software}")
            return (
                AIGeneratedCheck(
                    passed=False,
                    confidence=1.0,
                    indicators=indicators,
                    notes="AI generation marker found in EXIF metadata",
                ),
                hash_bundle,
            )

        max_similarity = 0.0
        matched_reference: str | None = None
        for reference_path, known_hash in self._known_ai_hashes.items():
            similarity = hash_bundle_similarity(hash_bundle, known_hash)
            if similarity > max_similarity:
                max_similarity = similarity
                matched_reference = reference_path

        if max_similarity >= 0.9 and matched_reference is not None:
            indicators.append(f"Hash similarity {max_similarity:.2f} to known AI image: {matched_reference}")
            return (
                AIGeneratedCheck(
                    passed=False,
                    confidence=round(max_similarity, 4),
                    indicators=indicators,
                    notes="Perceptual hash closely matches a known AI-generated image",
                ),
                hash_bundle,
            )

        confidence = 1.0 if software else 0.5
        notes = (
            "No AI metadata detected and hash similarity below threshold"
            if software
            else "No explicit software metadata; hash comparison below threshold"
        )
        return (
            AIGeneratedCheck(
                passed=True,
                confidence=confidence,
                indicators=indicators,
                notes=notes,
            ),
            hash_bundle,
        )

    async def _run_duplicate_check(self, loaded_image: LoadedImage) -> tuple[DuplicateCheck, list[float]]:
        embedding = await asyncio.to_thread(self._compute_image_embedding_sync, loaded_image.image)
        query_vector = self._prepare_embedding(embedding)

        async with self._duplicate_lock:
            if self._duplicate_index.ntotal == 0:
                return (
                    DuplicateCheck(
                        passed=None,
                        confidence=0.5,
                        similar_images=[],
                        notes="not_checked: duplicate index is empty",
                    ),
                    query_vector.tolist(),
                )

            top_k = min(5, self._duplicate_index.ntotal)
            scores, indices = self._duplicate_index.search(np.array([query_vector], dtype="float32"), top_k)

        max_similarity = 0.0
        similar_images: list[str] = []
        for score, index in zip(scores[0], indices[0], strict=False):
            if index < 0:
                continue

            matched_path = self._faiss_to_image_path.get(int(index))
            if not matched_path or matched_path == loaded_image.image_path:
                continue

            max_similarity = max(max_similarity, float(score))
            if float(score) > 0.95:
                similar_images.append(matched_path)

        passed = max_similarity < 0.95
        confidence = round(max(0.0, 1.0 - max_similarity), 4)
        notes = (
            "No similar historical images found"
            if passed
            else f"High similarity detected against {len(similar_images)} prior images"
        )
        return (
            DuplicateCheck(
                passed=passed,
                confidence=confidence,
                similar_images=similar_images,
                notes=notes,
            ),
            query_vector.tolist(),
        )

    async def _add_to_duplicate_index(self, *, image_path: str, embedding: list[float]) -> None:
        async with self._duplicate_lock:
            if image_path in self._indexed_paths:
                return
            vector = np.array([self._prepare_embedding(embedding)], dtype="float32")
            self._duplicate_index.add(vector)
            self._faiss_to_image_path[self._duplicate_index.ntotal - 1] = image_path
            self._indexed_paths.add(image_path)

    def _compute_overall_verdict(
        self,
        *,
        reverse_search_check: ReverseSearchCheck,
        ai_generated_check: AIGeneratedCheck,
        duplicate_check: DuplicateCheck,
    ) -> VerificationVerdict:
        failure_strengths = [
            self._reverse_failure_strength(reverse_search_check),
            self._ai_failure_strength(ai_generated_check),
            self._duplicate_failure_strength(duplicate_check),
        ]
        checks = [reverse_search_check, ai_generated_check, duplicate_check]

        if any(
            check.passed is False and strength > 0.8
            for check, strength in zip(checks, failure_strengths, strict=False)
        ):
            return VerificationVerdict.FAIL

        if any(check.passed is False for check in checks):
            return VerificationVerdict.SUSPICIOUS

        return VerificationVerdict.PASS

    def _reverse_failure_strength(self, check: ReverseSearchCheck) -> float:
        if check.passed is not False:
            return 0.0
        return min(len(check.found_urls) / 3, 1.0)

    def _ai_failure_strength(self, check: AIGeneratedCheck) -> float:
        if check.passed is not False:
            return 0.0
        return check.confidence

    def _duplicate_failure_strength(self, check: DuplicateCheck) -> float:
        if check.passed is not False or not check.similar_images:
            return 0.0
        return max(0.95, 1.0 - check.confidence)

    def _load_image_sync(self, image_path: str) -> LoadedImage:
        resolved_path = self._resolve_image_path(image_path)
        try:
            file_bytes = resolved_path.read_bytes()
            with Image.open(resolved_path) as image:
                exif_data = self._extract_exif_data(image)
                rgb_image = image.convert("RGB")
        except FileNotFoundError as exc:
            raise ImageVerificationError(f"Image file not found: {image_path}. Please resubmit the assignment images.") from exc
        except UnidentifiedImageError as exc:
            raise ImageVerificationError(f"Uploaded file is not a readable image: {image_path}") from exc
        except OSError as exc:
            raise ImageVerificationError(f"Cannot process image: {image_path}") from exc

        return LoadedImage(
            image_path=image_path,
            resolved_path=resolved_path,
            image=rgb_image,
            exif_data=exif_data,
            sha256=hashlib.sha256(file_bytes).hexdigest(),
            public_url=self._build_public_url(image_path),
        )

    def _resolve_image_path(self, image_path: str) -> Path:
        normalized = image_path.strip().replace("\\", "/")
        if not normalized:
            raise ImageVerificationError("Cannot process image")

        parsed = urlparse(normalized)
        if parsed.scheme in {"http", "https"}:
            normalized = parsed.path

        relative_path = normalized.lstrip("/")
        candidates = [
            Path(normalized),
            self._project_root / relative_path,
            self._backend_root / relative_path,
            Path.cwd() / relative_path,
        ]

        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()

        raise ImageVerificationError(f"Image file not found: {image_path}. Please resubmit the assignment images.")

    def _extract_exif_data(self, image: Image.Image) -> dict[str, Any]:
        exif_payload: dict[str, Any] = {}
        try:
            exif = image.getexif()
        except (AttributeError, OSError):
            return exif_payload

        if not exif:
            return exif_payload

        for tag_id, value in exif.items():
            tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
            if isinstance(value, bytes):
                exif_payload[tag_name] = value.decode("utf-8", errors="replace")
            else:
                exif_payload[tag_name] = value
        return exif_payload

    def _build_public_url(self, image_path: str) -> str | None:
        normalized = image_path.strip().replace("\\", "/")
        if normalized.startswith("http://") or normalized.startswith("https://"):
            return normalized

        settings = get_settings()
        if not settings.public_upload_base_url:
            return None

        return urljoin(settings.public_upload_base_url.rstrip("/") + "/", normalized.lstrip("/"))

    def _compute_image_embedding_sync(self, image: Image.Image) -> np.ndarray:
        model, preprocess = self._get_resnet_components()
        tensor = preprocess(image).unsqueeze(0)
        with torch.inference_mode():
            vector = model(tensor).squeeze(0).cpu().numpy().astype("float32")
        return self._prepare_embedding(vector)

    def _get_resnet_components(self) -> tuple[nn.Module, Any]:
        if self._image_model is None or self._image_preprocess is None:
            weights = ResNet50_Weights.DEFAULT
            model = resnet50(weights=weights)
            model.fc = nn.Identity()
            model.eval()
            self._image_model = model
            self._image_preprocess = weights.transforms()
        return self._image_model, self._image_preprocess

    def _prepare_embedding(self, embedding: list[float] | np.ndarray) -> np.ndarray:
        vector = np.asarray(embedding, dtype="float32").reshape(-1)
        if vector.shape[0] < IMAGE_EMBEDDING_DIMENSION:
            padded_vector = np.zeros(IMAGE_EMBEDDING_DIMENSION, dtype="float32")
            padded_vector[: vector.shape[0]] = vector
            vector = padded_vector
        elif vector.shape[0] > IMAGE_EMBEDDING_DIMENSION:
            vector = vector[:IMAGE_EMBEDDING_DIMENSION]

        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        return vector.astype("float32")

    def _reset_google_usage_if_needed(self) -> None:
        today = date.today()
        if self._reverse_search_day != today:
            self._reverse_search_day = today
            self._reverse_search_calls_today = 0


def get_image_verification_service() -> ImageVerificationService:
    return _IMAGE_VERIFICATION_SERVICE


_IMAGE_VERIFICATION_SERVICE = ImageVerificationService()
