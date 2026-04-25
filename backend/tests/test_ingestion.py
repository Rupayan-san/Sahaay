from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_text_ingestion_success(client: AsyncClient) -> None:
    response = await client.post(
        "/api/ingest",
        json={
            "description": "Water pump broken at Village A",
            "location": "Village A",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["content"] == "Water pump broken at Village A"
    assert payload["data"]["source_type"] == "form"


@pytest.mark.asyncio
async def test_text_ingestion_too_short(client: AsyncClient) -> None:
    response = await client.post(
        "/api/ingest",
        json={
            "description": "bad",
            "location": "Village A",
        },
    )

    assert response.status_code == 400
    assert "at least 10 characters" in response.json()["detail"]


@pytest.mark.asyncio
async def test_image_ingestion_no_file_returns_error(client: AsyncClient) -> None:
    response = await client.post(
        "/api/ingest",
        files={},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "No file uploaded"


@pytest.mark.asyncio
async def test_image_ingestion_accepts_multipart_upload(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_extract_text_and_metadata(_: object) -> tuple[str, dict[str, str]]:
        return "Broken road near Village A", {"source": "test-image"}

    monkeypatch.setattr("app.api.routes.ingestion.extract_text_and_metadata", fake_extract_text_and_metadata)

    response = await client.post(
        "/api/ingest",
        files={"file": ("report.png", b"fake-image-bytes", "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["content"] == "Broken road near Village A"
    assert payload["data"]["source_type"] == "image"


@pytest.mark.asyncio
async def test_image_ingestion_falls_back_when_ocr_fails(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.utils.ocr import OCRProcessingError

    def fake_extract_text_and_metadata(_: object) -> tuple[str, dict[str, str]]:
        raise OCRProcessingError("Image OCR processing failed")

    monkeypatch.setattr("app.api.routes.ingestion.extract_text_and_metadata", fake_extract_text_and_metadata)

    response = await client.post(
        "/api/ingest",
        files={"file": ("field-photo.jpg", b"fake-image-bytes", "image/jpeg")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "Image report uploaded for review" in payload["data"]["content"]
    assert payload["data"]["source_type"] == "image"
    assert payload["data"]["metadata"]["ocr_status"] == "failed"


@pytest.mark.asyncio
async def test_ingest_creates_issue_when_forwarded_to_issue_endpoint(
    client: AsyncClient,
    service_mocks: dict[str, object],
) -> None:
    ingest_response = await client.post(
        "/api/ingest",
        json={
            "description": "Water pump broken at Village A",
            "location": "Village A",
        },
    )

    assert ingest_response.status_code == 200
    content = ingest_response.json()["data"]["content"]

    issue_response = await client.post("/api/issues", json={"raw_text": content})

    assert issue_response.status_code == 200
    service_mocks["gemini"].extract_issue.assert_awaited_once_with("Water pump broken at Village A")
    service_mocks["embedding"].upsert_issue.assert_awaited_once()
