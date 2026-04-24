from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_issue_success(client: AsyncClient) -> None:
    response = await client.post("/api/issues", json={"raw_text": "Water pump broken at Village A"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["matched_existing"] is False
    assert payload["data"]["issue_id"] == "test-issue-id"
    assert payload["data"]["title"] == "Water pump broken"


@pytest.mark.asyncio
async def test_create_issue_empty_text(client: AsyncClient) -> None:
    response = await client.post("/api/issues", json={"raw_text": ""})

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_issues_returns_list(client: AsyncClient) -> None:
    response = await client.get("/api/issues")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["data"], list)


@pytest.mark.asyncio
async def test_get_issues_with_filters(client: AsyncClient) -> None:
    response = await client.get("/api/issues?status=open&category=water&limit=10")

    assert response.status_code == 200
