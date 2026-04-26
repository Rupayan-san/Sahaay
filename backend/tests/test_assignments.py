from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_apply_to_issue_as_volunteer(
    client: AsyncClient,
    seeded_issue: dict[str, object],
    seeded_volunteer: dict[str, object],
) -> None:
    response = await client.post(
        "/api/issues/test-issue-id/apply",
        headers={"X-Actor-Id": "vol-123", "X-Actor-Role": "volunteer"},
        json={"volunteer_id": "vol-123"},
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_apply_as_admin_rejected(
    client: AsyncClient,
    seeded_issue: dict[str, object],
    seeded_volunteer: dict[str, object],
) -> None:
    response = await client.post(
        "/api/issues/test-issue-id/apply",
        headers={"X-Actor-Id": "admin-123", "X-Actor-Role": "admin"},
        json={"volunteer_id": "vol-123"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_status_transition_invalid(
    client: AsyncClient,
    seeded_assignment: dict[str, object],
) -> None:
    response = await client.post(
        "/api/assignments/test-assignment-id/complete",
        headers={"X-Actor-Id": "admin-123", "X-Actor-Role": "admin"},
        json={"admin_id": "admin-123"},
    )

    assert response.status_code == 400
    assert "Cannot change from applied to completed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_submit_without_images(client: AsyncClient, test_database) -> None:
    now = datetime.now(timezone.utc)
    await test_database.get_collection("assignments").insert_one(
        {
            "_id": ObjectId(),
            "assignment_id": "submit-test-id",
            "issue_id": "test-issue-id",
            "volunteer_id": "vol-123",
            "status": "in_progress",
            "applied_at": now,
            "assigned_at": now,
            "started_at": now,
            "submitted_at": None,
            "completed_at": None,
            "submission_data": None,
            "admin_notes": None,
            "application_message": None,
            "created_at": now,
            "updated_at": now,
        }
    )

    response = await client.post(
        "/api/assignments/submit-test-id/submit",
        headers={"X-Actor-Id": "vol-123", "X-Actor-Role": "volunteer"},
        json={
            "submission_data": {
                "notes": "Finished the work",
                "before_images": [],
                "after_images": [],
            }
        },
    )

    assert response.status_code == 400
    assert "submission_data.after_images" in response.json()["detail"]


@pytest.mark.asyncio
async def test_submit_multipart_saves_uploaded_images(client: AsyncClient, test_database) -> None:
    now = datetime.now(timezone.utc)
    await test_database.get_collection("assignments").insert_one(
        {
            "_id": ObjectId(),
            "assignment_id": "multipart-submit-id",
            "issue_id": "test-issue-id",
            "volunteer_id": "vol-123",
            "status": "in_progress",
            "applied_at": now,
            "assigned_at": now,
            "started_at": now,
            "submitted_at": None,
            "completed_at": None,
            "submission_data": None,
            "admin_notes": None,
            "application_message": None,
            "created_at": now,
            "updated_at": now,
        }
    )

    image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )

    response = await client.post(
        "/api/assignments/multipart-submit-id/submit",
        headers={"X-Actor-Id": "vol-123", "X-Actor-Role": "volunteer"},
        data={"notes": "Finished the work"},
        files={
            "after_images": ("after.png", image_bytes, "image/png"),
        },
    )

    assert response.status_code == 200
    submission_data = response.json()["data"]["submission_data"]
    assert len(submission_data["after_images"]) == 1

    stored_path = Path(__file__).resolve().parents[1] / submission_data["after_images"][0]
    try:
        assert stored_path.exists()
        assert stored_path.read_bytes() == image_bytes
    finally:
        stored_path.unlink(missing_ok=True)
