from datetime import datetime, timezone
from fastapi import APIRouter
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])

@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(timestamp=datetime.now(timezone.utc))
