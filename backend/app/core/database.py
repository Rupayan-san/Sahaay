from __future__ import annotations

import logging
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient[Any] | None = None
_database: AsyncIOMotorDatabase[Any] | None = None


async def connect_to_mongo() -> None:
    """Initialize the shared MongoDB connection."""
    global _client, _database

    if _client is not None and _database is not None:
        return

    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_uri, uuidRepresentation="standard")
    await client.admin.command("ping")

    _client = client
    _database = client[settings.mongodb_db_name]
    logger.info("Connected to MongoDB database '%s'", settings.mongodb_db_name)


async def close_mongo_connection() -> None:
    """Close the shared MongoDB connection."""
    global _client, _database

    if _client is not None:
        _client.close()
        logger.info("Closed MongoDB connection")

    _client = None
    _database = None


def get_database() -> AsyncIOMotorDatabase[Any]:
    if _database is None:
        raise RuntimeError("MongoDB connection has not been initialized")

    return _database


def get_mongo_client() -> AsyncIOMotorClient[Any]:
    if _client is None:
        raise RuntimeError("MongoDB connection has not been initialized")

    return _client


def get_issue_collection() -> AsyncIOMotorCollection[Any]:
    return get_database().get_collection("issues")


def get_volunteer_collection() -> AsyncIOMotorCollection[Any]:
    return get_database().get_collection("volunteers")


def get_assignment_collection() -> AsyncIOMotorCollection[Any]:
    return get_database().get_collection("assignments")


def get_verification_collection() -> AsyncIOMotorCollection[Any]:
    return get_database().get_collection("verifications")


def get_rating_collection() -> AsyncIOMotorCollection[Any]:
    return get_database().get_collection("ratings")
