"""Setup and connection endpoints. Health lives here so the UI has one place to poll."""

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["setup"])


@router.get("/health")
def get_health() -> dict[str, str]:
    return {"status": "ok", "source": settings.source, "database": str(settings.database_path)}
