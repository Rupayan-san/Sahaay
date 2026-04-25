from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from app.models.ingestion import FormIngestionRequest, IngestionData, IngestionResponse, SourceType
from app.utils.ocr import OCRProcessingError, extract_text_and_metadata
from app.utils.whisper import SpeechTranscriptionError, transcribe_audio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ingestion"])

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg"}
AUDIO_EXTENSIONS = {".mp3", ".wav"}
AUDIO_CONTENT_TYPES = {"audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav"}


@router.post("/ingest", response_model=IngestionResponse, status_code=status.HTTP_200_OK)
async def ingest(request: Request) -> IngestionResponse:
    """Ingest image, audio, or JSON form submissions into a unified response shape."""
    content_type = request.headers.get("content-type", "").lower()

    if "application/json" in content_type:
        return await _handle_json_payload(request)

    if "multipart/form-data" in content_type:
        return await _handle_multipart_payload(request)

    if not content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file uploaded",
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported content type. Use multipart/form-data or application/json.",
    )


async def _handle_json_payload(request: Request) -> IngestionResponse:
    try:
        payload = await request.json()
    except ValueError as exc:
        logger.warning("Invalid JSON payload received", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="JSON payload must be an object",
        )

    try:
        form_payload = FormIngestionRequest(**payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_format_validation_error(exc),
        ) from exc

    metadata: dict[str, str] = {}
    if form_payload.category:
        metadata["category"] = form_payload.category
    if form_payload.severity:
        metadata["severity"] = form_payload.severity

    return IngestionResponse(
        data=IngestionData(
            content=form_payload.description,
            source_type=SourceType.FORM,
            metadata=metadata,
            location=form_payload.location,
        )
    )


async def _handle_multipart_payload(request: Request) -> IngestionResponse:
    try:
        form_data = await request.form()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Invalid multipart payload received", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid multipart form payload",
        ) from exc

    upload = _extract_single_upload(form_data)
    source_type = _detect_source_type(upload)

    if source_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Upload PNG, JPG, JPEG, MP3, or WAV.",
        )

    try:
        file_bytes = await upload.read()

        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty",
            )

        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            detail = (
                "Image file too large (max 10MB)"
                if source_type == SourceType.IMAGE
                else "Audio file too large (max 10MB)"
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

        temp_path = _write_temp_file(file_bytes, Path(upload.filename or "").suffix)

        try:
            if source_type == SourceType.IMAGE:
                try:
                    content, metadata = extract_text_and_metadata(temp_path)
                except OCRProcessingError as exc:
                    logger.warning("Image OCR failed; creating fallback image report", exc_info=exc)
                    content = _build_image_fallback_content(upload)
                    metadata = {
                        "ocr_status": "failed",
                        "ocr_error": str(exc),
                        "filename": upload.filename or "uploaded image",
                        "content_type": upload.content_type or "unknown",
                    }
            else:
                content, metadata = transcribe_audio(temp_path)
        except SpeechTranscriptionError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        finally:
            _delete_temp_file(temp_path)
    finally:
        await upload.close()

    return IngestionResponse(
        data=IngestionData(
            content=content,
            source_type=source_type,
            metadata=metadata,
        )
    )


def _extract_single_upload(form_data: object) -> UploadFile:
    uploads = [value for value in form_data.values() if isinstance(value, UploadFile)]

    if not uploads:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file uploaded",
        )

    if len(uploads) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide exactly one file per request",
        )

    return uploads[0]


def _detect_source_type(upload: UploadFile) -> SourceType | None:
    suffix = Path(upload.filename or "").suffix.lower()
    content_type = (upload.content_type or "").lower()

    if suffix in IMAGE_EXTENSIONS or content_type in IMAGE_CONTENT_TYPES:
        return SourceType.IMAGE

    if suffix in AUDIO_EXTENSIONS or content_type in AUDIO_CONTENT_TYPES:
        return SourceType.AUDIO

    return None


def _build_image_fallback_content(upload: UploadFile) -> str:
    filename = Path(upload.filename or "uploaded image").name
    return (
        "Image report uploaded for review. "
        f"Source file: {filename}. "
        "OCR could not extract readable text, so the issue details should be reviewed manually."
    )


def _write_temp_file(file_bytes: bytes, suffix: str) -> Path:
    temp_dir = _resolve_temp_dir()
    normalized_suffix = suffix if suffix else ".bin"

    with tempfile.NamedTemporaryFile(
        mode="wb",
        delete=False,
        dir=temp_dir,
        suffix=normalized_suffix,
    ) as temp_file:
        temp_file.write(file_bytes)
        return Path(temp_file.name)


def _resolve_temp_dir() -> str:
    """Use /tmp on Unix-like systems and the platform temp dir on Windows."""
    preferred_tmp = Path("/tmp")
    if os.name == "nt":
        preferred_tmp = Path(tempfile.gettempdir())

    preferred_tmp.mkdir(parents=True, exist_ok=True)
    return str(preferred_tmp)


def _delete_temp_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Failed to delete temp file %s", path, exc_info=True)


def _format_validation_error(exc: ValidationError) -> str:
    messages: list[str] = []

    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", []))
        message = error.get("msg", "Invalid value")
        messages.append(f"{location}: {message}" if location else message)

    return "; ".join(messages) or "Invalid request payload"
