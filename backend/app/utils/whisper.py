from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import whisper

logger = logging.getLogger(__name__)

WHISPER_MODEL_NAME = "base"


class SpeechTranscriptionError(Exception):
    """Raised when audio transcription cannot be completed successfully."""


@lru_cache(maxsize=1)
def _get_model() -> Any:
    logger.info("Loading Whisper model '%s'", WHISPER_MODEL_NAME)
    return whisper.load_model(WHISPER_MODEL_NAME)


def transcribe_audio(audio_path: str | Path) -> tuple[str, dict[str, Any]]:
    """Transcribe speech from an audio file using the Whisper base model."""
    resolved_path = Path(audio_path)

    try:
        model = _get_model()
        result = model.transcribe(str(resolved_path), fp16=False, verbose=False)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Whisper transcription failed for %s", resolved_path)
        raise SpeechTranscriptionError("Speech transcription failed") from exc

    transcribed_text = str(result.get("text", "")).strip()
    if not transcribed_text:
        raise SpeechTranscriptionError("Speech transcription failed")

    segments = result.get("segments") or []
    metadata: dict[str, Any] = {
        "model": WHISPER_MODEL_NAME,
        "segment_count": len(segments),
    }

    language = result.get("language")
    if language:
        metadata["language"] = language

    if segments:
        metadata["duration_seconds"] = round(float(segments[-1].get("end", 0.0)), 2)

    return transcribed_text, metadata
