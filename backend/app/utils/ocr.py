from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytesseract
from PIL import ExifTags, Image, UnidentifiedImageError

logger = logging.getLogger(__name__)


class OCRProcessingError(Exception):
    """Raised when image OCR cannot be completed successfully."""


def extract_text_and_metadata(image_path: str | Path) -> tuple[str, dict[str, Any]]:
    """Run OCR on an image and return the extracted text plus image metadata."""
    resolved_path = Path(image_path)

    try:
        with Image.open(resolved_path) as image:
            width, height = image.size
            metadata: dict[str, Any] = {
                "image_size": f"{width}x{height}",
                "image_format": image.format,
                "image_mode": image.mode,
            }

            exif_metadata = _extract_exif_metadata(image)
            metadata["has_exif"] = bool(exif_metadata)
            if exif_metadata:
                metadata["exif"] = exif_metadata

            extracted_text = pytesseract.image_to_string(image).strip()
    except UnidentifiedImageError as exc:
        logger.warning("Unsupported image payload received: %s", resolved_path, exc_info=exc)
        raise OCRProcessingError("Invalid image file") from exc
    except (OSError, RuntimeError, pytesseract.TesseractError) as exc:
        logger.exception("OCR processing failed for %s", resolved_path)
        raise OCRProcessingError("Image OCR processing failed") from exc

    if len("".join(extracted_text.split())) < 5:
        raise OCRProcessingError("No readable text found in image")

    return extracted_text, metadata


def _extract_exif_metadata(image: Image.Image) -> dict[str, Any]:
    exif_payload: dict[str, Any] = {}

    try:
        exif = image.getexif()
    except (AttributeError, OSError) as exc:
        logger.warning("Could not read EXIF metadata", exc_info=exc)
        return exif_payload

    if not exif:
        return exif_payload

    for tag_id, value in exif.items():
        tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
        if tag_name == "GPSInfo" and isinstance(value, dict):
            exif_payload[tag_name] = {
                ExifTags.GPSTAGS.get(gps_tag, str(gps_tag)): _serialize_exif_value(gps_value)
                for gps_tag, gps_value in value.items()
            }
            continue

        exif_payload[tag_name] = _serialize_exif_value(value)

    return exif_payload


def _serialize_exif_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (list, tuple)):
        return [_serialize_exif_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize_exif_value(item) for key, item in value.items()}
    return str(value)
