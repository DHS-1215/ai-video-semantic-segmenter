from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.health import HealthPayload, HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def read_health() -> HealthResponse:
    settings = get_settings()
    payload = HealthPayload(
        status="ok",
        service="api",
        environment=settings.app_env,
    )
    return HealthResponse(success=True, data=payload)
