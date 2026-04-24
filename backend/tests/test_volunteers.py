from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_volunteer_success(client: AsyncClient) -> None:
    response = await client.post(
        "/api/volunteers",
        json={
            "name": "John",
            "email": "john@test.com",
            "skills": "plumber pipe repair",
            "location": {"city": "Kolkata", "district": "North", "state": "WB"},
        },
    )

    assert response.status_code == 201
    assert response.json()["data"]["volunteer_id"] == "test-vol-id"


@pytest.mark.asyncio
async def test_register_volunteer_missing_email(client: AsyncClient) -> None:
    response = await client.post(
        "/api/volunteers",
        json={
            "name": "John",
            "skills": "plumber pipe repair",
            "location": {"city": "Kolkata", "district": "North", "state": "WB"},
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_volunteers(client: AsyncClient) -> None:
    response = await client.get("/api/volunteers")

    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


@pytest.mark.asyncio
async def test_match_volunteers_for_issue(client: AsyncClient) -> None:
    response = await client.post("/api/issues/test-issue-id/match")

    assert response.status_code == 200
    assert isinstance(response.json()["matches"], list)


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, service_mocks: dict[str, object]) -> None:
    service_mocks["matching"].register_volunteer.side_effect = ValueError("Email already registered")

    response = await client.post(
        "/api/volunteers",
        json={
            "name": "John",
            "email": "john@test.com",
            "skills": "plumber pipe repair",
            "location": {"city": "Kolkata", "district": "North", "state": "WB"},
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"
