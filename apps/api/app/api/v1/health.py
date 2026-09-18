"""Health and readiness endpoints. Unauthenticated; safe metadata only."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    environment: str
    version: str


API_VERSION = "0.1.0"


@router.get("", response_model=HealthResponse)
async def health() -> HealthResponse:
    from app.core.config import settings

    return HealthResponse(
        status="ok",
        environment=settings.ENVIRONMENT,
        version=API_VERSION,
    )
