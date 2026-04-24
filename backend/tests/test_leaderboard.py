from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_leaderboard_default(client: AsyncClient) -> None:
    response = await client.get("/api/leaderboard")

    assert response.status_code == 200
    assert isinstance(response.json()["leaderboard"], list)


@pytest.mark.asyncio
async def test_get_leaderboard_by_trust_score(client: AsyncClient) -> None:
    response = await client.get("/api/leaderboard?category=trust_score&limit=5")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_leaderboard_monthly(client: AsyncClient) -> None:
    response = await client.get("/api/leaderboard?timeframe=month")

    assert response.status_code == 200
