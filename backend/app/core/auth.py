from __future__ import annotations

from enum import Enum

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel, Field


class ActorRole(str, Enum):
    ADMIN = "admin"
    VOLUNTEER = "volunteer"


class AuthenticatedActor(BaseModel):
    actor_id: str = Field(..., min_length=1)
    role: ActorRole


async def get_current_actor(
    actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
    actor_role: ActorRole | None = Header(default=None, alias="X-Actor-Role"),
) -> AuthenticatedActor:
    if not actor_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Actor-Id header",
        )

    if actor_role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Actor-Role header",
        )

    return AuthenticatedActor(actor_id=actor_id.strip(), role=actor_role)


async def require_admin(actor: AuthenticatedActor = Depends(get_current_actor)) -> AuthenticatedActor:
    if actor.role != ActorRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return actor


async def require_volunteer(actor: AuthenticatedActor = Depends(get_current_actor)) -> AuthenticatedActor:
    if actor.role != ActorRole.VOLUNTEER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Volunteer only")
    return actor
