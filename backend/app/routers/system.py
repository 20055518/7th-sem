from fastapi import APIRouter
from app.config import get_settings
from app.database import mongo_client

settings = get_settings()
router = APIRouter(tags=["system"])


@router.get("/db-health")
def database_health() -> dict[str, str]:
    try:
        mongo_client.admin.command("ping")
        return {
            "status": "ok",
            "database": "MongoDB connected",
        }
    except Exception:
        return {
            "status": "error",
            "database": "MongoDB unavailable",
        }


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "phase": "5 - Nurse Triage",
    }
