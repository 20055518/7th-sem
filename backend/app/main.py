from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient

from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Phase 1 foundation for the Smart QR-Based Hospital Patient Journey Management System.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

mongo_client = MongoClient(
    settings.mongodb_uri,
    serverSelectionTimeoutMS=2000,
)


@app.get(f"{settings.api_prefix}/db-health", tags=["system"])
def database_health() -> dict[str, str]:
    try:
        mongo_client.admin.command("ping")
        return {"status": "ok", "database": "MongoDB connected"}
    except Exception:
        return {"status": "error", "database": "MongoDB unavailable"}

@app.get(f"{settings.api_prefix}/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """Lightweight readiness check; database connectivity is added in Phase 2."""
    return {"status": "ok", "service": settings.app_name, "phase": "1"}
