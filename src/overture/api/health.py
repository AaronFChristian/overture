"""Health check endpoint.

Deliberately dependency-free right now: it does not touch the database.
Once the DB layer lands (session 2), this becomes two checks — liveness
(is the process up) and readiness (can it reach Postgres) — because
conflating them makes container orchestrators restart a healthy process
just because its database had a blip.
"""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="overture")
