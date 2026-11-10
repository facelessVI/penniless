"""Setup and connection endpoints. Health lives here so the UI has one place to poll."""

from fastapi import APIRouter

from app.config import DATABASE_PATH, SOURCE

router = APIRouter(tags=["setup"])


@router.get("/health")
def get_health() -> dict[str, str]:
    return {"status": "ok", "source": SOURCE, "database": str(DATABASE_PATH)}
